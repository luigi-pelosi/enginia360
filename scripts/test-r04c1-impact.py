#!/usr/bin/env python3
"""Explicit release acceptance must run, selected before production edits."""
import importlib.util
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class ReleaseImpactTests(unittest.TestCase):
    def test_release_direct_dependencies(self):
        for path in ('scripts/test-r04c1-impact.py','scripts/test-r04c1-guard-mutation.py','scripts/run-r04c1-tests.py','tests/browser/r04c1-acceptance.cjs','compose.r04c1-test.yaml','src/Modules/Inventory/Enginia360.Inventory/ReleaseEndpoints.cs','database/runtime/migrations/0023_reservation_releases.sql','web/src/ui01/runtime/MaterialRelease.tsx'):
            with self.subTest(path=path):
                s=m.selection([path])
                self.assertTrue(s.get('r04c1'),path)
                for key in ('r04a','r03a2','browser','migrations','ui01b','ui_build','ui_tests','r06_offline'): self.assertTrue(s[key],key)
                self.assertIn('AccountingBoundaryTests',s['api_filter'])
                self.assertFalse(s['full_architecture'])
    def test_dispatch_only(self):
        w=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('      r04c1: ${{ steps.selection.outputs.r04c1 }}',w)
        self.assertIn('  affected-r04c1:\n',w)
        b=re.split(r'\n  [A-Za-z][A-Za-z0-9_-]*:',w.split('  affected-r04c1:\n',1)[1],maxsplit=1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && needs.impact.outputs.r04c1 == 'true'",b)
        self.assertIn('timeout 600 python3 scripts/run-r04c1-tests.py',b)
        self.assertIn('R04A_POOL_SIZE=1 timeout 600 python3 scripts/run-r04c1-tests.py',b)
        self.assertIn('timeout 420 python3 scripts/test-r04c1-lifecycle.py',b)
        self.assertIn('npm run build:ui01-runtime',b)
        self.assertNotIn('continue-on-error',b)
    def test_owning_module_declares_only_new_operative_release(self):
        import json
        module=json.loads((ROOT/'src/Modules/Inventory/module.json').read_text())
        self.assertIn('inventory.reservations.release',module['providedActions'])
        self.assertIn('inventory.reservation_releases',module['ownedTables'])
        self.assertNotIn('inventory.reservations.release',(ROOT/'database/runtime/migrations/0016_limited_grant_administration.sql').read_text())
    def test_lifecycle_probe_budget_covers_cold_build_and_stays_within_command_limit(self):
        text=(ROOT/'scripts/test-r04c1-lifecycle.py').read_text()
        self.assertIn('legacy.PROBE_DEADLINE_SECONDS = 420',text)
        self.assertIn('PROBE_DEADLINE_SECONDS=240',(ROOT/'scripts/test-r00b-lifecycle.py').read_text())
    def test_term_wording_matches_actual_held_line_lock(self):
        text=(ROOT/'scripts/test-r04c1-lifecycle.py').read_text()
        self.assertIn('hold-line:',text)
        self.assertIn('held SQL line lock',text)
        self.assertNotIn('SQL stock',text)
    def test_negative(self):
        self.assertFalse(m.selection(['docs/r04c1-release.md']).get('r04c1',False))
        with self.assertRaises(ValueError):m.selection(['scripts/unmapped-release.py'])
if __name__=='__main__':unittest.main()
