"""Install the loopback port-forward under its dedicated Kubernetes identity."""
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import time

kubectl = shutil.which("kubectl")
if not kubectl:
    raise SystemExit("kubectl is required")
config_home = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
config = Path(os.environ.get("FN_MCP_TUNNEL_CONFIG") or config_home / "infra-mcp/kubernetes-tunnel/config").expanduser().absolute()
if not config.is_file() or config.stat().st_uid != os.getuid() or config.stat().st_mode & 0o077:
    raise SystemExit("A private tunnel kubeconfig owned by this user is required. Run issue-tunnel.py first.")
args = [kubectl, "--kubeconfig", str(config), "--context", "mcp-tunnel"]
identity = json.loads(subprocess.check_output(args + ["--request-timeout=10s", "auth", "whoami", "-o", "json"],
                                              text=True))["status"]["userInfo"]
if identity["username"] != "fn-local-kubernetes-mcp-tunnel" or set(identity.get("groups", [])) != {"system:authenticated"}:
    raise SystemExit("Unexpected identity. The tunnel requires the dedicated client certificate.")
domain = f"gui/{os.getuid()}"
label = "com.xiwen.kubernetes-mcp.tunnel"
plist = Path.home() / "Library/LaunchAgents" / (label + ".plist")
job = {
    "Label": label,
    "ProgramArguments": args + ["-n", "infra-mcp-system",
                         "port-forward", "--address", "127.0.0.1", "deployment/kubernetes-mcp", "19443:9443"],
    "EnvironmentVariables": {"PATH": os.environ["PATH"], "KUBECTL_PORT_FORWARD_WEBSOCKETS": "false"},
    "KeepAlive": True, "ThrottleInterval": 5, "RunAtLoad": True,
}
plist.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile(dir=plist.parent, delete=False) as out:
    plistlib.dump(job, out)
os.replace(out.name, plist)
if subprocess.run(["launchctl", "print", f"{domain}/{label}"], capture_output=True).returncode == 0:
    subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], check=True)
# A recently unloaded label can take a moment to leave the launchd domain.
for attempt in range(5):
    result = subprocess.run(["launchctl", "bootstrap", domain, str(plist)], capture_output=True, text=True)
    if result.returncode == 0:
        break
    if attempt == 4:
        raise SystemExit(result.stderr)
    time.sleep(1)
