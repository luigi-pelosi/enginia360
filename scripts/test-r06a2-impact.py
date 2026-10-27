#!/usr/bin/env python3
"""Finite staging-only impact, PR offline and exact-head opt-in PostgreSQL."""
import importlib.util
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
OWN = {'scripts/r06a2_transfer.py', 'scripts/r06a2_storage.py', 'scripts/run-r06a2-tests.py',
       'scripts/test-r06a2-transfer.py', 'scripts/test-r06a2-storage.py', 'scripts/test-r06a2-impact.py',
       'scripts/test-r06a2-lifecycle.py'}
DEPS = {'scripts/r06_synthetic.py', 'scripts/r06_reconcile.py', 'scripts/r06b1_restore.py', 'postgres.runtime.Dockerfile'}


def workflow(text):
    assert 'r06a2: ${{ steps.selection.outputs.r06a2 }}' in text
    block = re.split(r'\n  [\w-]+:\n', text.split('  affected-r06-staging:\n')[1], maxsplit=1)[0]
    assert "github.event_name == 'workflow_dispatch' && needs.impact.outputs.r06a2 == 'true'" in block
    for command in ('timeout 180 python3 -I scripts/run-r06a2-tests.py',
                    'timeout 180 python3 -I scripts/test-r06a2-lifecycle.py --actual'):
        assert 'run: ' + command in block
    assert 'continue-on-error' not in block
    offline = text.split('  affected-r06-offline:\n')[1].split('\n  affected-', 1)[0]
    assert 'python3 -I scripts/test-r06a2-transfer.py' in offline
    assert 'python3 -I scripts/test-r06a2-lifecycle.py' in offline
    assert '  push:' not in text.split('concurrency:')[0]


class Impact(unittest.TestCase):
    def test_owned_runtime_and_wiring_only_select_staging_and_offline(self):
        for paths in ([p] for p in OWN):
            s = m.selection(paths)
            self.assertTrue(s.get('r06a2'), paths)
            self.assertTrue(s['r06_offline'])
            self.assertEqual(s['api_filter'], '')
            for key in ('browser', 'migrations', 'r06b1', 'ui_build', 'full_architecture'):
                self.assertFalse(s[key], key)
        s = m.selection(sorted(OWN | m.R06_WIRING | {'docs/r06a2-synthetic-import-export.md'}))
        self.assertTrue(s['r06a2'])
        self.assertFalse(s['browser'])

    def test_dependencies_and_mixed_security_changes_preserve_acceptance(self):
        for p in DEPS:
            self.assertTrue(m.selection([p]).get('r06a2'), p)
        s = m.selection(['scripts/r06a2_storage.py', 'src/Enginia360.Api/Program.cs'])
        self.assertTrue(s['browser'] and s['migrations'] and s['r06a2'])

    def test_negative_and_unknown(self):
        for p in ('docs/r06a2-synthetic-import-export.md', 'web/src/ui01/App.tsx', 'scripts/run-r04c1-tests.py'):
            self.assertFalse(m.selection([p]).get('r06a2', False))
        for p in ('scripts/r06a2_unreviewed.py', 'compose.r06a2-unknown.yaml', 'docs/hidden.py'):
            with self.assertRaises(ValueError):
                m.selection([p])

    def test_executable_workflow_and_mutations(self):
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        workflow(text)
        for token in ('r06a2: ${{ steps.selection.outputs.r06a2 }}',
                      'timeout 180 python3 -I scripts/run-r06a2-tests.py',
                      'timeout 180 python3 -I scripts/test-r06a2-lifecycle.py --actual',
                      'python3 -I scripts/test-r06a2-transfer.py'):
            with self.assertRaises((AssertionError, IndexError)):
                workflow(text.replace(token, 'removed'))

if __name__ == '__main__':
    unittest.main()
