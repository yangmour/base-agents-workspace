"""MySQL boundary tests use a deterministic connection; no real database is contacted."""
import importlib.util
import json
import ssl
from unittest.mock import Mock

import pytest

from infra_mcp.config import ACTIONS, InfraError, Profile


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.events = []
        self.columns = [
            {'column_name': 'id', 'column_type': 'bigint', 'is_nullable': 'NO', 'column_key': 'PRI', 'extra': ''},
            {'column_name': 'tenant', 'column_type': 'int', 'is_nullable': 'NO', 'column_key': 'PRI', 'extra': ''},
            {'column_name': 'name', 'column_type': 'varchar(255)', 'is_nullable': 'YES', 'column_key': '', 'extra': ''},
        ]
        self.table = {'table_type': 'BASE TABLE', 'engine': 'InnoDB'}
        self.primary = [{'column_name': 'id'}, {'column_name': 'tenant'}]
        self.rows = [{'id': 1, 'tenant': 2, 'name': 'test'}]
        self.databases = [{'database_name': 'app'}, {'database_name': 'outside'}, {'database_name': 'mysql'}]
        self.tables = [{'table_name': 'items'}, {'table_name': 'outside'}]
        self.rowcount = 1
        self.lastrowid = 9
        self.result = []
        self.fail_write = None
        self.fail_commit = None
        self.fail_rollback = None

    def cursor(self):
        return self

    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        self.events.append(sql)
        if 'information_schema.COLUMNS' in sql:
            self.result = self.columns
        elif 'information_schema.STATISTICS' in sql:
            self.result = self.primary
        elif 'information_schema.SCHEMATA' in sql:
            self.result = self.databases
        elif 'information_schema.TABLES' in sql:
            self.result = self.tables if 'AS table_name' in sql else ([self.table] if self.table else [])
        elif sql.startswith(('INSERT ', 'UPDATE ', 'DELETE ')):
            if self.fail_write:
                raise self.fail_write
            self.result = []
        elif sql == 'SELECT 1':
            self.result = [{'1': 1}]
        elif sql.startswith('SELECT 1 FROM'):
            self.result = []
        elif sql.startswith('SELECT '):
            self.result = self.rows
        else:
            self.result = []
        return self.rowcount

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0] if self.result else None

    def begin(self):
        self.events.append('BEGIN')

    def commit(self):
        self.events.append('COMMIT')
        if self.fail_commit:
            raise self.fail_commit

    def rollback(self):
        self.events.append('ROLLBACK')
        if self.fail_rollback:
            raise self.fail_rollback

    def force_close(self):
        self.events.append('CLOSE')

    def check_deadline(self):
        pass


def service(monkeypatch, permissions=ACTIONS, scope=None, **options):
    assert importlib.util.find_spec('infra_mcp.mysql_service'), 'MySQL adapter is not implemented'
    from infra_mcp.mysql_service import MySQLService
    connection = FakeConnection()
    constructor = Mock(return_value=connection)
    monkeypatch.setattr('infra_mcp.mysql_service.BoundedConnection', constructor)
    profile = Profile('test', 'mysql', {'username': 'tester', 'database': 'app', **options}, frozenset(permissions), scope or {})
    config = Mock()
    config.get.return_value = profile
    return MySQLService(config), connection, constructor


def run(backend, operation='select_rows', **args):
    action = {'insert_row': 'create', 'update_row': 'update', 'delete_row': 'delete'}.get(operation, 'read')
    return backend.run('test', action, operation, args)['data']


@pytest.mark.parametrize('operation,arguments', [
    ('select_rows', {'table': 'items'}), ('insert_row', {'table': 'items', 'values': {'name': 'new'}}),
    ('update_row', {'table': 'items', 'key': {'id': 1, 'tenant': 2}, 'values': {'name': 'new'}}),
    ('delete_row', {'table': 'items', 'key': {'id': 1, 'tenant': 2}}),
])
def test_permissions_deny_before_connect(monkeypatch, operation, arguments):
    backend, _, constructor = service(monkeypatch, permissions=[])
    with pytest.raises(InfraError) as error:
        run(backend, operation, **arguments)
    assert error.value.code == 'permission_denied'
    constructor.assert_not_called()


@pytest.mark.parametrize('args', [
    {'database': 'outside', 'table': 'items'}, {'table': 'outside'},
    {'database': 'mysql', 'table': 'user'}, {'database': 'information_schema', 'table': 'TABLES'},
    {'database': 'performance_schema', 'table': 'threads'}, {'database': 'sys', 'table': 'version'},
])
def test_scope_and_system_databases_deny_before_connect(monkeypatch, args):
    backend, _, constructor = service(monkeypatch, scope={'databases': ['app'], 'tables': ['app.items']})
    with pytest.raises(InfraError):
        run(backend, **args)
    constructor.assert_not_called()


@pytest.mark.parametrize('args', [
    {'table': 'items; DROP TABLE users'}, {'table': 'app.items'}, {'table': '`items`'},
    {'table': 'items', 'columns': ['name, SLEEP(10)']}, {'table': 'items', 'columns': []},
    {'table': 'items', 'where': [{'column': 'id', 'op': 'eq OR 1=1', 'value': 1}]},
    {'table': 'items', 'where': [{'column': 'id', 'op': 'in', 'value': []}]},
    {'table': 'items', 'where': [{'column': 'id', 'op': 'eq', 'value': {'nested': 1}}]},
    {'table': 'items', 'where': [{'column': 'id', 'op': 'eq', 'value': float('inf')}]},
    {'table': 'items', 'order_by': [{'column': 'id', 'direction': 'DESC; DROP TABLE t'}]},
    {'table': 'items', 'limit': True}, {'table': 'items', 'limit': 201},
    {'table': 'items', 'offset': 1000001}, {'table': 'items', 'sql': 'SELECT 1'},
])
def test_invalid_query_rejected_before_connect(monkeypatch, args):
    backend, _, constructor = service(monkeypatch)
    with pytest.raises(InfraError) as error:
        run(backend, **args)
    assert error.value.code == 'invalid_argument'
    constructor.assert_not_called()


@pytest.mark.parametrize('values', [{}, {'name': ['nested']}, {'name': {'nested': 1}}, {'name': 'x' * 65537}, {'bad.name': 1}, {'name': float('nan')}])
def test_invalid_write_values_rejected_before_connect(monkeypatch, values):
    backend, _, constructor = service(monkeypatch)
    with pytest.raises(InfraError) as error:
        run(backend, 'insert_row', table='items', values=values)
    assert error.value.code == 'invalid_argument'
    constructor.assert_not_called()


def test_total_input_has_byte_cap_before_connect(monkeypatch):
    backend, _, constructor = service(monkeypatch)
    with pytest.raises(InfraError):
        run(backend, 'insert_row', table='items', values={f'col{i}': 'x' * 65536 for i in range(5)})
    constructor.assert_not_called()


def test_select_binds_values_and_has_more_with_one_extra_row(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    injected = "x'; DROP TABLE items; --"
    connection.rows = [{'name': 'a'}, {'name': 'b'}, {'name': 'c'}]
    data = run(backend, table='items', columns=['name'], where=[{'column': 'name', 'op': 'eq', 'value': injected}],
               order_by=[{'column': 'id', 'direction': 'desc'}], limit=2, offset=5)
    sql, params = connection.calls[-1]
    assert sql == 'SELECT `name` FROM `app`.`items` WHERE `name` = %s ORDER BY `id` DESC LIMIT %s OFFSET %s'
    assert params == (injected, 3, 5) and injected not in sql
    assert data == {'rows': [{'name': 'a'}, {'name': 'b'}], 'offset': 7, 'has_more': True}
    assert connection.events[-2:] == ['ROLLBACK', 'CLOSE']


def test_null_in_and_comparisons_are_only_fixed_sql_tokens(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    run(backend, table='items', where=[{'column': 'name', 'op': 'eq', 'value': None},
        {'column': 'tenant', 'op': 'in', 'value': [1, 2]}, {'column': 'id', 'op': 'gte', 'value': 3},
        {'column': 'name', 'op': 'is_not_null'}])
    sql, params = connection.calls[-1]
    assert 'WHERE `name` IS NULL AND `tenant` IN (%s, %s) AND `id` >= %s AND `name` IS NOT NULL' in sql
    assert params == (1, 2, 3, 101, 0)


@pytest.mark.parametrize('key,values', [
    ({'id': 1}, {'name': 'a'}), ({'id': 1, 'tenant': 2, 'name': 'a'}, {'name': 'b'}),
    ({'id': 1, 'tenant': 2}, {'id': 3}), ({'id': 1, 'tenant': 2}, {'missing': 1}),
])
def test_update_requires_complete_primary_key_and_cannot_change_it(monkeypatch, key, values):
    backend, connection, _ = service(monkeypatch)
    with pytest.raises(InfraError) as error:
        run(backend, 'update_row', table='items', key=key, values=values)
    assert error.value.code == 'invalid_argument'
    assert not any(sql.startswith('UPDATE ') for sql, _ in connection.calls)
    assert connection.events[-2:] == ['ROLLBACK', 'CLOSE']


@pytest.mark.parametrize('operation', ['update_row', 'delete_row'])
def test_missing_primary_key_disallows_targeted_writes(monkeypatch, operation):
    backend, connection, _ = service(monkeypatch)
    for column in connection.columns:
        column['column_key'] = ''
    connection.primary = []
    args = {'table': 'items', 'key': {'id': 1}}
    if operation == 'update_row':
        args['values'] = {'name': 'a'}
    with pytest.raises(InfraError) as error:
        run(backend, operation, **args)
    assert error.value.code == 'invalid_argument'
    assert not any(sql.startswith(('UPDATE ', 'DELETE ')) for sql, _ in connection.calls)


@pytest.mark.parametrize('operation', ['select_rows', 'insert_row', 'update_row', 'delete_row', 'describe_table'])
@pytest.mark.parametrize('table', [{'table_type': 'VIEW', 'engine': None}, {'table_type': 'BASE TABLE', 'engine': 'MyISAM'}])
def test_only_innodb_base_tables_allowed(monkeypatch, operation, table):
    backend, connection, _ = service(monkeypatch)
    connection.table = table
    args = {'table': 'items'}
    if operation in {'insert_row', 'update_row'}:
        args['values'] = {'name': 'a'}
    if operation in {'update_row', 'delete_row'}:
        args['key'] = {'id': 1, 'tenant': 2}
    with pytest.raises(InfraError):
        run(backend, operation, **args)
    assert not any(sql.startswith(('INSERT ', 'UPDATE ', 'DELETE ', 'SELECT * FROM')) for sql, _ in connection.calls)
    assert connection.events[-1] == 'CLOSE'


def test_writes_are_one_transaction_with_mdl_and_bound_primary_key(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    result = run(backend, 'update_row', table='items', key={'tenant': 2, 'id': 1}, values={'name': "';--"})
    assert result == {'affected_rows': 1}
    sql, params = connection.calls[-1]
    assert sql == 'UPDATE `app`.`items` SET `name` = %s WHERE `id` = %s AND `tenant` = %s'
    assert params == ("';--", 1, 2)
    assert connection.events.index('BEGIN') < connection.events.index('SELECT 1 FROM `app`.`items` LIMIT 0')
    assert connection.events[-2:] == ['COMMIT', 'CLOSE']
    assert sum('information_schema.TABLES' in sql for sql, _ in connection.calls) == 2


def test_insert_and_delete_use_single_row_statements(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    assert run(backend, 'insert_row', table='items', values={'name': 'a'}) == {'affected_rows': 1, 'last_insert_id': 9}
    assert connection.calls[-1] == ('INSERT INTO `app`.`items` (`name`) VALUES (%s)', ('a',))
    connection.rowcount = 0
    assert run(backend, 'delete_row', table='items', key={'id': 1, 'tenant': 2}) == {'affected_rows': 0}
    assert connection.calls[-1] == ('DELETE FROM `app`.`items` WHERE `id` = %s AND `tenant` = %s', (1, 2))


def test_write_failure_rolls_back_without_leaking_or_retrying(monkeypatch):
    backend, connection, constructor = service(monkeypatch)
    connection.fail_write = RuntimeError('sensitive SQL/password')
    with pytest.raises(InfraError) as error:
        run(backend, 'insert_row', table='items', values={'name': 'a'})
    assert error.value.code == 'backend_error' and 'sensitive' not in str(error.value)
    assert connection.events[-2:] == ['ROLLBACK', 'CLOSE']
    constructor.assert_called_once()


def test_commit_failure_is_unknown_and_never_claims_rollback(monkeypatch):
    backend, connection, constructor = service(monkeypatch)
    connection.fail_commit = OSError('password-sensitive')
    with pytest.raises(InfraError) as error:
        run(backend, 'insert_row', table='items', values={'name': 'a'})
    assert error.value.code == 'outcome_unknown'
    assert 'verify' in str(error.value).lower() and 'password-sensitive' not in str(error.value)
    assert connection.events[-2:] == ['COMMIT', 'CLOSE'] and 'ROLLBACK' not in connection.events
    constructor.assert_called_once()


def test_unexpected_multirow_write_rolls_back(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    connection.rowcount = 2
    with pytest.raises(InfraError):
        run(backend, 'delete_row', table='items', key={'id': 1, 'tenant': 2})
    assert 'COMMIT' not in connection.events and connection.events[-2:] == ['ROLLBACK', 'CLOSE']


def test_connect_options_disable_extra_capabilities_and_bound_response(monkeypatch):
    backend, connection, constructor = service(monkeypatch, timeout=0.75, max_response_bytes=2048)
    assert run(backend, 'check_connection') == {'reachable': True}
    kwargs = constructor.call_args.kwargs
    assert kwargs['operation_timeout'] == 0.75 and kwargs['max_response_bytes'] == 2048
    assert kwargs['local_infile'] is False and kwargs['client_flag'] == 0 and kwargs['autocommit'] is False
    assert kwargs['charset'] == 'utf8mb4' and kwargs['use_unicode'] is True
    for name in ('connect_timeout', 'read_timeout', 'write_timeout'):
        assert 0 < kwargs[name] <= 0.75
    assert ('SET SESSION max_execution_time = %s', (750,)) in connection.calls
    assert ('SET SESSION innodb_lock_wait_timeout = %s', (1,)) in connection.calls
    assert ('SET SESSION lock_wait_timeout = %s', (1,)) in connection.calls


def test_tls_always_verifies_certificate_and_hostname(monkeypatch):
    backend, _, constructor = service(monkeypatch, tls=True)
    run(backend, 'check_connection')
    context = constructor.call_args.kwargs['ssl']
    assert isinstance(context, ssl.SSLContext) and context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize('options', [
    {'host': 'localhost/path'}, {'port': True}, {'tls': 'false'}, {'tls': False, 'ca_file': '/tmp/ca'},
    {'client_flag': 65536}, {'local_infile': True}, {'init_command': 'SET @a=1'},
    {'username': 2}, {'username': ''}, {'username': 'user', 'username_env': 'X'},
    {'max_response_bytes': 16777217},
])
def test_invalid_connection_config_never_connects(monkeypatch, options):
    backend, _, constructor = service(monkeypatch, **options)
    with pytest.raises(InfraError):
        run(backend, 'check_connection')
    constructor.assert_not_called()


def test_metadata_pages_filter_scope_without_returning_hidden_details(monkeypatch):
    backend, connection, _ = service(monkeypatch, scope={'databases': ['app'], 'tables': ['app.items']})
    data = run(backend, 'list_databases', limit=2)
    assert data == {'databases': ['app'], 'offset': 2, 'has_more': True}
    data = run(backend, 'list_tables', limit=1)
    assert data == {'tables': ['items'], 'offset': 1, 'has_more': True}
    assert all('LIMIT %s OFFSET %s' in sql for sql, _ in connection.calls if 'SCHEMATA' in sql or 'AS table_name' in sql)
    assert 'outside' not in json.dumps(data)


def test_schema_discovery_is_bounded_and_overwide_tables_fail_closed(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    connection.columns = [{'column_name': f'c{i}', 'column_key': ''} for i in range(201)]
    with pytest.raises(InfraError) as error:
        run(backend, table='items')
    assert error.value.code == 'result_too_large'
    assert len(connection.calls) <= 8
    assert any('information_schema.COLUMNS' in sql and 'LIMIT 201' in sql for sql, _ in connection.calls)


def test_unknown_column_rejected_before_business_query(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    with pytest.raises(InfraError):
        run(backend, table='items', columns=['missing'])
    assert not any(sql.startswith('SELECT `missing`') for sql, _ in connection.calls)


def test_plaintext_profile_explicitly_disables_opportunistic_tls(monkeypatch):
    backend, _, constructor = service(monkeypatch)
    run(backend, 'check_connection')
    assert constructor.call_args.kwargs['ssl_disabled'] is True


def test_tls_profile_explicitly_enables_verified_tls(monkeypatch):
    backend, _, constructor = service(monkeypatch, tls=True)
    run(backend, 'check_connection')
    assert constructor.call_args.kwargs['ssl_disabled'] is False


def test_unicode_password_is_encoded_as_utf8_bytes(monkeypatch):
    monkeypatch.setenv('MYSQL_TEST_PASSWORD', '密码')
    backend, _, constructor = service(monkeypatch, password_env='MYSQL_TEST_PASSWORD')
    run(backend, 'check_connection')
    assert constructor.call_args.kwargs['password'] == '密码'.encode('utf-8')


def test_close_error_does_not_turn_known_committed_write_into_failure(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    connection.force_close = Mock(side_effect=OSError('close failed'))
    assert run(backend, 'insert_row', table='items', values={'name': 'a'})['affected_rows'] == 1
    assert 'COMMIT' in connection.events


def test_unique_not_null_index_is_not_a_primary_key(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    # COLUMN_KEY can say PRI for a UNIQUE NOT NULL index when no PRIMARY KEY exists.
    connection.primary = []
    with pytest.raises(InfraError) as error:
        run(backend, 'delete_row', table='items', key={'id': 1, 'tenant': 2})
    assert error.value.code == 'invalid_argument'
    assert any('information_schema.STATISTICS' in sql and 'INDEX_NAME = %s' in sql and 'PRIMARY' in params
               for sql, params in connection.calls)
    assert not any(sql.startswith('DELETE ') for sql, _ in connection.calls)


def test_metadata_lookup_cannot_confuse_differently_cased_table_names(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    run(backend, table='items')
    for sql, params in connection.calls:
        if any(name in sql for name in ['information_schema.TABLES', 'information_schema.COLUMNS', 'information_schema.STATISTICS']):
            assert 'BINARY TABLE_SCHEMA = BINARY %s' in sql
            assert 'BINARY TABLE_NAME = BINARY %s' in sql


def test_change_to_nontransactional_table_during_mdl_acquisition_is_rejected(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    original = connection.execute
    def change_after_lock(sql, params=()):
        result = original(sql, params)
        if sql.startswith('SELECT 1 FROM'):
            connection.table = {'table_type': 'BASE TABLE', 'engine': 'MyISAM'}
        return result
    connection.execute = change_after_lock
    with pytest.raises(InfraError):
        run(backend, 'insert_row', table='items', values={'name': 'a'})
    assert not any(sql.startswith('INSERT ') for sql, _ in connection.calls)
    assert connection.events[-2:] == ['ROLLBACK', 'CLOSE']


def test_rollback_failure_does_not_leak_or_hide_original_failure(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    connection.fail_write = ValueError('write-secret')
    connection.fail_rollback = OSError('rollback-secret')
    with pytest.raises(InfraError) as error:
        run(backend, 'insert_row', table='items', values={'name': 'a'})
    assert error.value.code == 'backend_error' and 'ValueError' in str(error.value)
    assert 'secret' not in str(error.value) and connection.events[-1] == 'CLOSE'


@pytest.mark.parametrize('operation', ['select_rows', 'insert_row'])
def test_tables_without_primary_key_still_allow_read_and_insert(monkeypatch, operation):
    backend, connection, _ = service(monkeypatch)
    connection.primary = []
    args = {'table': 'items'}
    if operation == 'insert_row':
        args['values'] = {'name': 'a'}
    result = run(backend, operation, **args)
    assert result.get('affected_rows', 1) == 1


def test_describe_returns_real_primary_key_order(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    connection.primary = [{'column_name': 'tenant'}, {'column_name': 'id'}]
    data = run(backend, 'describe_table', table='items')
    assert data['primary_key'] == ['tenant', 'id']
    assert data['columns'] == connection.columns
    assert connection.events[-2:] == ['ROLLBACK', 'CLOSE']


@pytest.mark.parametrize('field', ['where', 'order_by'])
def test_filter_and_order_item_count_are_bounded_before_connect(monkeypatch, field):
    backend, _, constructor = service(monkeypatch)
    value = [{'column': 'id', 'op': 'eq', 'value': 1}] if field == 'where' else [{'column': 'id', 'direction': 'asc'}]
    with pytest.raises(InfraError):
        run(backend, table='items', **{field: value * 21})
    constructor.assert_not_called()


def test_missing_table_never_runs_business_sql(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    connection.table = None
    with pytest.raises(InfraError) as error:
        run(backend, 'insert_row', table='items', values={'name': 'a'})
    assert error.value.code == 'not_found'
    assert not any(sql.startswith('INSERT ') for sql, _ in connection.calls)


def test_unchanged_update_is_zero_affected_without_claiming_missing(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    connection.rowcount = 0
    assert run(backend, 'update_row', table='items', key={'id': 1, 'tenant': 2}, values={'name': 'test'}) == {'affected_rows': 0}
    assert connection.events[-2:] == ['COMMIT', 'CLOSE']


def test_deadline_after_successful_commit_ack_does_not_report_unknown_outcome(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    def deadline():
        if 'COMMIT' in connection.events:
            raise InfraError('timeout', 'late commit')
    connection.check_deadline = deadline
    assert run(backend, 'insert_row', table='items', values={'name': 'a'})['affected_rows'] == 1
    assert 'ROLLBACK' not in connection.events and connection.events[-1] == 'CLOSE'


def test_in_filter_values_and_null_ne_are_bound(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    payload = "'; SELECT SLEEP(10); --"
    run(backend, table='items', where=[{'column': 'name', 'op': 'in', 'value': [payload, True, None, 1.25]},
                                     {'column': 'name', 'op': 'ne', 'value': None}])
    sql, params = connection.calls[-1]
    assert '`name` IN (%s, %s, %s, %s) AND `name` IS NOT NULL' in sql
    assert payload not in sql and params[:4] == (payload, True, None, 1.25)


def test_date_decimal_binary_rows_use_shared_encoder(monkeypatch):
    import datetime
    from decimal import Decimal
    backend, connection, _ = service(monkeypatch)
    connection.rows = [{'date': datetime.date(2026, 11, 7), 'amount': Decimal('12.30'), 'binary': b'\xff'}]
    row = run(backend, table='items')['rows'][0]
    assert row == {'date': '2026-11-07', 'amount': '12.30', 'binary': {'encoding': 'base64', 'value': '/w=='}}


@pytest.mark.parametrize('key_value,column_type', [
    (0, 'varchar(64)'), (True, 'int'), (9007199254740992.0, 'bigint'),
    (1.5, 'decimal(10,2)'), (True, 'decimal(10,2)'), (True, 'double'),
    ('1e100', 'decimal(10,2)'), ('not-a-number', 'decimal(10,2)'),
    (123, 'datetime'), ('x', 'unknown_custom_type'),
])
def test_primary_key_types_cannot_use_ambiguous_mysql_coercion(monkeypatch, key_value, column_type):
    backend, connection, _ = service(monkeypatch)
    connection.columns[0]['column_type'] = column_type
    with pytest.raises(InfraError) as error:
        run(backend, 'update_row', table='items', key={'id': key_value, 'tenant': 2}, values={'name': 'new'})
    assert error.value.code == 'invalid_argument'
    assert not any(sql.startswith('UPDATE ') for sql, _ in connection.calls)
    assert connection.events[-2:] == ['ROLLBACK', 'CLOSE']


def test_numeric_input_for_text_primary_key_cannot_change_one_of_many_coerced_matches(monkeypatch):
    backend, connection, _ = service(monkeypatch)
    connection.columns[0]['column_type'] = 'varchar(64)'
    connection.primary = [{'column_name': 'id'}]
    # WHERE id = 0 would match both nonnumeric PKs. Only one changes, so rowcount=1 cannot catch it.
    connection.rows = [{'id': 'alpha', 'name': 'old'}, {'id': 'beta', 'name': 'new'}]
    connection.rowcount = 1
    with pytest.raises(InfraError):
        run(backend, 'update_row', table='items', key={'id': 0}, values={'name': 'new'})
    assert not any(sql.startswith('UPDATE ') for sql, _ in connection.calls)


@pytest.mark.parametrize('column_type,key_value,expected', [
    ('varchar(64)', 'alpha', 'alpha'), ('bigint unsigned', 9007199254740993, 9007199254740993),
    ('date', '2026-11-07', '2026-11-07'), ('double', 1.5, 1.5),
    ('bit(4)', 3, 3), ('year', 2026, 2026), ('varbinary(64)', 'abc', 'abc'),
])
def test_compatible_primary_key_types_keep_parameter_binding(monkeypatch, column_type, key_value, expected):
    backend, connection, _ = service(monkeypatch)
    connection.columns[0]['column_type'] = column_type
    run(backend, 'delete_row', table='items', key={'id': key_value, 'tenant': 2})
    assert connection.calls[-1][1] == (expected, 2)


def test_decimal_primary_key_binds_exact_decimal_literal(monkeypatch):
    from decimal import Decimal
    backend, connection, _ = service(monkeypatch)
    connection.columns[0]['column_type'] = 'decimal(30,4)'
    run(backend, 'delete_row', table='items', key={'id': '9007199254740993.2500', 'tenant': 2})
    assert type(connection.calls[-1][1][0]) is Decimal
    assert connection.calls[-1][1][0] == Decimal('9007199254740993.2500')


@pytest.mark.parametrize('column_type,key_value', [('enum(\'\',\'a\')', ''), ('set(\'a\',\'b\')', 'a,b'), ('timestamp', '2026-11-01 01:30:00')])
def test_enum_set_and_timestamp_primary_keys_fail_closed_for_writes(monkeypatch, column_type, key_value):
    backend, connection, _ = service(monkeypatch)
    connection.columns[0]['column_type'] = column_type
    with pytest.raises(InfraError) as error:
        run(backend, 'delete_row', table='items', key={'id': key_value, 'tenant': 2})
    assert error.value.code == 'invalid_argument'
    assert not any(sql.startswith('DELETE ') for sql, _ in connection.calls)
