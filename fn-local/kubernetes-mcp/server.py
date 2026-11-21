"""One fixed stdio MCP subprocess per mutually authenticated loopback connection."""
import asyncio
import contextlib
import os
from pathlib import Path
import signal
import ssl
import sys

LIMIT = 8
QUEUE_TIMEOUT = 15
# Longer than the one-time approval window plus the maximum Kubernetes timeout.
IDLE_TIMEOUT = 300


async def relay(reader, writer, touch):
    while chunk := await reader.read(64 * 1024):
        touch()
        writer.write(chunk)
        await writer.drain()


async def relay_session(reader, writer, process, idle_timeout=IDLE_TIMEOUT):
    clock = asyncio.get_running_loop().time
    last_activity = clock()

    def touch():
        nonlocal last_activity
        last_activity = clock()

    async def idle():
        while (remaining := last_activity + idle_timeout - clock()) > 0:
            await asyncio.sleep(remaining)

    tasks = [asyncio.create_task(relay(reader, process.stdin, touch)),
             asyncio.create_task(relay(process.stdout, writer, touch)),
             asyncio.create_task(idle())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def serve():
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls_dir = Path(os.environ["MCP_TLS_DIR"])
    tls.load_cert_chain(tls_dir / "server.crt", tls_dir / "server.key")
    tls.load_verify_locations(tls_dir / "ca.crt")
    tls.verify_mode = ssl.CERT_REQUIRED
    active = set()
    slots = asyncio.Semaphore(LIMIT)

    async def client(reader, writer):
        task = asyncio.current_task()
        # Bound waiting sockets as well as the number of resident MCP processes.
        if len(active) >= 2 * LIMIT:
            writer.close()
            return
        active.add(task)
        process = None
        acquired = False
        try:
            try:
                await asyncio.wait_for(slots.acquire(), QUEUE_TIMEOUT)
            except TimeoutError:
                return
            acquired = True
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "infra_mcp", "kubernetes", "--config", str(Path(__file__).with_name("profiles.json")),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
            await relay_session(reader, writer, process)
        finally:
            if process is not None:
                process.stdin.close()
                if process.returncode is None:
                    with contextlib.suppress(ProcessLookupError):
                        process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 3)
                except TimeoutError:
                    with contextlib.suppress(ProcessLookupError):
                        process.kill()
                    await process.wait()
            if acquired:
                slots.release()
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


if __name__ == "__main__":
    asyncio.run(serve())
