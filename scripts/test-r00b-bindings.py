#!/usr/bin/env python3
"""Real, opt-in SQL acceptance of the external identity boundary, not provisioning."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('migration_tests', ROOT / 'scripts/test-r00-migrations.py')
assert spec is not None and spec.loader is not None
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)

@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS') == '1', 'isolated PostgreSQL opt-in required')
class BindingTests(unittest.TestCase):
    setUp = legacy.PostgreSqlTests.setUp
    tearDown = legacy.PostgreSqlTests.tearDown
    sql = legacy.PostgreSqlTests.sql
    start_migration = legacy.PostgreSqlTests.start_migration
    migrate = legacy.PostgreSqlTests.migrate

    def test_binding_is_empty_forced_rls_exact_and_read_only(self):
        self.assertEqual(self.migrate()[0], 0)
        self.assertEqual(self.sql("SELECT to_regclass('organization_access.external_identity_bindings') IS NOT NULL"), 't', 'opaque issuer/subject binding schema missing')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.external_identity_bindings'), '0')
        self.assertEqual(self.sql("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='organization_access.external_identity_bindings'::regclass"), 't')
        # Synthetic acceptance rows only after proving a migrated empty store.
        self.sql('''INSERT INTO organization_access.external_identity_bindings VALUES
            ('aaaaaaaa-0000-0000-0000-000000000001','https://issuer-a.test','Opaque-subject'),
            ('aaaaaaaa-0000-0000-0000-000000000002','https://issuer-a.test','opaque-subject'),
            ('bbbbbbbb-0000-0000-0000-000000000001','https://issuer-b.test','Opaque-subject');''')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.external_identity_bindings', app=True), '0')
        for issuer, subject, expected in [
            ('https://issuer-a.test', 'Opaque-subject', 'aaaaaaaa-0000-0000-0000-000000000001'),
            ('https://issuer-a.test', 'opaque-subject', 'aaaaaaaa-0000-0000-0000-000000000002'),
            ('https://issuer-b.test', 'Opaque-subject', 'bbbbbbbb-0000-0000-0000-000000000001')]:
            output = self.sql(f'''BEGIN;
                SELECT set_config('app.identity_issuer','{issuer}',true);
                SELECT set_config('app.external_subject','{subject}',true);
                SELECT "InternalIdentityId" FROM organization_access.external_identity_bindings;
                COMMIT;
                SELECT count(*) FROM organization_access.external_identity_bindings;''', app=True)
            self.assertEqual(output.splitlines(), [issuer, subject, expected, '0'])
        app = os.environ['R00_APP_USER']
        self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','organization_access.external_identity_bindings','INSERT,UPDATE,DELETE,TRUNCATE')"), 'f')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'), '0', 'binding implicitly provisioned membership')

if __name__ == '__main__':
    unittest.main()
