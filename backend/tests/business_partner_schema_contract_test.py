"""Contratto degli schemi: anagrafiche in masterdata, numerazione in foundation."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from database.sql_source import load_foundation_sql
BP = ('business_partner', 'business_partner_tax_identifier', 'business_partner_address',
      'business_partner_address_usage', 'business_partner_contact_channel')


class BusinessPartnerSchemaContractTests(unittest.TestCase):
    def test_fresh_ownership(self):
        sql = load_foundation_sql()
        tables = set(re.findall(r'CREATE TABLE (\w+)\.(\w+)', sql))
        for table in BP:
            self.assertIn(('masterdata', table), tables)
            self.assertNotIn(('foundation', table), tables)
        for table in ('numbering_series', 'numbering_counter'):
            self.assertIn(('foundation', table), tables)
        self.assertIn('CREATE FUNCTION masterdata.guard_business_partner()', sql)
        self.assertIn('EXECUTE FUNCTION foundation.set_updated_at()', sql)
        self.assertIn('REVOKE ALL ON SCHEMA masterdata FROM PUBLIC', sql)
        self.assertIn('GRANT USAGE ON SCHEMA masterdata TO enginia360_app', sql)

    def test_incremental_uses_identity_preserving_moves(self):
        import hashlib
        released = ROOT / 'database/migrations/archive/business_partner/20261118_business_partners.sql'
        self.assertEqual(hashlib.sha256(released.read_bytes()).hexdigest(),
                         '9108323100e8cf950574894ddb12ca9b99e76962ac75475d678fafaad0110a7e')
        migration = ROOT / 'database/migrations/archive/business_partner/20261119_business_partner_masterdata.sql'
        self.assertTrue(migration.exists(), 'Missing masterdata ownership migration')
        sql = migration.read_text()
        for table in BP:
            self.assertIn(f'ALTER TABLE foundation.{table} SET SCHEMA masterdata;', sql)
        self.assertIn('ALTER FUNCTION foundation.guard_business_partner() SET SCHEMA masterdata;', sql)
        self.assertNotRegex(sql, r'(?i)\b(?:DROP|COPY|CREATE VIEW)\b')
        self.assertIn('pg_advisory_xact_lock(3607902026)', sql)
        self.assertIn("lock_timeout = '10s'", sql)
        self.assertIn("statement_timeout = '60s'", sql)

    def test_no_stale_backend_domain_qualification(self):
        for folder in ('Modules', 'Verification'):
            for path in (ROOT / 'backend' / folder).rglob('*.cs'):
                self.assertNotRegex(path.read_text(), r'foundation\.business_partner\b|foundation\.business_partner_', str(path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
