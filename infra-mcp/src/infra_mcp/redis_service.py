"""Bounded, scoped Redis string operations; never accepts arbitrary commands."""
import base64

import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from .redis_protocol import BoundedRESP2Parser
from .base import BaseService, Operation
from .config import InfraError, integer, secret, validate_name


class RedisService(BaseService):
    service = 'redis'
    operations = {
        'check_connection': Operation('read', 'Check Redis connectivity using PING. Returns no server configuration or secrets.', {}),
        'inspect': Operation('read', 'Read key type and remaining TTL without retrieving its value.', {'key': 'Exact scoped key.'}),
        'read_collection': Operation('read', 'Read a bounded page of a hash, list, set, sorted set or stream. Type is discovered automatically. Scan pages may be empty; continue cursor until zero. Oversized pages fail without advancing.', {'key':'Exact scoped collection key.', 'limit':'Maximum items, 1–200, default 100.', 'cursor':'Hash/set scan cursor; default 0.', 'offset':'List/sorted set zero-based starting offset; default 0.', 'start':'Stream lower ID bound, default -; use exclusive (last-id for next page.'}),
        'hash_set': Operation('update', 'Set one hash field. Requires create and update because HSET can create both key and field.', {'key':'Exact scoped hash key.', 'field':'Exact field name, at most 1024 characters.', 'value':'UTF-8 value, at most 65536 bytes.'}, additional_permissions=('create',)),
        'hash_delete': Operation('delete', 'Delete one field from a scoped hash.', {'key':'Exact scoped hash key.', 'field':'Exact field name.'}),
        'scan': Operation('read', 'Scan a bounded page of scoped keys. Continue with returned cursor until zero. An oversized page fails; retry the same cursor with a larger limit or narrower pattern.', {'cursor': 'Nonnegative Redis SCAN cursor from prior page; default 0.', 'pattern': 'Redis glob to narrow scan, default *. Scope is always enforced separately.', 'limit': 'Maximum returned keys, 1–200; default 100. Scan work is capped independently.'}),
        'get': Operation('read', 'Read a bounded prefix of a string key. Binary values are base64 encoded.', {'key': 'Exact key permitted by key_patterns scope.', 'max_bytes': 'Maximum returned bytes, 1–65536; default 4096.'}),
        'create': Operation('create', 'Create a string key only if absent (atomic SET NX).', {'key': 'Exact scoped key.', 'value': 'UTF-8 string, at most 65536 encoded bytes.', 'ttl_seconds': 'Optional expiration in seconds, 1–31536000; omitted means no expiration.'}),
        'update': Operation('update', 'Replace an existing string only (atomic SET XX); preserve existing TTL unless ttl_seconds is supplied.', {'key': 'Exact scoped key.', 'value': 'UTF-8 string, at most 65536 encoded bytes.', 'ttl_seconds': 'Optional replacement expiration, 1–31536000 seconds.'}),
        'expire': Operation('update', 'Set expiration on an existing key without changing its value.', {'key': 'Exact scoped key.', 'seconds': 'Required expiration seconds, 1–31536000.'}),
        'ttl': Operation('read', 'Read remaining expiration seconds: -1 means persistent; -2 means missing.', {'key': 'Exact scoped key.'}),
        'delete': Operation('delete', 'Delete one exact scoped key.', {'key': 'Exact scoped key to permanently delete.'}),
    }

    def _client(self, profile):
        options = profile.options
        if redis.__version__ != '7.4.1':
            raise InfraError('invalid_config', 'Bounded Redis parser requires redis-py 7.4.1')
        return redis.Redis.from_pool(redis.ConnectionPool(
            protocol=2, parser_class=BoundedRESP2Parser,
            connection_class=redis.SSLConnection if options.get('tls', False) else redis.Connection,
            host=options.get('host', 'localhost'),
            port=integer(options, 'port', 6379, 1, 65535),
            db=integer(options, 'db', 0, 0, 65535),
            username=secret(profile, 'username') or options.get('username'), password=secret(profile, 'password'),
            **({'ssl_cert_reqs': 'required', 'ssl_ca_certs': options.get('ca_file')} if options.get('tls', False) else {}),
            socket_connect_timeout=profile.timeout, socket_timeout=profile.timeout,
            decode_responses=False, retry=Retry(NoBackoff(), 0),
            retry_on_timeout=False,
        ))

    def execute(self, profile, operation, arguments):
        key = None
        if operation not in ('scan', 'check_connection'):
            key = validate_name(arguments.get('key'), 'key')
            profile.check_scope('key_patterns', key)
        # Validate arguments before connecting, including write payload sizes.
        if operation in ('create', 'update', 'hash_set'):
            value = arguments.get('value')
            if not isinstance(value, str) or len(value.encode('utf-8')) > 65536:
                raise InfraError('invalid_argument', 'value must be a string of at most 65536 UTF-8 bytes')
            ttl = integer(arguments, 'ttl_seconds', None, 1, 31536000) if 'ttl_seconds' in arguments else None
        elif operation == 'expire':
            if 'seconds' not in arguments:
                raise InfraError('invalid_argument', 'seconds is required')
            seconds = integer(arguments, 'seconds', 60, 1, 31536000)
        elif operation == 'get':
            maximum = integer(arguments, 'max_bytes', 4096, 1, 65536)
        elif operation == 'scan':
            cursor = integer(arguments, 'cursor', 0, 0, 2**64 - 1)
            limit = integer(arguments, 'limit', 100, 1, 200)
            pattern = validate_name(arguments.get('pattern', '*'), 'pattern')
        if operation in ('hash_set', 'hash_delete'):
            field = validate_name(arguments.get('field'), 'field')
        if operation == 'read_collection':
            limit = integer(arguments, 'limit', 100, 1, 200)
            cursor = integer(arguments, 'cursor', 0, 0, 2**64 - 1)
            offset = integer(arguments, 'offset', 0, 0, 2**31 - 1)
            start = validate_name(arguments.get('start', '-'), 'stream start')
        client = self._client(profile)
        try:
            if operation == 'check_connection': return {'reachable': bool(client.ping())}
            if operation == 'inspect': return {'type': client.type(key).decode('ascii'), 'ttl_seconds': client.ttl(key)}
            if operation == 'hash_set': return {'added': client.hset(key, mapping={field: value})}
            if operation == 'hash_delete': return {'deleted': client.hdel(key, field)}
            if operation == 'read_collection':
                kind = client.type(key).decode('ascii')
                next_cursor = 0
                if kind == 'hash': next_cursor, items = client.hscan(key, cursor=cursor, count=limit)
                elif kind == 'set': next_cursor, items = client.sscan(key, cursor=cursor, count=limit)
                elif kind == 'list': items = client.lrange(key, offset, offset + limit - 1)
                elif kind == 'zset': items = client.zrange(key, offset, offset + limit - 1, withscores=True)
                elif kind == 'stream': items = client.xrange(key, min=start, max='+', count=limit)
                elif kind == 'none': items = []
                else: raise InfraError('invalid_argument', 'Key is not a supported collection type; use get for strings')
                if len(items) > limit:
                    raise InfraError('result_too_large', 'Collection page exceeds limit; retry the same cursor with a larger limit')
                items = self._decode(items)
                return {'type': kind, 'items': items, 'cursor': int(next_cursor), 'offset': offset + len(items)}
            if operation == 'scan':
                cursor, candidates = client.scan(cursor=cursor, match=pattern, count=limit)
                keys = []
                # COUNT is a hint, so enforce a hard response bound as well.
                for candidate in candidates:
                    try:
                        candidate = candidate.decode('utf-8') if isinstance(candidate, bytes) else candidate
                        profile.check_scope('key_patterns', candidate)
                    except (InfraError, UnicodeDecodeError):
                        continue
                    keys.append(candidate)
                if len(keys) > limit:
                    raise InfraError('result_too_large', 'SCAN page exceeds limit; retry the same cursor with a larger limit or narrower pattern')
                return {'keys': keys, 'cursor': int(cursor), 'truncated': False}
            if operation == 'get':
                value = client.getrange(key, 0, maximum)
                if not value and not client.exists(key):
                    return {'value': None, 'encoding': 'utf-8', 'truncated': False}
                truncated = len(value) > maximum
                value = value[:maximum]
                try:
                    text, encoding = value.decode('utf-8'), 'utf-8'
                except UnicodeDecodeError:
                    text, encoding = base64.b64encode(value).decode('ascii'), 'base64'
                return {'value': text, 'encoding': encoding, 'truncated': truncated}
            if operation in ('create', 'update'):
                kwargs = {'nx': True} if operation == 'create' else {'xx': True}
                if ttl is not None: kwargs['ex'] = ttl
                elif operation == 'update': kwargs['keepttl'] = True
                if operation == 'update':
                    try:
                        with client.pipeline() as pipeline:
                            pipeline.watch(key)
                            kind = pipeline.type(key)
                            if kind == b'none': return {'updated': False}
                            if kind != b'string':
                                raise InfraError('invalid_argument', 'Update requires an existing string key')
                            pipeline.multi()
                            pipeline.set(key, value, **kwargs)
                            return {'updated': bool(pipeline.execute()[0])}
                    except redis.WatchError:
                        raise InfraError('conflict', 'Key changed concurrently; update was not retried') from None
                return {'created': bool(client.set(key, value, **kwargs))}
            if operation == 'expire': return {'updated': bool(client.expire(key, seconds))}
            if operation == 'ttl': return {'seconds': client.ttl(key)}
            if operation == 'delete': return {'deleted': bool(client.delete(key))}
            raise InfraError('invalid_operation', 'Unsupported Redis operation')
        finally:
            client.close()

    @staticmethod
    def _decode(value):
        if isinstance(value, dict):
            return {RedisService._decode(k): RedisService._decode(v) for k,v in value.items()}
        if isinstance(value, (list, tuple)):
            return [RedisService._decode(item) for item in value]
        if isinstance(value, bytes):
            try: return value.decode('utf-8')
            except UnicodeDecodeError: return 'base64:' + base64.b64encode(value).decode('ascii')
        return value
