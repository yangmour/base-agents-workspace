"""Scoped MySQL metadata and single-row CRUD, with no caller-supplied SQL."""
from __future__ import annotations

import datetime
import contextlib
from decimal import Decimal
import ipaddress
import json
import math
import re
import ssl
from pathlib import Path

from pymysql.cursors import DictCursor

from .base import BaseService, Operation
from .config import InfraError, integer, secret
from .mysql_protocol import BoundedConnection


_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_$]{0,63}\Z')
_HOST_LABEL = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z')
_SYSTEM_DATABASES = frozenset({'mysql', 'information_schema', 'performance_schema', 'sys'})
_COMPARISONS = {'eq': '=', 'ne': '<>', 'lt': '<', 'lte': '<=', 'gt': '>', 'gte': '>='}
_DECIMAL_KEY = re.compile(r'[+-]?[0-9]{1,65}(?:\.[0-9]{1,30})?\Z')
_TARGET = {'database': 'Optional database; defaults to the connection database.', 'table': 'One exact table name.'}
_PAGE = {'limit': 'Page size, 1–200; default 100.', 'offset': 'Zero-based offset, 0–1000000; default 0. Use returned offset for the next page.'}
_VALUES = 'Nonempty object of column names and JSON scalar values; strings at most 64 KiB.'
_KEY = 'Every PRIMARY KEY column and no extras. Integer keys require JSON integers; decimal keys integers or fixed-point strings; text/binary/date/time/datetime keys strings; float/double keys numbers. Booleans and enum/set/timestamp keys are unsupported.'


def _identifier(value, label='identifier'):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise InfraError('invalid_argument', f'{label} must be a simple MySQL identifier of at most 64 ASCII characters')
    return value


def _quote(value):
    return '`' + _identifier(value) + '`'


def _scalar(value):
    if value is None or type(value) in (bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, str):
        try:
            if len(value.encode('utf-8')) <= 65536:
                return value
        except UnicodeError:
            pass
    raise InfraError('invalid_argument', 'Values must be JSON scalars; strings are limited to 64 KiB and numbers must be finite')


def _mapping(value, label):
    if not isinstance(value, dict) or not 1 <= len(value) <= 200:
        raise InfraError('invalid_argument', f'{label} must contain between 1 and 200 columns')
    return {_identifier(column, 'column'): _scalar(item) for column, item in value.items()}


def _known_fields(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise InfraError('invalid_argument', 'Unsupported or malformed operation arguments')


def _primary_value(value, column_type):
    family = column_type.split('(', 1)[0].split(' ', 1)[0].lower()
    # Implicit numeric comparisons can match several distinct string/BIGINT keys.
    # Enforce compatible types, retaining exact DECIMAL literals instead of doubles.
    if family in {'tinyint', 'smallint', 'mediumint', 'int', 'integer', 'bigint', 'bit', 'year'}:
        if type(value) is int:
            return value
    elif family in {'decimal', 'numeric'}:
        if type(value) is int:
            return Decimal(value)
        if isinstance(value, str) and _DECIMAL_KEY.fullmatch(value):
            return Decimal(value)
    elif family in {'float', 'double', 'real'}:
        if type(value) is int or type(value) is float and math.isfinite(value):
            return value
    elif family in {'char', 'varchar', 'tinytext', 'text', 'mediumtext', 'longtext',
                    'binary', 'varbinary', 'tinyblob', 'blob', 'mediumblob', 'longblob',
                    'date', 'time', 'datetime'}:
        if isinstance(value, str):
            return value
    raise InfraError('invalid_argument', 'Primary-key value must use a compatible JSON type; booleans and unsupported column types are not allowed')


class MySQLService(BaseService):
    service = 'mysql'
    operations = {
        'check_connection': Operation('read', 'Check MySQL connectivity using SELECT 1.', {}),
        'list_databases': Operation('read', 'List a bounded page of scoped non-system database names. Filtered pages may be empty; continue while has_more.', _PAGE),
        'list_tables': Operation('read', 'List a bounded page of scoped InnoDB base table names. Filtered pages may be empty; continue while has_more.', {'database': _TARGET['database'], **_PAGE}),
        'describe_table': Operation('read', 'Describe at most 200 columns and the primary key of one scoped InnoDB base table.', _TARGET),
        'select_rows': Operation('read', 'Read one bounded page from a scoped InnoDB table. No raw SQL, joins, functions or subqueries.', {**_TARGET, **_PAGE,
            'columns': 'Optional list of 1–200 column names; omitted selects all columns.',
            'where': 'Optional AND list of at most 20 filters: {column, op, value}. op: eq/ne/lt/lte/gt/gte/in/is_null/is_not_null. in takes 1–100 scalar values; null checks omit value.',
            'order_by': 'Optional list of at most 20 {column, direction} objects; direction asc or desc.'}),
        'insert_row': Operation('create', 'Insert exactly one row into an InnoDB table; no replace, ignore or upsert. Database triggers and constraints still apply.', {**_TARGET, 'values': _VALUES}),
        'update_row': Operation('update', 'Update one row by its complete primary key; cannot modify primary-key columns. affected_rows may be zero for unchanged values. Database triggers and constraints still apply.', {**_TARGET, 'key': _KEY, 'values': _VALUES}),
        'delete_row': Operation('delete', 'Delete one row by its complete primary key. Database triggers and cascading constraints still apply.', {**_TARGET, 'key': _KEY}),
    }

    def _prepare(self, profile, operation, arguments):
        _known_fields(arguments, self.operations[operation].parameters)
        # Bound the entire input before connection/authentication, as well as each value.
        try:
            encoded = json.dumps(arguments, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise InfraError('invalid_argument', 'Arguments must be valid finite JSON') from None
        if len(encoded) > 262144:
            raise InfraError('invalid_argument', 'Operation arguments exceed 256 KiB')
        result = {}
        if operation not in {'check_connection', 'list_databases'}:
            database = _identifier(arguments.get('database', profile.options.get('database')), 'database')
            if database.lower() in _SYSTEM_DATABASES:
                raise InfraError('scope_denied', 'System databases are not available for business operations')
            profile.check_scope('databases', database)
            result['database'] = database
        if operation not in {'check_connection', 'list_databases', 'list_tables'}:
            table = _identifier(arguments.get('table'), 'table')
            profile.check_scope('tables', database + '.' + table)
            result['table'] = table
            result['target'] = _quote(database) + '.' + _quote(table)
        if operation in {'list_databases', 'list_tables', 'select_rows'}:
            result['limit'] = integer(arguments, 'limit', 100, 1, 200)
            result['offset'] = integer(arguments, 'offset', 0, 0, 1000000)
        if operation in {'insert_row', 'update_row'}:
            result['values'] = _mapping(arguments.get('values'), 'values')
        if operation in {'update_row', 'delete_row'}:
            result['key'] = _mapping(arguments.get('key'), 'key')
            if any(value is None for value in result['key'].values()):
                raise InfraError('invalid_argument', 'Primary-key values cannot be null')
        if operation == 'select_rows':
            columns = arguments.get('columns')
            if 'columns' in arguments:
                if not isinstance(columns, list) or not 1 <= len(columns) <= 200:
                    raise InfraError('invalid_argument', 'columns must contain between 1 and 200 names')
                columns = [_identifier(column, 'column') for column in columns]
                if len(set(columns)) != len(columns):
                    raise InfraError('invalid_argument', 'columns cannot contain duplicates')
            result['columns'] = columns
            conditions = arguments.get('where', [])
            if not isinstance(conditions, list) or len(conditions) > 20:
                raise InfraError('invalid_argument', 'where must be a list of at most 20 filters')
            filters, parameters, referenced = [], [], set(columns or [])
            for condition in conditions:
                _known_fields(condition, {'column', 'op', 'value'})
                column = _identifier(condition.get('column'), 'filter column')
                referenced.add(column)
                op = condition.get('op')
                if not isinstance(op, str) or op not in {*_COMPARISONS, 'in', 'is_null', 'is_not_null'}:
                    raise InfraError('invalid_argument', 'Unsupported filter operator')
                if op in {'is_null', 'is_not_null'}:
                    if 'value' in condition:
                        raise InfraError('invalid_argument', 'Null-check filters must omit value')
                    filters.append(_quote(column) + (' IS NULL' if op == 'is_null' else ' IS NOT NULL'))
                    continue
                if 'value' not in condition:
                    raise InfraError('invalid_argument', 'Filter value is required')
                value = condition['value']
                if op == 'in':
                    if not isinstance(value, list) or not 1 <= len(value) <= 100:
                        raise InfraError('invalid_argument', 'in requires between 1 and 100 scalar values')
                    parameters.extend(_scalar(item) for item in value)
                    filters.append(_quote(column) + ' IN (' + ', '.join(['%s'] * len(value)) + ')')
                else:
                    value = _scalar(value)
                    if value is None and op in {'eq', 'ne'}:
                        filters.append(_quote(column) + (' IS NULL' if op == 'eq' else ' IS NOT NULL'))
                    else:
                        filters.append(_quote(column) + ' ' + _COMPARISONS[op] + ' %s')
                        parameters.append(value)
            ordering = arguments.get('order_by', [])
            if not isinstance(ordering, list) or len(ordering) > 20:
                raise InfraError('invalid_argument', 'order_by must be a list of at most 20 columns')
            order_sql = []
            for item in ordering:
                _known_fields(item, {'column', 'direction'})
                column = _identifier(item.get('column'), 'order column')
                direction = item.get('direction', 'asc')
                if direction not in ('asc', 'desc'):
                    raise InfraError('invalid_argument', 'Order direction must be asc or desc')
                referenced.add(column)
                order_sql.append(_quote(column) + ' ' + direction.upper())
            result.update(where=(' WHERE ' + ' AND '.join(filters)) if filters else '',
                          where_params=parameters, order=(' ORDER BY ' + ', '.join(order_sql)) if order_sql else '',
                          referenced=referenced)
        return result

    def _client(self, profile):
        options = profile.options
        allowed = {'host', 'port', 'username', 'username_env', 'username_file', 'password_env', 'password_file',
                   'database', 'tls', 'ca_file', 'timeout', 'max_response_bytes', 'max_output_bytes', 'max_items',
                   'redact', 'environment'}
        if set(options) - allowed:
            raise InfraError('invalid_config', 'Unsupported MySQL connection options')
        host = options.get('host', '127.0.0.1')
        if not isinstance(host, str) or not host or len(host) > 253:
            raise InfraError('invalid_config', 'MySQL host must be an IP address or DNS hostname')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not all(_HOST_LABEL.fullmatch(label) for label in host.rstrip('.').split('.')):
                raise InfraError('invalid_config', 'MySQL host must be an IP address or DNS hostname') from None
        if 'username' in options and ('username_env' in options or 'username_file' in options):
            raise InfraError('invalid_config', 'Choose one username source')
        username = secret(profile, 'username') if 'username' not in options else options['username']
        if not isinstance(username, str) or not username or len(username.encode('utf-8')) > 256 or any(ord(char) < 32 or ord(char) == 127 for char in username):
            raise InfraError('invalid_config', 'MySQL username must be a nonempty string of at most 256 UTF-8 bytes without control characters')
        password = secret(profile, 'password')
        if password is not None and (not isinstance(password, str) or len(password.encode('utf-8')) > 65536):
            raise InfraError('invalid_config', 'MySQL password must be a string of at most 64 KiB')
        tls = options.get('tls', False)
        if type(tls) is not bool:
            raise InfraError('invalid_config', 'tls must be a boolean')
        context = None
        if 'ca_file' in options and not tls:
            raise InfraError('invalid_config', 'ca_file requires tls=true')
        if tls:
            ca_file = options.get('ca_file')
            if ca_file is not None:
                if not isinstance(ca_file, str) or not ca_file or '\x00' in ca_file:
                    raise InfraError('invalid_config', 'ca_file must be a certificate file path')
                ca_file = str(Path(ca_file).expanduser())
            try:
                context = ssl.create_default_context(cafile=ca_file)
            except (OSError, ValueError, ssl.SSLError):
                raise InfraError('invalid_config', 'Cannot load the configured MySQL CA certificate') from None
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
        if 'database' in options:
            _identifier(options['database'], 'configured database')
        timeout = profile.timeout
        # Never forward arbitrary driver options: multi-statements, local files, and init commands remain unavailable.
        return BoundedConnection(host=host, port=integer(options, 'port', 3306, 1, 65535),
            user=username, password=password.encode('utf-8') if password is not None else None, charset='utf8mb4', use_unicode=True,
            cursorclass=DictCursor, autocommit=False, local_infile=False, client_flag=0,
            ssl=context, ssl_disabled=not tls, connect_timeout=timeout, read_timeout=timeout, write_timeout=timeout,
            max_response_bytes=integer(options, 'max_response_bytes', 1048576, 1024, 16777216),
            operation_timeout=timeout)

    @staticmethod
    def _query(connection, cursor, sql, params=()):
        connection.check_deadline()
        cursor.execute(sql, tuple(params))
        connection.check_deadline()

    def _table_type(self, connection, cursor, data):
        self._query(connection, cursor,
            'SELECT TABLE_TYPE AS table_type, ENGINE AS engine FROM information_schema.TABLES '
            'WHERE BINARY TABLE_SCHEMA = BINARY %s AND BINARY TABLE_NAME = BINARY %s LIMIT 1', (data['database'], data['table']))
        table = cursor.fetchone()
        if not table:
            raise InfraError('not_found', 'Requested table was not found or is not accessible')
        if table['table_type'] != 'BASE TABLE' or table['engine'] != 'InnoDB':
            raise InfraError('invalid_argument', 'Only InnoDB base tables are supported')
        return table

    def _schema(self, connection, cursor, data):
        self._table_type(connection, cursor, data)
        # Hold a transaction-level metadata lock while rechecking schema and doing CRUD;
        # another session cannot swap the validated table or alter its primary key mid-write.
        self._query(connection, cursor, 'SELECT 1 FROM ' + data['target'] + ' LIMIT 0')
        self._table_type(connection, cursor, data)
        self._query(connection, cursor,
            'SELECT COLUMN_NAME AS column_name, COLUMN_TYPE AS column_type, IS_NULLABLE AS is_nullable, '
            'COLUMN_KEY AS column_key, EXTRA AS extra FROM information_schema.COLUMNS '
            'WHERE BINARY TABLE_SCHEMA = BINARY %s AND BINARY TABLE_NAME = BINARY %s ORDER BY ORDINAL_POSITION LIMIT 201',
            (data['database'], data['table']))
        columns = cursor.fetchall()
        if len(columns) > 200:
            raise InfraError('result_too_large', 'Tables with more than 200 columns are unsupported')
        if not columns:
            raise InfraError('not_found', 'Requested table columns are not accessible')
        names = {_identifier(column['column_name'], 'database column') for column in columns}
        # COLUMN_KEY=PRI may describe a UNIQUE NOT NULL index without an actual PRIMARY;
        # only the explicitly named PRIMARY index authorizes update/delete targeting.
        self._query(connection, cursor,
            'SELECT COLUMN_NAME AS column_name FROM information_schema.STATISTICS '
            'WHERE BINARY TABLE_SCHEMA = BINARY %s AND BINARY TABLE_NAME = BINARY %s AND INDEX_NAME = %s '
            'ORDER BY SEQ_IN_INDEX LIMIT 201', (data['database'], data['table'], 'PRIMARY'))
        primary_rows = cursor.fetchall()
        if len(primary_rows) > 200:
            raise InfraError('result_too_large', 'Primary keys with more than 200 columns are unsupported')
        primary_key = [_identifier(column['column_name'], 'primary key column') for column in primary_rows]
        if set(primary_key) - names or len(set(primary_key)) != len(primary_key):
            raise InfraError('backend_error', 'Inconsistent primary-key metadata')
        referenced = data.get('referenced', set()) | set(data.get('values', {})) | set(data.get('key', {}))
        if referenced - names:
            raise InfraError('invalid_argument', 'Requested column does not exist in this table')
        return columns, primary_key

    @staticmethod
    def _visible(profile, database, table=None):
        try:
            _identifier(database, 'database')
            if database.lower() in _SYSTEM_DATABASES:
                return False
            profile.check_scope('databases', database)
            if table is not None:
                _identifier(table, 'table')
                profile.check_scope('tables', database + '.' + table)
            return True
        except InfraError:
            return False

    def _list(self, connection, cursor, profile, operation, data):
        limit, offset = data['limit'], data['offset']
        if operation == 'list_databases':
            self._query(connection, cursor,
                'SELECT SCHEMA_NAME AS database_name FROM information_schema.SCHEMATA '
                'WHERE SCHEMA_NAME NOT IN (%s, %s, %s, %s) ORDER BY SCHEMA_NAME LIMIT %s OFFSET %s',
                (*sorted(_SYSTEM_DATABASES), limit + 1, offset))
        else:
            self._query(connection, cursor,
                'SELECT TABLE_NAME AS table_name FROM information_schema.TABLES '
                'WHERE BINARY TABLE_SCHEMA = BINARY %s AND TABLE_TYPE = %s AND ENGINE = %s ORDER BY TABLE_NAME LIMIT %s OFFSET %s',
                (data['database'], 'BASE TABLE', 'InnoDB', limit + 1, offset))
        candidates = cursor.fetchall()
        page = candidates[:limit]
        if operation == 'list_databases':
            items = [row['database_name'] for row in page if self._visible(profile, row['database_name'])]
            key = 'databases'
        else:
            items = [row['table_name'] for row in page if self._visible(profile, data['database'], row['table_name'])]
            key = 'tables'
        # Continuation counts scanned names, not returned names, so a filtered empty page can advance.
        return {key: items, 'offset': offset + len(page), 'has_more': len(candidates) > limit}

    def execute(self, profile, operation, arguments):
        data = self._prepare(profile, operation, arguments)
        connection = self._client(profile)
        commit_started = False
        try:
            cursor = connection.cursor()
            timeout = profile.timeout
            for variable, value in (('max_execution_time', max(1, int(timeout * 1000))),
                                    ('innodb_lock_wait_timeout', math.ceil(timeout)),
                                    ('lock_wait_timeout', math.ceil(timeout))):
                self._query(connection, cursor, f'SET SESSION {variable} = %s', (value,))
            if operation == 'check_connection':
                self._query(connection, cursor, 'SELECT 1')
                return {'reachable': bool(cursor.fetchone())}
            if operation in {'list_databases', 'list_tables'}:
                return self._list(connection, cursor, profile, operation, data)
            connection.check_deadline()
            connection.begin()
            columns, primary_key = self._schema(connection, cursor, data)
            if operation == 'describe_table':
                return {'database': data['database'], 'table': data['table'], 'engine': 'InnoDB',
                        'columns': columns, 'primary_key': primary_key}
            if operation == 'select_rows':
                columns_sql = ', '.join(_quote(column) for column in data['columns']) if data['columns'] else '*'
                self._query(connection, cursor, 'SELECT ' + columns_sql + ' FROM ' + data['target'] + data['where'] + data['order'] + ' LIMIT %s OFFSET %s',
                            (*data['where_params'], data['limit'] + 1, data['offset']))
                rows = cursor.fetchall()
                page = rows[:data['limit']]
                # Date/time values retain machine-readable ISO representations; other MySQL
                # values (Decimal and binary included) use the shared bounded output encoder.
                page = [{key: value.isoformat() if isinstance(value, (datetime.date, datetime.time)) else value
                         for key, value in row.items()} for row in page]
                return {'rows': page, 'offset': data['offset'] + len(page), 'has_more': len(rows) > data['limit']}
            if operation in {'update_row', 'delete_row'}:
                if not primary_key or set(data['key']) != set(primary_key):
                    raise InfraError('invalid_argument', 'update_row and delete_row require exactly the complete PRIMARY KEY')
                if set(data.get('values', {})) & set(primary_key):
                    raise InfraError('invalid_argument', 'Updating primary-key columns is not supported')
                predicate = ' AND '.join(_quote(column) + ' = %s' for column in primary_key)
                column_types = {column['column_name']: column['column_type'] for column in columns}
                key_values = tuple(_primary_value(data['key'][column], column_types[column]) for column in primary_key)
            if operation == 'insert_row':
                names = list(data['values'])
                sql = 'INSERT INTO ' + data['target'] + ' (' + ', '.join(_quote(name) for name in names) + ') VALUES (' + ', '.join(['%s'] * len(names)) + ')'
                params = tuple(data['values'].values())
            elif operation == 'update_row':
                sql = 'UPDATE ' + data['target'] + ' SET ' + ', '.join(_quote(name) + ' = %s' for name in data['values']) + ' WHERE ' + predicate
                params = (*data['values'].values(), *key_values)
            elif operation == 'delete_row':
                sql, params = 'DELETE FROM ' + data['target'] + ' WHERE ' + predicate, key_values
            else:
                raise InfraError('invalid_operation', 'Unsupported MySQL operation')
            self._query(connection, cursor, sql, params)
            affected_rows = cursor.rowcount
            if affected_rows not in (0, 1):
                raise InfraError('backend_error', 'Unexpected affected row count; transaction was not committed')
            result = {'affected_rows': affected_rows}
            if operation == 'insert_row':
                result['last_insert_id'] = cursor.lastrowid
            connection.check_deadline()
            # Once COMMIT may have reached the server, a transport error cannot prove rollback.
            # Never retry automatically: callers must verify the row before attempting again.
            commit_started = True
            connection.commit()
            return result
        except Exception:
            if commit_started:
                raise InfraError('outcome_unknown', 'Commit outcome is unknown; verify the row before retrying') from None
            raise
        finally:
            if not commit_started:
                try:
                    connection.rollback()
                except Exception:
                    pass
            # Closing the socket directly avoids draining an oversized or timed-out response.
            with contextlib.suppress(Exception):
                connection.force_close()
