"""Final company fiscal definitions, no historical upgrade source dependency."""
from pathlib import Path
import hashlib
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CompanyTaxSourceTests(unittest.TestCase):

    def test_exact_four_tables_and_no_automatic_company_data(self):
        source = (ROOT/'database/taxmanagement.sql').read_text()
        source = 'CREATE TABLE taxmanagement.tax_regimes' + source.split('CREATE TABLE taxmanagement.tax_regimes',1)[1].split('CREATE TABLE taxmanagement.tax_rules',1)[0]
        self.assertEqual(re.findall(r'^CREATE TABLE taxmanagement\.([a-z_]+)', source, re.M),
            ['tax_regimes','company_tax_configurations','company_tax_registrations','company_tax_regime_profiles'])
        self.assertEqual(re.findall(r'^INSERT INTO taxmanagement\.([a-z_]+)', source, re.M), ['tax_regimes'])
        self.assertNotIn('SECURITY DEFINER', source)
        self.assertNotIn('ALTER TABLE foundation.company ', source)
        self.assertNotIn('ALTER TABLE foundation.site ', source)
        self.assertNotIn('tax_audit_events', source)
        self.assertEqual(source.count('DEFERRABLE INITIALLY DEFERRED'), 5)
        self.assertIn('tax_code text', source)
        self.assertIn('CREATE FUNCTION taxmanagement.require_company_tax_initial_chain()', source)
        self.assertIn('CREATE FUNCTION taxmanagement.require_company_tax_registration_initial_profile()', source)
        self.assertNotRegex(source, r'(?im)^ALTER TABLE.*ADD COLUMN')
        self.assertIn("DATE '2026-11-26',true,true", source)
        self.assertNotIn('2021-01-01', source)
        self.assertIn("WHERE c.iso_code IN ('IT','DE','FR') AND t.code='VAT'", source)


if __name__ == '__main__':
    unittest.main()
