#!/usr/bin/env python3
"""Finite offline dossier selection; unknown and mixed executable paths stay safe."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
PATHS = ['docs/r05a1-giobby-read-contract.md', 'docs/r05a1-evidence.json',
         'docs/r05a1-provider-questions.md', 'scripts/r05a1_evidence.py',
         'scripts/test-r05a1-evidence.py', 'scripts/test-r05a1-impact.py']
WIRING = ['scripts/select-ci-impact.py', '.github/workflows/ci.yml']
class ImpactTests(unittest.TestCase):
    def test_finite_paths_select_only_dossier_job(self):
        for paths in [[p] for p in PATHS] + [PATHS+WIRING]:
            with self.subTest(paths=paths):
                selected = impact.selection(paths)
                self.assertTrue(selected.get('r05a1_offline'), 'missing narrow offline dossier selection')
                self.assertEqual(selected['api_filter'], '')
                for key,value in selected.items():
                    if key not in ('changed_paths','api_filter','r05a1_offline'):
                        self.assertFalse(value,key)
    def test_unknown_executables_fail_closed(self):
        for p in ['scripts/r05a1_unknown.py','docs/r05a1.py','src/unknown.py']:
            with self.assertRaises(ValueError): impact.selection(PATHS+WIRING+[p])
    def test_mixed_security_runtime_preserved(self):
        for p in ['src/Enginia360.Api/Program.cs','src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs']:
            result=impact.selection(PATHS+WIRING+[p])
            self.assertTrue(result['browser']); self.assertTrue(result['migrations'])
            self.assertTrue(result['r05a1_offline']); self.assertFalse(result['full_architecture'])
        self.assertTrue(impact.selection(WIRING)['browser'])
    def test_workflow_narrow_offline_job(self):
        text=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('python3 -I scripts/test-r05a1-impact.py',text)
        self.assertIn('  affected-r05a1-offline:',text)
        block=text.split('  affected-r05a1-offline:')[1].split('\n  affected-r06-offline:')[0]
        self.assertIn("if: needs.impact.outputs.r05a1_offline == 'true'",block)
        self.assertIn('python3 -I scripts/test-r05a1-evidence.py',block)
        self.assertIn('python3 -I scripts/r05a1_evidence.py --check',block)
        for forbidden in ('docker','workflow_dispatch','curl','pip install'): self.assertNotIn(forbidden,block)
        self.assertNotIn('  push:',text.split('concurrency:')[0])
if __name__=='__main__': unittest.main()
