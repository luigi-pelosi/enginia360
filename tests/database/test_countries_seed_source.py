"""Offline contract for the pinned, Italian, insert-only world country seed."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DATA = ROOT / 'database/seeds/countries'
SQL = ROOT / 'database/seeds/countries.sql'


class CountriesSeedSourceTests(unittest.TestCase):
    def test_dataset_exactly_matches_existing_iso_whitelist_and_pinned_italian_names(self):
        self.assertTrue((DATA / 'countries.json').is_file(), 'Missing world country dataset')
        rows = json.loads((DATA / 'countries.json').read_text(encoding='utf-8'))
        codes = re.findall(r'"([A-Z]{2})"', (ROOT / 'backend/Modules/Geography/CountryCodes.cs').read_text())
        self.assertEqual(len(rows), 249)
        self.assertEqual([r['iso_code'] for r in rows], codes)
        self.assertEqual(len(set(codes)), 249)
        self.assertTrue(all(set(r) == {'name', 'iso_code'} and r['name'].strip() == r['name'] and r['name'] for r in rows))
        names = json.loads((DATA / 'cldr-territories-it.json').read_text(encoding='utf-8'))['main']['it']['localeDisplayNames']['territories']
        self.assertEqual(rows, [{'name': names[code], 'iso_code': code} for code in codes])
        self.assertEqual(next(r['name'] for r in rows if r['iso_code'] == 'IT'), 'Italia')
        self.assertTrue(set(codes).isdisjoint({'XK', 'AC', 'DG', 'EU', 'ZZ'}))
        # Optional host reference is a cross-check, never a runtime dependency.
        reference = Path('/usr/share/iso-codes/json/iso_3166-1.json')
        if reference.is_file():
            self.assertEqual(set(codes), {r['alpha_2'] for r in json.loads(reference.read_text())['3166-1']})
        provenance = json.loads((DATA / 'sources.json').read_text())
        self.assertEqual(provenance['cldr_commit'], '7d2b9cb11cec08f4d333ad73209deb3df0711c3b')
        self.assertIn(provenance['cldr_commit'], provenance['cldr_url'])
        self.assertEqual(provenance['license'], 'Unicode-3.0')
        self.assertIn('UNICODE LICENSE V3', (DATA / 'UNICODE-LICENSE.txt').read_text())
        manifest = json.loads((DATA / 'SHA256SUMS.json').read_text())
        self.assertEqual(set(manifest), {'countries.json', 'cldr-territories-it.json', 'UNICODE-LICENSE.txt',
                                        'sources.json', 'generate_sql.py', '../countries.sql'})
        for filename, digest in manifest.items():
            self.assertEqual(hashlib.sha256((DATA / filename).read_bytes()).hexdigest(), digest, filename)
        self.assertEqual(json.loads((ROOT / 'database/seeds/italy/countries.json').read_text()), [{'name': 'Italia', 'iso_code': 'IT'}])

    def test_generated_sql_is_reproducible_insert_only_and_escapes_literals(self):
        import importlib.util
        self.assertTrue(SQL.is_file(), 'Missing canonical insert-only SQL seed')
        spec = importlib.util.spec_from_file_location('generate_countries', DATA / 'generate_sql.py')
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        rows = json.loads((DATA / 'countries.json').read_text(encoding='utf-8'))
        source = SQL.read_text(encoding='utf-8')
        self.assertEqual(source, generator.render_sql(rows))
        result = subprocess.run([sys.executable, str(DATA / 'generate_sql.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("('L''isola', 'IT')", generator.render_sql([{'name': "L'isola", 'iso_code': 'IT'}]))
        self.assertRegex(source, r'INSERT INTO foundation\.country\s*\(name, iso_code\) VALUES\n')
        self.assertEqual(len(re.findall(r"^    \('(?:[^']|'')*', '[A-Z]{2}'\)[,]?$", source, re.M)), 249)
        self.assertTrue(source.endswith('ON CONFLICT (iso_code) DO NOTHING;\n'))
        self.assertEqual(source.count(';'), 1)
        self.assertNotRegex(source, r'(?im)^\s*(?:UPDATE|DELETE|GRANT|ALTER|BEGIN|COMMIT|SELECT|CREATE)\b')
        self.assertNotIn('DO UPDATE', source)
        self.assertNotIn('\\\\', source)
        for rows in ([{'name': 'Test', 'iso_code': 'ZZ'}], [{'name': '', 'iso_code': 'IT'}],
                     [{'name': 'Italia', 'iso_code': 'IT'}] * 2):
            with self.assertRaises(ValueError):
                generator.render_sql(rows)

    def test_fresh_baseline_expands_seed_before_company_fragment_inside_transaction(self):
        from database.sql_source import load_foundation_sql, read_sql
        baseline = ROOT / 'database/foundation.sql'
        source = baseline.read_text()
        directives = [line for line in source.splitlines() if line.lstrip().startswith('\\')]
        expected = [r'\ir ' + filename for filename in ('masterdata_business_partner.sql', 'masterdata_payments.sql', 'masterdata_catalog.sql', 'seeds/countries.sql', 'taxmanagement.sql')]
        self.assertEqual(directives, expected)
        self.assertLess(source.index('BEGIN;'), source.index('CREATE TABLE foundation.country'))
        self.assertLess(source.index('CREATE TABLE foundation.country'), source.index(r'\ir seeds/countries.sql'))
        self.assertLess(source.index(expected[-1]), source.rindex('COMMIT;'))
        expanded = load_foundation_sql()
        self.assertEqual(expanded, read_sql(baseline))
        self.assertIn(SQL.read_text().rstrip('\n'), expanded)
        self.assertNotRegex(expanded, r'(?m)^\\')

    def test_loader_rejects_noncanonical_order_duplicates_and_nested_psql(self):
        from database.sql_source import load_foundation_sql, read_sql
        import os
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as temporary:
            database = Path(temporary)
            original = (ROOT / 'database/foundation.sql').read_text()
            self.assertIn(r'\ir seeds/countries.sql', original)
            for directive in [line for line in original.splitlines() if line.startswith('\\ir ')]:
                relative = directive[4:]
                target = database / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / 'database' / relative, target)
            path = database / 'foundation.sql'
            seed = r'\ir seeds/countries.sql'
            for mutation in (original.replace(seed, ''), original.replace(seed, seed + '\n' + seed),
                             original.replace(seed, r'\i seeds/countries.sql'),
                             original.replace(seed, r'\ir seeds/../seeds/countries.sql'),
                             original.replace(seed, r' \ir seeds/countries.sql'),
                             original.replace(seed, r'\ir seeds/countries.sql -- extra'),
                             original.replace(seed, '') + '\n' + seed + '\n\\echo unsafe',
                             original.replace(seed, '').replace(r'\ir masterdata_business_partner.sql', seed + '\n' + r'\ir masterdata_business_partner.sql')):
                path.write_text(mutation)
                for loader in (load_foundation_sql, read_sql):
                    with self.assertRaises(ValueError):
                        loader(path)
            path.write_text(original)
            (database / 'seeds/countries.sql').write_text('SELECT 1;\n\\echo unsafe\n')
            with self.assertRaisesRegex(ValueError, 'frammento'):
                load_foundation_sql(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
