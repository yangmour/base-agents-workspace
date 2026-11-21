"""Per-request write approval. No caller-supplied approval flags or cached grants."""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import types
from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field, StrictBool


class WriteDecision(BaseModel):
    allow_once: StrictBool = Field(title="允许本次")


# Read the request as data on stdin. It never becomes executable AppleScript
# or part of the process argument list. Return/Escape both default to denial.
_DIALOG = """
ObjC.import('Foundation')
const data = $.NSFileHandle.fileHandleWithStandardInput.readDataToEndOfFile
const message = ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding))
const app = Application.currentApplication()
app.includeStandardAdditions = true
const result = app.displayDialog(message, {
    withTitle: 'MCP 写入确认', buttons: ['拒绝', '允许本次'],
    defaultButton: '拒绝', cancelButton: '拒绝', givingUpAfter: 120
})
result.buttonReturned === '允许本次' && !result.gaveUp ? 'allow' : 'deny'
"""


async def desktop_approval(message: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "/usr/bin/osascript", "-l", "JavaScript", "-e", _DIALOG,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, _ = await proc.communicate(message.encode("utf-8"))
        return proc.returncode == 0 and stdout.strip() == b"allow"
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


def approval_message(service: str, connection: str, action: str, operation: str, arguments: dict) -> str:
    request = json.dumps({"服务": service, "连接": connection, "动作": action,
                          "操作": operation, "参数": arguments}, ensure_ascii=False, indent=2, allow_nan=False)
    # Escape directional and other non-printing characters supplied in names/values.
    request = "".join(ch if ch == "\n" or ch.isprintable() else ascii(ch)[1:-1] for ch in request)
    return "请核对本次写入。授权仅对下面这一条请求生效。\n" + request


async def confirm_write(ctx: Context | None, message: str) -> None:
    try:
        async with asyncio.timeout(120):
            if sys.platform == "darwin":
                accepted = await desktop_approval(message)
            else:
                # Cluster-hosted stdio servers have no desktop. A trusted
                # interactive MCP client must present this form to its operator.
                capability = types.ClientCapabilities(elicitation=types.ElicitationCapability())
                if ctx is None or not ctx.request_context.session.check_client_capability(capability):
                    raise ToolError("approval_required: 客户端无法显示确认，写入未执行")
                result = await ctx.elicit(message, WriteDecision)
                accepted = result.action == "accept" and result.data.allow_once is True
    except ToolError:
        raise
    except Exception:
        raise ToolError("approval_required: 未取得本次确认，写入未执行") from None
    if not accepted:
        raise ToolError("approval_denied: 本次写入未获允许")
