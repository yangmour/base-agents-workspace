"""Fixed-controller HTTP transport for Jenkins API token authentication."""
import re
import ssl
from base64 import b64encode
from urllib.parse import quote, urlsplit

import httpx

from .config import InfraError, integer, secret, validate_name


class JenkinsClient:
    def __init__(self, profile):
        self.profile = profile
        self.base_url = validate_name(profile.options.get("url"), "Jenkins URL").rstrip("/")
        try:
            url = urlsplit(self.base_url)
            _ = url.port
        except ValueError:
            raise InfraError("invalid_config", "Invalid Jenkins controller URL") from None
        if (url.scheme not in {"http", "https"} or not url.hostname or url.username is not None
                or url.query or url.fragment or "\\" in self.base_url):
            raise InfraError("invalid_config", "Invalid Jenkins controller URL")
        self.username = profile.options.get("username") or secret(profile, "username")
        self.token = secret(profile, "token")
        if self.username is not None:
            validate_name(self.username, "Jenkins username")
        if bool(self.username) != bool(self.token):
            raise InfraError("invalid_config", "Jenkins API token and username must be configured together")
        self.maximum = integer(profile.options, "max_response_bytes", 1048576, 1024, 16777216)

    @staticmethod
    def job_path(job):
        pieces = validate_name(job, "job").split("/")
        for name in pieces:
            # Jenkins encodes slashes in multibranch item names as literal %2F.
            raw = re.sub(r"%2f", "", name, flags=re.I)
            if name in {"", ".", ".."} or any(c in raw for c in "%\\?#*[]"):
                raise InfraError("invalid_argument", "Invalid Jenkins job path")
        return "".join("/job/" + quote(name, safe="") for name in pieces)

    def redact(self, text):
        if self.token:
            basic = b64encode(f"{self.username}:{self.token}".encode()).decode()
            for value in (self.token, quote(self.token, safe=""), basic):
                text = text.replace(value, "[REDACTED]")
        text = re.sub(r"(?i)\b(authorization\s*[:=]\s*(?:basic|bearer)\s+)\S+", r"\1[REDACTED]", text)
        text = re.sub(r"(?im)(\b[\w.-]*(?:password|passwd|token|credential|secret|api[_-]?key)[\w.-]*\s*[:=]\s*).+$",
                      r"\1[REDACTED]", text)
        return re.sub(r"(https?://)[^/\s@]+@", r"\1[REDACTED]@", text)

    def request(self, method, path, *, params=None, data=None, content=None, headers=None,
                accepted=(200,), max_bytes=None, truncate=False):
        if (not path.startswith("/") or path.startswith("//") or any(c in path for c in "?#\\\r\n")
                or any(part in {".", ".."} for part in path.split("/"))):
            raise InfraError("invalid_argument", "Invalid Jenkins API path")
        verify = self.profile.options.get("verify_tls", True)
        if ca := self.profile.options.get("ca_file"):
            try:
                verify = ssl.create_default_context(cafile=ca)
            except (ValueError, OSError):
                raise InfraError("invalid_config", "Cannot load Jenkins CA certificate") from None
        limit = self.maximum if max_bytes is None else min(max_bytes, self.maximum)
        try:
            with httpx.Client(timeout=self.profile.timeout, verify=verify, follow_redirects=False, trust_env=False,
                              auth=(self.username, self.token) if self.username else None) as client:
                with client.stream(method, self.base_url + path, params=params, data=data, content=content,
                                   headers=headers) as response:
                    if response.status_code not in accepted:
                        raise InfraError("backend_http_error", f"Jenkins returned HTTP {response.status_code}")
                    body = bytearray()
                    for chunk in response.iter_bytes(65536):
                        if len(body) + len(chunk) > limit:
                            if not truncate:
                                raise InfraError("output_limit", "Jenkins response exceeds byte limit")
                            body.extend(chunk[:limit - len(body)])
                            break
                        body.extend(chunk)
                    # Bytes are decoded already, so keep only headers consumed by adapters.
                    metadata = {k: v for k, v in response.headers.items()
                                if k.lower() in {"location", "x-text-size", "x-more-data", "content-type"}}
                    return httpx.Response(response.status_code, headers=metadata, content=bytes(body),
                                          request=response.request)
        except httpx.TimeoutException:
            raise InfraError("timeout", "Jenkins request timed out") from None
        except (httpx.HTTPError, OSError, ValueError):
            raise InfraError("backend_error", "Jenkins request failed; check connection settings") from None

    def json(self, path, params=None):
        try:
            result = self.request("GET", path, params=params).json()
        except (ValueError, RecursionError):
            raise InfraError("backend_error", "Invalid Jenkins JSON response") from None
        if not isinstance(result, dict):
            raise InfraError("backend_error", "Expected a Jenkins JSON object")
        return result
