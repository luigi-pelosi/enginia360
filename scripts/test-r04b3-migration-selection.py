#!/usr/bin/env python3
"""Bounded migration partitions preserve every existing suite and receipt proof."""
import ast
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner', ROOT/'scripts/run-r00a-tests.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
ORIGINAL = {'scripts/test-'+name+'.py' for name in ('r00-migrations','r00b-bindings','r01b-grants','r02b-authority','r04b1-supplier','r04b2a-purchase','r04b2b1-prices','r04b2b2-freeze','r04b2b3-dispatch','r03a-migration')}
class MigrationSelection(unittest.TestCase):
    def test_finite_disjoint_partitions_preserve_original_and_new_coverage(self):
        self.assertTrue(hasattr(runner, 'selected_suites'), 'bounded migration selection missing')
        foundation = set(runner.selected_suites('foundation'))
        purchasing = set(runner.selected_suites('purchasing'))
        self.assertFalse(foundation & purchasing)
        self.assertEqual(foundation | purchasing, ORIGINAL)
        self.assertEqual(set(runner.selected_suites('receipts')), {'scripts/test-r04b3-receipts.py'})
        self.assertEqual(set(runner.selected_suites('all')), ORIGINAL)
        with self.assertRaises(ValueError): runner.selected_suites('unknown')
    def test_ci_executes_all_partitions_with_existing_finite_budget(self):
        import re
        text = (ROOT/'.github/workflows/ci.yml').read_text().split('  affected-migrations:\n')[1].split('\n  affected-browser:')[0]
        steps = text.split('      - name:')
        selected = [s for s in steps if '\n        run: timeout 600 sh scripts/run-r00a-tests.sh\n' in s]
        self.assertEqual({re.search(r'R00_MIGRATION_SUITE: (\w+)', s).group(1) if re.search(r'R00_MIGRATION_SUITE: (\w+)', s) else None for s in selected}, {'foundation','purchasing','receipts'})
        self.assertEqual(len(selected), 3)
        text = (ROOT/'scripts/run-r00a-tests.py').read_text()
        self.assertIn("os.environ.get('R00_MIGRATION_SUITE', 'all')", text)
        tree = ast.parse(text)
        loops = [n for n in ast.walk(tree) if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'suite']
        self.assertEqual(len(loops), 1)
        self.assertEqual(set(ast.literal_eval(loops[0].iter)), ORIGINAL | {'scripts/test-r04b3-receipts.py'})
        self.assertIn('if suite not in selected:', text)
        self.assertIn('selected = selected_suites(', text)
if __name__ == '__main__': unittest.main()
