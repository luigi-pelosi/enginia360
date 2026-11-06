#!/usr/bin/env python3
"""Finite MVP08 impact selection sources. Execute only at final whole-point gate."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py');assert spec and spec.loader
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ImpactTests(unittest.TestCase):
 def test_every_new_exact_producer_selects_stage_capacity_and_direct_regressions(self):
  for path in sorted(m.DEVELOPMENT_FILES):
   result=m.selection([path])
   for key in ('document_development','documents','document_types','tenant_roles','membership_access','frontend','migrations','browser'):self.assertTrue(result[key],(path,key))
   for name in ('DocumentDevelopmentTests','DocumentInventoryTests','DocumentTypeManagementTests','BusinessMembershipFenceTests'):self.assertIn('FullyQualifiedName~'+name,result['api_filter'])
   self.assertFalse(result['full_architecture'])
 def test_full_point_committed_base_and_dirty_overlay_stays_finite(self):
  actual=set(subprocess.check_output(['git','diff','--name-only','7d505db049880ef6fc4a2307dcd4575165c08923'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
  for paths in (m.DEVELOPMENT_SCOPE,actual):
   result=m.selection(sorted(paths));self.assertTrue(result['document_development']);self.assertFalse(result['full_architecture'])
   for key in ('r03a','r03b','r03c','r04a','r04b2b3'):self.assertFalse(result.get(key),(key,sorted(paths)))
   # The current whole point can explicitly correct the shared restore runner;
   # the historical pure MVP08 scope still must not acquire that consumer.
   self.assertEqual(result['r06b1'],bool(set(paths)&{'scripts/run-r06b1-tests.py','scripts/test-r06b1-guards.py','scripts/test-r06b1-lifecycle.py'}))
 def test_unknown_and_near_prefix_executable_fail_closed(self):
  for path in ('src/Modules/Documents/Enginia360.Documents/Unknown.cs','frontend/app/documents/unknown.ts','scripts/run-mvp08-copy.py','docs/workflow.py'):
   with self.assertRaises(ValueError):m.selection(['database/runtime/migrations/0046_document_development.sql',path])
 def test_mixed_producers_keep_original_true_flags_and_all_filters(self):
  for path in ('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs','src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs'):
   before=m.selection([path]);after=m.selection(sorted(m.DEVELOPMENT_SCOPE|{path}))
   for key,value in before.items():
    if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(after.get(key),key)
   for token in before['api_filter'].split('|'):
    if token:self.assertIn(token,after['api_filter'])
   self.assertTrue(after['document_development'])
 def test_shared_consumer_mappings_are_additive(self):
  for path in sorted(m.DEVELOPMENT_DIRECT):
   result=m.selection([path]);self.assertTrue(result['document_development'],path);self.assertIn('DocumentDevelopmentTests',result['api_filter'])
 def test_disjoint_exhaustive_sql_partition_preparation(self):
  spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/run-mvp08-tests.py');assert spec and spec.loader
  runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
  spec=importlib.util.spec_from_file_location('suite',ROOT/'scripts/test-mvp08-document-development.py');assert spec and spec.loader
  suite=importlib.util.module_from_spec(spec);spec.loader.exec_module(suite)
  expected=['DocumentDevelopmentTests.'+name for name in unittest.defaultTestLoader.getTestCaseNames(suite.DocumentDevelopmentTests)]
  partitions=runner.sql_partitions();flat=[name for group in partitions for name in group];self.assertEqual(sorted(flat),expected);self.assertEqual(len(flat),len(set(flat)));self.assertTrue(all(partitions))
 def test_exact_head_two_pool_job_no_original_deadline_or_image_drift(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text();job=workflow.split('  affected-document-development:',1)[1].split('  affected-documents:',1)[0]
  for token in ("github.event_name == 'workflow_dispatch'","needs.impact.outputs.document_development == 'true'",'ref: ${{ github.sha }}','MVP08_POOL_SIZE=4','MVP08_POOL_SIZE=1','timeout 1500','timeout-minutes: 60','set -o pipefail','if-no-files-found: error',"printf 'TMPDIR=%s"):
   self.assertIn(token,job)
  self.assertNotIn('\n  push:',workflow)
  self.assertIn('default: false',workflow.split('full_architecture:',1)[1].split('concurrency:',1)[0])
  runner=(ROOT/'scripts/run-mvp08-tests.py').read_text()
  for token in ('for partition,cases in enumerate(partitions,1):',"*cases, '-v'",'assert executed==sum(map(len,partitions))','timeout=240','timeout=360','time.monotonic() + 420','capture_protected_runtime','verify_protected_runtime'):
   self.assertIn(token,runner)
if __name__=='__main__':unittest.main()
