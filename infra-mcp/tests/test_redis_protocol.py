from types import SimpleNamespace
import pytest
from redis._parsers.encoders import Encoder
from infra_mcp.config import InfraError
from infra_mcp.redis_protocol import BoundedRESP2Parser


class Socket:
    def __init__(self, payload, fragment=3):
        self.payload, self.fragment, self.closed = payload, fragment, False
        self.received = 0
    def recv(self, size):
        size = min(size, self.fragment)
        data, self.payload = self.payload[:size], self.payload[size:]
        self.received += len(data)
        return data
    def close(self): self.closed = True
    def settimeout(self, value): pass


def parser(payload, budget=128):
    sock = Socket(payload)
    instance = BoundedRESP2Parser(16)
    instance.MAX_REPLY_BYTES = budget
    instance.on_connect(SimpleNamespace(_sock=sock, socket_timeout=1, encoder=Encoder('utf-8','strict',False)))
    return instance, sock


def test_fragmented_bulk_and_array():
    instance, sock = parser(b'*2\r\n$3\r\nfoo\r\n$3\r\nbar\r\n')
    assert instance.read_response() == [b'foo',b'bar']
    assert not sock.closed


@pytest.mark.parametrize('payload',[b'$100000000\r\n', b'*100\r\n' + b'+abc\r\n'*100, b'+'+b'x'*1000])
def test_oversized_reply_closes_socket_before_budget(payload):
    instance, sock = parser(payload, 64)
    with pytest.raises(InfraError) as error: instance.read_response()
    assert error.value.code == 'result_too_large'
    assert sock.closed
    assert sock.received <= 64
