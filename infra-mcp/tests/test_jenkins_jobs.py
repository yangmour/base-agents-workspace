import xml.etree.ElementTree as ET

import httpx
import pytest

from infra_mcp.config import InfraError, Profile
from infra_mcp.jenkins_jobs import handle_job


class Client:
    base_url = "https://ci.example"

    def __init__(self):
        self.xml = None
        self.writes = []

    def job_path(self, name):
        return "".join("/job/" + part for part in name.split("/"))

    def json(self, path, params=None):
        assert path.strip("/") == "whoAmI/api/json"
        return {"name": "svc-ci", "authenticated": True}

    def redact(self, text):
        return text.replace("hidden-token", "***")

    def request(self, method, path, **kwargs):
        if method == "GET":
            assert path == "/job/apps/job/api/config.xml"
            code = 404 if self.xml is None else 200
            return httpx.Response(code, content=self.xml or b"")
        self.writes.append((path, kwargs))
        if path.endswith("doDelete"):
            self.xml = None
        else:
            self.xml = kwargs["content"]
        return httpx.Response(200)


@pytest.fixture
def setup(tmp_path):
    client = Client()
    profile = Profile("lab", "jenkins", {}, frozenset(), {})
    def call(op, **args):
        return handle_job(client, profile, op, {"job": "apps/api", **args}, tmp_path / "state")
    return client, call


CONFIG = {"repository": "https://git.example/repo.git", "branch": "*/main",
          "jenkinsfile": "ci/Jenkinsfile", "parameters": [{"name": "BRANCH", "type": "string", "default": "main"}]}


def test_lifecycle(setup, tmp_path):
    client, call = setup
    preview = call("preview_job_config", mode="create", config=CONFIG)
    assert preview["expected_version"] == "absent" and preview["diff"]
    assert not client.writes
    call("create_job", expected_version="absent", config=CONFIG)
    assert client.writes[-1][0] == "/job/apps/createItem" and client.writes[-1][1]["params"]["name"] == "api"
    client.xml = client.xml.replace(b"</flow-definition>", b"<custom>hidden-token</custom></flow-definition>")
    current = call("get_job_config")
    assert current["config"]["parameters"][0]["name"] == "BRANCH"
    preview = call("preview_job_config", mode="update", config={"branch": "*/release"})
    assert "release" in str(preview["diff"]) and "hidden-token" not in str(preview)
    with pytest.raises(InfraError):
        call("update_job", expected_version="bad", config={"branch": "*/oops"})
    call("update_job", expected_version=current["version"], config={"branch": "*/release"})
    assert ET.fromstring(client.xml).findtext("custom") == "hidden-token"
    raw = client.xml
    deleted = call("delete_job", expected_version=call("get_job_config")["version"])
    assert client.xml is None
    call("restore_job", expected_version="absent", snapshot_id=deleted["snapshot_id"])
    assert client.xml == raw
    history = call("list_job_history")
    assert "svc-ci" in str(history) and "hidden-token" not in str(history)
    assert all(p.stat().st_mode & 0o077 == 0 for p in (tmp_path / "state").iterdir())


@pytest.mark.parametrize("bad", [{"repository": "https://user:secret@git.example/repo"},
                                 {"jenkinsfile": "../Jenkinsfile"}, {"branch": "\nmain"},
                                 {"script": "arbitrary"}, {"repository": "file:///tmp/repo"},
                                 {"parameters": [{"name": "PASSWORD", "type": "string", "default": "secret"}]}])
def test_rejects_invalid_config(setup, bad):
    client, call = setup
    with pytest.raises(InfraError):
        call("create_job", expected_version="absent", config=CONFIG | bad)
    assert not client.writes


def test_redirect_to_login_keeps_snapshot_and_tracks_uncertainty(setup):
    client, call = setup
    call("create_job", expected_version="absent", config=CONFIG)
    request = client.request
    def redirect(method, path, **kwargs):
        if path.endswith("/doDelete"):
            return httpx.Response(302, headers={"Location": "/login"})
        return request(method, path, **kwargs)
    client.request = redirect
    with pytest.raises(InfraError):
        call("delete_job", expected_version=call("get_job_config")["version"])
    event = call("list_job_history")["events"][0]
    assert event["status"] == "outcome_unknown" and event["snapshot_id"]


def test_records_trusted_caller_id(tmp_path):
    client = Client()
    profile = Profile("lab", "jenkins", {"caller_id": "automation"}, frozenset(), {})
    args = {"job": "apps/api", "expected_version": "absent", "config": CONFIG, "caller_id": "untrusted"}
    handle_job(client, profile, "create_job", args, tmp_path)
    event = handle_job(client, profile, "list_job_history", {"job": "apps/api"}, tmp_path)["events"][0]
    assert event["caller_id"] == "automation"


def test_multibranch_lifecycle_preserves_traits_and_exclusions(setup):
    client, call = setup
    config = {"type": "multibranch", "repository": CONFIG["repository"], "jenkinsfile": "foo/Pipeline", "branch": "feature/* main"}
    call("create_job", expected_version="absent", config=config)
    root = ET.fromstring(client.xml)
    assert root.tag == "org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject"
    source = root.find("sources/data/jenkins.branch.BranchSource/source")
    assert source.get("class") == "jenkins.plugins.git.GitSCMSource"
    trait = source.find("traits/jenkins.scm.impl.trait.WildcardSCMHeadFilterTrait")
    trait.find("excludes").text = "feature/private"
    ET.SubElement(source.find("traits"), "other.trait")
    client.xml = ET.tostring(root)
    current = call("get_job_config")
    assert current["config"]["parameter_source"] == "Jenkinsfile"
    assert current["config"]["branch"] == "feature/* main"
    assert "other.trait" not in str(current)
    preview = call("preview_job_config", mode="update", config={"branch": "release/*"})
    assert "release/*" in str(preview["diff"])
    call("update_job", expected_version=current["version"], config={"branch": "release/*"})
    assert b"feature/private" in client.xml and b"other.trait" in client.xml
    before_delete = client.xml
    deleted = call("delete_job", expected_version=call("get_job_config")["version"])
    call("restore_job", expected_version="absent", snapshot_id=deleted["snapshot_id"])
    assert client.xml == before_delete


def test_branch_child_rejects_direct_mutations(setup):
    client, call = setup
    client.xml = b'<flow-definition><definition class="org.jenkinsci.plugins.workflow.multibranch.SCMBinder"><scriptPath>Jenkinsfile</scriptPath></definition></flow-definition>'
    read = call("get_job_config")
    assert read["config"]["managed_by"] == "apps"
    for mode in ("delete", "update"):
        with pytest.raises(InfraError, match="parent"):
            call(mode + "_job", expected_version=read["version"], config={"branch": "main"})
    assert not client.writes


def test_child_branch_property_identifies_managed_job_even_with_scm_definition(setup):
    client, call = setup
    call("create_job", expected_version="absent", config=CONFIG)
    root = ET.fromstring(client.xml)
    ET.SubElement(root.find("properties"), "org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty")
    client.xml = ET.tostring(root)
    assert call("get_job_config")["config"]["managed_by"] == "apps"
