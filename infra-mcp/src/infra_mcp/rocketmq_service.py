"""Scoped RocketMQ operations using the Dashboard 2.1 HTTP API."""

import re

from .base import BaseService, Operation
from .config import InfraError, integer
from .http import request_json


_NAME = re.compile(r"[A-Za-z0-9_-]{1,127}")
_SYSTEM_GROUPS = {
    "DEFAULT_CONSUMER", "DEFAULT_PRODUCER", "TOOLS_CONSUMER", "SCHEDULE_CONSUMER",
    "FILTERSRV_CONSUMER", "__MONITOR_CONSUMER", "CLIENT_INNER_PRODUCER",
    "SELF_TEST_P_GROUP", "SELF_TEST_C_GROUP", "CID_ONS-HTTP-PROXY",
    "CID_ONSAPI_PERMISSION", "CID_ONSAPI_OWNER", "CID_ONSAPI_PULL",
}
_PAGE = {"offset": "Zero-based offset, default 0", "limit": "1–200, default 100"}
_TOPIC = {"topic": "Exact topic name"}
_GROUP = {"group": "Exact consumer group name"}
_TOPIC_CONFIG = {
    **_TOPIC, "read_queues": "Number of read queues, 1–1024",
    "write_queues": "Number of write queues, 1–1024",
    "permission": "2 (write), 4 (read), or 6 (read/write)",
    "message_type": "NORMAL, FIFO, DELAY, or TRANSACTION",
    "ordered": "Legacy ordered-topic flag, boolean; defaults to false on create",
}
_GROUP_CONFIG = {
    **_GROUP, "consume_enabled": "Boolean", "ordered": "Boolean (FIFO consumption)",
    "retry_max_times": "Integer 0–100",
}


def _name(value):
    return isinstance(value, str) and bool(_NAME.fullmatch(value))


def _user_name(value):
    return (_name(value)
            and not value.upper().startswith(("RMQ_SYS_", "CID_RMQ_SYS_"))
            and value.upper() not in _SYSTEM_GROUPS | {
                "TBW102", "SCHEDULE_TOPIC_XXXX", "DEFAULTHEARTBEATSYNCERTOPIC",
            })


def _invalid_response():
    return InfraError("backend_error", "Unexpected RocketMQ Dashboard response")


class RocketMQService(BaseService):
    service = "rocketmq"
    operations = {
        "check_connection": Operation("read", "Check Dashboard access and brokers in the configured cluster."),
        "list_topics": Operation("read", "List visible application topics.", _PAGE),
        "get_topic": Operation("read", "Read configuration for an exact topic.", _TOPIC),
        "topic_stats": Operation("read", "Read queue offset statistics for an exact topic.", _TOPIC),
        "create_topic": Operation("create", "Upsert a topic; defaults to 8 read/write queues, permission 6 and NORMAL.", _TOPIC_CONFIG, ("update",)),
        "update_topic": Operation("update", "Upsert a topic with all configuration fields explicitly supplied.", _TOPIC_CONFIG, ("create",)),
        "delete_topic": Operation("delete", "Delete an exact topic and its NameServer route.", _TOPIC),
        "list_groups": Operation("read", "List visible consumer groups from the Dashboard cache.", _PAGE),
        "get_group": Operation("read", "Read broker settings for an exact consumer group.", _GROUP),
        "create_group": Operation("create", "Upsert a consumer group using supplied settings and broker defaults.", _GROUP_CONFIG, ("update",)),
        "update_group": Operation("update", "Change specified settings on each broker hosting an existing group.", _GROUP_CONFIG, ("create",)),
        "delete_group": Operation("delete", "Delete a group, its offsets, and associated retry and dead-letter topics.", _GROUP),
        "send_message": Operation("create", "Send a UTF-8 message to an existing NORMAL topic.", {
            **_TOPIC, "body": "Required nonempty string, up to 64 KiB",
            "key": "Optional message key", "tag": "Optional tag",
        }),
    }

    @staticmethod
    def _request(profile, method, path, **kwargs):
        if method == "POST":
            kwargs["csrf_path"] = "/rocketmq-dashboard/csrf-token"
        response = request_json(profile, method, path, **kwargs)
        if not isinstance(response, dict) or type(response.get("status")) is not int or "data" not in response:
            raise _invalid_response()
        if response["status"] != 0:
            raise InfraError("backend_error", f"RocketMQ Dashboard returned status {response['status']}; details withheld")
        return response["data"]

    def _cluster(self, profile):
        cluster = profile.options.get("cluster")
        if not _name(cluster):
            raise InfraError("invalid_config", "Configure an exact RocketMQ cluster name")
        data = self._request(profile, "GET", "/cluster/list.query")
        if not isinstance(data, dict) or not isinstance(data.get("clusterInfo"), dict):
            raise _invalid_response()
        clusters = data["clusterInfo"].get("clusterAddrTable")
        # Topic deletion changes NameServer routes. A connection must target a
        # Dashboard serving just the named cluster, including for discovery.
        if not isinstance(clusters, dict) or set(clusters) != {cluster}:
            raise InfraError("backend_error", "RocketMQ Dashboard must serve exactly the configured cluster")
        brokers = clusters[cluster]
        if not isinstance(brokers, list) or not brokers or not all(map(_name, brokers)):
            raise InfraError("backend_error", "Configured RocketMQ cluster has no usable brokers")
        return cluster, sorted(set(brokers))

    def _topics(self, profile):
        data = self._request(profile, "GET", "/topic/list.query",
                             params={"skipSysProcess": "false", "skipRetryAndDlq": "true"})
        names = data.get("topicList") if isinstance(data, dict) else None
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise _invalid_response()
        return names

    def _groups(self, profile, group, brokers):
        data = self._request(profile, "GET", "/consumer/examineSubscriptionGroupConfig.query",
                             params={"consumerGroup": group})
        if not isinstance(data, list):
            raise _invalid_response()
        configs = {}
        for entry in data:
            if not isinstance(entry, dict):
                raise _invalid_response()
            names = entry.get("brokerNameList")
            config = entry.get("subscriptionGroupConfig")
            if (not isinstance(names, list) or len(names) != 1 or names[0] not in brokers
                    or names[0] in configs or not isinstance(config, dict) or config.get("groupName") != group):
                raise _invalid_response()
            configs[names[0]] = config
        if not configs:
            raise InfraError("not_found", "Consumer group configuration was not found")
        return configs

    def _page(self, profile, kind, names, offset, limit):
        visible = []
        for name in sorted(set(n for n in names if _user_name(n))):
            try:
                profile.check_scope(kind, name)
            except InfraError as error:
                if error.code != "scope_denied":
                    raise
            else:
                visible.append(name)
        page = visible[offset:offset + limit]
        return {kind: page, "offset": offset + len(page), "has_more": offset + len(page) < len(visible)}

    def _write(self, profile, path, **kwargs):
        try:
            return self._request(profile, "POST", path, **kwargs)
        except InfraError as error:
            if error.code in {"timeout", "backend_error", "backend_http_error", "output_limit"}:
                raise InfraError("outcome_unknown", "RocketMQ write was not confirmed; check its state before retrying") from None
            raise

    def _mutate(self, profile, path, **kwargs):
        if self._write(profile, path, **kwargs) is not True:
            raise InfraError("outcome_unknown", "RocketMQ write was not confirmed; check its state before retrying")

    @staticmethod
    def _topic_config(operation, arguments):
        if operation == "update_topic" and set(arguments) != set(_TOPIC_CONFIG):
            raise InfraError("invalid_argument", "Topic update requires all topic configuration fields")
        perm = integer(arguments, "permission", 6, 2, 6)
        message_type = arguments.get("message_type", "NORMAL")
        ordered = arguments.get("ordered", False)
        if perm not in (2, 4, 6) or message_type not in ("NORMAL", "FIFO", "DELAY", "TRANSACTION"):
            raise InfraError("invalid_argument", "Unsupported topic permission or message type")
        if type(ordered) is not bool:
            raise InfraError("invalid_argument", "ordered must be a boolean")
        return {
            "readQueueNums": integer(arguments, "read_queues", 8, 1, 1024),
            "writeQueueNums": integer(arguments, "write_queues", 8, 1, 1024),
            "perm": perm, "messageType": message_type, "order": ordered,
        }

    @staticmethod
    def _group_config(arguments):
        changes = {}
        for argument, field in (("consume_enabled", "consumeEnable"), ("ordered", "consumeMessageOrderly")):
            if argument in arguments:
                if type(arguments[argument]) is not bool:
                    raise InfraError("invalid_argument", f"{argument} must be a boolean")
                changes[field] = arguments[argument]
        if "retry_max_times" in arguments:
            changes["retryMaxTimes"] = integer(arguments, "retry_max_times", None, 0, 100)
        return changes

    @staticmethod
    def _message(arguments):
        message = {"topic": arguments["topic"], "traceEnabled": False}
        for key, field, maximum in (("body", "messageBody", 65536), ("key", "key", 255), ("tag", "tag", 127)):
            if key not in arguments and key != "body":
                continue
            value = arguments.get(key)
            try:
                valid = isinstance(value, str) and 0 < len(value.encode("utf-8")) <= maximum
            except UnicodeError:
                valid = False
            if not valid or (key != "body" and any(ord(c) < 32 or ord(c) == 127 for c in value)):
                raise InfraError("invalid_argument", f"Invalid RocketMQ message {key}")
            message[field] = value
        return message

    def execute(self, profile, operation, arguments):
        if set(arguments) - self.operations[operation].parameters.keys():
            raise InfraError("invalid_argument", "Unsupported RocketMQ operation arguments")
        resource = next((k for k in ("topic", "group") if k in self.operations[operation].parameters), None)
        target = arguments.get(resource)
        if resource:
            if not _user_name(target):
                raise InfraError("invalid_argument", "Use an exact application topic or consumer group name")
            profile.check_scope(resource + "s", target)
        if operation in ("list_topics", "list_groups"):
            offset = integer(arguments, "offset", 0, 0, 1_000_000)
            limit = integer(arguments, "limit", 100, 1, 200)
        if operation in ("create_topic", "update_topic"):
            topic_config = self._topic_config(operation, arguments)
        if operation in ("create_group", "update_group"):
            group_config = self._group_config(arguments)
            if operation == "update_group" and not group_config:
                raise InfraError("invalid_argument", "Supply at least one group setting to update")
        if operation == "send_message":
            message = self._message(arguments)

        cluster, brokers = self._cluster(profile)
        if operation == "check_connection":
            return {"connected": True, "cluster": cluster, "broker_count": len(brokers)}
        if operation == "list_topics":
            names = [n for n in self._topics(profile) if n not in {cluster, *brokers}]
            return self._page(profile, "topics", names, offset, limit)
        if operation == "list_groups":
            data = self._request(profile, "GET", "/consumer/groupList.query", params={"skipSysGroup": "true"})
            if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
                raise _invalid_response()
            names = [row.get("group") for row in data if row.get("subGroupType") != "SYSTEM"]
            return self._page(profile, "groups", names, offset, limit)

        if resource == "topic":
            if target in {cluster, *brokers} or ("%SYS%" + target) in self._topics(profile):
                raise InfraError("scope_denied", "RocketMQ system topics are outside the application scope")
            params = {"topic": target}
            if operation == "get_topic":
                return self._request(profile, "GET", "/topic/examineTopicConfig.query", params=params)
            if operation == "topic_stats":
                return self._request(profile, "GET", "/topic/stats.query", params=params)
            if operation == "delete_topic":
                self._mutate(profile, "/topic/deleteTopic.do", params={**params, "clusterName": cluster})
                return {"topic": target, "deleted": True}
            if operation == "send_message":
                configs = self._request(profile, "GET", "/topic/examineTopicConfig.query", params=params)
                if (not isinstance(configs, list) or not configs or not all(
                        isinstance(row, dict) and row.get("topicName") == target
                        and row.get("messageType") == "NORMAL" for row in configs)):
                    raise InfraError("invalid_argument", "Message sending requires an existing NORMAL topic")
                sent = self._write(profile, "/topic/sendTopicMessage.do", json=message)
                if not isinstance(sent, dict) or sent.get("sendStatus") != "SEND_OK":
                    raise InfraError("outcome_unknown", "RocketMQ send was not confirmed; check before retrying")
                return {"topic": target, "message_id": sent.get("msgId"), "send_status": "SEND_OK"}
            self._mutate(profile, "/topic/createOrUpdate.do", json={
                "clusterNameList": [cluster], "topicName": target, **topic_config,
            })
            return {"topic": target, "upserted": True}

        if operation == "create_group":
            self._mutate(profile, "/consumer/createOrUpdate.do", json={
                "clusterNameList": [cluster], "subscriptionGroupConfig": {"groupName": target, **group_config},
            })
            return {"group": target, "upserted": True}
        configs = self._groups(profile, target, brokers)
        if operation == "get_group":
            return {"group": target, "brokers": configs}
        if operation == "delete_group":
            self._mutate(profile, "/consumer/deleteSubGroup.do", json={
                "groupName": target, "brokerNameList": sorted(configs),
            })
            return {"group": target, "deleted": True}
        # Retain per-broker settings that the caller did not change.
        for broker, config in configs.items():
            self._mutate(profile, "/consumer/createOrUpdate.do", json={
                "brokerNameList": [broker], "subscriptionGroupConfig": {**config, **group_config},
            })
        return {"group": target, "updated": True}
