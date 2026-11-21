"""Mac frontend for the cluster-hosted Kubernetes MCP, including older pods."""
import asyncio
from contextlib import asynccontextmanager, suppress
import json
import os
import signal

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from .approval import WriteDecision, approval_message, confirm_write
from .config import ACTIONS
from .paths import bin_dir, profile_file

_READS = {"list_connections", "list_operations", "check_connection", "read"}


@asynccontextmanager
async def upstream(transport, decision=None):
    async with stdio_client(transport) as (reader, writer):
        async with ClientSession(reader, writer, elicitation_callback=decision) as session:
            await session.initialize()
            yield session


def approved_form(message):
    # Each approved write owns a separate downstream session. A newer Pod
    # requests confirmation on that session. Relay only the exact decision
    # already made on the Mac, once. Older read-only Pods do not request it.
    consumed = False

    async def reply(context, params):
        nonlocal consumed
        if (not consumed and getattr(params, "requestedSchema", None) == WriteDecision.model_json_schema()
                and params.message == message):
            consumed = True
            return types.ElicitResult(action="accept", content={"allow_once": True})
        return types.ElicitResult(action="decline")

    return reply


ISSUER = bin_dir() / "infra-kubernetes-release-issuer"
ISSUER_CONNECTION = "release-issuer"
ISSUER_RELEASES = ["develop", "higress-system", "logging"]
ISSUER_OPERATIONS = {
    "list_release_credentials": ("read", "list", None, "List managed release sessions and expiry; metadata only."),
    "issue_release_credential": ("create", "issue", "release", "Issue a one-hour named release after a Mac confirmation."),
    "delete_expired_release_credential": ("delete", "delete-expired", "session", "Confirm removal of one expired release session."),
}


async def call_issuer(name, arguments):
    operation = arguments.get("operation")
    item = ISSUER_OPERATIONS.get(operation)
    if not item or name != item[0]:
        raise ValueError("Issuer operation does not belong to this CRUD action")
    _, command, field, _ = item
    params = arguments.get("arguments") or {}
    if set(params) != ({field} if field else set()) or (field and not isinstance(params[field], str)):
        raise ValueError("Invalid issuer arguments")
    proc = await asyncio.create_subprocess_exec(
        str(ISSUER), command, *([params[field]] if field else []), stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
    try:
        stdout, _ = await proc.communicate()
    finally:
        if proc.returncode is None:
            with suppress(ProcessLookupError):
                os.killpg(proc.pid, signal.SIGTERM)
            await proc.wait()
    result = json.loads(stdout)
    if proc.returncode:
        raise ValueError(result.get("error", "Release issuer failed"))
    return {"ok": True, "connection": ISSUER_CONNECTION, "operation": operation,
            "data": result, "truncated": False, "redacted": False}


def build_frontend(transport):
    # The frontend implements this fixed tool schema itself. Local credential
    # management and MCP discovery also work while the tunnel is disconnected.
    from .server import build_server
    schema = build_server("kubernetes", profile_file())
    server = Server("infra-kubernetes", instructions="Reads are direct. Each write requires approval on this Mac.")

    @server.list_tools()
    async def list_tools():
        return await schema.list_tools()

    @server.call_tool()
    async def call_tool(name, arguments):
        issuer_enabled = ISSUER.is_file()
        if issuer_enabled and arguments.get("connection") == ISSUER_CONNECTION:
            if name == "check_connection":
                await call_issuer("read", {"operation": "list_release_credentials"})
                return {"ok": True, "connection": ISSUER_CONNECTION, "operation": "check_connection",
                        "data": {"connected": True}, "truncated": False, "redacted": False}
            return await call_issuer(name, arguments)
        if name in _READS:
            async with upstream(transport) as session:
                result = await session.call_tool(name, arguments)
            if name == "list_connections" and not result.isError:
                listing = result.structuredContent
                for profile in listing["connections"]:
                    if "allow_after_approval" not in profile:
                        # Older Pods report the backend ceiling as direct permissions.
                        permissions = profile["permissions"]
                        profile["allow_after_approval"] = sorted(
                            action for action in ACTIONS - {"read"} if permissions.get(action)
                        )
                        for action in ACTIONS - {"read"}:
                            permissions[action] = False
                if issuer_enabled:
                    listing["connections"].append({"name": ISSUER_CONNECTION, "environment": "local operator",
                        "permissions": {action: action == "read" for action in ACTIONS},
                        "allow_after_approval": ["create", "delete"], "scope": {"releases": ISSUER_RELEASES}})
                return listing
            if name == "list_operations" and issuer_enabled and not result.isError:
                listing = result.structuredContent
                for op, (action, _, field, description) in ISSUER_OPERATIONS.items():
                    params = {} if not field else {field: ", ".join(ISSUER_RELEASES) if field == "release" else "Exact release session ID"}
                    listing["operations"][op] = {"action": action, "description": description, "parameters": params,
                                                 "additional_permissions": [], "connection": ISSUER_CONNECTION}
                return listing
            return result
        if name not in ACTIONS:
            raise ValueError("Unknown Kubernetes MCP tool")
        message = approval_message("kubernetes", arguments["connection"], name,
                                   arguments["operation"], arguments.get("arguments") or {})
        await confirm_write(None, message)
        async with upstream(transport, approved_form(message)) as session:
            return await session.call_tool(name, arguments)

    return server


async def serve_tunnel(argv):
    transport = StdioServerParameters(command=argv[0], args=argv[1:])
    server = build_frontend(transport)
    async with stdio_server() as (reader, writer):
        await server.run(reader, writer, server.create_initialization_options())
