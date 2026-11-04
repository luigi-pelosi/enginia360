#!/usr/bin/env python3
"""Final-phase MVP06 finite CI selection tests; source preparation is not execution."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py');assert spec and spec.loader
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ImpactTests(unittest.TestCase):
 def test_every_exact_source_selects_whole_company_types_and_actual_permission_consumers(self):
  for path in sorted(m.DOCUMENT_TYPES_FILES):
   result=m.selection([path])
   for key in ('document_types','catalog_management','counterparty_management','tenant_roles','membership_access','federated_onboarding','authenticated_organization','frontend','migrations','browser'):self.assertTrue(result[key],(path,key))
   for name in ('DocumentTypeManagementTests','BusinessMembershipFenceTests','CatalogManagementTests'):self.assertIn('FullyQualifiedName~'+name,result['api_filter'])
   self.assertFalse(result['full_architecture'])
 def test_entire_finite_manifest_and_actual_tracked_untracked_paths_stay_bounded(self):
  manifests=[sorted(m.DOCUMENT_TYPES_SCOPE)]
  actual=set(subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
  if actual:
   # Include the already-committed part of this whole point when correcting a
   # shared fixture; dirty-only paths are not the entire MVP06 change manifest.
   actual |= set(subprocess.check_output(['git','diff','--name-only','43a4ff836d67bf1b4f01eb27ccc318171ee45f8d','HEAD'],cwd=ROOT,text=True).splitlines())
   manifests.append(sorted(actual))
  for paths in manifests:
   result=m.selection(paths);self.assertTrue(result['document_types'])
   for key in ('r04a','r03a','r03b','r03c','r04b2b3','r06b1','full_architecture'):self.assertFalse(result.get(key),key)
 def test_committed_point_is_retained_for_a_dirty_shared_fixture_only_overlay(self):
  calls=[]
  def output(command,**kwargs):
   calls.append(command)
   if command==['git','diff','--name-only']:return 'tests/browser/mvp05-catalog.cjs\n'
   if command==['git','ls-files','--others','--exclude-standard']:return ''
   if command==['git','diff','--name-only','43a4ff836d67bf1b4f01eb27ccc318171ee45f8d','HEAD']:return 'database/runtime/migrations/0044_document_types.sql\n'
   raise AssertionError(command)
  with patch('subprocess.check_output',side_effect=output):
   self.test_entire_finite_manifest_and_actual_tracked_untracked_paths_stay_bounded()
  self.assertEqual(len(calls),3)
  self.assertEqual(calls[-1],['git','diff','--name-only','43a4ff836d67bf1b4f01eb27ccc318171ee45f8d','HEAD'])
 def test_shared_producers_add_new_consumer_never_erase_prior_flags(self):
  for path in sorted(m.DOCUMENT_TYPES_DIRECT):
   result=m.selection([path]);self.assertTrue(result['document_types'],path);self.assertIn('DocumentTypeManagementTests',result['api_filter'])
  for path in ('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs','src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs'):
   before=m.selection([path]);after=m.selection(sorted(m.DOCUMENT_TYPES_SCOPE|{path}))
   for key,value in before.items():
    if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(after.get(key),key)
   for token in before['api_filter'].split('|'):
    if token:self.assertIn(token,after['api_filter'])
   self.assertTrue(after['document_types'])
 def test_unknown_and_near_prefix_executable_paths_fail_closed(self):
  for path in ('src/Modules/DocumentTypes/Enginia360.DocumentTypes/Unmapped.cs','frontend/app/document-types/unknown.ts','scripts/run-mvp06-unknown.py','src/Unknown/Types.cs'):
   with self.assertRaises(ValueError):m.selection(['database/runtime/migrations/0044_document_types.sql',path])
 def test_exact_head_dispatched_two_pools_private_scratch_artifact_not_skip(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text();job=workflow.split('  affected-document-types:',1)[1].split('  affected-catalog-management:',1)[0]
  for token in ("github.event_name == 'workflow_dispatch'","needs.impact.outputs.document_types == 'true'",'ref: ${{ github.sha }}','MVP06_POOL_SIZE=4','MVP06_POOL_SIZE=1','set -o pipefail','actions/upload-artifact@v4','if-no-files-found: error',"printf 'TMPDIR=%s"):
   self.assertIn(token,job)
  self.assertNotIn('\n  push:',workflow)
  runner=(ROOT/'scripts/run-mvp06-tests.py').read_text()
  for token in ('DocumentTypeTests','DocumentTypeManagementTests','BusinessMembershipFenceTests','mvp06-document-types.cjs','document-types-sql-readback.json','immutable-document-types-readback.json','runtime-hardening.json','actual-runtime-catalog.json','assert len(hashes)==43','notExecuted','r00.cleanup(command, project)','capture_protected_runtime','verify_protected_runtime'):
   self.assertIn(token,runner)
  self.assertIn('Workshop__Enabled: "false"',runner);self.assertIn('DocumentTypes__Enabled: "true"',runner);self.assertNotIn("action == 'master-setup'",runner)
if __name__=='__main__':unittest.main()
