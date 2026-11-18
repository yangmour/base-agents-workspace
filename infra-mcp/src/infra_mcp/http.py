"""Fixed-origin JSON requests with bounded responses and no credential-bearing errors."""
from __future__ import annotations

import json as json_module
import ssl
from urllib.parse import urlsplit

import httpx

from .config import InfraError, Profile, integer, secret


def request_json(profile: Profile, method: str, path: str, *, json=None, params=None, data=None, headers=None,
                 csrf_path=None):
    base = profile.options.get("url")
    if not isinstance(base, str):
        raise InfraError("invalid_config", "An HTTP url is required")
    try:
        parsed = urlsplit(base)
        valid = (parsed.scheme in {"http", "https"} and parsed.hostname and not parsed.username
                 and not parsed.password and not parsed.query and not parsed.fragment)
        _ = parsed.port
    except ValueError:
        valid = False
    if not valid or any(ord(c) < 32 for c in base) or "\\" in base:
        raise InfraError("invalid_config", "url must be HTTP(S) without embedded credentials, query, or fragment")
    for endpoint in (path,) if csrf_path is None else (path, csrf_path):
        if (not isinstance(endpoint, str) or not endpoint.startswith("/") or endpoint.startswith("//")
                or any(c in endpoint for c in "?#\\")):
            raise InfraError("invalid_argument", "Invalid backend path")
    maximum = integer(profile.options, "max_response_bytes", 1048576, 1024, 16777216)
    username = profile.options.get("username")
    if username is None:
        username = secret(profile, "username")
    password = secret(profile, "password")
    api_key = secret(profile, "api_key")
    token = secret(profile, "token")
    if sum((username is not None or password is not None, api_key is not None, token is not None)) > 1:
        raise InfraError("invalid_config", "Choose one authentication method per connection")
    if username is not None and not isinstance(username, str):
        raise InfraError("invalid_config", "username must be a string")
    if password is not None and username is None:
        raise InfraError("invalid_config", "Basic authentication requires username")
    request_headers = {"Accept": "application/json"}
    if api_key is not None:
        request_headers["Authorization"] = f"ApiKey {api_key}"
    if token is not None:
        request_headers["Authorization"] = f"Bearer {token}"
    # Only fixed adapters supply these headers; MCP callers cannot set arbitrary headers.
    if headers:
        request_headers.update(headers)
    verify = profile.options.get("verify_tls", True)
    if type(verify) is not bool:
        raise InfraError("invalid_config", "verify_tls must be boolean")
    if profile.options.get("ca_file"):
        try:
            verify = ssl.create_default_context(cafile=profile.options["ca_file"])
        except (OSError, TypeError, ValueError):
            raise InfraError("invalid_config", "Cannot load TLS CA file") from None
    try:
        with httpx.Client(timeout=profile.timeout, follow_redirects=False, verify=verify,
                          auth=(username, password or "") if username is not None else None,
                          headers=request_headers, trust_env=False) as client:
            write_headers = None
            if csrf_path is not None:
                try:
                    # Dashboard versions with CSRF issue a cookie from this
                    # fixed GET endpoint. Keep its value in this request session.
                    with client.stream("GET", base.rstrip("/") + csrf_path) as csrf:
                        if csrf.is_success:
                            token = csrf.cookies.get("XSRF-TOKEN")
                            if not token or len(token) > 4096 or not token.isascii() or not token.isprintable():
                                raise InfraError("csrf_failed", "Dashboard did not issue a valid CSRF cookie")
                            write_headers = {"X-XSRF-TOKEN": token}
                        elif csrf.status_code != 404:
                            raise InfraError("csrf_failed", "Dashboard CSRF request was rejected")
                except (httpx.HTTPError, httpx.CookieConflict, ValueError):
                    raise InfraError("csrf_failed", "Dashboard CSRF request failed") from None
            with client.stream(method, base.rstrip("/") + path, json=json, params=params, data=data,
                               headers=write_headers) as response:
                if not 200 <= response.status_code < 300:
                    raise InfraError("backend_http_error", f"Backend returned HTTP {response.status_code}; response body withheld")
                body = bytearray()
                for chunk in response.iter_bytes():
                    if len(body) + len(chunk) > maximum:
                        raise InfraError("output_limit", "Backend response exceeds configured byte limit")
                    body.extend(chunk)
                if not body:
                    return {"status": response.status_code}
                try:
                    return json_module.loads(body)
                except (ValueError, RecursionError):
                    raise InfraError("backend_error", "Backend returned invalid JSON") from None
    except InfraError:
        raise
    except httpx.TimeoutException:
        raise InfraError("timeout", "Backend HTTP request timed out") from None
    except (httpx.HTTPError, ValueError, OSError):
        raise InfraError("backend_error", "Backend HTTP request failed; check URL, TLS and authentication") from None
