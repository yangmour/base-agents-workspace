"""Resolve operator-owned locations from the same environment as the shell clients."""
import os
from pathlib import Path


def location(key: str, default: Path) -> Path:
    return Path(os.environ.get(key) or default).expanduser().absolute()


def config_dir() -> Path:
    return location("XDG_CONFIG_HOME", Path.home() / ".config") / "infra-mcp"


def profile_file() -> Path:
    return location("INFRA_MCP_CONFIG", config_dir() / "profiles.json")


def releases_dir() -> Path:
    return location("FN_MCP_RELEASE_DIR", config_dir() / "releases")


def sessions_dir() -> Path:
    return location("XDG_STATE_HOME", Path.home() / ".local/state") / "infra-mcp/release-sessions"


def bin_dir() -> Path:
    return location("XDG_BIN_HOME", Path.home() / ".local/bin")
