#!/bin/sh
# Provision client authentication for this Mac. Run once per transport installation.
set -eu
umask 077
dest="${FN_MCP_CERT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/infra-mcp/kubernetes-transport}"
# Keep relative overrides stable when changing to the temporary directory.
case "$dest" in /*) ;; *) dest="$PWD/$dest" ;; esac
ssl=$(command -v "${OPENSSL_BIN:-openssl}")
case "$ssl" in /*) ;; *) ssl="$PWD/$ssl" ;; esac
mkdir -p "$(dirname "$dest")"
if [ -e "$dest" ]; then echo "Transport directory already exists: $dest" >&2; exit 1; fi
stage=$(mktemp -d "$(dirname "$dest")/.kubernetes-transport.XXXXXX")
trap 'rm -rf "$stage"' EXIT
cd "$stage"
"$ssl" req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 1100 -subj /CN=fn-mcp-transport-ca \
  -addext basicConstraints=critical,CA:TRUE,pathlen:0 -addext keyUsage=critical,keyCertSign -keyout ca.key -out ca.crt
for peer in server client; do
  "$ssl" req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -subj "/CN=kubernetes-mcp-$peer" -keyout "$peer.key" -out "$peer.csr"
  echo 'basicConstraints=critical,CA:FALSE' > ext
  echo 'keyUsage=critical,digitalSignature' >> ext
  echo "extendedKeyUsage=${peer}Auth" >> ext
  if [ "$peer" = server ]; then echo 'subjectAltName=DNS:kubernetes-mcp' >> ext; fi
  "$ssl" x509 -req -in "$peer.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -days 730 -extfile ext -out "$peer.crt"
done
mkdir client
cp ca.crt client.crt client.key client/
kubectl -n infra-mcp-system create secret generic kubernetes-mcp-transport \
  --from-file=ca.crt --from-file=server.key --from-file=server.crt
mv client "$dest"
