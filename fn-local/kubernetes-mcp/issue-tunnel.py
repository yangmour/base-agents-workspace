"""Operator-run issuance for one fixed, namespace-scoped port-forward identity."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

USER = "fn-local-kubernetes-mcp-tunnel"
CONTEXT = "mcp-tunnel"
SIGNER = "kubernetes.io/kube-apiserver-client"
NAMESPACE = "infra-mcp-system"


def run(*args, data=None):
    return subprocess.check_output(args, input=data, text=True)


def main():
    os.umask(0o077)
    config_home = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = Path(os.environ.get("FN_MCP_TUNNEL_CONFIG") or config_home / "infra-mcp/kubernetes-tunnel/config").expanduser().absolute()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    operator = ["kubectl", "--context", run("kubectl", "config", "current-context").strip(), "--request-timeout=12s"]
    # Export only the cluster endpoint and trust configuration.
    cluster = json.loads(run(*operator, "config", "view", "--minify", "--flatten", "--raw",
                             "-o", "jsonpath={.clusters[0].cluster}"))
    if not cluster["server"].startswith("https://") or cluster.get("insecure-skip-tls-verify"):
        raise SystemExit("A TLS-verified API endpoint is required")
    if path.exists():
        previous = json.loads(path.read_text())
        if (previous["current-context"] != CONTEXT or previous["users"][0]["name"] != USER
                or previous["clusters"][0]["cluster"] != cluster):
            raise SystemExit("Existing kubeconfig belongs to another identity or cluster")

    ssl = os.environ.get("OPENSSL_BIN") or "openssl"
    with tempfile.TemporaryDirectory(dir=path.parent) as directory:
        tmp = Path(directory)
        key, csr = tmp / "client.key", tmp / "client.csr"
        run(ssl, "req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256",
            "-nodes", "-subj", "/CN=" + USER, "-keyout", str(key), "-out", str(csr))
        spec = {"signerName": SIGNER, "usages": ["client auth"], "expirationSeconds": 90 * 86400,
                "request": base64.b64encode(csr.read_bytes()).decode()}
        obj = {"apiVersion": "certificates.k8s.io/v1", "kind": "CertificateSigningRequest",
               "metadata": {"generateName": "fn-mcp-tunnel-"}, "spec": spec}
        req = json.loads(run(*operator, "create", "-f", "-", "-o", "json", data=json.dumps(obj)))
        if any(req["spec"].get(k) != v for k, v in spec.items()):
            raise SystemExit("Submitted CSR differs from local request")
        name = req["metadata"]["name"]
        # Keep the returned UID and resourceVersion on the approval update.
        req["status"] = {"conditions": [{"type": "Approved", "status": "True",
                                         "reason": "TunnelProvisioning", "message": "Dedicated MCP tunnel client"}]}
        url = "/apis/certificates.k8s.io/v1/certificatesigningrequests/" + name
        run(*operator, "replace", "--raw", url + "/approval", "-f", "-", data=json.dumps(req))
        for _ in range(30):
            signed = json.loads(run(*operator, "get", "csr", name, "-o", "json"))
            cert = signed.get("status", {}).get("certificate")
            if cert and signed["metadata"]["uid"] == req["metadata"]["uid"]:
                break
            time.sleep(1)
        else:
            raise SystemExit("CSR has not been signed: " + name)
        data = {"apiVersion": "v1", "kind": "Config", "current-context": CONTEXT,
                "clusters": [{"name": "fn", "cluster": cluster}],
                "contexts": [{"name": CONTEXT, "context": {"cluster": "fn", "user": USER, "namespace": NAMESPACE}}],
                "users": [{"name": USER, "user": {"client-certificate-data": cert,
                         "client-key-data": base64.b64encode(key.read_bytes()).decode()}}]}
        fresh = tmp / "config"
        fresh.write_text(json.dumps(data))
        identity = json.loads(run("kubectl", "--kubeconfig", str(fresh), "--request-timeout=10s",
                                  "auth", "whoami", "-o", "json"))["status"]["userInfo"]
        if identity["username"] != USER or set(identity.get("groups", [])) != {"system:authenticated"}:
            raise SystemExit("Unexpected issued Kubernetes identity")
        os.replace(fresh, path)
        print(USER, run(ssl, "x509", "-noout", "-enddate",
                        data=base64.b64decode(cert).decode()).strip(), flush=True)


if __name__ == "__main__":
    main()
