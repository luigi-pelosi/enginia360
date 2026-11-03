#!/usr/bin/env python3
"""Finite user administration selection; no arbitrary executable exemptions."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
FILES={
 'database/runtime/migrations/0039_tenant_roles.sql',
 'src/Enginia360.Api/PlatformAdministration/TenantRoleAdministration.cs',
 'scripts/test-mvp03b1-roles.py','scripts/run-mvp03b1-tests.py','scripts/test-mvp03b1-impact.py',
 'frontend/app/users/page.tsx','frontend/components/tenant-role-workspace.tsx',
 'frontend/lib/tenant-roles.ts','frontend/tests/tenant-roles.test.tsx',
 'tests/browser/mvp03b1-roles.cjs',
}
class ImpactTests(unittest.TestCase):
 def test_finite_paths_select_current_authorization_and_authenticated_consumers(self):
  for path in FILES:
   with self.subTest(path=path):
    result=m.selection([path])
    self.assertTrue(result.get('tenant_roles',False),'missing actual tenant roles acceptance: '+path)
    for key in ('browser','migrations','frontend','organization_administration','authenticated_organization'):
     self.assertTrue(result.get(key,False),key)
    self.assertIn('AuthorizedContextContractTests',result['api_filter'])
    self.assertFalse(result['full_architecture'])
 def test_shared_producers_keep_new_consumer_and_existing_flags(self):
  for path in ('src/Enginia360.Api/OrganizationAccess/OrganizationAccessModule.cs','src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs','frontend/lib/private-backend.ts','frontend/components/shell.tsx','database/runtime/manifest.json','scripts/run-r00b-tests.py','scripts/run-mvp02c-tests.py'):
   self.assertTrue(m.selection([path]).get('tenant_roles',False),path)
  result=m.selection(['frontend/app/users/page.tsx','src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'])
  self.assertTrue(result['r04a']);self.assertTrue(result['tenant_roles'])
 def test_bounded_composition_does_not_run_unrelated_erp(self):
  result=m.selection(sorted(FILES|{'scripts/select-ci-impact.py','.github/workflows/ci.yml','docs/mvp03b1-tenant-role-contract.md','src/Enginia360.Api/OrganizationAccess/OrganizationAccessModule.cs','src/Enginia360.Api/Program.cs','database/runtime/manifest.json','docs/r06-migration-inventory.json','docs/r06-migration-inventory.md'}))
  self.assertTrue(result['platform_foundation_only'])
 def test_unknown_executable_is_not_hidden(self):
  for path in ('frontend/app/users/unknown.ts','scripts/run-mvp03b1-unknown.py','docs/mvp03b1-unknown.py'):
   with self.assertRaises(ValueError):m.selection(['frontend/app/users/page.tsx',path])
 def test_runtime_job_executes_both_pools_with_artifacts(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text()
  self.assertIn('      tenant_roles:',workflow)
  self.assertIn('scripts/test-mvp03b1-impact.py',workflow)
  job=workflow.split('  affected-tenant-roles:',1)[1].split('\n  affected-',1)[0]
  for token in ("github.event_name == 'workflow_dispatch'","needs.impact.outputs.tenant_roles == 'true'",'scripts/run-mvp03b1-tests.py','MVP03B1_POOL_SIZE=1','--evidence-dir','actions/upload-artifact@v4'):
   self.assertIn(token,job)
if __name__=='__main__':unittest.main()
