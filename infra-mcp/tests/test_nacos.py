import json
from urllib.parse import parse_qs, unquote_plus

import httpx
import pytest

from infra_mcp.config import ConfigStore, InfraError


def service(tmp_path, monkeypatch, responder=None, **options):
    # Import after the test is collected, so missing implementation is an explicit failure.
    import importlib.util
    assert importlib.util.find_spec('infra_mcp.nacos_service'), 'Nacos adapter is not implemented'
    from infra_mcp.nacos_service import NacosService
    path = tmp_path / 'config.json'
    options.setdefault('permissions', dict.fromkeys(('read', 'create', 'update', 'delete'), True))
    path.write_text(json.dumps({'profiles': {'nacos': {'test': {
        'url': 'http://localhost:8848/nacos', **options}}}}))
    requests = []
    original = httpx.Client

    def handle(request):
        requests.append(request)
        return responder(request) if responder else httpx.Response(200, json={'code': 0, 'data': True})

    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handle), **kw))
    return NacosService(ConfigStore(path)), requests


def test_nacos_default_crud_and_private_discovery(tmp_path, monkeypatch):
    backend, _ = service(tmp_path, monkeypatch, password_env='TEST_SECRET', username='user')
    info = backend.list_connections()['connections'][0]
    assert set(info['permissions']) == {'create', 'read', 'update', 'delete'}
    assert 'username' not in info and 'TEST_SECRET' not in json.dumps(info)


@pytest.mark.parametrize('permissions', [{'read': True}, {'create': True}, {'update': True}])
def test_config_publish_requires_create_and_update_before_login(tmp_path, monkeypatch, permissions):
    backend, calls = service(tmp_path, monkeypatch, permissions=permissions, username='user', password_env='UNSET')
    with pytest.raises(InfraError) as error:
        backend.run('test', 'create', 'publish_config', {'data_id': 'app.yaml', 'content': 'test'})
    assert error.value.code == 'permission_denied'
    assert not calls


@pytest.mark.parametrize('arguments', [
    {'namespace_id': 'other', 'group': 'APP', 'data_id': 'app.yaml'},
    {'namespace_id': 'public', 'group': 'OTHER', 'data_id': 'app.yaml'},
    {'namespace_id': 'public', 'group': 'APP', 'data_id': 'other.yaml'},
])
def test_scope_rejected_before_authentication(tmp_path, monkeypatch, arguments):
    backend, calls = service(tmp_path, monkeypatch, scope={'namespaces': ['public'], 'groups': ['APP'], 'data_ids': ['app.*']})
    with pytest.raises(InfraError) as error:
        backend.run('test', 'read', 'get_config', arguments)
    assert error.value.code == 'scope_denied'
    assert not calls


def test_login_is_form_and_token_is_header_never_query_or_output(tmp_path, monkeypatch):
    monkeypatch.setenv('NACOS_PASS', 'sensitive-password')
    def respond(request):
        if request.url.path.endswith('/auth/user/login'):
            return httpx.Response(200, json={'accessToken': 'sensitive-token', 'tokenTtl': 100})
        return httpx.Response(200, json={'code': 0, 'data': {'content': 'synthetic'}})
    backend, calls = service(tmp_path, monkeypatch, respond, username='user', password_env='NACOS_PASS')
    result = backend.run('test', 'read', 'get_config', {'data_id': 'app.yaml'})
    assert len(calls) == 2
    assert calls[0].url.path == '/nacos/v3/auth/user/login'
    assert parse_qs(calls[0].content.decode()) == {'username': ['user'], 'password': ['sensitive-password']}
    assert calls[1].headers['accessToken'] == 'sensitive-token'
    assert 'Authorization' not in calls[1].headers
    assert 'sensitive' not in str(calls[1].url)
    assert 'sensitive' not in json.dumps(result)


def test_config_publish_and_delete_use_fixed_v3_paths_and_encoded_arguments(tmp_path, monkeypatch):
    backend, calls = service(tmp_path, monkeypatch)
    args = {'namespace_id': '', 'group': 'APP', 'data_id': 'file&name.yaml', 'content': 'key: 中文&=value', 'type': 'yaml'}
    backend.run('test', 'create', 'publish_config', args)
    body = parse_qs(calls[0].content.decode())
    assert calls[0].method == 'POST' and calls[0].url.path == '/nacos/v3/admin/cs/config'
    assert body['namespaceId'] == ['public'] and body['content'] == [args['content']]
    assert body['groupName'] == ['APP'] and body['dataId'] == ['file&name.yaml']
    backend.run('test', 'delete', 'delete_config', args)
    assert calls[1].method == 'DELETE'
    assert calls[1].url.params['dataId'] == args['data_id']


def test_nonzero_application_error_never_returns_backend_text(tmp_path, monkeypatch):
    backend, _ = service(tmp_path, monkeypatch, lambda req: httpx.Response(200, json={
        'code': 20004, 'message': 'PASSWORD-SENSITIVE', 'data': 'TOKEN-SENSITIVE'}))
    with pytest.raises(InfraError) as error:
        backend.run('test', 'read', 'get_config', {'data_id': 'missing'})
    assert error.value.code == 'backend_error'
    assert '20004' in str(error.value) and 'SENSITIVE' not in str(error.value)


def test_list_configs_filters_scope_and_does_not_echo_content(tmp_path, monkeypatch):
    rows = [{'namespaceId': 'public', 'groupName': 'APP', 'dataId': 'app.yaml', 'content': 'NOT-LISTED'},
            {'namespaceId': 'public', 'groupName': 'APP', 'dataId': 'outside.yaml'},
            {'namespaceId': 'other', 'groupName': 'APP', 'dataId': 'app-other.yaml'}]
    backend, calls = service(tmp_path, monkeypatch, lambda req: httpx.Response(200, json={
        'code': 0, 'data': {'pageItems': rows, 'totalCount': 50, 'pagesAvailable': 5}}),
        scope={'namespaces': ['public'], 'groups': ['APP'], 'data_ids': ['app*']})
    result = backend.run('test', 'read', 'list_configs', {'group': 'APP', 'page_size': 10})['data']
    assert len(result['items']) == 1 and result['items'][0]['dataId'] == 'app.yaml'
    assert 'NOT-LISTED' not in json.dumps(result) and 'totalCount' not in result
    assert calls[0].url.params['pageSize'] == '10'
    assert result['has_more'] is True


@pytest.mark.parametrize('name', ['OTHER@@service', 'service*', '../service'])
def test_service_names_cannot_override_group_or_address_multiple_targets(tmp_path, monkeypatch, name):
    backend, calls = service(tmp_path, monkeypatch)
    with pytest.raises(InfraError):
        backend.run('test', 'delete', 'delete_service', {'service_name': name})
    assert not calls


def test_services_and_instances_use_correct_methods_and_typed_forms(tmp_path, monkeypatch):
    backend, calls = service(tmp_path, monkeypatch)
    common = {'service_name': 'app', 'group': 'APP'}
    backend.run('test', 'create', 'create_service', {**common, 'metadata': {'test': 'one'}})
    backend.run('test', 'update', 'update_service', {**common, 'protect_threshold': 0.5, 'metadata': {'test': 'two'}, 'selector': {'type': 'none'}})
    backend.run('test', 'create', 'register_instance', {**common, 'ip': '127.0.0.1', 'port': 9999, 'ephemeral': False})
    backend.run('test', 'update', 'update_instance', {**common, 'ip': '127.0.0.1', 'port': 9999, 'enabled': False, 'weight': 7, 'metadata': {'test': 'two'}})
    backend.run('test', 'delete', 'deregister_instance', {**common, 'ip': '127.0.0.1', 'port': 9999})
    assert [c.method for c in calls] == ['POST', 'PUT', 'POST', 'PUT', 'DELETE']
    assert parse_qs(calls[0].content.decode())['metadata'] == ['{"test":"one"}']
    assert parse_qs(calls[2].content.decode())['ephemeral'] == ['false']
    assert parse_qs(calls[3].content.decode())['enabled'] == ['false']


@pytest.mark.parametrize('operation,arguments,required', [
    ('update_service', {'service_name': 'app', 'metadata': {'keep': 'value'}, 'protect_threshold': 0.5, 'selector': {'type': 'none'}}, 'metadata'),
    ('update_service', {'service_name': 'app', 'metadata': {'keep': 'value'}, 'protect_threshold': 0.5, 'selector': {'type': 'none'}}, 'protect_threshold'),
    ('update_service', {'service_name': 'app', 'metadata': {'keep': 'value'}, 'protect_threshold': 0.5, 'selector': {'type': 'none'}}, 'selector'),
    ('update_instance', {'service_name': 'app', 'ip': '127.0.0.1', 'port': 9999, 'weight': 7, 'enabled': False, 'metadata': {'keep': 'value'}}, 'weight'),
    ('update_instance', {'service_name': 'app', 'ip': '127.0.0.1', 'port': 9999, 'weight': 7, 'enabled': False, 'metadata': {'keep': 'value'}}, 'enabled'),
    ('update_instance', {'service_name': 'app', 'ip': '127.0.0.1', 'port': 9999, 'weight': 7, 'enabled': False, 'metadata': {'keep': 'value'}}, 'metadata'),
])
def test_native_updates_require_complete_representation_before_backend(tmp_path, monkeypatch, operation, arguments, required):
    backend, calls = service(tmp_path, monkeypatch)
    arguments = {key: value for key, value in arguments.items() if key != required}
    with pytest.raises(InfraError) as error:
        backend.run('test', 'update', operation, arguments)
    assert error.value.code == 'invalid_argument'
    assert not calls


@pytest.mark.parametrize('selector', [None, {'type': 'other'}, {'type': 'label'}, {'type': 'label', 'expression': 1}, {'type': 'none', 'expression': 'ignored'}, {'type': 'label', 'expression': 'x', 'extra': 'ignored'}])
def test_service_selector_rejects_invalid_or_ignored_fields(tmp_path, monkeypatch, selector):
    backend, calls = service(tmp_path, monkeypatch)
    with pytest.raises(InfraError) as error:
        backend.run('test', 'create', 'create_service', {'service_name': 'app', 'selector': selector})
    assert error.value.code == 'invalid_argument'
    assert not calls


def test_service_replacement_sends_explicit_selector_and_full_state(tmp_path, monkeypatch):
    backend, calls = service(tmp_path, monkeypatch)
    selector = {'type': 'label', 'expression': 'CONSUMER.label.zone = PROVIDER.label.zone'}
    backend.run('test', 'update', 'update_service', {'service_name': 'app', 'metadata': {'version': 'two'}, 'protect_threshold': 0.6, 'selector': selector})
    body = parse_qs(calls[0].content.decode())
    assert json.loads(unquote_plus(body['selector'][0])) == selector
    assert json.loads(body['metadata'][0]) == {'version': 'two'}
    assert body['protectThreshold'] == ['0.6']


def test_selector_survives_nacos_extra_url_decode_after_form_decoding(tmp_path, monkeypatch):
    backend, calls = service(tmp_path, monkeypatch)
    selector = {'type': 'label', 'expression': 'CONSUMER.label.zone = "中文+%2B%25"'}
    backend.run('test', 'create', 'create_service', {'service_name': 'app', 'selector': selector})
    # Spring decodes the form once, then Nacos parseSelector calls URLDecoder again.
    spring_form = parse_qs(calls[0].content.decode())
    server_selector = json.loads(unquote_plus(spring_form['selector'][0]))
    assert server_selector == selector


def test_service_pages_use_paginated_detail_branch_and_filter_to_exact_scope(tmp_path, monkeypatch):
    rows = [
        {'namespaceId': 'public', 'groupName': 'APP.v1+', 'serviceName': 'owned', 'metadata': {'private': 'not-returned'}, 'clusterMap': {'hosts': 'not-returned'}},
        {'namespaceId': 'public', 'groupName': 'APP.v1+', 'serviceName': 'outside'},
        {'namespaceId': 'other', 'groupName': 'APP.v1+', 'serviceName': 'owned'},
        {'namespaceId': 'public', 'groupName': 'OTHER', 'serviceName': 'owned'},
    ]
    backend, calls = service(tmp_path, monkeypatch, lambda req: httpx.Response(200, json={
        'code': 0, 'data': {'pageItems': rows, 'pagesAvailable': 3, 'totalCount': 50}}),
        scope={'namespaces': ['public'], 'groups': ['APP.v1+'], 'services': ['owned']})
    result = backend.run('test', 'read', 'list_services', {'group': 'APP.v1+', 'page': 2, 'page_size': 1})['data']
    assert 'groupNameParam' not in calls[0].url.params
    assert 'groupName' not in calls[0].url.params
    assert calls[0].url.params['withInstances'] == 'true'
    assert calls[0].url.params['pageNo'] == '2' and calls[0].url.params['pageSize'] == '1'
    assert result == {'items': [{'name': 'owned', 'groupName': 'APP.v1+'}], 'page': 2, 'has_more': True}
    assert 'not-returned' not in json.dumps(result)


def test_service_detail_page_null_namespace_uses_scoped_request_namespace(tmp_path, monkeypatch):
    rows = [{'namespaceId': None, 'groupName': 'APP', 'serviceName': 'owned'},
            {'namespaceId': 'other', 'groupName': 'APP', 'serviceName': 'owned'},
            {'namespaceId': None, 'serviceName': 'owned'}]
    backend, _ = service(tmp_path, monkeypatch, lambda req: httpx.Response(200, json={
        'code': 0, 'data': {'pageItems': rows, 'pagesAvailable': 1}}),
        scope={'namespaces': ['tenant-one'], 'groups': ['APP'], 'services': ['owned']})
    data = backend.run('test', 'read', 'list_services', {'namespace_id': 'tenant-one', 'group': 'APP'})['data']
    assert data['items'] == [{'name': 'owned', 'groupName': 'APP'}]


def test_scoped_empty_service_page_preserves_backend_continuation(tmp_path, monkeypatch):
    backend, _ = service(tmp_path, monkeypatch, lambda req: httpx.Response(200, json={
        'code': 0, 'data': {'pageItems': [{'groupName': 'OTHER', 'serviceName': 'owned'}],
                           'pagesAvailable': 2, 'totalCount': 50}}),
        scope={'namespaces': ['public'], 'groups': ['APP'], 'services': ['owned']})
    data = backend.run('test', 'read', 'list_services', {'group': 'APP', 'page': 1, 'page_size': 1})['data']
    assert data == {'items': [], 'page': 1, 'has_more': True}


@pytest.mark.parametrize('fields', [{'port': True}, {'port': 70000}, {'ip': 'not-an-ip'}, {'weight': float('nan')}, {'enabled': 'false'}, {'metadata': {'key': 2}}])
def test_invalid_instance_payload_fails_before_request(tmp_path, monkeypatch, fields):
    backend, calls = service(tmp_path, monkeypatch)
    with pytest.raises(InfraError):
        backend.run('test', 'create', 'register_instance', {'service_name': 'app', 'ip': '127.0.0.1', 'port': 9999, **fields})
    assert not calls


def test_conflicting_authentication_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('NACOS_TOKEN', 'secret')
    monkeypatch.setenv('NACOS_PASS', 'secret')
    backend, calls = service(tmp_path, monkeypatch, username='user', password_env='NACOS_PASS', token_env='NACOS_TOKEN')
    with pytest.raises(InfraError) as error:
        backend.run('test', 'read', 'check_connection')
    assert error.value.code == 'invalid_config' and not calls
