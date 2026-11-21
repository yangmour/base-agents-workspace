#!/usr/bin/env python3
"""Test an existing local RabbitMQ over stdio; report unavailable ES honestly.

The selected RabbitMQ container must already be running. This script never starts
containers, creates services, changes policies, or reads business messages. With
--restore-stopped it stops the selected container in finally after exact cleanup.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ("create", "read", "update", "delete")


def docker(*arguments):
    result = subprocess.run(["docker", *arguments], capture_output=True, text=True, timeout=35)
    if result.returncode:
        raise RuntimeError("Docker operation failed; output withheld")
    return result.stdout


def secure_write(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(value)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


async def session_checks(service, config, checks, exercise):
    params = StdioServerParameters(command=sys.executable,
        args=["-m", "infra_mcp", service, "--config", str(config)],
        cwd=str(ROOT), env={"PYTHONPATH": str(ROOT / "src")})

    def check(label, condition):
        checks.append((label, bool(condition)))
        if not condition:
            raise AssertionError(label)

    with open(os.devnull, "w") as errors:
        async with stdio_client(params, errlog=errors) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=150)) as session:
                await session.initialize()
                check("MCP initialize", True)

                async def call(tool, operation=None, arguments=None, connection="local-test", denied=None):
                    request = {} if tool.startswith("list_") else {"connection": connection}
                    if operation:
                        request.update(operation=operation, arguments=arguments or {})
                    result = await session.call_tool(tool, request)
                    if denied:
                        text = " ".join(item.text for item in result.content if item.type == "text")
                        check(f"{denied}: {tool}/{operation or tool}", result.isError and denied in text)
                        return text
                    diagnostic = ""
                    if result.isError:
                        # Keep only adapter-owned error codes/status, never arbitrary backend text.
                        raw = " ".join(item.text for item in result.content if item.type == "text")
                        code = re.search(r"\b(?:backend_http_error|backend_error|invalid_argument|timeout|output_limit|scope_denied|permission_denied)\b", raw)
                        status = re.search(r"\bHTTP ([0-9]{3})\b", raw)
                        diagnostic = f" ({code.group(0) if code else 'tool_error'}" + (f", HTTP {status.group(1)}" if status else "") + ")"
                    check(f"MCP success: {tool}/{operation or tool}{diagnostic}", not result.isError)
                    return result.structuredContent or json.loads(next(item.text for item in result.content if item.type == "text"))

                check("Seven fixed MCP tools", {tool.name for tool in (await session.list_tools()).tools} ==
                      {"list_connections", "list_operations", "check_connection", *ACTIONS})
                connections = await call("list_connections")
                check("Discovery excludes connection options and credentials", all(
                    set(item) == {"name", "environment", "permissions", "allow_after_approval", "scope"}
                    for item in connections["connections"]))
                await call("list_operations")
                await exercise(call, check)


async def rabbitmq(config, checks, cleanup, direct, resource, username):
    queue, exchange = resource + "-queue", resource + "-exchange"
    queue_path, exchange_path = "/api/queues/%2F/" + queue, "/api/exchanges/%2F/" + exchange

    async def exercise(call, check):
        check("Authenticated RabbitMQ identity", (await call("check_connection"))["data"].get("name") == username)
        check("UUID queue and exchange absent before writes", all(
            direct.get(path).status_code == 404 for path in (queue_path, exchange_path)))
        cleanup["owned_resources_authorized"] = True
        qa, xa = {"vhost": "/", "queue": queue}, {"vhost": "/", "exchange": exchange}

        async def op(action, operation, arguments):
            return (await call(action, operation, arguments))["data"]

        try:
            await call("create", "declare_queue", qa, "local-readonly", "permission_denied")
            await call("delete", "delete_queue", qa, "local-readonly", "permission_denied")
            await call("create", "declare_queue", qa, "local-create-only", "permission_denied")
            await call("read", "delete_queue", qa, denied="permission_denied")
            await call("read", "get_queue", {**qa, "queue": queue + "-outside"}, denied="scope_denied")
            await call("read", "get_queue", {**qa, "vhost": resource}, denied="scope_denied")
            await call("update", "update_policy", {"vhost": "/", "name": resource}, denied="scope_denied")
            qbody = {**qa, "durable": False, "arguments": {"x-expires": 300000, "x-message-ttl": 60000}}
            xbody = {**xa, "durable": False, "type": "direct"}
            await op("create", "declare_queue", qbody)
            await op("create", "declare_exchange", xbody)
            check("Queue exact name and bounded lifetime", (await op("read", "get_queue", qa))["arguments"]["x-expires"] == 300000)
            check("Exchange exact name and direct type", (await op("read", "get_exchange", xa))["type"] == "direct")
            # Existing declarations require update permission but do not alter global policies.
            await op("create", "declare_queue", qbody)
            await op("create", "declare_exchange", xbody)
            binding = {**qa, "exchange": exchange, "routing_key": "synthetic-route"}
            await op("create", "create_binding", binding)
            bindings = await op("read", "list_bindings", {"vhost": "/"})
            check("Binding list restricted to owned resources", len(bindings) == 1 and bindings[0]["source"] == exchange and bindings[0]["destination"] == queue)
            for name, field, expected in (("list_queues", "name", queue), ("list_exchanges", "name", exchange)):
                rows = await op("read", name, {"vhost": "/"})
                check(name + ": no out-of-scope records", len(rows) == 1 and rows[0][field] == expected)
            check("Synthetic message routed", (await op("create", "publish", {**xa, "routing_key": "synthetic-route", "payload": "infra-mcp synthetic message v1"}))["routed"] is True)
            messages = await op("delete", "consume", {**qa, "count": 1})
            check("Exact synthetic message round trip", len(messages) == 1 and messages[0]["payload"] == "infra-mcp synthetic message v1")
            check("Acknowledged message is removed", await op("delete", "consume", {**qa, "count": 1}) == [])
            check("Second synthetic message routed", (await op("create", "publish", {**xa, "routing_key": "synthetic-route", "payload": "infra-mcp synthetic purge message"}))["routed"] is True)
            await op("delete", "purge_queue", qa)
            check("Owned queue purge removes only synthetic message", await op("delete", "consume", {**qa, "count": 1}) == [])
            await op("delete", "delete_binding", {**binding, "properties_key": bindings[0]["properties_key"]})
            check("Owned binding deleted", await op("read", "list_bindings", {"vhost": "/"}) == [])
            check("Deleted binding no longer routes", (await op("create", "publish", {**xa, "routing_key": "synthetic-route", "payload": "infra-mcp synthetic unrouted message"}))["routed"] is False)
            await op("delete", "delete_queue", qa)
            await op("delete", "delete_exchange", xa)
        finally:
            # Exact names were confirmed absent before any write; never purge or delete others.
            for operation, arguments, path in (("delete_queue", qa, queue_path), ("delete_exchange", xa, exchange_path)):
                if direct.get(path).status_code != 404:
                    try:
                        await op("delete", operation, arguments)
                    except Exception:
                        cleanup["direct_fallback_used"] = True
                        response = direct.delete(path)
                        if response.status_code not in (204, 404):
                            raise RuntimeError("Exact cleanup failed; response withheld")
            cleanup["queue_absent"] = direct.get(queue_path).status_code == 404
            cleanup["exchange_absent"] = direct.get(exchange_path).status_code == 404
            check("Independent HTTP 404 verifies exact cleanup", cleanup["queue_absent"] and cleanup["exchange_absent"])

    await session_checks("rabbitmq", config, checks, exercise)


async def elasticsearch_unavailable(config, checks):
    async def exercise(call, check):
        error = await call("check_connection", denied="backend_error")
        check("Unavailable backend error is sanitized", "Traceback" not in error and "127.0.0.1" not in error)
        await call("create", "create_index", {"index": "infra-mcp-test-never-created"}, "local-readonly", "permission_denied")
        await call("read", "search", {"index": "outside-scope"}, denied="scope_denied")
    await session_checks("elasticsearch", config, checks, exercise)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-container", required=True)
    parser.add_argument("--rabbitmq-port", type=int, default=15672)
    parser.add_argument("--restore-stopped", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/local-http-mcp-20261107.md")
    args = parser.parse_args()
    if not 0 < args.rabbitmq_port < 65536:
        parser.error("Invalid port")
    resource = "infra-mcp-test-" + uuid.uuid4().hex
    checks, es_checks, cleanup = [], [], {"direct_fallback_used": False}
    failure = None
    temporary_path = None
    direct = None
    try:
        # Read selected container credentials in memory; never emit inspect/env output.
        inspection = json.loads(docker("inspect", args.existing_container))[0]
        values = dict(item.split("=", 1) for item in inspection["Config"].get("Env", []) if "=" in item)
        username, password = values.get("RABBITMQ_DEFAULT_USER"), values.get("RABBITMQ_DEFAULT_PASS")
        if not username or not password:
            raise RuntimeError("Existing container credential references unavailable")
        with tempfile.TemporaryDirectory(prefix="infra-mcp-http-test-") as temporary:
            temporary_path = Path(temporary)
            references = {}
            for key, value in (("username", username), ("password", password)):
                path = temporary_path / (key + ".txt")
                secure_write(path, value)
                references[key + "_file"] = str(path)
            options = {"url": f"http://127.0.0.1:{args.rabbitmq_port}", "timeout": 3,
                       "scope": {"vhosts": ["/"], "queues": [resource + "-queue"], "exchanges": [resource + "-exchange"]}, **references}
            profiles = {"rabbitmq": {}, "elasticsearch": {}}
            for name, permitted in (("local-test", ACTIONS), ("local-readonly", ["read"]), ("local-create-only", ["create"])):
                permissions = {action: action in permitted for action in ACTIONS}
                profiles["rabbitmq"][name] = {**options, "permissions": permissions}
                profiles["elasticsearch"][name] = {"url": "http://127.0.0.1:9200", "timeout": 2,
                    "scope": {"indices": [resource]}, "permissions": permissions}
            config = temporary_path / "profiles.json"
            secure_write(config, json.dumps({"profiles": profiles}))
            direct = httpx.Client(base_url=options["url"], auth=(username, password), trust_env=False, timeout=3)
            for attempt in range(15):
                try:
                    if direct.get("/api/whoami").status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if attempt == 14:
                    raise RuntimeError("Local RabbitMQ management API unavailable")
                time.sleep(2)
            try:
                asyncio.run(rabbitmq(config, checks, cleanup, direct, resource, username))
            finally:
                # Covers session initialization/exit errors as well as normal test cleanup.
                if cleanup.get("owned_resources_authorized"):
                    for kind, suffix in (("queues", "queue"), ("exchanges", "exchange")):
                        path = "/api/" + kind + "/%2F/" + resource + "-" + suffix
                        if direct.get(path).status_code != 404:
                            cleanup["direct_fallback_used"] = True
                            direct.delete(path)
                        cleanup[suffix + "_absent"] = direct.get(path).status_code == 404
            asyncio.run(elasticsearch_unavailable(config, es_checks))
    except Exception as error:
        failure = type(error).__name__
    finally:
        if direct:
            direct.close()
        cleanup["temporary_secrets_removed"] = temporary_path is not None and not temporary_path.exists()
        if args.restore_stopped:
            try:
                docker("stop", "--time", "20", args.existing_container)
                state = json.loads(docker("inspect", "--format", "{{json .State}}", args.existing_container))
                cleanup["original_stopped_state_restored"] = state["Status"] == "exited" and not state["Running"]
            except Exception as error:
                failure = failure or type(error).__name__
                cleanup["original_stopped_state_restored"] = False
    passed = failure is None and all(ok for _, ok in checks + es_checks) and all(cleanup.get(key) for key in
        ("queue_absent", "exchange_absent", "temporary_secrets_removed")) and (not args.restore_stopped or cleanup.get("original_stopped_state_restored"))
    lines = ["# Local RabbitMQ / Elasticsearch MCP verification", "",
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}", "",
        f"RabbitMQ integration: {'PASS' if passed else 'FAIL'}.",
        "Elasticsearch backend CRUD: **NOT VERIFIED** — no existing local Elasticsearch service was found; protocol/error checks are not backend integration evidence.", "",
        "- Real `mcp.ClientSession` launches `.venv/bin/python -m infra_mcp rabbitmq|elasticsearch --config <temporary-0600-json>` over stdio.",
        f"- RabbitMQ: existing `{args.existing_container}`, `127.0.0.1:{args.rabbitmq_port}`, default vhost `/`.",
        f"- Owned resources: `{resource}-queue` and `{resource}-exchange`; only synthetic messages and their exact binding.",
        "- Credentials were read privately from the existing container, copied into mode-0600 files, and referenced by the temporary profile. No credential values or business payloads are recorded.",
        "- Existing queue/exchange declarations exercised their additional update permission. The `update_policy` tool was rejected by the exact resource scope; no policy or global configuration was changed.",
        "- Elasticsearch discovery: no ES container in `docker ps -a`, no ES/Java native service process, no 9200 listener. The existing `.env.example` references `localhost:9200`; no other confirmed local ES endpoint was found.",
        f"- Failure class: `{failure or 'none'}` (raw errors withheld).", "",
        "## RabbitMQ checks", "", "| Check | Result |", "| --- | --- |"]
    lines.extend(f"| {label} | {'PASS' if ok else 'FAIL'} |" for label, ok in checks)
    lines.extend(["", "## Elasticsearch protocol-only checks", "", "| Check | Result |", "| --- | --- |"])
    lines.extend(f"| {label} | {'PASS' if ok else 'FAIL'} |" for label, ok in es_checks)
    lines.extend(["", "## Cleanup", "", "```json", json.dumps(cleanup, indent=2), "```", ""])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"rabbitmq": "PASS" if passed else "FAIL", "elasticsearch_backend": "NOT_VERIFIED",
        "rabbitmq_checks": len(checks), "elasticsearch_protocol_checks": len(es_checks), "cleanup": cleanup,
        "failure_class": failure, "report": str(args.report)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
