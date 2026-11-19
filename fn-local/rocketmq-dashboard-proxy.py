#!/usr/bin/env python3
"""fn-local：给 fn 集群里的 RocketMQ Dashboard(2.0.0，登录模式) 加一层本机登录注入代理。

infra-mcp 的 RocketMQ MCP 只支持无登录或反向代理认证，不能自己走 Dashboard 的
网页登录。这个代理在 127.0.0.1 上监听，收到请求后用 admin 凭据登录 Dashboard，
把 JSESSIONID 注入到上游请求里，从而让 MCP 侧按 2.1.0 的 API 正常调用。

- 只监听回环地址，不对外暴露；不在日志里输出口令和请求体。
- 上游使用 2.0.0 API，兼容 2.1.0 的调用方式；仅对 examineTopicConfig 补 messageType 字段。
- 会话失效时自动重新登录并重试一次。

环境变量（都有默认值）：
  FN_PROXY_LISTEN          监听地址，默认 127.0.0.1:18084
  FN_RMQ_DASHBOARD_URL     上游 Dashboard，默认 http://127.0.0.1:18083
  FN_RMQ_USERNAME          Dashboard 用户名，默认 admin
  FN_RMQ_PASSWORD_FILE     口令文件，默认 infra-mcp/.secrets/fn-k8s-rocketmq.password
"""

import http.client
import json
import os
import signal
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(HERE, ".."))

DEFAULT_PASSWORD_FILE = os.path.join(WORKSPACE, "infra-mcp", ".secrets", "fn-k8s-rocketmq.password")

LISTEN = os.environ.get("FN_PROXY_LISTEN", "127.0.0.1:18084")
UPSTREAM = urllib.parse.urlsplit(os.environ.get("FN_RMQ_DASHBOARD_URL", "http://127.0.0.1:18083"))
USERNAME = os.environ.get("FN_RMQ_USERNAME", "admin")
PASSWORD_FILE = os.environ.get("FN_RMQ_PASSWORD_FILE") or DEFAULT_PASSWORD_FILE


def listen_address():
    host, _, port = LISTEN.partition(":")
    return host or "127.0.0.1", int(port or "18084")


class Session:
    """Maintains one Dashboard login session for all proxied requests."""

    def __init__(self):
        self._lock = threading.Lock()
        self._cookie = None

    def invalidate(self):
        self._cookie = None

    def _password(self):
        with open(PASSWORD_FILE, encoding="utf-8") as handle:
            return handle.read().rstrip("\r\n")

    def refresh(self):
        with self._lock:
            try:
                password = self._password()
            except OSError:
                self._cookie = None
                return False
            path = UPSTREAM.path.rstrip("/") + "/login/login.do?" + urllib.parse.urlencode(
                {"username": USERNAME, "password": password}
            )
            connection = http.client.HTTPConnection(
                UPSTREAM.hostname, UPSTREAM.port or 80, timeout=15
            )
            try:
                connection.request("POST", path, body=b"", headers={"Accept": "application/json"})
                response = connection.getresponse()
                body = response.read()
                header = response.getheader("Set-Cookie") or ""
            except OSError:
                self._cookie = None
                return False
            finally:
                connection.close()
            try:
                payload = json.loads(body.decode("utf-8"))
            except ValueError:
                payload = {}
            cookie = None
            for part in header.split(","):
                piece = part.strip().split(";")[0]
                if piece.startswith("JSESSIONID="):
                    cookie = piece
            if payload.get("status") != 0 or cookie is None:
                self._cookie = None
                return False
            self._cookie = cookie
            return True

    def cookie(self):
        if self._cookie is not None:
            return self._cookie
        return None if not self.refresh() else self._cookie


SESSION = Session()


def needs_login(status, content_type, location):
    lowered = (content_type or "").lower()
    if status in (301, 302, 303, 307) and "login" in (location or "").lower():
        return True
    if status == 401:
        return True
    return status == 200 and "text/html" in lowered


def normalize_topic_config(payload):
    """Dashboard 2.0.0 的 examineTopicConfig 不返回 messageType；补成 NORMAL 供 MCP 校验。"""
    try:
        document = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return payload
    changed = False
    data = document.get("data") if isinstance(document, dict) else None
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "messageType" not in item:
                item["messageType"] = "NORMAL"
                changed = True
    return json.dumps(document, ensure_ascii=False).encode("utf-8") if changed else payload


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # noqa: D401 - silence per-request noise
        return

    def do_GET(self):
        self._forward("GET")

    def do_POST(self):
        self._forward("POST")

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        return self.rfile.read(length) if length > 0 else None

    def _reply(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type or "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass
        self.close_connection = True

    def _fail(self, status, message):
        self._reply(status, json.dumps({"status": -1, "data": None, "errMsg": message}).encode(), "application/json")

    def _forward(self, method):
        body = self._read_body()
        for _ in range(2):
            cookie = SESSION.cookie()
            if cookie is None:
                return self._fail(503, "RocketMQ dashboard login failed")
            headers = {"Accept": "application/json", "Cookie": cookie}
            content_type = self.headers.get("Content-Type")
            if content_type:
                headers["Content-Type"] = content_type
            if body is not None:
                headers["Content-Length"] = str(len(body))
            connection = http.client.HTTPConnection(
                UPSTREAM.hostname, UPSTREAM.port or 80, timeout=30
            )
            try:
                connection.request(method, UPSTREAM.path.rstrip("/") + self.path, body=body, headers=headers)
                response = connection.getresponse()
                payload = response.read()
                status = response.status
                response_type = response.getheader("Content-Type") or "application/json"
                location = response.getheader("Location") or ""
            except OSError:
                connection.close()
                return self._fail(502, "RocketMQ dashboard unreachable")
            connection.close()
            if needs_login(status, response_type, location):
                SESSION.invalidate()
                continue
            if "/topic/examineTopicConfig.query" in self.path:
                payload = normalize_topic_config(payload)
            return self._reply(status, payload, response_type)
        return self._fail(503, "RocketMQ dashboard session could not be established")


def main():
    host, port = listen_address()
    if not os.path.exists(PASSWORD_FILE):
        print(f"password file not found: {PASSWORD_FILE}", file=sys.stderr)
        return 1
    if not SESSION.refresh():
        print("initial RocketMQ dashboard login failed", file=sys.stderr)
        return 1
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True

    def shutdown(signum, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    print(f"rocketmq dashboard proxy listening on http://{host}:{port} -> {UPSTREAM.scheme}://{UPSTREAM.netloc}{UPSTREAM.path or ''}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
