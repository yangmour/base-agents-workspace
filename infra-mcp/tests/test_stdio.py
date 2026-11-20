import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.parametrize("service", ["redis", "rabbitmq", "elasticsearch", "kubernetes", "nacos", "mysql", "rocketmq", "jenkins"])
def test_actual_stdio_discovery_and_unconfigured_calls(tmp_path, service):
    async def check():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "infra_mcp", service, "--config", str(tmp_path / "missing.json")],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                by_name = {t.name: t for t in tools}
                assert set(by_name) == {"list_connections", "list_operations", "check_connection", "create", "read", "update", "delete"}
                assert by_name["read"].annotations.readOnlyHint is True
                assert by_name["delete"].annotations.destructiveHint is True
                listing = await session.call_tool("list_connections", {})
                assert not listing.isError
                assert "configuration_needed" in listing.content[0].text
                operations = await session.call_tool("list_operations", {})
                assert not operations.isError
                payload = json.loads(operations.content[0].text)
                assert {item["action"] for item in payload["operations"].values()} == {"create", "read", "update", "delete"}
                denied = await session.call_tool("check_connection", {"connection": "missing"})
                assert denied.isError
                assert "unknown_connection" in denied.content[0].text
    asyncio.run(check())
