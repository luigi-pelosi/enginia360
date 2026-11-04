#!/usr/bin/env python3
"""Final-only finite first-entry impact and current-state consistency assertions."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
assert spec and spec.loader
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def current_state(root):
 item=next(i for i in json.loads((root/'docs/mvp-backlog.json').read_text())['items'] if i['id']=='MVP-03')
 assert item['status']=='done' and item['runtimeDelivered'] is True
 assert item['existingMembershipAccess']['runtimeDelivered'] is True
 assert item['existingMembershipAccess']['pr']==165
 pending=item['federatedFirstEntry']
 assert pending['issueNumber']==166 and pending['runtimeDelivered'] is True
 assert pending['pr']==167 and pending['mergedMain']=='c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb'
 assert pending['prCi']==41752991377 and pending['runtimeDispatch']==41753044926
 assert pending['initialMembershipEnabled'] is False and pending['automaticRolesOrDelegations'] is False
 assert pending['contract']=='docs/mvp03b2b-federated-onboarding.md'
 assert pending['implementationStatus']=='source_complete'
 assert pending['validationStatus']=='verified_parent_exact_head_artifacts'
 # Historical D97/D98 summary is not a live implementation-state assertion.
 for name in ('AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md','docs/mvp03b2-user-onboarding.md'):
  text=(root/name).read_text()
  assert '#164' in text and '#166' in text
  assert '41752991377' in text and '41753044926' in text
  assert 'c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb' in text
  assert 'mvp03b2b-federated-onboarding.md' in text
class FederatedImpactTests(unittest.TestCase):
 def test_each_exact_file_selects_real_runtime_without_full_architecture(self):
  for path in sorted(m.FEDERATED_ONBOARDING_FILES):
   with self.subTest(path=path):
    r=m.selection([path]);self.assertTrue(r['federated_onboarding']);self.assertTrue(r['frontend']);self.assertTrue(r['browser']);self.assertTrue(r['migrations']);self.assertFalse(r['full_architecture']);self.assertIn('FederatedOnboardingTests',r['api_filter'])
 def test_actual_combined_scope_and_mixed_producers_preserve_their_consumers(self):
  files=sorted(m.FEDERATED_ONBOARDING_FILES|{'src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs','src/Enginia360.Api/Program.cs','src/Enginia360.Api/PlatformAdministration/TenantRoleAdministration.cs','frontend/lib/private-backend.ts','frontend/components/tenant-role-workspace.tsx','database/runtime/manifest.json','scripts/select-ci-impact.py','.github/workflows/ci.yml','scripts/run-mvp03b2a-tests.py'})
  files=sorted(set(files)|{
   'AGENTS.md','PROJECT_CHARTER.md','docs/mvp-backlog.json','docs/mvp-baseline.md',
   'docs/mvp-delivery-plan.md','docs/mvp03b2-user-onboarding.md','docs/mvp03b2b-federated-onboarding.md',
   'docs/r06-migration-inventory.json','frontend/components/shell.tsx','frontend/tests/shell.test.tsx',
   'web/src/ui01/Editor.acceptance.test.tsx'})
  actual=m.selection(files);self.assertTrue(actual['federated_onboarding']);self.assertTrue(actual['membership_access']);self.assertTrue(actual['tenant_roles']);self.assertTrue(actual['authenticated_organization']);self.assertFalse(actual['full_architecture'])
  for path,key in [('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','r04a'),('src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs','r03a'),('src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs','r03c')]:
   baseline=m.selection([path]);mixed=m.selection(files+[path]);self.assertTrue(mixed[key]);self.assertTrue(mixed['federated_onboarding'])
   for name,value in baseline.items():
    if isinstance(value,bool) and value and name!='platform_foundation_only':self.assertTrue(mixed.get(name),name)
 def test_unknown_mixed_executable_not_swallowed_by_new_anchor(self):
  for path in ('frontend/app/onboarding/unknown.ts','scripts/run-mvp03b2b-unknown.py','src/Unknown/Onboarding.cs'):
   with self.assertRaises(ValueError):m.selection(['database/runtime/migrations/0041_federated_onboarding.sql',path])
 def test_dispatch_only_exact_head_two_pools_artifact_and_old_consumers_remain(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text();job=workflow.split('  affected-federated-onboarding:',1)[1].split('  affected-membership-access:',1)[0]
  for token in ("github.event_name == 'workflow_dispatch'","needs.impact.outputs.federated_onboarding == 'true'",'ref: ${{ github.sha }}','fetch-depth: 0','MVP03B2B_POOL_SIZE=4','MVP03B2B_POOL_SIZE=1','set -o pipefail','actions/upload-artifact@v4','if-no-files-found: error','printf \'TMPDIR=%s'):
   self.assertIn(token,job)
  self.assertNotIn('\n  push:',workflow);self.assertIn('affected-membership-access:',workflow)
  runner=(ROOT/'scripts/run-mvp03b2b-tests.py').read_text()
  for token in ('FederatedOnboardingTests','OnboardingTests','mvp03b2b-onboarding.cjs','assert len(hashes)==40','actual-runtime-catalog.json','runtime-hardening.json','onboarding-sql-readback.json','artifact-sha256.json','r00.cleanup(command, project)'):
   self.assertIn(token,runner)
 def test_candidate_hashes_include_clean_test_fixtures_and_build_inputs(self):
  import subprocess,hashlib
  spec=importlib.util.spec_from_file_location('onboarding_runner',ROOT/'scripts/run-mvp03b2b-tests.py')
  self.assertIsNotNone(spec);self.assertIsNotNone(spec.loader)
  runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
  hashes=runner.candidate_source_hashes()
  paths=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
  self.assertEqual(set(hashes),{path for path in paths if (ROOT/path).is_file()})
  for path in ('tests/browser/mvp03b2b-onboarding.cjs','tests/Enginia360.Api.Tests/FederatedOnboardingTests.cs','compose.mvp02c-test.yaml','runtime-pool-test.Dockerfile','frontend/package-lock.json','database/runtime/manifest.json'):
   self.assertEqual(hashes[path],hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
 def test_current_delivered_activation_and_unverified_first_entry_with_negative_mutations(self):
  current_state(ROOT)
  names=['docs/mvp-backlog.json','AGENTS.md','PROJECT_CHARTER.md','docs/mvp-baseline.md','docs/mvp-delivery-plan.md','docs/mvp03b2-user-onboarding.md']
  with tempfile.TemporaryDirectory(prefix='mvp03b2b-current-') as directory:
   root=Path(directory)
   for name in names:
    target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
   current_state(root);file=root/'docs/mvp-backlog.json';original=file.read_text()
   for field in ('initialMembershipEnabled','automaticRolesOrDelegations','runtimeDelivered','implementationStatus','validationStatus'):
    value=json.loads(original);item=next(i for i in value['items'] if i['id']=='MVP-03');item['federatedFirstEntry'][field]=False if field=='runtimeDelivered' else True;file.write_text(json.dumps(value))
    with self.assertRaises(AssertionError):current_state(root)
    file.write_text(original)
   for name in names[1:]:
    file=root/name;original_text=file.read_text();file.write_text(original_text.replace('mvp03b2b-federated-onboarding.md','REMOVED'))
    with self.assertRaises(AssertionError):current_state(root)
    file.write_text(original_text)
if __name__=='__main__':unittest.main()
