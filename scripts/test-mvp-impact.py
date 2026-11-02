#!/usr/bin/env python3
"""Finite offline reset selection, mixed producer regressions and CI wiring."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('impact', ROOT / 'scripts/select-ci-impact.py')
assert SPEC is not None and SPEC.loader is not None
impact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(impact)
FILES = {
    'AGENTS.md', 'PROJECT_CHARTER.md', 'docs/mvp-baseline.md',
    'docs/mvp-existing-code-assessment.md', 'docs/mvp-delivery-plan.md',
    'docs/mvp-backlog.json', 'docs/productization-plan.md',
    'scripts/test-mvp-baseline.py', 'scripts/test-mvp-impact.py',
    'scripts/select-ci-impact.py', '.github/workflows/ci.yml',
}
# Shared wiring alone keeps its historical acceptance contract. An MVP-specific
# document/guard anchors this exception, never the selector/workflow by itself.
ANCHORS = FILES - {'AGENTS.md', 'docs/productization-plan.md',
                   'scripts/select-ci-impact.py', '.github/workflows/ci.yml'}


def validate_workflow(text):
    trigger = text.split('concurrency:', 1)[0]
    assert '  push:' not in trigger and '  pull_request:' in trigger, 'PR-only auto CI'
    assert 'full_architecture:' in trigger and 'default: false' in trigger, 'explicit full exception'
    assert 'mvp_offline: ${{ steps.selection.outputs.mvp_offline }}' in text, 'impact output missing'
    block = text.split('  affected-mvp-offline:\n')[1].split('\n  affected-', 1)[0]
    assert "if: needs.impact.outputs.mvp_offline == 'true'" in block, 'offline selection condition'
    assert 'needs: impact' in block, 'impact dependency'
    assert '"$RUNNER_TEMP" >> "$GITHUB_ENV"' in block and 'TMPDIR=%s' in block, 'private scratch initialization'
    for command in ('python3 -I scripts/test-mvp-baseline.py', 'python3 -I scripts/test-mvp-impact.py'):
        assert command in block, 'MVP guard not executed'
    assert 'docker ' not in block and 'scripts/run-' not in block, 'offline job may not run runtime'


class MvpImpactTests(unittest.TestCase):
    def test_finite_docs_and_wiring_only_are_offline(self):
        self.assertEqual(getattr(impact, 'MVP_OFFLINE_FILES', None), FILES)
        for paths in ([*FILES], *([anchor] for anchor in ANCHORS)):
            with self.subTest(paths=paths):
                result = impact.selection(paths)
                self.assertTrue(result.get('mvp_offline'), 'MVP offline selector missing')
                self.assertEqual(result['api_filter'], '')
                for key, value in result.items():
                    if isinstance(value, bool) and key != 'mvp_offline':
                        self.assertFalse(value, key)

    def test_shared_wiring_alone_preserves_historical_runtime_contract(self):
        for path in ('scripts/select-ci-impact.py', '.github/workflows/ci.yml'):
            result = impact.selection([path])
            self.assertTrue(result['browser'])
            self.assertTrue(result['migrations'])
            self.assertFalse(result.get('mvp_offline', False))

    def test_mixed_source_preserves_all_existing_consumers(self):
        for producer in ('src/Enginia360.Api/Program.cs',
                         'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
                         'web/src/ui01/runtime/PurchaseIntent.tsx',
                         'src/Modules/Counterparties/Enginia360.Counterparties/CommonEndpoints.cs'):
            baseline = impact.selection([producer])
            mixed = impact.selection([producer, *FILES])
            self.assertTrue(mixed.get('mvp_offline'))
            for key, value in baseline.items():
                if isinstance(value, bool) and value:
                    self.assertTrue(mixed[key], key)
            for consumer in baseline['api_filter'].split('|'):
                self.assertIn(consumer, mixed['api_filter'])
            self.assertFalse(mixed['full_architecture'])

    def test_unknown_executable_or_invalid_paths_fail_closed(self):
        for path in ('scripts/new-runtime.py', 'src/Modules/Unknown/New.cs',
                     'docs/unmapped.py', '../AGENTS.md', '/AGENTS.md'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                impact.selection([*FILES, path])
        self.assertFalse(impact.selection(['docs/unrelated.md']).get('mvp_offline', False))
        self.assertFalse(impact.selection([]).get('mvp_offline', False))

    def test_workflow_and_negative_wiring_mutations(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        validate_workflow(text)
        for token in ('mvp_offline: ${{ steps.selection.outputs.mvp_offline }}',
                      "if: needs.impact.outputs.mvp_offline == 'true'",
                      'python3 -I scripts/test-mvp-baseline.py',
                      'python3 -I scripts/test-mvp-impact.py'):
            with self.subTest(token=token), self.assertRaises((AssertionError, IndexError)):
                validate_workflow(text.replace(token, 'removed'))
        with self.assertRaises(AssertionError):
            validate_workflow(text.replace('  pull_request:', '  push:'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
