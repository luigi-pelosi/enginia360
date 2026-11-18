from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UserPersonalDetailsTests(unittest.TestCase):
    def test_baseline_personal_details_are_required_without_legacy_backfill(self):
        source = (ROOT.parent / 'database/foundation.sql').read_text()
        user = source.split('CREATE TABLE foundation."user" (', 1)[1].split('\n);', 1)[0]
        for field in ['first_name', 'last_name', 'email']:
            self.assertIn(field + ' text NOT NULL', user)
            self.assertIn('user_' + field + '_check', user)
        self.assertIn('date_of_birth date', user)
        self.assertIn('phone_number text', user)
        self.assertIn('char_length(phone_number) <= 50', user)
        self.assertNotIn('display_name', user)
        self.assertNotIn('user_profile_backfill', source)
        self.assertNotIn('UPDATE foundation."user"', source)

    def test_profile_contract_and_date_binding(self):
        resources = (ROOT / 'Api/Resources/Resources.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        fields = resources.split('new("users", "user", [', 1)[1].split(']),', 1)[0]
        for field in ['username', 'first_name', 'last_name', 'email', 'date_of_birth',
                      'phone_number', 'preferred_language', 'is_enabled']:
            self.assertIn('"' + field + '"', fields)
        self.assertNotIn('display_name', fields)
        self.assertIn('Options: ["it", "en"], DefaultValue: "it"', fields)
        endpoints = (ROOT / 'Api/Resources/DataEndpoints.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertIn('"date" => NpgsqlDbType.Date', endpoints)
        search = (ROOT / 'Modules/Geography/Geography.cs').read_text()
        self.assertIn("concat_ws(' ',first_name,last_name)", search)
        self.assertIn('SearchExpression(r)', endpoints)
        self.assertNotIn('display_name', endpoints)

    def test_bootstrap_and_session_use_personal_details(self):
        security = (ROOT / 'Modules/Identity/Security.cs').read_text().replace('ResourceCatalog.', 'Resources.').replace('GeographyCatalog.', 'Geography.')
        self.assertIn('BootstrapInput(string Username,string FirstName,string LastName,string Email,string Password)', security)
        self.assertIn('displayName = User.FullName', security)
        self.assertIn('preferredLanguage = User.PreferredLanguage', security)
        self.assertNotIn('input.DisplayName', security)


if __name__ == '__main__':
    unittest.main()
