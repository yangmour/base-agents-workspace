"""Nacos 3 Admin API operations; no console, user, or server administration."""
from dataclasses import replace
import ipaddress
import json
import math
from urllib.parse import quote

from .base import BaseService, Operation
from .config import InfraError, integer, secret, validate_name
from .http import request_json


COMMON = {'namespace_id': 'Exact namespace ID; empty or omitted means public.',
          'group': 'Exact group; default DEFAULT_GROUP.'}
CONFIG = {**COMMON, 'data_id': 'Exact configuration data ID.'}
SERVICE = {**COMMON, 'service_name': 'Exact ungrouped service name; no @@ or wildcard.'}
INSTANCE = {**SERVICE, 'ip': 'IPv4 or IPv6 address.', 'port': 'Integer 1–65535.',
            'cluster': 'Exact cluster name; default DEFAULT.',
            'ephemeral': 'Boolean, default true. This MCP does not send heartbeats.'}
PAGE = {'page': 'Page number, default 1.', 'page_size': 'Page size 1–200, default 20.'}


def exact(value, label):
    value = validate_name(value, label)
    if value != value.strip() or any(c in value for c in '*?[]/\\') or '@@' in value:
        raise InfraError('invalid_argument', f'{label} must be one exact name')
    return value


def boolean(arguments, key, default=None):
    value = arguments.get(key, default)
    if type(value) is not bool:
        raise InfraError('invalid_argument', f'{key} must be boolean')
    return 'true' if value else 'false'


def number(arguments, key, maximum):
    value = arguments[key]
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise InfraError('invalid_argument', f'{key} is outside its supported numeric range')
    return value


def metadata(value):
    if not isinstance(value, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
        raise InfraError('invalid_argument', 'metadata must map strings to strings')
    encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    if len(encoded.encode()) > 65536:
        raise InfraError('invalid_argument', 'metadata exceeds 64 KiB')
    return encoded


def selector(value):
    if not isinstance(value, dict) or value.get('type') not in ('none', 'label'):
        raise InfraError('invalid_argument', 'selector must have type none or label')
    expected = {'type'} if value['type'] == 'none' else {'type', 'expression'}
    if set(value) != expected:
        raise InfraError('invalid_argument', 'selector contains missing or unsupported fields')
    if value['type'] == 'label' and (not isinstance(value['expression'], str) or not value['expression'].strip()):
        raise InfraError('invalid_argument', 'label selector requires a nonempty expression')
    encoded = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    if len(encoded.encode()) > 65536:
        raise InfraError('invalid_argument', 'selector exceeds 64 KiB')
    # Nacos parseSelector URL-decodes again after Spring has decoded the form.
    # Encode this field once here so literal plus/percent and Unicode survive.
    return quote(encoded, safe='')


class NacosService(BaseService):
    service = 'nacos'
    operations = {
        'check_connection': Operation('read', 'Check Nacos 3 Admin API connectivity and authentication.'),
        'get_config': Operation('read', 'Read one configuration. Content may contain application secrets.', CONFIG),
        'list_configs': Operation('read', 'Read a filtered page of configuration metadata, without content.', {**COMMON, **PAGE}),
        'publish_config': Operation('create', 'Publish configuration: native upsert requires create AND update.',
            {**CONFIG, 'content': 'Required UTF-8 text, at most 65536 bytes.',
             'type': 'text, json, xml, yaml, html or properties; default text.'}, ('update',)),
        'delete_config': Operation('delete', 'Delete one exact configuration.', CONFIG),
        'list_services': Operation('read', 'Read one filtered service page.', {**COMMON, **PAGE}),
        'get_service': Operation('read', 'Read one exact service.', SERVICE),
        'create_service': Operation('create', 'Create a service; backend rejects existing services.',
            {**SERVICE, 'metadata': 'Optional string-to-string object.', 'ephemeral': 'Boolean; default false.',
             'protect_threshold': 'Optional number 0–1.',
             'selector': 'Optional selector object: {type: none} or {type: label, expression: string}; default none.'}),
        'update_service': Operation('update', 'Replace service metadata, protection threshold and selector. All three fields are required; this is not a partial update.',
            {**SERVICE, 'metadata': 'Required replacement string-to-string object.', 'protect_threshold': 'Required number 0–1.',
             'selector': 'Required selector object: {type: none} or {type: label, expression: string}.'}),
        'delete_service': Operation('delete', 'Delete an empty service; backend rejects services with instances.', SERVICE),
        'list_instances': Operation('read', 'List instances of one exact service; HTTP response size is bounded.',
            {**SERVICE, 'healthy_only': 'Boolean, default false.'}),
        'get_instance': Operation('read', 'Read one instance.', INSTANCE),
        'register_instance': Operation('create', 'Register/re-register one instance; requires create AND update.',
            {**INSTANCE, 'weight': 'Optional number 0–1000000.', 'enabled': 'Optional boolean.',
             'healthy': 'Optional boolean.', 'metadata': 'Optional string-to-string object.'}, ('update',)),
        'update_instance': Operation('update', 'Replace instance weight, enabled state and metadata via native PUT. All three fields are required; requires create too. Does not change health status.',
            {**INSTANCE, 'weight': 'Required number 0–1000000.', 'enabled': 'Required boolean.',
             'metadata': 'Required replacement string-to-string object.'}, ('create',)),
        'deregister_instance': Operation('delete', 'Deregister one exact instance.', INSTANCE),
    }

    @staticmethod
    def _request(profile, method, path, params=None, data=None):
        if profile.options.get('api_version', 3) != 3:
            raise InfraError('invalid_config', 'This adapter supports Nacos 3.x only')
        username = profile.options.get('username')
        referenced_username = secret(profile, 'username')
        if username is not None and referenced_username is not None:
            raise InfraError('invalid_config', 'Choose one username source')
        username = referenced_username if username is None else username
        password, token = secret(profile, 'password'), secret(profile, 'token')
        if any(k in profile.options for k in ('api_key_env', 'api_key_file')):
            raise InfraError('invalid_config', 'Nacos supports access token or username/password authentication')
        if token is not None and (username is not None or password is not None):
            raise InfraError('invalid_config', 'Choose token or username/password authentication')
        if (username is None) != (password is None):
            raise InfraError('invalid_config', 'Nacos login requires username and password')
        # The shared transport must not turn Nacos credentials into HTTP Basic/Bearer auth.
        private_keys = {key + suffix for key in ('username', 'password', 'token', 'api_key')
                        for suffix in ('', '_env', '_file')}
        transport = replace(profile, options={k: v for k, v in profile.options.items() if k not in private_keys})
        if username is not None:
            validate_name(username, 'username')
            response = request_json(transport, 'POST', '/v3/auth/user/login', data={
                'username': username, 'password': password})
            token = response.get('accessToken') if isinstance(response, dict) else None
            if not isinstance(token, str) or not token:
                raise InfraError('backend_error', 'Nacos login failed; response withheld')
        headers = {}
        if token is not None:
            if not isinstance(token, str) or not token or len(token) > 65536 or any(ord(c) < 33 or ord(c) > 126 for c in token):
                raise InfraError('invalid_config', 'Invalid access token')
            headers['accessToken'] = token
        response = request_json(transport, method, '/v3/admin/' + path, params=params, data=data, headers=headers)
        # Nacos can return an application failure inside an HTTP 200 response.
        if not isinstance(response, dict) or type(response.get('code')) is not int or 'data' not in response:
            raise InfraError('backend_error', 'Invalid Nacos response envelope')
        if response['code'] != 0:
            raise InfraError('backend_error', f'Nacos returned code {response["code"]}; details withheld')
        return response['data']

    def execute(self, profile, operation, arguments):
        if operation == 'check_connection':
            self._request(profile, 'GET', 'ns/service/selector/types')
            return {'connected': True, 'api_version': 3}
        namespace = arguments.get('namespace_id', 'public')
        namespace = 'public' if namespace == '' else exact(namespace, 'namespace_id')
        group = exact(arguments.get('group', 'DEFAULT_GROUP'), 'group')
        profile.check_scope('namespaces', namespace)
        profile.check_scope('groups', group)
        params = {'namespaceId': namespace, 'groupName': group}
        if operation in ('list_configs', 'list_services'):
            page = integer(arguments, 'page', 1, 1, 1000000)
            size = integer(arguments, 'page_size', 20, 1, 200)
            params.update(pageNo=page, pageSize=size)
            path = 'cs/config/list' if operation == 'list_configs' else 'ns/service/list'
            if operation == 'list_configs':
                params['search'] = 'blur'
            else:
                # Nacos 3.0's summary branch returns an unpaged collection. The
                # detail branch paginates correctly; its extra data is discarded
                # below. Avoid server regex group filters: use exact local scope
                # filtering on each namespace page, which can produce empty pages.
                params.pop('groupName')
                params['withInstances'] = 'true'
            result = self._request(profile, 'GET', path, params=params)
            return self._page(profile, result, namespace, group, page, operation == 'list_configs')
        if operation in ('get_config', 'publish_config', 'delete_config'):
            data_id = exact(arguments.get('data_id'), 'data_id')
            profile.check_scope('data_ids', data_id)
            params['dataId'] = data_id
            if operation == 'publish_config':
                content = arguments.get('content')
                if not isinstance(content, str) or len(content.encode()) > 65536:
                    raise InfraError('invalid_argument', 'content must be text of at most 64 KiB')
                kind = arguments.get('type', 'text')
                if kind not in ('text', 'json', 'xml', 'yaml', 'html', 'properties'):
                    raise InfraError('invalid_argument', 'Unsupported configuration type')
                result = self._request(profile, 'POST', 'cs/config', data={**params, 'content': content, 'type': kind})
            else:
                result = self._request(profile, 'GET' if operation == 'get_config' else 'DELETE', 'cs/config', params=params)
            if operation == 'get_config' and isinstance(result, dict):
                # Do not deliver encryption keys or internal credential fields, even if redaction is disabled.
                return {k: v for k, v in result.items() if k in {'dataId', 'groupName', 'namespaceId', 'content', 'md5', 'type', 'modifyTime', 'desc', 'appName'}}
            return {'published' if operation == 'publish_config' else 'deleted': result} if operation != 'get_config' else result
        service = exact(arguments.get('service_name'), 'service_name')
        profile.check_scope('services', service)
        params['serviceName'] = service
        if operation == 'list_instances':
            params['healthyOnly'] = boolean(arguments, 'healthy_only', False)
            return self._request(profile, 'GET', 'ns/instance/list', params=params)
        instance = operation in ('get_instance', 'register_instance', 'update_instance', 'deregister_instance')
        if instance:
            ip = arguments.get('ip')
            try:
                if not isinstance(ip, str) or '%' in ip:
                    raise ValueError()
                ipaddress.ip_address(ip)
            except ValueError:
                raise InfraError('invalid_argument', 'ip must be an IPv4 or IPv6 address') from None
            params.update(ip=ip, port=integer(arguments, 'port', None, 1, 65535),
                          clusterName=exact(arguments.get('cluster', 'DEFAULT'), 'cluster'),
                          ephemeral=boolean(arguments, 'ephemeral', True))
        path = 'ns/instance' if instance else 'ns/service'
        if operation in ('get_service', 'get_instance', 'delete_service', 'deregister_instance'):
            method = 'GET' if operation.startswith('get_') else 'DELETE'
            return self._request(profile, method, path, params=params)
        # Native Nacos PUT fills omitted fields with defaults. Require the complete
        # replacement so updating metadata cannot silently enable an instance or
        # reset a service's threshold/selector; a GET+PUT would introduce races.
        required = {'weight', 'enabled', 'metadata'} if operation == 'update_instance' else {
            'metadata', 'protect_threshold', 'selector'} if operation == 'update_service' else set()
        if required - arguments.keys():
            raise InfraError('invalid_argument', 'Full replacement requires: ' + ', '.join(sorted(required)))
        if 'metadata' in arguments:
            params['metadata'] = metadata(arguments['metadata'])
        if instance:
            for key in ('enabled', 'healthy'):
                if key in arguments:
                    params[key] = boolean(arguments, key)
            if 'weight' in arguments:
                params['weight'] = number(arguments, 'weight', 1000000)
        else:
            if operation == 'create_service':
                params['ephemeral'] = boolean(arguments, 'ephemeral', False)
                params['selector'] = selector(arguments.get('selector', {'type': 'none'}))
            elif operation == 'update_service':
                params['selector'] = selector(arguments['selector'])
            if 'protect_threshold' in arguments:
                params['protectThreshold'] = number(arguments, 'protect_threshold', 1)
        method = 'POST' if operation in ('create_service', 'register_instance') else 'PUT'
        return self._request(profile, method, path, data=params)

    @staticmethod
    def _page(profile, response, namespace, group, page, configs):
        if not isinstance(response, dict) or not isinstance(response.get('pageItems'), list):
            raise InfraError('backend_error', 'Invalid Nacos page response')
        items = []
        for row in response['pageItems']:
            if not isinstance(row, dict):
                continue
            # ServiceDetailInfo leaves namespaceId null in Nacos 3.0/3.3, even
            # though the backend query is scoped to the requested namespace.
            ns = (row.get('namespaceId', namespace) or 'public') if configs else (row.get('namespaceId') or namespace)
            row_group = row.get('groupName', group) if configs else row.get('groupName')
            if ns != namespace or row_group != group:
                continue
            name = row.get('dataId') if configs else row.get('serviceName', row.get('name'))
            try:
                profile.check_scope('data_ids' if configs else 'services', name)
            except InfraError:
                continue
            fields = {'dataId', 'groupName', 'namespaceId', 'md5', 'appName', 'type', 'createTime', 'modifyTime'} if configs else {
                'name', 'groupName', 'clusterCount', 'ipCount', 'healthyInstanceCount', 'triggerFlag'}
            item = {key: value for key, value in row.items() if key in fields}
            if not configs:
                item['name'] = name
            items.append(item)
        pages = response.get('pagesAvailable')
        if type(pages) is not int or pages < 0:
            raise InfraError('backend_error', 'Invalid Nacos pagination')
        # Counts from the backend can include resources outside scope. Return continuation only.
        return {'items': items, 'page': page, 'has_more': page < pages}
