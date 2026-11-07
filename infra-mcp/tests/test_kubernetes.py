import json
from types import SimpleNamespace
import pytest
from infra_mcp.kubernetes_service import KubernetesService, _run_bounded

class Profile:
    options = {'context': 'safe', 'kubeconfig': '/tmp/config'}
    timeout = 1
    scope = {'namespaces': ['allowed'], 'resources': ['pods', 'deployments', 'secrets']}
    def check_scope(self, kind, value):
        if self.scope.get(kind) and value not in self.scope[kind]:
            raise ValueError('scope denied')

def service(monkeypatch, output=None):
    calls = []
    def run(argv, data, timeout):
        calls.append((argv, data, timeout))
        return json.dumps(output or {'metadata': {'name': 'one'}})
    monkeypatch.setattr('infra_mcp.kubernetes_service._run_bounded', run)
    return KubernetesService(None), calls

def test_fixed_context_and_namespace(monkeypatch):
    s, calls = service(monkeypatch)
    s.execute(Profile(), 'get', {'namespace': 'allowed', 'resource': 'pods', 'name': 'one'})
    argv = calls[0][0]
    assert argv[:5] == ['kubectl', '--kubeconfig', '/tmp/config', '--context', 'safe']
    assert '--namespace' in argv and 'allowed' in argv

@pytest.mark.parametrize('args', [
    {'namespace': 'other', 'resource': 'pods', 'name': 'one'},
    {'namespace': 'allowed', 'resource': 'pods/../../secrets', 'name': 'one'},
    {'namespace': 'allowed', 'resource': 'pods', 'name': '--raw=/api'},
])
def test_invalid_target_never_calls_backend(monkeypatch, args):
    s, calls = service(monkeypatch)
    with pytest.raises(Exception): s.execute(Profile(), 'get', args)
    assert calls == []

@pytest.mark.parametrize('manifest', [
    {'apiVersion':'v1', 'kind':'Pod','metadata':{'name':'one','namespace':'other'}},
    {'apiVersion':'v1', 'kind':'Secret','metadata':{'name':'one'}},
    {'apiVersion':'v1', 'kind':'Pod','metadata':{'generateName':'auto-'}},
    {'apiVersion':'v1', 'kind':'Pod','metadata':{'name':'two'}},
])
def test_manifest_identity(monkeypatch, manifest):
    s, calls = service(monkeypatch)
    with pytest.raises(Exception):
        s.execute(Profile(), 'create', {'namespace':'allowed','resource':'pods','name':'one','manifest':manifest})
    assert not calls

@pytest.mark.parametrize('patch', [{'kind':'Secret'}, {'apiVersion':'v2'}, {'metadata':None}, {'metadata':{'name':'other'}}, {'metadata':{'namespace':'other'}}])
def test_patch_identity(monkeypatch, patch):
    s, calls = service(monkeypatch)
    with pytest.raises(Exception): s.execute(Profile(), 'patch', {'namespace':'allowed','resource':'pods','name':'one','patch':patch})
    assert not calls

@pytest.mark.parametrize('field,value', [('tail',-1),('tail',10001),('since_seconds',0),('limit_bytes',1048577)])
def test_log_bounds(monkeypatch, field, value):
    s, calls = service(monkeypatch)
    with pytest.raises(Exception): s.execute(Profile(), 'logs', {'namespace':'allowed','resource':'pods','name':'one',field:value})
    assert not calls

def test_secret_and_list_scope(monkeypatch):
    s, calls = service(monkeypatch, {'items':[{'kind':'Secret','metadata':{'name':'one','namespace':'allowed'},'data':{'key':'sensitive'}}, {'kind':'Secret','metadata':{'name':'two','namespace':'other'}}]})
    result = s.execute(Profile(), 'list', {'namespace':'allowed','resource':'secrets'})
    assert len(result['items']) == 1
    assert 'sensitive' not in json.dumps(result)

def test_timeout_and_output_bound():
    import sys
    with pytest.raises(Exception): _run_bounded([sys.executable,'-c','import time;time.sleep(2)'], None, .05)
    with pytest.raises(Exception): _run_bounded([sys.executable,'-c','import sys;sys.stdout.write("x"*2000000)'], None, 2)

def test_fixed_operation_permissions():
    assert KubernetesService.operations['restart'].action == 'update'
    assert KubernetesService.operations['scale'].action == 'update'
    assert 'exec' not in KubernetesService.operations and 'apply' not in KubernetesService.operations

def test_create_and_patch_use_stdin(monkeypatch):
    s, calls = service(monkeypatch)
    s.execute(Profile(), 'create', {'namespace':'allowed','resource':'pods','name':'one','manifest':{'apiVersion':'v1','kind':'Pod','metadata':{'name':'one'},'spec':{}}})
    assert calls[0][0][-4:] == ['-f','-','-o','json']
    assert json.loads(calls[0][1])['metadata']['name'] == 'one'
    s.execute(Profile(), 'patch', {'namespace':'allowed','resource':'pods','name':'one','patch':{'metadata':{'labels':{'app':'demo'}}}})
    assert '--patch-file=/dev/stdin' in calls[1][0]
    assert 'demo' not in ' '.join(calls[1][0])

def test_delete_accepts_kubectl_name_output_and_reports_request_only(monkeypatch):
    from infra_mcp.config import ACTIONS, Profile as RealProfile
    profile = RealProfile('session', 'kubernetes', {'kubeconfig': '/tmp/subadminconfig', 'context': 'session'}, ACTIONS,
                          {'namespaces': ['allowed'], 'resources': ['configmaps']})
    calls = []
    def run(argv, data, timeout):
        calls.append((argv, data, timeout))
        return 'configmap/example\n'
    monkeypatch.setattr('infra_mcp.kubernetes_service._run_bounded', run)
    result = KubernetesService(None).execute(profile, 'delete',
        {'namespace': 'allowed', 'resource': 'configmaps', 'name': 'example'})
    assert result == {'deletion_requested': True, 'namespace': 'allowed',
                      'resource': 'configmaps', 'name': 'example'}
    assert calls[0][0][-6:] == ['delete', 'configmaps', 'example', '--wait=false', '-o', 'name']
    assert calls[0][1] is None

def test_real_runner_disables_shell(monkeypatch):
    import subprocess
    import sys
    original = subprocess.Popen
    seen=[]
    def spawn(*args,**kwargs):
        seen.append(kwargs)
        return original(*args,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',spawn)
    assert _run_bounded([sys.executable,'-c','print("ok")'],None,2) == 'ok\n'
    assert seen[0]['shell'] is False

def test_mandatory_secret_redaction_reports_flag_when_generic_redaction_disabled(monkeypatch):
    from infra_mcp.config import Profile as RealProfile
    profile = RealProfile('local','kubernetes',{'context':'safe','kubeconfig':'/tmp/config','redact':False},frozenset({'read'}),{'namespaces':['allowed'],'resources':['secrets']})
    class Store:
        def get(self,service,connection): return profile
    monkeypatch.setattr('infra_mcp.kubernetes_service._run_bounded', lambda *args: json.dumps({'kind':'Secret','metadata':{'name':'one','namespace':'allowed','annotations':{'last-applied':'sensitive'}},'data':{'key':'sensitive'}}))
    result = KubernetesService(Store()).run('local','read','get',{'namespace':'allowed','resource':'secrets','name':'one'})
    assert result['redacted'] is True
    assert 'sensitive' not in json.dumps(result)

def test_check_connection_uses_fixed_connection_and_returns_no_cluster_details(monkeypatch):
    s, calls = service(monkeypatch, {'clientVersion':{'gitVersion':'client'},'serverVersion':{'gitVersion':'private'}})
    assert s.execute(Profile(),'check_connection',{}) == {'connected':True}
    assert calls[0][0] == ['kubectl','--kubeconfig','/tmp/config','--context','safe','version','--output=json']
    assert KubernetesService.operations['check_connection'].action == 'read'


def test_events_are_namespace_scoped_and_read_only(monkeypatch):
    from infra_mcp.config import ACTIONS, Profile as RealProfile, InfraError
    profile = RealProfile('session', 'kubernetes', {'kubeconfig': '/tmp/subadminconfig', 'context': 'session'}, ACTIONS,
                          {'namespaces': ['allowed'], 'resources': ['events'], 'names': ['one']})
    s, calls = service(monkeypatch, {'items': [
        {'kind': 'Event', 'metadata': {'name': 'one', 'namespace': 'allowed'}},
        {'kind': 'Event', 'metadata': {'name': 'two', 'namespace': 'allowed'}},
        {'kind': 'Event', 'metadata': {'name': 'one', 'namespace': 'other'}},
    ]})
    result = s.execute(profile, 'list', {'namespace': 'allowed', 'resource': 'events'})
    assert len(result['items']) == 1
    assert 'events' in calls[0][0]
    before = len(calls)
    for operation in ('create', 'patch', 'delete'):
        with pytest.raises(InfraError):
            s.execute(profile, operation, {'namespace': 'allowed', 'resource': 'events', 'name': 'one'})
    assert len(calls) == before
    with pytest.raises(InfraError):
        s.execute(profile, 'list', {'namespace': 'other', 'resource': 'events'})
