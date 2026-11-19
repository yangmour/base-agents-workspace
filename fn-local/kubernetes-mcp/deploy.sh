#!/bin/sh
set -eu
base=$(CDPATH= cd -- "$(dirname "$0")" && pwd -P)
project=$(CDPATH= cd -- "${INFRA_MCP_PROJECT_DIR:-$base/../../infra-mcp}" && pwd -P)
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
cp "$base"/workload.yaml "$base"/server.py "$base"/kubeconfig "$base"/profiles.json "$stage/"
(cd "$project" && uv export --frozen --no-dev --no-emit-project --format requirements-txt) > "$stage/requirements.txt"
python3 - "$project/src" "$stage/infra-mcp.zip" <<'PYCODE'
from pathlib import Path
import sys, zipfile
root = Path(sys.argv[1])
with zipfile.ZipFile(sys.argv[2], "w") as out:
    for p in sorted((root/"infra_mcp").rglob("*.py")):
        info = zipfile.ZipInfo(p.relative_to(root).as_posix())
        out.writestr(info, p.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)
PYCODE
cat > "$stage/kustomization.yaml" <<'YAML'
resources: [workload.yaml]
configMapGenerator:
  - name: kubernetes-mcp-app
    namespace: infra-mcp-system
    files: [server.py, kubeconfig, profiles.json, requirements.txt, infra-mcp.zip]
YAML
kubectl apply -k "$stage"
