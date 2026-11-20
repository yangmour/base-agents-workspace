import json
from unittest.mock import patch

import httpx
import pytest

from infra_mcp.config import ConfigStore, InfraError
from infra_mcp.jenkins_client import JenkinsClient
from infra_mcp.jenkins_service import JenkinsService

TARGET = {"environment": "test", "service": "auth", "branch": "develop", "cluster": "cluster-uid",
          "namespace": "develop", "deployment": "auth", "rollback_job": "test/undo"}
JOB = "test/auth"

@pytest.fixture
def service(tmp_path):
    config = {"url": "http://localhost:8080/ci", "username": "bot", "token_file": "api-token",
              "targets": {JOB: TARGET}, "capabilities": ["deploy", "rollback", "cancel"],
              "scope": {"jobs": ["test/*"]}}
    (tmp_path / "api-token").write_text("private-example")
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps({"profiles": {"jenkins": {"local": config}}}))
    return JenkinsService(ConfigStore(path))

def test_catalog_and_scope(service):
    data = service.run("local", "read", "list_pipelines", {"environment": "test"})["data"]
    assert data["pipelines"][0]["job"] == JOB
    assert data["pipelines"][0]["branch"] == "develop"
    assert service.run("local", "read", "list_pipelines", {"environment": "prod"})["data"]["pipelines"] == []
    with pytest.raises(InfraError, match="scope"):
        service.run("local", "read", "build_status", {"job": "prod/auth", "build": 1})

def test_no_dynamic_branch_on_fixed_job(service):
    with pytest.raises(InfraError, match="branch"):
        service.run("local", "create", "deploy", {"job": JOB, "branch": "main", "request_id": "x"})

def test_client_restricts_paths_and_hides_token(service):
    client = JenkinsClient(service.config.get("jenkins", "local"))
    assert client.job_path("Folder A/web") == "/job/Folder%20A/job/web"
    for name in ["prod/../other", "test//foo", "a/%2e%2e", "a/./x"]:
        with pytest.raises(InfraError):
            client.job_path(name)
    assert "private-example" not in client.redact("error private-example")
    with pytest.raises(InfraError):
        client.request("GET", "//example.invalid/")

def test_live_observation_fallback_and_commit_evidence(service):
    release = dict(TARGET, ready=True, image="registry/auth:7", commit="a"*40, revision=3,
                   observed_at="2026-11-20T02:00:00Z")
    with patch("infra_mcp.jenkins_service.builds.history", return_value=[
            {"result": "SUCCESS", "job": JOB, "build": 7, "release": release, "timestamp": 200},
            {"job": JOB, "build": 6, "release": dict(release, namespace="prod"), "timestamp": 100}]):
        result = service.run("local", "read", "current_version", {"job": JOB})["data"]
        assert result["source"] == "last_verified_deployment"
        assert result["release"]["commit"] == "a"*40

def test_fixed_origin_no_redirect_and_response_size(service, monkeypatch):
    client = JenkinsClient(service.config.get("jenkins", "local"))
    seen = []
    def respond(request):
        seen.append(str(request.url))
        assert request.headers["Authorization"].startswith("Basic ")
        if request.url.path.endswith("/big"):
            return httpx.Response(200, content=b"x"*3000)
        return httpx.Response(302, headers={"Location": "https://other.invalid/"})
    transport = httpx.MockTransport(respond)
    constructor = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: constructor(transport=transport, **kw))
    with pytest.raises(InfraError):
        client.json("/api/json")
    assert client.request("GET", "/big", max_bytes=100, truncate=True).content == b"x"*100
    assert len(seen) == 2 and all(url.startswith(client.base_url + "/") for url in seen)


def evidence(revision, build):
    return {"result": "SUCCESS", "job": JOB, "build": build, "kind": "deploy", "verified": True,
            "release": dict(TARGET, ready=True, image="registry/auth:same-tag", commit="a"*40,
                            source_build=build, revision=revision, observed_at="2026-11-20T02:00:00Z")}


def test_previous_revision_anchors_on_live_state(service):
    profile = service.config.get("jenkins", "local")
    rows = [evidence(9, 20), evidence(8, 17), evidence(7, 15)]
    current = {"source": "kubernetes", "release": rows[1]["release"]}
    with patch("infra_mcp.jenkins_service.records", return_value=rows), patch.object(service, "current", return_value=current):
        assert service.rollback_source(None, profile, {**TARGET, "job": JOB}, {})["build"] == 15


def test_optional_commit_pin_needs_declared_support(service):
    with pytest.raises(InfraError, match="commit"):
        service.run("local", "read", "preview_deploy", {"job": JOB, "commit": "b"*40})


def test_stop_then_query_actual_version(service):
    response = {"state": "aborted", "result": "ABORTED", "build": 3}
    with patch("infra_mcp.jenkins_service.builds.status", return_value=response), patch.object(
        service, "current", return_value={"source": "kubernetes", "release": {"image": "app:v2"}}):
        result = service.run("local", "read", "build_status", {"job": JOB, "build": 3})["data"]
        assert result["deployment_observation"]["release"]["image"] == "app:v2"


def test_release_and_rollback_share_real_service_entry_point(service, monkeypatch):
    from urllib.parse import parse_qs

    params_sent = []
    latest = evidence(4, 8)
    meta = {"buildable": True, "_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob",
            "property": [{"parameterDefinitions": [{"name": name, "type": "StringParameterDefinition"}
                          for name in ("REQUEST_ID", "SOURCE_BUILD", "TARGET_IMAGE", "TARGET_COMMIT", "TARGET_REVISION")]}]}

    def respond(request):
        path = request.url.path
        if path.endswith("/buildWithParameters"):
            params_sent.append((path, parse_qs(request.content.decode())))
            return httpx.Response(201, headers={"Location": f"/ci/queue/item/{len(params_sent)}/"})
        if path == "/ci/job/test/job/auth/8/api/json":
            return httpx.Response(200, json={"number": 8, "result": "SUCCESS", "queueId": 1,
                "artifacts": [{"relativePath": "infra-release.json"}]})
        if path.endswith("/8/artifact/infra-release.json"):
            return httpx.Response(200, json=latest["release"])
        if path.endswith("/api/json"):
            return httpx.Response(200, json=meta)
        raise AssertionError(path)
    constructor = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: constructor(transport=httpx.MockTransport(respond), **kw))
    arguments = {"job": JOB, "branch": "develop", "request_id": "rc-1"}
    for _ in range(2):
        assert service.run("local", "create", "deploy", arguments)["data"]["queue_id"] == 1
    assert service.run("local", "read", "request_status", {"job": JOB, "request_id": "rc-1"})["data"]["queue_id"] == 1
    assert service.run("local", "read", "build_status", {"job": JOB, "build": 8})["data"]["deployment_readiness"] == "verified"
    rollback = {"environment": "test", "service": "auth", "source_build": 8, "request_id": "rollback-1"}
    assert service.run("local", "create", "rollback", rollback)["data"]["queue_id"] == 2
    assert params_sent == [
        ("/ci/job/test/job/auth/buildWithParameters", {"REQUEST_ID": ["rc-1"]}),
        ("/ci/job/test/job/undo/buildWithParameters", {"REQUEST_ID": ["rollback-1"], "SOURCE_BUILD": ["8"],
         "TARGET_COMMIT": ["a"*40], "TARGET_REVISION": ["4"], "TARGET_IMAGE": ["registry/auth:same-tag"]})]


def test_read_grant_cannot_publish_or_change_configuration(service):
    profile = json.loads(service.config.path.read_text())
    profile["profiles"]["jenkins"]["local"]["capabilities"] = []
    service.config.path.write_text(json.dumps(profile))
    for action, operation in (("create","deploy"), ("create","rollback"), ("update","cancel_build"), ("delete","delete_job")):
        with pytest.raises(InfraError, match="capability"):
            service.run("local", action, operation, {"job": JOB})


def test_live_observation_uses_scoped_k8s_and_omits_environment(service):
    profile = json.loads(service.config.path.read_text())
    profile["profiles"]["jenkins"]["local"]["targets"][JOB]["kubernetes_connection"] = "observer"
    profile["profiles"]["kubernetes"] = {"observer": {"kubeconfig": "subadminconfig", "context": "test",
        "permissions": {"read": True}, "scope": {"namespaces": ["develop"], "resources": ["deployments"], "names": ["auth"]}}}
    service.config.path.write_text(json.dumps(profile))
    obj = {"metadata": {"generation": 5, "annotations": {"deployment.kubernetes.io/revision": "12"}},
           "spec": {"replicas": 2, "template": {"metadata": {"annotations": {"infra.xiwen.io/commit": "e"*40,
               "infra.xiwen.io/build": "51"}}, "spec": {"containers": [{"name": "auth", "image": "registry/auth:51",
               "env": [{"name": "PASSWORD", "value": "not-for-output"}]}]}}},
           "status": {"observedGeneration": 5, "replicas": 2, "updatedReplicas": 2, "readyReplicas": 1, "availableReplicas": 1}}
    with patch("infra_mcp.kubernetes_service._run_bounded", return_value=json.dumps(obj)) as call:
        output = service.run("local", "read", "current_version", {"job": JOB})["data"]
    assert output["source"] == "kubernetes" and output["release"]["revision"] == 12
    assert output["release"]["ready"] is False and output["release"]["source_build"] == 51
    assert "not-for-output" not in str(output)
    assert ["get", "deployments", "auth"] == call.call_args.args[0][-5:-2]


def test_scoped_discovery_traverses_permitted_folder_only(service):
    with patch.object(JenkinsClient, "json", return_value={"jobs": [
        {"fullName": "test", "_class": "com.cloudbees.hudson.plugins.folder.Folder"},
        {"fullName": "private", "_class": "com.cloudbees.hudson.plugins.folder.Folder"}]}) as call:
        rows = service.run("local", "read", "discover_jobs")["data"]["jobs"]
        assert [row["job"] for row in rows] == ["test"]
        with pytest.raises(InfraError, match="scope"):
            service.run("local", "read", "discover_jobs", {"folder": "private"})
        assert call.call_count == 1


def test_describe_multibranch_child_reads_actual_scm_head(service):
    xml = b"""<flow-definition><properties><org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty>
      <branch><head><name>feature/team</name></head></branch>
      </org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty></properties>
      <definition class="org.jenkinsci.plugins.workflow.multibranch.SCMBinder"><scriptPath>ci/app.jenkins</scriptPath></definition>
      </flow-definition>"""
    with patch.object(JenkinsClient, "json", return_value={"buildable": True}), patch.object(
        JenkinsClient, "request", return_value=httpx.Response(200, content=xml)):
        info = service.run("local", "read", "describe_pipeline", {"job": JOB})["data"]
    assert info["script_branch"] == "feature/team" and info["jenkinsfile"] == "ci/app.jenkins"
    assert info["branch"] == "develop"


def test_branch_can_disambiguate_fixed_pipelines(service):
    profile = json.loads(service.config.path.read_text())
    target = dict(TARGET, branch="release", rollback_job="test/undo-release")
    profile["profiles"]["jenkins"]["local"]["targets"]["test/auth-release"] = target
    service.config.path.write_text(json.dumps(profile))
    metadata = {"_class": "org.jenkinsci.plugins.workflow.job.WorkflowJob", "buildable": True}
    with patch("infra_mcp.jenkins_service.metadata", return_value=metadata), patch.object(
            service, "current", return_value={"source": "unknown"}):
        preview = service.run("local", "read", "preview_deploy",
                              {"environment": "test", "service": "auth", "branch": "release"})["data"]
    assert preview["execution_job"] == "test/auth-release"


def test_discovery_explains_extra_write_capabilities(service):
    row = service.list_connections()["connections"][0]
    assert set(row["capabilities"]) == {"deploy", "rollback", "cancel"}
    ops = service.list_operations()["operations"]
    assert ops["restore_job"]["required_capabilities"] == ["configure"]
    assert ops["rollback"]["required_capabilities"] == ["rollback"]
