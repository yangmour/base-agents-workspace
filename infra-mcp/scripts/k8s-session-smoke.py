#!/usr/bin/env python3
"""Explicit live rehearsal: issue -> MCP ConfigMap CRUD -> revoke -> clean up.

This is an operator integration test, not an unattended credential issuer.
Only a new, randomly named namespace and resources created by this run are changed.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import ssl
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
TOKEN_DURATION = "24h"
TOKEN_MAX_LIFETIME = dt.timedelta(days=1)


def now():
    return dt.datetime.now(dt.timezone.utc)


class TrialFailure(Exception):
    pass


class AdminFailure(TrialFailure):
    def __init__(self, reason):
        super().__init__(f"Administrator request failed: {reason}")
        self.reason = reason


class Trial:
    def __init__(self, admin_config: Path, report_dir: Path):
        self.admin_config = admin_config.resolve()
        self.report_dir = report_dir.resolve()
        self.report_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.private = self.report_dir / "private"
        self.private.mkdir(mode=0o700)
        self.session = "ai-" + secrets.token_hex(10)
        self.namespace = "infra-mcp-trial-" + secrets.token_hex(6)
        self.nonce = secrets.token_hex(16)
        self.child_config = self.private / "subadminconfig"
        self.profile_path = self.private / "profiles.private.json"
        self.http = None
        self.cluster = None
        self.expires = None
        self.context = None
        self.state = {"started_at": now().isoformat(), "namespace": self.namespace,
                      "session": self.session, "scope": "ConfigMap CRUD only",
                      "resources": {}, "events": [], "result": "running"}
        self.admin_hash = hashlib.sha256(self.admin_config.read_bytes()).hexdigest()
        self.save()

    def save(self):
        destination = self.report_dir / "receipt.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2))
        temporary.chmod(0o600)
        temporary.replace(destination)

    def record(self, stage, **details):
        event = {"time": now().isoformat(), "stage": stage, **details}
        self.state["events"].append(event)
        self.save()
        print(json.dumps(event, ensure_ascii=False), flush=True)

    def admin(self, args, payload=None):
        cmd = ["kubectl", "--kubeconfig", str(self.admin_config), "--request-timeout=15s"]
        if self.context:
            cmd += ["--context", self.context]
        result = subprocess.run(cmd + args, input=json.dumps(payload) if payload is not None else None,
                                capture_output=True, text=True, timeout=22)
        if result.returncode:
            text = result.stderr.lower()
            reason = next((label for marker, label in [
                ("(notfound)", "not_found"), ("(alreadyexists)", "already_exists"),
                ("(conflict)", "uid_conflict"), ("(forbidden)", "forbidden"),
                ("(unauthorized)", "unauthorized"), ("x509", "tls_error")]
                if marker in text), "request_error")
            raise AdminFailure(reason)
        try:
            return json.loads(result.stdout)
        except ValueError:
            raise TrialFailure("Administrator command did not return JSON") from None

    def create(self, key, manifest, path):
        manifest.setdefault("metadata", {}).setdefault("labels", {})["infra-mcp-trial"] = self.nonce
        self.state["resources"][key] = {"path": path, "name": manifest["metadata"]["name"],
                                        "uid": None, "creation_attempted": True}
        self.save()
        try:
            created = self.admin(["create", "-f", "-", "-o", "json"], manifest)
        except AdminFailure as error:
            if error.reason == "already_exists":
                self.state["resources"][key]["creation_attempted"] = False
                self.save()
            raise
        self.state["resources"][key]["uid"] = created["metadata"]["uid"]
        self.record("created", resource=key, uid=created["metadata"]["uid"])
        return created

    def existing(self, record):
        try:
            return self.admin(["get", "--raw=" + record["path"]])
        except AdminFailure as error:
            if error.reason == "not_found":
                return None
            raise

    def delete(self, key):
        record = self.state["resources"].get(key)
        if not record or not record["creation_attempted"]:
            return
        current = self.existing(record)
        if current is None:
            record["absent_verified"] = True
            self.save()
            return
        meta = current["metadata"]
        if record["uid"] is None and meta.get("labels", {}).get("infra-mcp-trial") == self.nonce:
            record["uid"] = meta["uid"]
            self.save()
        if record["uid"] != meta["uid"]:
            raise TrialFailure("Cleanup refused a resource with a different UID")
        self.admin(["delete", "--raw=" + record["path"], "-f", "-"], {
            "apiVersion": "v1", "kind": "DeleteOptions",
            "preconditions": {"uid": record["uid"]}, "propagationPolicy": "Background"})
        self.record("deletion_requested", resource=key)

    def wait_absent(self, key, seconds=25):
        record = self.state["resources"].get(key)
        if not record or not record["creation_attempted"]:
            return
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if self.existing(record) is None:
                record["absent_verified"] = True
                self.record("absence_verified", resource=key)
                return
            time.sleep(1)
        raise TrialFailure(f"Resource cleanup is still pending: {key}")

    def issue(self):
        config = self.admin(["config", "view", "--minify", "--flatten", "--raw", "-o", "json"])
        self.context = config["current-context"]
        self.cluster = config["clusters"][0]["cluster"]
        if self.cluster.get("insecure-skip-tls-verify") or not self.cluster.get("certificate-authority-data"):
            raise TrialFailure("Verified TLS and an embedded cluster CA are required")
        if not self.cluster.get("server", "").startswith("https://") or self.cluster.get("proxy-url"):
            raise TrialFailure("This rehearsal requires a direct HTTPS cluster connection")
        version = self.admin(["get", "--raw=/version"])["gitVersion"]
        self.state["server_version"] = version
        self.state["cluster_fingerprint"] = hashlib.sha256(self.cluster["server"].encode()).hexdigest()[:16]
        self.record("cluster_connected", server_version=version)
        ns = self.namespace
        self.create("namespace", {"apiVersion": "v1", "kind": "Namespace", "metadata": {
            "name": ns, "labels": {"pod-security.kubernetes.io/enforce": "restricted",
                                   "pod-security.kubernetes.io/enforce-version": "latest"}}}, f"/api/v1/namespaces/{ns}")
        core = f"/api/v1/namespaces/{ns}"
        rbac = f"/apis/rbac.authorization.k8s.io/v1/namespaces/{ns}"
        metadata = {"name": self.session, "namespace": ns}
        self.create("serviceaccount", {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": dict(metadata),
                                       "automountServiceAccountToken": False}, f"{core}/serviceaccounts/{self.session}")
        anchor = self.create("anchor", {"apiVersion": "v1", "kind": "Secret", "type": "Opaque", "metadata": dict(metadata)},
                             f"{core}/secrets/{self.session}")
        self.create("role", {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "Role", "metadata": dict(metadata),
                             "rules": [{"apiGroups": [""], "resources": ["configmaps"],
                                        "verbs": ["get", "list", "watch", "create", "update", "patch", "delete"]}]},
                    f"{rbac}/roles/{self.session}")
        self.create("rolebinding", {"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding", "metadata": dict(metadata),
            "subjects": [{"kind": "ServiceAccount", "name": self.session, "namespace": ns}],
            "roleRef": {"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": self.session}},
            f"{rbac}/rolebindings/{self.session}")
        requested_at = now()
        token_response = self.admin(["-n", ns, "create", "token", self.session,
            "--bound-object-kind=Secret", "--bound-object-name=" + self.session,
            "--bound-object-uid=" + anchor["metadata"]["uid"], "--duration=" + TOKEN_DURATION, "-o", "json"])
        status = token_response["status"]
        self.expires = dt.datetime.fromisoformat(status["expirationTimestamp"].replace("Z", "+00:00"))
        if not now() < self.expires <= now() + TOKEN_MAX_LIFETIME:
            raise TrialFailure("Actual token expiry exceeds the 24-hour policy or is already expired")
        child_cluster = {key: self.cluster[key] for key in ("server", "certificate-authority-data", "tls-server-name") if key in self.cluster}
        child = {"apiVersion": "v1", "kind": "Config", "current-context": self.session,
            "clusters": [{"name": "session-cluster", "cluster": child_cluster}],
            "users": [{"name": self.session, "user": {"token": status["token"]}}],
            "contexts": [{"name": self.session, "context": {"cluster": "session-cluster", "user": self.session, "namespace": ns}}]}
        session_profile = {"kubeconfig": str(self.child_config), "context": self.session, "timeout": 20,
                           "permissions": {key: True for key in ("create", "read", "update", "delete")},
                           "scope": {"namespaces": [ns], "resources": ["configmaps"]}}
        profiles = {"profiles": {"kubernetes": {"trial": session_profile}}}
        for path, data in [(self.child_config, child), (self.profile_path, profiles)]:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as output:
                json.dump(data, output)
        ca = base64.b64decode(self.cluster["certificate-authority-data"]).decode()
        self.http = httpx.Client(base_url=self.cluster["server"].rstrip("/"),
            verify=ssl.create_default_context(cadata=ca), timeout=10, follow_redirects=False,
            trust_env=False, headers={"Authorization": "Bearer " + status["token"]})
        self.state["expiration_timestamp"] = status["expirationTimestamp"]
        self.state["requested_token_duration"] = TOKEN_DURATION
        self.state["actual_requested_lifetime_seconds"] = round((self.expires - requested_at).total_seconds())
        self.record("temporary_credentials_issued", expires_at=status["expirationTimestamp"],
                    file_mode=oct(self.child_config.stat().st_mode & 0o777), contains_admin_credentials=False)

    def request(self, method, path, payload=None):
        extensions = {"sni_hostname": self.cluster["tls-server-name"]} if self.cluster.get("tls-server-name") else {}
        return self.http.request(method, path, json=payload, extensions=extensions)

    def expect_status(self, path, expected, stage, wait_seconds=0):
        deadline = time.monotonic() + wait_seconds
        while True:
            response = self.request("GET", path)
            if response.status_code == expected:
                if expected == 401 and now() >= self.expires:
                    raise TrialFailure("Token expired naturally before revocation could be demonstrated")
                self.record(stage, http_status=expected)
                return
            if time.monotonic() >= deadline:
                raise TrialFailure(f"{stage}: expected HTTP {expected}, got {response.status_code}")
            time.sleep(1)

    def verify_permissions(self):
        for verb in ("get", "list", "watch", "create", "update", "patch", "delete"):
            self.permission(verb, "configmaps", True)
        for verb, resource, group, subresource, namespace in [
            ("get", "secrets", "", None, self.namespace),
            ("create", "pods", "", None, self.namespace),
            ("create", "serviceaccounts", "", "token", self.namespace),
            ("create", "rolebindings", "rbac.authorization.k8s.io", None, self.namespace),
            ("get", "nodes", "", None, ""),
            ("get", "configmaps", "", None, "default")]:
            self.permission(verb, resource, False, group, subresource, namespace)
        self.expect_status(f"/api/v1/namespaces/{self.namespace}/secrets", 403, "secret_read_denied")
        self.expect_status("/api/v1/namespaces/default/configmaps", 403, "other_namespace_denied")

    def permission(self, verb, resource, expected, group="", subresource=None, namespace=None):
        attrs = {"namespace": self.namespace if namespace is None else namespace, "verb": verb,
                 "group": group, "resource": resource}
        if subresource:
            attrs["subresource"] = subresource
        response = self.request("POST", "/apis/authorization.k8s.io/v1/selfsubjectaccessreviews", {
            "apiVersion": "authorization.k8s.io/v1", "kind": "SelfSubjectAccessReview",
            "spec": {"resourceAttributes": attrs}})
        if (response.status_code not in (200, 201)
                or response.json().get("status", {}).get("allowed") is not expected
                or response.json().get("status", {}).get("evaluationError")):
            raise TrialFailure(f"Unexpected authorization for {verb} {resource}")
        self.record("permission_verified", verb=verb, resource=resource, subresource=subresource, allowed=expected,
                    namespace=attrs["namespace"])

    async def exercise(self):
        env = {key: os.environ[key] for key in ("PATH", "HOME", "TMPDIR", "LANG") if key in os.environ}
        env["PYTHONPATH"] = str(ROOT / "src")
        params = StdioServerParameters(command=sys.executable,
            args=["-m", "infra_mcp", "kubernetes", "--config", str(self.profile_path)], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()

                async def call(tool, operation=None, arguments=None):
                    args = {"connection": "trial"}
                    if operation:
                        args.update(operation=operation, arguments=arguments or {})
                    result = await client.call_tool(tool, args)
                    if result.isError:
                        raise TrialFailure(f"MCP tool failed: {tool}/{operation or tool}")
                    data = json.loads(result.content[0].text)
                    if data.get("ok") is not True:
                        raise TrialFailure("MCP returned a non-success envelope")
                    return data["data"]

                await call("check_connection")
                self.record("mcp_connected")
                target = {"namespace": self.namespace, "resource": "configmaps", "name": "crud-probe"}
                created = await call("create", "create", {**target, "manifest": {
                    "apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "crud-probe", "namespace": self.namespace},
                    "data": {"phase": "created", "session": self.session}}})
                self.state["resources"]["configmap"] = {"path": f"/api/v1/namespaces/{self.namespace}/configmaps/crud-probe",
                    "name": "crud-probe", "uid": created["metadata"]["uid"], "creation_attempted": True}
                self.record("mcp_create_verified", resource="configmap")
                read_back = await call("read", "get", target)
                if read_back.get("data", {}).get("phase") != "created":
                    raise TrialFailure("Created ConfigMap did not read back correctly")
                self.record("mcp_read_verified")
                await call("update", "patch", {**target, "patch": {"data": {"phase": "updated"}}})
                read_back = await call("read", "get", target)
                if read_back.get("data", {}).get("phase") != "updated":
                    raise TrialFailure("Updated ConfigMap did not read back correctly")
                self.record("mcp_update_verified")
                await call("delete", "delete", target)
                await asyncio.to_thread(self.expect_status, self.state["resources"]["configmap"]["path"], 404,
                                        "mcp_delete_verified", 15)
                own_list = f"/api/v1/namespaces/{self.namespace}/configmaps"
                await asyncio.to_thread(self.expect_status, own_list, 200, "authorized_before_revocation")
                await asyncio.to_thread(self.delete, "rolebinding")
                await asyncio.to_thread(self.wait_absent, "rolebinding")
                await asyncio.to_thread(self.expect_status, own_list, 403, "rbac_revocation_verified", 60)
                denied = await client.call_tool("read", {"connection": "trial", "operation": "list",
                                                       "arguments": {"namespace": self.namespace, "resource": "configmaps"}})
                if not denied.isError:
                    raise TrialFailure("MCP remained usable after RBAC revocation")
                self.record("mcp_rejects_revoked_permissions")
                await asyncio.to_thread(self.delete, "anchor")
                await asyncio.to_thread(self.wait_absent, "anchor")
                await asyncio.to_thread(self.expect_status, own_list, 401, "bound_token_revocation_verified", 90)
                sa = await asyncio.to_thread(self.existing, self.state["resources"]["serviceaccount"])
                if sa is None:
                    raise TrialFailure("ServiceAccount was absent; anchor-only revocation was not isolated")
                self.record("anchor_revocation_proven_with_serviceaccount_present")

    def cleanup(self):
        failures = []
        try:
            for key in ("rolebinding", "anchor", "serviceaccount", "role", "configmap", "namespace"):
                try:
                    self.delete(key)
                    self.wait_absent(key, 90 if key == "namespace" else 20)
                except Exception as error:
                    failures.append({"resource": key, "error_type": type(error).__name__})
                    try:
                        self.record("cleanup_pending", resource=key, error_type=type(error).__name__)
                    except OSError:
                        print(json.dumps({"stage": "cleanup_pending", "resource": key, "receipt_write_failed": True}), flush=True)
        finally:
            if self.http:
                try:
                    self.http.close()
                except Exception:
                    pass
            for path in (self.child_config, self.profile_path):
                try:
                    path.unlink(missing_ok=True)
                except OSError as error:
                    failures.append({"resource": "local_" + path.name, "error_type": type(error).__name__})
            try:
                self.private.rmdir()
            except OSError as error:
                failures.append({"resource": "local_private_directory", "error_type": type(error).__name__})
        self.state["cleanup_complete"] = not failures
        self.state["cleanup_failures"] = failures
        self.state["local_credentials_removed"] = not self.child_config.exists()
        try:
            self.state["admin_source_unchanged"] = hashlib.sha256(self.admin_config.read_bytes()).hexdigest() == self.admin_hash
        except OSError:
            self.state["admin_source_unchanged"] = None
        self.record("cleanup_finished", complete=not failures, local_credentials_removed=self.state["local_credentials_removed"],
                    admin_source_unchanged=self.state["admin_source_unchanged"])

    def report(self):
        self.state["finished_at"] = now().isoformat()
        self.save()
        started = dt.datetime.fromisoformat(self.state["started_at"]).astimezone(ZoneInfo("Asia/Shanghai"))
        lines = ["# Kubernetes 临时凭据真实验证", "", f"- 开始时间：{started.isoformat()}",
                 f"- 结果：{self.state['result']}", f"- 测试范围：{self.state['scope']}",
                 f"- 临时命名空间：{self.namespace}", f"- 会话身份：{self.session}",
                 f"- 实际到期时间：{self.state.get('expiration_timestamp', '未签发')}",
                 f"- 远端清理完成：{self.state.get('cleanup_complete', False)}",
                 f"- 本地子凭据已删除：{self.state.get('local_credentials_removed', False)}",
                 f"- 原管理员配置未改变：{self.state.get('admin_source_unchanged', False)}", "",
                 "## 脱敏事件记录", "", "| 时间（UTC） | 验证步骤 | 结果 |", "|---|---|---|"]
        for event in self.state["events"]:
            details = {k: v for k, v in event.items() if k not in {"time", "stage"}}
            lines.append(f"| {event['time']} | {event['stage']} | `{json.dumps(details, ensure_ascii=False)}` |")
        lines += ["", "验证项为真实 stdio MCP ConfigMap CRUD，以及 API 明确 HTTP 状态区分 RBAC 撤权与 Token 吊销；各项实际结果以上述事件记录为准。",
                  "只改变本次创建的测试资源；未创建业务 Pod/Deployment。本次不证明完整 workload Admission 隔离或独立自动清理器已经部署。"]
        (self.report_dir / "report.md").write_text("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-config", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Explicitly authorize creation and cleanup of this trial's resources")
    args = parser.parse_args()
    if not args.execute:
        parser.error("This is a live integration test; pass --execute to run it")
    os.umask(0o077)
    trial = Trial(args.admin_config, args.report_dir)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        trial.issue()
        trial.verify_permissions()
        asyncio.run(asyncio.wait_for(trial.exercise(), timeout=300))
        trial.state["result"] = "passed"
    except BaseException as error:
        trial.state["result"] = "failed"
        safe_message = str(error) if isinstance(error, TrialFailure) else type(error).__name__
        trial.record("trial_failed", error=safe_message)
    finally:
        trial.cleanup()
        if not trial.state["cleanup_complete"]:
            trial.state["result"] = "cleanup_pending"
        trial.report()
    return 0 if trial.state["result"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
