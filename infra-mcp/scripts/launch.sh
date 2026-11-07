#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ ! -x "$project_dir/.venv/bin/infra-mcp" ]; then
  echo "Run uv sync --extra dev in $project_dir first." >&2
  exit 1
fi
export INFRA_MCP_CONFIG="${INFRA_MCP_CONFIG:-$project_dir/profiles.json}"
exec "$project_dir/.venv/bin/infra-mcp" "$@"
