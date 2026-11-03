#!/usr/bin/env python3
"""Opt-in real PostgreSQL platform authority acceptance."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch as mock_patch
import uuid
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('legacy', ROOT / 'scripts/test-r00-migrations.py')
assert spec and spec.loader
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS') == '1', 'isolated SQL required')
class AuthorityTests(unittest.TestCase):
    setUp = legacy.PostgreSqlTests.setUp
    tearDown = legacy.PostgreSqlTests.tearDown
    sql = legacy.PostgreSqlTests.sql
    start_migration = legacy.PostgreSqlTests.start_migration
    migrate = legacy.PostgreSqlTests.migrate

    def test_no_default_and_forced_rls(self):
        self.assertEqual(self.migrate()[0], 0)
        self.assertEqual(self.sql("SELECT to_regclass('organization_access.platform_authority') IS NOT NULL"), 't', 'persistent platform authority missing')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority'), '0')
        self.assertEqual(self.sql("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='organization_access.platform_authority'::regclass"), 't')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'), '0')

    def owner_sql(self, text, ok=True):
        env = dict(os.environ, PGDATABASE=self.database, PGUSER=self.owner, PGPASSWORD=os.environ['R00_OWNER_PASSWORD'])
        result = subprocess.run(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'], input=text, text=True, env=env, capture_output=True, timeout=20)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def payload(self, **changes):
        return dict(commandId=str(uuid.uuid4()), operation='grant', internalIdentityId='aaaaaaaa-0000-0000-0000-000000000001', issuer='https://issuer.test', subject='Opaque-subject', verificationReference=str(uuid.uuid4()), expectedRevision=0, **changes)

    def command(self, payload):
        value = json.dumps(payload).replace("'", "''")
        return json.loads(self.owner_sql("SELECT organization_access.command_platform_authority('" + value + "'::jsonb);").stdout)

    def prepare(self):
        self.assertEqual(self.migrate()[0], 0)
        self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.command_platform_authority(jsonb)') IS NOT NULL"), 't', 'owner command missing')
        self.sql("INSERT INTO organization_access.external_identity_bindings VALUES('aaaaaaaa-0000-0000-0000-000000000001','https://issuer.test','Opaque-subject');")

    def test_owner_grant_requires_exact_binding_and_atomic_audit(self):
        self.prepare()
        p = self.payload()
        self.assertEqual(self.command(dict(p, subject='opaque-subject'))['state'], 'forbidden')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority_audit'), '0')
        result = self.command(p)
        self.assertEqual(result['state'], 'applied')
        self.assertEqual(result['snapshot'], dict(internalIdentityId=p['internalIdentityId'], active=True, revision=1))
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority_audit'), '1')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'), '0')

    def test_exact_replay_conflict_and_replay_after_revoke_binding_loss(self):
        self.prepare()
        p = self.payload()
        first = self.command(p)
        self.assertEqual(self.command(p), dict(state='replayed', snapshot=first['snapshot']))
        self.assertEqual(self.command(dict(p, verificationReference=str(uuid.uuid4())))['state'], 'conflict')
        self.sql('DELETE FROM organization_access.external_identity_bindings;')
        revoke = dict(p, commandId=str(uuid.uuid4()), operation='revoke', expectedRevision=1)
        self.assertEqual(self.command(revoke)['snapshot'], dict(internalIdentityId=p['internalIdentityId'], active=False, revision=2))
        self.assertEqual(self.command(p), dict(state='replayed', snapshot=first['snapshot']))
        self.assertEqual(self.sql('SELECT "Active" FROM organization_access.platform_authority'), 'f')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority_audit'), '2')

    def test_revoke_does_not_require_binding_and_revision_conflicts(self):
        self.prepare()
        p = self.payload()
        self.command(p)
        self.sql('DELETE FROM organization_access.external_identity_bindings;')
        revoke = dict(p, commandId=str(uuid.uuid4()), operation='revoke', expectedRevision=1)
        self.assertEqual(self.command(revoke)['state'], 'applied')
        self.assertEqual(self.command(dict(revoke, commandId=str(uuid.uuid4())))['state'], 'conflict')

    def test_closed_invalid_inputs_are_controlled_without_writes(self):
        self.prepare()
        p = self.payload()
        bad = [None, [], dict(p, extra=True), dict(p, operation='GRANT'), dict(p, expectedRevision=True), dict(p, expectedRevision=-1), dict(p, expectedRevision=2147483647), dict(p, subject=''), dict(p, subject='x' * 256), dict(p, issuer='http://issuer.test'), dict(p, issuer='https://user@issuer.test'), dict(p, issuer='https://issuer.test?q=1'), dict(p, internalIdentityId='00000000-0000-0000-0000-000000000000'), dict(p, commandId=p['commandId'].upper()), dict(p, verificationReference='not-a-uuid')]
        for value in bad:
            with self.subTest(value=value):
                self.assertEqual(self.command(value)['state'], 'invalid')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority_audit'), '0')

    def test_app_cannot_mutate_or_read_audit_and_owner_audit_immutable(self):
        self.prepare()
        p = self.payload()
        self.command(p)
        app = os.environ['R00_APP_USER']
        for relation in ('platform_authority', 'platform_authority_audit'):
            self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','organization_access.{relation}','INSERT,UPDATE,DELETE,TRUNCATE')"), 'f')
        self.assertEqual(self.sql(f"SELECT has_function_privilege('{app}','organization_access.command_platform_authority(jsonb)','EXECUTE')"), 'f')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority', app=True), '0')
        for command in ('UPDATE organization_access.platform_authority_audit SET "Request"=\'{}\'', 'DELETE FROM organization_access.platform_authority_audit', 'TRUNCATE organization_access.platform_authority_audit'):
            self.assertNotEqual(self.owner_sql(command, ok=False).returncode, 0)

    def test_audit_failure_rolls_back_authority(self):
        self.prepare()
        p = self.payload()
        self.sql("CREATE FUNCTION organization_access.fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'fixture audit refusal'; END $$; CREATE TRIGGER fixture_fail BEFORE INSERT ON organization_access.platform_authority_audit FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_fail();")
        result = self.owner_sql("SELECT organization_access.command_platform_authority('" + json.dumps(p) + "')", ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority'), '0')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority_audit'), '0')

    def test_physical_concurrent_exact_commands_serialize_and_replay_once(self):
        self.prepare()
        p = self.payload()
        env = dict(os.environ, PGDATABASE=self.database, PGUSER=self.owner, PGPASSWORD=os.environ['R00_OWNER_PASSWORD'])
        holder = subprocess.Popen(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        workers = []
        try:
            holder.stdin.write('BEGIN; SELECT pg_advisory_xact_lock(777036); SELECT pg_backend_pid();\\echo LOCKED\n')
            holder.stdin.flush()
            lines = []
            while True:
                line = holder.stdout.readline().strip()
                if line == 'LOCKED':
                    break
                if line:
                    lines.append(line)
            pid = int(lines[-1])
            statement = "SELECT organization_access.command_platform_authority('" + json.dumps(p) + "');"
            for _ in range(2):
                proc = subprocess.Popen(['psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-c', statement], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
                workers.append(proc)
            import time
            deadline = time.monotonic() + 10
            while self.sql(f'SELECT count(*) FROM pg_stat_activity WHERE {pid}=ANY(pg_blocking_pids(pid))') != '2':
                self.assertLess(time.monotonic(), deadline, 'two physical command waiters required')
                time.sleep(0.05)
            holder.stdin.write('COMMIT;\\q\n')
            holder.stdin.flush()
            holder.communicate(timeout=10)
            states = []
            for proc in workers:
                output, error = proc.communicate(timeout=10)
                self.assertEqual(proc.returncode, 0, error)
                states.append(json.loads(output)['state'])
            self.assertEqual(sorted(states), ['applied', 'replayed'])
            self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority_audit'), '1')
        finally:
            for proc in [holder, *workers]:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)

    def test_nonprivileged_actor_rls_exact_tuple_and_no_binding_inheritance(self):
        self.prepare()
        p = self.payload()
        self.command(p)
        settings = f"SELECT set_config('app.identity_subject','{p['internalIdentityId']}',true),set_config('app.identity_issuer','{p['issuer']}',true),set_config('app.external_subject','{p['subject']}',true);"
        result = self.sql('BEGIN;' + settings + 'SELECT count(*) FROM organization_access.platform_authority;COMMIT;SELECT count(*) FROM organization_access.platform_authority;', app=True)
        self.assertEqual(result.splitlines()[-2:], ['1', '0'])
        for issuer, subject in [('https://other.test', p['subject']), (p['issuer'], 'opaque-subject')]:
            self.assertEqual(self.sql(f"BEGIN;SELECT set_config('app.identity_subject','{p['internalIdentityId']}',true),set_config('app.identity_issuer','{issuer}',true),set_config('app.external_subject','{subject}',true);SELECT count(*) FROM organization_access.platform_authority;COMMIT;", app=True).splitlines()[-1], '0')
        self.sql('DELETE FROM organization_access.external_identity_bindings;')
        self.assertEqual(self.sql('BEGIN;' + settings + 'SELECT count(*) FROM organization_access.platform_authority;COMMIT;', app=True).splitlines()[-1], '0')

    def test_maximum_revision_and_active_other_identity_conflict(self):
        self.prepare()
        p = self.payload()
        self.command(p)
        self.sql("INSERT INTO organization_access.external_identity_bindings VALUES('bbbbbbbb-0000-0000-0000-000000000001','https://issuer.test','Other');")
        self.assertEqual(self.command(dict(p, commandId=str(uuid.uuid4()), internalIdentityId='bbbbbbbb-0000-0000-0000-000000000001', subject='Other', expectedRevision=1))['state'], 'conflict')
        self.sql('UPDATE organization_access.platform_authority SET "Revision"=2147483647;')
        self.assertEqual(self.command(dict(p, commandId=str(uuid.uuid4()), expectedRevision=2147483646))['state'], 'conflict')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.platform_authority_audit'), '1')

class FixtureTests(unittest.TestCase):
    def test_fixture_extension_restores_readonly_mount_for_nonroot(self):
        import tempfile
        spec = importlib.util.spec_from_file_location('authority_runner', ROOT / 'scripts/run-mvp02a-tests.py')
        assert spec and spec.loader
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as directory:
            state = Path(directory)
            sql, identities = runner.fixtures(state, 'synthetic-fixture-only')
            self.assertTrue(sql)
            for name in ('realm.json', 'browser.json'):
                self.assertEqual((state / name).stat().st_mode & 0o777, 0o444)
            self.assertEqual(json.loads((state / 'browser.json').read_text())['authorityIdentity'], identities[4])
            source = state / 'authority.json'
            for operation in ('grant', 'revoke', 'grant'):
                runner.write_readonly_json(source, {'operation': operation})
                self.assertEqual(json.loads(source.read_text()), {'operation': operation})
                self.assertEqual(source.stat().st_mode & 0o777, 0o444)

class OwnerInputTests(unittest.TestCase):

    def test_json_reader_refuses_duplicates_and_oversize_before_psql(self):
        import tempfile
        path = ROOT / 'scripts/owner-platform-authority.py'
        spec = importlib.util.spec_from_file_location('owner_reader', path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        reader = getattr(module, 'read_command', lambda path: json.loads(path.read_text()))
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            source = Path(directory) / 'command.json'
            for text in ('{"operation":"grant","operation":"revoke"}', ' ' * 8193 + '{}'):
                source.write_text(text)
                with self.assertRaises(ValueError):
                    reader(source)

    def test_closed_canonical_limits_and_tls(self):
        path = ROOT / 'scripts/owner-platform-authority.py'
        self.assertTrue(path.exists(), 'finite owner CLI missing')
        spec = importlib.util.spec_from_file_location('owner_cli', path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        p = dict(commandId=str(uuid.uuid4()), operation='grant', internalIdentityId=str(uuid.uuid4()), issuer='https://issuer.test', subject='Opaque', verificationReference=str(uuid.uuid4()), expectedRevision=0)
        self.assertEqual(module.validate(p), p)
        for k, v in [('commandId', p['commandId'].upper()), ('expectedRevision', True), ('expectedRevision', 2147483647), ('issuer', 'https://user@issuer.test'), ('subject', 'x' * 256), ('operation', 'grant '), ('verificationReference', '')]:
            with self.subTest(k=k, v=v):
                with self.assertRaises(ValueError):
                    module.validate(dict(p, **{k: v}))
        with self.assertRaises(ValueError):
            module.validate(dict(p, extra=True))
        with mock_patch.dict(os.environ, {'PGSSLMODE': 'disable'}):
            with self.assertRaises(ValueError):
                module.apply(p)
if __name__ == '__main__':
    unittest.main()
