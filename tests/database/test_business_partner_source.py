"""Baseline BP dichiarativa unica e composizione psql per nuove installazioni."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


class BusinessPartnerSourceTests(unittest.TestCase):
    def test_stdin_loader_expands_only_the_canonical_include(self):
        import importlib.util
        import tempfile
        spec = importlib.util.spec_from_file_location('sql_source', ROOT / 'database/sql_source.py')
        self.assertTrue(Path(spec.origin).is_file(), 'Manca il loader per le fixture stdin')
        loader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loader)
        self.assertTrue(callable(getattr(loader, 'read_sql', None)), 'Manca API read_sql(path)')
        source = loader.load_foundation_sql()
        self.assertEqual(loader.read_sql(ROOT / 'database/foundation.sql'), source)
        main = (ROOT / 'database/foundation.sql').read_text()
        expected = main
        fragments = ('masterdata_business_partner.sql', 'masterdata_payments.sql', 'masterdata_catalog.sql', 'seeds/countries.sql', 'taxmanagement.sql')
        for filename in fragments:
            self.assertEqual(main.splitlines().count('\\ir ' + filename), 1)
            expected = expected.replace('\\ir ' + filename, (ROOT / 'database' / filename).read_text().rstrip('\n'))
        self.assertEqual(source, expected)
        self.assertNotIn('\\ir ', source)
        with tempfile.TemporaryDirectory(dir=__import__('os').environ.get('TMPDIR')) as temporary:
            path = Path(temporary) / 'foundation.sql'
            for command in ('\\ir other.sql', '\\i masterdata_business_partner.sql', '\\ir ../masterdata_business_partner.sql'):
                path.write_text(command + '\n')
                with self.assertRaises(ValueError):
                    loader.load_foundation_sql(path)
            path.write_text('SELECT 1;\n')
            self.assertEqual(loader.read_sql(path), 'SELECT 1;\n')
            with self.assertRaises(ValueError):
                loader.load_foundation_sql(path)
            path.write_text('\\ir masterdata_business_partner.sql\n' * 2)
            with self.assertRaises(ValueError):
                loader.load_foundation_sql(path)

    def test_archive_hash_manifest_preserves_all_historical_migrations(self):
        import hashlib
        archive = ROOT / 'database/migrations/archive/business_partner'
        lines = (archive / 'SHA256SUMS').read_text().splitlines()
        self.assertEqual(len(lines), 3)
        for line in lines:
            digest, filename = line.split('  ')
            self.assertEqual(hashlib.sha256((archive / filename).read_bytes()).hexdigest(), digest)
            self.assertFalse((ROOT / 'database/migrations' / filename).exists())

    def test_domain_is_one_declarative_fragment_before_commit(self):
        domain = ROOT / 'database/masterdata_business_partner.sql'
        self.assertTrue(domain.is_file(), 'Manca il frammento canonico Business Partner')
        sql = domain.read_text()
        self.assertNotRegex(sql, r'(?im)^\s*ALTER\b')
        self.assertNotRegex(sql, r'(?im)^\s*(?:BEGIN|COMMIT);\s*$')
        tables = re.findall(r'^CREATE TABLE (foundation|masterdata)\.([^\s(]+)', sql, re.M)
        self.assertEqual(set(tables), {('foundation','role_company'),
            ('masterdata','business_partner'), ('masterdata','business_partner_tax_identifier'),
            ('masterdata','business_partner_address'), ('masterdata','business_partner_address_usage'),
            ('masterdata','business_partner_contact_channel'), ('masterdata','company_business_partner'),
            ('masterdata','company_business_partner_role')})
        self.assertEqual(sum(schema == 'masterdata' for schema, _ in tables), 7)
        numbering = (ROOT / 'database/foundation.sql').read_text()
        self.assertTrue({'numbering_series','numbering_counter'} <= set(re.findall(r'^CREATE TABLE foundation\.([^\s(]+)', numbering, re.M)))
        main = (ROOT / 'database/foundation.sql').read_text()
        self.assertEqual(main.count('\\ir masterdata_business_partner.sql'), 1)
        self.assertLess(main.index('GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE foundation.warehouse_type'), main.index('\\ir masterdata_business_partner.sql'))
        self.assertEqual([line for line in main.splitlines() if line.startswith('\\ir ')], ['\\ir '+name for name in ('masterdata_business_partner.sql', 'masterdata_payments.sql', 'masterdata_catalog.sql', 'seeds/countries.sql', 'taxmanagement.sql')])
        self.assertNotRegex(main, r'CREATE TABLE (?:masterdata\.business_partner|foundation\.role_company)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
