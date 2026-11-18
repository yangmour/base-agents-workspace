import json

import pytest

from infra_mcp.config import ConfigStore, InfraError
from infra_mcp.rocketmq_service import RocketMQService


@pytest.fixture
def backend(tmp_path, monkeypatch):
    conf = tmp_path / "profiles.json"
    profile = {"url": "http://localhost:18082", "cluster": "Local",
               "scope": {"topics": ["app-*"], "groups": ["app-*"]}}
    conf.write_text(json.dumps({"profiles": {"rocketmq": {
        "full": profile, "create-only": {**profile, "permissions": {"create": True}},
        "update-only": {**profile, "permissions": {"update": True}},
    }}}))
    calls = []
    data = {
        "/cluster/list.query": {"clusterInfo": {"clusterAddrTable": {"Local": ["broker-a"]}}},
        "/topic/list.query": {"topicList": ["app-z", "outside", "%SYS%app-internal", "app-a", "app-b"]},
        "/consumer/examineSubscriptionGroupConfig.query": [
            {"brokerNameList": ["broker-a"], "subscriptionGroupConfig": {"groupName": "app-g"}},
        ],
    }

    def request(profile, method, path, **kwargs):
        calls.append((method, path, kwargs))
        reply = data.get(path, True)
        return reply if isinstance(reply, dict) and "status" in reply else {"status": 0, "data": reply}

    monkeypatch.setattr("infra_mcp.rocketmq_service.request_json", request)
    return RocketMQService(ConfigStore(conf)), calls, data


@pytest.mark.parametrize(("connection", "action", "operation", "arguments"), [
    ("create-only", "create", "create_topic", {"topic": "app-test"}),
    ("update-only", "update", "update_group", {"group": "app-test"}),
    ("full", "delete", "delete_topic", {"topic": "other"}),
    ("full", "delete", "delete_group", {"group": "app-?", "broker": "arbitrary"}),
])
def test_guards_apply_before_http(backend, connection, action, operation, arguments):
    service, calls, _ = backend
    with pytest.raises(InfraError) as error:
        service.run(connection, action, operation, arguments)
    assert error.value.code in {"permission_denied", "scope_denied", "invalid_argument"}
    assert calls == []


def test_topic_pagination_filters_before_slicing(backend):
    service, _, _ = backend
    result = service.run("full", "read", "list_topics", {"offset": 1, "limit": 1})
    assert result["data"] == {"topics": ["app-b"], "offset": 2, "has_more": True}


def test_dashboard_application_error_is_not_success_or_disclosed(backend):
    service, _, data = backend
    data["/cluster/list.query"] = {"status": -1, "data": None, "errMsg": "private backend details"}
    with pytest.raises(InfraError, match="status -1") as error:
        service.run("full", "read", "check_connection")
    assert "private backend details" not in str(error.value)


def test_dashboard_connected_without_brokers_is_not_ready(backend):
    service, _, data = backend
    data["/cluster/list.query"] = {"clusterInfo": {"clusterAddrTable": {"Local": []}}}
    with pytest.raises(InfraError):
        service.run("full", "read", "check_connection")


def test_mutation_uses_only_configured_cluster_and_discovered_brokers(backend):
    service, calls, _ = backend
    service.run("full", "delete", "delete_group", {"group": "app-g"})
    assert calls[-1] == ("POST", "/consumer/deleteSubGroup.do",
                         {"json": {"groupName": "app-g", "brokerNameList": ["broker-a"]},
                          "csrf_path": "/rocketmq-dashboard/csrf-token"})


def test_cluster_mismatch_never_mutates(backend):
    service, calls, data = backend
    data["/cluster/list.query"]["clusterInfo"]["clusterAddrTable"]["Other"] = ["broker-b"]
    with pytest.raises(InfraError):
        service.run("full", "create", "create_topic", {"topic": "app-new"})
    assert all(method == "GET" for method, _, _ in calls)


def test_dashboard_marks_existing_system_topics(backend):
    service, calls, _ = backend
    with pytest.raises(InfraError, match="system"):
        service.run("full", "delete", "delete_topic", {"topic": "app-internal"})
    assert all(method == "GET" for method, _, _ in calls)
