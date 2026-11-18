"""Offline lifecycle tests: no kubectl process, credential, or cluster is used."""
import copy
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/k8s-session.py'
TIME = dt.datetime(2026, 11, 7, 0, 0, tzinfo=dt.timezone.utc)


@pytest.fixture
def cli(monkeypatch):
    assert SCRIPT.exists(), 'The persistent K8s lifecycle CLI has not been implemented'
    spec = importlib.util.spec_from_file_location('k8s_session', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'now', lambda: TIME)
    return module


class Cluster:
    """Small API simulator with real objects, ownership, and UID preconditions."""
    def __init__(self, cli):
        self.cli, self.context = cli, None
        self.objects, self.calls, self.deletes = {}, [], []
        self.expiry = TIME + dt.timedelta(hours=24)
        self.server, self.ns_uid = 'https://cluster.example', 'namespace-uid'
        self.lose_create = None
        self.conflict_create = None
        self.fail_delete = False
        self.ca = 'Q0E='

    def call(self, args, payload=None):
        self.calls.append((args, copy.deepcopy(payload)))
        if args[:2] == ['config', 'view']:
            return {'current-context': self.context or 'admin-context',
                    'clusters': [{'name': 'admin-cluster', 'cluster': {
                        'server': self.server, 'certificate-authority-data': self.ca,
                        'tls-server-name': 'k8s.example'}}],
                    'users': [{'user': {'token': 'ADMIN-SECRET', 'client-key-data': 'ADMIN-KEY',
                                       'exec': {'command': 'credential-command'}}}]}
        if 'token' in args:
            return {'status': {'token': 'CHILD-SECRET', 'expirationTimestamp': self.expiry.isoformat()}}
        if args[:1] == ['create']:
            obj = copy.deepcopy(payload)
            path = self.cli.object_path(obj['metadata']['namespace'], obj['metadata']['name'], obj['kind'])
            obj['metadata']['uid'] = 'uid-' + obj['kind']
            if obj['kind'] == self.conflict_create:
                obj['metadata']['labels'] = {'foreign': 'true'}
                self.objects[path] = obj
                raise self.cli.BackendError('already_exists')
            self.objects[path] = obj
            if obj['kind'] == self.lose_create:
                raise self.cli.BackendError('timeout')
            return copy.deepcopy(obj)
        raw = next(arg[6:] for arg in args if arg.startswith('--raw='))
        if args[0] == 'get':
            if raw == '/api/v1/namespaces/existing':
                return {'metadata': {'uid': self.ns_uid}}
            if raw not in self.objects:
                raise self.cli.BackendError('not_found')
            return copy.deepcopy(self.objects[raw])
        assert args[0] == 'delete'
        assert '-o' not in args
        if self.fail_delete:
            raise self.cli.BackendError('timeout')
        assert payload['preconditions']['uid'] == self.objects[raw]['metadata']['uid']
        self.deletes.append(raw)
        del self.objects[raw]
        return {'kind': 'Status', 'status': 'Success'}


def issue(cli, tmp_path, cluster=None, **kwargs):
    cluster = cluster or Cluster(cli)
    result = cli.issue(cluster, tmp_path / 'sessions', 'existing', **kwargs)
    return cluster, Path(result['session_dir'])


def receipt(path):
    return json.loads((path / 'session.json').read_text())


@pytest.mark.parametrize('hours', [24, 2])
def test_issue_retains_independent_credential_and_actual_expiry(cli, tmp_path, hours):
    cluster = Cluster(cli)
    cluster.expiry = TIME + dt.timedelta(hours=hours)
    _, path = issue(cli, tmp_path, cluster)
    child = json.loads((path / 'client/subadminconfig').read_text())
    profile = json.loads((path / 'client/profiles.json').read_text())['profiles']['kubernetes']['session']
    assert child['users'][0]['user'] == {'token': 'CHILD-SECRET'}
    assert 'ADMIN' not in json.dumps(child)
    assert 'exec' not in json.dumps(child)
    assert profile['kubeconfig'] == 'subadminconfig'
    assert profile['context'] == path.name
    assert profile['scope'] == {'namespaces': ['existing'], 'resources': ['configmaps']}
    assert profile['permissions'] == dict.fromkeys(['create', 'read', 'update', 'delete'], True)
    assert '--duration=24h' in next(args for args, _ in cluster.calls if 'token' in args)
    assert receipt(path)['expiration_timestamp'] == cluster.expiry.isoformat()
    assert 'SECRET' not in (path / 'session.json').read_text()
    assert path.stat().st_mode & 0o777 == 0o700
    for name in ['session.json', 'client/subadminconfig', 'client/profiles.json']:
        assert (path / name).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('hours', [25, 0, -1])
def test_invalid_actual_expiry_rolls_back_without_delivering(cli, tmp_path, hours):
    cluster = Cluster(cli)
    cluster.expiry = TIME + dt.timedelta(hours=hours)
    with pytest.raises(cli.SessionError):
        issue(cli, tmp_path, cluster)
    path = next((tmp_path / 'sessions').glob('ai-*'))
    assert not cluster.objects
    assert not (path / 'client/subadminconfig').exists()
    assert receipt(path)['state'] == 'revoked'


def test_readonly_and_subresource_rbac_follow_permissions(cli, tmp_path):
    cluster, _ = issue(cli, tmp_path, resources=['pods', 'deployments', 'events'], permissions=['read'])
    role = next(obj for obj in cluster.objects.values() if obj['kind'] == 'Role')
    assert all(set(rule['verbs']) <= {'get', 'list', 'watch'} for rule in role['rules'])
    assert any(rule['resources'] == ['pods/log'] and rule['verbs'] == ['get'] for rule in role['rules'])
    assert any(rule['resources'] == ['deployments/scale'] and rule['verbs'] == ['get'] for rule in role['rules'])
    assert all('secrets' not in rule['resources'] for rule in role['rules'])


def test_events_never_receive_write_verbs(cli, tmp_path):
    cluster, _ = issue(cli, tmp_path, resources=['events', 'deployments'], permissions=['read', 'update'])
    role = next(obj for obj in cluster.objects.values() if obj['kind'] == 'Role')
    assert all(rule['verbs'] == ['get', 'list', 'watch'] for rule in role['rules'] if rule['resources'] == ['events'])
    assert any(rule['resources'] == ['deployments/scale'] and rule['verbs'] == ['get', 'update', 'patch'] for rule in role['rules'])


@pytest.mark.parametrize('resource', ['secrets', 'serviceaccounts', 'nodes', 'pods/exec', '*', '../roles'])
def test_forbidden_resources_fail_before_any_backend_call(cli, tmp_path, resource):
    cluster = Cluster(cli)
    with pytest.raises(cli.SessionError):
        issue(cli, tmp_path, cluster, resources=[resource])
    assert cluster.calls == []


def test_revoke_is_ordered_uid_guarded_and_idempotent(cli, tmp_path):
    cluster, path = issue(cli, tmp_path)
    cli.revoke(cluster, path)
    assert [url.split('/')[-2] for url in cluster.deletes] == ['rolebindings', 'secrets', 'serviceaccounts', 'roles']
    assert receipt(path)['state'] == 'revoked'
    assert not (path / 'client/subadminconfig').exists()
    assert not (path / 'client/profiles.json').exists()
    cli.revoke(cluster, path)
    assert len(cluster.deletes) == 4


def test_revoke_does_not_delete_same_name_replacement(cli, tmp_path):
    cluster, path = issue(cli, tmp_path)
    rb = next(key for key in cluster.objects if '/rolebindings/' in key)
    cluster.objects[rb]['metadata']['uid'] = 'foreign-replacement'
    with pytest.raises(cli.SessionError):
        cli.revoke(cluster, path)
    assert rb in cluster.objects
    assert rb not in cluster.deletes
    assert receipt(path)['state'] == 'cleanup_pending'
    assert not (path / 'client/subadminconfig').exists()


@pytest.mark.parametrize('change', ['server', 'ns_uid', 'context'])
def test_wrong_identity_refuses_remote_cleanup_but_removes_local_credentials(cli, tmp_path, change):
    cluster, path = issue(cli, tmp_path)
    setattr(cluster, change, 'https://wrong.example' if change == 'server' else 'wrong-identity')
    with pytest.raises(cli.SessionError):
        cli.revoke(cluster, path)
    assert not cluster.deletes
    assert len(cluster.objects) == 4
    assert not (path / 'client/subadminconfig').exists()
    assert receipt(path)['state'] == 'cleanup_pending'


def test_lost_create_response_recovers_only_matching_nonce(cli, tmp_path):
    cluster = Cluster(cli)
    cluster.lose_create = 'Secret'
    with pytest.raises(cli.SessionError):
        issue(cli, tmp_path, cluster)
    assert not cluster.objects
    path = next((tmp_path / 'sessions').glob('ai-*'))
    assert receipt(path)['state'] == 'revoked'


def test_already_exists_does_not_claim_or_delete_foreign_object(cli, tmp_path):
    cluster = Cluster(cli)
    cluster.conflict_create = 'Secret'
    with pytest.raises(cli.SessionError):
        issue(cli, tmp_path, cluster)
    assert len(cluster.objects) == 1
    assert next(iter(cluster.objects.values()))['metadata']['labels'] == {'foreign': 'true'}


def test_revoke_failure_keeps_retry_receipt_but_removes_local_credentials(cli, tmp_path):
    cluster, path = issue(cli, tmp_path)
    cluster.fail_delete = True
    with pytest.raises(cli.SessionError):
        cli.revoke(cluster, path)
    assert receipt(path)['state'] == 'cleanup_pending'
    assert not (path / 'client/subadminconfig').exists()
    cluster.fail_delete = False
    cli.revoke(cluster, path)
    assert receipt(path)['state'] == 'revoked'
    assert not cluster.objects


def test_cleanup_expired_preserves_active_and_handles_expired(cli, tmp_path, monkeypatch):
    cluster, first = issue(cli, tmp_path)
    _, second = issue(cli, tmp_path, cluster)
    state = receipt(first)
    state['expiration_timestamp'] = (TIME - dt.timedelta(seconds=1)).isoformat()
    cli.atomic_json(first / 'session.json', state)
    result = cli.cleanup_expired(cluster, tmp_path / 'sessions')
    assert result['errors'] == []
    assert receipt(first)['state'] == 'revoked'
    assert receipt(second)['state'] == 'active'
    assert (second / 'client/subadminconfig').exists()


def test_status_is_local_and_marks_expiration(cli, tmp_path):
    _, path = issue(cli, tmp_path)
    result = cli.status(path)
    assert result['online_verified'] is False
    assert result['expired'] is False
    assert result['state'] == 'active'


def test_flock_prevents_other_process_from_revoking(cli, tmp_path):
    _, path = issue(cli, tmp_path)
    with cli.session_lock(path):
        code = "import fcntl,os,sys; f=os.open(sys.argv[1],os.O_RDWR); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)"
        result = subprocess.run([sys.executable, '-c', code, str(path / '.lock')], capture_output=True)
    assert result.returncode != 0
    assert b'BlockingIOError' in result.stderr


def test_cleanup_skips_locked_session(cli, tmp_path):
    cluster, path = issue(cli, tmp_path)
    state = receipt(path)
    state['state'] = 'cleanup_pending'
    cli.atomic_json(path / 'session.json', state)
    with cli.session_lock(path):
        result = cli.cleanup_expired(cluster, tmp_path / 'sessions')
    assert result['skipped_locked'] == [path.name]
    assert not cluster.deletes


def test_unsafe_receipt_and_symlinks_never_reach_backend(cli, tmp_path):
    cluster, path = issue(cli, tmp_path)
    state = receipt(path)
    state['namespace'] = '../../other'
    cli.atomic_json(path / 'session.json', state)
    count = len(cluster.calls)
    with pytest.raises(cli.SessionError):
        cli.revoke(cluster, path)
    assert len(cluster.calls) == count
    alias = tmp_path / 'alias'
    alias.symlink_to(path, target_is_directory=True)
    with pytest.raises(cli.SessionError):
        cli.status(alias)


def test_persistent_lifecycle_cli_is_available():
    assert SCRIPT.exists(), 'Persistent issue/status/revoke/cleanup-expired CLI is missing'


@pytest.mark.parametrize('permission', ['create', 'update'])
def test_write_only_does_not_implicitly_add_read(cli, tmp_path, permission):
    cluster, _ = issue(cli, tmp_path, resources=['pods', 'deployments'], permissions=[permission])
    role = next(obj for obj in cluster.objects.values() if obj['kind'] == 'Role')
    assert all(not (set(rule['verbs']) & {'get', 'list', 'watch'}) for rule in role['rules'])


def test_namespace_replacement_during_issue_never_delivers_token(cli, tmp_path):
    cluster = Cluster(cli)
    original = cluster.call
    def replace_namespace(args, payload=None):
        result = original(args, payload)
        if args[:1] == ['create']:
            cluster.ns_uid = 'replaced-namespace'
        return result
    cluster.call = replace_namespace
    with pytest.raises(cli.SessionError):
        issue(cli, tmp_path, cluster)
    path = next((tmp_path / 'sessions').glob('ai-*'))
    assert not (path / 'client/subadminconfig').exists()
    assert receipt(path)['state'] == 'cleanup_pending'


def test_interrupt_during_revoke_is_never_recorded_as_revoked(cli, tmp_path):
    cluster, path = issue(cli, tmp_path)
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt()
    cluster.call = interrupted
    with pytest.raises((KeyboardInterrupt, cli.SessionError)):
        cli.revoke(cluster, path)
    assert receipt(path)['state'] == 'cleanup_pending'
    assert not receipt(path)['objects_absent']
    assert not (path / 'client/subadminconfig').exists()


def test_receipt_storage_failure_still_removes_local_credential(cli, tmp_path, monkeypatch):
    cluster, path = issue(cli, tmp_path)
    def disk_full(*args, **kwargs):
        raise OSError('disk full')
    monkeypatch.setattr(cli, 'save', disk_full)
    with pytest.raises(OSError):
        cli.revoke(cluster, path)
    assert not (path / 'client/subadminconfig').exists()


def test_finalizer_retains_cleanup_pending_until_absence(cli, tmp_path, monkeypatch):
    cluster, path = issue(cli, tmp_path)
    original = cluster.call
    def finalizer(args, payload=None):
        if args[0] == 'delete':
            return {'status': 'Success'}
        return original(args, payload)
    cluster.call = finalizer
    monkeypatch.setattr(cli.time, 'sleep', lambda _: None)
    with pytest.raises(cli.SessionError):
        cli.revoke(cluster, path)
    assert receipt(path)['state'] == 'cleanup_pending'
    assert not receipt(path)['objects_absent']
    assert not (path / 'client/subadminconfig').exists()


def test_namespace_already_absent_can_be_cleaned(cli, tmp_path):
    cluster, path = issue(cli, tmp_path)
    cluster.objects.clear()
    original = cluster.call
    def no_namespace(args, payload=None):
        if args == ['get', '--raw=/api/v1/namespaces/existing']:
            raise cli.BackendError('not_found')
        return original(args, payload)
    cluster.call = no_namespace
    assert cli.revoke(cluster, path)['objects_absent'] is True
    assert receipt(path)['state'] == 'revoked'


def test_lost_create_does_not_recover_wrong_nonce(cli, tmp_path):
    cluster = Cluster(cli)
    original = cluster.call
    def lost_foreign(args, payload=None):
        result = original(args, payload)
        if args[:1] == ['create'] and payload['kind'] == 'Secret':
            path = cli.object_path('existing', payload['metadata']['name'], 'Secret')
            cluster.objects[path]['metadata']['labels'][cli.LABEL] = 'foreign'
            raise cli.BackendError('timeout')
        return result
    cluster.call = lost_foreign
    with pytest.raises(cli.SessionError):
        issue(cli, tmp_path, cluster)
    assert len(cluster.objects) == 1
    path = next((tmp_path / 'sessions').glob('ai-*'))
    assert receipt(path)['state'] == 'cleanup_pending'


def test_backend_diagnostics_never_expose_credentials(cli, tmp_path, monkeypatch):
    config = tmp_path / 'fake-config'
    config.write_text('not a real credential')
    def failed_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 1, stdout='CHILD-SECRET', stderr='ADMIN-SECRET Error from server (Forbidden):')
    monkeypatch.setattr(cli.subprocess, 'run', failed_run)
    backend = cli.Kubectl(config)
    with pytest.raises(cli.BackendError) as raised:
        backend.call(['get', '--raw=/version'])
    assert str(raised.value) == 'Administrator request failed: forbidden'


@pytest.mark.parametrize('field,value', [('server', 'http://unsafe.example'), ('server', 'https://user:pass@cluster.example'), ('proxy-url', 'http://proxy'), ('insecure-skip-tls-verify', True), ('certificate-authority-data', '')])
def test_unsafe_cluster_connection_is_rejected_before_creating_objects(cli, tmp_path, field, value):
    cluster = Cluster(cli)
    original = cluster.call
    def unsafe(args, payload=None):
        result = original(args, payload)
        if args[:2] == ['config', 'view']:
            result['clusters'][0]['cluster'][field] = value
        return result
    cluster.call = unsafe
    with pytest.raises(cli.SessionError):
        issue(cli, tmp_path, cluster)
    assert not cluster.objects


def test_successful_revoke_stays_terminal_after_namespace_changes(cli, tmp_path):
    cluster, path = issue(cli, tmp_path)
    cli.revoke(cluster, path)
    cluster.ns_uid = 'recreated-namespace'
    assert cli.revoke(cluster, path)['state'] == 'revoked'
    assert receipt(path)['objects_absent'] is True


def test_crash_during_child_write_leaves_no_untracked_token_after_cleanup(cli, tmp_path):
    code = '''import importlib.util, json, os, runpy, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("session", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
tests = runpy.run_path(sys.argv[2])
m.now = lambda: tests["TIME"]
original_dump = json.dump
def crash_after_token_write(value, stream, **kwargs):
    original_dump(value, stream, **kwargs)
    if isinstance(value, dict) and value.get("kind") == "Config":
        stream.flush()
        os._exit(17)
m.json.dump = crash_after_token_write
m.issue(tests["Cluster"](m), Path(sys.argv[3]), "existing")
'''
    root = tmp_path / 'sessions'
    process = subprocess.run([sys.executable, '-c', code, str(SCRIPT), __file__, str(root)], capture_output=True)
    assert process.returncode == 17, process.stderr.decode()
    path = next(root.glob('ai-*'))
    cli.cleanup_expired(Cluster(cli), root)
    assert receipt(path)['state'] == 'revoked'
    assert not any('CHILD-SECRET' in file.read_text() for file in path.rglob('*') if file.is_file())


def test_issue_failure_includes_retry_directory_without_secrets(cli, tmp_path, monkeypatch, capsys):
    cluster = Cluster(cli)
    cluster.expiry = TIME - dt.timedelta(seconds=1)
    monkeypatch.setattr(cli, 'Kubectl', lambda *args: cluster)
    result = cli.main(['issue', '--admin-config', '/unused', '--namespace', 'existing', '--state-root', str(tmp_path / 'sessions')])
    output = capsys.readouterr()
    assert result == 1
    assert output.out == ''
    failure = json.loads(output.err)
    assert Path(failure['session_dir']).joinpath('session.json').exists()
    assert 'SECRET' not in output.err


def test_cleanup_continues_after_a_failed_session(cli, tmp_path):
    cluster, first = issue(cli, tmp_path)
    _, second = issue(cli, tmp_path, cluster)
    for path in (first, second):
        data = receipt(path)
        data['state'] = 'cleanup_pending'
        cli.atomic_json(path / 'session.json', data)
    foreign = next(key for key in cluster.objects if first.name in key and '/rolebindings/' in key)
    cluster.objects[foreign]['metadata']['uid'] = 'new-uid'
    result = cli.cleanup_expired(cluster, tmp_path / 'sessions')
    assert len(result['errors']) == 1
    assert receipt(first)['state'] == 'cleanup_pending'
    assert receipt(second)['state'] == 'revoked'


def test_cli_cleanup_returns_failure_for_partial_errors(cli, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'Kubectl', lambda *args: Cluster(cli))
    monkeypatch.setattr(cli, 'cleanup_expired', lambda *args: {'errors': [{'session': 'test', 'error': 'timeout'}]})
    assert cli.main(['cleanup-expired', '--admin-config', '/unused']) == 1
    assert json.loads(capsys.readouterr().out)['errors']
