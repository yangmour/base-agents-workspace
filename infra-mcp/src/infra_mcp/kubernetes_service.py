"""Scoped kubectl operations with fixed connection arguments and bounded I/O."""
import json
import os
import re
import selectors
import subprocess
import time
from .base import BaseService, Operation
from .config import InfraError, integer

MAX_OUTPUT = 1024 * 1024
RESOURCES = {'pods': ('v1','Pod'), 'services': ('v1','Service'), 'configmaps': ('v1','ConfigMap'), 'secrets': ('v1','Secret'), 'deployments': ('apps/v1','Deployment'), 'statefulsets': ('apps/v1','StatefulSet'), 'daemonsets': ('apps/v1','DaemonSet'), 'jobs': ('batch/v1','Job'), 'cronjobs': ('batch/v1','CronJob'), 'persistentvolumeclaims': ('v1','PersistentVolumeClaim'), 'ingresses': ('networking.k8s.io/v1','Ingress'), 'events': ('v1','Event')}

def fail(message):
    raise InfraError('invalid_arguments', message)

def name(value):
    if not isinstance(value, str) or len(value) > 253 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', value):
        fail('Invalid Kubernetes name')
    return value

def _run_bounded(argv, data, timeout):
    payload = data.encode() if data is not None else b''
    if len(payload) > MAX_OUTPUT: fail('Input exceeds limit')
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    selector = selectors.DefaultSelector()
    chunks = {process.stdout: bytearray(), process.stderr: bytearray()}
    deadline = time.monotonic() + timeout
    try:
        for stream in chunks:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        if payload:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE)
        else:
            process.stdin.close()
        offset = 0
        total = 0
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise InfraError('timeout', 'Kubernetes operation timed out')
            for key, mask in selector.select(min(remaining, .1)):
                stream = key.fileobj
                if mask == selectors.EVENT_WRITE:
                    try: offset += os.write(stream.fileno(), payload[offset:offset+8192])
                    except BrokenPipeError: offset = len(payload)
                    if offset == len(payload):
                        selector.unregister(stream)
                        stream.close()
                else:
                    block = os.read(stream.fileno(), 65536)
                    if not block:
                        selector.unregister(stream)
                    else:
                        total += len(block)
                        if total > MAX_OUTPUT: raise InfraError('output_limit', 'Kubernetes output exceeds limit')
                        chunks[stream].extend(block)
        remaining = deadline - time.monotonic()
        if remaining <= 0: raise InfraError('timeout', 'Kubernetes operation timed out')
        try: code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired: raise InfraError('timeout', 'Kubernetes operation timed out') from None
        if code: raise InfraError('backend_error', 'Kubernetes command failed')
        return chunks[process.stdout].decode('utf-8', errors='replace')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()

class KubernetesService(BaseService):
    service = 'kubernetes'
    operations = {
        'check_connection': Operation('read', 'Check configured kubectl server connectivity; returns only connected status', {}),
        'list': Operation('read', 'List resources within one namespace; Secret data and annotations always redacted, including redact=false', {'namespace':'Required namespace','resource':'Required supported plural resource'}),
        'get': Operation('read', 'Get a named resource; Secret data and annotations always redacted, including redact=false', {'namespace':'Required namespace','resource':'Required supported plural resource','name':'Required resource name'}),
        'create': Operation('create', 'Create an explicitly named JSON manifest', {'namespace':'Required namespace','resource':'Required supported plural resource','name':'Required resource name','manifest':'Required object; apiVersion/kind/name must match target; namespace optional and must match'}),
        'patch': Operation('update', 'Merge patch a resource without changing identity', {'namespace':'Required namespace','resource':'Required supported plural resource','name':'Required resource name','patch':'Required JSON merge patch object; identity fields forbidden'}),
        'delete': Operation('delete', 'Delete one resource without waiting', {'namespace':'Required namespace','resource':'Required supported plural resource','name':'Required resource name'}),
        'logs': Operation('read', 'Read bounded pod logs', {'namespace':'Required namespace','resource':'Must be pods','name':'Required pod name','container':'Optional container name','tail':'Integer 1..10000, default 100','since_seconds':'Integer 1..86400, default 3600','limit_bytes':'Integer 1..1048576, default 65536'}),
        'restart': Operation('update', 'Restart workload rollout', {'namespace':'Required namespace','resource':'deployments, statefulsets or daemonsets','name':'Required workload name'}),
        'scale': Operation('update', 'Set workload replica count', {'namespace':'Required namespace','resource':'deployments or statefulsets','name':'Required workload name','replicas':'Required integer 0..10000'}),
    }

    def run(self, connection, action, operation, arguments=None):
        result = super().run(connection, action, operation, arguments)
        # Secret scrubbing is mandatory even when generic redaction is disabled.
        # Keep the public envelope honest without per-connection mutable state.
        if '[REDACTED]' in json.dumps(result['data']):
            result['redacted'] = True
        return result

    def observe_deployment(self, profile, namespace, deployment, project):
        """Project version metadata before the generic resource response strips annotations."""
        profile.require('read')
        return self._execute(profile, 'get', {'namespace': namespace, 'resource': 'deployments',
                                              'name': deployment}, project)

    def execute(self, profile, operation, arguments):
        return self._execute(profile, operation, arguments)

    def _execute(self, profile, operation, arguments, project=None):
        if operation not in self.operations: fail('Unsupported Kubernetes operation')
        config, context = profile.options.get('kubeconfig'), profile.options.get('context')
        if not isinstance(config, str) or not os.path.isabs(config) or '\x00' in config: fail('An absolute configured kubeconfig is required')
        if not isinstance(context, str) or not context or any(ord(c)<32 for c in context): fail('A configured context is required')
        argv = ['kubectl','--kubeconfig',config,'--context',context]
        if operation == 'check_connection':
            output = _run_bounded(argv + ['version','--output=json'], None, profile.timeout)
            try: response = json.loads(output)
            except (ValueError, TypeError): raise InfraError('backend_error', 'Invalid Kubernetes response') from None
            if not isinstance(response, dict) or not isinstance(response.get('serverVersion'), dict):
                raise InfraError('backend_error', 'Kubernetes server did not report connectivity')
            return {'connected': True}
        ns = name(arguments.get('namespace'))
        resource = arguments.get('resource')
        if resource not in RESOURCES: fail('Unsupported Kubernetes resource')
        if resource == 'events' and operation not in ('list', 'get'):
            fail('Events support read operations only')
        profile.check_scope('namespaces', ns)
        profile.check_scope('resources', resource)
        target = None if operation == 'list' else name(arguments.get('name'))
        if target: profile.check_scope('names', target)
        argv += ['--namespace',ns]
        data = None
        if operation in ('list','get'):
            argv += ['get', resource] + ([target] if target else []) + ['-o','json']
        elif operation == 'create':
            manifest = arguments.get('manifest')
            if not isinstance(manifest, dict): fail('manifest must be an object')
            meta = manifest.get('metadata')
            if not isinstance(meta,dict) or meta.get('name') != target or meta.get('namespace',ns) != ns or 'generateName' in meta: fail('Manifest metadata must match target')
            if (manifest.get('apiVersion'),manifest.get('kind')) != RESOURCES[resource]: fail('Manifest kind must match target')
            argv += ['create','-f','-','-o','json']
            data = json.dumps(manifest)
        elif operation == 'patch':
            patch = arguments.get('patch')
            if not isinstance(patch,dict): fail('patch must be an object')
            if 'apiVersion' in patch or 'kind' in patch: fail('Patch cannot change identity')
            if 'metadata' in patch:
                meta = patch['metadata']
                if not isinstance(meta,dict) or any(k in meta for k in ('name','namespace','generateName','uid','resourceVersion','selfLink')): fail('Patch cannot change identity')
            argv += ['patch',resource,target,'--type=merge','--patch-file=/dev/stdin','-o','json']
            data = json.dumps(patch)
        elif operation == 'delete': argv += ['delete',resource,target,'--wait=false','-o','name']
        elif operation == 'logs':
            if resource != 'pods': fail('Logs require pods')
            argv += ['logs',target, '--tail='+str(integer(arguments,'tail',100,1,10000)), '--since='+str(integer(arguments,'since_seconds',3600,1,86400))+'s', '--limit-bytes='+str(integer(arguments,'limit_bytes',65536,1,MAX_OUTPUT))]
            if 'container' in arguments: argv += ['--container',name(arguments['container'])]
        elif operation == 'restart':
            if resource not in ('deployments','statefulsets','daemonsets'): fail('Unsupported restart resource')
            argv += ['rollout','restart',resource+'/'+target,'-o','json']
        elif operation == 'scale':
            if resource not in ('deployments','statefulsets'): fail('Unsupported scale resource')
            argv += ['scale',resource+'/'+target,'--replicas='+str(integer(arguments,'replicas',None,0,10000)),'-o','json']
        output = _run_bounded(argv,data,profile.timeout)
        if operation == 'logs': return {'logs':output}
        if operation == 'delete':
            # --wait=false acknowledges the request, not completed resource removal.
            return {'deletion_requested': True, 'namespace': ns, 'resource': resource, 'name': target}
        try: result = json.loads(output)
        except (ValueError,TypeError): raise InfraError('backend_error','Invalid Kubernetes response') from None
        if project is not None:
            return project(result)
        def clean(obj):
            if isinstance(obj,dict):
                if obj.get('kind') == 'Secret' or resource == 'secrets':
                    for key in ('data','stringData'):
                        if key in obj: obj[key] = '[REDACTED]'
                metadata = obj.get('metadata')
                if isinstance(metadata,dict):
                    # Annotations may contain complete manifests or credentials.
                    if 'annotations' in metadata: metadata['annotations'] = '[REDACTED]'
                    metadata.pop('managedFields',None)
                for value in obj.values(): clean(value)
            elif isinstance(obj,list):
                for value in obj: clean(value)
        if isinstance(result,dict) and isinstance(result.get('items'),list):
            filtered=[]
            for item in result['items']:
                meta=item.get('metadata',{})
                try:
                    if meta.get('namespace',ns) != ns: continue
                    profile.check_scope('names',meta.get('name',''))
                except Exception: continue
                filtered.append(item)
            result['items']=filtered
        clean(result)
        return result
