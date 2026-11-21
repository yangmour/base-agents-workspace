#!/usr/bin/env python3
"""Single trusted host CLI for persistent, namespace-scoped Kubernetes sessions."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LABEL = 'infra-mcp-ownership'
KINDS = ('RoleBinding', 'Secret', 'ServiceAccount', 'Role')
RESOURCE_GROUPS = {
    'pods': '', 'services': '', 'configmaps': '', 'persistentvolumeclaims': '',
    'events': '', 'deployments': 'apps', 'statefulsets': 'apps', 'daemonsets': 'apps',
    'jobs': 'batch', 'cronjobs': 'batch', 'ingresses': 'networking.k8s.io',
}
PERMISSIONS = {'create': ['create'], 'read': ['get', 'list', 'watch'],
               'update': ['update', 'patch'], 'delete': ['delete']}
SESSION_RE = re.compile(r'ai-[0-9a-f]{24}\Z')
NAME_RE = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z')
PATCH_KINDS = ('pods', 'configmaps', 'deployments', 'statefulsets', 'daemonsets')


class SessionError(Exception):
    pass


class BackendError(SessionError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__('Administrator request failed: ' + reason)


class Locked(SessionError):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc)


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.utcoffset() is None:
            raise ValueError()
        return parsed
    except (ValueError, TypeError, AttributeError):
        raise SessionError('Invalid timezone-aware expiry in session data') from None


def safe_path(value, *, directory=False, private=False):
    path = Path(value).expanduser().absolute()
    if '..' in path.parts:
        raise SessionError('Parent traversal is not allowed')
    # A trusted host is required; reject symlinks instead of silently following them.
    for parent in [*reversed(path.parents), path]:
        if parent.is_symlink():
            raise SessionError('Symlink paths are not allowed')
    if path.exists():
        info = path.lstat()
        if directory and not stat.S_ISDIR(info.st_mode):
            raise SessionError('Expected a directory')
        if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
            raise SessionError('Expected a regular, unlinked file')
        if private and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise SessionError('Session storage must be owned by this user and private')
    return path


def atomic_json(path, data):
    path = safe_path(path)
    fd, temporary = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def private_json(path, data):
    # Write credentials only to tracked filenames: SIGKILL must not leave a token temp file.
    path = safe_path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(data, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def session_lock(path):
    path = safe_path(path, directory=True, private=True)
    if not path.is_dir():
        raise SessionError('Session directory does not exist')
    lock = safe_path(path / '.lock', private=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Locked('Session is busy; retry later') from None
        yield
    finally:
        os.close(fd)


class Kubectl:
    def __init__(self, admin_config, context=None):
        self.admin_config = safe_path(admin_config)
        if not self.admin_config.is_file():
            raise SessionError('Administrator kubeconfig does not exist')
        self.context = context

    def call(self, args, payload=None):
        command = ['kubectl', '--kubeconfig', str(self.admin_config), '--request-timeout=15s']
        if self.context:
            command += ['--context', self.context]
        try:
            result = subprocess.run(command + args, input=json.dumps(payload) if payload is not None else None,
                                    capture_output=True, text=True, timeout=22)
        except subprocess.TimeoutExpired:
            raise BackendError('timeout') from None
        except OSError:
            raise BackendError('cannot_execute_kubectl') from None
        # Never expose stderr/stdout: exec plugins and API errors may echo credentials.
        if result.returncode:
            reason = next((label for marker, label in [
                ('(notfound)', 'not_found'), ('(alreadyexists)', 'already_exists'),
                ('(conflict)', 'uid_conflict'), ('(forbidden)', 'forbidden'),
                ('(unauthorized)', 'unauthorized'), ('x509', 'tls_error'),
                ('deadline exceeded', 'timeout'), ('timeout', 'timeout'), ('timed out', 'timeout'),
                ('connection refused', 'connection_refused'), ('connection reset', 'connection_reset'),
                ('unexpected eof', 'connection_closed'), (': eof', 'connection_closed'),
                ('no route to host', 'network_unreachable'), ('no such host', 'dns_error'),
                ('serviceunavailable', 'service_unavailable')
            ] if marker in result.stderr.lower()), 'request_error')
            raise BackendError(reason)
        try:
            return json.loads(result.stdout)
        except ValueError:
            raise BackendError('invalid_json') from None


def connection(backend):
    raw = backend.call(['config', 'view', '--minify', '--flatten', '--raw', '-o', 'json'])
    try:
        cluster = raw['clusters'][0]['cluster']
        context = raw['current-context']
        parsed = urlsplit(cluster['server'])
        ca = base64.b64decode(cluster['certificate-authority-data'], validate=True)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or not ca or cluster.get('insecure-skip-tls-verify')
                or cluster.get('proxy-url') or not isinstance(context, str) or not context):
            raise ValueError()
        child = {key: cluster[key] for key in ('server', 'certificate-authority-data', 'tls-server-name') if key in cluster}
    except (KeyError, IndexError, TypeError, ValueError):
        raise SessionError('Require a direct HTTPS cluster with embedded CA and verified TLS') from None
    fingerprint = hashlib.sha256(json.dumps(child, sort_keys=True).encode()).hexdigest()
    backend.context = context
    return child, context, fingerprint


def object_path(namespace, name, kind):
    plural = {'ServiceAccount': 'serviceaccounts', 'Secret': 'secrets', 'Role': 'roles', 'RoleBinding': 'rolebindings'}[kind]
    prefix = '/api/v1' if kind in ('Secret', 'ServiceAccount') else '/apis/rbac.authorization.k8s.io/v1'
    return f'{prefix}/namespaces/{namespace}/{plural}/{name}'


def existing(backend, path):
    try:
        return backend.call(['get', '--raw=' + path])
    except BackendError as error:
        if error.reason == 'not_found':
            return None
        raise


def selected(values, choices, label):
    if not values or any(value not in choices for value in values) or len(set(values)) != len(values):
        raise SessionError('Invalid or duplicate ' + label)
    return list(values)


def rules_for(resources, permissions):
    rules = []
    verbs = [verb for permission in PERMISSIONS if permission in permissions for verb in PERMISSIONS[permission]]
    for resource in resources:
        allowed = PERMISSIONS['read'] if resource == 'events' and 'read' in permissions else ([] if resource == 'events' else verbs)
        if allowed:
            rules.append({'apiGroups': ['', 'events.k8s.io'] if resource == 'events' else [RESOURCE_GROUPS[resource]],
                          'resources': [resource], 'verbs': allowed})
        if resource == 'pods' and 'read' in permissions:
            rules.append({'apiGroups': [''], 'resources': ['pods/log'], 'verbs': ['get']})
        if resource in ('deployments', 'statefulsets'):
            scale = (['get'] if 'read' in permissions else []) + (['update', 'patch'] if 'update' in permissions else [])
            if scale:
                rules.append({'apiGroups': ['apps'], 'resources': [resource + '/scale'], 'verbs': scale})
    if not rules:
        raise SessionError('The requested resources and permissions grant no supported operations')
    return rules


def load_receipt(path):
    path = safe_path(path, directory=True, private=True)
    source = safe_path(path / 'session.json', private=True)
    try:
        if source.stat().st_size > 100000:
            raise ValueError()
        data = json.loads(source.read_text())
        if (data['version'] != 1 or not SESSION_RE.fullmatch(data['session']) or data['session'] != path.name
                or not NAME_RE.fullmatch(data['namespace'])
                or not re.fullmatch('[0-9a-f]{32}', data['nonce'])
                or not re.fullmatch('[0-9a-f]{64}', data['cluster_fingerprint'])
                or not isinstance(data['context'], str) or not data['context']
                or not isinstance(data['namespace_uid'], str) or not data['namespace_uid']
                or data['state'] not in ('issuing', 'active', 'cleanup_pending', 'revoked')
                or not isinstance(data['objects'], dict) or set(data['objects']) - set(KINDS)):
            raise ValueError()
        for record in data['objects'].values():
            if (type(record['attempted']) is not bool or
                    (record['uid'] is not None and (not isinstance(record['uid'], str) or not record['uid']))):
                raise ValueError()
        if data.get('expiration_timestamp') is not None:
            timestamp(data['expiration_timestamp'])
        if data['state'] == 'active' and not data.get('expiration_timestamp'):
            raise ValueError()
    except (KeyError, TypeError, ValueError, OSError):
        raise SessionError('Missing or unsafe session receipt') from None
    return data


def save(path, data):
    atomic_json(path / 'session.json', data)


def summary(path, data):
    expiry = data.get('expiration_timestamp')
    return {'session_dir': str(path), 'session': data['session'], 'state': data['state'],
            'namespace': data['namespace'], 'expiration_timestamp': expiry,
            'expired': timestamp(expiry) <= now() if expiry else None,
            'child_config': str(path / 'client/subadminconfig'),
            'profiles': str(path / 'client/profiles.json'),
            'online_verified': False, 'objects_absent': data.get('objects_absent', False)}


def remove_local(path):
    client = safe_path(path / 'client', directory=True, private=True)
    if not client.exists():
        return
    for name in ('subadminconfig', 'profiles.json'):
        target = safe_path(client / name)
        target.unlink(missing_ok=True)


def cleanup_locked(backend, path, data):
    errors = []
    remote_complete = False
    data['state'] = 'cleanup_pending'
    try:
        save(path, data)
        if backend.context is not None and backend.context != data['context']:
            raise SessionError('Cleanup refused: context differs from receipt')
        backend.context = data['context']
        _, context, fingerprint = connection(backend)
        if context != data['context'] or fingerprint != data['cluster_fingerprint']:
            raise SessionError('Cleanup refused: cluster identity differs from receipt')
        namespace = existing(backend, '/api/v1/namespaces/' + data['namespace'])
        if namespace is not None and namespace.get('metadata', {}).get('uid') != data['namespace_uid']:
            raise SessionError('Cleanup refused: namespace UID differs from receipt')
        for kind in KINDS:
            record = data['objects'].get(kind)
            if not record or not record['attempted']:
                continue
            try:
                resource_path = object_path(data['namespace'], data['session'], kind)
                current = existing(backend, resource_path)
                if current is not None:
                    meta = current.get('metadata', {})
                    # Only a lost create response may be recovered through the random ownership nonce.
                    if record['uid'] is None and meta.get('labels', {}).get(LABEL) == data['nonce']:
                        record['uid'] = meta.get('uid')
                        save(path, data)
                    if not record['uid'] or record['uid'] != meta.get('uid'):
                        raise SessionError('Cleanup refused: object UID or ownership differs')
                    try:
                        backend.call(['delete', '--raw=' + resource_path, '-f', '-'], {
                            'apiVersion': 'v1', 'kind': 'DeleteOptions',
                            'preconditions': {'uid': record['uid']}, 'propagationPolicy': 'Background'})
                    except BackendError as error:
                        if error.reason != 'not_found':
                            raise
                    # A successful delete response may only mean deletion was scheduled (finalizers).
                    for attempt in range(6):
                        current = existing(backend, resource_path)
                        if current is None:
                            break
                        if current.get('metadata', {}).get('uid') != record['uid']:
                            raise SessionError('Cleanup refused: object was replaced during deletion')
                        if attempt == 5:
                            raise SessionError('Object deletion is still pending')
                        time.sleep(0.2)
                record['absent_verified'] = True
                save(path, data)
            except SessionError as error:
                errors.append(str(error))
        remote_complete = True
    except SessionError as error:
        errors.append(str(error))
    finally:
        if not remote_complete and not errors:
            errors.append('Cleanup interrupted before object absence was confirmed')
        try:
            remove_local(path)
        except (SessionError, OSError):
            errors.append('Local credential removal failed; inspect session client directory')
        data['objects_absent'] = not errors
        data['state'] = 'cleanup_pending' if errors else 'revoked'
        data['cleanup_errors'] = errors
        save(path, data)
    if errors:
        raise SessionError('; '.join(dict.fromkeys(errors)))
    return summary(path, data)


def verify_namespace(backend, data):
    namespace = existing(backend, '/api/v1/namespaces/' + data['namespace'])
    if not namespace or namespace.get('metadata', {}).get('uid') != data['namespace_uid']:
        raise SessionError('Namespace changed during issuance; credentials were not delivered')


def group_patch_targets(targets):
    grouped = {}
    for target in targets:
        kind, _, name = target.partition('/')
        if (kind not in PATCH_KINDS or len(name) > 253
                or not all(NAME_RE.fullmatch(label) for label in name.split('.'))):
            raise SessionError(f'Expected KIND/NAME with an exact name and kind in {", ".join(PATCH_KINDS)}')
        names = grouped.setdefault(kind, [])
        if name in names:
            raise SessionError('Duplicate patch target')
        names.append(name)
    if not grouped:
        raise SessionError('Named patch grants require at least one target')
    return grouped


def issue(backend, state_root, namespace, resources=None, permissions=None, *, patch_targets=None, release_lifecycle=False):
    if not NAME_RE.fullmatch(namespace):
        raise SessionError('Invalid namespace name')
    if release_lifecycle and not patch_targets:
        raise SessionError('A managed release requires named patch targets')
    targets = {}
    if patch_targets is not None:
        if resources is not None or permissions is not None:
            raise SessionError('--patch-target cannot be combined with --resources or --permissions')
        targets = group_patch_targets(patch_targets)
        resources, permissions = list(targets), ['read', 'update']
        rules = [{'apiGroups': [RESOURCE_GROUPS[kind]], 'resources': [kind],
                  'resourceNames': names, 'verbs': ['get', 'patch']} for kind, names in targets.items()]
        diagnostics = release_lifecycle and namespace == 'higress-system'
        if diagnostics:
            rules.extend([{'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get', 'list']},
                          {'apiGroups': ['', 'events.k8s.io'], 'resources': ['events'], 'verbs': ['get', 'list']}])
        hours = 1
    else:
        resources = selected(['configmaps'] if resources is None else resources, RESOURCE_GROUPS, 'resources')
        permissions = selected(list(PERMISSIONS) if permissions is None else permissions, PERMISSIONS, 'permissions')
        rules = rules_for(resources, permissions)
        hours = 24
    cluster, context, fingerprint = connection(backend)
    # A failed read here has no session or cluster objects to clean up.
    for attempt in range(3):
        try:
            ns = existing(backend, '/api/v1/namespaces/' + namespace)
            break
        except BackendError as error:
            transient = error.reason in ('timeout', 'connection_refused', 'connection_reset',
                                         'connection_closed', 'service_unavailable')
            if not transient or attempt == 2:
                raise SessionError(f'Namespace preflight ({namespace}) failed: {error.reason}') from None
            time.sleep(2 ** attempt)
    if not ns or not ns.get('metadata', {}).get('uid'):
        raise SessionError('An existing namespace is required')
    root = safe_path(state_root, directory=True, private=True)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    name, nonce = 'ai-' + secrets.token_hex(12), secrets.token_hex(16)
    path = root / name
    path.mkdir(mode=0o700, exist_ok=False)
    data = {'version': 1, 'session': name, 'namespace': namespace, 'namespace_uid': ns['metadata']['uid'],
            'nonce': nonce, 'context': context, 'cluster_fingerprint': fingerprint,
            'created_at': now().isoformat(), 'requested_duration': f'{hours}h', 'expiration_timestamp': None,
            'state': 'issuing', 'resources': resources, 'permissions': permissions, 'objects': {}}
    if release_lifecycle:
        data['cleanup_on_expiry'] = True
    if targets:
        data['patch_targets'] = targets
    with session_lock(path):
        save(path, data)
        success = False
        try:
            for kind in ('ServiceAccount', 'Secret', 'Role', 'RoleBinding'):
                verify_namespace(backend, data)
                manifest = {'apiVersion': 'v1' if kind in ('ServiceAccount', 'Secret') else 'rbac.authorization.k8s.io/v1',
                            'kind': kind, 'metadata': {'name': name, 'namespace': namespace, 'labels': {LABEL: nonce}}}
                if kind == 'ServiceAccount':
                    manifest['automountServiceAccountToken'] = False
                elif kind == 'Secret':
                    manifest['type'] = 'Opaque'
                elif kind == 'Role':
                    manifest['rules'] = rules
                else:
                    manifest.update(subjects=[{'kind': 'ServiceAccount', 'name': name, 'namespace': namespace}],
                                    roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name})
                record = {'attempted': True, 'uid': None}
                data['objects'][kind] = record
                save(path, data)  # Persist intent before sending a request whose response could be lost.
                try:
                    created = backend.call(['create', '-f', '-', '-o', 'json'], manifest)
                except BackendError as error:
                    if error.reason == 'already_exists':
                        record['attempted'] = False
                        save(path, data)
                    raise
                record['uid'] = created.get('metadata', {}).get('uid')
                if not record['uid']:
                    raise SessionError('Created object response omitted its UID')
                save(path, data)
            verify_namespace(backend, data)
            response = backend.call(['-n', namespace, 'create', 'token', name,
                '--bound-object-kind=Secret', '--bound-object-name=' + name,
                '--bound-object-uid=' + data['objects']['Secret']['uid'], f'--duration={hours}h', '-o', 'json'])
            token_status = response.get('status', {})
            expires = timestamp(token_status.get('expirationTimestamp'))
            if not now() < expires <= now() + dt.timedelta(hours=hours):
                raise SessionError('Actual token expiry exceeds the requested duration or is already expired')
            token = token_status.get('token')
            if not isinstance(token, str) or not token:
                raise SessionError('TokenRequest returned no token')
            verify_namespace(backend, data)
            data['expiration_timestamp'] = token_status['expirationTimestamp']
            save(path, data)
            client = path / 'client'
            client.mkdir(mode=0o700)
            child = {'apiVersion': 'v1', 'kind': 'Config', 'current-context': name,
                     'clusters': [{'name': 'session-cluster', 'cluster': cluster}],
                     'users': [{'name': name, 'user': {'token': token}}],
                     'contexts': [{'name': name, 'context': {'cluster': 'session-cluster', 'user': name, 'namespace': namespace}}]}
            profile = {'kubeconfig': 'subadminconfig', 'context': name, 'timeout': 20,
                       'permissions': {'read': 'read' in permissions},
                       'allow_after_approval': [key for key in permissions if key != 'read'],
                       'scope': {'namespaces': [namespace], 'resources': resources}}
            profiles = {'session': profile}
            if targets:
                profiles = {'release-' + kind: {**profile, 'scope': {
                    'namespaces': [namespace], 'resources': [kind], 'names': names}}
                    for kind, names in targets.items()}
                if diagnostics:
                    profiles['rollout-diagnostics'] = {**profile, 'permissions': {'read': True},
                        'allow_after_approval': [], 'scope': {'namespaces': [namespace], 'resources': ['pods', 'events']}}
            private_json(client / 'subadminconfig', child)
            private_json(client / 'profiles.json', {'profiles': {'kubernetes': profiles}})
            data['state'] = 'active'
            save(path, data)
            success = True
            return summary(path, data)
        except (SessionError, OSError, KeyboardInterrupt) as error:
            error.session_dir = str(path)
            raise
        finally:
            if not success:
                try:
                    cleanup_locked(backend, path, data)
                except (SessionError, OSError):
                    pass  # Receipt remains cleanup_pending; do not hide the original issue failure.


def revoke(backend, session_dir):
    path = safe_path(session_dir, directory=True, private=True)
    with session_lock(path):
        data = load_receipt(path)
        if data['state'] == 'revoked' and data.get('objects_absent') is True:
            remove_local(path)
            return summary(path, data)
        return cleanup_locked(backend, path, data)


def status(session_dir):
    path = safe_path(session_dir, directory=True, private=True)
    with session_lock(path):
        return summary(path, load_receipt(path))


def cleanup_expired(backend, state_root):
    root = safe_path(state_root, directory=True, private=True)
    if not root.is_dir():
        raise SessionError('State root does not exist')
    result = {'cleaned': [], 'skipped_active': [], 'skipped_locked': [], 'errors': []}
    initial_context = backend.context
    for path in sorted(root.iterdir()):
        if not SESSION_RE.fullmatch(path.name):
            continue
        try:
            with session_lock(path):
                data = load_receipt(path)
                if data['state'] == 'revoked':
                    continue
                if data['state'] == 'active' and timestamp(data['expiration_timestamp']) > now():
                    result['skipped_active'].append(path.name)
                    continue
                backend.context = initial_context
                cleanup_locked(backend, path, data)
                result['cleaned'].append(path.name)
        except Locked:
            result['skipped_locked'].append(path.name)
        except (SessionError, OSError) as error:
            result['errors'].append({'session': path.name, 'error': str(error) if isinstance(error, SessionError) else 'Local storage error'})
        finally:
            backend.context = initial_context
    return result


def operator_state_path(path, legacy, current):
    # An explicitly migrated legacy root is a lookup alias only. The normal
    # ownership and no-symlink checks still apply to every actual state path.
    path = path.expanduser().absolute()
    if legacy.is_symlink() and path.is_relative_to(legacy) and '..' not in path.parts:
        target = Path(os.path.normpath(legacy.parent / legacy.readlink()))
        if target == current:
            return current / path.relative_to(legacy)
    return path


def main(argv=None):
    legacy = ROOT / 'sessions'
    current = (Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state').expanduser().absolute()
               / 'infra-mcp/sessions')
    default_root = legacy if legacy.is_dir() and not legacy.is_symlink() else current
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('issue', 'status', 'revoke', 'cleanup-expired'):
        sub = commands.add_parser(command)
        if command != 'status':
            sub.add_argument('--admin-config', required=True, type=Path)
            sub.add_argument('--context')
        if command in ('status', 'revoke'):
            sub.add_argument('--session-dir', required=True, type=Path)
        else:
            sub.add_argument('--state-root', default=default_root, type=Path)
        if command == 'issue':
            sub.add_argument('--namespace', required=True)
            sub.add_argument('--resources')
            sub.add_argument('--permissions')
            sub.add_argument('--patch-target', action='append', metavar='KIND/NAME',
                             help=f'One-hour get/patch access; kinds: {", ".join(PATCH_KINDS)}; repeat per target')
    args = parser.parse_args(argv)
    for field in ('session_dir', 'state_root'):
        if hasattr(args, field):
            setattr(args, field, operator_state_path(getattr(args, field), legacy, current))
    try:
        if args.command == 'status':
            result = status(args.session_dir)
        else:
            backend = Kubectl(args.admin_config, args.context)
            if args.command == 'issue':
                resources = args.resources.split(',') if args.resources is not None else None
                permissions = args.permissions.split(',') if args.permissions is not None else None
                result = issue(backend, args.state_root, args.namespace, resources, permissions,
                               patch_targets=args.patch_target)
            elif args.command == 'revoke':
                result = revoke(backend, args.session_dir)
            else:
                result = cleanup_expired(backend, args.state_root)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result.get('errors') else 0
    except (SessionError, OSError, KeyboardInterrupt):
        error = sys.exc_info()[1]
        failure = {'error': str(error) if isinstance(error, SessionError) else 'Local storage error or interrupted'}
        if getattr(error, 'session_dir', None):
            failure['session_dir'] = error.session_dir
        print(json.dumps(failure), file=sys.stderr)
        return 1


if __name__ == '__main__':
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
