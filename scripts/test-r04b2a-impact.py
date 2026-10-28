#!/usr/bin/env python3
"""Finite purchase-intent impact; unknown executable paths remain closed."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
impact=importlib.util.module_from_spec(spec);spec.loader.exec_module(impact)
OWN={
 'scripts/test-r04b2a-impact.py','scripts/test-r04b2a-purchase.py','scripts/run-r04b2a-tests.py','scripts/test-r04b2a-lifecycle.py',
 'tests/browser/r04b2a-acceptance.cjs','compose.r04b2a-test.yaml','database/runtime/migrations/0028_purchase_intents.sql',
 'src/Modules/Inventory/Enginia360.Inventory/PurchaseIntentEndpoints.cs',
 'src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseIntentContracts.cs',
 'src/Modules/Counterparties/Enginia360.Counterparties/PurchaseSuppliers.cs',
 'src/Modules/Integrations/Enginia360.Integrations/PurchaseDestination.cs',
 'web/src/ui01/runtime/PurchaseIntent.tsx','web/src/ui01/runtime/PurchaseIntent.test.tsx',
 'tests/Enginia360.Api.Tests/PurchaseIntentTests.cs'}
DIRECT={'web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/runtime.css',
 'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','database/runtime/manifest.json',
 'src/Modules/Integrations/Enginia360.Integrations/IntegrationsModule.cs',
 'src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs'}
class Impact(unittest.TestCase):
 def test_every_direct_path_selects_purchase_runtime_and_security(self):
  for path in sorted(OWN|DIRECT):
   with self.subTest(path=path):
    try: selected=impact.selection([path])
    except ValueError as e: self.fail(str(e))
    self.assertTrue(selected.get('r04b2a'),path)
    self.assertTrue(selected['migrations']);self.assertTrue(selected['ui_build'])
    self.assertIn('PurchaseIntentTests',selected['api_filter'])
    self.assertFalse(selected['full_architecture'])
 def test_unmapped_and_documentation(self):
  with self.assertRaises(ValueError): impact.selection(['scripts/unmapped-purchase.py'])
  self.assertFalse(impact.selection(['docs/r04b2a-purchase-intent.md']).get('r04b2a'))
if __name__=='__main__':unittest.main()
