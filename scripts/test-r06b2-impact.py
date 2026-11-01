#!/usr/bin/env python3
"""Finite offline readiness scope; no runtime acceptance for registry/docs."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
PATHS = ['scripts/r06_readiness.py', 'scripts/test-r06-readiness.py', 'scripts/test-r06b2-impact.py',
         'docs/r06-readiness-registry.json', 'docs/r06-recovery-runbook.md']


def validate_workflow(text):
    triggers = text.split('concurrency:')[0]
    assert '  pull_request:' in triggers and '  push:' not in triggers
    impact_block = text.split('  impact:\n')[1].split('  affected-r06-offline:')[0]
    assert 'python3 scripts/test-r06b2-impact.py' in impact_block, 'independent impact job must guard offline selection/wiring'
    block = text.split('  affected-r06-offline:\n')[1].split('\n  affected-api:')[0]
    assert "if: needs.impact.outputs.r06_offline == 'true'" in block
    for command in ('python3 -I scripts/test-r06b2-impact.py', 'python3 -I scripts/test-r06-readiness.py',
                    'python3 -I scripts/r06_readiness.py'):
        assert command in block, 'readiness acceptance not executed in offline job: '+command
    assert 'docker' not in block and 'workflow_dispatch' not in block
    assert 'timeout-minutes: 3' in block


class ImpactTests(unittest.TestCase):
    def test_post_receipt_reconciliation_is_offline_with_executable_guards(self):
        paths = ['docs/productization-plan.md', 'docs/productization-backlog.json',
                 'docs/r04b3-receipt-runtime.md', 'docs/r06-recovery-runbook.md',
                 'scripts/test-productization-consistency.py', 'scripts/test-c00-consistency.py',
                 'scripts/select-ci-impact.py', 'scripts/test-r06b2-impact.py', '.github/workflows/ci.yml']
        selected = impact.selection(paths)
        self.assertTrue(selected['r06_offline'])
        self.assertEqual(selected['api_filter'], '')
        self.assertFalse(any(v for k, v in selected.items() if k not in ('r06_offline', 'changed_paths', 'api_filter')))
        for unsafe in ('scripts/post_receipt_unknown.py', 'docs/post_receipt_unknown.cs'):
            with self.assertRaises(ValueError):
                impact.selection(paths+[unsafe])
        mixed = impact.selection(paths+['src/Enginia360.Api/Program.cs'])
        self.assertTrue(mixed['browser'] and mixed['migrations'])
        self.assertFalse(mixed['full_architecture'])
        block = (ROOT/'.github/workflows/ci.yml').read_text().split('  affected-r06-offline:\n')[1].split('\n  affected-api:')[0]
        self.assertIn("run: printf 'TMPDIR=%s\\n' \"$RUNNER_TEMP\" >> \"$GITHUB_ENV\"", block)
        for command in ('python3 -I scripts/test-c00-consistency.py', 'python3 -I scripts/test-productization-consistency.py'):
            self.assertIn(command, block)

    def test_workflow_runs_readiness_acceptance_and_cli(self):
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        validate_workflow(text)
        for token in ('python3 -I scripts/test-r06b2-impact.py', 'python3 -I scripts/test-r06-readiness.py',
                      'python3 -I scripts/r06_readiness.py', "needs.impact.outputs.r06_offline == 'true'"):
            with self.subTest(token=token), self.assertRaises(AssertionError):
                validate_workflow(text.replace(token, 'removed'))

    def test_unknown_executable_stays_fail_closed_and_runtime_keeps_security(self):
        for path in ('scripts/r06_unsafe.py', 'docs/new-readiness.py'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                impact.selection(PATHS+[path])
        selected = impact.selection(PATHS+['src/Enginia360.Api/Program.cs'])
        self.assertTrue(selected['r06_offline'] and selected['browser'] and selected['migrations'])
        self.assertFalse(selected['full_architecture'])

    def test_registry_paths_select_only_offline(self):
        for paths in [[p] for p in PATHS] + [PATHS + ['scripts/select-ci-impact.py', '.github/workflows/ci.yml',
                'docs/productization-plan.md', 'docs/productization-backlog.json', 'docs/r06-restore-rehearsal.md',
                'docs/r06-migration-inventory.md']]:
            with self.subTest(paths=paths):
                try:
                    selected = impact.selection(paths)
                except ValueError as error:
                    self.fail('readiness offline paths unmapped: '+str(error))
                self.assertTrue(selected['r06_offline'])
                self.assertEqual(selected['api_filter'], '')
                for key, value in selected.items():
                    if key not in ('changed_paths', 'api_filter', 'r06_offline'):
                        self.assertFalse(value, key)


if __name__ == '__main__':
    unittest.main()
