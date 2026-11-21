"""Trusted Mac issuer for two named releases. The MCP receives metadata only."""
import asyncio
from contextlib import contextmanager
import ctypes
import fcntl
from importlib import util
import json
import os
from pathlib import Path
import sys
import tempfile

from infra_mcp.paths import config_dir, releases_dir, sessions_dir
from infra_mcp.approval import approval_message, confirm_write

spec = util.spec_from_file_location("k8s_session", Path(__file__).with_name("k8s-session.py"))
sessions = util.module_from_spec(spec)
spec.loader.exec_module(sessions)

ROOT = sessions_dir()
RELEASES = releases_dir()
SETTINGS = config_dir() / "release-issuer.json"
TARGETS = {"develop": {"deployments": ["file"]},
           "higress-system": {"deployments": ["higress-console", "higress-gateway"],
                              "configmaps": ["higress-access-filebeat"]}}


@contextmanager
def manager_lock():
    sessions.safe_path(ROOT, directory=True, private=True)
    fd = os.open(ROOT / ".issuer.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def backend():
    settings = json.loads(sessions.safe_path(SETTINGS, private=True).read_text())
    config = SETTINGS.parent / Path(settings["admin_config"]).expanduser()
    issuer = sessions.Kubectl(Path(os.path.normpath(config)), settings["context"])
    if sessions.connection(issuer)[2] != settings["cluster_fingerprint"]:
        raise sessions.SessionError("Issuer cluster identity changed")
    return issuer


def receipt(sid):
    if not sessions.SESSION_RE.fullmatch(sid):
        raise ValueError("Invalid release session")
    row = sessions.load_receipt(ROOT / sid)
    if row.get("patch_targets") != TARGETS.get(row["namespace"]) or row["namespace"] not in TARGETS:
        raise ValueError("Not a registered release policy")
    return row


def metadata(row):
    info = {k: row.get(k) for k in ("session", "namespace", "state", "expiration_timestamp", "patch_targets")}
    return {**info, "expired": expired(row), "cleanup_on_expiry": row.get("cleanup_on_expiry") is True}


def records():
    return [receipt(p.name) for p in sorted(ROOT.iterdir()) if sessions.SESSION_RE.fullmatch(p.name)]


def installed(namespace):
    file = RELEASES / namespace / "profiles.json"
    if not file.exists():
        return None
    ids = {p["context"] for p in json.loads(file.read_text())["profiles"]["kubernetes"].values()}
    if len(ids) != 1:
        raise ValueError("Mismatched installed release profiles")
    return ids.pop()


def publish(report):
    ns, sid = report["namespace"], report["session"]
    client = ROOT / sid / "client"
    active = sessions.safe_path(RELEASES / ns, directory=True, private=True)
    RELEASES.mkdir(mode=0o700, parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=ns + "-generation-", dir=RELEASES))
    # Both operator entry points move together. Each profile pins its own token
    # path, including during a simultaneous refresh by an old MCP process.
    profile_file = client / "profiles.json"
    profiles = json.loads(profile_file.read_text())
    token = os.path.relpath(client / "subadminconfig", active)
    for profile in profiles["profiles"]["kubernetes"].values():
        profile["kubeconfig"] = token
    sessions.private_json(stage / "profiles.json", profiles)
    (stage / "subadminconfig").symlink_to(token)
    if active.exists():
        lib = ctypes.CDLL(None, use_errno=True)
        if lib.renamex_np(os.fsencode(stage), os.fsencode(active), 2) != 0:  # RENAME_SWAP
            raise OSError(ctypes.get_errno(), "Atomic credential swap failed")
    else:
        os.rename(stage, active)


def remove_copies(row):
    # Match the retired generation; never unlink a replacement just because
    # it uses the same namespace. The caller holds the publication lock.
    ns, sid = row["namespace"], row["session"]
    for directory in RELEASES.iterdir():
        if directory.is_symlink() or not directory.is_dir() or not (directory.name == ns or directory.name.startswith(ns + "-")):
            continue
        for name in ("subadminconfig", "profiles.json"):
            path = directory / name
            if path.is_symlink():
                if Path(os.path.normpath(directory / path.readlink())) != ROOT / sid / "client" / name:
                    continue
            elif path.is_file():
                obj = json.loads(path.read_text())
                contexts = ({obj.get("current-context")} if name == "subadminconfig" else
                            {p.get("context") for p in obj["profiles"]["kubernetes"].values()})
                if contexts != {sid}:
                    continue
            else:
                continue
            path.unlink()
        if directory.name != ns and not any(directory.iterdir()):
            directory.rmdir()


def expired(row):
    return bool(row["expiration_timestamp"] and sessions.timestamp(row["expiration_timestamp"]) <= sessions.now())


def clean(row):
    try:
        result = sessions.revoke(backend(), ROOT / row["session"])
    finally:
        # The API server can be offline at expiry. Retain the receipt for
        # another UID-checked revocation, but discard the expired local token.
        if expired(row):
            sessions.remove_local(ROOT / row["session"])
            remove_copies(row)
    if not result["objects_absent"]:
        raise ValueError("Revocation is pending")
    if not expired(row):
        remove_copies(row)
    return {"session": row["session"], "objects_absent": True}


def ask(action, operation, details):
    asyncio.run(confirm_write(None, approval_message("infra-kubernetes", "release-issuer", action, operation, details)))


def issue(ns):
    if ns not in TARGETS:
        raise ValueError("Unsupported release")
    previous = installed(ns)
    details = {"命名空间": ns, "具名对象 get/patch": TARGETS[ns], "有效期": "1 小时",
               "只读诊断": ["pods", "events"] if ns == "higress-system" else [],
               "当前会话": previous, "到期处理": "自动回收本次会话的专属 RBAC、服务账号、绑定 Secret 和本机凭据"}
    ask("create", "issue_release_credential", details)
    with manager_lock():
        if previous != installed(ns):
            raise ValueError("Installed release changed. Request approval again.")
        issuer = backend()
        targets = [kind + "/" + name for kind, names in TARGETS[ns].items() for name in names]
        report = sessions.issue(issuer, ROOT, ns, patch_targets=targets, release_lifecycle=True)
        try:
            publish(report)
        except BaseException:
            sessions.revoke(issuer, ROOT / report["session"])
            raise
        return metadata(receipt(report["session"]))


def run(args):
    if args == ["list"]:
        return {"credentials": [metadata(row) for row in records() if row["state"] != "revoked"]}
    if len(args) == 2 and args[0] == "issue":
        return issue(args[1])
    if len(args) == 2 and args[0] == "delete-expired":
        row = receipt(args[1])
        if not expired(row):
            raise ValueError("Credential has not expired")
        ask("delete", "delete_expired_release_credential", metadata(row))
        with manager_lock():
            current = receipt(args[1])
            if not expired(current) or current["nonce"] != row["nonce"]:
                raise ValueError("Credential changed. Request approval again.")
            return clean(current)
    if args == ["sweep"]:
        with manager_lock():
            failures = []
            for row in records():
                if row.get("cleanup_on_expiry") is not True:
                    continue
                try:
                    if row["state"] == "revoked":
                        remove_copies(row)
                    elif expired(row) or row["state"] in ("issuing", "cleanup_pending"):
                        clean(row)
                except (OSError, ValueError, sessions.SessionError):
                    failures.append(row["session"])
            if failures:
                raise sessions.SessionError("Cleanup pending for " + ", ".join(failures))
        return {"checked": True}
    raise ValueError("Unsupported issuer operation")


if __name__ == "__main__":
    try:
        print(json.dumps(run(sys.argv[1:]), ensure_ascii=False))
    except Exception as exc:
        from mcp.server.fastmcp.exceptions import ToolError
        # Backend/OS exceptions can contain credential paths or API payloads.
        msg = str(exc) if isinstance(exc, (sessions.SessionError, ToolError)) else "Invalid or unavailable release operation"
        print(json.dumps({"error": msg}), flush=True)
        sys.exit(1)
