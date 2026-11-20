"""Fixed action authorization, sanitized errors and bounded results."""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from typing import Any

from .config import ACTIONS, ConfigStore, InfraError, Profile, integer


@dataclass(frozen=True)
class Operation:
    action: str
    description: str
    parameters: dict[str, str] = field(default_factory=dict)
    additional_permissions: tuple[str, ...] = ()


SENSITIVE = re.compile(r"(?:password|passwd|authorization|credential|secret|token|api[_-]?key|private[_-]?key)", re.I)


def bounded_data(value: Any, profile: Profile) -> tuple[Any, bool, bool]:
    max_items = integer(profile.options, "max_items", 200, 1, 5000)
    max_bytes = integer(profile.options, "max_output_bytes", 131072, 1024, 1048576)
    truncated = False
    redacted = False

    def walk(item, depth=0):
        nonlocal truncated, redacted
        if depth > 24:
            truncated = True
            return "[DEPTH LIMIT]"
        if isinstance(item, bytes):
            try:
                item = item.decode("utf-8")
            except UnicodeDecodeError:
                item = {"encoding": "base64", "value": base64.b64encode(item).decode("ascii")}
        if isinstance(item, dict):
            result = {}
            if len(item) > max_items:
                truncated = True
            is_k8s_secret = item.get("kind") == "Secret"
            for key, child in list(item.items())[:max_items]:
                key = str(key)
                if profile.options.get("redact", True) and (SENSITIVE.search(key) or is_k8s_secret and key in {"data", "stringData"}):
                    result[key] = "[REDACTED]"
                    redacted = True
                elif profile.options.get("redact", True) and key == "value" and SENSITIVE.search(str(item.get("name", ""))):
                    result[key] = "[REDACTED]"
                    redacted = True
                else:
                    result[key] = walk(child, depth + 1)
            return result
        if isinstance(item, (tuple, list, set, frozenset)):
            if len(item) > max_items:
                truncated = True
            return [walk(child, depth + 1) for child in list(item)[:max_items]]
        if isinstance(item, str) and len(item.encode("utf-8")) > max_bytes // 2:
            truncated = True
            return item.encode("utf-8")[:max_bytes // 2].decode("utf-8", errors="ignore")
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        return str(item)

    result = walk(value)
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(encoded) > max_bytes:
        truncated = True
        result = {"preview": encoded[:max_bytes // 2].decode("utf-8", errors="ignore"), "notice": "Output truncated; narrow the query"}
    return result, truncated, redacted


class BaseService:
    service: str
    operations: dict[str, Operation]

    def __init__(self, config: ConfigStore):
        self.config = config

    def list_connections(self) -> dict:
        profiles = self.config.profiles(self.service)
        return {"connections": [self.connection_metadata(p) for p in profiles.values()],
                "configuration_needed": not bool(profiles)}

    def connection_metadata(self, profile: Profile) -> dict:
        return {"name": profile.name, "environment": profile.options.get("environment", ""),
                "permissions": {action: action in profile.permissions for action in sorted(ACTIONS)},
                "scope": profile.scope}

    def list_operations(self) -> dict:
        return {"operations": {name: {"action": op.action, "description": op.description,
                                       "parameters": op.parameters,
                                       "additional_permissions": list(op.additional_permissions)}
                               for name, op in self.operations.items()}}

    def run(self, connection: str, action: str, operation: str, arguments: dict | None = None) -> dict:
        if not isinstance(operation, str) or operation not in self.operations:
            raise InfraError("invalid_operation", "Unknown operation; use list_operations first")
        op = self.operations[operation]
        if action not in ACTIONS or op.action != action:
            raise InfraError("permission_denied", "Operation does not belong to the requested CRUD action")
        profile = self.config.get(self.service, connection)
        # Check the fixed classification before opening sockets or starting subprocesses.
        profile.require(action)
        for extra in op.additional_permissions:
            profile.require(extra)
        if arguments is not None and not isinstance(arguments, dict):
            raise InfraError("invalid_argument", "arguments must be a JSON object")
        try:
            value = self.execute(profile, operation, arguments or {})
            data, truncated, redacted = bounded_data(value, profile)
        except InfraError:
            raise
        except Exception as error:
            # Backend exceptions often contain DSNs, HTTP auth, or full command lines.
            raise InfraError("backend_error", f"{self.service} request failed ({type(error).__name__}); check connection settings and backend availability") from None
        return {"ok": True, "connection": connection, "operation": operation, "data": data,
                "truncated": truncated, "redacted": redacted}

    def execute(self, profile: Profile, operation: str, arguments: dict) -> Any:
        raise NotImplementedError
