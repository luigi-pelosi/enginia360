from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
class ContractTests(unittest.TestCase):
    def test_cookies_require_https(self):
        source = (ROOT / 'Program.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertEqual(source.count('o.Cookie.SecurePolicy=CookieSecurePolicy.Always'), 2)
        self.assertNotIn('CookieSecurePolicy.SameAsRequest', source)

    def test_resource_whitelist(self):
        source = (ROOT / 'Api/Resources/Resources.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.') if (ROOT / 'Api/Resources/Resources.cs').exists() else ''
        for key in ['tenants', 'companies', 'sites', 'warehouse-types', 'warehouses', 'warehouse-locations', 'settings', 'users', 'groups', 'roles', 'permissions']:
            self.assertIn('"' + key + '"', source)

if __name__ == '__main__': unittest.main()
