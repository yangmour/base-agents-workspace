"""Manage the fn loopback forwards. The periodic check also respects manual stops."""
import argparse
import fcntl
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
STATE = Path(os.getenv("FN_STATE_DIR", ROOT / ".state")).absolute()
NS = os.getenv("FN_NAMESPACE", "develop")
PROXY = ROOT / "rocketmq-dashboard-proxy.py"
PORTS = {
    "mysql": (13306, "mysql", 3306),
    "redis": (16379, "redis", 6379),
    "rabbitmq": (25672, "rabbitmq", 15672),
    "nacos": (18848, "nacos", 8848),
    "elasticsearch": (19200, "elasticsearch", 9200),
    "rocketmq": (18083, "rocketmq-dashboard", 8082),
    "rocketmq-proxy": (18084, None, None),
}


def kubectl():
    args = ["kubectl"]
    if os.getenv("FN_CONTEXT"):
        args += ["--context", os.environ["FN_CONTEXT"]]
    return args + ["-n", NS]


def tunnel_args(name):
    port, service, remote = PORTS[name]
    return kubectl() + ["port-forward", "--address", "127.0.0.1",
                        "svc/service-" + service, f"{port}:{remote}"]


def healthy(name):
    port = PORTS[name][0]
    try:
        if name in ("redis", "mysql"):
            with socket.create_connection(("127.0.0.1", port), 2) as sock:
                if name == "redis":
                    sock.sendall(b"*1\r\n$4\r\nPING\r\n")
                    return sock.recv(64).startswith((b"+PONG", b"-NOAUTH"))
                with sock.makefile("rb") as response:
                    greeting = response.read(5)
                return len(greeting) == 5 and greeting[4] == 10
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=6 if name == "rocketmq-proxy" else 3)
        try:
            if name == "rocketmq-proxy":
                conn.request("GET", "/cluster/list.query")
                response = conn.getresponse()
                if response.status != 200:
                    return False
                doc = json.loads(response.read(262144))
                return isinstance(doc, dict) and isinstance(doc.get("data"), dict) and "clusterInfo" in doc["data"]
            conn.request("HEAD", "/")
            return conn.getresponse().status < 500
        finally:
            conn.close()
    except (OSError, ValueError, http.client.HTTPException):
        return False


def listening(name):
    try:
        with socket.create_connection(("127.0.0.1", PORTS[name][0]), 1):
            return True
    except OSError:
        return False


def process_command(pid):
    result = subprocess.run(["ps", "-p", str(pid), "-o", "args="], capture_output=True, text=True)
    return result.stdout.strip()


def owned(name):
    try:
        pid = int((STATE / (name + ".pid")).read_text())
    except (FileNotFoundError, ValueError):
        return None
    if pid < 2:
        return None
    cmd = process_command(pid)
    if name == "rocketmq-proxy":
        return pid if cmd.endswith(" " + str(PROXY)) else None
    if cmd.endswith(f" {Path(__file__).resolve()} watch {name}"):
        return pid
    # Existing installations saved the PID of the original sh supervisor.
    args = " ".join(tunnel_args(name)[-5:])
    if cmd.startswith("sh -c while :;") and args in cmd and str(STATE / (name + ".log")) in cmd:
        return pid
    return None


def owns_listener(name, owner):
    port = PORTS[name][0]
    result = subprocess.run(["lsof", "-nP", "-t", f"-iTCP@127.0.0.1:{port}", "-sTCP:LISTEN"],
                            capture_output=True, text=True, timeout=3)
    for pid in result.stdout.split():
        if pid == str(owner):
            return True
        parent = subprocess.run(["ps", "-p", pid, "-o", "ppid="], capture_output=True, text=True)
        if parent.stdout.strip() == str(owner) and name != "rocketmq-proxy":
            return " ".join(tunnel_args(name)[-5:]) in process_command(pid)
    return False


def stop(name):
    pid = owned(name)
    if pid:
        if os.getpgid(pid) == pid:
            os.killpg(pid, signal.SIGTERM)
        else:
            # Legacy supervisors share a process group with their launcher.
            children = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True)
            os.kill(pid, signal.SIGTERM)
            for child in children.stdout.split():
                if name != "rocketmq-proxy" and " ".join(tunnel_args(name)[-5:]) in process_command(child):
                    try:
                        os.kill(int(child), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
        for _ in range(20):
            if not listening(name):
                break
            time.sleep(0.1)
    (STATE / (name + ".pid")).unlink(missing_ok=True)


def start(name):
    owner = owned(name)
    if owner:
        if listening(name) and not owns_listener(name, owner):
            print("[busy]", name, PORTS[name][0], file=sys.stderr)
            return False
        if healthy(name) or healthy(name):
            print("[ready]", name)
            return True
        stop(name)
    if listening(name):
        print("[busy]", name, PORTS[name][0], file=sys.stderr)
        return False
    if name == "rocketmq-proxy":
        args = [os.getenv("FN_PYTHON") or sys.executable, str(PROXY)]
    else:
        args = [sys.executable, str(Path(__file__).resolve()), "watch", name]
    with (STATE / (name + ".log")).open("ab") as log:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log,
                                   stderr=log, start_new_session=True)
    (STATE / (name + ".pid")).write_text(f"{process.pid}\n")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and process.poll() is None:
        if healthy(name) and owns_listener(name, process.pid):
            print("[up]", name)
            return True
        time.sleep(0.4)
    print("[unavailable]", name, file=sys.stderr)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", nargs="?", default="status",
                        choices=["start", "stop", "restart", "ensure", "periodic", "status", "logs", "watch"])
    parser.add_argument("name", nargs="?", choices=PORTS)
    args = parser.parse_args()
    if os.getenv("FN_KUBECONFIG"):
        os.environ["KUBECONFIG"] = os.environ["FN_KUBECONFIG"]
    if args.action == "watch":
        if not args.name or args.name == "rocketmq-proxy":
            parser.error("watch requires a tunnel name")
        if not os.getenv("FN_CONTEXT"):
            os.environ["FN_CONTEXT"] = subprocess.check_output(
                ["kubectl", "config", "current-context"], text=True, timeout=5).strip()
        while True:
            subprocess.run(tunnel_args(args.name))
            time.sleep(2)
    os.umask(0o077)
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    names = [args.name] if args.name else list(PORTS)
    if args.name == "rocketmq" and args.action not in ("logs", "status"):
        names.append("rocketmq-proxy")
    if args.action == "logs":
        for name in names:
            path = STATE / (name + ".log")
            if path.exists():
                subprocess.run(["tail", "-n", "20", str(path)] if not args.name else ["cat", str(path)])
        return 0
    if args.action == "status":
        for name in names:
            print(f"{name:15} {PORTS[name][0]:5}  pid={owned(name) or '-'}  healthy={healthy(name)}")
        return 0
    with (STATE / "control.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another forward operation is active", file=sys.stderr)
            return 0 if args.action == "periodic" else 1
        if args.action == "periodic":
            names = [n for n in names if not (STATE / (n + ".paused")).exists()]
        if names and args.action != "stop":
            try:
                subprocess.run(kubectl() + ["--request-timeout=4s", "get", "--raw=/version"],
                               check=True, stdout=subprocess.DEVNULL, timeout=6)
            except (OSError, subprocess.SubprocessError):
                print("Kubernetes API unavailable", file=sys.stderr)
                return 1
        failed = []
        for name in reversed(names) if args.action == "stop" else names:
            paused = STATE / (name + ".paused")
            try:
                if args.action == "stop":
                    paused.touch()
                    stop(name)
                    continue
                if args.action != "periodic":
                    paused.unlink(missing_ok=True)
                if args.action == "restart":
                    stop(name)
                if name == "rocketmq-proxy" and "rocketmq" in failed:
                    failed.append(name)
                elif not start(name):
                    failed.append(name)
            except (OSError, subprocess.SubprocessError) as exc:
                print(name, exc, file=sys.stderr)
                failed.append(name)
        if failed:
            print("Failed:", ", ".join(failed), file=sys.stderr)
        return int(bool(failed))


if __name__ == "__main__":
    sys.exit(main())
