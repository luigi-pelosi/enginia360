#!/usr/bin/env python3
"""Offline manifest contract, plus opt-in real PostgreSQL migration acceptance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
manifest_count = str(len(json.loads((ROOT/'database/runtime/manifest.json').read_text())))
ENGINE = ROOT / 'scripts/apply-runtime-migrations.py'

def engine():
    spec = importlib.util.spec_from_file_location('runtime_migrations', ENGINE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class ConfigurationTests(unittest.TestCase):
    def test_bootstrap_rejects_missing_overlapping_reserved_or_weak_runtime_values(self):
        spec = importlib.util.spec_from_file_location('runtime_config', ROOT / 'scripts/validate-runtime-config.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        good = {'R00_OWNER_USER':'runtime_owner', 'R00_APP_USER':'runtime_app',
                'R00_OWNER_PASSWORD':'a'*48, 'R00_APP_PASSWORD':'b'*48,
                'POSTGRES_PASSWORD':'c'*48, 'POSTGRES_DB':'runtime'}
        module.validate(good)
        for key, value in [('R00_OWNER_USER','pg_reserved'), ('R00_APP_USER','runtime_owner'),
                           ('R00_APP_PASSWORD','a'*48), ('R00_OWNER_PASSWORD',''),
                           ('POSTGRES_PASSWORD','weak'), ('POSTGRES_DB','bad database')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    module.validate(dict(good, **{key:value}))

class BaselineTests(unittest.TestCase):
    def test_runtime_baseline_has_fifteen_units_without_business_dml(self):
        path = ROOT / 'database/runtime/manifest.json'
        units = engine().load_manifest(path) if path.exists() else []
        self.assertEqual(len(units), int(manifest_count), 'fixture-free runtime schema missing')
        published = json.loads(path.read_text())[:14]
        digest = hashlib.sha256(json.dumps(published, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '91cd082ac5ad4ccf370161047d586b357b804d5e99f013947046507f766650b2',
                         'published R00.a manifest prefix changed')
        self.assertEqual(hashlib.sha256(json.dumps(json.loads(path.read_text())[:15],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                         'e482b5b8ee7d876c97a3704ebf0fe63da8437782be8d9e59feea00d9f982eb7e','published 15-unit prefix changed')
        self.assertEqual(hashlib.sha256(json.dumps(json.loads(path.read_text())[:16],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                         '48c02b9f2af5a24892ab54a81894ab71a96d722d241ee120089993bcefbf1512','published 16-unit prefix changed')
        for unit in units[:15]:
            self.assertNotRegex(unit['sql'], r'(?im)^\s*INSERT\s+INTO', unit['id'])
        self.assertIn('accounting.chart_accounts', units[13]['sql'])
        self.assertIn('organization_access.external_identity_bindings', units[14]['sql'])

class ManifestTests(unittest.TestCase):
    def test_rejects_drift_traversal_duplicates_gaps_and_wrappers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'migrations').mkdir()
            sql = b'SELECT 1;\n'
            filename = root / 'migrations/0001_example.sql'
            filename.write_bytes(sql)
            good = {'id': '0001_example', 'path': 'migrations/0001_example.sql',
                    'sha256': hashlib.sha256(sql).hexdigest()}
            cases = [[dict(good, sha256='0'*64)], [dict(good, path='../escape.sql')],
                     [good, good], [dict(good, id='0002_example')],
                     [dict(good, path='/etc/passwd')], [],
                     [dict(good, id='0001_example\u0027')]]
            for entries in cases:
                with self.subTest(entries=entries):
                    (root / 'manifest.json').write_text(json.dumps(entries))
                    with self.assertRaises(ValueError):
                        engine().load_manifest(root / 'manifest.json')
            for sql in [b'BEGIN;\nSELECT 1;\nCOMMIT;\n', b'\\connect elsewhere\n',
                        b'-- wrapper comment\nBEGIN; SELECT 1; COMMIT;', b'SELECT 1; COMMIT;']:
                filename.write_bytes(sql)
                (root / 'manifest.json').write_text(json.dumps([dict(good, sha256=hashlib.sha256(sql).hexdigest())]))
                with self.assertRaises(ValueError):
                    engine().load_manifest(root / 'manifest.json')

    def test_explicit_manifest_preserves_order_and_verified_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'migrations').mkdir()
            sql = b'CREATE SCHEMA example;\n'
            (root / 'migrations/0001_example.sql').write_bytes(sql)
            manifest = [{'id': '0001_example', 'path': 'migrations/0001_example.sql',
                         'sha256': hashlib.sha256(sql).hexdigest()}]
            (root / 'manifest.json').write_text(json.dumps(manifest))
            module = engine()
            actual = module.load_manifest(root / 'manifest.json') if module else []
            self.assertEqual([(entry['id'], entry['sql']) for entry in actual], [('0001_example', sql.decode())])

import subprocess
import secrets

@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS') == '1', 'real PostgreSQL opt-in; CI runner must enable')
class PostgreSqlTests(unittest.TestCase):
    def setUp(self):
        self.database = 'r00a_test_' + secrets.token_hex(8)
        self.owner = os.environ['R00_OWNER_USER']
        self.sql(f'CREATE DATABASE "{self.database}" OWNER "{self.owner}"', database=os.environ['PGDATABASE'])

    def tearDown(self):
        self.sql(f'DROP DATABASE "{self.database}" WITH (FORCE)', database=os.environ['PGDATABASE'])

    def sql(self, sql, database=None, app=False):
        env = dict(os.environ, PGDATABASE=database or self.database)
        if app:
            env.update(PGUSER=os.environ['R00_APP_USER'], PGPASSWORD=os.environ['R00_APP_PASSWORD'])
        result = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'], input=sql, text=True,
                                env=env, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def start_migration(self, manifest=None):
        env = dict(os.environ, PGDATABASE=self.database, PGUSER=self.owner,
                   PGPASSWORD=os.environ['R00_OWNER_PASSWORD'])
        args = ['python3', str(ENGINE), '--manifest', str(manifest or ROOT / 'database/runtime/manifest.json')]
        return subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def migrate(self, manifest=None):
        process = self.start_migration(manifest)
        try:
            output, error = process.communicate(timeout=35)
            return process.returncode, output, error
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def manifest(self, statements):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / 'migrations').mkdir()
        entries = []
        for number, statement in enumerate(statements, 1):
            identifier = f'{number:04d}_unit'
            (root / f'migrations/{identifier}.sql').write_text(statement)
            entries.append({'id': identifier, 'path': f'migrations/{identifier}.sql', 'sha256': hashlib.sha256(statement.encode()).hexdigest()})
        (root / 'manifest.json').write_text(json.dumps(entries))
        return root / 'manifest.json'

    def test_checksum_history_future_and_gap_are_refused_without_writes(self):
        statements = ['CREATE SCHEMA probe;', 'CREATE TABLE probe.second(id int);']
        path = self.manifest(statements)
        self.assertEqual(self.migrate(path)[0], 0)
        self.assertNotEqual(self.migrate(self.manifest([statements[0]+'-- changed', statements[1]]))[0], 0, 'checksum drift was silently adopted')
        self.sql("INSERT INTO runtime_migrations.applied(id,checksum) VALUES('9999_future',repeat('0',64))")
        self.assertNotEqual(self.migrate(path)[0], 0, 'future history accepted')
        self.sql("DELETE FROM runtime_migrations.applied WHERE id IN ('9999_future','0001_unit')")
        self.assertNotEqual(self.migrate(path)[0], 0, 'non-prefix history accepted')

    def test_user_schema_with_pg_letters_is_not_mistaken_for_system_schema(self):
        self.sql('CREATE SCHEMA pgx_legacy; CREATE TABLE pgx_legacy.business(id int);')
        self.assertNotEqual(self.migrate()[0], 0, 'user schema with pg prefix was silently adopted')
        self.assertEqual(self.sql("SELECT to_regnamespace('runtime_migrations') IS NULL"), 't')

    def test_untracked_nonempty_database_is_never_adopted(self):
        self.sql('CREATE TABLE public.legacy_business(id int);')
        self.assertNotEqual(self.migrate()[0], 0, 'untracked nonempty database was adopted')
        self.assertEqual(self.sql("SELECT to_regnamespace('runtime_migrations') IS NULL"), 't')

    def test_concurrent_runners_share_lock_and_recheck_ledger(self):
        path = self.manifest(["CREATE SCHEMA probe; CREATE TABLE probe.runs(pid int, locks int); INSERT INTO probe.runs SELECT pg_backend_pid(),count(*) FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory' AND granted; SELECT pg_sleep(1);"])
        first = self.start_migration(path)
        import time
        for _ in range(100):
            if self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='enginia360-runtime-migrator'") != '0':
                break
            time.sleep(0.02)
        second = self.start_migration(path)
        try:
            first_output = first.communicate(timeout=20)
            second_output = second.communicate(timeout=20)
            self.assertEqual([first.returncode, second.returncode], [0, 0], (first_output, second_output))
            self.assertEqual(self.sql('SELECT count(*) FROM probe.runs'), '1')
            self.assertEqual(self.sql('SELECT locks FROM probe.runs'), '1', 'migration SQL did not execute on the advisory-lock connection')
            self.assertEqual(self.sql('SELECT count(*) FROM runtime_migrations.applied'), '1')
        finally:
            for process in (first, second):
                if process.poll() is None:
                    process.kill()
                process.communicate()

    def test_advisory_lock_wait_is_bounded_before_ledger_creation(self):
        import time
        env = dict(os.environ, PGDATABASE=self.database, PGAPPNAME='r00a-lock-holder')
        holder = subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1','-c',"SELECT pg_advisory_lock(hashtextextended('enginia360.runtime_migrations.v1',0)); SELECT pg_sleep(20);"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            active = '0'
            for _ in range(100):
                active = self.sql("SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE a.datname=current_database() AND a.application_name='r00a-lock-holder' AND l.locktype='advisory' AND l.granted")
                if active == '1':
                    break
                time.sleep(0.02)
            self.assertEqual(active, '1')
            started = time.monotonic()
            self.assertNotEqual(self.migrate()[0], 0)
            self.assertLess(time.monotonic()-started, 15)
            self.assertEqual(self.sql("SELECT to_regnamespace('runtime_migrations') IS NULL"), 't')
        finally:
            self.sql("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND application_name='r00a-lock-holder'")
            holder.communicate(timeout=5)

    def test_application_role_memberships_cannot_enable_escalation(self):
        app = os.environ['R00_APP_USER']
        self.sql(f'GRANT postgres TO "{app}"')
        try:
            self.assertNotEqual(self.migrate()[0], 0, 'application role could SET ROLE to infrastructure')
        finally:
            self.sql(f'REVOKE postgres FROM "{app}"')

    def test_outbox_role_must_remain_nologin_and_narrow(self):
        self.sql('ALTER ROLE enginia360_outbox_reader LOGIN')
        try:
            self.assertNotEqual(self.migrate()[0], 0, 'interactive BYPASSRLS outbox role accepted')
        finally:
            self.sql('ALTER ROLE enginia360_outbox_reader NOLOGIN')

    def test_unsafe_application_role_is_refused_before_any_ddl(self):
        app = os.environ['R00_APP_USER']
        self.sql(f'ALTER ROLE "{app}" BYPASSRLS')
        try:
            self.assertNotEqual(self.migrate()[0], 0, 'BYPASSRLS application role accepted')
            self.assertEqual(self.sql("SELECT to_regnamespace('runtime_migrations') IS NULL"), 't')
        finally:
            self.sql(f'ALTER ROLE "{app}" NOBYPASSRLS')

    def test_killed_runner_cannot_leave_child_to_commit_unrecorded_work(self):
        path = self.manifest(['CREATE SCHEMA probe;', 'CREATE TABLE probe.killed(id int); DO $$ BEGIN PERFORM pg_sleep(2); END $$;'])
        process = self.start_migration(path)
        import time
        active = '0'
        try:
            for _ in range(100):
                active = self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='enginia360-runtime-migrator' AND query LIKE '%pg_sleep(2)%'")
                if active == '1':
                    break
                time.sleep(0.02)
            self.assertEqual(active, '1')
            process.kill()
            process.communicate(timeout=5)
            time.sleep(2.2)
            self.assertEqual(self.sql("SELECT to_regclass('probe.killed') IS NULL"), 't', 'orphaned child committed after runner SIGKILL')
            self.assertEqual(self.sql('SELECT count(*) FROM runtime_migrations.applied'), '1')
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()

    def test_terminating_runner_closes_lock_connection_and_rolls_back_unit(self):
        path = self.manifest(['CREATE SCHEMA probe;', 'CREATE TABLE probe.cancelled(id int); SELECT pg_sleep(8);'])
        process = self.start_migration(path)
        import time
        try:
            for _ in range(100):
                active = self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='enginia360-runtime-migrator' AND query LIKE '%pg_sleep(8)%'")
                if active == '1':
                    break
                time.sleep(0.02)
            self.assertEqual(active, '1', 'cancellation test never reached in-flight unit')
            process.terminate()
            process.communicate(timeout=5)
            time.sleep(0.2)
            self.assertEqual(self.sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND application_name='enginia360-runtime-migrator'"), '0', 'runner left its connection/lock alive')
            self.assertEqual(self.sql("SELECT to_regclass('probe.cancelled') IS NULL"), 't')
            self.assertEqual(self.sql('SELECT count(*) FROM runtime_migrations.applied'), '1')
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()

    def test_future_ledger_is_refused(self):
        path = self.manifest(['CREATE SCHEMA probe;'])
        self.assertEqual(self.migrate(path)[0], 0)
        self.sql("INSERT INTO runtime_migrations.applied(id,checksum) VALUES('9999_future',repeat('0',64))")
        self.assertNotEqual(self.migrate(path)[0], 0, 'future history accepted')

    def test_gapped_ledger_is_refused(self):
        path = self.manifest(['CREATE SCHEMA IF NOT EXISTS probe;', 'CREATE TABLE probe.second(id int);'])
        self.assertEqual(self.migrate(path)[0], 0)
        self.sql("DELETE FROM runtime_migrations.applied WHERE id='0001_unit'")
        self.assertNotEqual(self.migrate(path)[0], 0, 'gapped history accepted')

    def test_damaged_ledger_checksum_is_refused(self):
        path = self.manifest(['CREATE SCHEMA probe;'])
        self.assertEqual(self.migrate(path)[0], 0)
        self.sql("UPDATE runtime_migrations.applied SET checksum=repeat('0',64)")
        self.assertNotEqual(self.migrate(path)[0], 0, 'damaged ledger checksum accepted')

    def test_history_regressions_fail_when_prefix_guard_is_removed(self):
        global ENGINE
        original = ENGINE
        source = original.read_text()
        needle = 'IF EXISTS (SELECT 1 FROM runtime_migrations.applied a FULL JOIN expected_migrations e USING (id)'
        self.assertEqual(source.count(needle), 1)
        with tempfile.TemporaryDirectory() as directory:
            mutant = Path(directory) / 'mutant.py'
            mutant.write_text(source.replace(needle, needle.replace('IF EXISTS', 'IF FALSE AND EXISTS')))
            try:
                ENGINE = mutant
                suite = unittest.TestSuite(PostgreSqlTests(name) for name in (
                    'test_future_ledger_is_refused', 'test_gapped_ledger_is_refused', 'test_damaged_ledger_checksum_is_refused'))
                result = unittest.TestResult()
                suite.run(result)
                self.assertEqual(result.testsRun, 3)
                self.assertEqual(len(result.errors), 0, result.errors)
                self.assertEqual(len(result.failures), 3, 'history tests did not detect all three unsafe adoptions')
            finally:
                ENGINE = original

    def test_role_privileges_and_rls_with_opt_in_synthetic_rows(self):
        self.assertEqual(self.migrate()[0], 0)
        app = os.environ['R00_APP_USER']
        self.assertEqual(self.sql(f"SELECT NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolinherit) FROM pg_roles WHERE rolname='{app}'"), 't')
        self.assertEqual(self.sql(f"SELECT count(*) FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname='{app}')"), '0')
        self.assertEqual(self.sql(f"SELECT pg_has_role('{app}','enginia360_outbox_reader','MEMBER') OR pg_has_role('{app}','{self.owner}','MEMBER')"), 'f')
        self.assertEqual(self.sql("SELECT NOT rolcanlogin AND rolbypassrls AND NOT (rolsuper OR rolcreatedb OR rolcreaterole) FROM pg_roles WHERE rolname='enginia360_outbox_reader'"), 't')
        self.assertEqual(self.sql("SELECT count(*) FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner WHERE r.rolname='enginia360_outbox_reader' AND p.prosecdef AND p.proconfig=ARRAY['search_path=pg_catalog, pg_temp']"), '2')
        self.assertEqual(self.sql("SELECT has_schema_privilege('enginia360_outbox_reader','workshop','CREATE') OR has_table_privilege('enginia360_outbox_reader','workshop.administrative_requests','SELECT')"), 'f')
        for statement in ['SET ROLE enginia360_outbox_reader', f'SET ROLE "{self.owner}"', 'CREATE ROLE forbidden', "INSERT INTO runtime_migrations.applied(id,checksum) VALUES('9999_fake',repeat('0',64))", 'CREATE TABLE public.forbidden(id int)']:
            env = dict(os.environ, PGDATABASE=self.database, PGUSER=app, PGPASSWORD=os.environ['R00_APP_PASSWORD'])
            result = subprocess.run(['psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1'], input=statement, text=True, env=env, capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0, statement)
        # Acceptance data, inserted only after the empty-database proof. Never part of a migration.
        self.sql('''INSERT INTO counterparties.counterparties VALUES
 ('11111111-0000-0000-0000-000000000001','11111111-1111-1111-1111-111111111111','Synthetic A','SYNTH-A','Test only'),
 ('22222222-0000-0000-0000-000000000001','22222222-2222-2222-2222-222222222222','Synthetic B','SYNTH-B','Test only');''')
        self.assertEqual(self.sql('SELECT count(*) FROM counterparties.counterparties', app=True), '0')
        for tenant in ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222'):
            for end in ('COMMIT', 'ROLLBACK'):
                output = self.sql(f"BEGIN; SET LOCAL app.tenant_id='{tenant}'; SELECT count(*) FROM counterparties.counterparties; {end}; SELECT count(*) FROM counterparties.counterparties;", app=True)
                self.assertEqual(output.splitlines(), ['1','0'])

    def test_dump_restore_to_distinct_ephemeral_database_preserves_manifest(self):
        self.assertEqual(self.migrate()[0], 0)
        restored = self.database + '_restore'
        self.sql(f'CREATE DATABASE "{restored}" OWNER "{self.owner}"', database=os.environ['PGDATABASE'])
        try:
            with tempfile.TemporaryDirectory() as directory:
                dump = Path(directory) / 'runtime.dump'
                env = dict(os.environ, PGDATABASE=self.database)
                subprocess.run(['pg_dump', '-Fc', '-f', str(dump)], env=env, check=True, capture_output=True, timeout=20)
                self.assertGreater(dump.stat().st_size, 0)
                digest = hashlib.sha256(dump.read_bytes()).hexdigest()
                subprocess.run(['pg_restore', '--exit-on-error', '-d', restored, str(dump)], env=env, check=True, capture_output=True, timeout=20)
                self.assertEqual(hashlib.sha256(dump.read_bytes()).hexdigest(), digest)
            self.assertEqual(self.sql('SELECT row_to_json(a) FROM runtime_migrations.applied a ORDER BY id'), self.sql('SELECT row_to_json(a) FROM runtime_migrations.applied a ORDER BY id', database=restored))
            original = self.database
            self.database = restored
            try:
                self.assertEqual(self.migrate()[0], 0)
            finally:
                self.database = original
        finally:
            self.sql(f'DROP DATABASE "{restored}" WITH (FORCE)', database=os.environ['PGDATABASE'])

    def test_failed_unit_rolls_back_and_resume_starts_at_failed_unit(self):
        first = 'CREATE SCHEMA probe; CREATE TABLE probe.first(pid int); INSERT INTO probe.first VALUES(pg_backend_pid());'
        second = 'CREATE TABLE probe.second(pid int); INSERT INTO probe.second VALUES(pg_backend_pid());'
        third = 'CREATE TABLE probe.third(pid int); INSERT INTO probe.third VALUES(pg_backend_pid());'
        path = self.manifest([first, second + 'SELECT 1/0;', third])
        self.assertNotEqual(self.migrate(path)[0], 0)
        self.assertEqual(self.sql('SELECT count(*) FROM runtime_migrations.applied'), '1')
        self.assertEqual(self.sql("SELECT to_regclass('probe.second') IS NULL AND to_regclass('probe.third') IS NULL"), 't', 'failed unit leaked DDL or later unit ran')
        self.assertEqual(self.migrate(self.manifest([first, second, third]))[0], 0)
        self.assertEqual(self.sql('SELECT count(*) FROM probe.first'), '1')
        self.assertEqual(self.sql('SELECT count(*) FROM runtime_migrations.applied'), '3')
        self.assertEqual(self.sql('SELECT (SELECT pid FROM probe.second)=(SELECT pid FROM probe.third)'), 't', 'units must share one connection')

    def test_first_boot_has_complete_empty_rls_schema_and_second_boot_is_noop(self):
        code, output, error = self.migrate()
        self.assertEqual(code, 0, error)
        self.assertEqual(self.sql("SELECT to_regclass('runtime_migrations.applied') IS NOT NULL"), 't', 'migration ledger absent')
        self.assertEqual(self.sql('SELECT count(*) FROM runtime_migrations.applied'), manifest_count)
        tables = self.sql("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema','runtime_migrations') ORDER BY 1").splitlines()
        import re
        units = engine().load_manifest(ROOT / 'database/runtime/manifest.json')
        expected = {table for unit in units for table in re.findall(r'CREATE TABLE(?: IF NOT EXISTS)? ([a-z_]+\.[a-z_]+)', unit['sql'])}
        self.assertEqual(set(tables), expected, 'runtime schema inventory differs from the full manifest')
        self.assertIn('billing.invoices', tables)
        self.assertIn('accounting.chart_accounts', tables)
        for table in tables:
            self.assertEqual(self.sql(f'SELECT count(*) FROM {table}'), '0', table)
        self.assertEqual(self.sql("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT IN ('pg_catalog','information_schema','runtime_migrations') AND c.relkind='r' AND NOT (c.relrowsecurity AND c.relforcerowsecurity)"), '0')
        before = self.sql('SELECT row_to_json(a) FROM runtime_migrations.applied a ORDER BY id')
        self.assertEqual(self.migrate()[0], 0)
        self.assertEqual(self.sql('SELECT row_to_json(a) FROM runtime_migrations.applied a ORDER BY id'), before)

if __name__ == '__main__':
    unittest.main()
