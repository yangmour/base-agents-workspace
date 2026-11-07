"""Explicit redis-py 7.4.1 Python RESP2 parser with a wire-byte ceiling.

Never use hiredis or RESP3 here. The wrapper sits below SocketBuffer, including
SSL sockets, so neither fragmented lines nor aggregate arrays bypass the cap.
"""
from redis._parsers.resp2 import _RESP2Parser
from .config import InfraError


class _BudgetSocket:
    def __init__(self, sock, budget):
        self.sock, self.remaining = sock, budget
    def recv(self, size):
        if self.remaining <= 0:
            self.sock.close()
            raise InfraError('result_too_large', 'Redis response exceeds the wire-byte limit')
        data = self.sock.recv(min(size, self.remaining))
        self.remaining -= len(data)
        return data
    def settimeout(self, value): self.sock.settimeout(value)


class BoundedRESP2Parser(_RESP2Parser):
    MAX_REPLY_BYTES = 1048576

    def on_connect(self, connection):
        super().on_connect(connection)
        self._budget_socket = _BudgetSocket(connection._sock, self.MAX_REPLY_BYTES)
        self._buffer._sock = self._budget_socket
        # Reject an oversized declared bulk before SocketBuffer.read allocates.
        original_read = self._buffer.read
        def bounded_read(length):
            if length < 0 or length + 2 > self.MAX_REPLY_BYTES:
                connection._sock.close()
                raise InfraError('result_too_large', 'Redis bulk response exceeds the wire-byte limit')
            return original_read(length)
        self._buffer.read = bounded_read

    def read_response(self, disable_decoding=False):
        # SocketBuffer may prefetch following replies; count buffered data too.
        self._budget_socket.remaining = self.MAX_REPLY_BYTES - self._buffer.unread_bytes()
        try:
            return super().read_response(disable_decoding=disable_decoding)
        except (InfraError, RecursionError):
            self._budget_socket.sock.close()
            self.on_disconnect()
            raise InfraError('result_too_large', 'Redis response exceeds safe parser limits') from None
