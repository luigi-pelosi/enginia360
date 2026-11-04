#!/usr/bin/env python3
"""Final-only MVP04 finite impact/source contract. Does not execute runtime acceptance."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ImpactTests(unittest.TestCase):
 def test_each_exact_new_source_selects_real_runtime_and_identity_compatibility(self):
  for path in sorted(m.COUNTERPARTY_MANAGEMENT_FILES):
   with self.subTest(path=path):
    result=m.selection([path]);self.assertTrue(result['counterparty_management']);self.assertTrue(result['frontend']);self.assertTrue(result['migrations']);self.assertTrue(result['membership_access']);self.assertTrue(result['tenant_roles']);self.assertTrue(result['federated_onboarding']);self.assertFalse(result['full_architecture']);self.assertIn('CounterpartyManagementTests',result['api_filter'])
 def test_complete_finite_scope_is_not_historical_erp_campaign(self):
  result=m.selection(sorted(m.COUNTERPARTY_MANAGEMENT_SCOPE))
  self.assertTrue(result['counterparty_management']);self.assertFalse(result['full_architecture'])
  for key in ('r04a','r03a','r03b','r03c','r04b2b3','r06b1'):self.assertFalse(result.get(key),key)
 def test_mixed_producers_retain_original_true_flags(self):
  for source in ('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs','src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs'):
   before=m.selection([source]);after=m.selection(sorted(m.COUNTERPARTY_MANAGEMENT_SCOPE|{source}))
   for key,value in before.items():
    if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(after.get(key),key)
   self.assertTrue(after['counterparty_management'])
 def test_unknown_executable_and_near_prefix_fail_closed(self):
  for path in ('frontend/app/counterparties/arbitrary.ts','scripts/run-mvp04-unknown.py','src/Unknown/Counterparty.cs'):
   with self.assertRaises(ValueError):m.selection(['database/runtime/migrations/0042_counterparty_management.sql',path])
 def test_dispatch_exact_head_two_pools_non_skipped_results_and_hardening_sources(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text();job=workflow.split('  affected-counterparty-management:',1)[1].split('  affected-federated-onboarding:',1)[0]
  for token in ("github.event_name == 'workflow_dispatch'","needs.impact.outputs.counterparty_management == 'true'",'ref: ${{ github.sha }}','MVP04_POOL_SIZE=4','MVP04_POOL_SIZE=1','set -o pipefail','actions/upload-artifact@v4','if-no-files-found: error',"printf 'TMPDIR=%s"):
   self.assertIn(token,job)
  self.assertNotIn('\n  push:',workflow)
  runner=(ROOT/'scripts/run-mvp04-tests.py').read_text()
  for token in ('CounterpartyManagementTests','CounterpartyMembershipFenceTests','CounterpartyTests','mvp04-counterparties.cjs','counterparty-sql-readback.json','runtime-hardening.json','actual-runtime-catalog.json','assert len(hashes)==41','notExecuted','r00.cleanup(command, project)','owner-master-authority.py'):
   self.assertIn(token,runner)
 def test_catalog_no_legacy_scope_wildcard_or_implicit_administrative_business_right(self):
  sql=(ROOT/'database/runtime/migrations/0042_counterparty_management.sql').read_text()
  for token in ('current_membership_access(NULL)','counterparty_permission','tenant_role_snapshot_changed','current_tenant_role_scopes_before_access','organization-context.read','counterparties.shared.read','counterparties.extensions.write','IS NOT DISTINCT FROM company','management_audit','immutable_management_audit','pg_advisory_xact_lock(777036)'):
   self.assertIn(token,sql)
  self.assertNotIn('GRANT ALL',sql);self.assertNotIn('DISABLE ROW LEVEL SECURITY',sql)
 def test_truthful_predecessor_and_unverified_current_with_negative_mutations(self):
  def check(root):
   data=json.loads((root/'docs/mvp-backlog.json').read_text());items={x['id']:x for x in data['items']};previous=items['MVP-03'];current=items['MVP-04']
   self.assertEqual(previous['status'],'done');self.assertIs(previous['runtimeDelivered'],True)
   proof=previous['federatedFirstEntry'];self.assertEqual(proof['pr'],167);self.assertEqual(proof['prCi'],41752991377);self.assertEqual(proof['runtimeDispatch'],41753044926);self.assertEqual(proof['mergedMain'],'c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb')
   self.assertIs(previous['userAdministrationPolicy']['runtimeDelivered'],False);self.assertIs(previous['userOnboardingPolicy']['runtimeDelivered'],False)
   self.assertIs(proof['initialMembershipEnabled'],False);self.assertIs(proof['automaticRolesOrDelegations'],False)
   self.assertEqual(current['status'],'done');self.assertIs(current['runtimeDelivered'],True);self.assertEqual(current['validationStatus'],'verified_parent_exact_head_artifacts');self.assertEqual(current['pr'],168);self.assertEqual(current['prCi'],41780772823);self.assertEqual(current['runtimeDispatch'],41780819337)
   for name in ('AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md'):
    text=(root/name).read_text();self.assertIn('41752991377',text);self.assertIn('41753044926',text);self.assertIn('mvp04-counterparties-contract.md',text)
  check(ROOT)
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);names=('docs/mvp-backlog.json','AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md')
   for name in names:
    file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes((ROOT/name).read_bytes())
   original=(root/names[0]).read_text()
   for field,value in [('status','in_progress'),('runtimeDelivered',False)]:
    data=json.loads(original);next(i for i in data['items'] if i['id']=='MVP-03')[field]=value;(root/names[0]).write_text(json.dumps(data))
    with self.assertRaises(AssertionError):check(root)
    (root/names[0]).write_text(original)
   for field,value in [('status','in_progress'),('runtimeDelivered',False),('validationStatus','LOCAL_FINAL_PASSED_REMOTE_PENDING')]:
    data=json.loads(original);next(i for i in data['items'] if i['id']=='MVP-04')[field]=value;(root/names[0]).write_text(json.dumps(data))
    with self.assertRaises(AssertionError):check(root)
    (root/names[0]).write_text(original)
   for name in names[1:]:
    file=root/name;text=file.read_text();file.write_text(text.replace('41753044926','REMOVED'))
    with self.assertRaises(AssertionError):check(root)
    file.write_text(text)
if __name__=='__main__':unittest.main()
