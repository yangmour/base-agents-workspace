import pytest
from infra_mcp.redis_service import RedisService
from infra_mcp.config import InfraError, Profile


class Config:
    def __init__(self, permissions=None):
        self.profile = Profile('test', 'redis', {'host': 'localhost'}, frozenset(permissions if permissions is not None else ['create','read','update','delete']), {'key_patterns': ['app:*']})
    def get(self, service, connection):
        return self.profile


class FakeRedis:
    def __init__(self):
        self.calls = []
        self.values = {'app:existing': b'abcdef', 'other:secret': b'private'}
    def type(self,key): return b'string' if key in self.values else b'none'
    def pipeline(self):
        owner = self
        class Pipeline:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def watch(self,key): pass
            def type(self,key): return owner.type(key)
            def multi(self): pass
            def set(self,*args,**kwargs): self.pending = (args,kwargs)
            def execute(self): return [owner.set(*self.pending[0],**self.pending[1])]
        return Pipeline()
    def close(self): pass
    def scan(self, cursor=0, **kwargs):
        self.calls.append(('scan', kwargs))
        return 0, list(self.values)
    def getrange(self, key, start, end):
        self.calls.append(('getrange', key, start, end))
        return self.values.get(key, b'')[start:end+1]
    def exists(self, key): return int(key in self.values)
    def set(self, key, value, **kwargs):
        self.calls.append(('set', key, value, kwargs))
        if kwargs.get('nx') and key in self.values: return None
        if kwargs.get('xx') and key not in self.values: return None
        self.values[key] = value.encode()
        return True
    def expire(self, key, seconds):
        self.calls.append(('expire', key, seconds))
        return key in self.values
    def delete(self, key):
        self.calls.append(('delete', key))
        return int(self.values.pop(key, None) is not None)


@pytest.fixture
def adapter(monkeypatch):
    fake = FakeRedis()
    service = RedisService(Config())
    monkeypatch.setattr(service, '_client', lambda p: fake)
    return service, fake


def test_scope_denied_before_backend(adapter):
    service, fake = adapter
    with pytest.raises(InfraError): service.run('test', 'read', 'get', {'key': 'other:secret'})
    assert fake.calls == []


def test_scan_filters_and_bounds(adapter):
    service, fake = adapter
    result = service.run('test', 'read', 'scan', {'limit': 1})
    assert result['data']['keys'] == ['app:existing']


def test_create_nx_and_update_xx(adapter):
    service, fake = adapter
    assert service.run('test','create','create',{'key':'app:new','value':'x'})['data']['created']
    assert fake.calls[-1][-1]['nx'] is True
    assert not service.run('test','create','create',{'key':'app:new','value':'y'})['data']['created']
    assert not service.run('test','update','update',{'key':'app:missing','value':'y'})['data']['updated']
    service.run('test','update','update',{'key':'app:new','value':'z'})
    assert fake.calls[-1][-1]['xx'] is True


def test_get_reads_only_bounded_range(adapter):
    service, fake = adapter
    result = service.run('test','read','get',{'key':'app:existing','max_bytes':3})
    assert result['data']['value'] == 'abc'
    assert result['data']['truncated'] is True
    assert ('getrange','app:existing',0,3) in fake.calls


def test_expiry_requires_update_and_delete_requires_delete(adapter):
    service, fake = adapter
    service.config = Config(['read'])
    for action, operation in [('update','expire'),('delete','delete')]:
        with pytest.raises(InfraError): service.run('test', action, operation, {'key':'app:existing','seconds':60})
    assert fake.calls == []


def test_errors_are_sanitized(adapter, monkeypatch):
    service, fake = adapter
    def fail(*args): raise RuntimeError('password=super-secret localhost')
    monkeypatch.setattr(fake, 'getrange', fail)
    with pytest.raises(InfraError) as error:
        service.run('test','read','get',{'key':'app:existing'})
    assert 'super-secret' not in str(error.value)


def test_client_security_settings(monkeypatch):
    import infra_mcp.redis_service as module
    captured = {}
    def constructor(**kwargs):
        captured.update(kwargs)
        return FakeRedis()
    monkeypatch.setattr(module.redis, 'ConnectionPool', constructor)
    monkeypatch.setattr(module.redis.Redis, 'from_pool', lambda connection_pool: connection_pool)
    monkeypatch.setattr(module, 'secret', lambda p, name: {'username':'user', 'password':'secret'}[name])
    profile = Profile('test','redis',{'host':'localhost','tls':True,'timeout':4}, frozenset(['read']), {})
    RedisService(Config())._client(profile)
    assert captured['connection_class'] is module.redis.SSLConnection
    assert captured['parser_class'] is module.BoundedRESP2Parser
    assert captured['protocol'] == 2
    assert captured['ssl_cert_reqs'] == 'required'
    assert captured['socket_connect_timeout'] == 4
    assert captured['socket_timeout'] == 4
    assert captured['retry'].get_retries() == 0


def test_invalid_write_arguments_do_not_access_backend(adapter):
    service, fake = adapter
    for arguments in [
        {'key':'app:x','value':'x'*65537},
        {'key':'app:x','value':'x','ttl_seconds':True},
    ]:
        with pytest.raises(InfraError): service.run('test','create','create',arguments)
    assert fake.calls == []


def test_expiry_and_deletion(adapter):
    service, fake = adapter
    assert service.run('test','update','expire',{'key':'app:existing','seconds':60})['data']['updated']
    assert service.run('test','delete','delete',{'key':'app:existing'})['data']['deleted']
    assert not service.run('test','delete','delete',{'key':'app:existing'})['data']['deleted']


def test_scan_excess_never_advances_past_omitted_keys(adapter):
    service, fake = adapter
    fake.values['app:second'] = b'x'
    with pytest.raises(InfraError) as error:
        service.run('test','read','scan',{'limit':1})
    assert error.value.code == 'result_too_large'


def test_expire_rejects_delete_semantics(adapter):
    service, fake = adapter
    with pytest.raises(InfraError):
        service.run('test','update','expire',{'key':'app:existing','seconds':0})
    assert fake.calls == []


def test_additional_operations(adapter, monkeypatch):
    service, fake = adapter
    monkeypatch.setattr(fake, 'ping', lambda: True, raising=False)
    monkeypatch.setattr(fake, 'type', lambda key: b'hash', raising=False)
    monkeypatch.setattr(fake, 'ttl', lambda key: 30, raising=False)
    monkeypatch.setattr(fake, 'hscan', lambda key, **kw: (0,{b'field':b'value'}), raising=False)
    monkeypatch.setattr(fake, 'hset', lambda key, mapping: 1, raising=False)
    monkeypatch.setattr(fake, 'hdel', lambda key, field: 1, raising=False)
    assert service.run('test','read','check_connection',{})['data']['reachable']
    assert service.run('test','read','inspect',{'key':'app:existing'})['data']['type'] == 'hash'
    assert service.run('test','read','read_collection',{'key':'app:existing'})['data']['items'] == {'field':'value'}
    assert service.run('test','update','hash_set',{'key':'app:existing','field':'a','value':'b'})['data']['added'] == 1
    assert service.run('test','delete','hash_delete',{'key':'app:existing','field':'a'})['data']['deleted'] == 1
    service.config = Config(['update'])
    with pytest.raises(InfraError): service.run('test','update','hash_set',{'key':'app:existing','field':'a','value':'b'})


@pytest.mark.parametrize('kind,method,payload', [
    ('list','lrange',[b'a',b'b']), ('set','sscan',(0,[b'a'])),
    ('zset','zrange',[(b'a',1.0)]), ('stream','xrange',[(b'1-0',{b'f':b'v'})]),
])
def test_collection_types(adapter, monkeypatch, kind, method, payload):
    service, fake = adapter
    monkeypatch.setattr(fake,'type',lambda key:kind.encode(),raising=False)
    monkeypatch.setattr(fake,method,lambda *args,**kwargs:payload,raising=False)
    result = service.run('test','read','read_collection',{'key':'app:existing','limit':2})
    assert result['data']['type'] == kind
    assert result['data']['items']


def test_update_rejects_nonstring_without_write(adapter, monkeypatch):
    service, fake = adapter
    monkeypatch.setattr(fake,'type',lambda key:b'hash',raising=False)
    with pytest.raises(InfraError):
        service.run('test','update','update',{'key':'app:existing','value':'replacement'})
    assert not [call for call in fake.calls if call[0]=='set']


def test_update_conflict_never_retries(adapter, monkeypatch):
    from redis.exceptions import WatchError
    service, fake = adapter
    class Pipeline:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def watch(self,key): pass
        def type(self,key): return b'string'
        def multi(self): pass
        def set(self,*args,**kwargs): pass
        def execute(self): raise WatchError()
    monkeypatch.setattr(fake,'pipeline',lambda:Pipeline(),raising=False)
    with pytest.raises(InfraError) as error:
        service.run('test','update','update',{'key':'app:existing','value':'replacement'})
    assert error.value.code == 'conflict'
    assert not [call for call in fake.calls if call[0]=='set']


@pytest.mark.parametrize('tls',[False,True])
def test_real_client_pool_configuration_without_connecting(tls):
    service = RedisService(Config())
    profile = Profile('test','redis',{'host':'localhost','tls':tls},frozenset(['read']),{})
    client = service._client(profile)
    try:
        assert client.auto_close_connection_pool is True
        pool = client.connection_pool
        connection = pool.connection_class(**pool.connection_kwargs)
        assert connection._sock is None
        assert type(connection._parser).__name__ == 'BoundedRESP2Parser'
    finally:
        client.close()
