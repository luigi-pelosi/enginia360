"""Riscontri di conservazione dati per l'unificazione degli utenti."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import unittest


def sql(database, statement):
    result = subprocess.run(
        ['docker', 'exec', '-i', 'enginia360-foundation-db', 'psql', '-U', 'postgres',
         '-d', database, '-X', '-At', '-v', 'ON_ERROR_STOP=1'],
        input=statement, text=True, capture_output=True, check=True,
    )
    return result.stdout.strip()


def snapshot(database):
    tables = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='foundation' ORDER BY tablename").splitlines()
    result = {}
    for table in tables:
        if not table.replace('_', '').isalnum():
            raise ValueError('Nome tabella inatteso')
        rows = sql(database, f'SELECT row_to_json(t) FROM foundation.{table} t ORDER BY id' if table not in ('login_limit', 'user_role', 'user_group_member', 'user_group_role', 'role_permission') else f'SELECT row_to_json(t) FROM foundation.{table} t')
        result[table] = [json.loads(line) for line in rows.splitlines() if line]
    return result


def ordered(rows):
    return sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows)


def verify(before, after):
    assert 'app_user' not in after, 'app_user ancora presente'
    assert set(after) == set(before) - {'app_user'}, 'Tabelle inattese o mancanti'
    old_accounts = {row['id']: row for row in before['account']}
    linked = {(row['tenant_id'], row['user_id']): row for row in before['account'] if row['tenant_id'] is not None}
    accounts = {row['id']: row for row in after['account']}
    by_name = {(row['tenant_id'], row['username']): row for row in after['account']}
    expected_count = len(before['account']) + sum((row['tenant_id'], row['id']) not in linked for row in before['app_user'])
    assert len(accounts) == expected_count, 'Numero account non conservato'
    remap = {}
    for row in after['account']:
        assert 'user_id' not in row, 'Collegamento intermedio ancora presente'
        assert row['is_super_admin'] == (row['tenant_id'] is None), 'Ambito Super Admin incoerente'
    for old in before['account']:
        current = accounts[old['id']]
        for field in ('id', 'tenant_id', 'password_hash', 'security_stamp', 'is_super_admin',
                      'must_change_password', 'failed_attempts', 'locked_until'):
            assert current[field] == old[field], f'Campo account non conservato: {field}'
        if old['tenant_id'] is None:
            for field, value in old.items():
                if field != 'user_id':
                    assert current[field] == value, f'Account piattaforma modificato: {field}'
    for user in before['app_user']:
        current = by_name[(user['tenant_id'], user['username'])]
        original = linked.get((user['tenant_id'], user['id']))
        if original:
            assert current['id'] == original['id'], 'ID account esistente modificato'
            assert current['is_enabled'] == (original['is_enabled'] and user['is_enabled'])
        else:
            assert current['password_hash'] is None, 'Credenziale inventata per utente senza accesso'
            assert current['is_enabled'] == user['is_enabled']
            if user['id'] not in old_accounts:
                assert current['id'] == user['id'], 'ID libero del vecchio utente non conservato'
        for field in ('username', 'display_name', 'email', 'tenant_id'):
            assert current[field] == user[field], f'Dato utente non conservato: {field}'
        oldest = min(datetime.fromisoformat(user['created_at']), datetime.fromisoformat(original['created_at'])) if original else datetime.fromisoformat(user['created_at'])
        assert datetime.fromisoformat(current['created_at']) == oldest
        remap[(user['tenant_id'], user['id'])] = current['id']
    for table, rows in before.items():
        if table in ('account', 'app_user'):
            continue
        expected = []
        for row in rows:
            transformed = dict(row)
            if table in ('user_role', 'user_group_member'):
                transformed['user_id'] = remap[(row['tenant_id'], row['user_id'])]
            expected.append(transformed)
        assert ordered(after[table]) == ordered(expected), f'Dati o associazioni non conservati: {table}'
    return {'tables': len(after), 'accounts': len(accounts), 'legacy_users_mapped': len(remap), 'audit_rows_preserved': len(before['audit_event'])}


class SchemaTests(unittest.TestCase):
    def test_unified_account_schema(self):
        database = os.environ.get('ENGINIA360_MIGRATION_DB', 'enginia360_account_validation')
        self.assertEqual(sql(database, "SELECT to_regclass('foundation.app_user') IS NULL"), 't')
        self.assertEqual(sql(database, "SELECT count(*) FROM information_schema.columns WHERE table_schema='foundation' AND table_name='account' AND column_name='user_id'"), '0')
        self.assertEqual(sql(database, "SELECT count(*) FROM information_schema.columns WHERE table_schema='foundation' AND table_name='account' AND column_name='email'"), '1')
        self.assertEqual(sql(database, "SELECT count(*) FROM pg_constraint WHERE contype='f' AND confrelid='foundation.account'::regclass AND conrelid IN ('foundation.user_role'::regclass,'foundation.user_group_member'::regclass)"), '2')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('snapshot', 'verify', 'schema'))
    parser.add_argument('--database', default='enginia360_account_validation')
    parser.add_argument('--file')
    args = parser.parse_args()
    if args.action == 'schema':
        os.environ['ENGINIA360_MIGRATION_DB'] = args.database
        unittest.main(argv=['account_migration_checks'], exit=True)
    else:
        if not args.file:
            parser.error('--file obbligatorio')
        target = Path(args.file)
        if not str(target.resolve()).startswith('/root/.config/enginia360/account-migration/'):
            raise ValueError('Gli snapshot riservati devono rimanere fuori dal repository')
        if args.action == 'snapshot':
            data = snapshot(args.database)
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as handle:
                json.dump(data, handle, ensure_ascii=False)
            print('Snapshot riservato acquisito senza esporre credenziali.')
        else:
            original = json.loads(target.read_text())
            print(json.dumps(verify(original, snapshot(args.database))))
