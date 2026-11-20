import httpx
import pytest

from infra_mcp.config import InfraError


class Controller:
    base_url = "https://ci.test/jenkins"

    def __init__(self):
        self.routes = {}
        self.calls = []

    def job_path(self, job):
        return "".join("/job/" + part for part in job.split("/"))

    def redact(self, text):
        return text.replace("SENSITIVE", "[redacted]")

    def request(self, method, path, **options):
        self.calls.append((method, path, options))
        response = self.routes.get((method, path), httpx.Response(404))
        if isinstance(response, Exception):
            raise response
        if response.status_code not in options.get("accepted", (200,)):
            raise InfraError("upstream_error", str(response.status_code))
        return response

    def json(self, path, params=None):
        return self.request("GET", path, params=params).json()


def test_submit_once_across_controllers_and_restart(tmp_path):
    from infra_mcp.jenkins_builds import submit

    ci = Controller()
    path = "/job/team/job/test/build"
    ci.routes["POST", path] = httpx.Response(201, headers={"Location": "/jenkins/queue/item/9/"})
    for _ in range(2):
        assert submit(ci, "team/test", {}, "request-1", tmp_path)["queue_id"] == 9
    assert len([c for c in ci.calls if c[0] == "POST"]) == 1
    ci.base_url = "https://ci2.test/jenkins"
    assert submit(ci, "team/test", {}, "request-1", tmp_path)["queue_id"] == 9
    with pytest.raises(InfraError):
        submit(ci, "team/test", {"x": "other"}, "request-1", tmp_path)


def test_ambiguous_submission_is_never_repeated(tmp_path):
    from infra_mcp.jenkins_builds import submit

    ci = Controller()
    ci.routes["POST", "/job/app/buildWithParameters"] = httpx.ReadTimeout("timeout")
    ci.routes["GET", "/queue/api/json"] = httpx.Response(200, json={"items": []})
    ci.routes["GET", "/job/app/api/json"] = httpx.Response(200, json={"builds": []})
    assert submit(ci, "app", {"branch": "dev"}, "abc", tmp_path)["state"] == "submission_unknown"
    assert submit(ci, "app", {"branch": "dev"}, "abc", tmp_path)["state"] == "submission_unknown"
    assert sum(call[0] == "POST" for call in ci.calls) == 1


def test_expired_queue_exact_match_and_cancel_scope():
    from infra_mcp.jenkins_builds import status, cancel

    ci = Controller()
    ci.routes["GET", "/job/app/api/json"] = httpx.Response(
        200, json={"builds": [{"number": 21, "queueId": 11}, {"number": 20, "queueId": 10}]}
    )
    ci.routes["GET", "/job/app/20/api/json"] = httpx.Response(
        200, json={"number": 20, "queueId": 10, "building": True}
    )
    assert status(ci, "app", queue_id=10)["build"] == 20
    ci.routes["GET", "/queue/item/10/api/json"] = httpx.Response(200, json={"task": {"fullName": "other"}})
    with pytest.raises(InfraError):
        cancel(ci, "app", queue_id=10)
    assert all(call[0] == "GET" for call in ci.calls)


def test_history_and_progressive_log():
    from infra_mcp.jenkins_builds import history, log

    ci = Controller()
    ci.routes["GET", "/job/app/api/json"] = httpx.Response(
        200,
        json={
            "builds": [
                {"number": 2, "result": "SUCCESS", "artifacts": [{"relativePath": "infra-release.json"}]},
                {"number": 1, "result": "FAILURE"},
            ]
        },
    )
    ci.routes["GET", "/job/app/2/artifact/infra-release.json"] = httpx.Response(
        200, json={"image": "repo:tag", "password": "abc"}
    )
    rows = history(ci, "app", 1)
    assert len(rows) == 1 and rows[0]["release"] == {"image": "repo:tag"}
    ci.routes["GET", "/job/app/2/logText/progressiveText"] = httpx.Response(
        200, text="SENSITIVE\n", headers={"X-Text-Size": "10"}
    )
    page = log(ci, "app", 2)
    assert page["next_start"] == 10 and "SENSITIVE" not in page["text"]


def test_rejected_submission_and_read_only_lookup(tmp_path):
    from infra_mcp.jenkins_builds import submit, lookup

    ci = Controller()
    ci.routes["POST", "/job/app/build"] = httpx.Response(403, text="SENSITIVE")
    rejected = submit(ci, "app", {}, "ident", tmp_path)
    assert rejected["state"] == "rejected" and rejected["http_status"] == 403
    assert lookup(ci, "app", "ident", tmp_path) == rejected
    assert lookup(ci, "app", "missing", tmp_path)["state"] == "unknown"
    assert len(ci.calls) == 1


def test_recovery_with_declared_request_parameter(tmp_path):
    from infra_mcp.jenkins_builds import submit

    ci = Controller()
    ci.routes["POST", "/job/app/buildWithParameters"] = httpx.ReadTimeout("timeout")
    action = {"parameters": [{"name": "INFRA_MCP_REQUEST_ID", "value": "ident"}]}
    ci.routes["GET", "/queue/api/json"] = httpx.Response(
        200,
        json={
            "items": [
                {"id": 5, "task": {"fullName": "other"}, "actions": [action]},
                {"id": 6, "task": {"fullName": "app"}, "actions": [action]},
            ]
        },
    )
    result = submit(ci, "app", {"INFRA_MCP_REQUEST_ID": "ident"}, "ident", tmp_path)
    assert result["queue_id"] == 6


def test_build_metadata_and_failure_evidence():
    from infra_mcp.jenkins_builds import status

    ci = Controller()
    sha = "a" * 40
    ci.routes["GET", "/job/app/3/api/json"] = httpx.Response(
        200,
        json={
            "number": 3,
            "result": "FAILURE",
            "timestamp": 123,
            "actions": [{"lastBuiltRevision": {"SHA1": sha, "branch": [{"name": "origin/dev"}]}}],
        },
    )
    ci.routes["GET", "/job/app/3/wfapi/describe"] = httpx.Response(
        200, json={"stages": [{"status": "FAILED", "name": "compile"}]}
    )
    ci.routes["GET", "/job/app/3/logText/progressiveText"] = httpx.Response(
        200, text="Error: SENSITIVE", headers={"X-Text-Size": "16"}
    )
    row = status(ci, "app", build=3)
    assert row["scm"] == [{"commit": sha, "branches": ["origin/dev"]}]
    assert row["failure_evidence"] == {"stages": ["compile"], "excerpt": "Error: [redacted]"}


def test_log_uses_lower_connection_limit_and_marks_omitted_range():
    from infra_mcp.jenkins_builds import log

    ci = Controller()
    ci.maximum = 1024
    ci.routes["GET", "/job/app/3/logText/progressiveText"] = httpx.Response(
        200, content=b"\n" * 1024, headers={"X-Text-Size": "9000"}
    )
    page = log(ci, "app", 3)
    assert page["truncated"] and page["gap"] and page["next_start"] == 9000


def test_failure_excerpt_reads_the_tail():
    from infra_mcp.jenkins_builds import status

    class Tail(Controller):
        def request(self, method, path, **options):
            if path.endswith("/progressiveText"):
                offset = options["params"]["start"]
                return httpx.Response(
                    200,
                    content=b"begin\n" * 4000 if offset == 0 else b"Error: build broke\n",
                    headers={"X-Text-Size": "75000"},
                )
            return super().request(method, path, **options)

    ci = Tail()
    ci.routes["GET", "/job/app/2/api/json"] = httpx.Response(200, json={"number": 2, "result": "FAILURE"})
    assert status(ci, "app", build=2)["failure_evidence"]["excerpt"] == "Error: build broke"


def test_intent_pins_parameters_and_uses_parameterized_endpoint(tmp_path):
    from infra_mcp.jenkins_builds import submit_intent

    ci = Controller()
    ci.routes["POST", "/job/app/buildWithParameters"] = httpx.Response(
        201, headers={"Location": "/jenkins/queue/item/1/"}
    )
    intent = {"action": "rollback", "source": "previous"}
    row = submit_intent(ci, "app", "x", tmp_path, intent, lambda: ({}, True))

    def unexpected():
        pytest.fail("repeat request resolved mutable history")

    assert row["queue_id"] == 1
    assert submit_intent(ci, "app", "x", tmp_path, intent, unexpected) == row
    with pytest.raises(InfraError):
        submit_intent(ci, "app", "x", tmp_path, {"action": "release"}, unexpected)
    assert (tmp_path / "jenkins-requests.sqlite3").stat().st_mode & 0o777 == 0o600


def test_concurrent_intent_resolutions_use_one_payload(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from infra_mcp.jenkins_builds import submit_intent

    ci = Controller()
    ci.routes["POST", "/job/app/buildWithParameters"] = httpx.Response(
        201, headers={"Location": "/jenkins/queue/item/1/"}
    )
    wait = Barrier(2)

    def run(revision):
        wait.wait(timeout=5)
        return submit_intent(
            ci, "app", "x", tmp_path, {"source": "previous"}, lambda: ({"revision": revision}, True)
        )

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(run, ["1", "2"]))
    posts = [c for c in ci.calls if c[0] == "POST"]
    assert len(posts) == 1 and posts[0][2]["data"]["revision"] in {"1", "2"}


def test_reconciliation_uses_request_id_and_account_when_available(tmp_path):
    from infra_mcp.jenkins_builds import submit

    ci = Controller()
    ci.username = "operator"
    ci.routes["POST", "/job/app/buildWithParameters"] = httpx.ReadTimeout("timeout")

    def item(qid, user):
        return {
            "id": qid,
            "task": {"fullName": "app"},
            "actions": [
                {"parameters": [{"name": "REQUEST_ID", "value": "x"}]},
                {"causes": [{"userId": user}]},
            ],
        }

    ci.routes["GET", "/queue/api/json"] = httpx.Response(
        200, json={"items": [item(3, "someone"), item(5, "operator")]}
    )
    assert submit(ci, "app", {"REQUEST_ID": "x"}, "x", tmp_path)["queue_id"] == 5


def test_unavailable_artifact_preserves_neighbor_history():
    from infra_mcp.jenkins_builds import history

    ci = Controller()
    ci.routes["GET", "/job/app/api/json"] = httpx.Response(
        200,
        json={
            "builds": [
                {"number": n, "result": "SUCCESS", "artifacts": [{"relativePath": "infra-release.json"}]}
                for n in (3, 2, 1)
            ]
        },
    )
    ci.routes["GET", "/job/app/3/artifact/infra-release.json"] = httpx.Response(403)
    ci.routes["GET", "/job/app/2/artifact/infra-release.json"] = httpx.Response(200, text="invalid")
    ci.routes["GET", "/job/app/1/artifact/infra-release.json"] = httpx.Response(200, json={"revision": 2})
    rows = history(ci, "app")
    assert [r.get("release_evidence") for r in rows[:2]] == ["unknown", "unknown"]
    assert rows[2]["release"] == {"revision": 2}


def test_log_masks_third_party_credentials():
    from infra_mcp.jenkins_builds import log

    ci = Controller()
    msg = 'docker login --password "third-party-value"\n{"token":"abc000xyz"}\nBearer opaque-token-123\n'
    ci.routes["GET", "/job/app/1/logText/progressiveText"] = httpx.Response(
        200, text=msg, headers={"X-Text-Size": str(len(msg))}
    )
    page = log(ci, "app", 1)
    assert all(
        secret not in page["text"] for secret in ("third-party-value", "abc000xyz", "opaque-token-123")
    )


def test_private_request_state_rejects_symlink_or_shared_writable_directory(tmp_path):
    from infra_mcp.jenkins_builds import lookup

    ci = Controller()
    target = tmp_path / "other-file"
    target.write_text("untouched")
    state = tmp_path / "state"
    state.mkdir()
    (state / "jenkins-requests.sqlite3").symlink_to(target)
    with pytest.raises(InfraError):
        lookup(ci, "app", "x", state)
    assert target.read_text() == "untouched"
    shared = tmp_path / "shared"
    shared.mkdir()
    shared.chmod(0o777)
    with pytest.raises(InfraError):
        lookup(ci, "app", "x", shared)
