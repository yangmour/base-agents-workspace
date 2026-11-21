#!/usr/bin/env python3
"""Exercise the real MySQL stdio MCP in one disposable schema on a running local container.

The administrator harness owns only infra_mcp_smoke_<uuid>. It never starts or
stops containers, changes users/grants, or reads existing application tables.
Credentials remain in memory and are passed to the MCP via one environment
variable. --execute explicitly enables fixture DDL and its exact cleanup.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pymysql


ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ("create", "read", "update", "delete")
SECRET_ENV = "INFRA_MCP_MYSQL_SMOKE_PASSWORD"
ERROR_CODES = re.compile(r"\b(?:permission_denied|scope_denied|invalid_argument|invalid_operation|"
    r"backend_error|result_too_large|response_too_large|output_limit|timeout|outcome_unknown)\b")


def inspect_container(name):
    result = subprocess.run(["docker", "inspect", name], capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError("Local Docker metadata unavailable; details withheld")
    return json.loads(result.stdout)[0]


def verify_target(container, port):
    bindings = container["NetworkSettings"].get("Ports", {}).get("3306/tcp") or []
    if container["State"]["Status"] != "running" or not any(
        item["HostPort"] == str(port) and item["HostIp"] in {"127.0.0.1", "0.0.0.0"}
        for item in bindings
    ):
        raise RuntimeError("Selected container is not already running on the specified localhost port")
    if "mysql" not in container["Config"]["Image"].lower():
        raise RuntimeError("Selected container image is not MySQL")
    values = dict(item.split("=", 1) for item in container["Config"].get("Env", []) if "=" in item)
    if "MYSQL_ROOT_PASSWORD" not in values and values.get("MYSQL_ALLOW_EMPTY_PASSWORD", "").lower() not in {"1", "yes", "true"}:
        raise RuntimeError("Existing administrator credential source is unavailable")
    return values.get("MYSQL_ROOT_PASSWORD", "")


def connect_admin(port, password):
    return pymysql.connect(host="127.0.0.1", port=port, user="root", password=password,
        charset="utf8mb4", autocommit=True, connect_timeout=3, read_timeout=5,
        write_timeout=5, local_infile=False, ssl_disabled=True)


def scalar(connection, sql, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, parameters)
        row = cursor.fetchone()
        return row[0] if row else None


def create_fixtures(connection, schema):
    statements = [
        "CREATE TABLE items (id BIGINT PRIMARY KEY AUTO_INCREMENT, name VARCHAR(255) NOT NULL UNIQUE, quantity INT NOT NULL, secret_token VARCHAR(255)) ENGINE=InnoDB",
        "CREATE TABLE composite_items (tenant INT NOT NULL, id INT NOT NULL, name VARCHAR(255), PRIMARY KEY(tenant,id)) ENGINE=InnoDB",
        "CREATE TABLE no_primary (id INT, name VARCHAR(255)) ENGINE=InnoDB",
        "CREATE TABLE unique_not_primary (id INT NOT NULL UNIQUE, name VARCHAR(255)) ENGINE=InnoDB",
        "CREATE TABLE varchar_keys (id VARCHAR(255) PRIMARY KEY, name VARCHAR(255)) ENGINE=InnoDB",
        "CREATE TABLE bigint_keys (id BIGINT PRIMARY KEY, name VARCHAR(255)) ENGINE=InnoDB",
        "CREATE TABLE nontransactional (id INT PRIMARY KEY, name VARCHAR(255)) ENGINE=MyISAM",
        "CREATE TABLE large_values (id INT PRIMARY KEY, payload LONGBLOB) ENGINE=InnoDB",
        "CREATE VIEW item_view AS SELECT id,name FROM items",
    ]
    with connection.cursor() as cursor:
        cursor.execute(f"USE `{schema}`")
        for statement in statements:
            cursor.execute(statement)
        cursor.execute("INSERT INTO large_values(id,payload) VALUES (%s,%s)", (1, b"x" * (2 * 1024 * 1024)))
        cursor.execute("INSERT INTO large_values(id,payload) VALUES (%s,%s)", (2, b"y" * 10000))
        cursor.execute("INSERT INTO composite_items(tenant,id,name) VALUES (%s,%s,%s),(%s,%s,%s)", (1, 7, "one", 2, 7, "two"))
        cursor.execute("INSERT INTO no_primary(id,name) VALUES (%s,%s)", (1, "unkeyed"))
        cursor.execute("INSERT INTO unique_not_primary(id,name) VALUES (%s,%s)", (1, "unique-only"))
        cursor.execute("INSERT INTO varchar_keys(id,name) VALUES (%s,%s),(%s,%s)", ("alpha", "target", "beta", "original"))
        cursor.execute("INSERT INTO bigint_keys(id,name) VALUES (%s,%s),(%s,%s)", (9007199254740992, "target", 9007199254740993, "original"))


def profiles_for(schema, port):
    options = {"host": "127.0.0.1", "port": port, "username": "root", "password_env": SECRET_ENV,
        "database": schema, "tls": False, "timeout": 3, "environment": "local-disposable-test",
        "scope": {"databases": [schema], "tables": [schema + ".*"]}}
    profiles = {"local-test": {**options, "allow_after_approval": ["create", "update", "delete"]}, "default": options}
    for disabled in ACTIONS:
        profiles["deny-" + disabled] = {**options, "permissions": {action: action != disabled for action in ACTIONS}}
    profiles["items-only"] = {**options, "scope": {"databases": [schema], "tables": [schema + ".items"]}}
    profiles["small-output"] = {**options, "max_output_bytes": 1024}
    return {"profiles": {"mysql": profiles}}


async def exercise(config, password, schema, admin, port, checks):
    def check(label, condition):
        checks.append((label, bool(condition)))
        if not condition:
            raise AssertionError(label)

    params = StdioServerParameters(command=sys.executable,
        args=["-m", "infra_mcp", "mysql", "--config", str(config)], cwd=str(ROOT),
        env={"PYTHONPATH": str(ROOT / "src"), SECRET_ENV: password})
    with open(os.devnull, "w") as errors:
        async with stdio_client(params, errlog=errors) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=150)) as session:
                await session.initialize()
                check("Real stdio initialize", True)

                async def call(tool, operation=None, arguments=None, connection="local-test", denied=None, hidden=()):
                    request = {} if tool.startswith("list_") else {"connection": connection}
                    if operation:
                        request.update(operation=operation, arguments=arguments or {})
                    result = await session.call_tool(tool, request)
                    raw = " ".join(item.text for item in result.content if item.type == "text")
                    # Inspect complete error payloads, but never persist arbitrary backend text.
                    if result.isError:
                        protected = [*hidden, *([password] if password else [])]
                        check("Error payload withholds credentials and supplied sensitive literals", all(value not in raw for value in protected))
                    if denied is not None:
                        codes = (denied,) if isinstance(denied, str) else denied
                        check(f"Denied {tool}/{operation or tool}: {' or '.join(codes)}", bool(result.isError) and any(code in raw for code in codes))
                        return raw
                    code = ERROR_CODES.search(raw) if result.isError else None
                    check(f"MCP success {tool}/{operation or tool}" + (f" ({code.group()})" if code else ""), not result.isError)
                    return result.structuredContent or json.loads(raw)

                async def op(action, operation, arguments=None, connection="local-test"):
                    return (await call(action, operation, arguments, connection))["data"]

                tools = (await session.list_tools()).tools
                check("Exactly seven fixed tools", {tool.name for tool in tools} == {"list_connections", "list_operations", "check_connection", *ACTIONS})
                connections = await call("list_connections")
                check("Connection discovery exposes no options or credentials", all(set(item) == {"name", "environment", "permissions", "allow_after_approval", "scope"} for item in connections["connections"]))
                default = next(item for item in connections["connections"] if item["name"] == "default")
                check("Omitted permissions default to read only", default["permissions"] == {action: action == "read" for action in ACTIONS})
                operations = (await call("list_operations"))["operations"]
                check("Eight structured operations and no SQL or DDL operation", set(operations) == {"check_connection", "list_databases", "list_tables", "describe_table", "select_rows", "insert_row", "update_row", "delete_row"})
                check("Authenticated MySQL check", (await call("check_connection"))["data"] == {"reachable": True})

                for action, operation, arguments in [
                    ("read", "select_rows", {"table": "items"}),
                    ("create", "insert_row", {"table": "items", "values": {"name": "denied", "quantity": 0}}),
                    ("update", "update_row", {"table": "items", "key": {"id": 1}, "values": {"quantity": 0}}),
                    ("delete", "delete_row", {"table": "items", "key": {"id": 1}}),
                ]:
                    await call(action, operation, arguments, "deny-" + action, "permission_denied")
                await call("check_connection", connection="deny-read", denied="permission_denied")
                await call("read", "delete_row", {"table": "items", "key": {"id": 1}}, denied="permission_denied")
                await call("read", "select_rows", {"database": schema + "_outside", "table": "items"}, denied="scope_denied")
                await call("read", "select_rows", {"table": "composite_items"}, "items-only", "scope_denied")
                await call("read", "select_rows", {"database": "mysql", "table": "user"}, denied=("scope_denied", "invalid_argument"))

                # Only metadata names are scanned outside the test schema; scope must filter output.
                found = []
                offset = 0
                for _ in range(20):
                    page = await op("read", "list_databases", {"limit": 200, "offset": offset})
                    check("Database discovery only returns the owned schema", set(page["databases"]) <= {schema})
                    found.extend(page["databases"])
                    if not page["has_more"]:
                        break
                    offset = page["offset"]
                check("Owned schema appears in discovery", schema in found)
                tables = await op("read", "list_tables", {"limit": 100})
                check("Metadata lists owned test table", "items" in tables["tables"])
                scoped = await op("read", "list_tables", {"limit": 100}, "items-only")
                check("Table discovery filters qualified scope", scoped["tables"] == ["items"])
                description = await op("read", "describe_table", {"table": "composite_items"})
                check("Describe preserves composite primary-key order", description["primary_key"] == ["tenant", "id"] and description["engine"] == "InnoDB")

                ids = []
                literal = "bound'; DROP TABLE items; -- 中文🙂"
                for name in (literal, "second", "third"):
                    created = await op("create", "insert_row", {"table": "items", "values": {"name": name, "quantity": 1, "secret_token": "synthetic-sensitive-value"}})
                    check("Single-row INSERT committed", created["affected_rows"] == 1 and created["last_insert_id"] > 0)
                    ids.append(created["last_insert_id"])
                selected = await op("read", "select_rows", {"table": "items", "columns": ["id", "name"], "where": [{"column": "name", "op": "eq", "value": literal}]})
                check("SQL-looking Unicode value is bound and round-trips unchanged", selected["rows"] == [{"id": ids[0], "name": literal}])
                page = await op("read", "select_rows", {"table": "items", "columns": ["id"], "order_by": [{"column": "id", "direction": "asc"}], "limit": 2})
                check("First ordered page has two rows and continuation", page["rows"] == [{"id": ids[0]}, {"id": ids[1]}] and page["has_more"] and page["offset"] == 2)
                tail = await op("read", "select_rows", {"table": "items", "columns": ["id"], "order_by": [{"column": "id", "direction": "asc"}], "limit": 2, "offset": page["offset"]})
                check("Second ordered page ends without duplicates", tail["rows"] == [{"id": ids[2]}] and not tail["has_more"])
                redacted = await call("read", "select_rows", {"table": "items", "columns": ["secret_token"], "limit": 1})
                check("Sensitive column is redacted", redacted["redacted"] and redacted["data"]["rows"][0]["secret_token"] == "[REDACTED]")
                check("Full-key UPDATE affects one row", (await op("update", "update_row", {"table": "items", "key": {"id": ids[0]}, "values": {"quantity": 7}}))["affected_rows"] == 1)
                check("Committed UPDATE visible independently", scalar(admin, "SELECT quantity FROM items WHERE id=%s", (ids[0],)) == 7)
                check("Composite full key updates one tenant", (await op("update", "update_row", {"table": "composite_items", "key": {"id": 7, "tenant": 1}, "values": {"name": "updated"}}))["affected_rows"] == 1)
                check("Other composite-key tenant remains unchanged", scalar(admin, "SELECT name FROM composite_items WHERE tenant=2 AND id=7") == "two")
                await call("update", "update_row", {"table": "varchar_keys", "key": {"id": 0}, "values": {"name": "target"}}, denied="invalid_argument")
                check("Numeric input cannot coerce VARCHAR primary keys into a multirow update", scalar(admin, "SELECT COUNT(*) FROM varchar_keys WHERE (id='alpha' AND name='target') OR (id='beta' AND name='original')") == 2)
                await call("update", "update_row", {"table": "bigint_keys", "key": {"id": float(9007199254740992)}, "values": {"name": "target"}}, denied="invalid_argument")
                check("Floating input cannot collapse adjacent BIGINT primary keys", scalar(admin, "SELECT COUNT(*) FROM bigint_keys WHERE (id=9007199254740992 AND name='target') OR (id=9007199254740993 AND name='original')") == 2)

                for operation, arguments in [
                    ("update_row", {"table": "composite_items", "key": {"id": 7}, "values": {"name": "bad"}}),
                    ("delete_row", {"table": "composite_items", "key": {"id": 7}}),
                    ("update_row", {"table": "items", "key": {"id": ids[0]}, "values": {"id": 999}}),
                    ("update_row", {"table": "no_primary", "key": {"id": 1}, "values": {"name": "bad"}}),
                    ("delete_row", {"table": "no_primary", "key": {"id": 1}}),
                    ("update_row", {"table": "unique_not_primary", "key": {"id": 1}, "values": {"name": "bad"}}),
                    ("delete_row", {"table": "unique_not_primary", "key": {"id": 1}}),
                ]:
                    await call("delete" if operation == "delete_row" else "update", operation, arguments, denied="invalid_argument")
                for table in ("nontransactional", "item_view"):
                    await call("read", "select_rows", {"table": table}, denied="invalid_argument")
                for arguments in (
                    {"table": "items; DROP TABLE items"}, {"table": "items", "columns": ["name,SLEEP(10)"]},
                    {"table": "items", "where": [{"column": "id", "op": "eq OR 1=1", "value": 1}]},
                    {"table": "items", "order_by": [{"column": "id", "direction": "asc; DROP TABLE items"}]},
                    {"table": "items", "sql": "SELECT 1"},
                ):
                    await call("read", "select_rows", arguments, denied="invalid_argument")

                await call("update", "update_row", {"table": "items", "key": {"id": ids[1]}, "values": {"name": literal, "quantity": 999}}, denied="backend_error", hidden=(literal,))
                check("Duplicate-key error leaves both requested columns unchanged", scalar(admin, "SELECT COUNT(*) FROM items WHERE id=%s AND name=%s AND quantity=1", (ids[1], "second")) == 1)
                await call("create", "insert_row", {"table": "items", "values": {"name": literal, "quantity": 1}}, denied="backend_error", hidden=(literal,))
                check("Failed INSERT adds no row", scalar(admin, "SELECT COUNT(*) FROM items") == 3)

                # A separate test-owned transaction holds a row lock. The MCP must
                # report failure without committing or leaking its SQL/parameters.
                locker = connect_admin(port, password)
                try:
                    locker.begin()
                    with locker.cursor() as cursor:
                        cursor.execute(f"SELECT id FROM `{schema}`.items WHERE id=%s FOR UPDATE", (ids[0],))
                    started = time.monotonic()
                    await call("update", "update_row", {"table": "items", "key": {"id": ids[0]}, "values": {"quantity": 999}}, denied=("timeout", "backend_error"))
                    check("Lock-contention failure is bounded", time.monotonic() - started < 10)
                finally:
                    locker.rollback()
                    locker.close()
                check("Timed-out write did not commit", scalar(admin, "SELECT quantity FROM items WHERE id=%s", (ids[0],)) == 7)
                check("Fresh connection works after lock timeout", (await call("check_connection"))["data"] == {"reachable": True})

                await call("read", "select_rows", {"table": "large_values"}, denied=("result_too_large", "response_too_large", "output_limit"))
                check("Fresh connection works after oversized row abort", (await call("check_connection"))["data"] == {"reachable": True})
                check("Oversized read never changes stored bytes", scalar(admin, "SELECT OCTET_LENGTH(payload) FROM large_values WHERE id=1") == 2 * 1024 * 1024)
                limited = await call("read", "select_rows", {"table": "large_values", "columns": ["payload"], "where": [{"column": "id", "op": "eq", "value": 2}]}, "small-output")
                check("Serialized output cap is explicit and bounded", limited["truncated"] and len(json.dumps(limited["data"]).encode()) <= 1024)
                for row_id in ids:
                    check("Full-key DELETE affects one row", (await op("delete", "delete_row", {"table": "items", "key": {"id": row_id}}))["affected_rows"] == 1)
                check("Repeated DELETE reports zero affected rows", (await op("delete", "delete_row", {"table": "items", "key": {"id": ids[0]}}))["affected_rows"] == 0)
                check("All CRUD rows removed independently", scalar(admin, "SELECT COUNT(*) FROM items") == 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="codex-oneapi8-085546a79e39-mysql")
    parser.add_argument("--port", type=int, default=52635)
    parser.add_argument("--execute", action="store_true", help="Create and remove this run's UUID test schema")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/local-mysql-mcp-20261107.md")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Pass --execute to run disposable-schema DDL and real MCP checks")
    schema = "infra_mcp_smoke_" + uuid.uuid4().hex
    checks, cleanup = [], {"schema_created": False, "schema_absent": False, "temporary_config_removed": False}
    admin = original = temporary_path = None
    password = ""
    failure = None
    version = "not connected"
    started = time.monotonic()
    try:
        original = inspect_container(args.container)
        password = verify_target(original, args.port)
        admin = connect_admin(args.port, password)
        version = scalar(admin, "SELECT VERSION()")
        if not str(version).startswith(("8.0.", "8.4.")):
            raise RuntimeError("Only the validated MySQL 8.0/8.4 series is supported by this harness")
        exists = scalar(admin, "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,))
        if exists:
            raise RuntimeError("UUID schema unexpectedly exists; it will not be modified")
        checks.append(("Selected running localhost MySQL and UUID schema absence verified", True))
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4")
        cleanup["schema_created"] = True
        create_fixtures(admin, schema)
        with tempfile.TemporaryDirectory(prefix="infra-mcp-mysql-smoke-") as temporary:
            temporary_path = Path(temporary)
            config = temporary_path / "profiles.json"
            fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(profiles_for(schema, args.port), stream)
            asyncio.run(exercise(config, password, schema, admin, args.port, checks))
    except BaseException as error:
        # Raw driver/ExceptionGroup diagnostics can contain values and DSNs.
        failure = type(error).__name__
    finally:
        if admin is not None:
            try:
                admin.close()
            except Exception:
                pass
        if cleanup["schema_created"]:
            try:
                # Drop only a successfully created UUID schema owned by this run.
                if not re.fullmatch(r"infra_mcp_smoke_[0-9a-f]{32}", schema):
                    raise RuntimeError("Invalid owned schema marker")
                connection = connect_admin(args.port, password)
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(f"DROP DATABASE `{schema}`")
                    cleanup["schema_absent"] = scalar(connection, "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,)) == 0
                finally:
                    connection.close()
            except Exception as error:
                cleanup["cleanup_error_type"] = type(error).__name__
                failure = failure or "CleanupFailure"
        cleanup["temporary_config_removed"] = temporary_path is None or not temporary_path.exists()
        try:
            current = inspect_container(args.container)
            cleanup["container_unchanged"] = original is not None and all([
                current["Id"] == original["Id"], current["State"]["Status"] == original["State"]["Status"] == "running",
                current["State"]["StartedAt"] == original["State"]["StartedAt"],
                current["HostConfig"]["RestartPolicy"] == original["HostConfig"]["RestartPolicy"],
            ])
        except Exception:
            cleanup["container_unchanged"] = False
        passed = failure is None and checks and all(ok for _, ok in checks) and all(cleanup.get(key) for key in ("schema_absent", "temporary_config_removed", "container_unchanged"))
        report = ["# Local MySQL MCP real stdio verification", "", f"- UTC: {datetime.now(timezone.utc).isoformat()}",
            f"- Result: {'PASS' if passed else 'FAIL'}", f"- MySQL version: `{version}`",
            f"- Container: `{args.container}`; localhost port: `{args.port}`", f"- Owned disposable schema: `{schema}`",
            f"- Duration: {time.monotonic() - started:.2f} seconds", f"- Passed checks: {sum(ok for _, ok in checks)}/{len(checks)}",
            f"- Failure class: `{failure or 'none'}`", "", "## Checks", ""]
        report += [f"- [{'x' if ok else ' '}] {label}" for label, ok in checks]
        report += ["", "## Cleanup evidence", "", "```json", json.dumps(cleanup, indent=2, sort_keys=True), "```", "",
            "Only this run's random schema was created and removed. Existing business tables were not read or modified.",
            "Passwords were read from local Docker metadata into memory and passed via a child environment variable; no credential values or raw backend errors are recorded.",
            "The MCP only ran structured metadata/data operations. Administrator fixture DDL and exact schema cleanup were performed by this harness.", ""]
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text("\n".join(report), encoding="utf-8")
        print(json.dumps({"result": "PASS" if passed else "FAIL", "checks": len(checks), "passed": sum(ok for _, ok in checks), "failure_type": failure, "cleanup": cleanup, "report": str(args.report)}), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
