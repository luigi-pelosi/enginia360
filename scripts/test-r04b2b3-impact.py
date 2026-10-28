#!/usr/bin/env python3
"""Finite R04.b.2b.3 purchase-order connector selection; unknown executables fail closed, runtime acceptance is dispatch-only."""
import importlib.util
import re
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
impact=importlib.util.module_from_spec(spec);spec.loader.exec_module(impact)
OWN={'scripts/test-r04b2b3-impact.py','scripts/test-r04b2b3-dispatch.py','scripts/run-r04b2b3-tests.py','scripts/test-r04b2b3-lifecycle.py',
 'tests/browser/r04b2b3-acceptance.cjs','tests/browser/r04b2b3-readout.cjs','tests/browser/r04b2b3-giobby.py','compose.r04b2b3-test.yaml','database/runtime/migrations/0031_purchase_dispatch.sql',
 'tests/Enginia360.Api.Tests/GiobbyPurchaseOrderTests.cs','database/runtime/migrations/0032_purchase_dispatch_readout.sql'}
# PR2 readout: Inventory owner read, Inventory.Contracts delivery contract and the existing purchase panel.
READOUT={'src/Modules/Inventory/Enginia360.Inventory/PurchaseIntentEndpoints.cs','src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseDispatchReadout.cs',
 'web/src/ui01/runtime/PurchaseIntent.tsx','web/src/ui01/runtime/PurchaseIntent.test.tsx'}
INTEGRATIONS='src/Modules/Integrations/Enginia360.Integrations/'
DIRECT={INTEGRATIONS+name for name in ('Enginia360.Integrations.csproj','GiobbyHost.cs','GiobbyPurchaseOrderConnector.cs','GiobbySalesOrderConnector.cs','GiobbyWire.cs',
 'IntegrationsDbContext.cs','IntegrationsModule.cs','PurchaseDestination.cs','PurchaseConnector.cs','PurchaseDispatcher.cs','SimulatorConnector.cs','packages.lock.json')}|{
 'src/Modules/Integrations/module.json','src/Modules/Inventory/Enginia360.Inventory.Contracts/PurchaseDispatchContracts.cs',
 'src/Modules/Inventory/Enginia360.Inventory/PurchaseDispatchOutbox.cs','src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
 'src/Enginia360.Api/packages.lock.json','tests/Enginia360.Api.Tests/packages.lock.json','tests/Enginia360.Api.Tests/AdministrationBoundaryTests.cs',
 'scripts/test-r00-migrations.py','scripts/test-r04b2a-purchase.py','tests/Enginia360.Api.Tests/PurchaseIntentTests.cs','tests/browser/r04b2b1-acceptance.cjs','tests/browser/r04b2a-acceptance.cjs','tests/browser/r04b2b2-acceptance.cjs'}
WIRING={'database/runtime/manifest.json','migrator.runtime.Dockerfile','scripts/run-r00a-tests.py','scripts/run-r05b0-tests.py','scripts/select-ci-impact.py','scripts/test-r03a-impact.py','.github/workflows/ci.yml'}
DOCS={'docs/r04b2b3-giobby-purchase-order-connector.md','docs/productization-plan.md','docs/productization-backlog.json','docs/r06-migration-inventory.json','docs/r06-migration-inventory.md'}
class Impact(unittest.TestCase):
 def test_purchase_acceptance_waits_for_real_tls_api_before_opening_login(self):
  for name in ('r04b2a-acceptance.cjs','r04b2b1-acceptance.cjs','r04b2b2-acceptance.cjs','r04b2b3-acceptance.cjs','r04b2b3-readout.cjs'):
   text=(ROOT/'tests/browser'/name).read_text()
   with self.subTest(name=name):
    self.assertIn('await waitForTlsApi(browser)',text)
    login=re.search(r'await login\(browser,\s*0\)',text);assert login is not None
    self.assertLess(text.index('await waitForTlsApi(browser)'),login.start())
    self.assertIn("origin+'/auth/session'",text);self.assertIn('authenticated === false',text)
 def test_each_own_or_direct_path_selects_the_purchase_connector_runtime_and_security(self):
  for path in sorted(OWN|DIRECT|READOUT):
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
  s=impact.selection(sorted(OWN|DIRECT|READOUT|WIRING|DOCS))
  for key in ('r03a','r03a2','r03b','r03c','r04a','r04c1','r04c2','r05b0','r06b1','r06a2'):self.assertFalse(s[key],key+' is not a direct consumer of purchase dispatch')
  for key in ('browser','migrations','ui01b','r04b2b2','r04b2b3','r05b1','ui_build','r06_offline'):self.assertTrue(s[key],key)
  self.assertFalse(s['ui_tests']);self.assertFalse(s['full_architecture'])
  for name in ('GiobbyPurchaseOrderTests','GiobbySalesOrderTests','PurchaseIntentTests','AdministrationBoundaryTests','InventoryArchitectureTests'):self.assertIn(name,s['api_filter'])
  mixed=impact.selection(sorted(OWN|DIRECT|{'src/Modules/Inventory/Enginia360.Inventory/ReleaseEndpoints.cs'}))
  self.assertTrue(mixed['r04c1']);self.assertTrue(mixed['r04c2'],'a mixed real producer change retains stock acceptance')
 def test_readout_paths_keep_their_existing_consumers_and_add_the_dispatch_acceptance(self):
  for path in sorted(READOUT|{'database/runtime/migrations/0032_purchase_dispatch_readout.sql'}):
   with self.subTest(path=path):
    s=impact.selection([path]);self.assertTrue(s['r04b2b3']);self.assertTrue(s['migrations']);self.assertTrue(s['ui01b'])
    if path.endswith('PurchaseIntentEndpoints.cs'):self.assertTrue(s['r04b2a'] and s['r04b2b2'],'existing purchase consumers are retained')
    if path.endswith('.tsx'):self.assertTrue(s['r04b2a'])
  # An unrelated real producer never inherits the narrowed purchase slice.
  mixed=impact.selection(sorted(READOUT|{'src/Modules/Inventory/Enginia360.Inventory/ReleaseEndpoints.cs'}))
  self.assertTrue(mixed['r04c1'] and mixed['r04c2'])
 def test_browser_readout_acceptance_covers_states_layout_and_isolation(self):
  text=(ROOT/'tests/browser/r04b2b3-readout.cjs').read_text()
  for needle in ('Non inviata','In verifica','Confermata','Non inviabile','po-grant:remove','Aggiungi riga','1366','1920','768','1080','await waitForTlsApi(browser)'):self.assertIn(needle,text,needle)
  self.assertLess(text.index('await waitForTlsApi(browser)'),text.index('await login(browser,0)'))
  workflow=(ROOT/'.github/workflows/ci.yml').read_text().split('  affected-r04b2b3:')[1].split('\n  runtime-migrations:')[0]
  self.assertEqual(workflow.count('R04B2B3_SPEC=r04b2b3-readout.cjs'),2,'readout acceptance runs at pool4 and pool1 in its own command bound')
  self.assertIn('timeout-minutes: 60',workflow)
 def test_a_lone_integrations_change_keeps_the_generic_administration_consumers(self):
  s=impact.selection([INTEGRATIONS+'GiobbyWire.cs'])
  for key in ('r03c','r03a','r05b1','r04b2b3'):self.assertTrue(s[key],key)
if __name__=='__main__':unittest.main()
