#!/usr/bin/env python3
"""为指定命名空间内的具名 Kubernetes 对象签发一小时 get、patch 权限。"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ISSUER = Path(__file__).with_name("k8s-session.py")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-config", type=Path, default=Path.home() / ".kube/config")
    parser.add_argument("--context", help="目标集群上下文，默认使用 kubeconfig 的当前上下文")
    parser.add_argument("-n", "--namespace", required=True, help="所有目标对象所在的命名空间")
    parser.add_argument("targets", nargs="+", metavar="KIND/NAME",
                        help="精确对象名，支持 pods、configmaps、deployments、statefulsets、daemonsets")
    args = parser.parse_args()

    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    releases = Path(os.environ.get("FN_MCP_RELEASE_DIR") or config_home / "infra-mcp/releases")
    releases.mkdir(mode=0o700, parents=True, exist_ok=True)
    command = [sys.executable, str(ISSUER), "issue", "--admin-config", str(args.admin_config),
               "--namespace", args.namespace]
    if args.context:
        command.extend(["--context", args.context])
    for target in args.targets:
        command.extend(["--patch-target", target])
    result = subprocess.run(command, stdout=subprocess.PIPE, text=True, check=True)
    receipt = json.loads(result.stdout)
    source = Path(receipt["session_dir"]) / "client"
    print(f"管理员回执目录：{source.parent}", file=sys.stderr)
    for target in args.targets:
        check = subprocess.run(
            ["kubectl", "--kubeconfig", str(source / "subadminconfig"), "--request-timeout=10s",
             "auth", "can-i", "patch", target, "-n", args.namespace],
            capture_output=True, text=True, timeout=15,
        )
        if check.returncode or check.stdout.strip() != "yes":
            sys.exit(f"临时权限核验失败：patch {target}。请按回执检查或撤销本次签发。")

    # 每次交付独立目录。两个文件全部复制完成后才向调用方返回路径。
    destination = Path(tempfile.mkdtemp(prefix=f"{args.namespace}-release.", dir=releases))
    try:
        for name in ("profiles.json", "subadminconfig"):
            shutil.copy(source / name, destination / name)
    except BaseException:
        shutil.rmtree(destination)
        raise
    print(f"到期时间：{receipt['expiration_timestamp']}", file=sys.stderr)
    print(destination)


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.SubprocessError) as error:
        sys.exit(f"Kubernetes 临时客户端交付失败：{error}")
