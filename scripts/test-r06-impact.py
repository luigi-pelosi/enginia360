#!/usr/bin/env python3
"""Narrow offline R06 impact, with fail-closed workflow mutations."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
PATHS = ['scripts/r06_inventory.py', 'scripts/r06_synthetic.py', 'scripts/r06_reconcile.py',
         'scripts/test-r06-inventory.py', 'scripts/test-r06-reconcile.py', 'scripts/test-r06-impact.py',
         'docs/r06-migration-inventory.json', 'docs/r06-migration-inventory.md']


def validate_workflow(text):
    assert '  push:' not in text.split('concurrency:')[0]
    assert '  pull_request:' in text.split('concurrency:')[0]
    assert 'r06_offline: ${{ steps.selection.outputs.r06_offline }}' in text
    block = text.split('  affected-r06-offline:\n')[1].split('\n  affected-api:')[0]
    assert "if: needs.impact.outputs.r06_offline == 'true'" in block
    assert 'timeout-minutes: 3' in block
    for script in ('test-r06-impact.py', 'test-r06-inventory.py', 'test-r06-reconcile.py'):
        assert 'python3 -I scripts/'+script in block
    assert 'docker' not in block and 'workflow_dispatch' not in block


class ImpactTests(unittest.TestCase):
    def test_inventory_direct_producers_also_select_the_lightweight_guard(self):
        for path in ('database/runtime/manifest.json', 'database/runtime/migrations/0022_workshop_own_actual_time.sql',
                     'scripts/apply-runtime-migrations.py',
                     'src/Modules/Workshop/Enginia360.Workshop/CommercialEndpoints.cs'):
            with self.subTest(path=path):
                selected = impact.selection([path])
                self.assertTrue(selected.get('r06_offline'), 'inventory consumer must see producer drift')
                self.assertFalse(selected['full_architecture'])

    def assert_offline(self, paths):
        selected = impact.selection(paths)
        self.assertTrue(selected.get('r06_offline'), selected)
        self.assertEqual(selected['api_filter'], '')
        for key in ('browser', 'ui01b', 'r03a', 'r03a2', 'r04a', 'r03b', 'r03c',
                    'migrations', 'ui_build', 'ui_tests', 'full_architecture'):
            self.assertFalse(selected[key], key)

    def test_explicit_offline_paths_only_select_lightweight_checks(self):
        for path in PATHS:
            with self.subTest(path=path):
                self.assert_offline([path])
        self.assert_offline(PATHS + ['scripts/select-ci-impact.py', '.github/workflows/ci.yml', 'scripts/test-r03a-impact.py'])

    def test_unknown_executable_is_not_a_wildcard(self):
        for path in ('scripts/r06_unreviewed.py', 'scripts/test-r06-new.py', 'docs/r06-unreviewed.py'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                impact.selection(PATHS + [path])

    def test_mixed_runtime_changes_keep_existing_security_selection(self):
        selected = impact.selection(PATHS + ['src/Enginia360.Api/Program.cs'])
        self.assertTrue(selected.get('r06_offline'))
        self.assertTrue(selected['browser'])
        self.assertTrue(selected['migrations'])
        self.assertFalse(selected['full_architecture'])

    def test_actual_offline_workflow_and_removed_checks_fail_closed(self):
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        validate_workflow(text)
        for token in ('r06_offline: ${{ steps.selection.outputs.r06_offline }}',
                      'python3 -I scripts/test-r06-inventory.py',
                      'python3 -I scripts/test-r06-reconcile.py',
                      "needs.impact.outputs.r06_offline == 'true'"):
            with self.subTest(token=token), self.assertRaises(AssertionError):
                validate_workflow(text.replace(token, 'removed'))


if __name__ == '__main__':
    unittest.main()
