from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UserRenameTests(unittest.TestCase):
    def test_baseline_creates_quoted_user_directly(self):
        source = (ROOT.parent / 'database/foundation.sql').read_text()
        self.assertIn('CREATE TABLE foundation."user" (', source)
        self.assertIn('user_global_admin_check', source)
        self.assertIn('CREATE UNIQUE INDEX ux_user_username', source)
        self.assertNotIn('ALTER TABLE foundation.account', source)
        self.assertNotIn('DROP TABLE', source)
        self.assertNotRegex(source, r'CREATE TABLE foundation\.(?:account|app_user)\b')

    def test_generic_tables_use_central_qualified_identifier_quoting(self):
        resources = (ROOT / 'Api/Resources/Resources.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        endpoints = (ROOT / 'Api/Resources/DataEndpoints.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertIn('{SqlNames.Table(r.Table)}', resources)
        self.assertIn('new("users", "user",', resources)
        self.assertEqual(endpoints.count('{SqlNames.Table(r.Table)}'), 5)
        self.assertEqual(endpoints.count('{SqlNames.Table(link.Table)}'), 3)
        for source in (resources, endpoints):
            self.assertNotRegex(source, r'foundation\.\{\w+\.Table\}')
        self.assertIn('public static string Identifier(string name)', ((ROOT / 'Modules/Identity/User.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.') + (ROOT / 'Infrastructure/Persistence/AppDb.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.') + (ROOT / 'Infrastructure/Persistence/SqlNames.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')))

    def test_canonical_user_entity_and_identity(self):
        database = ((ROOT / 'Modules/Identity/User.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.') + (ROOT / 'Infrastructure/Persistence/AppDb.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.') + (ROOT / 'Infrastructure/Persistence/SqlNames.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.'))
        self.assertIn('public sealed class User', database)
        self.assertIn('DbSet<User> Users => Set<User>()', database)
        self.assertIn('ToTable("user", "foundation")', database)
        security = (ROOT / 'Modules/Identity/Security.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertIn('IdentityState(User User,', security)
        self.assertIn('PasswordHasher<User>', security)
        for path in (p for p in ROOT.rglob('*.cs') if not {'obj', 'bin', 'publish'}.intersection(p.relative_to(ROOT).parts)):
            self.assertNotRegex(path.read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.'), r'\b(?:Account|Accounts|account|accounts)\b', path.name)
        self.assertIn('db.Users.SingleOrDefaultAsync', (ROOT / 'Modules/Identity/AuthEndpoints.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.'))
        self.assertIn('Entries<User>()', (ROOT / 'Api/Resources/DataEndpoints.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.'))


if __name__ == '__main__':
    unittest.main()
