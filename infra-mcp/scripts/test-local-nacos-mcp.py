#!/usr/bin/env python3
"""Run real Nacos 3 stdio MCP checks against existing local development containers.

Only exact UUID configuration/service/instance resources are touched. Existing
containers may be temporarily started with --start-existing and are restored in
reverse dependency order. Never initializes users, schemas, images or containers.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import runpy
import tempfile
import time
import uuid

from dotenv import dotenv_values
import httpx


ROOT = Path(__file__).resolve().parents[1]
HELPERS = runpy.run_path(str(ROOT / "scripts/test-local-http-mcp.py"))
docker, secure_write, session_checks = (HELPERS[key] for key in ("docker", "secure_write", "session_checks"))
ACTIONS = ("create", "read", "update", "delete")
URL = "http://127.0.0.1:8848/nacos"


def inspect(name):
    return json.loads(docker("inspect", name))[0]


def container_env(container):
    return dict(item.split("=", 1) for item in container["Config"].get("Env", []) if "=" in item)


def preflight(nacos, database):
    values = container_env(nacos)
    host = values.get("MYSQL_SERVICE_HOST")
    matches = False
    for network, settings in database["NetworkSettings"]["Networks"].items():
        aliases = set(settings.get("Aliases") or []) | {database["Name"].lstrip("/"), settings.get("IPAddress")}
        matches |= network in nacos["NetworkSettings"]["Networks"] and host in aliases
    if not matches or values.get("MYSQL_SERVICE_PORT", "3306") != "3306":
        raise RuntimeError("Database target was not verified as the selected local container")
    if any(key != "MYSQL_SERVICE_HOST" and "HOST" in key and key.startswith("MYSQL") and value
           for key, value in values.items()):
        raise RuntimeError("Additional database target requires explicit inspection")
    if database["HostConfig"].get("Links") or database["Config"].get("Labels", {}).get("com.docker.compose.depends_on"):
        raise RuntimeError("Database container has unreviewed dependencies")
    command = " ".join(database["Config"].get("Cmd") or []).lower()
    if any(flag in command for flag in ("master-host", "source-host", "replica", "slave-", "init-command")):
        raise RuntimeError("Database command contains an unreviewed replication or initialization option")
    if any(container["State"]["Status"] not in ("running", "exited") for container in (nacos, database)):
        raise RuntimeError("Unexpected initial container state")
    return values.get("NACOS_AUTH_ENABLE", "false").lower() == "true"


def envelope(client, method, path, arguments=None, form=False):
    response = client.request(method, "/nacos/v3/admin/" + path,
                              **({"data": arguments} if form else {"params": arguments}))
    try:
        body = response.json()
    except ValueError:
        body = {}
    return response.status_code, body


def absent(client, path, arguments, code):
    _, body = envelope(client, "GET", path, arguments)
    return isinstance(body, dict) and body.get("code") == code


def poll(predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while True:
        if predicate():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)


def exact_cleanup(client, identifiers, cleanup):
    config, service, instance = identifiers
    for key, path, arguments, missing in (("instance_absent", "ns/instance", instance, 20004),
            ("service_absent", "ns/service", service, 21008), ("config_absent", "cs/config", config, 20004)):
        # A service already removed also makes its exact instance absent.
        is_absent = lambda: absent(client, path, arguments, missing) or (
            key == "instance_absent" and absent(client, "ns/service", service, 21008))
        if not is_absent():
            cleanup["direct_fallback_used"] = True
            envelope(client, "DELETE", path, arguments)
        cleanup[key] = poll(is_absent)


async def exercise(config_path, direct, checks, cleanup, resource, group):
    common = {"namespace_id": "public", "group": group}
    ca, sa = {**common, "data_id": resource + ".json"}, {**common, "service_name": resource}
    sa2 = {**common, "service_name": resource + "-page2"}
    ia = {**sa, "ip": "127.0.0.1", "port": 65432, "ephemeral": False}
    direct_common = {"namespaceId": "public", "groupName": group}
    identifiers = ({**direct_common, "dataId": ca["data_id"]},
        {**direct_common, "serviceName": resource},
        {**direct_common, "serviceName": resource, "ip": "127.0.0.1", "port": 65432, "clusterName": "DEFAULT", "ephemeral": "false"})
    second_service = {**direct_common, "serviceName": sa2["service_name"]}

    async def run(call, check):
        async def op(action, operation, arguments):
            return (await call(action, operation, arguments))["data"]

        check("Authenticated Nacos 3 connectivity", (await call("check_connection"))["data"] == {"connected": True, "api_version": 3})
        check("UUID config and service absent before writes", absent(direct, "cs/config", identifiers[0], 20004)
              and absent(direct, "ns/service", identifiers[1], 21008) and absent(direct, "ns/service", second_service, 21008))
        cleanup["authorized_resources"] = True
        try:
            await call("create", "publish_config", {**ca, "content": "synthetic"}, "local-readonly", "permission_denied")
            await call("create", "publish_config", {**ca, "content": "synthetic"}, "local-create-only", "permission_denied")
            await call("delete", "delete_config", ca, "local-readonly", "permission_denied")
            await call("create", "register_instance", ia, "local-create-only", "permission_denied")
            await call("update", "update_instance", ia, "local-update-only", "permission_denied")
            for args in ({**ca, "namespace_id": resource}, {**ca, "group": group + "-outside"}, {**ca, "data_id": resource + "-outside"}):
                await call("read", "get_config", args, denied="scope_denied")
            await call("read", "get_service", {**sa, "service_name": resource + "-outside"}, denied="scope_denied")
            for revision in (1, 2):
                content = json.dumps({"test": resource, "revision": revision})
                check(f"Publish config revision {revision}", (await op("create", "publish_config", {**ca, "content": content, "type": "json"}))["published"] is True)
                check(f"Exact config content revision {revision}", (await op("read", "get_config", ca))["content"] == content)
            page = await op("read", "list_configs", {**common, "page_size": 100})
            check("Scoped config metadata list", len(page["items"]) == 1 and page["items"][0]["dataId"] == ca["data_id"] and "content" not in page["items"][0])
            await op("create", "create_service", {**sa, "ephemeral": False, "protect_threshold": 0.37,
                "metadata": {"owner": resource, "phase": "one"}, "selector": {"type": "none"}})
            service = await op("read", "get_service", sa)
            check("Owned service metadata", service["metadata"] == {"owner": resource, "phase": "one"})
            await call("update", "update_service", {**sa, "metadata": {"phase": "incomplete"}}, denied="invalid_argument")
            await op("update", "update_service", {**sa, "metadata": {"owner": resource, "phase": "two"},
                "protect_threshold": 0.37, "selector": {"type": "none"}})
            service = await op("read", "get_service", sa)
            check("Explicit service replacement preserves threshold", abs(service["protectThreshold"] - 0.37) < 0.00001 and service["metadata"] == {"owner": resource, "phase": "two"})
            await op("create", "create_service", {**sa2, "ephemeral": False, "metadata": {"owner": resource}})
            expected, seen, clean_pages = {resource, sa2["service_name"]}, [], True
            for page_number in range(1, 201):
                page = await op("read", "list_services", {**common, "page": page_number, "page_size": 1})
                check("Namespace page remains bounded and locally scoped", len(page["items"]) <= 1 and all(row["name"] in expected and row["groupName"] == group for row in page["items"]))
                seen.extend(row["name"] for row in page["items"])
                clean_pages &= all(set(row) <= {"name", "groupName", "clusterCount", "ipCount", "healthyInstanceCount", "triggerFlag"} for row in page["items"])
                if set(seen) == expected or not page["has_more"]:
                    break
            check("Two owned services found on distinct pages without duplicates", set(seen) == expected and len(seen) == 2)
            check("Detail pagination strips metadata and instance payloads", clean_pages)
            await op("delete", "delete_service", sa2)
            check("Secondary pagination service removed", poll(lambda: absent(direct, "ns/service", second_service, 21008)))
            await op("create", "register_instance", {**ia, "enabled": False, "weight": 7, "metadata": {"owner": resource, "phase": "one"}})
            check("Instance becomes readable", poll(lambda: envelope(direct, "GET", "ns/instance", identifiers[2])[1].get("code") == 0))
            instance = await op("read", "get_instance", ia)
            check("Synthetic instance disabled with weight seven", instance["enabled"] is False and instance["weight"] == 7)
            await call("update", "update_instance", {**ia, "metadata": {"phase": "incomplete"}}, denied="invalid_argument")
            await op("update", "update_instance", {**ia, "enabled": False, "weight": 7, "metadata": {"owner": resource, "phase": "two"}})
            check("Instance replacement becomes readable", poll(lambda: envelope(direct, "GET", "ns/instance", identifiers[2])[1].get("data", {}).get("metadata", {}).get("phase") == "two"))
            instance = await op("read", "get_instance", ia)
            check("Explicit instance replacement preserves disabled and weight seven", instance["enabled"] is False and instance["weight"] == 7 and instance["metadata"] == {"owner": resource, "phase": "two"})
            instances = await op("read", "list_instances", {**sa, "healthy_only": False})
            check("Only owned synthetic instance listed", isinstance(instances, list) and len(instances) == 1 and instances[0]["ip"] == "127.0.0.1" and instances[0]["port"] == 65432)
            await op("delete", "deregister_instance", ia)
            check("Exact instance removed", poll(lambda: absent(direct, "ns/instance", identifiers[2], 20004)))
            await op("delete", "delete_service", sa)
            check("Exact service removed", poll(lambda: absent(direct, "ns/service", identifiers[1], 21008)))
            check("Exact config deleted", (await op("delete", "delete_config", ca))["deleted"] is True)
            check("Exact config independently absent", absent(direct, "cs/config", identifiers[0], 20004))
        finally:
            for operation, arguments, path, params, code in (("deregister_instance", ia, "ns/instance", identifiers[2], 20004),
                    ("delete_service", sa, "ns/service", identifiers[1], 21008), ("delete_config", ca, "cs/config", identifiers[0], 20004)):
                if absent(direct, path, params, code) or operation == "deregister_instance" and absent(direct, "ns/service", identifiers[1], 21008):
                    continue
                try:
                    await op("delete", operation, arguments)
                except Exception:
                    cleanup["mcp_cleanup_error"] = True

    try:
        await session_checks("nacos", config_path, checks, run)
    finally:
        if cleanup.get("authorized_resources"):
            exact_cleanup(direct, identifiers, cleanup)
            if not absent(direct, "ns/service", second_service, 21008):
                cleanup["direct_fallback_used"] = True
                envelope(direct, "DELETE", "ns/service", second_service)
            cleanup["secondary_service_absent"] = poll(lambda: absent(direct, "ns/service", second_service, 21008))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nacos-container", default="dev-nacos")
    parser.add_argument("--database-container", default="dev-mysql")
    parser.add_argument("--credential-env-file", type=Path, required=True)
    parser.add_argument("--start-existing", action="store_true")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/local-nacos-mcp-20261107.md")
    args = parser.parse_args()
    resource, group = "infra-mcp-test-" + uuid.uuid4().hex, "INFRA_MCP_TEST_" + uuid.uuid4().hex + ".v1"
    checks, cleanup, originals, started = [], {"direct_fallback_used": False}, {}, []
    failure, direct, temp_path = None, None, None
    try:
        nacos, database = inspect(args.nacos_container), inspect(args.database_container)
        auth = preflight(nacos, database)
        for name, container in ((args.nacos_container, nacos), (args.database_container, database)):
            originals[name] = {"state": container["State"]["Status"], "restart": container["HostConfig"]["RestartPolicy"]}
        checks.append(("Database target verified as existing local Docker dependency", True))
        credentials = dotenv_values(args.credential_env_file, interpolate=False)
        username = credentials.get("NACOS_ADMIN_USERNAME") or credentials.get("NACOS_USERNAME")
        password = credentials.get("NACOS_ADMIN_PASSWORD") or credentials.get("NACOS_PASSWORD")
        if auth and (not username or not password or "${" in username or "${" in password):
            raise RuntimeError("Configured API credentials unavailable; no guessing or initialization")
        for name in (args.database_container, args.nacos_container):
            if originals[name]["state"] == "exited":
                if not args.start_existing:
                    raise RuntimeError("Existing local dependency is stopped")
                started.append(name)
                docker("start", name)
            if name == args.database_container:
                if not poll(lambda: inspect(name)["State"].get("Health", {}).get("Status") == "healthy", 60):
                    raise RuntimeError("Existing local database healthcheck unavailable")
                print(json.dumps({"phase": "existing_mysql_healthy"}), flush=True)
        direct = httpx.Client(base_url="http://127.0.0.1:8848", timeout=4, trust_env=False, follow_redirects=False)
        deadline = time.monotonic() + 90
        while True:
            try:
                if auth:
                    response = direct.post("/nacos/v3/auth/user/login", data={"username": username, "password": password})
                    body = response.json()
                    token = body.get("accessToken")
                    if isinstance(token, str) and token:
                        direct.headers["accessToken"] = token
                        break
                    if response.status_code in (401, 403):
                        raise PermissionError("Configured existing Nacos account rejected")
                elif envelope(direct, "GET", "ns/service/selector/types")[1].get("code") == 0:
                    break
            except (httpx.HTTPError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("Nacos did not become ready within the bounded wait")
            time.sleep(2)
        print(json.dumps({"phase": "existing_nacos_authenticated"}), flush=True)
        with tempfile.TemporaryDirectory(prefix="infra-mcp-nacos-test-") as temporary:
            temp_path = Path(temporary)
            references = {}
            if auth:
                for key, value in (("username", username), ("password", password)):
                    path = temp_path / (key + ".txt")
                    secure_write(path, value)
                    references[key + "_file"] = str(path)
            options = {"url": URL, "timeout": 5, "environment": "local-isolated-test", **references,
                "scope": {"namespaces": ["public"], "groups": [group], "data_ids": [resource + ".json"], "services": [resource, resource + "-page2"]}}
            profiles = {}
            for name, permissions in (("local-test", ACTIONS), ("local-readonly", ["read"]),
                    ("local-create-only", ["create"]), ("local-update-only", ["update"])):
                profiles[name] = {**options, "permissions": {action: action in permissions for action in ACTIONS}}
            config_path = temp_path / "profiles.json"
            secure_write(config_path, json.dumps({"profiles": {"nacos": profiles}}))
            asyncio.run(exercise(config_path, direct, checks, cleanup, resource, group))
    except Exception as error:
        failure = type(error).__name__
    finally:
        if direct:
            direct.close()
        cleanup["temporary_credentials_removed"] = temp_path is not None and not temp_path.exists()
        for name in reversed(started):
            try:
                docker("stop", "--time", "20", name)
            except Exception as error:
                failure = failure or type(error).__name__
        for name, original in originals.items():
            try:
                current = inspect(name)
                cleanup[name + "_state_restored"] = current["State"]["Status"] == original["state"]
                cleanup[name + "_restart_unchanged"] = current["HostConfig"]["RestartPolicy"] == original["restart"]
            except Exception as error:
                failure = failure or type(error).__name__
    passed = failure is None and checks and all(ok for _, ok in checks) and all(cleanup.get(key) for key in
        ("config_absent", "service_absent", "secondary_service_absent", "instance_absent", "temporary_credentials_removed")) and all(
            cleanup.get(name + "_state_restored") and cleanup.get(name + "_restart_unchanged") for name in originals)
    lines = ["# Local Nacos 3 MCP verification", "", f"Result: {'PASS' if passed else 'FAIL / NOT FULLY VERIFIED'}", "",
        f"Timestamp: {datetime.now(timezone.utc).isoformat()}", f"Endpoint: `{URL}`; existing Nacos `v3.0.0`.",
        "Transport: real `mcp.ClientSession` over `.venv/bin/python -m infra_mcp nacos --config <temporary-0600-profile>`.",
        f"Exact test group: `{group}`; data ID: `{resource}.json`; service: `{resource}`; instance: `127.0.0.1:65432`, persistent and disabled.",
        f"Secondary service `{resource}-page2` exists only to verify distinct `page_size=1` pages; the group contains a literal dot to exercise exact local filtering.",
        "Only owned UUID resources were created, modified or deleted; configuration content reads used only synthetic test content. Service pagination is scoped to the namespace at the backend and then filtered by exact group/service locally: other groups' metadata can enter memory but is never output or saved. Existing credentials were read privately from the original local .env and referenced through mode-0600 temporary files. No administrator initialization, database schema operation, remote backend, image pull, new container, or global configuration change was performed.",
        "Service and instance updates supply every replacement field explicitly. Incomplete metadata-only updates must fail before any backend request.",
        f"Checks passed: {sum(ok for _, ok in checks)}/{len(checks)}. Failure class: `{failure or 'none'}`; arbitrary backend text withheld.",
        "", "| Check | Result |", "| --- | --- |"]
    lines.extend(f"| {label} | {'PASS' if ok else 'FAIL'} |" for label, ok in checks)
    lines.extend(["", "## Cleanup and original-state restoration", "", "```json", json.dumps(cleanup, indent=2), "```", ""])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"result": "PASS" if passed else "FAIL", "checks": len(checks), "failure_class": failure,
        "cleanup": cleanup, "report": str(args.report)}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
