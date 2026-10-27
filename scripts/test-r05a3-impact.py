#!/usr/bin/env python3
"""Finite offline owned-capture selection; never live ERP credentials in CI."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec is not None and spec.loader is not None
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
FILES = {'docs/r05a3-sandbox-business-contract.md','docs/r05a3-evidence.json',
         'tests/fixtures/r05a3-owned-captures.json','scripts/r05a3_captures.py',
         'scripts/test-r05a3-evidence.py','scripts/test-r05a3-impact.py'}
SHARED = {'docs/productization-plan.md','docs/productization-backlog.json',
          'docs/foundation/01-glossary-and-domain-boundaries.md',
          'scripts/test-c00-consistency.py','scripts/test-r04-authority.py',
          'scripts/test-r05a2-evidence.py'}
WIRING = {'scripts/select-ci-impact.py','.github/workflows/ci.yml'}
class ImpactTests(unittest.TestCase):
    def test_finite_new_and_combined_scope(self):
        for paths in [{p} for p in FILES]+[FILES|SHARED|WIRING]:
            with self.subTest(paths=paths):
                r=impact.selection(paths)
                self.assertTrue(r.get('r05a3_offline'),'missing actual-business evidence selection')
                for k,v in r.items():
                    if k not in ('changed_paths','r05a3_offline','r05a2_offline','r06_offline'):
                        self.assertFalse(v,k)
    def test_unknown_executables_and_mixed_security_fail_closed(self):
        for p in ('scripts/r05a3_unknown.py','tests/fixtures/r05a3_unknown.py','docs/r05a3.py'):
            with self.assertRaises(ValueError):impact.selection(FILES|{p})
        for p in ('src/Enginia360.Api/Program.cs','src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'):
            r=impact.selection(FILES|WIRING|{p})
            self.assertTrue(r.get('r05a3_offline'));self.assertTrue(r['browser']);self.assertTrue(r['migrations'])
        self.assertTrue(impact.selection(WIRING)['browser'])
    def test_offline_workflow_has_no_sandbox_transport(self):
        text=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('python3 -I scripts/test-r05a3-impact.py',text)
        self.assertIn('  affected-r05a3-offline:',text)
        block=text.split('  affected-r05a3-offline:')[1].split('\n  affected-r05a2-offline:')[0]
        self.assertIn("if: needs.impact.outputs.r05a3_offline == 'true'",block)
        self.assertIn('python3 -I scripts/test-r05a3-evidence.py',block)
        self.assertIn('not provider compatibility',block)
        self.assertIn('TMPDIR=%s',block)
        for forbidden in ('docker','curl','pip install','secrets.'):self.assertNotIn(forbidden,block)
        self.assertNotIn('  push:',text.split('concurrency:')[0])
if __name__=='__main__':unittest.main()
