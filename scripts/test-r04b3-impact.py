#!/usr/bin/env python3
"""Finite receiving paths retain permission, schema and dispatch consumers."""
import importlib.util,json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
impact=importlib.util.module_from_spec(spec);spec.loader.exec_module(impact)
OWN={'scripts/test-r04b3-migration-selection.py','scripts/test-r04b3-lifecycle.py','scripts/run-r04b3-tests.py','scripts/owner-receipt-grant.py','tests/browser/r04b3-acceptance.cjs','tests/browser/r04b3-giobby.py','compose.r04b3-test.yaml',
 'scripts/test-r04b3-impact.py','scripts/test-r04b3-receipts.py','database/runtime/migrations/0033_receipt_intents.sql',
 'src/Modules/Inventory/Enginia360.Inventory/ReceiptIntentEndpoints.cs','src/Modules/Inventory/Enginia360.Inventory/ReceiptDispatchOutbox.cs',
 'src/Modules/Inventory/Enginia360.Inventory.Contracts/ReceiptContracts.cs','src/Modules/Integrations/Enginia360.Integrations/ReceiptDispatcher.cs',
 'src/Modules/Integrations/Enginia360.Integrations/GiobbyReceiptConnector.cs','src/Modules/Integrations/Enginia360.Integrations/ReceiptDestination.cs',
 'tests/Enginia360.Api.Tests/GiobbyReceiptTests.cs'}
class Impact(unittest.TestCase):
 def test_receiving_composition_retains_material_siblings_without_unrelated_producers(self):
  paths=OWN|{'web/src/ui01/runtime/ReceiptReceiving.tsx','web/src/ui01/runtime/ReceiptReceiving.test.tsx','web/src/ui01/runtime/MaterialOperations.tsx','web/src/ui01/runtime/MaterialOperations.test.tsx','database/runtime/migrations/0034_receipt_sources.sql'}
  s=impact.selection(sorted(paths))
  for key in ('r04a','r04c1','r04c2','r04b2b3','ui01b','browser','migrations'):self.assertTrue(s[key],key)
  for key in ('r03a','r03a2','r03b','r03c','r05b0','r06a2','r06b1'):self.assertFalse(s[key],key)
  self.assertTrue(impact.selection(sorted(paths|{'web/src/ui01/runtime/MaterialPicking.tsx'}))['r03a'])
 def test_receiving_ui_and_forward_read_paths_select_receipt_acceptance(self):
  for path in ('web/src/ui01/runtime/ReceiptReceiving.tsx','web/src/ui01/runtime/ReceiptReceiving.test.tsx','database/runtime/migrations/0034_receipt_sources.sql'):
   with self.subTest(path=path):
    s=impact.selection([path]);self.assertTrue(s['r04b2b3']);self.assertTrue(s['ui_build']);self.assertTrue(s['browser']);self.assertFalse(s['full_architecture'])
 def test_receipt_paths_select_real_runtime_security_and_consumers(self):
  for path in sorted(OWN):
   with self.subTest(path=path):
    try:s=impact.selection([path])
    except ValueError as e:self.fail(str(e))
    for key in ('r04b2b3','migrations','browser','ui01b','r06_offline'):self.assertTrue(s[key],(path,key))
    for name in ('GiobbyReceiptTests','GiobbyPurchaseOrderTests','AdministrationBoundaryTests'):self.assertIn(name,s['api_filter'])
    self.assertFalse(s['full_architecture'])
 def test_receipt_manifest_narrows_only_finite_direct_consumers(self):
  shared={'scripts/test-r04-authority.py','docs/r04b3-receipt-runtime.md','src/Modules/Inventory/module.json','src/Modules/Inventory/Enginia360.Inventory/TechnicalAuditFilter.cs','database/runtime/manifest.json','migrator.runtime.Dockerfile','scripts/run-r00a-tests.py','scripts/run-r05b0-tests.py','scripts/select-ci-impact.py','.github/workflows/ci.yml'}
  selected=impact.selection(sorted(OWN|shared))
  for key in ('r04b2b3','r04b2a','r04b2b2','r05b1','browser','migrations','ui01b','r06_offline'):self.assertTrue(selected[key],key)
  for key in ('r03a','r03a2','r03b','r03c','r04a','r04c1','r04c2','r05b0','r06b1','r06a2'):self.assertFalse(selected[key],key)
  outside=impact.selection(sorted(OWN|shared|{'src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs'}))
  self.assertTrue(outside['r03a']);self.assertTrue(outside['r03a2'])
 def test_module_and_runner_publish_the_receipt_owners(self):
  inventory=json.loads((ROOT/'src/Modules/Inventory/module.json').read_text());integrations=json.loads((ROOT/'src/Modules/Integrations/module.json').read_text())
  for table in ('inventory.receipt_intents','inventory.receipt_outbox','inventory.receipt_outcomes'):self.assertIn(table,inventory['ownedTables'])
  self.assertIn('inventory.receipts.create',inventory['providedActions']);self.assertIn('integrations.receipt_dispatches',integrations['ownedTables'])
  for file in ('scripts/test-r04b3-receipts.py','scripts/owner-receipt-grant.py'):self.assertIn(file,(ROOT/'migrator.runtime.Dockerfile').read_text())
 def test_receipt_acceptance_and_sql_are_executable_in_selected_ci(self):
  text=(ROOT/'.github/workflows/ci.yml').read_text()
  for command in ('python3 -I scripts/test-r04b3-impact.py','timeout 600 python3 scripts/run-r04b3-tests.py','R05B0_POOL_SIZE=1 timeout 600 python3 scripts/run-r04b3-tests.py','timeout 420 python3 scripts/test-r04b3-lifecycle.py'):
   self.assertIn('run: '+command,text,'selected receipt acceptance is not wired')
 def test_docs_do_not_start_runtime_and_unknown_receipt_script_refuses(self):
  self.assertFalse(impact.selection(['docs/r04b3-receipt-runtime.md'])['r04b2b3'])
  with self.assertRaises(ValueError):impact.selection(['scripts/receipt-unmapped.py'])
if __name__=='__main__':unittest.main()
