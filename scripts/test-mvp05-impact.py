#!/usr/bin/env python3
"""MVP05 finite source/CI selection guards, final phase only."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ImpactTests(unittest.TestCase):
 def test_each_exact_catalog_source_selects_real_catalog_and_direct_identity_consumers(self):
  for path in sorted(m.CATALOG_MANAGEMENT_FILES):
   with self.subTest(path=path):
    result=m.selection([path])
    for key in ('catalog_management','counterparty_management','tenant_roles','membership_access','federated_onboarding','authenticated_organization','frontend','migrations','browser'):self.assertTrue(result[key],key)
    for name in ('CatalogManagementTests','BusinessMembershipFenceTests','SupplierPurchasePriceTests','WorkshopBoundaryTests','CommercialCalculationTests'):self.assertIn(name,result['api_filter'])
    self.assertFalse(result['full_architecture'])
 def test_full_finite_manifest_stays_bounded_not_unrelated_erp(self):
  result=m.selection(sorted(m.CATALOG_MANAGEMENT_SCOPE))
  self.assertTrue(result['catalog_management']);self.assertTrue(result['counterparty_management'])
  for key in ('r04a','r03a','r03b','r03c','r04b2b3','r06b1','full_architecture'):self.assertFalse(result.get(key),key)
 def test_mixed_producers_preserve_original_true_flags_and_filters(self):
  for source in ('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs','src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs'):
   before=m.selection([source]);after=m.selection(sorted(m.CATALOG_MANAGEMENT_SCOPE|{source}))
   for key,value in before.items():
    if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(after.get(key),key)
   for token in before['api_filter'].split('|'):
    if token:self.assertIn(token,after['api_filter'])
   self.assertTrue(after['catalog_management'])
 def test_unknown_executable_and_near_prefix_fail_closed(self):
  for path in ('frontend/app/catalog/arbitrary.ts','scripts/run-mvp05-unknown.py','scripts/run-r00b-tests-copy.py','scripts/run-mvp02b-tests-copy.py','src/Unknown/Catalog.cs','src/Modules/Catalog/Enginia360.Catalog/Unmapped.cs'):
   with self.assertRaises(ValueError):m.selection(['database/runtime/migrations/0043_catalog_management.sql',path])
 def test_direct_shared_producers_keep_new_consumer_without_narrowing_old(self):
  for path in sorted(m.CATALOG_MANAGEMENT_DIRECT):
   result=m.selection([path]);self.assertTrue(result['catalog_management'],path);self.assertIn('CatalogManagementTests',result['api_filter'])
 def test_shared_catalog_module_alone_preserves_legacy_consumers_and_combined_manifest_is_finite(self):
  module='src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs'
  standalone=m.selection([module])
  for key in ('ui01b','r04b2b1','catalog_management'):
   self.assertTrue(standalone[key],key)
  exact=m.selection(sorted(m.CATALOG_MANAGEMENT_FILES | {module}))
  self.assertTrue(exact['catalog_management'])
  self.assertFalse(exact['full_architecture'])
  mixed=m.selection(sorted(m.CATALOG_MANAGEMENT_SCOPE | {'src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs'}))
  self.assertTrue(mixed['ui01b'])
 def test_current_protected_inventory_fixture_composition_keeps_direct_foundation_not_unrelated_erp(self):
  fixtures={'scripts/run-r00a-tests.py','scripts/run-r00b-tests.py','scripts/test-r00b-lifecycle.py','scripts/run-mvp02a-tests.py','scripts/run-mvp02b-tests.py','scripts/run-mvp02c-tests.py','scripts/run-mvp03b1-tests.py'}
  result=m.selection(sorted(m.CATALOG_MANAGEMENT_SCOPE|fixtures))
  for key in ('catalog_management','platform_authority','organization_administration','authenticated_organization','tenant_roles','membership_access','federated_onboarding','counterparty_management','browser','frontend','migrations'):
   self.assertTrue(result.get(key),key)
  self.assertTrue(result['platform_foundation_only'])
  for key in ('r03a','r03b','r03c','r04a','r04b2a','r04b2b1','r04b2b3','r04c1','r04c2','r06b1','full_architecture'):
   self.assertFalse(result.get(key),key)
  for path,key in [('scripts/run-r00a-tests.py','migrations'),('scripts/run-r00b-tests.py','browser'),('scripts/run-mvp02a-tests.py','platform_authority'),('scripts/run-mvp02b-tests.py','organization_administration'),('scripts/run-mvp02c-tests.py','authenticated_organization'),('scripts/run-mvp03b1-tests.py','tenant_roles')]:
   self.assertTrue(m.selection([path])[key],path)
 def test_dispatch_exact_head_two_pools_private_scratch_no_skipped_acceptance(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text();job=workflow.split('  affected-catalog-management:',1)[1].split('  affected-counterparty-management:',1)[0]
  for token in ("github.event_name == 'workflow_dispatch'","needs.impact.outputs.catalog_management == 'true'",'ref: ${{ github.sha }}','MVP05_POOL_SIZE=4','MVP05_POOL_SIZE=1','set -o pipefail','actions/upload-artifact@v4','if-no-files-found: error',"printf 'TMPDIR=%s"):
   self.assertIn(token,job)
  self.assertNotIn('\n  push:',workflow)
  runner=(ROOT/'scripts/run-mvp05-tests.py').read_text()
  for token in ('CatalogTests','CatalogManagementTests','BusinessMembershipFenceTests','PriceSqlTests','mvp05-catalog.cjs','catalog-sql-readback.json','runtime-hardening.json','actual-runtime-catalog.json','assert len(hashes)==42','notExecuted','r00.cleanup(command, project)','owner-master-authority.py','catalog.establish_authority','catalog.management_audit'):
   self.assertIn(token,runner)
  self.assertIn('Workshop__Enabled: "false"',runner)
if __name__=='__main__':unittest.main()
