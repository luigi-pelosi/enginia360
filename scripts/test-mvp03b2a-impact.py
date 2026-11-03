#!/usr/bin/env python3
"""Final-phase finite membership impact tests; unknown/mixed producers fail closed."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MembershipImpactTests(unittest.TestCase):
 def test_published_byte_proof_checkout_has_the_exact_baseline_history(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text()
  job=workflow.split('  affected-membership-access:',1)[1].split('  affected-tenant-roles:',1)[0]
  self.assertIn('ref: ${{ github.sha }}',job)
  self.assertIn('fetch-depth: 0',job,'published-byte comparison needs the exact historical base, not a shallow head-only checkout')
  self.assertIn("2bad821b46b29d5ebb0556461f0eb3b3a61df280:database/runtime/manifest.json",(ROOT/'scripts/run-mvp03b2a-tests.py').read_text())
 def test_finite_membership_files_select_actual_owning_acceptance(self):
  for path in (
   'database/runtime/migrations/0040_membership_access.sql',
   'scripts/run-mvp03b2a-tests.py','scripts/test-mvp03b2a-membership.py',
   'tests/Enginia360.Api.Tests/BusinessMembershipFenceTests.cs',
   'tests/Enginia360.Api.Tests/WorkshopMembershipFenceTests.cs',
   'tests/browser/mvp03b2a-membership.cjs',
   *('src/Modules/'+module+'/Enginia360.'+module+'/MembershipOperation.cs' for module in ('Inventory','Billing','Accounting','Catalog','Vehicles','Integrations'))):
   with self.subTest(path=path):
    result=m.selection([path]);self.assertTrue(result['membership_access']);self.assertTrue(result['browser']);self.assertTrue(result['migrations']);self.assertTrue(result['frontend']);self.assertFalse(result['full_architecture'])
    for consumer in ('MembershipAccessTests','CounterpartyMembershipFenceTests','WorkshopMembershipFenceTests','BusinessMembershipFenceTests','RuntimeMigrationPoolTests'):
     self.assertIn('FullyQualifiedName~'+consumer,result['api_filter'])
 def test_mixed_real_producers_keep_their_consumer_jobs(self):
  for path,key in (
   ('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','r04a'),
   ('src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs','r03a'),
   ('src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs','r03c')):
   result=m.selection(['database/runtime/migrations/0040_membership_access.sql',path]);self.assertTrue(result['membership_access']);self.assertTrue(result[key]);self.assertFalse(result.get('platform_foundation_only',False))
 def test_exact_new_owning_files_keep_direct_consumers_without_directory_bypass(self):
  for path in (
   'src/Modules/Billing/Enginia360.Billing/BillingDbContext.cs',
   'src/Modules/Billing/Enginia360.Billing/ConfirmedInvoices.cs',
   'src/Modules/Accounting/Enginia360.Accounting/AccountingModule.cs',
   'src/Modules/Counterparties/Enginia360.Counterparties/Infrastructure/CounterpartiesDbContext.cs'):
   result=m.selection([path]);self.assertTrue(result['membership_access']);self.assertTrue(result['browser']);self.assertTrue(result['migrations'])
   self.assertIn('BillingBoundaryTests',result['api_filter']);self.assertIn('AccountingBoundaryTests',result['api_filter'])
  with self.assertRaises(ValueError):m.selection(['src/Modules/Billing/Enginia360.Billing/UnknownMemberConsumer.cs'])
 def test_unknown_nearby_executables_are_not_hidden(self):
  for path in ('scripts/run-mvp03b2a-unknown.py','docs/mvp03b2a-unknown.py','frontend/app/users/unknown.ts','src/Unknown/MembershipOperation.cs'):
   with self.assertRaises(ValueError):m.selection(['database/runtime/migrations/0040_membership_access.sql',path])
 def test_membership_runtime_job_is_exact_head_bounded_two_pool_dispatch_only(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text()
  job=workflow.split('  affected-membership-access:',1)[1].split('  affected-tenant-roles:',1)[0]
  for token in ("github.event_name == 'workflow_dispatch'","needs.impact.outputs.membership_access == 'true'",'ref: ${{ github.sha }}','MVP03B2A_POOL_SIZE=4','MVP03B2A_POOL_SIZE=1','scripts/run-mvp03b2a-tests.py','set -o pipefail','actions/upload-artifact@v4','if-no-files-found: error'):
   self.assertIn(token,job)
  self.assertIn('scripts/test-mvp03b2a-impact.py',workflow)
if __name__=='__main__':unittest.main()
