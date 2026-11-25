"""Disposable PostgreSQL 18 proof; requires Docker and a locally available image.

Run: python3 -m unittest discover -s tests/database -p test_currency_migration_runtime.py -v
No existing container or database is contacted. Override CURRENCY_TEST_IMAGE if needed.
"""
import os
from pathlib import Path
import subprocess
import time
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'database' / 'foundation.sql'
MIGRATION = ROOT / 'database' / 'migrations' / '20261120_currency.sql'
VERSION_MIGRATION = ROOT / 'database' / 'migrations' / '20261120_currency_version.sql'


def run(*args, input=None, check=True):
    return subprocess.run(args, input=input, text=True, capture_output=True, check=check)


class CurrencyMigrationRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.container = 'currency-proof-' + uuid.uuid4().hex[:12]
        cls.started = False
        try:
            image = os.environ.get('CURRENCY_TEST_IMAGE', 'postgres:18.6-alpine3.24')
            run('docker', 'image', 'inspect', image)
            run('docker', 'run', '-d', '--name', cls.container, '--network', 'none',
                '--tmpfs', '/var/lib/postgresql', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image)
            cls.started = True
            for _ in range(60):
                if run('docker', 'exec', cls.container, 'psql', '-X', '-qAt', '-h', '127.0.0.1', '-U', 'postgres', '-d', 'postgres', '-c', 'SELECT 1', check=False).returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError('isolated PostgreSQL did not start')
            cls.sql('postgres', 'CREATE ROLE enginia360_app;')
            for db in ('fresh', 'upgrade', 'collision', 'seed_collision'):
                run('docker', 'exec', cls.container, 'createdb', '-U', 'postgres', db)
            # Expand only the baseline's canonical includes, as in the repository loader.
            import sys
            sys.path.insert(0, str(ROOT / 'database'))
            from sql_source import load_foundation_sql
            baseline = load_foundation_sql(BASELINE)
            migration = MIGRATION.read_text()
            block = migration[migration.index('-- Fonte:'):migration.rindex('\nCOMMIT;')]
            if baseline.count(block) != 1:
                raise AssertionError('baseline currency definition/seed diverges from migration')
            version_migration = VERSION_MIGRATION.read_text()
            version_block = version_migration[version_migration.index('ALTER TABLE'):version_migration.rindex('COMMIT;')]
            old = baseline.replace(block, '', 1).replace(version_block, '', 1)
            cls.version_migration = version_migration
            cls.sql('fresh', baseline)
            for db in ('upgrade', 'collision', 'seed_collision'):
                cls.sql(db, old)
                cls.sql(db, "INSERT INTO foundation.tenant(id,code,name) VALUES ('10000000-0000-0000-0000-000000000001','currency-proof','Preserve me');")
            cls.migration = migration
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'started', False):
            run('docker', 'rm', '-f', cls.container, check=False)
            cls.started = False

    @classmethod
    def sql(cls, db, text, check=True):
        return run('docker', 'exec', '-i', cls.container, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', db, input=text, check=check)

    def test_migration_matches_fresh_schema_and_seed_preserves_existing_data(self):
        self.sql('upgrade', self.migration)
        before = self.sql('upgrade', "SELECT row_to_json(c)::text FROM foundation.currency c ORDER BY code").stdout
        self.sql('upgrade', self.version_migration)
        after = self.sql('upgrade', "SELECT (row_to_json(c)::jsonb - 'version')::text FROM foundation.currency c ORDER BY code").stdout
        import json
        self.assertEqual([json.loads(x) for x in before.splitlines()], [json.loads(x) for x in after.splitlines()])
        self.assertEqual(self.sql('upgrade', 'SELECT count(*) FROM foundation.currency WHERE version<>1;').stdout.strip(), '0')
        def dump(db):
            return run('docker', 'exec', self.container, 'pg_dump', '-U', 'postgres', '-s', '-t', 'foundation.currency', '--no-owner', db).stdout
        # pg_dump emits a random restrict key on each invocation.
        def normalize(s):
            return '\n'.join(line for line in s.splitlines() if not line.startswith(('\\restrict ', '\\unrestrict ')))
        self.assertEqual(normalize(dump('fresh')), normalize(dump('upgrade')))
        query = "SELECT code,numeric_code,name,coalesce(minor_units::text,'NULL'),is_enabled FROM foundation.currency ORDER BY code;"
        fresh = self.sql('fresh', query).stdout
        self.assertEqual(fresh, self.sql('upgrade', query).stdout)
        self.assertGreater(len(fresh.splitlines()), 100)
        self.assertIn('EUR|978|Euro|2|t', fresh)
        self.assertIn('XAU|959|Gold|NULL|t', fresh)
        self.assertEqual(self.sql('upgrade', "SELECT name FROM foundation.tenant WHERE code='currency-proof';").stdout.strip(), 'Preserve me')
        again = self.sql('upgrade', self.migration, check=False)
        self.assertNotEqual(again.returncode, 0)
        self.assertEqual(fresh, self.sql('upgrade', query).stdout)

    def test_preexisting_table_collision_rolls_back(self):
        self.sql('collision', 'CREATE TABLE foundation.currency (marker text); INSERT INTO foundation.currency VALUES (\'existing\');')
        result = self.sql('collision', self.migration, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already exists', result.stderr)
        self.assertEqual(self.sql('collision', "SELECT (SELECT marker FROM foundation.currency), (SELECT name FROM foundation.tenant WHERE code='currency-proof');").stdout.strip(), 'existing|Preserve me')

    def test_duplicate_seed_collision_rolls_back_ddl_and_data(self):
        original = "('AFN','971','Afghani',2)"
        duplicate = "('AED','784','UAE Dirham',2)"
        self.assertEqual(self.migration.count(original), 1)
        result = self.sql('seed_collision', self.migration.replace(original, duplicate, 1), check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('duplicate key', result.stderr)
        self.assertEqual(self.sql('seed_collision', "SELECT to_regclass('foundation.currency') IS NULL, (SELECT name FROM foundation.tenant WHERE code='currency-proof');").stdout.strip(), 't|Preserve me')


if __name__ == '__main__':
    unittest.main()
