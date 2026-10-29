#!/usr/bin/env python3
"""Finite receipt-evidence selection, never runtime or provider access."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec is not None and spec.loader is not None
impact=importlib.util.module_from_spec(spec);spec.loader.exec_module(impact)
FILES={'docs/r05a8-sandbox-receipt-contract.md','docs/r05a8-evidence.json',
       'tests/fixtures/r05a8-owned-captures.json','scripts/r05a8_receipt.py',
       'scripts/test-r05a8-evidence.py','scripts/test-r05a8-impact.py'}
SHARED={'docs/productization-plan.md','docs/productization-backlog.json','docs/r06-recovery-runbook.md'}
WIRING={'scripts/select-ci-impact.py','.github/workflows/ci.yml'}
class ImpactTests(unittest.TestCase):
    def test_receipt_evidence_selects_only_offline(self):
        for paths in [{p} for p in FILES]+[FILES|SHARED|WIRING]:
            with self.subTest(paths=paths):
                try: result=impact.selection(paths)
                except ValueError as error: self.fail(str(error))
                self.assertTrue(result.get('r05a8_offline'), 'missing receipt evidence selection')
                for k,v in result.items():
                    if k not in {'changed_paths','r05a8_offline','r06_offline'}: self.assertFalse(v,k)
    def test_unknown_executable_and_mixed_security_remain_fail_closed(self):
        for p in ['scripts/r05a8_unknown.py','tests/fixtures/r05a8_unknown.py','docs/r05a8.py']:
            with self.assertRaises(ValueError): impact.selection(FILES|{p})
        r=impact.selection(FILES|{'src/Enginia360.Api/Program.cs'})
        self.assertTrue(r.get('r05a8_offline'));self.assertTrue(r['browser']);self.assertTrue(r['migrations'])
        self.assertTrue(impact.selection(WIRING)['browser'])
    def test_workflow_selects_receipt_guard_without_credentials(self):
        text=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('  affected-r05a8-offline:',text)
        block=text.split('  affected-r05a8-offline:')[1].split('\n  affected-r05a7-offline:')[0]
        self.assertIn("if: needs.impact.outputs.r05a8_offline == 'true'",block)
        self.assertIn('python3 -I scripts/test-r05a8-evidence.py',block)
        for p in ['docker','curl','secrets.','pip install']:self.assertNotIn(p,block)
        self.assertNotIn('  push:',text.split('concurrency:')[0])
if __name__=='__main__':unittest.main()
