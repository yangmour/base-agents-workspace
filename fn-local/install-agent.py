"""Install the current user's launchd recovery job for the selected Kubernetes context."""
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent
label = "com.xiwen.fn-local.forward"
domain = f"gui/{os.getuid()}"
plist = Path.home() / "Library" / "LaunchAgents" / (label + ".plist")
kubectl = shutil.which("kubectl")
if not kubectl:
    sys.exit("kubectl is required")
env = {
    "PATH": os.pathsep.join([str(Path(kubectl).parent), "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]),
    "FN_NAMESPACE": os.getenv("FN_NAMESPACE", "develop"),
}
config = os.getenv("FN_KUBECONFIG") or os.getenv("KUBECONFIG") or str(Path.home() / ".kube/config")
env["FN_KUBECONFIG"] = config
env["FN_CONTEXT"] = os.getenv("FN_CONTEXT") or subprocess.check_output(
    [kubectl, "config", "current-context"], env={**os.environ, "KUBECONFIG": config}, text=True).strip()
state = Path(os.getenv("FN_STATE_DIR", root / ".state")).resolve()
state.mkdir(mode=0o700, exist_ok=True, parents=True)
env["FN_STATE_DIR"] = str(state)
for name in ("FN_PYTHON", "FN_RMQ_DASHBOARD_URL", "FN_RMQ_PASSWORD_FILE", "FN_RMQ_USERNAME"):
    if name in os.environ:
        env[name] = os.environ[name]
job = {
    "Label": label, "ProgramArguments": [sys.executable, str(root / "forward.py"), "periodic"],
    "RunAtLoad": True, "StartInterval": 60, "AbandonProcessGroup": True,
    "EnvironmentVariables": env,
    "StandardErrorPath": str(state / "agent.log"),
}
plist.parent.mkdir(parents=True, exist_ok=True)
if subprocess.run(["launchctl", "print", f"{domain}/{label}"], capture_output=True).returncode == 0:
    subprocess.run(["launchctl", "bootout", f"{domain}/{label}"], check=True)
with tempfile.NamedTemporaryFile(dir=plist.parent, delete=False) as f:
    plistlib.dump(job, f)
os.replace(f.name, plist)
subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True)
print(plist)
