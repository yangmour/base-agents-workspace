#!/bin/sh
set -eu
certs="${FN_MCP_CERT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/infra-mcp/kubernetes-transport}"
exec infra-mcp kubernetes --stdio-tunnel "${OPENSSL_BIN:-openssl}" s_client -connect 127.0.0.1:19443 -servername kubernetes-mcp \
  -verify_hostname kubernetes-mcp -verify_return_error -CAfile "$certs/ca.crt" \
  -cert "$certs/client.crt" -key "$certs/client.key" -quiet -no_ign_eof
