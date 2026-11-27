"""Contratto del frammento canonico TaxManagement per nuove installazioni."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

class TaxManagementSourceTests(unittest.TestCase):
    def test_canonical_fragment_exists_and_is_transaction_free(self):
        path = ROOT / 'database/taxmanagement.sql'
        self.assertTrue(path.exists(), 'Frammento canonico TaxManagement mancante')
        sql = path.read_text()
        self.assertNotRegex(sql, r'(?im)^\s*(BEGIN;|COMMIT;|\\)')
        tables = re.findall(r'CREATE TABLE taxmanagement\.(\w+)', sql)
        self.assertEqual(set(tables), {'tax_types', 'tax_nature_codes', 'tax_codes', 'tax_code_versions', 'tax_audit_events', 'item_tax_classifications', 'partner_tax_classifications', 'item_tax_profiles', 'partner_tax_profiles', 'tax_regimes', 'company_tax_configurations', 'company_tax_registrations', 'company_tax_regime_profiles', 'tax_rules', 'tax_rule_versions', 'tax_rule_conditions'})
        self.assertEqual(len(tables), 16)

if __name__ == '__main__':
    unittest.main()
