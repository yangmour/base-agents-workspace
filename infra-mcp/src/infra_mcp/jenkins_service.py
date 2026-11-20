"""Jenkins release catalog and operations on explicitly mapped deployment targets."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from . import jenkins_builds as builds
from .base import BaseService, Operation
from .config import InfraError, integer, validate_name
from .jenkins_client import JenkinsClient
from .jenkins_jobs import JOB_OPERATIONS, handle_job, parse_xml, summary
from .kubernetes_service import KubernetesService


JOB = {"job": "Full release Job path (including folders)"}
SELECT = {**JOB, "environment": "Optional exact environment", "service": "Optional exact service"}
RUN = {**SELECT, "kind": "deploy (default) or rollback", "build": "Build number or use queue_id",
       "queue_id": "Exact queue item id"}
BRANCH = {"branch": "Business branch; must match the fixed branch or a configured branch parameter"}
PIN = {"commit": "Optional full business commit SHA; requires a configured assertion parameter"}
ROLLBACK = {"source_build": "Exact successful build; omit to select the previous verified version",
            "source_kind": "deploy (default) or rollback for an explicit source_build"}
IDENTITY = ("environment", "service", "cluster", "namespace", "deployment")
REQUEST = {"request_id": "Stable unique ID for this submission; reuse for retries"}
STRING_TYPES = {"StringParameterDefinition", "ChoiceParameterDefinition", "TextParameterDefinition"}
META_TREE = ("fullName,_class,buildable,lastBuild[number],property[parameterDefinitions"
             "[name,type,choices]]")


def failure(message):
    raise InfraError("invalid_argument", message)


def capability(profile, name):
    grants = profile.options.get("capabilities", [])
    if not isinstance(grants, list) or name not in grants:
        raise InfraError("permission_denied", f"Connection does not grant Jenkins {name} capability")


def mapped_targets(profile):
    targets = profile.options.get("targets", {})
    if not isinstance(targets, dict):
        raise InfraError("invalid_config", "Jenkins targets must map complete Job paths to deployments")
    reserved = set(targets)
    rows = []
    for job, target in targets.items():
        JenkinsClient.job_path(job)
        if not isinstance(target, dict) or not all(isinstance(target.get(k), str) and target[k] for k in IDENTITY):
            raise InfraError("invalid_config", "Each Jenkins target needs environment, service, cluster, namespace and deployment")
        rollback = target.get("rollback_job")
        if rollback:
            JenkinsClient.job_path(rollback)
            if rollback in reserved:
                raise InfraError("invalid_config", "Use a separate rollback Job per deployment target")
            reserved.add(rollback)
        try:
            profile.check_scope("jobs", job)
        except InfraError as error:
            if error.code == "scope_denied":
                continue
            raise
        rows.append({**target, "job": job})
    return rows


def select_target(profile, args):
    if "job" in args:
        profile.check_scope("jobs", args["job"])
    keys = ("job", "environment", "service")
    if not any(k in args for k in keys):
        failure("Specify a job, environment or service")
    candidates = [x for x in mapped_targets(profile) if all(x[k] == args[k] for k in keys if k in args)]
    if len(candidates) > 1 and "branch" in args:
        candidates = [t for t in candidates if t.get("branch") == args["branch"] or t.get("branch_parameter")]
    if len(candidates) != 1:
        names = ", ".join(x["job"] for x in candidates[:15])
        failure(f"Select one mapped pipeline; matching Jobs: {names or '(none)'}")
    return candidates[0]


def job_for(profile, target, kind):
    if kind not in {"deploy", "rollback"}:
        failure("kind must be deploy or rollback")
    job = target.get("rollback_job" if kind == "rollback" else "job")
    if not job:
        failure("No rollback Job mapped for this target")
    profile.check_scope("jobs", job)
    return job


def public_target(profile, target):
    result = {k: target.get(k) for k in (*IDENTITY, "job", "branch", "script_branch", "branch_parameter", "rollback_job")}
    rollback = result.get("rollback_job")
    if rollback:
        try:
            profile.check_scope("jobs", rollback)
        except InfraError as error:
            if error.code != "scope_denied":
                raise
            result.pop("rollback_job")
    result["metadata_source"] = "profile"
    return result


def folder_visible(profile, folder):
    """A scoped reader can traverse ancestors of permitted Job paths."""
    if not folder:
        return True
    JenkinsClient.job_path(folder)
    try:
        profile.check_scope("jobs", folder)
        return True
    except InfraError as error:
        if error.code != "scope_denied":
            raise
    return (any(t["job"].startswith(folder + "/") for t in mapped_targets(profile))
            or any(pattern.startswith(folder + "/") for pattern in profile.scope.get("jobs", [])))


def metadata(client, job):
    return client.json(client.job_path(job) + "/api/json", params={"tree": META_TREE})


def definitions(meta):
    return {p["name"]: p for prop in meta.get("property", [])
            for p in prop.get("parameterDefinitions", []) if isinstance(p.get("name"), str)}


def validate_parameters(meta, params):
    if meta.get("buildable") is not True or meta.get("_class") != "org.jenkinsci.plugins.workflow.job.WorkflowJob":
        failure("Selected job must be a buildable Jenkins Pipeline")
    declared = definitions(meta)
    for key, value in params.items():
        param = declared.get(key, {})
        if param.get("type") not in STRING_TYPES or not isinstance(value, str):
            failure(f"String or choice parameter not declared by Jenkins: {key}")
        if param.get("type") == "ChoiceParameterDefinition" and value not in param.get("choices", []):
            failure(f"Value is outside the declared choices for {key}")


def deployment_parameters(target, args):
    branch = args.get("branch", target.get("branch"))
    if branch is None:
        failure("A known business branch is required for deployment")
    validate_name(branch, "branch")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_./-]{0,249}", branch) or ".." in branch or "//" in branch:
        failure("Invalid business branch")
    key = target.get("branch_parameter")
    if not key and branch != target.get("branch"):
        failure("Requested branch differs from the fixed business branch")
    params = {key: branch} if key else {}
    if "commit" in args:
        pin = target.get("commit_parameter")
        value = args["commit"]
        if not pin or not isinstance(value, str) or not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", value):
            failure("A commit pin requires a supported commit parameter and a full SHA")
        params[pin] = value.lower()
    return branch, params


def verified(target, item):
    record = item.get("release") or {}
    return (item.get("result") == "SUCCESS" and record.get("ready") is True
            and all(record.get(k) == target[k] for k in IDENTITY)
            and type(record.get("revision")) is int and record["revision"] > 0
            and bool(record.get("image")) and re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", record.get("commit") or ""))


def records(client, profile, target, limit):
    result = []
    for kind in ("deploy", "rollback"):
        if kind == "rollback" and not target.get("rollback_job"):
            continue
        try:
            job = job_for(profile, target, kind)
        except InfraError as error:
            if error.code == "scope_denied":
                continue
            raise
        for item in builds.history(client, job, limit):
            result.append({**item, "job": job, "kind": kind,
                           "verified": bool(verified(target, item)),
                           "image_availability": "unverified"})
    # Jenkins start time can precede the time a queued deployment acquired its target lock.
    return sorted(result, key=record_time, reverse=True)[:limit]


def record_time(item):
    value = (item.get("release") or {}).get("observed_at")
    if isinstance(value, str):
        try:
            observed = datetime.fromisoformat(value)
            if observed.tzinfo:
                return observed.timestamp()
        except ValueError:
            pass
    return item.get("timestamp", 0) / 1000


def last_observed(items):
    latest = next((item for item in items if item["verified"]), None)
    if latest:
        return {"source": "last_verified_deployment", "job": latest["job"], "build": latest["build"],
                "release": latest["release"]}
    return {"source": "unknown", "release": None}


def live_version(obj, container):
    meta, spec, status = obj["metadata"], obj["spec"], obj.get("status", {})
    template = spec["template"]
    image = next((c["image"] for c in template["spec"]["containers"] if c["name"] == container), None)
    if not image:
        raise InfraError("observation_failed", "Configured deployment container was not found")
    desired = spec.get("replicas", 1)
    ready = (desired > 0 and type(meta.get("generation")) is int and
             status.get("observedGeneration", -1) >= meta["generation"] and
             all(status.get(k, 0) == desired for k in ("updatedReplicas", "replicas", "availableReplicas", "readyReplicas")))
    revision = meta.get("annotations", {}).get("deployment.kubernetes.io/revision", "")
    annotations = template.get("metadata", {}).get("annotations", {})
    build = annotations.get("infra.xiwen.io/build", "")
    return {"source": "kubernetes", "release": {"revision": int(revision) if revision.isdigit() else None,
            "image": image, "commit": annotations.get("infra.xiwen.io/commit"), "ready": ready,
            "source_build": int(build) if build.isdigit() else None,
            "observed_at": datetime.now(UTC).isoformat()}}


class JenkinsService(BaseService):
    service = "jenkins"
    operations = {
        "check_connection": Operation("read", "Check controller connectivity"),
        "discover_jobs": Operation("read", "List accessible immediate children of a Jenkins folder", {"folder": "Full folder path, omit for root"}),
        "list_pipelines": Operation("read", "Select configured pipelines by exact metadata", {**SELECT, **BRANCH}),
        "describe_pipeline": Operation("read", "Show configured target and parameters reported by Jenkins", SELECT),
        "release_history": Operation("read", "Recent deploy and rollback builds with publication evidence", {**SELECT, "limit": "1..100 (default 20)"}),
        "current_version": Operation("read", "Read current workload or last verified deployment", SELECT),
        "preview_deploy": Operation("read", "Resolve exact release target, branch, parameters and current version", {**SELECT, **BRANCH, **PIN}),
        "deploy": Operation("create", "Submit the selected release Job", {**SELECT, **BRANCH, **PIN, **REQUEST}, ("read",)),
        "preview_rollback": Operation("read", "Resolve previous or explicit verified release", {**SELECT, **ROLLBACK}),
        "rollback": Operation("create", "Submit dedicated rollback Job using verified release evidence", {**SELECT, **ROLLBACK, **REQUEST}, ("read",)),
        "request_status": Operation("read", "Look up persisted submission by request_id", {**SELECT, "kind": RUN["kind"], **REQUEST}),
        "build_status": Operation("read", "Resolve this queue item or build and show rollout evidence", RUN),
        "build_log": Operation("read", "Read bounded progressive log", {**SELECT, "kind": RUN["kind"], "build": "Build number", "start": "Byte offset (default 0)"}),
        "cancel_build": Operation("update", "Cancel queued item or stop exact build and report deployment observation", RUN, ("read",)),
        **JOB_OPERATIONS,
    }

    def connection_metadata(self, profile):
        return {**super().connection_metadata(profile), "capabilities": profile.options.get("capabilities", [])}

    def list_operations(self):
        result = super().list_operations()
        for name, entry in result["operations"].items():
            if entry["action"] != "read":
                grant = "configure" if name in JOB_OPERATIONS else "cancel" if name == "cancel_build" else name
                entry["required_capabilities"] = [grant]
        return result

    def current(self, client, profile, target, history=None):
        observer = target.get("kubernetes_connection")
        issue = None
        if observer:
            try:
                k8s = self.config.get("kubernetes", observer)
                return KubernetesService(self.config).observe_deployment(
                    k8s, target["namespace"], target["deployment"],
                    lambda obj: live_version(obj, target.get("container", target["deployment"])))
            except InfraError as error:
                issue = error.code
        current = last_observed(history if history is not None else records(client, profile, target, 20))
        if issue:
            current["observation_error"] = issue
        return current

    def rollback_source(self, client, profile, target, args):
        if "source_build" in args:
            job = job_for(profile, target, args.get("source_kind", "deploy"))
            item = builds.status(client, job, build=args["source_build"])
            if not verified(target, item):
                failure("Selected build has no verified release for this deployment")
        else:
            item = None
            for limit in (10, 100):
                history = records(client, profile, target, limit)
                current = self.current(client, profile, target, history)
                running = current["release"] or {}
                anchor = running.get("revision")
                if type(anchor) is not int or current.get("observation_error"):
                    if len(history) == limit and limit < 100 and not current.get("observation_error"):
                        continue
                    failure("Current revision could not be verified; specify source_build")
                if current["source"] != "kubernetes" and (not history or not history[0]["verified"]):
                    failure("Recent deployment outcome is uncertain; specify source_build")
                eligible = []
                for entry in history:
                    release = entry.get("release") or {}
                    if not entry["verified"] or release["revision"] >= anchor:
                        continue
                    same_build = (running.get("source_build") and
                                  all(running.get(k) == release.get(k) for k in ("source_build", "image", "commit")))
                    if not same_build:
                        eligible.append(entry)
                item = max(eligible, key=lambda row: row["release"]["revision"], default=None)
                if item or len(history) < limit:
                    break
            if item is None:
                failure("No earlier verified revision in retained history; specify source_build")
        return item

    def after_stop(self, client, profile, target, result):
        try:
            observed = self.current(client, profile, target)
        except InfraError as error:
            observed = {"source": "unknown", "error": error.code}
        result["deployment_observation"] = observed
        if result["state"] == "cancellation_requested":
            result["follow_up"] = "Poll build_status until terminal; deployment may still change"
        elif observed["source"] == "kubernetes":
            result["follow_up"] = "Compare the observed version with the intended version before rollback"
        else:
            result["follow_up"] = "Live workload version unverified; inspect the deployment before rollback"
        return result

    def resolve_release(self, client, profile, target, args, kind, job):
        selected = {"target": public_target(profile, target), "execution_job": job}
        if kind == "rollback":
            source = self.rollback_source(client, profile, target, args)
            record = source["release"]
            params = {"TARGET_REVISION": str(record["revision"]), "TARGET_IMAGE": record["image"],
                      "TARGET_COMMIT": record["commit"], "SOURCE_BUILD": str(record.get("source_build", source["build"]))}
            if digest := record.get("digest"):
                params["TARGET_DIGEST"] = digest
            selected.update(source_build=source["build"], source_job=source["job"], release=record,
                            image_availability="pending_execution_check")
        else:
            selected["branch"], params = deployment_parameters(target, args)
            selected["target_commit"] = args.get("commit")
        meta = metadata(client, job)
        declared = definitions(meta)
        for name in ("REQUEST_ID", "INFRA_MCP_REQUEST_ID"):
            if "request_id" in args and name in declared:
                params[name] = args["request_id"]
        validate_parameters(meta, params)
        return selected, params, bool(declared)

    def execute(self, profile, operation, args):
        allowed = self.operations[operation].parameters
        if unknown := args.keys() - allowed.keys():
            failure(f"Unknown {operation} argument: {sorted(unknown)[0]}")
        client = JenkinsClient(profile)
        # Runtime files are private and scoped by connection and controller, never a caller-supplied path.
        key = hashlib.sha256(f"{profile.name}\0{client.base_url}".encode()).hexdigest()
        state = self.config.path.parent / ".jenkins-state" / key
        if operation in JOB_OPERATIONS:
            job = args.get("job")
            client.job_path(job)
            profile.check_scope("jobs", job)
            if JOB_OPERATIONS[operation].action != "read":
                capability(profile, "configure")
            return handle_job(client, profile, operation, args, state)
        if operation == "check_connection":
            client.json("/api/json", {"tree": "mode"})
            return {"connected": True}
        if operation == "discover_jobs":
            folder = args.get("folder")
            if not folder_visible(profile, folder):
                raise InfraError("scope_denied", "Folder is outside this connection's scope")
            path = client.job_path(folder) if folder else ""
            content = client.json(path + "/api/json", {"tree": "jobs[name,fullName,_class]"})
            jobs = []
            for child in content.get("jobs", []):
                full = child.get("fullName") or "/".join(filter(None, (folder, child.get("name"))))
                try:
                    client.job_path(full)
                    profile.check_scope("jobs", full)
                except InfraError:
                    child_type = child.get("_class", "")
                    if not (child_type.endswith(("Folder", "MultiBranchProject")) and folder_visible(profile, full)):
                        continue
                jobs.append({"job": full, "type": child.get("_class")})
            return {"jobs": jobs}
        if operation == "list_pipelines":
            return {"pipelines": [public_target(profile, t) for t in mapped_targets(profile)
                                   if all(t.get(k) == v for k, v in args.items())]}
        target = select_target(profile, args)
        if operation == "describe_pipeline":
            meta = metadata(client, target["job"])
            info = {**public_target(profile, target), "type": meta.get("_class"), "buildable": meta.get("buildable"),
                    "parameters": list(definitions(meta)), "last_build": meta.get("lastBuild")}
            response = client.request("GET", client.job_path(target["job"]) + "/config.xml", accepted=(200, 403, 404))
            if response.status_code == 200:
                try:
                    scm = summary(parse_xml(response.content), client.redact)
                    info["jenkinsfile"] = scm["jenkinsfile"]
                    if scm.get("repository"):
                        info["repository"] = scm["repository"]
                    if scm.get("type") == "multibranch":
                        info["branch_filter"] = scm["branch"]
                    elif scm.get("branch"):
                        info.update(script_branch=scm["branch"], script_branch_source="jenkins_config")
                except InfraError as error:
                    if error.code != "unsupported_job":
                        raise
            return info
        if operation == "release_history":
            return {"builds": records(client, profile, target, integer(args, "limit", 20, 1, 100))}
        if operation == "current_version":
            return self.current(client, profile, target)
        if operation in {"request_status", "build_status", "build_log", "cancel_build"}:
            job = job_for(profile, target, args.get("kind", "deploy"))
            if operation == "request_status":
                return builds.lookup(client, job, args.get("request_id"), state)
            if operation == "build_log":
                return builds.log(client, job, args.get("build"), args.get("start", 0))
            if operation == "cancel_build":
                capability(profile, "cancel")
                result = builds.cancel(client, job, args.get("queue_id"), args.get("build"))
                return self.after_stop(client, profile, target, result)
            result = builds.status(client, job, args.get("queue_id"), args.get("build"))
            result["deployment_readiness"] = "verified" if verified(target, result) else "unverified"
            if result["state"] in {"failure", "unstable"}:
                evidence = result.get("failure_evidence", {})
                result["failure_reason"] = evidence.get("excerpt") or "Cause unknown from available build logs"
            if result["state"] == "aborted":
                return self.after_stop(client, profile, target, result)
            return result

        rollback = operation in {"preview_rollback", "rollback"}
        kind = "rollback" if rollback else "deploy"
        preview = operation.startswith("preview_")
        if not preview:
            capability(profile, kind)
        job = job_for(profile, target, kind)
        if preview:
            selected, params, _ = self.resolve_release(client, profile, target, args, kind, job)
            return {**selected, "parameters": params, "current": self.current(client, profile, target)}
        intent = {"target": {k: target[k] for k in (*IDENTITY, "job")}, "kind": kind,
                  "selection": {k: args[k] for k in ("branch", "commit", "source_build", "source_kind") if k in args}}

        def resolve():
            _, params, parameterized = self.resolve_release(client, profile, target, args, kind, job)
            return params, parameterized

        return builds.submit_intent(client, job, args.get("request_id"), state, intent, resolve)
