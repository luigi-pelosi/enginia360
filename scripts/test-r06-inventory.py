#!/usr/bin/env python3
"""Manifest inventory acceptance; no DB or legacy repository access."""
import importlib.util
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_tool():
    path = ROOT/'scripts/r06_inventory.py'
    assert path.exists(), 'offline inventory tool is missing'
    spec = importlib.util.spec_from_file_location('inventory', path)
    assert spec and spec.loader
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


class InventoryTests(unittest.TestCase):
    def test_malformed_command_evidence_fails_closed_without_traceback(self):
        records = json.loads((ROOT/'docs/r06-migration-inventory.json').read_text())
        command_row = next(i for i, r in enumerate(records) if r['available_command'])
        for field, value in (('source', 1), ('registration', []), ('purpose', None)):
            with self.subTest(field=field):
                mutated = copy.deepcopy(records)
                mutated[command_row]['available_command'][field] = value
                with self.assertRaises(ValueError):
                    load_tool().verify(ROOT, mutated)

    def test_manifest_selected_only_new_table_checksum_and_coverage_mutations(self):
        tool = load_tool()
        records = json.loads((ROOT/'docs/r06-migration-inventory.json').read_text())
        for mutated in (records[:-1], records+[records[0]]):
            with self.assertRaisesRegex(ValueError, 'coverage'):
                tool.verify(ROOT, mutated)
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)/'runtime'
            shutil.copytree(ROOT/'database/runtime', runtime)
            manifest = runtime/'manifest.json'
            baseline = tool.definitions(manifest)
            (runtime/'migrations/9999_excluded.sql').write_text('CREATE TABLE outside.excluded ("Id" uuid PRIMARY KEY);')
            self.assertEqual(tool.definitions(manifest), baseline, 'excluded files must not become published tables')
            entries = json.loads(manifest.read_text())
            number = len(entries)+1
            identifier = f'{number:04d}_synthetic_guard'
            sql = ('-- CREATE TABLE fake.comment ("Id" uuid PRIMARY KEY);\n'
                   'CREATE TABLE synthetic.unclassified ("Id" uuid PRIMARY KEY);\n'
                   "SELECT 'CREATE TABLE fake.literal (x int)';\n")
            path = f'migrations/{identifier}.sql'
            (runtime/path).write_text(sql)
            entries.append({'id': identifier, 'path': path, 'sha256': hashlib.sha256(sql.encode()).hexdigest()})
            manifest.write_text(json.dumps(entries))
            found = tool.definitions(manifest)
            self.assertEqual(set(found)-set(baseline), {'synthetic.unclassified'})
            with self.assertRaisesRegex(ValueError, 'coverage'):
                tool.verify(ROOT, records, manifest)
            (runtime/path).write_text(sql+'-- checksum corruption')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                tool.definitions(manifest)

    def test_cli_reports_computed_counts_and_refuses_mutation(self):
        command = [sys.executable, '-I', str(ROOT/'scripts/r06_inventory.py')]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['tables'], len(load_tool().definitions(ROOT/'database/runtime/manifest.json')))
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp)/'bad.json'
            bad.write_text('[]')
            result = subprocess.run(command+['--inventory', str(bad)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('refused', result.stderr)

    def test_classification_cannot_authorize_import_or_relabel_security(self):
        records = json.loads((ROOT/'docs/r06-migration-inventory.json').read_text())
        security = next(i for i, r in enumerate(records) if r['table'] == 'organization_access.external_identity_bindings')
        cases = [(0, 'migration_eligibility', 'IMPORT_VIA_COMMAND'),
                 (security, 'handling_constraint', 'IMPORT_VIA_COMMAND'),
                 (security, 'category', 'shared_master'),
                 (0, 'owner', 'unrelated'), (0, 'reconcile_keys', []),
                 (0, 'reconcile_keys', ['NotAColumn']),
                 (0, 'available_command', {'source': 'missing', 'registration': 'fabricated'})]
        for index, key, value in cases:
            with self.subTest(key=key, value=value):
                mutated = copy.deepcopy(records)
                mutated[index][key] = value
                with self.assertRaises(ValueError):
                    load_tool().verify(ROOT, mutated)

    def test_invalid_category_is_refused(self):
        records = json.loads((ROOT/'docs/r06-migration-inventory.json').read_text())
        records[0]['category'] = 'IMPORT_EVERYTHING'
        with self.assertRaisesRegex(ValueError, 'classification'):
            load_tool().verify(ROOT, records)

    def test_published_manifest_create_definitions_are_exactly_inventoried(self):
        tool = load_tool()
        records = json.loads((ROOT/'docs/r06-migration-inventory.json').read_text())
        summary = tool.verify(ROOT, records)
        definitions = tool.definitions(ROOT/'database/runtime/manifest.json')
        self.assertGreater(len(definitions), 0)
        self.assertEqual(summary['tables'], len(definitions))
        self.assertEqual({r['table'] for r in records}, set(definitions))
        self.assertTrue(all(r['migration_eligibility'] == 'UNDECIDED' for r in records))
        for row in records:
            self.assertEqual(row['definition'], definitions[row['table']])


if __name__ == '__main__':
    unittest.main()
