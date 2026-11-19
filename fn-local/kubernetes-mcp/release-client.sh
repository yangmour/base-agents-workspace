#!/bin/sh
# Local stdio client for credentials delivered by an independent release operator.
set -eu
case "${1:-}" in
  develop|higress-system) namespace=$1 ;;
  *) echo 'Expected develop or higress-system' >&2; exit 2 ;;
esac
root="${FN_MCP_RELEASE_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/infra-mcp/releases}"
exec infra-mcp kubernetes --config "$root/$namespace/profiles.json"
