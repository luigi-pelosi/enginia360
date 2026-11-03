#!/usr/bin/env python3
"""Finite organization operations: unknown adjacent producers fail closed."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT / 'scripts/select-ci-impact.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FILES = {'src/Enginia360.Api/PlatformAdministration/OrganizationAdministration.cs',
 'scripts/test-mvp02b-impact.py','scripts/test-mvp02b-organization.py','scripts/run-mvp02b-tests.py',
 'tests/browser/mvp02b-organization.cjs','database/runtime/migrations/0037_organization_administration.sql'}
WIRING = {'src/Enginia360.Api/PlatformAdministration/PlatformAuthority.cs',
 'database/runtime/manifest.json','docs/r06-migration-inventory.json','docs/r06-migration-inventory.md',
 'scripts/select-ci-impact.py','.github/workflows/ci.yml','docs/mvp-delivery-plan.md',
 'docs/mvp02b-organization-administration.md','migrator.runtime.Dockerfile',
 'src/Enginia360.Api/Program.cs','tests/Enginia360.Api.Tests/ExternalIdentityAuthenticationTests.cs'}
class ImpactTests(unittest.TestCase):
 def test_finite_operations_select_real_security_consumers_not_erp(self):
  for paths in [*[ [p] for p in FILES], sorted(FILES|WIRING)]:
   with self.subTest(paths=paths):
    result=m.selection(paths)
    self.assertTrue(result['organization_administration'])
    self.assertTrue(result['platform_authority'])
    self.assertTrue(result['browser'])
    self.assertTrue(result['migrations'])
    self.assertIn('ExternalIdentityAuthenticationTests',result['api_filter'])
    for flag in ('full_architecture','ui01b','r04a','r04b2b3','r06_offline'):
     self.assertFalse(result[flag])
 def test_unknown_adjacent_producer_fails_closed(self):
  with self.assertRaises(ValueError):
   m.selection(['src/Enginia360.Api/PlatformAdministration/UnmappedOrganization.cs'])
 def test_mixed_business_producer_retains_consumers(self):
  result=m.selection(['scripts/test-mvp02b-organization.py','src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'])
  self.assertTrue(result['organization_administration'])
  self.assertTrue(result['r04a'])
 def test_ci_executes_organization_runtime_at_both_pool_sizes_and_retains_logs(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text()
  self.assertIn('  affected-organization-administration:',workflow)
  job=workflow.split('  affected-organization-administration:',1)[1].split('\n  affected-',1)[0]
  self.assertIn("github.event_name == 'workflow_dispatch'",job)
  self.assertIn("needs.impact.outputs.organization_administration == 'true'",job)
  self.assertIn('scripts/run-mvp02b-tests.py',job)
  self.assertIn('MVP02B_POOL_SIZE=1',job)
  self.assertIn('actions/upload-artifact@v4',job)
  self.assertIn('scripts/test-mvp02b-impact.py',workflow)
 def test_delegation_append_only_migration_selects_both_consumers(self):
  result=m.selection(['database/runtime/migrations/0038_organization_delegation.sql'])
  self.assertTrue(result.get('organization_administration',False))
  self.assertTrue(result.get('authenticated_organization',False))
  self.assertFalse(result['full_architecture'])
 def test_full_delegation_slice_retains_security_not_unrelated_erp(self):
  paths=FILES|WIRING|{'database/runtime/migrations/0038_organization_delegation.sql','docs/mvp03a-organization-delegation.md','docs/mvp03a-progress.md','docs/mvp-backlog.json','frontend/app/organization/page.tsx','frontend/components/organization-workspace.tsx','frontend/lib/organization.ts','frontend/lib/private-backend.ts','frontend/tests/organization.test.tsx','scripts/run-mvp02c-tests.py','tests/browser/mvp02c-organization.cjs'}
  result=m.selection(sorted(paths))
  self.assertTrue(result['organization_administration']);self.assertTrue(result['authenticated_organization']);self.assertTrue(result['frontend']);self.assertTrue(result['platform_authority'])
  self.assertTrue(result['platform_foundation_only'])
  for key in ('ui01b','r03a','r04a','r05b0','r06b1','r06_offline','full_architecture'):self.assertFalse(result[key],key)
if __name__=='__main__': unittest.main()
