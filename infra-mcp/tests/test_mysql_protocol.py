import io
import struct

import pytest
from pymysql.constants import CLIENT

from infra_mcp.config import InfraError
from infra_mcp.mysql_protocol import BoundedConnection


class Socket:
    def __init__(self):
        self.closed = False
        self.timeouts = []
        self.sent = []

    def settimeout(self, value):
        self.timeouts.append(value)

    def sendall(self, value):
        self.sent.append(value)

    def close(self):
        self.closed = True


class Reader(io.BytesIO):
    def __init__(self, payload, fragment=3):
        super().__init__(payload)
        self.received = 0
        self.fragment = fragment

    def read1(self, size):
        data = super().read(min(size, self.fragment))
        self.received += len(data)
        return data


def connection(payload=b"", budget=1024):
    conn = BoundedConnection(max_response_bytes=budget, operation_timeout=10,
                             defer_connect=True, ssl_disabled=True)
    sock, reader = Socket(), Reader(payload)
    conn._sock, conn._rfile = sock, reader
    conn._current_timeout = None
    conn._next_seq_id = 0
    return conn, sock, reader


def test_fragmented_packet_and_cumulative_budget():
    payload = b"hello"
    conn, sock, reader = connection(struct.pack("<I", len(payload)) + payload)
    assert conn._read_packet().get_all_data() == payload
    assert reader.received == 9
    assert conn.remaining_response_bytes == 1015
    assert not sock.closed
    conn.force_close()


def test_huge_declared_packet_rejected_before_body_allocation():
    conn, sock, reader = connection(struct.pack("<I", 16_000_000))
    with pytest.raises(InfraError) as error:
        conn._read_packet()
    assert error.value.code == "result_too_large"
    assert reader.received == 4
    assert sock.closed


def test_budget_is_not_reset_between_reads_or_queries():
    conn, sock, reader = connection(b"x" * 1100)
    assert len(conn._read_bytes(600)) == 600
    with pytest.raises(InfraError):
        conn._read_bytes(500)
    assert reader.received == 600
    assert sock.closed


def test_deadline_checked_between_fragments_not_just_packets(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("infra_mcp.mysql_protocol.time.monotonic", lambda: now[0])
    conn, sock, reader = connection(b"x" * 100)
    original = reader.read1
    def slow_read(size):
        now[0] += 6
        return original(size)
    reader.read1 = slow_read
    with pytest.raises(InfraError) as error:
        conn._read_bytes(100)
    assert error.value.code == "timeout"
    assert reader.received == 6
    assert sock.closed
    assert max(sock.timeouts) <= 10


def test_expired_deadline_prevents_writing(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("infra_mcp.mysql_protocol.time.monotonic", lambda: now[0])
    conn, sock, _ = connection()
    now[0] += 11
    with pytest.raises(InfraError):
        conn._write_bytes(b"COMMIT")
    assert not sock.sent
    assert sock.closed


def test_close_never_sends_quit_or_drains_pending_result():
    conn, sock, reader = connection(b"pending result")
    conn.force_close()
    conn.force_close()
    assert reader.received == 0
    assert not sock.sent
    assert sock.closed


def test_short_read_closes_connection():
    conn, sock, _ = connection(b"a")
    with pytest.raises(Exception):
        conn._read_bytes(20)
    assert sock.closed


def test_local_infile_and_multi_statements_are_not_negotiated():
    conn, _, _ = connection()
    assert not conn.client_flag & (CLIENT.MULTI_STATEMENTS | CLIENT.LOCAL_FILES)
    conn.force_close()


def test_connect_never_retries(monkeypatch):
    calls = []
    monkeypatch.setattr("pymysql.connections.Connection.connect", lambda *a, **k: calls.append(1))
    conn = BoundedConnection(operation_timeout=10, ssl_disabled=True, defer_connect=True)
    conn.connect(Socket())
    with pytest.raises(InfraError):
        conn.connect()
    assert calls == [1]


def test_multiple_dns_addresses_share_one_connect_deadline(monkeypatch):
    now, budgets, sockets = [100.0], [], []
    monkeypatch.setattr("infra_mcp.mysql_protocol.time.monotonic", lambda: now[0])
    monkeypatch.setattr("infra_mcp.mysql_protocol.socket.getaddrinfo", lambda *a: [
        (2, 1, 6, '', ('192.0.2.1', 3306)), (2, 1, 6, '', ('192.0.2.2', 3306))])
    class Unreachable(Socket):
        def connect(self, address):
            budget = self.timeouts[-1]
            budgets.append(budget)
            now[0] += budget
            raise OSError("unreachable")
    def make_socket(*args):
        sock = Unreachable()
        sockets.append(sock)
        return sock
    monkeypatch.setattr("infra_mcp.mysql_protocol.socket.socket", make_socket)
    with pytest.raises(InfraError) as error:
        BoundedConnection(operation_timeout=10, connect_timeout=6, ssl_disabled=True)
    assert error.value.code == 'timeout'
    assert budgets == [6, 4]
    assert now[0] == 110
    assert all(sock.closed for sock in sockets)


def test_ssl_handshake_inherits_remaining_time_after_slow_request_write(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("infra_mcp.mysql_protocol.time.monotonic", lambda: now[0])
    conn, sock, _ = connection()
    def slow_write(value):
        now[0] += 8
    sock.sendall = slow_write
    conn._write_bytes(b'SSLRequest')
    assert sock.timeouts[-1] == 2
    assert conn._current_timeout == 2
    conn.force_close()


def test_deadline_between_socket_creation_and_driver_handoff_closes_socket(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("infra_mcp.mysql_protocol.time.monotonic", lambda: now[0])
    sock = Socket()
    def opened(connection):
        now[0] = 111.0
        return sock
    monkeypatch.setattr(BoundedConnection, '_open_socket', opened)
    with pytest.raises(InfraError):
        BoundedConnection(operation_timeout=10, ssl_disabled=True)
    assert sock.closed


@pytest.mark.parametrize("kwargs", [
    {"max_response_bytes": True}, {"max_response_bytes": 1023},
    {"max_response_bytes": 16_777_217}, {"operation_timeout": 0},
    {"operation_timeout": float("nan")}, {"operation_timeout": True},
])
def test_invalid_limits_fail_before_connect(kwargs):
    with pytest.raises(InfraError):
        BoundedConnection(defer_connect=True, **kwargs)
