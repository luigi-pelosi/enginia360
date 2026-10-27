#!/usr/bin/env python3
"""Finite sandbox evidence scope; no business/network/runtime acceptance implied."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
FILES = {'docs/r05a2-sandbox-contract.md', 'docs/r05a2-evidence.json',
         'scripts/test-r05a2-evidence.py', 'scripts/test-r05a2-impact.py'}
SHARED = {'docs/productization-plan.md', 'docs/productization-backlog.json',
          'docs/foundation/01-glossary-and-domain-boundaries.md',
          'scripts/test-c00-consistency.py', 'scripts/test-r04-authority.py'}
WIRING = {'scripts/select-ci-impact.py', '.github/workflows/ci.yml'}
class ImpactTests(unittest.TestCase):
    def test_finite_new_and_combined_scope(self):
        for paths in [{p} for p in FILES] + [FILES | SHARED | WIRING]:
            with self.subTest(paths=paths):
                result = impact.selection(paths)
                self.assertTrue(result.get('r05a2_offline'), 'missing sandbox evidence selection')
                for key, value in result.items():
                    if key not in ('changed_paths', 'r05a2_offline', 'r06_offline'):
                        self.assertFalse(value, key)
    def test_unknown_and_mixed_paths(self):
        for path in ('scripts/r05a2_new.py', 'docs/r05a2.py'):
            with self.assertRaises(ValueError): impact.selection(FILES | {path})
        for path in ('src/Enginia360.Api/Program.cs', 'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'):
            result = impact.selection(FILES | WIRING | {path})
            self.assertTrue(result.get('r05a2_offline'))
            self.assertTrue(result['browser']); self.assertTrue(result['migrations'])
        self.assertTrue(impact.selection(WIRING)['browser'])
    def test_workflow_executes_offline_only(self):
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('python3 -I scripts/test-r05a2-impact.py', text)
        self.assertIn('  affected-r05a2-offline:', text)
        block = text.split('  affected-r05a2-offline:')[1].split('\n  affected-r05a1-offline:')[0]
        self.assertIn("if: needs.impact.outputs.r05a2_offline == 'true'", block)
        self.assertIn('python3 -I scripts/test-r05a2-evidence.py', block)
        self.assertIn('not provider compatibility', block)
        self.assertIn('"$RUNNER_TEMP" >> "$GITHUB_ENV"', block)
        self.assertIn('TMPDIR=%s', block)
        for forbidden in ('docker', 'curl', 'pip install'): self.assertNotIn(forbidden, block)
        self.assertNotIn('  push:', text.split('concurrency:')[0])
if __name__ == '__main__': unittest.main()
