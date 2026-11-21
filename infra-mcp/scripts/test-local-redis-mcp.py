#!/usr/bin/env python3
"""Exercise real stdio MCP against an existing loopback Redis, using owned keys only."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry


ROOT = Path(__file__).resolve().parents[1]
LOOPBACK = {"localhost", "127.0.0.1", "::1"}


def secure_write(path: Path, content: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


async def exercise(args, config_path, prefix, direct, checks, cleanup):
    keys = [prefix + suffix for suffix in ("string", "missing", "hash")]
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "infra_mcp", "redis", "--config", str(config_path)],
        cwd=str(ROOT),
        env={"PYTHONPATH": str(ROOT / "src")},
    )

    def check(label, condition):
        checks.append((label, bool(condition)))
        if not condition:
            raise AssertionError(label)

    # Backend stderr can contain arbitrary dependency text; never print or retain it.
    with open(os.devnull, "w") as error_log:
        async with stdio_client(parameters, errlog=error_log) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=150)) as session:
                await session.initialize()
                check("MCP initialize", True)

                async def call(tool, operation=None, arguments=None, connection="local-test", denied=None):
                    payload = {} if tool.startswith("list_") else {"connection": connection}
                    if operation is not None:
                        payload.update(operation=operation, arguments=arguments or {})
                    result = await session.call_tool(tool, payload)
                    if denied:
                        text = " ".join(item.text for item in result.content if item.type == "text")
                        check(f"{denied}: {operation}", result.isError and denied in text)
                        return None
                    if result.isError:
                        # Keep reports free of backend text, connection strings and values.
                        checks.append((f"MCP call succeeded: {tool}/{operation or tool}", False))
                        raise RuntimeError("MCP tool call failed; backend text withheld")
                    decoded = result.structuredContent
                    if decoded is None:
                        decoded = json.loads(next(item.text for item in result.content if item.type == "text"))
                    return decoded

                async def operation(action, name, key=None, connection="local-test", **arguments):
                    if key is not None:
                        arguments["key"] = key
                    return (await call(action, name, arguments, connection))["data"]

                tools = {tool.name for tool in (await session.list_tools()).tools}
                check("MCP tool discovery", tools == {"list_connections", "list_operations", "check_connection", "create", "read", "update", "delete"})
                listing = await call("list_connections")
                profiles = {profile["name"]: profile for profile in listing["connections"]}
                check("list_connections: isolated profiles and scope", set(profiles) == {"local-test", "local-readonly", "local-update-only"} and all(profile["scope"] == {"key_patterns": [prefix + "*"]} for profile in profiles.values()))
                check("list_connections: no connection credentials", all(set(profile) == {"name", "environment", "permissions", "allow_after_approval", "scope"} for profile in profiles.values()))
                listing = await call("list_operations")
                check("list_operations: CRUD and hash operations", {"create", "get", "update", "ttl", "delete", "hash_set", "hash_delete", "read_collection"} <= set(listing["operations"]))
                check("check_connection: PING", (await call("check_connection"))["data"] == {"reachable": True})
                # Exact-key existence is the only independent Redis read. Never scan business keys.
                check("fresh UUID keys absent before writes", direct.exists(*keys) == 0)
                cleanup["authorized"] = True
                try:
                    await call("read", "get", {"key": prefix[:-1] + "-outside:key"}, denied="scope_denied")
                    await call("create", "create", {"key": keys[0], "value": "synthetic"}, "local-readonly", "permission_denied")
                    await call("update", "hash_set", {"key": keys[2], "field": "field-a", "value": "synthetic"}, "local-update-only", "permission_denied")
                    check("create: atomic NX", (await operation("create", "create", keys[0], value="synthetic-v1", ttl_seconds=300))["created"] is True)
                    value = await operation("read", "get", keys[0])
                    check("get: synthetic string round trip", value == {"value": "synthetic-v1", "encoding": "utf-8", "truncated": False})
                    check("create: cannot overwrite", (await operation("create", "create", keys[0], value="must-not-overwrite"))["created"] is False)
                    check("create: original value preserved", (await operation("read", "get", keys[0]))["value"] == "synthetic-v1")
                    ttl_before = (await operation("read", "ttl", keys[0]))["seconds"]
                    check("ttl: create expiration", 0 < ttl_before <= 300)
                    check("update: cannot create missing key", (await operation("update", "update", keys[1], value="must-not-create"))["updated"] is False)
                    check("update: missing key remains absent", (await operation("read", "ttl", keys[1]))["seconds"] == -2)
                    check("update: existing string", (await operation("update", "update", keys[0], value="synthetic-v2"))["updated"] is True)
                    check("update: replacement round trip", (await operation("read", "get", keys[0]))["value"] == "synthetic-v2")
                    ttl_after = (await operation("read", "ttl", keys[0]))["seconds"]
                    check("update: preserves existing TTL", 0 < ttl_after <= ttl_before)
                    bounded = await operation("read", "get", keys[0], max_bytes=4)
                    check("get: bounded prefix", bounded == {"value": "synt", "encoding": "utf-8", "truncated": True})
                    check("expire: existing string", (await operation("update", "expire", keys[0], seconds=120))["updated"] is True)
                    check("expire: replacement TTL", 0 < (await operation("read", "ttl", keys[0]))["seconds"] <= 120)
                    check("hash_set: creates field", (await operation("update", "hash_set", keys[2], field="field-a", value="synthetic-h1"))["added"] == 1)
                    check("hash: bounded lifetime", (await operation("update", "expire", keys[2], seconds=300))["updated"] is True)
                    check("inspect: hash type", (await operation("read", "inspect", keys[2]))["type"] == "hash")
                    check("hash_set: updates field", (await operation("update", "hash_set", keys[2], field="field-a", value="synthetic-h2"))["added"] == 0)
                    collection = await operation("read", "read_collection", keys[2], limit=10)
                    check("read_collection: synthetic hash round trip", collection["type"] == "hash" and collection["items"] == {"field-a": "synthetic-h2"} and collection["cursor"] == 0)
                    await call("update", "update", {"key": keys[2], "value": "must-not-replace-hash"}, denied="invalid_argument")
                    check("update: hash remains intact", (await operation("read", "read_collection", keys[2], limit=10))["items"] == {"field-a": "synthetic-h2"})
                    check("hash_delete: exact field", (await operation("delete", "hash_delete", keys[2], field="field-a"))["deleted"] == 1)
                    check("hash: last field removal removes key", (await operation("read", "ttl", keys[2]))["seconds"] == -2)
                    check("delete: existing key", (await operation("delete", "delete", keys[0]))["deleted"] is True)
                    check("delete: missing key", (await operation("delete", "delete", keys[0]))["deleted"] is False)
                    check("get: deleted key absent", (await operation("read", "get", keys[0]))["value"] is None)
                finally:
                    # Cleanup never broadens scope, including when an assertion or tool call fails.
                    mcp_cleanup = True
                    for key in keys:
                        try:
                            await operation("delete", "delete", key)
                            mcp_cleanup = mcp_cleanup and (await operation("read", "ttl", key))["seconds"] == -2
                        except Exception:
                            mcp_cleanup = False
                    cleanup["mcp_exact_deletes_and_ttl"] = mcp_cleanup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=sorted(LOOPBACK), default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--db", type=int, default=0)
    parser.add_argument("--username-file", type=Path)
    parser.add_argument("--password-file", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / f"reports/local-redis-mcp-{datetime.now():%Y%m%d}.md")
    args = parser.parse_args()
    if not 0 < args.port < 65536 or not 0 <= args.db < 65536:
        parser.error("port or database outside supported range")
    prefix = "infra-mcp-test:" + uuid.uuid4().hex + ":"
    keys = [prefix + suffix for suffix in ("string", "missing", "hash")]
    checks, cleanup = [], {"authorized": False, "mcp_exact_deletes_and_ttl": False, "fallback_used": False}
    failure_type = None
    direct = None
    temporary_path = None
    try:
        with tempfile.TemporaryDirectory(prefix="infra-mcp-redis-test-") as temporary:
            temporary_path = Path(temporary)
            credentials, references = {}, {}
            for label in ("username", "password"):
                source = getattr(args, label + "_file")
                if source is not None:
                    if source.stat().st_size > 65536:
                        raise ValueError("Credential file exceeds limit")
                    value = source.read_text(encoding="utf-8").rstrip("\r\n")
                    copied = temporary_path / (label + ".txt")
                    secure_write(copied, value)
                    credentials[label] = value
                    references[label + "_file"] = str(copied)
            options = {"host": args.host, "port": args.port, "db": args.db, "timeout": 3,
                       "environment": "local-isolated-test", "scope": {"key_patterns": [prefix + "*"]}, **references}
            profiles = {}
            for name, permissions in [("local-test", ["create", "read", "update", "delete"]), ("local-readonly", ["read"]), ("local-update-only", ["update"])]:
                profiles[name] = {**options, "permissions": {action: action in permissions for action in ["create", "read", "update", "delete"]}}
            config_path = temporary_path / "profiles.json"
            secure_write(config_path, json.dumps({"profiles": {"redis": profiles}}))
            direct = redis.Redis(host=args.host, port=args.port, db=args.db, socket_connect_timeout=3,
                                 socket_timeout=3, retry=Retry(NoBackoff(), 0), **credentials)
            try:
                asyncio.run(exercise(args, config_path, prefix, direct, checks, cleanup))
            finally:
                if cleanup["authorized"]:
                    # Fallback also deletes only the three exact UUID keys we verified absent initially.
                    if not cleanup["mcp_exact_deletes_and_ttl"]:
                        cleanup["fallback_used"] = True
                        direct.delete(*keys)
                    cleanup["exact_keys_remaining"] = direct.exists(*keys)
    except Exception as error:
        failure_type = type(error).__name__
    finally:
        if direct is not None:
            direct.close()
    cleanup["temporary_directory_removed"] = temporary_path is not None and not temporary_path.exists()
    passed = failure_type is None and all(ok for _, ok in checks) and cleanup.get("exact_keys_remaining") == 0 and cleanup["temporary_directory_removed"]
    report = ["# Local Redis MCP verification", "", f"Result: {'PASS' if passed else 'FAIL'}", "",
              f"- Timestamp: {datetime.now(timezone.utc).isoformat()}",
              f"- Endpoint: `{args.host}:{args.port}`, database `{args.db}` (loopback only)",
              "- Transport: real MCP `ClientSession` over child-process stdin/stdout",
              f"- Child command: `{sys.executable} -m infra_mcp redis --config <temporary-0600-profile>`",
              f"- Test prefix: `{prefix}`", f"- Checks: {sum(ok for _, ok in checks)}/{len(checks)} passed",
              f"- Failure class: `{failure_type or 'none'}`; raw backend text withheld", "",
              "| Check | Result |", "| --- | --- |"]
    report.extend(f"| {label} | {'PASS' if ok else 'FAIL'} |" for label, ok in checks)
    report += ["", "## Cleanup evidence", ""]
    report.extend(f"- {name}: `{value}`" for name, value in cleanup.items())
    report += ["", "Only the three exact UUID-owned keys were accessed. No FLUSH, KEYS, SCAN, database-wide count, business values, or remote endpoints were used. Config and any copied credentials were created mode 0600 in a private temporary directory and removed on exit. No services were started or installed.", "",
               "Reproduce:", "", "```sh", f".venv/bin/python scripts/test-local-redis-mcp.py --host {args.host} --port {args.port} --db {args.db}", "```", ""]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"result": "PASS" if passed else "FAIL", "checks_passed": sum(ok for _, ok in checks), "checks_total": len(checks), "cleanup": cleanup, "failure_class": failure_type, "report": str(args.report)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
