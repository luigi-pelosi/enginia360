#!/usr/bin/env python3
"""Finite R04.b.2b.3 purchase-order connector selection; unknown executables fail closed, runtime acceptance is dispatch-only."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
impact=importlib.util.module_from_spec(spec);spec.loader.exec_module(impact)
OWN={'scripts/test-r04b2b3-impact.py','scripts/test-r04b2b3-dispatch.py','scripts/run-r04b2b3-tests.py','scripts/test-r04b2b3-lifecycle.py',
 'tests/browser/r04b2b3-acceptance.cjs','tests/browser/r04b2b3-giobby.py','compose.r04b2b3-test.yaml','database/runtime/migrations/0031_purchase_dispatch.sql',
 'tests/Enginia360.Api.Tests/GiobbyPurchaseOrderTests.cs'}
INTEGRATIONS='src/Modules/Integrations/Enginia360.Integrations/'
DIRECT={INTEGRATIONS+name for name in ('Enginia360.Integrations.csproj','GiobbyHost.cs','GiobbyPurchaseOrderConnector.cs','GiobbySalesOrderConnector.cs','GiobbyWire.cs',
 'IntegrationsDbContext.cs','IntegrationsModule.cs','PurchaseDestination.cs','PurchaseConnector.cs','PurchaseDispatcher.cs','SimulatorConnector.cs','packages.lock.json')}|{
 'src/Modules/Integrations/module.json','src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseDispatchContracts.cs',
 'src/Modules/Inventory/Enginia360.Inventory/PurchaseDispatchOutbox.cs','src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
 'src/Enginia360.Api/packages.lock.json','tests/Enginia360.Api.Tests/packages.lock.json','tests/Enginia360.Api.Tests/AdministrationBoundaryTests.cs',
 'scripts/test-r00-migrations.py','tests/Enginia360.Api.Tests/PurchaseIntentTests.cs'}
WIRING={'database/runtime/manifest.json','migrator.runtime.Dockerfile','scripts/run-r00a-tests.py','scripts/run-r05b0-tests.py','scripts/select-ci-impact.py','scripts/test-r03a-impact.py','.github/workflows/ci.yml'}
DOCS={'docs/r04b2b3-giobby-purchase-order-connector.md','docs/productization-plan.md','docs/productization-backlog.json','docs/r06-migration-inventory.json','docs/r06-migration-inventory.md'}
class Impact(unittest.TestCase):
 def test_each_own_or_direct_path_selects_the_purchase_connector_runtime_and_security(self):
  for path in sorted(OWN|DIRECT):
   with self.subTest(path=path):
    try:s=impact.selection([path])
    except ValueError as e:self.fail(str(e))
    self.assertTrue(s.get('r04b2b3'),path);self.assertTrue(s['migrations']);self.assertTrue(s['ui_build']);self.assertFalse(s['full_architecture'])
    self.assertIn('GiobbyPurchaseOrderTests',s['api_filter'])
 def test_unknown_executables_fail_closed_and_docs_do_not_start_runtime(self):
  for path in ('scripts/unmapped-purchase.py',):
   with self.subTest(path=path):
    with self.assertRaises(ValueError):impact.selection([path])
  self.assertFalse(impact.selection(['docs/r04b2b3-giobby-purchase-order-connector.md']).get('r04b2b3'))
 def test_acceptance_is_dispatch_only_with_pool_and_term(self):
  text=(ROOT/'.github/workflows/ci.yml').read_text()
  self.assertIn('  affected-r04b2b3:',text)
  job=text.split('  affected-r04b2b3:')[1].split('\n  affected-')[0].split('\n  runtime-migrations:')[0]
  self.assertIn("github.event_name == 'workflow_dispatch'",job);self.assertIn("needs.impact.outputs.r04b2b3 == 'true'",job)
  for needle in ('scripts/run-r04b2b3-tests.py','R05B0_POOL_SIZE=1','scripts/test-r04b2b3-lifecycle.py'):self.assertIn(needle,job)
  self.assertIn('python3 -I scripts/test-r04b2b3-impact.py',text);self.assertIn('r04b2b3: ${{ steps.selection.outputs.r04b2b3 }}',text)
 def test_this_bounded_increment_selects_its_consumers_not_unrelated_historical_runtime(self):
  s=impact.selection(sorted(OWN|DIRECT|WIRING|DOCS))
  for key in ('r03a','r03a2','r03b','r03c','r04a','r04c1','r04c2','r05b0','r06b1','r06a2'):self.assertFalse(s[key],key+' is not a direct consumer of purchase dispatch')
  for key in ('browser','migrations','ui01b','r04b2b2','r04b2b3','r05b1','ui_build','r06_offline'):self.assertTrue(s[key],key)
  self.assertFalse(s['ui_tests']);self.assertFalse(s['full_architecture'])
  for name in ('GiobbyPurchaseOrderTests','GiobbySalesOrderTests','PurchaseIntentTests','AdministrationBoundaryTests','InventoryArchitectureTests'):self.assertIn(name,s['api_filter'])
  mixed=impact.selection(sorted(OWN|DIRECT|{'src/Modules/Inventory/Enginia360.Inventory/ReleaseEndpoints.cs'}))
  self.assertTrue(mixed['r04c1']);self.assertTrue(mixed['r04c2'],'a mixed real producer change retains stock acceptance')
 def test_a_lone_integrations_change_keeps_the_generic_administration_consumers(self):
  s=impact.selection([INTEGRATIONS+'GiobbyWire.cs'])
  for key in ('r03c','r03a','r05b1','r04b2b3'):self.assertTrue(s[key],key)
if __name__=='__main__':unittest.main()
