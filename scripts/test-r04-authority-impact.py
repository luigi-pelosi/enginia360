#!/usr/bin/env python3
"""Finite documentation/offline authority delivery; never a runtime exemption."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
PATHS = ['AGENTS.md', 'docs/foundation/01-glossary-and-domain-boundaries.md',
         'docs/productization-plan.md', 'docs/productization-backlog.json', 'docs/r06-recovery-runbook.md',
         'scripts/test-r04-authority.py', 'scripts/test-r04-authority-impact.py',
         'scripts/test-c00-consistency.py']
WIRING = ['scripts/select-ci-impact.py', '.github/workflows/ci.yml']
# D87 / R06.a descoping: documentation plus the register-bound history guards, no executable or runtime path.
D87_PATHS = PATHS + ['docs/r06-migration-inventory.md', 'scripts/test-r05a2-evidence.py', 'scripts/test-r05a3-evidence.py']
D87_JOBS = {'r06_offline', 'r05a2_offline', 'r05a3_offline'}


def validate_workflow(text):
    triggers = text.split('concurrency:')[0]
    assert '  pull_request:' in triggers and '  push:' not in triggers
    block = text.split('  impact:\n')[1].split('  affected-r06-offline:')[0]
    assert 'python3 scripts/test-r04-authority-impact.py' in block
    block = text.split('  affected-r06-offline:\n')[1].split('\n  affected-api:')[0]
    assert "if: needs.impact.outputs.r06_offline == 'true'" in block
    assert 'timeout-minutes: 3' in block
    assert 'docker' not in block and 'workflow_dispatch' not in block
    for command in ('python3 -I scripts/test-r04-authority-impact.py',
                    'python3 -I scripts/test-r04-authority.py',
                    'python3 -I scripts/test-r04-authority.py --check'):
        assert command in block, 'offline authority acceptance missing: '+command


class ImpactTests(unittest.TestCase):
    def test_finite_authority_paths_only_select_offline(self):
        for paths in [[p] for p in PATHS] + [PATHS+WIRING]:
            with self.subTest(paths=paths):
                selected = impact.selection(paths)
                self.assertTrue(selected['r06_offline'])
                self.assertEqual(selected['api_filter'], '')
                for key, value in selected.items():
                    if key not in ('changed_paths', 'api_filter', 'r06_offline'):
                        self.assertFalse(value, key)

    def test_d87_descoping_delivery_selects_only_offline_jobs(self):
        for paths in (D87_PATHS, D87_PATHS + WIRING):
            with self.subTest(paths=paths):
                selected = impact.selection(paths)
                self.assertEqual({k for k, v in selected.items() if v is True}, D87_JOBS)
                self.assertEqual(selected['api_filter'], '')
                self.assertFalse(selected['full_architecture'])
        # The pre-existing authority guards stay in the offline block that these paths select.
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        for job, tests in (('affected-r05a2-offline', 'test-r05a2-evidence.py'), ('affected-r05a3-offline', 'test-r05a3-evidence.py')):
            block = text.split('  '+job+':\n')[1].split('\n  affected-')[0]
            self.assertIn(tests, block)
            self.assertNotIn('docker', block)

    def test_d89_priority_increment_reuses_finite_offline_mapping(self):
        paths = [path for path in D87_PATHS if path != 'docs/r06-migration-inventory.md']
        selected = impact.selection(paths)
        self.assertEqual({k for k, value in selected.items() if value is True}, D87_JOBS)
        self.assertEqual(selected['api_filter'], '')
        self.assertFalse(selected['full_architecture'])
        validate_workflow((ROOT/'.github/workflows/ci.yml').read_text())

    def test_d90_cap_decision_reuses_finite_offline_mapping(self):
        # Existing mapping regression, not a manufactured RED.
        paths = PATHS + ['docs/r04b1-supplier-role.md',
                        'scripts/test-r05a2-evidence.py', 'scripts/test-r05a3-evidence.py']
        selected = impact.selection(paths)
        self.assertEqual({k for k, value in selected.items() if value is True}, D87_JOBS)
        self.assertEqual(selected['api_filter'], '')
        self.assertFalse(selected['full_architecture'])
        validate_workflow((ROOT/'.github/workflows/ci.yml').read_text())

    def test_d91_supplier_pricing_reuses_finite_offline_mapping(self):
        # Already-mapped selection regression, not new-behavior RED.
        paths = PATHS + ['docs/r04b2a-purchase-intent.md',
                        'scripts/test-r05a2-evidence.py', 'scripts/test-r05a3-evidence.py']
        selected = impact.selection(paths)
        self.assertEqual({k for k, value in selected.items() if value is True}, D87_JOBS)
        self.assertEqual(selected['api_filter'], '')
        self.assertFalse(selected['full_architecture'])
        validate_workflow((ROOT/'.github/workflows/ci.yml').read_text())

    def test_d92_quote_visibility_selects_only_finite_offline_jobs(self):
        paths = PATHS + ['docs/r04b2a-purchase-intent.md',
                        'docs/r04b2b1-supplier-purchase-prices.md',
                        'scripts/test-r05a2-evidence.py', 'scripts/test-r05a3-evidence.py']
        selected = impact.selection(paths)
        self.assertEqual({k for k, value in selected.items() if value is True}, D87_JOBS)
        self.assertEqual(selected['api_filter'], '')
        self.assertFalse(selected['full_architecture'])
        validate_workflow((ROOT/'.github/workflows/ci.yml').read_text())

    def test_unknown_executables_fail_closed_even_in_mixed_offline_scope(self):
        for path in ('scripts/test-r04-authority-unknown.py', 'docs/authority.py',
                     'src/unknown.py', 'docs/new-authority.sh'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                impact.selection(PATHS+WIRING+[path])

    def test_mixed_security_and_stock_contracts_keep_acceptance(self):
        for path, required in (
            ('src/Enginia360.Api/Program.cs', ('browser', 'migrations', 'ui_build')),
            ('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
             ('browser', 'migrations', 'r04a', 'r04c1', 'r04c2', 'r06b1')),
            ('scripts/owner-stock-profile.py', ('r04a', 'r03a', 'ui01b'))):
            with self.subTest(path=path):
                selected = impact.selection(PATHS+WIRING+[path])
                self.assertTrue(selected['r06_offline'])
                self.assertFalse(selected['full_architecture'])
                for key in required:
                    self.assertTrue(selected[key], key)
        # Wiring alone retains the original security/runtime selection.
        self.assertTrue(impact.selection(WIRING)['browser'])

    def test_workflow_executes_offline_guard_and_mutations(self):
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        validate_workflow(text)
        for token in ('python3 scripts/test-r04-authority-impact.py',
                      'python3 -I scripts/test-r04-authority.py --check',
                      "needs.impact.outputs.r06_offline == 'true'"):
            with self.subTest(token=token), self.assertRaises(AssertionError):
                validate_workflow(text.replace(token, 'removed'))


if __name__ == '__main__':
    unittest.main()
