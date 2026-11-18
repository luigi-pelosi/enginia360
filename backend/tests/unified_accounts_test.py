from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class UnifiedAccountsTests(unittest.TestCase):
    def test_all_crud_read_paths_use_public_projection(self):
        resources = (ROOT / 'Api/Resources/Resources.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        endpoints = (ROOT / 'Api/Resources/DataEndpoints.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertIn('public static string Projection(Resource r)', resources)
        self.assertIn('Resources.Projection(r)', endpoints)
        self.assertIn('{Projection(r)}', resources)
        self.assertNotIn('row_to_json(t)', endpoints)

    def test_canonical_password_reset_never_creates_or_enables(self):
        source = (ROOT / 'Modules/Identity/AuthEndpoints.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.').split('app.MapPut("/api/users/{id:guid}/password"')[1]
        self.assertIn('a.Id==id', source)
        self.assertNotIn('new User', source)
        self.assertNotIn('IsEnabled=', source)
        self.assertNotIn('Resources.Row', source)

    def test_rbac_uses_canonical_user_and_pending_cannot_load(self):
        source = (ROOT / 'Modules/Identity/Security.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertNotIn('foundation.app_user', source)
        self.assertNotIn('a.UserId', source)
        self.assertIn('a.PasswordHash == null', source)
        self.assertIn('("user",a.Id)', source)

    def test_no_stale_tracked_user_after_raw_update(self):
        source = (ROOT / 'Api/Resources/DataEndpoints.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertNotIn('a.UserId', source)
        self.assertIn('security_stamp=gen_random_uuid()', source)
        self.assertIn('ReloadAsync()', source)

    def test_null_hash_explicitly_fails_login(self):
        source = (ROOT / 'Modules/Identity/AuthEndpoints.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertIn('user!.PasswordHash == null', source)
        self.assertIn('global?.PasswordHash ?? DummyHash', source)
        self.assertIn('local?.PasswordHash ?? DummyHash', source)
        self.assertIn('global?.PasswordHash != null', source)
        self.assertIn('local?.PasswordHash != null', source)

    def test_baseline_has_one_identity_and_no_legacy_tables(self):
        source = (ROOT.parent / 'database/foundation.sql').read_text()
        self.assertIn('CREATE TABLE foundation."user" (', source)
        self.assertNotIn('CREATE TABLE foundation.account', source)
        self.assertNotIn('CREATE TABLE foundation.app_user', source)
        self.assertNotIn('REFERENCES foundation.account', source)
        self.assertNotIn('REFERENCES foundation.app_user', source)

    def test_baseline_preserves_canonical_user_relations(self):
        source = (ROOT.parent / 'database/foundation.sql').read_text()
        for table in ['user_role', 'user_group_member']:
            self.assertIn('ALTER TABLE ONLY foundation.' + table, source)
        self.assertIn('REFERENCES foundation."user"(tenant_id, id)', source)
        self.assertIn('BEGIN;', source)
        self.assertIn('COMMIT;', source)
        self.assertNotIn('UPDATE foundation.audit_event', source)

if __name__ == '__main__':
    unittest.main()
