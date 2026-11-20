"""Bounded Jenkins queue, run and deployment-record operations."""

import hashlib
import json
import os
import stat
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .config import InfraError


FIELDS = (
    "number,queueId,building,result,timestamp,duration,artifacts[relativePath],"
    "actions[lastBuiltRevision[SHA1,branch[name]]]"
)
CAUSES = "actions[causes[shortDescription,note,userId],parameters[name,value]]"
REQUEST_PARAMETERS = {"REQUEST_ID", "INFRA_MCP_REQUEST_ID"}
LOG_BYTES = 16384
RESULTS = {"SUCCESS", "FAILURE", "ABORTED", "UNSTABLE", "NOT_BUILT"}
RELEASE_STRINGS = (
    "environment",
    "service",
    "cluster",
    "namespace",
    "deployment",
    "image",
    "commit",
    "observed_at",
    "digest",
    "branch",
    "action",
    "container",
)


def _positive(value, name):
    if type(value) is not int or not 0 < value <= 2**63 - 1:
        raise InfraError("invalid_argument", f"{name} must be a positive integer")
    return value


def _build_url(client, job, number):
    return client.base_url.rstrip("/") + client.job_path(job) + f"/{number}/"


def _job_matches(client, job, task):
    if not isinstance(task, dict):
        return False
    if task.get("fullName"):
        return task["fullName"] == job
    url = task.get("url")
    expected = urlsplit(client.base_url.rstrip("/") + client.job_path(job))
    if not isinstance(url, str):
        return False
    actual = urlsplit(url)
    return actual.path.rstrip("/") == expected.path.rstrip("/") and (
        not actual.netloc or actual.netloc == expected.netloc
    )


def _builds(client, job, limit, fields):
    tree = f"builds[{fields}]{{0,{limit}}}"
    return client.json(client.job_path(job) + "/api/json", params={"tree": tree}).get("builds", [])[:limit]


def _normalize(client, job, row):
    number = _positive(row.get("number"), "build")
    result = row.get("result")
    result = result if result in RESULTS else None
    state = "running" if row.get("building") else result.lower() if result else "unknown"
    item = {
        "job": job,
        "build": number,
        "state": state,
        "result": result,
        "url": _build_url(client, job, number),
    }
    for key, dest in (("timestamp", "timestamp"), ("duration", "duration"), ("queueId", "queue_id")):
        if type(row.get(key)) is int:
            item[dest] = row[key]
    revisions = []
    for action in row.get("actions", []):
        revision = action.get("lastBuiltRevision") or {}
        sha = revision.get("SHA1")
        if isinstance(sha, str) and re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", sha):
            branches = [
                client.redact(b["name"])[:256]
                for b in revision.get("branch", [])[:8]
                if isinstance(b.get("name"), str)
            ]
            revisions.append({"commit": sha, "branches": branches})
    if revisions:
        item["scm"] = revisions[:10]
    if result and any(a.get("relativePath") == "infra-release.json" for a in row.get("artifacts", [])):
        path = client.job_path(job) + f"/{number}/artifact/infra-release.json"
        try:
            record = client.json(path)
            if not isinstance(record, dict):
                raise ValueError("Expected an artifact object")
            release = {
                k: client.redact(record[k])
                for k in RELEASE_STRINGS
                if isinstance(record.get(k), str) and len(record[k]) <= 2048
            }
            if type(record.get("ready")) is bool:
                release["ready"] = record["ready"]
            for key in ("revision", "source_build", "source_revision"):
                if type(record.get(key)) is int and record[key] > 0:
                    release[key] = record[key]
            if release:
                item["release"] = release
            else:
                item["release_evidence"] = "unknown"
        except (InfraError, httpx.HTTPError, ValueError, RecursionError):
            item["release_evidence"] = "unknown"
    return item


def history(client, job, limit=20):
    if _positive(limit, "limit") > 100:
        raise InfraError("invalid_argument", "limit must be at most 100")
    return [_normalize(client, job, row) for row in _builds(client, job, limit, FIELDS)]


def log(client, job, build, start=0):
    _positive(build, "build")
    if type(start) is not int or not 0 <= start <= 2**63 - 1:
        raise InfraError("invalid_argument", "start must be a nonnegative byte offset")
    path = client.job_path(job) + f"/{build}/logText/progressiveText"
    budget = min(LOG_BYTES, getattr(client, "maximum", LOG_BYTES + 1) - 1)
    response = client.request("GET", path, params={"start": start}, max_bytes=budget + 1, truncate=True)
    # Jenkins offsets refer to bytes in its annotated log, not decoded response characters.
    offset = response.headers.get("X-Text-Size", "")
    if not re.fullmatch(r"[0-9]{1,19}", offset) or not start <= int(offset) <= 2**63 - 1:
        raise InfraError("invalid_argument", "Jenkins returned an invalid progressive log offset")
    truncated = len(response.content) > budget
    text = client.redact(response.content.decode("utf-8", errors="replace"))
    text = re.sub(r"(?i)(\bBearer\s+)\S+", r"\1[REDACTED]", text)
    text = re.sub(
        r"""(?im)(--(?:password|passwd|token|api-key|secret)(?:=|\s+)|["'](?:password|token|secret|api[_-]?key)["']\s*:\s*).+$""",
        r"\1[REDACTED]",
        text,
    )
    # Incomplete final lines can contain partial credentials.
    if truncated:
        text = text.rpartition("\n")[0]
    return {
        "job": job,
        "build": build,
        "start": start,
        "next_start": int(offset),
        "gap": truncated,
        "text": text[:LOG_BYTES],
        "truncated": truncated,
        "more": response.headers.get("X-More-Data", "").lower() == "true",
    }


def _build_status(client, job, number):
    path = client.job_path(job) + f"/{number}"
    row = client.json(path + "/api/json", params={"tree": FIELDS})
    if row.get("number") != number:
        raise InfraError("invalid_argument", "Jenkins returned a different build number")
    item = _normalize(client, job, row)
    if item["state"] in {"failure", "unstable"}:
        evidence = {}
        try:
            stages = client.request("GET", path + "/wfapi/describe", accepted=(200, 404))
            if stages.status_code == 200:
                evidence["stages"] = [
                    client.redact(s["name"])[:160]
                    for s in stages.json().get("stages", [])
                    if s.get("status") in {"FAILED", "UNSTABLE"} and isinstance(s.get("name"), str)
                ][:8]
        except (InfraError, httpx.HTTPError, ValueError):
            pass
        try:
            page = log(client, job, number)
            if page["truncated"]:
                page = log(
                    client,
                    job,
                    number,
                    max(
                        0, page["next_start"] - min(LOG_BYTES, getattr(client, "maximum", LOG_BYTES + 1) - 1)
                    ),
                )
            lines = page["text"].splitlines()
            errors = [line[:300] for line in lines if re.search(r"error|exception|failed|fatal", line, re.I)]
            evidence["excerpt"] = "\n".join(errors[-6:])
        except (InfraError, httpx.HTTPError, ValueError):
            pass
        item["failure_evidence"] = evidence
    return item


def status(client, job, queue_id=None, build=None):
    if (queue_id is None) == (build is None):
        raise InfraError("invalid_argument", "Specify exactly one of queue_id and build")
    if build is not None:
        return _build_status(client, job, _positive(build, "build"))
    _positive(queue_id, "queue_id")
    response = client.request(
        "GET",
        f"/queue/item/{queue_id}/api/json",
        accepted=(200, 404),
        params={"tree": "task[fullName,url],cancelled,why,executable[number]"},
    )
    item = {"job": job, "queue_id": queue_id}
    if response.status_code == 404:
        rows = _builds(client, job, 100, "number,queueId")
        match = next((row for row in rows if row.get("queueId") == queue_id), None)
        number = match["number"] if match else None
        if number is None:
            return {**item, "state": "unknown"}
    else:
        row = response.json()
        if not _job_matches(client, job, row.get("task")):
            raise InfraError("invalid_argument", "Queue item does not belong to the selected job")
        if row.get("cancelled"):
            return {**item, "state": "cancelled"}
        number = (row.get("executable") or {}).get("number")
        if number is None:
            why = row.get("why")
            return {
                **item,
                "state": "queued",
                "reason": client.redact(why)[:300] if isinstance(why, str) else None,
            }
    result = _build_status(client, job, _positive(number, "build"))
    if result.get("queue_id") != queue_id:
        raise InfraError("invalid_argument", "Build does not match the requested queue item")
    return result


def cancel(client, job, queue_id=None, build=None):
    item = status(client, job, queue_id=queue_id, build=build)
    if item["state"] == "queued":
        client.request("POST", "/queue/cancelItem", params={"id": queue_id}, accepted=(200, 204, 302))
    elif item["state"] == "running":
        client.request("POST", client.job_path(job) + f"/{item['build']}/stop", accepted=(200, 204, 302))
    else:
        return item
    return {**item, "state": "cancellation_requested"}


def _has_marker(row, marker, parameter_value, account):
    users = {c.get("userId") for a in row.get("actions", []) for c in a.get("causes", []) if c.get("userId")}
    if account and users and account not in users:
        return False
    for action in row.get("actions", []):
        if parameter_value and any(
            p.get("name") in REQUEST_PARAMETERS and p.get("value") == parameter_value
            for p in action.get("parameters", [])
        ):
            return True
        for cause in action.get("causes", []):
            if cause.get("note") == marker or str(cause.get("shortDescription", "")).endswith(
                " with note: " + marker
            ):
                return True
    return False


def _reconcile(client, job, marker, parameter_value):
    account = getattr(client, "username", None)
    tree = f"items[id,task[fullName,url],{CAUSES}]"
    items = client.json("/queue/api/json", params={"tree": tree}).get("items", [])
    matches = [
        i
        for i in items
        if _job_matches(client, job, i.get("task")) and _has_marker(i, marker, parameter_value, account)
    ]
    if len(matches) == 1:
        return _positive(matches[0].get("id"), "queue_id"), None
    if not matches:
        rows = _builds(client, job, 100, "number,queueId," + CAUSES)
        matches = [r for r in rows if _has_marker(r, marker, parameter_value, account)]
        if len(matches) == 1:
            return matches[0].get("queueId"), _positive(matches[0].get("number"), "build")
    return None, None


def _marker(client, job, request_id):
    client.job_path(job)
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", request_id):
        raise InfraError("invalid_argument", "Invalid request_id")
    identity = json.dumps([client.base_url.rstrip("/"), job, request_id])
    return "infra-mcp-" + hashlib.sha256(identity.encode()).hexdigest()


def _database(state_dir):
    directory = Path(state_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    owner = os.geteuid()
    # SQLite creates its journal beside this file. Other users must not be able to replace either.
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != owner or info.st_mode & 0o022:
        raise InfraError("invalid_config", "Jenkins request state requires an owner-controlled directory")
    path = directory / "jenkins-requests.sqlite3"
    try:
        fd = os.open(path, os.O_NOFOLLOW | os.O_CREAT | os.O_RDWR, 0o600)
    except OSError:
        raise InfraError("invalid_config", "Cannot open private Jenkins request state") from None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != owner or info.st_nlink != 1:
            raise InfraError("invalid_config", "Unsafe Jenkins request state file")
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY, digest TEXT NOT NULL, use_parameter INTEGER NOT NULL,
        queue_id INTEGER, build INTEGER, rejection INTEGER
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS intents (
        id TEXT PRIMARY KEY, digest TEXT NOT NULL, parameters TEXT NOT NULL, parameterized INTEGER NOT NULL
    )""")
    return db


def _receipt(db, client, job, request_id, marker):
    row = db.execute("SELECT * FROM requests WHERE id=?", (marker,)).fetchone()
    item = {"job": job, "request_id": request_id}
    if not row:
        return {**item, "state": "unknown"}
    if row["rejection"]:
        return {**item, "state": "rejected", "http_status": row["rejection"]}
    queue_id, build = row["queue_id"], row["build"]
    if not (queue_id or build):
        try:
            queue_id, build = _reconcile(client, job, marker, request_id if row["use_parameter"] else None)
        except (InfraError, httpx.HTTPError, ValueError):
            pass
        if queue_id or build:
            with db:
                db.execute("UPDATE requests SET queue_id=?,build=? WHERE id=?", (queue_id, build, marker))
    return {
        **item,
        "queue_id": queue_id,
        "build": build,
        "state": "located" if build else "queued" if queue_id else "submission_unknown",
    }


def lookup(client, job, request_id, state_dir):
    marker = _marker(client, job, request_id)
    with closing(_database(state_dir)) as db:
        return _receipt(db, client, job, request_id, marker)


def submit_intent(client, job, request_id, state_dir, intent, resolve):
    marker = _marker(client, job, request_id)
    digest = hashlib.sha256(json.dumps(intent, sort_keys=True).encode()).hexdigest()
    with closing(_database(state_dir)) as db:
        row = db.execute("SELECT * FROM intents WHERE id=?", (marker,)).fetchone()
        if row is None:
            # Resolve without holding a write lock across Jenkins reads. The first writer pins
            # its chosen deployment for all concurrent callers and all later retries.
            parameters, parameterized = resolve()
            with db:
                db.execute(
                    "INSERT OR IGNORE INTO intents VALUES (?,?,?,?)",
                    (marker, digest, json.dumps(parameters, sort_keys=True), parameterized),
                )
            row = db.execute("SELECT * FROM intents WHERE id=?", (marker,)).fetchone()
        if row["digest"] != digest:
            raise InfraError("conflict", "request_id already belongs to a different intent")
    return submit(
        client,
        job,
        json.loads(row["parameters"]),
        request_id,
        state_dir,
        parameterized=bool(row["parameterized"]),
    )


def submit(client, job, parameters, request_id, state_dir, parameterized=None):
    marker = _marker(client, job, request_id)
    use_parameter = bool(REQUEST_PARAMETERS.intersection(parameters))
    if any(parameters[name] != request_id for name in REQUEST_PARAMETERS.intersection(parameters)):
        raise InfraError("invalid_argument", "Request ID parameters must match request_id")
    if parameterized is None:
        parameterized = bool(parameters)
    digest = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
    with closing(_database(state_dir)) as db:
        # Commit the intent before sending. A crash at any subsequent point cannot replay a POST.
        with db:
            new = db.execute(
                "INSERT OR IGNORE INTO requests(id,digest,use_parameter) VALUES (?,?,?)",
                (marker, digest, use_parameter),
            ).rowcount
        saved = db.execute("SELECT digest FROM requests WHERE id=?", (marker,)).fetchone()
        if saved["digest"] != digest:
            raise InfraError("conflict", "request_id already belongs to a different parameter set")
        if new:
            endpoint = "/buildWithParameters" if parameterized else "/build"
            rejected = (400, 401, 403, 404, 405, 409, 422, 429)
            try:
                response = client.request(
                    "POST",
                    client.job_path(job) + endpoint,
                    data=parameters,
                    params={"cause": marker},
                    accepted=(201, 202, *rejected),
                )
            except (InfraError, httpx.HTTPError):
                response = None
            if response is not None:
                with db:
                    if response.status_code in rejected:
                        db.execute(
                            "UPDATE requests SET rejection=? WHERE id=?", (response.status_code, marker)
                        )
                    else:
                        location = urlsplit(response.headers.get("Location", ""))
                        controller = urlsplit(client.base_url.rstrip("/"))
                        pattern = re.escape(controller.path) + r"/queue/item/([1-9][0-9]{0,17})/?"
                        match = re.fullmatch(pattern, location.path)
                        if match and (not location.netloc or location.netloc == controller.netloc):
                            db.execute("UPDATE requests SET queue_id=? WHERE id=?", (int(match[1]), marker))
        return _receipt(db, client, job, request_id, marker)
