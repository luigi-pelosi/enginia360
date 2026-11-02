#!/usr/bin/env python3
"""New frontend scope must be finite; historical producers retain consumers."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT / 'scripts/select-ci-impact.py')
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)

class FrontendImpactTests(unittest.TestCase):
    def test_shell_only_selects_new_frontend_not_historical_runtime(self):
        result = impact.selection(['frontend/app/page.tsx', 'scripts/run-mvp01-tests.py',
            'scripts/test-mvp01-impact.py', 'scripts/select-ci-impact.py', '.github/workflows/ci.yml',
            'docs/mvp01-frontend.md', 'docs/mvp-backlog.json', 'docs/mvp-delivery-plan.md'])
        self.assertTrue(result.get('frontend'), 'new explicit frontend selection is required')
        self.assertTrue(result['mvp_offline'])
        self.assertEqual(result['api_filter'], '')
        for key, value in result.items():
            if isinstance(value, bool) and key not in ('frontend', 'mvp_offline'):
                self.assertFalse(value, key)

    def test_mixed_producer_retains_historical_consumers(self):
        for source in ('src/Enginia360.Api/Program.cs', 'web/src/ui01/runtime/PurchaseIntent.tsx'):
            baseline = impact.selection([source])
            mixed = impact.selection([source, 'frontend/app/page.tsx'])
            self.assertTrue(mixed.get('frontend'))
            for key, value in baseline.items():
                if isinstance(value, bool) and value: self.assertTrue(mixed[key], key)
            self.assertEqual(mixed['api_filter'], baseline['api_filter'])

    def test_unknown_paths_fail_closed_even_with_frontend_anchor(self):
        for path in ('frontend/new-handler.ts', 'frontend/app/api/new/route.ts',
                     'scripts/unknown.py', 'docs/new.sh', '../frontend/app/page.tsx'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                impact.selection(['frontend/app/page.tsx', path])

    def test_workflow_runs_both_new_scopes_without_automatic_runtime(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        def validate(value):
            trigger = value.split('concurrency:', 1)[0]
            assert '  push:' not in trigger and '  pull_request:' in trigger
            assert 'default: false' in trigger
            assert 'frontend: ${{ steps.selection.outputs.frontend }}' in value
            assert 'python3 -I scripts/test-mvp01-impact.py' in value
            build = value.split('  affected-frontend:\n', 1)[1].split('  affected-frontend-runtime:', 1)[0]
            runtime = value.split('  affected-frontend-runtime:\n', 1)[1].split('  affected-mvp-offline:', 1)[0]
            assert "if: needs.impact.outputs.frontend == 'true'" in build
            assert 'ref: ${{ github.event.pull_request.head.sha || github.sha }}' in build
            assert '--build-only' in build
            assert "if: github.event_name == 'workflow_dispatch' && needs.impact.outputs.frontend == 'true'" in runtime
            assert 'ref: ${{ github.sha }}' in runtime
            assert 'scripts/run-mvp01-tests.py --evidence-dir' in runtime
            assert 'actions/upload-artifact@v4' in runtime and 'if: always()' in runtime
        validate(text)
        for token in ("if: github.event_name == 'workflow_dispatch' && needs.impact.outputs.frontend == 'true'",
                      'frontend: ${{ steps.selection.outputs.frontend }}', '--build-only',
                      'scripts/run-mvp01-tests.py --evidence-dir', 'actions/upload-artifact@v4',
                      'ref: ${{ github.event.pull_request.head.sha || github.sha }}'):
            with self.subTest(token=token), self.assertRaises(AssertionError):
                validate(text.replace(token, 'removed'))

    def test_no_frontend_for_unrelated_or_shared_wiring_alone(self):
        self.assertFalse(impact.selection([]).get('frontend', False))
        self.assertFalse(impact.selection(['.github/workflows/ci.yml']).get('frontend', False))
        self.assertTrue(impact.selection(['.github/workflows/ci.yml'])['browser'])

if __name__ == '__main__': unittest.main(verbosity=2)
