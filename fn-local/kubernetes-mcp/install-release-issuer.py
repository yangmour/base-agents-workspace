"""Install the two-policy release issuer and its expiry-only Mac LaunchAgent."""
import argparse
from pathlib import Path
import json
import os
import plistlib
import runpy
import shlex
import shutil
import subprocess
import sys
import tempfile


def write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as file:
        os.fchmod(file.fileno(), mode)
        file.write(content)
    os.replace(file.name, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-config", type=Path, required=True)
    parser.add_argument("--context", required=True)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Requires a Mac operator desktop")
    home = Path.home()
    project = Path(os.getenv("INFRA_MCP_PROJECT_DIR") or Path(__file__).resolve().parents[2] / "infra-mcp")
    scripts = project / "scripts"
    paths = runpy.run_path(str(project / "src/infra_mcp/paths.py"))
    config_dir = paths["config_dir"]()
    cli = runpy.run_path(str(scripts / "k8s-session.py"))
    operator = cli["Kubectl"](args.admin_config, args.context)
    tunnel = cli["Kubectl"](paths["location"]("FN_MCP_TUNNEL_CONFIG", config_dir / "kubernetes-tunnel/config"), "mcp-tunnel")
    fingerprint = cli["connection"](operator)[2]
    if fingerprint != cli["connection"](tunnel)[2]:
        parser.error("Operator and tunnel target different clusters")
    settings = config_dir / "release-issuer.json"
    write(settings, json.dumps({"admin_config": os.path.relpath(operator.admin_config, settings.parent), "context": operator.context,
                                "cluster_fingerprint": fingerprint}).encode(), 0o600)
    root = paths["sessions_dir"]()
    root.mkdir(mode=0o700, exist_ok=True, parents=True)
    cli["safe_path"](root, directory=True, private=True)
    installed = Path(shutil.which("infra-mcp")).resolve()
    python = installed.with_name("python")
    subprocess.run([python, "-c", "from infra_mcp.approval import confirm_write; import infra_mcp.paths"], check=True)
    data = paths["location"]("XDG_DATA_HOME", home / ".local/share") / "infra-mcp/issuer"
    for name in ("k8s-session.py", "k8s-release-issuer.py"):
        write(data / name, (scripts / name).read_bytes(), 0o600)
    launcher = paths["bin_dir"]() / "infra-kubernetes-release-issuer"
    rel_python = shlex.quote(os.path.relpath(python, launcher.parent))
    rel_broker = shlex.quote(os.path.relpath(data / "k8s-release-issuer.py", launcher.parent))
    script = ('#!/bin/sh\nset -eu\nbase=$(CDPATH= cd -P -- "$(dirname "$0")" && pwd)\n'
              f'exec "$base"/{rel_python} "$base"/{rel_broker} "$@"\n')
    write(launcher, script.encode(), 0o700)
    label = "com.xiwen.kubernetes-release-expiry"
    plist = home / "Library/LaunchAgents" / (label + ".plist")
    kubectl = Path(shutil.which("kubectl"))
    environment = {"PATH": str(kubectl.parent) + ":" + os.defpath}
    for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "FN_MCP_RELEASE_DIR"):
        if os.environ.get(key):
            environment[key] = str(Path(os.environ[key]).expanduser().absolute())
    write(plist, plistlib.dumps({"Label": label, "ProgramArguments": [str(launcher), "sweep"],
        "EnvironmentVariables": environment,
        "RunAtLoad": True, "StartInterval": 60}), 0o600)
    domain = "gui/" + str(os.getuid())
    job = domain + "/" + label
    if subprocess.run(["launchctl", "print", job], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        subprocess.run(["launchctl", "bootout", job], check=True)
    subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True)


if __name__ == "__main__":
    main()
