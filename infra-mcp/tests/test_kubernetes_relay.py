import asyncio
import runpy
from pathlib import Path
from types import SimpleNamespace


def test_idle_tunnel_releases_both_relays():
    relay = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                               "fn-local/kubernetes-mcp/server.py"))["relay_session"]

    async def exercise():
        incoming = asyncio.StreamReader()
        outgoing = asyncio.StreamReader()
        class Sink:
            def __init__(self):
                self.data = bytearray()
            def write(self, data):
                self.data.extend(data)
            async def drain(self):
                pass

        client = Sink()
        process = SimpleNamespace(stdin=Sink(), stdout=outgoing)
        session = asyncio.create_task(relay(incoming, client, process, idle_timeout=.15))
        for _ in range(3):
            await asyncio.sleep(.07)
            assert not session.done()
            incoming.feed_data(b"request")
            outgoing.feed_data(b"response")
        await asyncio.wait_for(session, 1)
        assert process.stdin.data == b"request" * 3
        assert client.data == b"response" * 3
    asyncio.run(exercise())
