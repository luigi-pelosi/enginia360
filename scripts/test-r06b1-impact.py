#!/usr/bin/env python3
"""R06.b.1 restore rehearsal impact: new executable paths fail closed; runtime is dispatch-only; skipped is not a pass."""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

OWN = ('scripts/run-r06b1-tests.py', 'scripts/r06b1_restore.py', 'scripts/test-r06b1-impact.py',
       'scripts/test-r06b1-guards.py', 'scripts/test-r06b1-lifecycle.py',
       'tests/browser/r06b1-acceptance.cjs', 'compose.r06b1-test.yaml')
DEPENDENCIES = ('scripts/run-r00b-tests.py', 'scripts/run-r03b-tests.py', 'compose.r00b-test.yaml',
                'compose.r03b-test.yaml', 'scripts/apply-runtime-migrations.py', 'postgres.runtime.Dockerfile',
                'migrator.runtime.Dockerfile', 'database/runtime/migrations/0023_reservation_releases.sql',
                'database/runtime/bootstrap-roles.sh',
                'src/Modules/Workshop/Enginia360.Workshop/ActualTimeEndpoints.cs',
                'src/Modules/Inventory/Enginia360.Inventory/ReleaseEndpoints.cs')


def workflow_block(text):
    assert '  affected-r06-restore:\n' in text, 'dedicated restore job missing'
    assert 'r06b1: ${{ steps.selection.outputs.r06b1 }}' in text, 'impact output missing'
    block = re.split(r'\n  [A-Za-z][A-Za-z0-9_-]*:\n', text.split('  affected-r06-restore:\n', 1)[1], maxsplit=1)[0]
    assert "github.event_name == 'workflow_dispatch' && needs.impact.outputs.r06b1 == 'true'" in block
    assert 'timeout 600 python3 scripts/run-r06b1-tests.py' in block
    assert 'timeout 420 python3 scripts/test-r06b1-lifecycle.py' in block
    assert 'continue-on-error' not in block
    return block


class RestoreImpactTests(unittest.TestCase):
    def test_own_paths_select_restore_and_offline_guards_only(self):
        for path in OWN:
            with self.subTest(path=path):
                s = m.selection([path])
                self.assertTrue(s.get('r06b1'), path)
                self.assertTrue(s['r06_offline'])
                self.assertFalse(s['full_architecture'])
                for key in ('browser', 'migrations', 'ui01b', 'ui_build', 'ui_tests', 'r03a', 'r03b', 'r04a', 'r04c1'):
                    self.assertFalse(s[key], key + ' must not be dragged in by restore-only edits')
                self.assertEqual(s['api_filter'], '')

    def test_direct_dependencies_select_restore(self):
        for path in DEPENDENCIES:
            with self.subTest(path=path):
                s = m.selection([path])
                self.assertTrue(s.get('r06b1'), path)
                self.assertFalse(s['full_architecture'])

    def test_unrelated_and_docs_do_not_select_restore(self):
        for path in ('docs/r06-restore-rehearsal.md', 'web/src/ui01/runtime/OrderList.tsx', 'scripts/run-r04c1-tests.py'):
            with self.subTest(path=path):
                self.assertFalse(m.selection([path]).get('r06b1', False), path)

    def test_unknown_new_executables_fail_closed(self):
        for path in ('scripts/r06b1_unreviewed.py', 'scripts/run-r06b2-tests.py', 'tests/browser/r06b1-other.cjs'.replace('browser', 'unmapped'),
                     'compose.r06b1-unreviewed.yaml', 'docs/r06b1-hidden.py'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                m.selection([path])

    def test_workflow_is_dispatch_only_and_pr_stays_offline(self):
        text = (ROOT/'.github/workflow'.replace('workflow', 'workflows')/'ci.yml').read_text()
        block = workflow_block(text)
        self.assertNotIn('  push:', text.split('concurrency:')[0])
        self.assertIn('python3 scripts/test-r06b1-impact.py', text.split('  affected-r06-offline:')[0])
        self.assertIn('python3 scripts/test-r06b1-guards.py', text.split('  affected-r06-offline:')[0])
        self.assertNotIn('pull_request', block)
        self.assertIn('full_architecture', text)

    def test_removing_job_invocation_output_or_condition_fails_closed(self):
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        for token in ('r06b1: ${{ steps.selection.outputs.r06b1 }}',
                      "github.event_name == 'workflow_dispatch' && needs.impact.outputs.r06b1 == 'true'",
                      'timeout 600 python3 scripts/run-r06b1-tests.py',
                      'timeout 420 python3 scripts/test-r06b1-lifecycle.py'):
            with self.subTest(token=token), self.assertRaises(AssertionError):
                workflow_block(text.replace(token, 'removed'))
        with self.assertRaises(AssertionError):
            workflow_block(text.replace('  affected-r06-restore:\n', '  affected-r06-other:\n'))


if __name__ == '__main__':
    unittest.main()
