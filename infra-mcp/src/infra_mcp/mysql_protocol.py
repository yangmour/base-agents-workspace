"""Bounded transport for pinned PyMySQL 1.2.3 (private protocol API).

One connection belongs to one MCP operation. Its receive budget includes the
handshake, metadata and results, and cannot reset on each query or packet.
"""
from __future__ import annotations

import errno
import socket
import time
from importlib.metadata import version

from pymysql import err
from pymysql.connections import Connection
from pymysql.constants import CR

from .config import InfraError


class BoundedConnection(Connection):
    def __init__(self, *, max_response_bytes=1_048_576, operation_timeout=10, **kwargs):
        if type(max_response_bytes) is not int or not 1024 <= max_response_bytes <= 16_777_216:
            raise InfraError("invalid_config", "max_response_bytes must be between 1024 and 16777216")
        if (isinstance(operation_timeout, bool) or not isinstance(operation_timeout, (int, float))
                or not 0 < operation_timeout <= 120):
            raise InfraError("invalid_config", "operation_timeout must be greater than 0 and at most 120 seconds")
        if version("PyMySQL") != "1.2.3":
            raise InfraError("invalid_config", "Bounded MySQL transport requires PyMySQL 1.2.3")
        self.remaining_response_bytes = max_response_bytes
        self._deadline = time.monotonic() + operation_timeout
        self._attempted_connection = False
        self._sock = self._rfile = None
        super().__init__(**kwargs)

    def force_close(self):
        # Never use cursor.close(): unbuffered results may drain indefinitely.
        self._force_close()

    def check_deadline(self):
        remaining = self._deadline - time.monotonic()
        if remaining <= 0:
            self.force_close()
            raise InfraError("timeout", "MySQL operation deadline exceeded")
        return remaining

    def connect(self, sock=None):
        if self._attempted_connection:
            raise InfraError("backend_error", "MySQL operations never reconnect or retry automatically")
        self._attempted_connection = True
        self.check_deadline()
        if sock is None:
            sock = self._open_socket()
        self._sock = sock
        self._read_timeout = min(self._read_timeout or self.check_deadline(), self.check_deadline())
        super().connect(sock)
        self.check_deadline()

    def _open_socket(self):
        # socket.create_connection resets its timeout for every DNS address.
        # Share one deadline instead; blocking platform DNS itself is best effort.
        addresses = socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM)
        self.check_deadline()
        for family, kind, protocol, _, address in addresses:
            timeout = min(self.connect_timeout, self.check_deadline())
            candidate = socket.socket(family, kind, protocol)
            try:
                candidate.settimeout(timeout)
                candidate.connect(address)
                self.check_deadline()
                candidate.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                candidate.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                return candidate
            except OSError:
                candidate.close()
                self.check_deadline()
            except BaseException:
                candidate.close()
                raise
        raise err.OperationalError(CR.CR_CONN_HOST_ERROR, "MySQL connection could not be established")

    def _read_bytes(self, num_bytes):
        if num_bytes < 0 or num_bytes > self.remaining_response_bytes:
            self.force_close()
            raise InfraError("result_too_large", "MySQL response exceeds the connection receive limit; narrow the query")
        result = bytearray()
        # BufferedReader.read(n) may wait through arbitrarily many fragments.
        # read1 makes at most one underlying read, allowing deadline checks
        # between fragments as well as before allocating a declared packet.
        while len(result) < num_bytes:
            remaining = self.check_deadline()
            timeout = min(self._read_timeout or remaining, remaining)
            self._sock.settimeout(timeout)
            self._current_timeout = timeout
            try:
                chunk = self._rfile.read1(min(num_bytes - len(result), 65536))
            except OSError as error:
                if error.errno == errno.EINTR:
                    continue
                self.force_close()
                raise err.OperationalError(CR.CR_SERVER_LOST, "MySQL transport read failed") from None
            except BaseException:
                self.force_close()
                raise
            if not chunk:
                self.force_close()
                raise err.OperationalError(CR.CR_SERVER_LOST, "MySQL transport closed before completing the response")
            self.remaining_response_bytes -= len(chunk)
            result.extend(chunk)
            self.check_deadline()
        return bytes(result)

    def _write_bytes(self, data):
        remaining = self.check_deadline()
        self._write_timeout = min(self._write_timeout or remaining, remaining)
        super()._write_bytes(data)
        remaining = self.check_deadline()
        # TLS wrapping follows SSLRequest directly; it must inherit the updated
        # remaining budget rather than the timeout from before sendall.
        timeout = min(self._read_timeout or remaining, self._write_timeout, remaining)
        self._sock.settimeout(timeout)
        self._current_timeout = timeout
