#!/usr/bin/env python3
"""Finite D91/D92 quote/freeze selection; unknown executables fail closed."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
impact=importlib.util.module_from_spec(spec);spec.loader.exec_module(impact)
OWN={'scripts/test-r04b2b2-impact.py','scripts/test-r04b2b2-freeze.py','scripts/run-r04b2b2-tests.py','scripts/test-r04b2b2-lifecycle.py',
 'tests/browser/r04b2b2-acceptance.cjs','compose.r04b2b2-test.yaml','database/runtime/migrations/0030_purchase_price_freeze.sql'}
DIRECT={'src/Modules/Inventory/Enginia360.Inventory/PurchaseIntentEndpoints.cs','src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseIntentContracts.cs',
 'web/src/ui01/runtime/PurchaseIntent.tsx','web/src/ui01/runtime/PurchaseIntent.test.tsx','web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/runtime.css',
 'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','database/runtime/manifest.json','scripts/run-r00a-tests.py','scripts/run-r05b0-tests.py','migrator.runtime.Dockerfile'}
class Impact(unittest.TestCase):
 def test_each_path_selects_bounded_runtime_and_security(self):
  for path in sorted(OWN|DIRECT):
   with self.subTest(path=path):
    try:s=impact.selection([path])
    except ValueError as e:self.fail(str(e))
    self.assertTrue(s.get('r04b2b2'),path)
    self.assertTrue(s['migrations']);self.assertTrue(s['ui_build'])
    self.assertIn('PurchaseIntentTests',s['api_filter']);self.assertFalse(s['full_architecture'])
 def test_unknown_fails_closed_docs_do_not_start_runtime(self):
  with self.assertRaises(ValueError):impact.selection(['scripts/unmapped-freeze.py'])
  self.assertFalse(impact.selection(['docs/r04b2b2-purchase-price-freeze.md']).get('r04b2b2'))
 def test_acceptance_dispatch_only(self):
  text=(ROOT/'.github/workflows/ci.yml').read_text()
  self.assertIn('  affected-r04b2b2:',text)
  job=text.split('  affected-r04b2b2:')[1].split('\n  affected-')[0]
  self.assertIn("github.event_name == 'workflow_dispatch'",job)
  self.assertIn('scripts/run-r04b2b2-tests.py',job);self.assertIn('scripts/test-r04b2b2-lifecycle.py',job)
 def test_this_bounded_increment_does_not_select_unrelated_historical_runtime(self):
  paths=OWN|{'src/Modules/Inventory/Enginia360.Inventory/PurchaseIntentEndpoints.cs','src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseIntentContracts.cs','tests/Enginia360.Api.Tests/PurchaseIntentTests.cs','web/src/ui01/runtime/PurchaseIntent.tsx','web/src/ui01/runtime/PurchaseIntent.test.tsx','tests/browser/r04b2a-acceptance.cjs','scripts/test-r04b2a-purchase.py','database/runtime/manifest.json','migrator.runtime.Dockerfile','scripts/run-r00a-tests.py','scripts/run-r05b0-tests.py','scripts/select-ci-impact.py','.github/workflows/ci.yml','docs/r04b2b2-purchase-price-freeze.md','docs/productization-plan.md','docs/productization-backlog.json','docs/r06-migration-inventory.json','docs/r06-migration-inventory.md'}
  s=impact.selection(list(paths))
  for key in ('r03a','r03a2','r03b','r03c','r04a','r04c1','r04c2','r05b0','r05b1','r06b1','r06a2'):
   self.assertFalse(s[key],key+' is not a direct changed-behavior consumer of quote/freeze')
  for key in ('browser','migrations','ui01b','r04b2a','r04b2b1','r04b2b2','ui_build','r06_offline'):self.assertTrue(s[key],key)
  mixed=impact.selection(list(paths|{'src/Modules/Inventory/Enginia360.Inventory/ReleaseEndpoints.cs'}))
  self.assertTrue(mixed['r04c1']);self.assertTrue(mixed['r04c2'],'mixed real producer change must retain stock acceptance')
if __name__=='__main__':unittest.main()
