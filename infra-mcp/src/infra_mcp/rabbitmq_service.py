"""Fixed RabbitMQ management operations with explicit destructive consumption."""
from urllib.parse import quote

from .base import BaseService, Operation
from .config import InfraError, integer, validate_name
from .http import request_json


_V = {'vhost': 'Required exact virtual host name, including / for the default vhost.'}
_Q = {**_V, 'queue': 'Required exact queue name; URL encoded as a single component.'}
_X = {**_V, 'exchange': 'Required exact exchange name; use amq.default for the default exchange (publish also accepts empty string).'}


class RabbitMQService(BaseService):
    service = 'rabbitmq'
    operations = {
        'check_connection': Operation('read', 'Check authenticated management API identity.'),
        'overview': Operation('read', 'Read cluster aggregate health and metrics.'),
        'list_bindings': Operation('read', 'List permitted bindings within one virtual host.', _V),
        'create_binding': Operation(
            'create',
            'Create a binding from an exchange to a queue.',
            {
                **_Q,
                'exchange': 'Required source exchange name.',
                'routing_key': 'Routing key; defaults to empty.',
                'arguments': 'Optional binding arguments object.',
            },
        ),
        'delete_binding': Operation(
            'delete',
            'Delete one binding from an exchange to a queue.',
            {
                **_Q,
                'exchange': 'Required source exchange name.',
                'properties_key': 'Required exact binding properties_key returned by list_bindings.',
            },
        ),
        'update_policy': Operation(
            'update',
            'Create or update a vhost policy. Requires create permission and unrestricted queue/exchange scopes.',
            {
                **_V,
                'name': 'Required policy name.',
                'pattern': 'Required resource-name regular expression.',
                'definition': 'Required policy definition object.',
                'priority': 'Integer 0–2147483647; default 0.',
                'apply_to': 'all, queues or exchanges; default all.',
            },
            ('create',),
        ),
        'delete_policy': Operation(
            'delete',
            'Delete a policy in a permitted vhost; requires unrestricted queue/exchange scopes.',
            {**_V, 'name': 'Required exact policy name.'},
        ),
        'list_vhosts': Operation('read', 'List virtual hosts permitted by this profile.'),
        'list_queues': Operation('read', 'List permitted queues in one virtual host.', _V),
        'get_queue': Operation('read', 'Read one queue and its metrics.', _Q),
        'declare_queue': Operation(
            'create',
            'Declare a queue; PUT may update an existing queue and requires update permission.',
            {
                **_Q,
                'durable': 'Boolean, default true.',
                'auto_delete': 'Boolean, default false.',
                'arguments': 'Optional queue argument object.',
            },
            ('update',),
        ),
        'delete_queue': Operation('delete', 'Delete one queue and its messages.', _Q),
        'purge_queue': Operation('delete', 'Remove all ready messages from one queue.', _Q),
        'list_exchanges': Operation('read', 'List permitted exchanges in one virtual host.', _V),
        'get_exchange': Operation('read', 'Read one exchange.', _X),
        'declare_exchange': Operation(
            'create',
            'Declare an exchange; PUT requires both create and update permission.',
            {
                **_X,
                'type': 'direct, fanout, topic or headers; default direct.',
                'durable': 'Boolean, default true.',
                'auto_delete': 'Boolean, default false.',
                'arguments': 'Optional exchange argument object.',
            },
            ('update',),
        ),
        'delete_exchange': Operation('delete', 'Delete one exchange.', _X),
        'publish': Operation(
            'create',
            'Publish one message to an exchange.',
            {
                **_X,
                'routing_key': 'Routing key string; default empty.',
                'payload': 'Required UTF-8 payload string.',
                'properties': 'Optional AMQP message properties object.',
            },
        ),
        'consume': Operation(
            'delete',
            'Destructively consume messages; acknowledged messages are not requeued.',
            {
                **_Q,
                'count': 'Message count, integer 1–100; default 1.',
                'truncate': 'Maximum payload bytes per message, 1–65536; default 4096.',
            },
        ),
    }

    def execute(self, profile, operation, arguments):
        if operation == 'check_connection':
            return request_json(profile, 'GET', '/api/whoami')
        if operation == 'overview':
            return request_json(profile, 'GET', '/api/overview')
        if operation == 'list_vhosts':
            rows = request_json(profile, 'GET', '/api/vhosts')
            return [row for row in rows if self._allowed(profile, 'vhosts', row.get('name'))]
        vhost = validate_name(arguments.get('vhost'), 'vhost')
        if vhost in ('.', '..'):
            raise InfraError('invalid_argument', 'Invalid virtual host name.')
        profile.check_scope('vhosts', vhost)
        if operation.endswith('_policy'):
            return self._policy(profile, operation, arguments, vhost)
        if operation.endswith('_binding') or operation == 'list_bindings':
            return self._binding(profile, operation, arguments, vhost)
        kind = 'queues' if 'queue' in operation or operation == 'consume' else 'exchanges'
        root = '/api/' + kind + '/' + quote(vhost, safe='')
        if operation.startswith('list_'):
            rows = request_json(profile, 'GET', root)
            return [r for r in rows if self._allowed(profile, 'vhosts', r.get('vhost')) and self._allowed(profile, kind, r.get('name'))]
        target = arguments.get('queue' if kind == 'queues' else 'exchange')
        if kind == 'exchanges' and operation == 'publish' and target == '':
            target = 'amq.default'
        name = validate_name(target, kind[:-1])
        if name in ('.', '..'):
            raise InfraError('invalid_argument', 'Invalid resource name.')
        profile.check_scope(kind, name)
        path = root + '/' + quote(name, safe='')
        if operation.startswith('get_'):
            return request_json(profile, 'GET', path)
        if operation.startswith('delete_'):
            return request_json(profile, 'DELETE', path)
        if operation == 'purge_queue':
            # RabbitMQ's purge endpoint has no JSON representation; a JSON-only
            # Accept header can cause HTTP 406 before the destructive operation.
            return request_json(profile, 'DELETE', path + '/contents', headers={'Accept': '*/*'})
        if operation.startswith('declare_'):
            body = {
                'durable': self._boolean(arguments, 'durable', True),
                'auto_delete': self._boolean(arguments, 'auto_delete', False),
                'arguments': self._object(arguments, 'arguments'),
            }
            if kind == 'exchanges':
                exchange_type = arguments.get('type', 'direct')
                if exchange_type not in ('direct', 'fanout', 'topic', 'headers'):
                    raise InfraError('invalid_argument', 'Unsupported exchange type.')
                body['type'] = exchange_type
            return request_json(profile, 'PUT', path, json=body)
        if operation == 'publish':
            payload = arguments.get('payload')
            routing = arguments.get('routing_key', '')
            if not isinstance(payload, str) or not isinstance(routing, str):
                raise InfraError('invalid_argument', 'payload and routing_key must be strings.')
            if name == 'amq.default':
                profile.check_scope('queues', routing)
            return request_json(profile, 'POST', path + '/publish', json={
                'properties': self._object(arguments, 'properties'),
                'routing_key': routing,
                'payload': payload,
                'payload_encoding': 'string',
            })
        if operation == 'consume':
            return request_json(profile, 'POST', path + '/get', json={
                'count': integer(arguments, 'count', 1, 1, 100),
                'ackmode': 'ack_requeue_false',
                'encoding': 'auto',
                'truncate': integer(arguments, 'truncate', 4096, 1, 65536),
            })
        raise InfraError('invalid_operation', 'Unknown RabbitMQ operation.')

    @staticmethod
    def _allowed(profile, kind, value):
        if not isinstance(value, str):
            return False
        if kind == 'exchanges' and value == '':
            value = 'amq.default'
        try:
            profile.check_scope(kind, value)
        except InfraError:
            return False
        return True

    @staticmethod
    def _boolean(arguments, name, default):
        value = arguments.get(name, default)
        if not isinstance(value, bool):
            raise InfraError('invalid_argument', name + ' must be boolean.')
        return value

    @staticmethod
    def _object(arguments, name):
        value = arguments.get(name, {})
        if not isinstance(value, dict):
            raise InfraError('invalid_argument', name + ' must be an object.')
        return value

    def _policy(self, profile, operation, arguments, vhost):
        for kind in ('queues', 'exchanges'):
            if profile.scope.get(kind, ['*']) != ['*']:
                raise InfraError('scope_denied', 'Policy mutation requires unrestricted queue and exchange scopes.')
        name = validate_name(arguments.get('name'), 'policy name')
        if name in ('.', '..'):
            raise InfraError('invalid_argument', 'Invalid policy name.')
        path = '/api/policies/' + quote(vhost, safe='') + '/' + quote(name, safe='')
        if operation == 'delete_policy':
            return request_json(profile, 'DELETE', path)
        pattern = validate_name(arguments.get('pattern'), 'pattern')
        definition = arguments.get('definition')
        if not isinstance(definition, dict):
            raise InfraError('invalid_argument', 'definition must be an object.')
        apply_to = arguments.get('apply_to', 'all')
        if apply_to not in ('all', 'queues', 'exchanges'):
            raise InfraError('invalid_argument', 'Invalid apply_to value.')
        body = {
            'pattern': pattern,
            'definition': definition,
            'priority': integer(arguments, 'priority', 0, 0, 2147483647),
            'apply-to': apply_to,
        }
        return request_json(profile, 'PUT', path, json=body)

    def _binding(self, profile, operation, arguments, vhost):
        path = '/api/bindings/' + quote(vhost, safe='')
        if operation == 'list_bindings':
            rows = request_json(profile, 'GET', path)
            result = []
            for row in rows:
                destination_kind = {
                    'queue': 'queues',
                    'exchange': 'exchanges',
                }.get(row.get('destination_type'))
                if destination_kind and self._allowed(profile, 'vhosts', row.get('vhost')) and self._allowed(profile, 'exchanges', row.get('source')) and self._allowed(profile, destination_kind, row.get('destination')):
                    result.append(row)
            return result
        exchange = validate_name(arguments.get('exchange'), 'exchange')
        queue = validate_name(arguments.get('queue'), 'queue')
        for kind, name in (('exchanges', exchange), ('queues', queue)):
            if name in ('.', '..'):
                raise InfraError('invalid_argument', 'Invalid binding target.')
            profile.check_scope(kind, name)
        path += '/e/' + quote(exchange, safe='') + '/q/' + quote(queue, safe='')
        if operation == 'delete_binding':
            key = validate_name(arguments.get('properties_key'), 'properties_key')
            if key in ('.', '..'):
                raise InfraError('invalid_argument', 'Invalid binding properties key.')
            return request_json(profile, 'DELETE', path + '/' + quote(key, safe=''))
        routing = arguments.get('routing_key', '')
        if not isinstance(routing, str):
            raise InfraError('invalid_argument', 'routing_key must be a string.')
        return request_json(profile, 'POST', path, json={
            'routing_key': routing,
            'arguments': self._object(arguments, 'arguments'),
        })
