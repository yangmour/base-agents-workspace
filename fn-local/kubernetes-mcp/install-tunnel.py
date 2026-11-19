"""Pin a dedicated, loopback-only kubectl port-forward to the operator's selected cluster."""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile

kubectl = shutil.which("kubectl")
if not kubectl:
    raise SystemExit("kubectl is required")
env = {"PATH": os.environ["PATH"]}
if os.environ.get("KUBECONFIG"):
    # launchd can start in a different directory than the installer.
    env["KUBECONFIG"] = os.pathsep.join(
        str(Path(item).expanduser().absolute()) for item in os.environ["KUBECONFIG"].split(os.pathsep) if item
    )
context = subprocess.check_output([kubectl, "config", "current-context"], text=True).strip()
domain = f"gui/{os.getuid()}"
label = "com.xiwen.kubernetes-mcp.tunnel"
plist = Path.home() / "Library/LaunchAgents" / (label + ".plist")
job = {
    "Label": label,
    "ProgramArguments": [kubectl, "--context", context, "-n", "infra-mcp-system",
                         "port-forward", "--address", "127.0.0.1", "deployment/kubernetes-mcp", "19443:9443"],
    "EnvironmentVariables": env,
    "KeepAlive": True, "ThrottleInterval": 5, "RunAtLoad": True,
}
plist.parent.mkdir(parents=True, exist_ok=True)
if subprocess.run(["launchctl", "print", f"{domain}/{label}"], capture_output=True).returncode == 0:
    subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], check=True)
with tempfile.NamedTemporaryFile(dir=plist.parent, delete=False) as out:
    plistlib.dump(job, out)
os.replace(out.name, plist)
subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True)
