"""Reloadable named profiles and the authorization boundary shared by all backends."""
from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ACTIONS = frozenset({"create", "read", "update", "delete"})
SERVICES = frozenset({"redis", "rabbitmq", "elasticsearch", "kubernetes", "nacos", "mysql", "rocketmq", "jenkins"})
FILE_OPTIONS = frozenset({"username_file", "password_file", "api_key_file", "token_file", "ca_file", "kubeconfig"})


class InfraError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate_name(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 1024 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise InfraError("invalid_argument", f"Invalid {label}")
    return value


def integer(arguments: dict, name: str, default: int, minimum: int, maximum: int) -> int:
    value = arguments.get(name, default)
    if type(value) is not int or not minimum <= value <= maximum:
        raise InfraError("invalid_argument", f"{name} must be an integer between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class Profile:
    name: str
    service: str
    options: dict[str, Any]
    permissions: frozenset[str]
    scope: dict[str, list[str]]

    @property
    def timeout(self) -> float:
        value = self.options.get("timeout", 10)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 120:
            raise InfraError("invalid_config", "timeout must be greater than 0 and at most 120 seconds")
        return float(value)

    def require(self, action: str) -> None:
        if action not in ACTIONS or action not in self.permissions:
            raise InfraError("permission_denied", f"Connection '{self.name}' does not grant {action} permission")

    def check_scope(self, kind: str, value: str) -> None:
        validate_name(value, kind)
        patterns = self.scope.get(kind, ["*"])
        # A caller-supplied glob must not broaden the configured resource boundary.
        if any(c in value for c in "*?["):
            allowed = "*" in patterns or value in patterns
        else:
            allowed = any(fnmatch.fnmatchcase(value, pattern) for pattern in patterns)
        if not allowed:
            raise InfraError("scope_denied", f"Requested {kind} is outside this connection's scope")


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise InfraError("invalid_config", "Duplicate JSON configuration keys are not allowed")
        result[name] = value
    return result


class ConfigStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().absolute()

    def profiles(self, service: str) -> dict[str, Profile]:
        if service not in SERVICES:
            raise InfraError("invalid_config", "Unknown service")
        if not self.path.exists():
            return {}
        try:
            if self.path.stat().st_size > 2 * 1024 * 1024:
                raise InfraError("invalid_config", "Configuration exceeds 2 MiB")
            data = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        except InfraError:
            raise
        except (OSError, ValueError, RecursionError):
            raise InfraError("invalid_config", "Cannot read a valid JSON configuration") from None
        if not isinstance(data, dict) or set(data) != {"profiles"} or not isinstance(data["profiles"], dict):
            raise InfraError("invalid_config", "Expected an object containing profiles grouped by service")
        if set(data["profiles"]) - SERVICES:
            raise InfraError("invalid_config", "Unknown service in profiles")
        section = data["profiles"].get(service, {})
        if not isinstance(section, dict):
            raise InfraError("invalid_config", "Service profiles must be a JSON object")
        return {validate_name(name, "connection name"): self._profile(service, name, raw) for name, raw in section.items()}

    def _profile(self, service: str, name: str, raw: Any) -> Profile:
        if not isinstance(raw, dict):
            raise InfraError("invalid_config", "Each connection must be a JSON object")
        if "permissions" in raw:
            permissions = raw["permissions"]
            if not isinstance(permissions, dict) or set(permissions) - ACTIONS or any(type(v) is not bool for v in permissions.values()):
                raise InfraError("invalid_config", "permissions must contain only boolean create/read/update/delete entries")
            permitted = frozenset(k for k, v in permissions.items() if v)
        else:
            permitted = ACTIONS
        if service == "jenkins":
            grants = raw.get("capabilities", [])
            if not isinstance(grants, list) or not all(isinstance(g, str) and g in
                    {"deploy", "rollback", "configure", "cancel"} for g in grants):
                raise InfraError("invalid_config", "Unsupported Jenkins capabilities")
        scope = raw.get("scope", {})
        allowed_scope_keys = {
            "redis": {"key_patterns"}, "rabbitmq": {"vhosts", "queues", "exchanges"},
            "elasticsearch": {"indices"}, "kubernetes": {"namespaces", "resources", "names"},
            "nacos": {"namespaces", "groups", "data_ids", "services"},
            "mysql": {"databases", "tables"},
            "rocketmq": {"topics", "groups"},
            "jenkins": {"jobs"},
        }[service]
        if not isinstance(scope, dict) or set(scope) - allowed_scope_keys:
            raise InfraError("invalid_config", "Invalid resource scope keys")
        for patterns in scope.values():
            if not isinstance(patterns, list) or any(not isinstance(p, str) for p in patterns):
                raise InfraError("invalid_config", "Each resource scope must be a list of patterns")
            for pattern in patterns:
                validate_name(pattern, "scope pattern")
        if any(k in raw for k in ("password", "api_key", "token")):
            raise InfraError("invalid_config", "Use secret _env or _file references instead of inline credentials")
        for key in ("redact", "verify_tls", "tls"):
            if key in raw and type(raw[key]) is not bool:
                raise InfraError("invalid_config", f"{key} must be a boolean")
        options = {k: v for k, v in raw.items() if k not in {"scope", "permissions"}}
        # Clients can start the same server from different working directories.
        for key in FILE_OPTIONS & options.keys():
            value = options[key]
            if isinstance(value, str) and value.strip():
                try:
                    options[key] = str(self.path.parent / Path(value).expanduser())
                except RuntimeError:
                    raise InfraError("invalid_config", f"Cannot expand home directory in {key}") from None
        profile = Profile(name, service, options, permitted, scope)
        _ = profile.timeout
        integer(options, "max_output_bytes", 131072, 1024, 1048576)
        integer(options, "max_items", 200, 1, 5000)
        return profile

    def get(self, service: str, connection: str) -> Profile:
        validate_name(connection, "connection")
        profile = self.profiles(service).get(connection)
        if profile is None:
            raise InfraError("unknown_connection", "Unknown connection; use list_connections first")
        return profile


def secret(profile: Profile, name: str, required: bool = False) -> str | None:
    environment = profile.options.get(f"{name}_env")
    filename = profile.options.get(f"{name}_file")
    if environment is not None and filename is not None:
        raise InfraError("invalid_config", f"Choose one {name} secret reference")
    value = None
    if environment is not None:
        validate_name(environment, "environment variable reference")
        value = os.environ.get(environment)
    if filename is not None:
        validate_name(filename, "secret file reference")
        try:
            path = Path(filename).expanduser()
            if path.stat().st_size > 65536:
                raise InfraError("invalid_config", "Secret file exceeds 64 KiB")
            value = path.read_text(encoding="utf-8").rstrip("\r\n")
        except (OSError, ValueError):
            raise InfraError("missing_secret", f"Cannot read {name} secret file") from None
    if value is None and (required or environment is not None or filename is not None):
        raise InfraError("missing_secret", f"The configured {name} secret is unavailable")
    return value
