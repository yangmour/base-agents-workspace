"""Elasticsearch operations limited to one concrete scoped index."""
from urllib.parse import quote

from .base import BaseService, Operation
from .config import InfraError, integer, validate_name
from .http import request_json


_I = {
    'index': 'Required single concrete index name; wildcards, aliases expressions and _all are not supported.',
}
_D = {**_I, 'id': 'Required document ID; encoded as one URL component.'}


class ElasticsearchService(BaseService):
    service = 'elasticsearch'
    operations = {
        'check_connection': Operation('read', 'Check cluster availability and aggregate health.'),
        'count': Operation(
            'read',
            'Count matching documents in one permitted index.',
            {**_I, 'query': 'Optional query object; defaults to match_all.'},
        ),
        'list_indices': Operation('read', 'List permitted concrete indices and bounded summary metrics.'),
        'create_index': Operation(
            'create',
            'Create a new concrete index; fails if it exists.',
            {
                **_I,
                'settings': 'Optional index settings object.',
                'mappings': 'Optional index mapping object.',
            },
        ),
        'delete_index': Operation('delete', 'Delete one concrete index and its documents.', _I),
        'get_mapping': Operation('read', 'Read mappings for one concrete index.', _I),
        'search': Operation(
            'read',
            'Search one concrete index with bounded hits.',
            {
                **_I,
                'query': 'Optional Elasticsearch query object; defaults to match_all.',
                'size': 'Hit count, integer 0–100; default 10.',
                'from': 'Offset, integer 0–10000; default 0.',
            },
        ),
        'get_doc': Operation('read', 'Read one document.', _D),
        'create_doc': Operation(
            'create',
            'Create a document using _create; existing IDs cause conflict.',
            {**_D, 'document': 'Required JSON document object.'},
        ),
        'update_doc': Operation(
            'update',
            'Merge partial fields into an existing document; scripts and upsert are forbidden.',
            {**_D, 'document': 'Required partial JSON document object.'},
        ),
        'delete_doc': Operation('delete', 'Delete one document.', _D),
    }

    def execute(self, profile, operation, arguments):
        if operation == 'check_connection':
            return request_json(profile, 'GET', '/_cluster/health')
        if operation == 'list_indices':
            rows = request_json(profile, 'GET', '/_cat/indices', params={
                'format': 'json',
                'h': 'index,health,status,docs.count,store.size',
            })
            return [r for r in rows if self._allowed(profile, r.get('index'))]
        index = validate_name(arguments.get('index'), 'index')
        if index.startswith(('_', '-', '+')) or any((c in index for c in ',*?\\/<>|# :')) or index in ('.', '..'):
            raise InfraError('invalid_argument', 'index must be one concrete index name.')
        profile.check_scope('indices', index)
        path = '/' + quote(index, safe='')
        if operation == 'create_index':
            return request_json(profile, 'PUT', path, json={k: self._object(arguments, k) for k in ('settings', 'mappings') if k in arguments})
        if operation == 'delete_index':
            return request_json(profile, 'DELETE', path)
        if operation == 'get_mapping':
            return request_json(profile, 'GET', path + '/_mapping')
        if operation == 'count':
            return request_json(profile, 'POST', path + '/_count', json={
                'query': self._object(arguments, 'query', {'match_all': {}}),
            })
        if operation == 'search':
            return request_json(profile, 'POST', path + '/_search', json={
                'query': self._object(arguments, 'query', {'match_all': {}}),
                'size': integer(arguments, 'size', 10, 0, 100),
                'from': integer(arguments, 'from', 0, 0, 10000),
            })
        doc_id = validate_name(arguments.get('id'), 'id')
        if doc_id in ('.', '..'):
            raise InfraError('invalid_argument', 'Invalid document ID.')
        encoded = quote(doc_id, safe='')
        if operation == 'get_doc':
            return request_json(profile, 'GET', path + '/_doc/' + encoded)
        if operation == 'delete_doc':
            return request_json(profile, 'DELETE', path + '/_doc/' + encoded)
        document = self._object(arguments, 'document', required=True)
        if operation == 'create_doc':
            return request_json(profile, 'PUT', path + '/_create/' + encoded, json=document)
        if operation == 'update_doc':
            if any((k in arguments for k in ('script', 'upsert', 'doc_as_upsert', 'scripted_upsert'))):
                raise InfraError('invalid_argument', 'Scripts and upsert options are forbidden.')
            return request_json(profile, 'POST', path + '/_update/' + encoded, json={
                'doc': document,
                'doc_as_upsert': False,
            })
        raise InfraError('invalid_operation', 'Unknown Elasticsearch operation.')

    @staticmethod
    def _allowed(profile, index):
        if not isinstance(index, str):
            return False
        try:
            profile.check_scope('indices', index)
        except InfraError:
            return False
        return True

    @staticmethod
    def _object(arguments, name, default=None, required=False):
        value = arguments.get(name, None if required else {} if default is None else default)
        if not isinstance(value, dict):
            raise InfraError('invalid_argument', name + ' must be an object.')
        return value
