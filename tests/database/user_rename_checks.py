"""Riscontri di conservazione per la sola rinomina account → user."""

import json
import subprocess


def query(container, sql):
    result = subprocess.run(
        ['docker', 'exec', '-i', container, 'psql', '-U', 'postgres',
         '-d', 'enginia360', '-X', '-At', '-v', 'ON_ERROR_STOP=1'],
        input=sql, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def snapshot(container):
    tables = json.loads(query(container, """
        SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables
        WHERE schemaname='foundation';
    """))
    entries = []
    for table in tables:
        identifier = table.replace('"', '""')
        literal = table.replace("'", "''")
        entries.append(f"'{literal}',(SELECT coalesce(json_agg(t),'[]') FROM foundation.\"{identifier}\" t)")
    identity = """
        SELECT json_build_object(
            'oid',c.oid,'owner',pg_get_userbyid(c.relowner),'acl',c.relacl::text,
            'constraints',(SELECT json_agg(definition ORDER BY definition) FROM (
                SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conrelid=c.oid
            ) x),
            'indexes',(SELECT json_agg(definition ORDER BY definition::text) FROM (
                SELECT json_build_object('unique',indisunique,'primary',indisprimary,
                    'keys',indkey::text,'expression',pg_get_expr(indexprs,indrelid),
                    'predicate',pg_get_expr(indpred,indrelid)) AS definition
                FROM pg_index WHERE indrelid=c.oid
            ) x),
            'references',(SELECT json_agg(definition ORDER BY definition::text) FROM (
                SELECT json_build_object('table',conrelid::regclass::text,
                    'keys',conkey::text,'referenced_keys',confkey::text,
                    'update',confupdtype,'delete',confdeltype) AS definition
                FROM pg_constraint WHERE confrelid=c.oid
            ) x),
            'triggers',(SELECT json_agg(definition ORDER BY definition::text) FROM (
                SELECT json_build_object('name',tgname,'function',tgfoid,
                    'type',tgtype,'enabled',tgenabled,'args',encode(tgargs,'hex')) AS definition
                FROM pg_trigger WHERE tgrelid=c.oid AND NOT tgisinternal
            ) x)
        ) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='foundation' AND c.relname IN ('account','user')
    """
    return json.loads(query(container,
        "SELECT json_build_object('tables',json_build_object(" + ','.join(entries)
        + "),'identity',(" + identity + '));'))


def verify(before, after):
    expected = dict(before['tables'])
    expected['user'] = expected.pop('account')
    assert set(expected) == set(after['tables']), 'Insieme delle tabelle diverso dal previsto'
    ordered = lambda rows: sorted(json.dumps(row, sort_keys=True) for row in rows)
    for table, rows in expected.items():
        assert ordered(rows) == ordered(after['tables'][table]), f'Dati modificati: {table}'
    assert before['identity'] == after['identity'], 'Identità fisica, vincoli o privilegi modificati'
    return {'tables_preserved': len(expected), 'users_preserved': len(expected['user']),
            'data_credentials_permissions_preserved': True, 'relation_oid_preserved': True}
