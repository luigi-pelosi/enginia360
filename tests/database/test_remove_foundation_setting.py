"""Contratti sorgente della rimozione mirata; nessun accesso al database reale."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CODES = ('settings.read', 'settings.create', 'settings.update', 'settings.delete')

class RemoveSettingSourceTests(unittest.TestCase):
    def test_baseline_does_not_create_setting_or_its_grants(self):
        source = (ROOT / 'database/foundation.sql').read_text()
        self.assertNotRegex(source, r'foundation\.setting\b')
        self.assertNotIn("'settings'::text", source)

    def test_resource_and_exclusive_validation_are_removed(self):
        source = (ROOT / 'backend/Api/Resources/Resources.cs').read_text()
        self.assertNotIn('"settings"', source)
        self.assertNotIn('integrations.', source)

    def test_migration_is_transactional_empty_only_and_restrict(self):
        source = (ROOT / 'database/migrations/20261123_remove_foundation_setting.sql').read_text()
        self.assertRegex(source, r'(?m)^BEGIN;')
        self.assertRegex(source, r'pg_advisory_xact_lock\(3607902026\)')
        self.assertRegex(source, r'LOCK TABLE foundation\.setting IN ACCESS EXCLUSIVE MODE')
        self.assertIn('SELECT count(*) INTO setting_count FROM foundation.setting', source)
        self.assertIn('IF setting_count <> 0 THEN', source)
        self.assertIn('DROP TABLE foundation.setting RESTRICT;', source)
        self.assertNotRegex(source, r'(?i)\bCASCADE\b|\bTRUNCATE\b')
        self.assertNotRegex(source, r'(?i)DELETE FROM foundation\.setting\b')
        self.assertEqual(set(re.findall(r"'((?:payment-)?settings\.[a-z]+)'", source)), set(CODES))
        self.assertIn('GET DIAGNOSTICS removed_grants = ROW_COUNT', source)
        self.assertIn('GET DIAGNOSTICS removed_permissions = ROW_COUNT', source)
        self.assertRegex(source, r'(?m)^COMMIT;')

if __name__ == '__main__':
    unittest.main()
