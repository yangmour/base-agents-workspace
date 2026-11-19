"""Verify the deployed read-only MCP over its normal authenticated stdio entry point."""
import asyncio
import json
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

NAME = "fn-k8s-kubernetes"


async def main():
    env = {key: os.environ[key] for key in ("XDG_CONFIG_HOME", "FN_MCP_CERT_DIR", "OPENSSL_BIN") if key in os.environ}
    async with stdio_client(StdioServerParameters(command="infra-kubernetes-client", env=env)) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()

            async def call(tool, **args):
                result = await session.call_tool(tool, args)
                if result.isError:
                    raise RuntimeError(result.content[0].text)
                return json.loads(result.content[0].text)

            connections = (await call("list_connections"))["connections"]
            assert len(connections) == 1 and connections[0]["name"] == NAME
            assert connections[0]["permissions"] == {"read": True, "create": False, "update": False, "delete": False}
            assert connections[0]["scope"]["namespaces"] == ["develop"]
            await call("list_operations")
            assert (await call("check_connection", connection=NAME))["data"]["connected"]
            result = await call("read", connection=NAME, operation="list",
                                arguments={"namespace": "develop", "resource": "deployments"})
            print("develop deployments:", len(result["data"]["items"]))
            for tool, operation, error, args in [
                ("read", "list", "scope_denied", {"resource": "pods", "namespace": "default"}),
                ("update", "patch", "permission_denied", {"resource": "deployments", "namespace": "develop",
                                     "name": "mcp-permission-check", "patch": {}}),
            ]:
                denial = await session.call_tool(tool, {"connection": NAME, "operation": operation, "arguments": args})
                assert denial.isError and error in denial.content[0].text, denial.content[0].text
                print("denied:", tool, operation, args["namespace"])


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=60))
