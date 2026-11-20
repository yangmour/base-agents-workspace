"""Structured configuration management for Git-backed Jenkins Pipeline jobs."""
from __future__ import annotations

import difflib
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import uuid
import xml.etree.ElementTree as ET
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .base import Operation, SENSITIVE
from .config import InfraError


JOB = {"job": "Full folder-qualified job name"}
CONFIG = {"config": "Structured Git SCM patch: type=multibranch on creation for Git branch sources; branch is a wildcard include filter there. Fields: repository, branch, jenkinsfile, credentials_id, parameters (list of string, boolean or choice definitions)"}
EXPECTED = {"expected_version": "Version returned by read or preview; use absent for creation"}
SNAPSHOT = {"snapshot_id": "Deletion snapshot from this job's history"}
JOB_OPERATIONS = {
    "get_job_config": Operation("read", "Read SCM configuration and version", JOB),
    "preview_job_config": Operation("read", "Preview a redacted configuration change",
                                    JOB | {"mode": "create, update, delete, or restore"} | CONFIG | SNAPSHOT),
    "create_job": Operation("create", "Create SCM Pipeline job", JOB | EXPECTED | CONFIG),
    "update_job": Operation("update", "Patch supported fields of SCM Pipeline job", JOB | EXPECTED | CONFIG),
    "delete_job": Operation("delete", "Snapshot configuration and delete job (including builds)", JOB | EXPECTED),
    "restore_job": Operation("create", "Recreate job configuration from deletion snapshot", JOB | EXPECTED | SNAPSHOT),
    "list_job_history": Operation("read", "Return latest 100 configuration audit entries", JOB),
}

CPS = "org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition"
MB = "org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject"
BINDER = "org.jenkinsci.plugins.workflow.multibranch.SCMBinder"
FACTORY = "org.jenkinsci.plugins.workflow.multibranch.WorkflowBranchProjectFactory"
SOURCE = "jenkins.plugins.git.GitSCMSource"
FILTER = "jenkins.scm.impl.trait.WildcardSCMHeadFilterTrait"
GIT = "hudson.plugins.git.GitSCM"
REMOTE = "hudson.plugins.git.UserRemoteConfig"
BRANCH = "hudson.plugins.git.BranchSpec"
PARAMETERS = "hudson.model.ParametersDefinitionProperty"
TYPES = {"string": "hudson.model.StringParameterDefinition", "boolean": "hudson.model.BooleanParameterDefinition",
         "choice": "hudson.model.ChoiceParameterDefinition"}
NAMES = {v: k for k, v in TYPES.items()}
FIELDS = {"repository", "branch", "jenkinsfile", "credentials_id", "parameters"}


def invalid(message):
    raise InfraError("invalid_argument", message)


def child(node, tag):
    found = node.findall(tag)
    if len(found) > 1:
        raise InfraError("unsupported_job", "Ambiguous Jenkins XML structure")
    return found[0] if found else ET.SubElement(node, tag)


def string(value, name, limit=1024):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        invalid(f"Invalid {name}")
    return value


def repository(value):
    value = string(value, "repository", 2048)
    try:
        url = urlsplit(value)
        port = url.port
        host = url.hostname
    except ValueError:
        invalid("Invalid Git repository URL")
    if (url.scheme not in {"https", "ssh"} or not host or url.password is not None
            or url.username is not None and (url.scheme != "ssh" or url.username != "git")
            or not re.fullmatch(r"[A-Za-z0-9.-]+", host) or url.query or url.fragment
            or not re.fullmatch(r"/[a-zA-Z0-9._/~+-]+", url.path)
            or any(part in {"", ".", ".."} for part in url.path[1:].split("/"))):
        invalid("Use an HTTPS or SSH Git repository URL without embedded secrets")
    authority = ("git@" if url.username else "") + host
    if port is not None:
        authority += f":{port}"
    return urlunsplit((url.scheme, authority, url.path, "", ""))


def parameter_nodes(root):
    return root.findall(f"properties/{PARAMETERS}/parameterDefinitions/*")


def parse_xml(raw):
    try:
        source = raw.decode("utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", source, re.I) or "\x00" in source:
            raise ValueError
        root = ET.fromstring(source, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True)))
    except (UnicodeError, ValueError, ET.ParseError):
        raise InfraError("unsupported_job", "Invalid or unsupported job XML") from None
    if root.tag == MB or branch_child(root):
        return root
    definitions = root.findall("definition")
    if (root.tag != "flow-definition" or len(definitions) != 1 or definitions[0].get("class") != CPS
            or len(definitions[0].findall("scm")) != 1 or definitions[0].find("scm").get("class") != GIT):
        raise InfraError("unsupported_job", "Requires a Git SCM Pipeline job")
    return root


def branch_child(root):
    if root.tag != "flow-definition":
        return False
    return (root.find(f"definition[@class='{BINDER}']") is not None
            or root.find("properties/org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty") is not None)


def multibranch_scaffold():
    root = ET.Element(MB)
    sources = ET.SubElement(root, "sources", {"class": "jenkins.branch.MultiBranchProject$BranchSourceList"})
    entry = ET.SubElement(ET.SubElement(sources, "data"), "jenkins.branch.BranchSource")
    source = ET.SubElement(entry, "source", {"class": SOURCE})
    ET.SubElement(source, "id").text = str(uuid.uuid4())
    ET.SubElement(ET.SubElement(source, "traits"), "jenkins.plugins.git.traits.BranchDiscoveryTrait")
    ET.SubElement(sources, "owner", {"class": MB, "reference": "../.."})
    factory = ET.SubElement(root, "factory", {"class": FACTORY})
    ET.SubElement(factory, "owner", {"class": MB, "reference": "../.."})
    return root


def multibranch_fields(root):
    entries = root.findall("sources/data/*")
    factories = root.findall("factory")
    if (len(entries) != 1 or entries[0].tag != "jenkins.branch.BranchSource"
            or len(entries[0].findall("source")) != 1 or entries[0].find("source").get("class") != SOURCE
            or len(factories) != 1 or factories[0].get("class") != FACTORY):
        raise InfraError("unsupported_job", "Requires a single Git branch source and Workflow branch project factory")
    return entries[0].find("source"), factories[0]


def scaffold():
    root = ET.Element("flow-definition")
    ET.SubElement(root, "actions")
    ET.SubElement(root, "properties")
    definition = ET.SubElement(root, "definition", {"class": CPS})
    scm = ET.SubElement(definition, "scm", {"class": GIT})
    ET.SubElement(scm, "configVersion").text = "2"
    for parent, item in [("userRemoteConfigs", REMOTE), ("branches", BRANCH)]:
        ET.SubElement(ET.SubElement(scm, parent), item)
    ET.SubElement(scm, "extensions")
    ET.SubElement(definition, "lightweight").text = "true"
    return root


def single_scm(root):
    scm = root.find("definition/scm")
    remotes = scm.findall("userRemoteConfigs/*")
    branches = scm.findall("branches/*")
    if len(remotes) != 1 or remotes[0].tag != REMOTE or len(branches) != 1 or branches[0].tag != BRANCH:
        raise InfraError("unsupported_job", "Requires exactly one Git remote and branch specification")
    return remotes[0], branches[0]


def safe_repository(value, redact):
    try:
        return redact(repository(value))
    except InfraError:
        return "[UNSUPPORTED OR REDACTED URL]"


def summary(root, redact):
    if branch_child(root):
        branch = root.findtext("properties/org.jenkinsci.plugins.workflow.multibranch.BranchJobProperty/branch/head/name")
        return {"type": "branch_child", "branch": redact(branch) if branch else None,
                "jenkinsfile": redact(root.findtext("definition/scriptPath", "Jenkinsfile")),
                "parameter_source": "Jenkinsfile"}
    if root.tag == MB:
        source, factory = multibranch_fields(root)
        return {"type": "multibranch", "repository": safe_repository(source.findtext("remote"), redact),
                "branch": redact(source.findtext(f"traits/{FILTER}/includes", "*")),
                "branch_excludes": redact(source.findtext(f"traits/{FILTER}/excludes", "")),
                "credentials_id": redact(source.findtext("credentialsId", "")),
                "jenkinsfile": redact(factory.findtext("scriptPath", "Jenkinsfile")), "parameter_source": "Jenkinsfile"}
    remote, branch = single_scm(root)
    repo = safe_repository(remote.findtext("url"), redact)
    params = []
    for param in parameter_nodes(root):
        if not isinstance(param.tag, str):
            continue
        name = param.findtext("name", "")
        kind = NAMES.get(param.tag, "unmanaged")
        item = {"name": redact(name), "type": kind}
        if kind != "unmanaged":
            if SENSITIVE.search(name):
                item["default"] = "[REDACTED]"
            elif kind == "choice":
                item["choices"] = [redact(v.text or "") for v in param.findall("choices/a/string")]
            else:
                default = param.findtext("defaultValue", "")
                item["default"] = default.lower() == "true" if kind == "boolean" else redact(default)
        params.append(item)
    return {"repository": repo, "branch": redact(branch.findtext("name", "")),
            "jenkinsfile": redact(root.findtext("definition/scriptPath", "Jenkinsfile")),
            "credentials_id": redact(remote.findtext("credentialsId", "")), "parameters": params}


def set_parameters(root, params):
    if not isinstance(params, list) or len(params) > 128:
        invalid("parameters must be a list of up to 128 definitions")
    definitions = child(child(child(root, "properties"), PARAMETERS), "parameterDefinitions")
    existing = {p.findtext("name"): p for p in definitions if isinstance(p.tag, str)}
    if len(existing) != sum(isinstance(p.tag, str) for p in definitions):
        invalid("Existing parameter names are ambiguous")
    seen = set()
    for item in params:
        if not isinstance(item, dict):
            invalid("Invalid parameter definition")
        name = string(item.get("name"), "parameter name", 128)
        kind = item.get("type")
        if (not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or name in seen or kind not in TYPES
                or set(item) - {"name", "type", "choices" if kind == "choice" else "default"}):
            invalid("Unsupported or duplicate parameter definition")
        seen.add(name)
        if SENSITIVE.search(name):
            invalid("Sensitive build parameters must use Jenkins credential references")
        old = existing.get(name)
        if old is not None and old.tag != TYPES[kind]:
            invalid("Changing an existing parameter type is unsupported")
        node = ET.SubElement(definitions, TYPES[kind]) if old is None else old
        child(node, "name").text = name
        if kind == "choice":
            values = item.get("choices")
            if not isinstance(values, list) or not 1 <= len(values) <= 128:
                invalid("choice requires a non-empty list of up to 128 choices")
            options = child(node, "choices")
            options.set("class", "java.util.Arrays$ArrayList")
            array = child(options, "a")
            array.set("class", "string-array")
            for choice in array.findall("string"):
                array.remove(choice)
            for value in values:
                ET.SubElement(array, "string").text = string(value, "choice")
        elif kind == "boolean":
            default = item.get("default", False)
            if type(default) is not bool:
                invalid("Boolean default must be true or false")
            child(node, "defaultValue").text = str(default).lower()
        else:
            default = item.get("default", "")
            child(node, "defaultValue").text = "" if default == "" else string(default, "parameter default")
    for name, node in existing.items():
        if node.tag in NAMES and name not in seen:
            definitions.remove(node)


def apply(raw, config):
    if not isinstance(config, dict) or not config or set(config) - (FIELDS | {"type"}):
        invalid("Provide a nonempty structured SCM configuration")
    if "type" in config and (raw is not None or config["type"] not in ("multibranch", "pipeline")):
        invalid("Job type is available only on creation: pipeline or multibranch")
    if raw is None and "repository" not in config:
        invalid("repository is required to create a job")
    if raw is None:
        root = multibranch_scaffold() if config.get("type") == "multibranch" else scaffold()
        config = {"branch": "*" if root.tag == MB else "*/main", "jenkinsfile": "Jenkinsfile"} | config
    else:
        root = parse_xml(raw)
    if root.tag == MB:
        remote, script_owner = multibranch_fields(root)
        if "parameters" in config:
            invalid("Multibranch build parameters are defined in the Jenkinsfile")
        if "repository" in config:
            child(remote, "remote").text = repository(config["repository"])
        if "branch" in config:
            value = string(config["branch"], "branch includes", 512)
            parts = value.split(" ")
            if len(parts) > 32 or any(not re.fullmatch(r"[a-zA-Z0-9_.*-][a-zA-Z0-9_./*-]*", p)
                                      or ".." in p or "//" in p for p in parts):
                invalid("Invalid wildcard branch include filter")
            rule = child(child(remote, "traits"), FILTER)
            child(rule, "includes").text = value
            child(rule, "excludes")
    else:
        remote, branch = single_scm(root)
        script_owner = root.find("definition")
        if "repository" in config:
            child(remote, "url").text = repository(config["repository"])
        if "branch" in config:
            value = string(config["branch"], "branch", 255)
            if not re.fullmatch(r"(?:\*/)?[A-Za-z0-9_][A-Za-z0-9_./-]*", value) or ".." in value or "//" in value:
                invalid("Invalid Git branch specification")
            child(branch, "name").text = value
    if "jenkinsfile" in config:
        value = string(config["jenkinsfile"], "jenkinsfile", 512)
        if not re.fullmatch(r"[a-zA-Z0-9_./-]+", value) or any(p in {"", ".", ".."} for p in value.split("/")):
            invalid("Invalid repository-relative Jenkinsfile path")
        child(script_owner, "scriptPath").text = value
    if "credentials_id" in config:
        value = config["credentials_id"]
        if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9._-]{0,128}", value):
            invalid("Invalid credentials reference")
        child(remote, "credentialsId").text = value
    if "parameters" in config:
        set_parameters(root, config["parameters"])
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@contextmanager
def journal(directory):
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_uid != os.getuid():
        raise InfraError("invalid_config", "Job journal requires a private local state directory")
    directory.chmod(0o700)
    path = directory / "job-history.sqlite3"
    fd = os.open(directory / "job-history.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        db_fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(db_fd, 0o600)
        finally:
            os.close(db_fd)
        with closing(sqlite3.connect(path)) as db:
            db.row_factory = sqlite3.Row
            db.execute("""CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, instance TEXT NOT NULL, job TEXT NOT NULL, operation TEXT NOT NULL,
                time TEXT NOT NULL, account TEXT NOT NULL, previous_version TEXT NOT NULL,
                status TEXT NOT NULL, snapshot BLOB, caller_id TEXT)""")
            yield db
    finally:
        os.close(fd)


def get_raw(client, path):
    response = client.request("GET", path + "/config.xml", accepted=(200, 404))
    return None if response.status_code == 404 else response.content


def version(raw):
    return "absent" if raw is None else hashlib.sha256(raw).hexdigest()


def display(client, raw):
    return summary(parse_xml(raw), client.redact) if raw is not None else {}


def change(client, profile, operation, args, db):
    job = args["job"]
    instance = json.dumps([profile.name, str(client.base_url)])
    if operation == "list_job_history":
        rows = db.execute("""SELECT id AS event_id, job, operation, time, account AS jenkins_account,
            previous_version, status, caller_id, CASE WHEN snapshot IS NOT NULL THEN id END AS snapshot_id FROM events
            WHERE instance=? AND job=? ORDER BY rowid DESC LIMIT 100""", (instance, job))
        return {"events": [dict(row) for row in rows]}
    path = client.job_path(job)
    raw = get_raw(client, path)
    before = version(raw)
    if operation == "get_job_config":
        if raw is None:
            raise InfraError("not_found", "Job does not exist")
        config = display(client, raw)
        if config.get("type") == "branch_child":
            config["managed_by"] = job.rpartition("/")[0]
        return {"job": job, "version": before, "config": config}
    preview = operation == "preview_job_config"
    mode = args.get("mode") if preview else operation.removesuffix("_job")
    if mode not in {"create", "update", "delete", "restore"}:
        invalid("Invalid configuration change mode")
    if not preview and args.get("expected_version") != before:
        raise InfraError("version_conflict", "Job configuration changed; read or preview it again")
    if (mode in {"create", "restore"}) != (raw is None):
        raise InfraError("version_conflict", "Job existence conflicts with the requested operation")
    old_config = display(client, raw)
    if old_config.get("type") == "branch_child":
        raise InfraError("managed_job", "Configure the parent multibranch job; build parameters belong in its Jenkinsfile")
    updated = None
    if mode in {"update", "create"}:
        updated = apply(raw, args.get("config"))
    elif mode == "restore":
        key = string(args.get("snapshot_id"), "snapshot_id", 64)
        row = db.execute("SELECT snapshot FROM events WHERE instance=? AND job=? AND id=? AND snapshot IS NOT NULL",
                         (instance, job, key)).fetchone()
        if row is None:
            raise InfraError("not_found", "No matching job snapshot")
        updated = row["snapshot"]
    new_config = display(client, updated)
    if preview:
        def lines(data):
            return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False).splitlines()
        diff = list(difflib.unified_diff(lines(old_config), lines(new_config), fromfile="current", tofile="proposed", lineterm=""))
        return {"job": job, "mode": mode, "expected_version": before, "diff": diff}
    account = client.json("/whoAmI/api/json")
    name = account.get("name") if isinstance(account, dict) else None
    if not isinstance(name, str) or not name or account.get("anonymous") or account.get("authenticated") is False:
        raise InfraError("unauthenticated", "Cannot verify the Jenkins account for configuration audit")
    event = uuid.uuid4().hex
    caller = profile.options.get("caller_id")
    if caller is not None:
        caller = client.redact(string(caller, "configured caller_id", 256))
    db.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
               (event, instance, job, mode, datetime.now(timezone.utc).isoformat(), client.redact(name),
                before, "pending", raw if mode == "delete" else None, caller))
    db.commit()
    # Jenkins does not offer compare-and-swap for config.xml. Recheck directly before writing.
    try:
        if version(get_raw(client, path)) != before:
            raise InfraError("version_conflict", "Job configuration changed; read or preview it again")
        if mode in {"create", "restore"}:
            parent, _, short = job.rpartition("/")
            prefix = client.job_path(parent) if parent else ""
            client.request("POST", prefix + "/createItem", params={"name": short}, content=updated,
                           headers={"Content-Type": "application/xml"}, accepted=(200, 201))
        elif mode == "update":
            client.request("POST", path + "/config.xml", content=updated, headers={"Content-Type": "application/xml"})
        else:
            client.request("POST", path + "/doDelete", accepted=(200, 302, 303))
            if get_raw(client, path) is not None:
                raise InfraError("outcome_unknown", "Jenkins still returns the job after deletion")
    except Exception as error:
        status = "version_conflict" if isinstance(error, InfraError) and error.code == "version_conflict" else "outcome_unknown"
        db.execute("UPDATE events SET status=? WHERE id=?", (status, event))
        db.commit()
        raise
    db.execute("UPDATE events SET status='accepted' WHERE id=?", (event,))
    db.commit()
    result = {"job": job, "operation": mode, "status": "accepted", "event_id": event, "jenkins_account": client.redact(name)}
    if mode == "delete":
        result["snapshot_id"] = event
    return result


def handle_job(client, profile, operation, args, state_dir):
    if operation not in JOB_OPERATIONS:
        invalid("Unknown job configuration operation")
    with journal(state_dir) as db:
        return change(client, profile, operation, args, db)
