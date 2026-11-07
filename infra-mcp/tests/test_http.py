import json

import httpx
import pytest

from infra_mcp.config import ACTIONS, InfraError, Profile
from infra_mcp.http import request_json


def profile(**options):
    return Profile("test", "elasticsearch", {"url": "http://localhost:9200", **options}, ACTIONS, {})


def install_transport(monkeypatch, handler):
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


def test_fixed_encoded_paths_and_query_preserved(monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    install_transport(monkeypatch, respond)
    assert request_json(profile(), "GET", "/logs-1/_doc/a%2Fb", params={"size": 10}) == {"ok": True}
    assert b"a%2Fb" in requests[0].url.raw_path
    assert requests[0].url.params["size"] == "10"


@pytest.mark.parametrize("url", ["http://user:password@localhost", "file:///etc/passwd", "http://localhost?x=y", "http://localhost#fragment", "http://localhost:bad"])
def test_invalid_urls_fail_before_request(url):
    with pytest.raises(InfraError):
        request_json(profile(url=url), "GET", "/")


def test_http_errors_never_echo_upstream_credentials(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(401, text="password=SENSITIVE"))
    with pytest.raises(InfraError) as error:
        request_json(profile(), "GET", "/")
    assert "SENSITIVE" not in str(error.value)
    assert "401" in str(error.value)


def test_redirect_not_followed(monkeypatch):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://external.invalid"})

    install_transport(monkeypatch, respond)
    with pytest.raises(InfraError):
        request_json(profile(), "GET", "/")
    assert len(calls) == 1


def test_response_body_capped_while_reading(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(200, content=b"x" * 4096))
    with pytest.raises(InfraError, match="limit"):
        request_json(profile(max_response_bytes=1024), "GET", "/")


def test_env_basic_auth_is_used_and_not_returned(monkeypatch):
    monkeypatch.setenv("INFRA_HTTP_PASSWORD", "secret-password")
    requests = []
    install_transport(monkeypatch, lambda req: requests.append(req) or httpx.Response(204))
    assert request_json(profile(username="reader", password_env="INFRA_HTTP_PASSWORD"), "DELETE", "/index/_doc/id") == {"status": 204}
    assert requests[0].headers["authorization"].startswith("Basic ")


def test_ambiguous_auth_fails_closed(monkeypatch):
    monkeypatch.setenv("INFRA_API_KEY", "secret-key")
    monkeypatch.setenv("INFRA_PASSWORD", "secret-password")
    with pytest.raises(InfraError):
        request_json(profile(username="user", password_env="INFRA_PASSWORD", api_key_env="INFRA_API_KEY"), "GET", "/")


def test_http_timeout_and_parse_errors_are_sanitized(monkeypatch):
    def fail(request):
        raise httpx.ReadTimeout("SENSITIVE")
    install_transport(monkeypatch, fail)
    with pytest.raises(InfraError) as error:
        request_json(profile(), "GET", "/")
    assert "SENSITIVE" not in str(error.value)
