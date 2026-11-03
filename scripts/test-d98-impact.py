#!/usr/bin/env python3
"""Finite D98 docs-only exception; keep old producer consumers and budgets."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('impact', ROOT / 'scripts/select-ci-impact.py')
assert SPEC is not None and SPEC.loader is not None
impact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(impact)
FILES = {'docs/mvp03b2-user-onboarding.md', 'scripts/test-d98-policy.py',
         'scripts/test-d98-impact.py'}
SCOPE = FILES | {'AGENTS.md', 'PROJECT_CHARTER.md', 'docs/mvp-baseline.md',
                 'docs/mvp-backlog.json', 'docs/mvp-delivery-plan.md',
                 'scripts/select-ci-impact.py', '.github/workflows/ci.yml',
                 'docs/mvp03b-user-administration.md',
                 'docs/mvp03b1-tenant-role-contract.md', 'docs/mvp03b1-progress.md'}


def workflow(text):
    job = text.split('  affected-mvp-offline:\n')[1].split('\n  affected-', 1)[0]
    for command in ('python3 -I scripts/test-d98-policy.py', 'python3 -I scripts/test-d98-impact.py'):
        assert command in job, f'missing executed guard {command}'
    assert 'timeout-minutes: 3' in job, 'unchanged offline budget'
    assert 'TMPDIR=%s' in job and '"$RUNNER_TEMP" >> "$GITHUB_ENV"' in job, 'private scratch'
    assert 'docker ' not in job and 'scripts/run-' not in job, 'offline only'
    assert "if: needs.impact.outputs.mvp_offline == 'true'" in job, 'offline selector wiring'


class ImpactTests(unittest.TestCase):
    def test_exact_finite_paths(self):
        self.assertEqual(getattr(impact, 'D98_FILES', None), FILES)
        self.assertEqual(getattr(impact, 'D98_SCOPE', None), SCOPE)
        for paths in ([*SCOPE], *([p] for p in FILES)):
            result = impact.selection(paths)
            self.assertTrue(result.get('mvp_offline'))
            self.assertEqual(result['api_filter'], '')
            for key, value in result.items():
                if isinstance(value, bool) and key != 'mvp_offline':
                    self.assertFalse(value, key)

    def test_mixed_runtime_keeps_every_direct_consumer(self):
        for producer in ('src/Enginia360.Api/Program.cs',
                         'src/Enginia360.Api/PlatformAdministration/OrganizationAdministration.cs',
                         'frontend/components/organization-workspace.tsx',
                         'database/runtime/migrations/0038_organization_delegation.sql',
                         'src/Enginia360.Api/PlatformAdministration/TenantRoleAdministration.cs',
                         'frontend/components/tenant-role-workspace.tsx',
                         'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
                         'web/src/ui01/runtime/PurchaseIntent.tsx'):
            for additions in (FILES, SCOPE):
                with self.subTest(producer=producer, additions=additions):
                    base = impact.selection([producer])
                    mixed = impact.selection([producer, *additions])
                    self.assertTrue(mixed.get('mvp_offline'))
                    for key, value in base.items():
                        # This marker narrows execution; false adds consumers,
                        # unlike every positive runtime/offline job selector.
                        if isinstance(value, bool) and value and key != 'platform_foundation_only':
                            self.assertTrue(mixed[key], key)
                    for consumer in filter(None, base['api_filter'].split('|')):
                        self.assertIn(consumer, mixed['api_filter'])
                    self.assertFalse(mixed['full_architecture'])

    def test_unknown_execution_fails_closed_and_no_blanket_wiring_exception(self):
        for path in ('scripts/test-d98-unknown.py', 'docs/unknown.py', 'src/Unknown/New.cs',
                     '../AGENTS.md', '/AGENTS.md', 'docs//bad.md'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                impact.selection([*SCOPE, path])
        for path in ('scripts/select-ci-impact.py', '.github/workflows/ci.yml'):
            result = impact.selection([path])
            self.assertTrue(result['browser'])
            self.assertTrue(result['migrations'])
            self.assertFalse(result.get('mvp_offline', False))
        self.assertFalse(impact.selection(['docs/unrelated.md']).get('mvp_offline', False))

    def test_workflow_executes_guards_and_mutations_reject_removal(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        workflow(text)
        for token in ('python3 -I scripts/test-d98-policy.py',
                      'python3 -I scripts/test-d98-impact.py', 'timeout-minutes: 3',
                      'TMPDIR=%s', "if: needs.impact.outputs.mvp_offline == 'true'"):
            with self.subTest(token=token), self.assertRaises(AssertionError):
                workflow(text.replace(token, 'REMOVED'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
