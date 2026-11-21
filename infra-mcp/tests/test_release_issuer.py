import asyncio
from importlib import util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from infra_mcp import tunnel


@pytest.fixture
def issuer(tmp_path, monkeypatch):
    src = Path(__file__).resolve().parents[1] / "scripts/k8s-release-issuer.py"
    spec = util.spec_from_file_location("test_operator_release_broker", src)
    mod = util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    root = tmp_path / "sessions"
    root.mkdir(mode=0o700)
    releases = tmp_path / "releases"
    releases.mkdir(mode=0o700)
    monkeypatch.setattr(mod, "ROOT", root)
    monkeypatch.setattr(mod, "RELEASES", releases)
    return mod


def test_issue_is_scoped_and_requires_a_new_decision(issuer, monkeypatch):
    ask = Mock(side_effect=RuntimeError("declined"))
    backend = Mock()
    monkeypatch.setattr(issuer, "ask", ask)
    monkeypatch.setattr(issuer, "backend", backend)
    for _ in range(2):
        with pytest.raises(RuntimeError, match="declined"):
            issuer.run(["issue", "develop"])
    assert ask.call_count == 2
    assert ask.call_args.args[2]["具名对象 get/patch"] == {"deployments": ["file"]}
    with pytest.raises(ValueError):
        issuer.run(["issue", "kube-system"])
    backend.assert_not_called()


def test_sweep_respects_grant_and_expiry(issuer, monkeypatch):
    def record(name, expiry, grant=True):
        return {"session": name, "state": "active", "cleanup_on_expiry": grant, "expiration_timestamp": expiry}
    old, live, unmanaged = (record("old", "2000-01-01T00:00:00Z"), record("live", "2100-01-01T00:00:00Z"),
                            record("unmanaged", "2000-01-01T00:00:00Z", False))
    clean = Mock()
    monkeypatch.setattr(issuer, "records", lambda: [old, live, unmanaged])
    monkeypatch.setattr(issuer, "clean", clean)
    issuer.run(["sweep"])
    clean.assert_called_once_with(old)


@pytest.mark.skipif(sys.platform != "darwin", reason="Mac operator directory exchange")
def test_publication_and_expiry_do_not_remove_the_successor(issuer):
    for sid in ("old", "new"):
        client = issuer.ROOT / sid / "client"
        client.mkdir(parents=True, mode=0o700)
        (client / "profiles.json").write_text(json.dumps({"profiles": {"kubernetes": {
            "release-deployments": {"context": sid, "kubeconfig": "subadminconfig"}}}}))
        (client / "subadminconfig").write_text(json.dumps({"current-context": sid}))
        issuer.publish({"session": sid, "namespace": "develop"})
    issuer.remove_copies({"session": "old", "namespace": "develop"})
    assert issuer.installed("develop") == "new"
    assert json.loads((issuer.RELEASES / "develop/subadminconfig").read_text())["current-context"] == "new"


@pytest.mark.parametrize("action,op,args", [
    ("read", "issue_release_credential", {"release": "develop"}),
    ("delete", "issue_release_credential", {"release": "develop"}),
    ("create", "issue_release_credential", {"release": "develop", "admin_config": "/tmp/override"}),
    ("read", "sweep", {}),
    ("delete", "delete_expired_release_credential", {"session": "old", "force": True}),
])
def test_mcp_cannot_reclassify_an_issue_or_invoke_sweep(monkeypatch, action, op, args):
    child = AsyncMock()
    monkeypatch.setattr(tunnel.asyncio, "create_subprocess_exec", child)
    with pytest.raises(ValueError):
        asyncio.run(tunnel.call_issuer(action, {"operation": op, "arguments": args}))
    child.assert_not_called()


@pytest.mark.skipif(sys.platform != "darwin", reason="Mac operator directory exchange")
def test_published_generation_survives_directory_move(issuer, tmp_path, monkeypatch):
    import os
    root = tmp_path / "original layout"
    monkeypatch.setattr(issuer, "ROOT", root / "state/sessions")
    monkeypatch.setattr(issuer, "RELEASES", root / "custom/releases")
    client = issuer.ROOT / "current" / "client"
    client.mkdir(mode=0o700, parents=True)
    profiles = {"profiles": {"kubernetes": {"release-deployments":
                {"context": "current", "kubeconfig": "subadminconfig"}}}}
    (client / "profiles.json").write_text(json.dumps(profiles))
    (client / "subadminconfig").write_text("test credential")
    issuer.publish({"session": "current", "namespace": "develop"})
    moved = tmp_path / "moved layout"
    root.rename(moved)
    active = moved / "custom/releases/develop"
    ref = json.loads((active / "profiles.json").read_text())["profiles"]["kubernetes"]["release-deployments"]["kubeconfig"]
    assert not Path(ref).is_absolute() and not Path(os.readlink(active / "subadminconfig")).is_absolute()
    assert (active / ref).read_text() == (active / "subadminconfig").read_text() == "test credential"
    monkeypatch.setattr(issuer, "ROOT", moved / "state/sessions")
    monkeypatch.setattr(issuer, "RELEASES", moved / "custom/releases")
    # Expiry removes the pinned source first; cleanup must still recognize its dangling link.
    (moved / "state/sessions/current/client/subadminconfig").unlink()
    issuer.remove_copies({"session": "current", "namespace": "develop"})
    assert not list(active.iterdir())


def test_operator_paths_follow_custom_environment(tmp_path, monkeypatch):
    from infra_mcp import paths
    for key in ("XDG_CONFIG_HOME", "XDG_BIN_HOME", "XDG_STATE_HOME"):
        monkeypatch.setenv(key, str(tmp_path / key))
    monkeypatch.delenv("INFRA_MCP_CONFIG", raising=False)
    monkeypatch.delenv("FN_MCP_RELEASE_DIR", raising=False)
    assert paths.profile_file() == tmp_path / "XDG_CONFIG_HOME/infra-mcp/profiles.json"
    assert paths.releases_dir() == tmp_path / "XDG_CONFIG_HOME/infra-mcp/releases"
    assert paths.bin_dir() == tmp_path / "XDG_BIN_HOME"
    assert paths.sessions_dir() == tmp_path / "XDG_STATE_HOME/infra-mcp/release-sessions"
    monkeypatch.setenv("FN_MCP_RELEASE_DIR", str(tmp_path / "releases elsewhere"))
    assert paths.releases_dir() == tmp_path / "releases elsewhere"


@pytest.mark.parametrize("relative", [True, False])
def test_admin_config_is_anchored_to_issuer_settings(issuer, tmp_path, monkeypatch, relative):
    settings = tmp_path / "config" / "issuer.json"
    settings.parent.mkdir()
    operator = tmp_path / "cluster" / "config"
    settings.write_text(json.dumps({"admin_config": "../cluster/config" if relative else str(operator),
                                    "context": "pinned", "cluster_fingerprint": "test"}))
    settings.chmod(0o600)
    monkeypatch.setattr(issuer, "SETTINGS", settings)
    cli = Mock()
    monkeypatch.setattr(issuer.sessions, "Kubectl", cli)
    monkeypatch.setattr(issuer.sessions, "connection", lambda _: (None, None, "test"))
    monkeypatch.chdir(tmp_path)
    issuer.backend()
    cli.assert_called_once_with(operator, "pinned")


def test_logging_issues_three_isolated_named_sessions_after_approval(issuer, monkeypatch):
    calls = []
    def issue(backend, root, namespace, *, logging_rules, release_lifecycle):
        assert calls[0] == "approved" and release_lifecycle
        assert all(rule["resourceNames"] and "*" not in rule["resourceNames"] for rule in logging_rules)
        assert all(rule["resources"][0] not in {"secrets","roles","rolebindings"} for rule in logging_rules)
        assert all(r["resourceNames"] == ["logging-filebeat-stage"] for r in logging_rules if r["resources"] == ["pods/exec"])
        calls.append(namespace)
        return {"session": namespace, "child_config": str(root / namespace / "client/subadminconfig")}
    monkeypatch.setattr(issuer, "ask", lambda *args: calls.append("approved"))
    monkeypatch.setattr(issuer, "backend", lambda: object())
    monkeypatch.setattr(issuer.sessions, "issue", issue)
    monkeypatch.setattr(issuer, "receipt", lambda ns: {"session": ns, "namespace": ns, "expiration_timestamp": None})
    result = issuer.run(["issue", "logging"])
    assert calls == ["approved", "develop", "observability", "higress-system"]
    assert len(result["credentials"]) == 3
