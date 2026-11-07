import pytest
import httpx
from infra_mcp.config import Profile, InfraError
from infra_mcp.rabbitmq_service import RabbitMQService
import infra_mcp.rabbitmq_service as module

class Store:

    def __init__(self, permissions=('create', 'read', 'update', 'delete'), scope=None):
        self.profile = Profile('test', 'rabbitmq', {}, frozenset(permissions), scope or {})

    def get(self, service, connection):
        return self.profile

@pytest.fixture
def backend(monkeypatch):
    calls = []

    def request(*args, **kwargs):
        calls.append((args[1:], kwargs))
        return []
    monkeypatch.setattr(module, 'request_json', request)
    return calls

def test_escape_components(backend):
    RabbitMQService(Store()).run('test', 'read', 'get_queue', {'vhost': '/a', 'queue': 'q/a ?'})
    assert backend[0][0] == ('GET', '/api/queues/%2Fa/q%2Fa%20%3F')

@pytest.mark.parametrize('operation,action,args', [('declare_queue', 'create', {'vhost': '/', 'queue': 'q'}), ('declare_exchange', 'create', {'vhost': '/', 'exchange': 'x'}), ('publish', 'read', {'vhost': '/', 'exchange': 'x', 'payload': 'hi'}), ('consume', 'read', {'vhost': '/', 'queue': 'q'})])
def test_permissions_precede_backend(backend, operation, action, args):
    with pytest.raises(InfraError):
        RabbitMQService(Store(('create', 'read'))).run('test', action, operation, args)
    assert backend == []

def test_scope_and_missing_target(backend):
    service = RabbitMQService(Store(scope={'vhosts': ['safe']}))
    with pytest.raises(InfraError):
        service.run('test', 'read', 'get_queue', {'vhost': 'other', 'queue': 'q'})
    with pytest.raises(InfraError):
        service.run('test', 'read', 'get_queue', {'vhost': 'safe'})
    assert backend == []

def test_list_filters_vhosts_and_queues(monkeypatch):
    monkeypatch.setattr(module, 'request_json', lambda *a, **kw: [{'name': 'q', 'vhost': 'safe'}, {'name': 'bad', 'vhost': 'safe'}, {'name': 'q', 'vhost': 'other'}])
    result = RabbitMQService(Store(scope={'vhosts': ['safe'], 'queues': ['q']})).run('test', 'read', 'list_queues', {'vhost': 'safe'})
    assert result['data'] == [{'name': 'q', 'vhost': 'safe'}]

def test_consume_destructive_and_publish_create(backend):
    service = RabbitMQService(Store())
    service.run('test', 'delete', 'consume', {'vhost': '/', 'queue': 'q'})
    assert backend[-1][1]['json']['ackmode'] == 'ack_requeue_false'
    service.run('test', 'create', 'publish', {'vhost': '/', 'exchange': 'x', 'payload': 'hello', 'routing_key': 'q'})
    assert backend[-1][0] == ('POST', '/api/exchanges/%2F/x/publish')

@pytest.mark.parametrize('value', ['.', '..'])
def test_dot_path_targets_rejected(backend, value):
    with pytest.raises(InfraError):
        RabbitMQService(Store()).run('test', 'read', 'get_queue', {'vhost': '/', 'queue': value})
    assert backend == []

@pytest.mark.parametrize('operation,action,args,method,path', [('declare_queue', 'create', {'vhost': '/', 'queue': 'q'}, 'PUT', '/api/queues/%2F/q'), ('declare_exchange', 'create', {'vhost': '/', 'exchange': 'x'}, 'PUT', '/api/exchanges/%2F/x'), ('delete_queue', 'delete', {'vhost': '/', 'queue': 'q'}, 'DELETE', '/api/queues/%2F/q'), ('purge_queue', 'delete', {'vhost': '/', 'queue': 'q'}, 'DELETE', '/api/queues/%2F/q/contents'), ('get_exchange', 'read', {'vhost': '/', 'exchange': 'x'}, 'GET', '/api/exchanges/%2F/x'), ('delete_exchange', 'delete', {'vhost': '/', 'exchange': 'x'}, 'DELETE', '/api/exchanges/%2F/x')])
def test_fixed_routes(backend, operation, action, args, method, path):
    RabbitMQService(Store()).run('test', action, operation, args)
    assert backend[0][0] == (method, path)


def test_purge_accepts_empty_response_without_requiring_json_representation(monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        # RabbitMQ 3.12 purge does not advertise a JSON representation. Its
        # content negotiation rejects JSON-only Accept before deleting messages.
        return httpx.Response(406 if request.headers.get('accept') == 'application/json' else 204)

    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    store = Store(scope={'vhosts': ['/'], 'queues': ['test-owned-queue']})
    store.profile = Profile('test', 'rabbitmq', {'url': 'http://127.0.0.1:15672'}, store.profile.permissions, store.profile.scope)
    result = RabbitMQService(store).run('test', 'delete', 'purge_queue', {'vhost': '/', 'queue': 'test-owned-queue'})
    assert result['data'] == {'status': 204}
    assert len(requests) == 1
    assert requests[0].method == 'DELETE'
    assert requests[0].url.raw_path == b'/api/queues/%2F/test-owned-queue/contents'

@pytest.mark.parametrize('operation,args', [('get_queue', {'vhost': '/', 'queue': 'private'}), ('get_exchange', {'vhost': '/', 'exchange': 'private'})])
def test_resource_scopes(backend, operation, args):
    with pytest.raises(InfraError):
        RabbitMQService(Store(scope={'queues': ['q'], 'exchanges': ['x']})).run('test', 'read', operation, args)
    assert backend == []

@pytest.mark.parametrize('operation,rows,scope,expected', [('list_vhosts', [{'name': '/'}, {'name': 'private'}], {'vhosts': ['/']}, [{'name': '/'}]), ('list_exchanges', [{'name': 'x', 'vhost': '/'}, {'name': 'private', 'vhost': '/'}], {'exchanges': ['x']}, [{'name': 'x', 'vhost': '/'}])])
def test_other_list_filters(monkeypatch, operation, rows, scope, expected):
    monkeypatch.setattr(module, 'request_json', lambda *a, **kw: rows)
    assert RabbitMQService(Store(scope=scope)).run('test', 'read', operation, {'vhost': '/'})['data'] == expected

@pytest.mark.parametrize('operation,action,args,method,path', [('check_connection', 'read', {}, 'GET', '/api/whoami'), ('overview', 'read', {}, 'GET', '/api/overview'), ('list_bindings', 'read', {'vhost': '/'}, 'GET', '/api/bindings/%2F'), ('create_binding', 'create', {'vhost': '/', 'exchange': 'x/a', 'queue': 'q/b', 'routing_key': 'r'}, 'POST', '/api/bindings/%2F/e/x%2Fa/q/q%2Fb'), ('delete_binding', 'delete', {'vhost': '/', 'exchange': 'x', 'queue': 'q', 'properties_key': 'r/a'}, 'DELETE', '/api/bindings/%2F/e/x/q/q/r%2Fa'), ('update_policy', 'update', {'vhost': '/', 'name': 'p', 'pattern': '^q', 'definition': {'max-length': 10}}, 'PUT', '/api/policies/%2F/p'), ('delete_policy', 'delete', {'vhost': '/', 'name': 'p'}, 'DELETE', '/api/policies/%2F/p')])
def test_additional_fixed_routes(backend, operation, action, args, method, path):
    RabbitMQService(Store()).run('test', action, operation, args)
    assert backend[0][0] == (method, path)

def test_policy_upsert_needs_create(backend):
    with pytest.raises(InfraError, match='create permission'):
        RabbitMQService(Store(('update',))).run('test', 'update', 'update_policy', {'vhost': '/', 'name': 'p', 'pattern': '.*', 'definition': {}})
    assert backend == []

def test_policy_rejects_restricted_queue_scope(backend):
    with pytest.raises(InfraError, match='unrestricted'):
        RabbitMQService(Store(scope={'queues': ['q']})).run('test', 'update', 'update_policy', {'vhost': '/', 'name': 'p', 'pattern': '.*', 'definition': {}})
    assert backend == []

def test_bindings_filter_both_ends(monkeypatch):
    good = {'vhost': '/', 'source': 'x', 'destination': 'q', 'destination_type': 'queue'}
    monkeypatch.setattr(module, 'request_json', lambda *a, **kw: [good, {**good, 'source': 'private'}, {**good, 'destination': 'private'}])
    assert RabbitMQService(Store(scope={'exchanges': ['x'], 'queues': ['q']})).run('test', 'read', 'list_bindings', {'vhost': '/'})['data'] == [good]

def test_publish_default_exchange(backend):
    RabbitMQService(Store(scope={'exchanges':['amq.default'],'queues':['q']})).run('test','create','publish',{'vhost':'/','exchange':'','payload':'hello','routing_key':'q'})
    assert backend[0][0] == ('POST','/api/exchanges/%2F/amq.default/publish')

@pytest.mark.parametrize('exchange',['','amq.default'])
def test_default_exchange_enforces_queue_scope(backend,exchange):
    with pytest.raises(InfraError, match='outside'):
        RabbitMQService(Store(scope={'queues':['q']})).run('test','create','publish',{'vhost':'/','exchange':exchange,'payload':'hello','routing_key':'private'})
    assert backend == []
