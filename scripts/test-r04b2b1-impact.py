#!/usr/bin/env python3
"""Finite D91 purchase-list runtime impact, with direct producer coverage."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
impact=importlib.util.module_from_spec(spec);spec.loader.exec_module(impact)
OWN={
 'scripts/test-r04b2b1-impact.py','scripts/test-r04b2b1-prices.py','scripts/run-r04b2b1-tests.py','scripts/test-r04b2b1-lifecycle.py',
 'scripts/owner-purchase-price-grant.py','tests/browser/r04b2b1-acceptance.cjs','compose.r04b2b1-test.yaml',
 'database/runtime/migrations/0029_supplier_purchase_prices.sql',
 'src/Modules/Catalog/Enginia360.Catalog/PurchasePriceEndpoints.cs',
 'tests/Enginia360.Api.Tests/SupplierPurchasePriceTests.cs',
 'web/src/ui01/runtime/SupplierPurchasePrices.tsx','web/src/ui01/runtime/SupplierPurchasePrices.test.tsx'}
DIRECT={'src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs','src/Modules/Catalog/Enginia360.Catalog/Enginia360.Catalog.csproj',
 'src/Enginia360.Api/Program.cs','database/runtime/manifest.json',
 'web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/runtime.css',
 'scripts/run-r05b0-tests.py','scripts/run-r00a-tests.py','migrator.runtime.Dockerfile'}
class Impact(unittest.TestCase):
 def test_each_own_and_direct_producer_selects_runtime_security_and_build(self):
  for path in sorted(OWN|DIRECT):
   with self.subTest(path=path):
    try: selected=impact.selection([path])
    except ValueError as e:self.fail(str(e))
    self.assertTrue(selected.get('r04b2b1'),path)
    self.assertTrue(selected['migrations']);self.assertTrue(selected['ui_build'])
    self.assertIn('SupplierPurchasePriceTests',selected['api_filter'])
    self.assertFalse(selected['full_architecture'])
 def test_unknown_executable_fails_closed_docs_do_not_select_runtime(self):
  with self.assertRaises(ValueError):impact.selection(['scripts/unmapped-price.py'])
  self.assertFalse(impact.selection(['docs/r04b2b1-supplier-purchase-prices.md']).get('r04b2b1'))
 def test_new_runtime_is_dispatch_only_and_fixture_contract_is_explicit(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text()
  self.assertIn('  affected-r04b2b1:',workflow,'supplier price acceptance job absent')
  job=workflow.split('  affected-r04b2b1:')[1].split('\n  affected-')[0]
  self.assertIn("github.event_name == 'workflow_dispatch'",job)
  self.assertIn('scripts/run-r04b2b1-tests.py',job);self.assertIn('scripts/test-r04b2b1-lifecycle.py',job)
  self.assertIn('r04b2b1-acceptance.cjs',(ROOT/'scripts/run-r05b0-tests.py').read_text())
  self.assertIn('scripts/test-r04b2b1-prices.py',(ROOT/'migrator.runtime.Dockerfile').read_text())
  self.assertIn('scripts/test-r04b2b1-prices.py',(ROOT/'scripts/run-r00a-tests.py').read_text())
if __name__=='__main__':unittest.main()
