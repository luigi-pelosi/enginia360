"""Contratto ristretto per la sola baseline di nuove installazioni."""
from pathlib import Path
import re
import unittest
import dbbaseline
from test_foundation import TABLES

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
from database.sql_source import load_foundation_sql


class PortableBaselineTests(unittest.TestCase):
    def test_inventory_matches_sql_including_business_partner_tables(self):
        source = load_foundation_sql()
        tables = re.findall(r'^CREATE TABLE (foundation|masterdata)\.([^\s(]+)', source, re.MULTILINE)
        from test_foundation import table_schema
        self.assertEqual({(table_schema(name), name) for name in TABLES}, {(schema, name.strip('"')) for schema, name in tables})
        self.assertEqual(len(TABLES), len(tables))

    def test_masterdata_owns_only_business_partner_tables(self):
        source = load_foundation_sql()
        self.assertIn('CREATE SCHEMA masterdata', source)
        tables = re.findall(r'^CREATE TABLE masterdata\.([^\s(]+)', source, re.MULTILINE)
        self.assertEqual(set(tables), {'business_partner', 'business_partner_tax_identifier',
            'business_partner_address', 'business_partner_address_usage', 'business_partner_contact_channel',
            'company_business_partner', 'company_business_partner_role'})
        for name in ('numbering_series', 'numbering_counter'):
            self.assertIn('CREATE TABLE foundation.' + name, source)
        self.assertNotRegex(source, r'CREATE TABLE foundation\.business_partner')

    def test_baseline_has_no_personal_role(self):
        source = load_foundation_sql()
        self.assertNotIn('luigi_pelosi', source)
        self.assertIn("current_user <> 'postgres'", source)
        self.assertIn("rolname = 'enginia360_app'", source)

    def test_only_exact_personal_grants_are_removed(self):
        grants = ('GRANT USAGE ON SCHEMA foundation TO luigi_pelosi;\n'
                  'GRANT SELECT ON TABLE foundation.audit_event TO luigi_pelosi;\n')
        kept = ('-- ACL luigi_pelosi must not be hidden\n'
                'GRANT SELECT ON TABLE foundation.tenant TO enginia360_app;\n'
                'GRANT SELECT ON TABLE foundation.tenant TO PUBLIC;\n'
                'GRANT SELECT ON TABLE foundation.tenant TO luigi_pelosi_extra;\n'
                'GRANT SELECT ON TABLE foundation.tenant TO luigi_pelosi, other;\n'
                'GRANT SELECT ON TABLE other.tenant TO luigi_pelosi;\n'
                'ALTER TABLE foundation.tenant OWNER TO luigi_pelosi;\n'
                'REVOKE SELECT ON TABLE foundation.tenant FROM luigi_pelosi;\n'
                "COMMENT ON TABLE foundation.tenant IS 'TO luigi_pelosi;';\n")
        self.assertEqual(dbbaseline.normalize_product_dump(grants + kept), kept)
        self.assertEqual(dbbaseline.normalize_dump(grants + kept), grants + kept)
        for mutation in (kept.replace('TO enginia360_app', 'TO other'),
                         kept.replace('OWNER TO luigi_pelosi', 'OWNER TO postgres'),
                         kept.replace('SELECT', 'ALL'),
                         kept.replace('-- ACL luigi_pelosi must not be hidden\n', '')):
            self.assertNotEqual(dbbaseline.normalize_product_dump(kept),
                                dbbaseline.normalize_product_dump(mutation))


if __name__ == '__main__':
    unittest.main(verbosity=2)
