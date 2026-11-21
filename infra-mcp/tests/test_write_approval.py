import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp import types
from mcp.shared.memory import create_connected_server_and_client_session as connect

from infra_mcp import approval, tunnel
from infra_mcp.redis_service import RedisService
from infra_mcp.server import build_server


@pytest.fixture
def redis(tmp_path, monkeypatch):
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"profiles": {"redis": {"demo": {
        "permissions": {"read": True}, "allow_after_approval": ["create", "update", "delete"]
    }}}}))
    calls = []
    def execute(self, profile, operation, arguments):
        calls.append((operation, arguments))
        return {"called": operation}
    monkeypatch.setattr(RedisService, "execute", execute)
    return build_server("redis", path), calls, path


@pytest.mark.parametrize("action", ["create", "update", "delete"])
def test_mac_write_approval_is_per_call(redis, monkeypatch, action):
    server, calls, _ = redis
    prompt = AsyncMock(side_effect=[False, True, False, TimeoutError(), OSError()])
    monkeypatch.setattr(approval, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(approval, "desktop_approval", prompt)
    async def exercise():
        async with connect(server) as client:
            data = {"connection": "demo", "operation": action, "arguments": {"key": "sample", "value": "one"}}
            assert not (await client.call_tool("read", {**data, "operation": "get"})).isError
            assert (await client.call_tool("read", data)).isError
            prompt.assert_not_called()
            for error in [True, False, True, True, True]:
                assert (await client.call_tool(action, data)).isError == error
            assert prompt.await_count == 5
            assert action in prompt.await_args.args[0] and "sample" in prompt.await_args.args[0]
    asyncio.run(exercise())
    assert [op for op, args in calls] == ["get", action]


def test_profile_changed_during_confirmation_never_executes(redis, monkeypatch):
    server, calls, path = redis
    async def approve(message):
        data = json.loads(path.read_text())
        data["profiles"]["redis"]["demo"]["db"] = 2
        path.write_text(json.dumps(data))
        return True
    monkeypatch.setattr(approval, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(approval, "desktop_approval", approve)
    async def exercise():
        async with connect(server) as client:
            result = await client.call_tool("delete", {"connection": "demo", "operation": "delete"})
            assert result.isError and "approval_expired" in result.content[0].text
    asyncio.run(exercise())
    assert not calls


def test_remote_form_requires_an_explicit_true_per_call(redis, monkeypatch):
    server, calls, _ = redis
    monkeypatch.setattr(approval, "sys", SimpleNamespace(platform="linux"))
    replies = iter([("decline", None), ("cancel", None), ("accept", {}), ("accept", {"allow_once": "true"}),
                    ("accept", {"allow_once": False}), ("accept", {"allow_once": True}), ("cancel", None)])
    async def decide(ctx, params):
        assert params.requestedSchema["required"] == ["allow_once"]
        action, content = next(replies)
        return types.ElicitResult(action=action, content=content)
    async def exercise():
        data = {"connection": "demo", "operation": "delete", "arguments": {"key": "one", "approved": True}}
        async with connect(server) as client:
            result = await client.call_tool("delete", data)
            assert result.isError and "approval_required" in result.content[0].text
        async with connect(server, elicitation_callback=decide) as client:
            for error in [True, True, True, True, True, False, True]:
                assert (await client.call_tool("delete", data)).isError == error
    asyncio.run(exercise())
    assert len(calls) == 1


def test_kubernetes_tunnel_relays_only_the_same_approved_write(tmp_path, monkeypatch):
    from infra_mcp.kubernetes_service import KubernetesService
    path = tmp_path / "kube.json"
    path.write_text(json.dumps({"profiles": {"kubernetes": {"demo": {
        "permissions": {"read": True}, "allow_after_approval": ["delete"]}}}}))
    calls = []
    def execute(self, profile, operation, arguments):
        calls.append((operation, arguments))
        return {}
    monkeypatch.setattr(KubernetesService, "execute", execute)
    monkeypatch.setattr(approval, "sys", SimpleNamespace(platform="linux"))
    pod = build_server("kubernetes", path)
    prompt = AsyncMock(side_effect=[None, approval.ToolError("denied")])
    monkeypatch.setattr(tunnel, "confirm_write", prompt)
    open_sessions = set()
    @asynccontextmanager
    async def upstream(transport, decision=None):
        async with connect(pod, elicitation_callback=decision) as client:
            open_sessions.add(client)
            try:
                yield client
            finally:
                open_sessions.remove(client)
    monkeypatch.setattr(tunnel, "upstream", upstream)
    async def exercise():
        async with connect(tunnel.build_frontend(None)) as client:
            assert not open_sessions
            assert len((await client.list_tools()).tools) == 7
            assert not open_sessions
            data = {"connection": "demo", "operation": "delete", "arguments": {"name": "exact"}}
            assert not (await client.call_tool("read", {**data, "operation": "get"})).isError
            assert not open_sessions
            assert not (await client.call_tool("delete", data)).isError
            assert (await client.call_tool("delete", data)).isError
            assert not open_sessions and prompt.await_count == 2
        match = SimpleNamespace(requestedSchema=approval.WriteDecision.model_json_schema(), message="A")
        reply = tunnel.approved_form("A")
        assert (await reply(None, SimpleNamespace(requestedSchema={}, message="A"))).action == "decline"
        assert (await reply(None, SimpleNamespace(requestedSchema=match.requestedSchema, message="B"))).action == "decline"
        assert (await reply(None, match)).action == "accept"
        assert (await reply(None, match)).action == "decline"
    asyncio.run(exercise())
    assert calls == [("get", {"name": "exact"}), ("delete", {"name": "exact"})]


def test_concurrent_approvals_and_cancellation_are_isolated(redis, monkeypatch):
    server, calls, _ = redis
    monkeypatch.setattr(approval, "sys", SimpleNamespace(platform="darwin"))
    async def exercise():
        pending = asyncio.Event()
        cancelled = asyncio.Event()
        async def decide(message):
            if '"first"' in message:
                pending.set()
                try:
                    await asyncio.Future()
                finally:
                    cancelled.set()
            return '"second"' in message
        monkeypatch.setattr(approval, "desktop_approval", decide)
        async with connect(server) as client:
            def delete(key):
                return client.call_tool("delete", {"connection": "demo", "operation": "delete",
                                                   "arguments": {"key": key}})
            first = asyncio.create_task(delete("first"))
            await asyncio.wait_for(pending.wait(), 2)
            assert not (await delete("second")).isError
            # Disconnect while one request is still waiting for a decision.
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
        await asyncio.wait_for(cancelled.wait(), 2)
    asyncio.run(exercise())
    assert calls == [("delete", {"key": "second"})]
