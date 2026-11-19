"""One fixed stdio MCP subprocess per mutually authenticated loopback connection."""
import asyncio
import contextlib
import os
from pathlib import Path
import signal
import ssl
import sys

LIMIT = 8


async def relay(reader, writer):
    while chunk := await reader.read(64 * 1024):
        writer.write(chunk)
        await writer.drain()


async def serve():
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls_dir = Path(os.environ["MCP_TLS_DIR"])
    tls.load_cert_chain(tls_dir / "server.crt", tls_dir / "server.key")
    tls.load_verify_locations(tls_dir / "ca.crt")
    tls.verify_mode = ssl.CERT_REQUIRED
    active = set()

    async def client(reader, writer):
        task = asyncio.current_task()
        if len(active) >= LIMIT:
            writer.close()
            return
        active.add(task)
        process = None
        streams = []
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "infra_mcp", "kubernetes", "--config", str(Path(__file__).with_name("profiles.json")),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            streams = [asyncio.create_task(relay(reader, process.stdin)),
                       asyncio.create_task(relay(process.stdout, writer))]
            await asyncio.wait(streams, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for stream in streams:
                stream.cancel()
            await asyncio.gather(*streams, return_exceptions=True)
            if process is not None:
                process.stdin.close()
                if process.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 3)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            writer.close()
            active.discard(task)

    stop = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stop.set)
    async with await asyncio.start_server(client, "127.0.0.1", 9443, ssl=tls, ssl_handshake_timeout=5):
        await stop.wait()
    tasks = list(active)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


asyncio.run(serve())
