import json

import pytest

from infra_mcp.base import BaseService, Operation
from infra_mcp.config import ConfigStore, InfraError, Profile, integer, secret


class DemoService(BaseService):
    service = "redis"
    operations = {
        "get": Operation("read", "get value"),
        "set": Operation("update", "update value"),
        "declare": Operation("create", "upsert", additional_permissions=("update",)),
    }

    def __init__(self, config):
        super().__init__(config)
        self.calls = []

    def execute(self, profile, operation, arguments):
        self.calls.append((profile.name, operation, arguments))
        if arguments.get("fail"):
            raise RuntimeError("password=SHOULD_NEVER_LEAK")
        return arguments.get("result", {"value": profile.options.get("value", "ok")})


def store(tmp_path, profiles):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"profiles": {"redis": profiles}}))
    return ConfigStore(path)


def test_absent_permissions_enables_all_crud(tmp_path):
    p = store(tmp_path, {"local": {}}).get("redis", "local")
    assert p.permissions == frozenset({"create", "read", "update", "delete"})


def test_file_references_use_config_directory_after_working_directory_changes(tmp_path, monkeypatch):
    profile_dir = tmp_path / "local profiles"
    profile_dir.mkdir()
    (profile_dir / "password").write_text("test-secret\n")
    absolute_ca = tmp_path / "ca.pem"
    monkeypatch.chdir(tmp_path)
    path = profile_dir / "profiles.json"
    path.write_text(json.dumps({"profiles": {
        "redis": {"local": {"password_file": "password", "ca_file": str(absolute_ca)}},
        "kubernetes": {"session": {"kubeconfig": "client/subadminconfig", "context": "session"}},
    }}))
    config = ConfigStore(path.relative_to(tmp_path))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    redis = config.get("redis", "local")
    assert secret(redis, "password") == "test-secret"
    assert redis.options["ca_file"] == str(absolute_ca)
    assert config.get("kubernetes", "session").options["kubeconfig"] == str(profile_dir / "client/subadminconfig")


def test_mysql_connections_have_independent_crud_permissions(tmp_path):
    path = tmp_path / "mysql.json"
    path.write_text(json.dumps({"profiles": {"mysql": {
        "all": {}, "read-only": {"permissions": {"read": True}},
        "write": {"permissions": {"create": True, "update": True},
                  "scope": {"databases": ["app"], "tables": ["app.*"]}},
    }}}))
    config = ConfigStore(path)
    assert config.get("mysql", "all").permissions == {"create", "read", "update", "delete"}
    assert config.get("mysql", "read-only").permissions == {"read"}
    assert config.get("mysql", "write").permissions == {"create", "update"}
    config.get("mysql", "write").check_scope("tables", "app.tasks")
    with pytest.raises(InfraError):
        config.get("mysql", "write").check_scope("tables", "other.tasks")


def test_partial_permissions_deny_unspecified_actions(tmp_path):
    p = store(tmp_path, {"prod": {"permissions": {"read": True, "delete": False}}}).get("redis", "prod")
    assert p.permissions == {"read"}
    with pytest.raises(InfraError, match="permission"):
        p.require("update")


@pytest.mark.parametrize("permissions", [{"read": "false"}, {"read": 1}, {"write": True}, [], None])
def test_permissions_fail_closed_on_invalid_values(tmp_path, permissions):
    with pytest.raises(InfraError):
        store(tmp_path, {"bad": {"permissions": permissions}}).profiles("redis")


def test_configuration_reloads_and_connections_do_not_leak(tmp_path):
    cfg = store(tmp_path, {"a": {"value": "a"}, "b": {"value": "b"}})
    service = DemoService(cfg)
    assert service.run("a", "read", "get")["data"]["value"] == "a"
    assert service.run("b", "read", "get")["data"]["value"] == "b"
    cfg.path.write_text(json.dumps({"profiles": {"redis": {"a": {"permissions": {"read": False}}}}}))
    with pytest.raises(InfraError):
        service.run("a", "read", "get")
    with pytest.raises(InfraError):
        service.run("b", "read", "get")
    assert len(service.calls) == 2


@pytest.mark.parametrize("action,operation", [("update", "set"), ("read", "set"), ("delete", "get"), ("create", "declare")])
def test_denied_and_misclassified_operations_never_call_backend(tmp_path, action, operation):
    service = DemoService(store(tmp_path, {"ro": {"permissions": {"read": True}}}))
    with pytest.raises(InfraError):
        service.run("ro", action, operation)
    assert service.calls == []


def test_create_only_profile_cannot_redeclare_existing_entities(tmp_path):
    service = DemoService(store(tmp_path, {"c": {"permissions": {"create": True}}}))
    with pytest.raises(InfraError):
        service.run("c", "create", "declare")
    assert not service.calls


def test_missing_configuration_starts_with_empty_profiles(tmp_path):
    service = DemoService(ConfigStore(tmp_path / "not-created.json"))
    assert service.list_connections() == {"connections": [], "configuration_needed": True}


def test_connection_listing_never_returns_options_or_secrets(tmp_path):
    service = DemoService(store(tmp_path, {"local": {"password_env": "SECRET_ENV_NAME", "url": "http://private-host:8888"}}))
    result = json.dumps(service.list_connections())
    assert "private-host" not in result
    assert "SECRET_ENV_NAME" not in result


def test_backend_errors_never_echo_credentials(tmp_path):
    with pytest.raises(InfraError) as error:
        DemoService(store(tmp_path, {"local": {}})).run("local", "read", "get", {"fail": True})
    assert error.value.code == "backend_error"
    assert "SHOULD_NEVER_LEAK" not in str(error.value)


def test_scopes_reject_cross_scope_patterns_and_controls(tmp_path):
    p = store(tmp_path, {"local": {"scope": {"key_patterns": ["app:*", "fixed"]}}}).get("redis", "local")
    p.check_scope("key_patterns", "app:one")
    p.check_scope("key_patterns", "app:*")
    for name in ("other", "*", "app:a\n", "app:[a-z]*"):
        with pytest.raises(InfraError):
            p.check_scope("key_patterns", name)


def test_duplicate_json_keys_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"profiles":{},"profiles":{}}')
    with pytest.raises(InfraError):
        ConfigStore(path).profiles("redis")


def test_inline_credentials_rejected(tmp_path):
    with pytest.raises(InfraError):
        store(tmp_path, {"bad": {"password": "plaintext"}}).profiles("redis")


def test_secret_references_are_exclusive_and_resolved_at_call_time(tmp_path, monkeypatch):
    cfg = store(tmp_path, {"local": {"password_env": "INFRA_TEST_PASSWORD"}})
    monkeypatch.setenv("INFRA_TEST_PASSWORD", "example-one")
    assert secret(cfg.get("redis", "local"), "password") == "example-one"
    monkeypatch.setenv("INFRA_TEST_PASSWORD", "example-two")
    assert secret(cfg.get("redis", "local"), "password") == "example-two"
    monkeypatch.delenv("INFRA_TEST_PASSWORD")
    with pytest.raises(InfraError):
        secret(cfg.get("redis", "local"), "password")


def test_business_data_redaction_and_explicit_opt_out(tmp_path):
    service = DemoService(store(tmp_path, {"safe": {}, "raw": {"redact": False}}))
    arguments = {"result": {"password": "sensitive", "nested": {"api_key": "secret"}, "content": "visible"}}
    safe = service.run("safe", "read", "get", arguments)
    assert safe["data"]["password"] == "[REDACTED]"
    assert safe["data"]["nested"]["api_key"] == "[REDACTED]"
    assert safe["redacted"] is True
    assert service.run("raw", "read", "get", arguments)["data"]["password"] == "sensitive"


def test_results_bound_total_bytes_and_list_entries(tmp_path):
    service = DemoService(store(tmp_path, {"small": {"max_output_bytes": 2048, "max_items": 3}}))
    result = service.run("small", "read", "get", {"result": ["x" * 2000] * 20})
    assert result["truncated"] is True
    assert len(json.dumps(result, ensure_ascii=False).encode()) <= 3000


@pytest.mark.parametrize("value", [True, "1", 1.2, -1, 501])
def test_integer_rejects_ambiguous_and_unbounded_input(value):
    with pytest.raises(InfraError):
        integer({"count": value}, "count", 100, 0, 500)
