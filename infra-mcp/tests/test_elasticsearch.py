import pytest
from infra_mcp.config import Profile, InfraError
from infra_mcp.elasticsearch_service import ElasticsearchService
import infra_mcp.elasticsearch_service as module

class Store:

    def __init__(self, scope=None):
        self.profile = Profile('test', 'elasticsearch', {}, frozenset(('create', 'read', 'update', 'delete')), scope or {})

    def get(self, *args):
        return self.profile

@pytest.fixture
def backend(monkeypatch):
    calls = []

    def request(*args, **kwargs):
        calls.append((args[1:], kwargs))
        return {}
    monkeypatch.setattr(module, 'request_json', request)
    return calls

def test_create_route_is_non_overwriting_and_escaped(backend):
    ElasticsearchService(Store()).run('test', 'create', 'create_doc', {'index': 'safe', 'id': 'a/b ?', 'document': {'a': 1}})
    assert backend == [(('PUT', '/safe/_create/a%2Fb%20%3F'), {'json': {'a': 1}})]

def test_update_partial_document_without_upsert(backend):
    ElasticsearchService(Store()).run('test', 'update', 'update_doc', {'index': 'safe', 'id': '1', 'document': {'a': 2}})
    assert backend == [(('POST', '/safe/_update/1'), {'json': {'doc': {'a': 2}, 'doc_as_upsert': False}})]

@pytest.mark.parametrize('extra', [{'upsert': {}}, {'doc_as_upsert': True}, {'script': {'source': 'bad'}}])
def test_update_rejects_upsert_and_scripts(backend, extra):
    with pytest.raises(InfraError):
        ElasticsearchService(Store()).run('test', 'update', 'update_doc', {'index': 'safe', 'id': '1', 'document': {}, **extra})
    assert backend == []

@pytest.mark.parametrize('args', [{'index': 'other', 'id': '1'}, {'index': 'safe'}, {'index': 'safe,*', 'id': '1'}, {'index': '_all', 'id': '1'}])
def test_scope_missing_target_and_multi_target_rejected(backend, args):
    with pytest.raises(InfraError):
        ElasticsearchService(Store({'indices': ['safe']})).run('test', 'read', 'get_doc', args)
    assert backend == []

def test_action_mismatch(backend):
    with pytest.raises(InfraError):
        ElasticsearchService(Store()).run('test', 'read', 'delete_doc', {'index': 'safe', 'id': '1'})
    assert backend == []

def test_list_filters_indices(monkeypatch):
    monkeypatch.setattr(module, 'request_json', lambda *a, **kw: [{'index': 'safe'}, {'index': 'private'}])
    assert ElasticsearchService(Store({'indices': ['safe']})).run('test', 'read', 'list_indices', {})['data'] == [{'index': 'safe'}]

@pytest.mark.parametrize('operation,action,args,method,path', [('create_index', 'create', {'index': 'safe'}, 'PUT', '/safe'), ('delete_index', 'delete', {'index': 'safe'}, 'DELETE', '/safe'), ('get_mapping', 'read', {'index': 'safe'}, 'GET', '/safe/_mapping'), ('get_doc', 'read', {'index': 'safe', 'id': '1'}, 'GET', '/safe/_doc/1'), ('delete_doc', 'delete', {'index': 'safe', 'id': '1'}, 'DELETE', '/safe/_doc/1'), ('search', 'read', {'index': 'safe', 'size': 3}, 'POST', '/safe/_search')])
def test_fixed_routes(backend, operation, action, args, method, path):
    ElasticsearchService(Store()).run('test', action, operation, args)
    assert backend[0][0] == (method, path)

@pytest.mark.parametrize('operation,args,method,path', [('check_connection', {}, 'GET', '/_cluster/health'), ('count', {'index': 'safe', 'query': {'match_all': {}}}, 'POST', '/safe/_count')])
def test_monitoring_routes(backend, operation, args, method, path):
    ElasticsearchService(Store()).run('test', 'read', operation, args)
    assert backend[0][0] == (method, path)
