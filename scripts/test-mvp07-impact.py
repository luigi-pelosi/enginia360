#!/usr/bin/env python3
"""Final-phase MVP07 finite impact tests. SOURCES ONLY until entire #146 is implemented."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ImpactTests(unittest.TestCase):
 def test_every_exact_producer_selects_documents_and_actual_shared_consumers(self):
  for path in sorted(m.DOCUMENTS_FILES):
   result=m.selection([path])
   for key in ('documents','document_types','catalog_management','counterparty_management','tenant_roles','membership_access','frontend','migrations','browser'):self.assertTrue(result[key],(path,key))
   for name in ('DocumentInventoryTests','DocumentTypeManagementTests','BusinessMembershipFenceTests'):self.assertIn('FullyQualifiedName~'+name,result['api_filter'])
   self.assertFalse(result['full_architecture'])
 def test_whole_scope_and_actual_dirty_manifest_do_not_select_unrelated_architecture(self):
  actual=set(subprocess.check_output(['git','diff','--name-only','6ca378d94435eb78ff4955128e3646cc64ef1ece'],cwd=ROOT,text=True).splitlines())|set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
  for paths in (sorted(m.DOCUMENTS_SCOPE),sorted(actual)):
   if not paths:continue
   result=m.selection(paths);self.assertTrue(result['documents']);self.assertFalse(result['full_architecture'])
   for key in ('r03a','r03b','r03c','r04a','r04b2b3'):self.assertFalse(result.get(key),key)
   self.assertEqual(result['r06b1'],bool(set(paths)&{'scripts/run-r06b1-tests.py','scripts/test-r06b1-guards.py','scripts/test-r06b1-lifecycle.py'}))
 def test_whole_point_plus_exact_d99_historical_register_guard_remains_bounded(self):
  paths=m.DOCUMENTS_SCOPE|{'scripts/test-c00-consistency.py'}
  result=m.selection(sorted(paths))
  self.assertTrue(result['documents']);self.assertFalse(result['full_architecture'])
  for key in ('r03a','r03b','r03c','r04a','r04b2b3','r06b1'):self.assertFalse(result.get(key),key)
  mixed=m.selection(sorted(paths|{'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'}))
  original=m.selection(['src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'])
  for key,value in original.items():
   if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(mixed.get(key),key)
 def test_whole_point_plus_exact_first_boot_witness_fixture_keeps_bounded_foundation(self):
  paths=m.DOCUMENTS_SCOPE|{'scripts/test-r00-migrations.py'}
  result=m.selection(sorted(paths));self.assertTrue(result['documents']);self.assertTrue(result['platform_authority']);self.assertTrue(result['migrations']);self.assertTrue(result['platform_foundation_only'])
  for key in ('r03a','r03b','r03c','r04a','r04b2b3','r06b1'):self.assertFalse(result.get(key),key)
  mixed=m.selection(sorted(paths|{'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'}));original=m.selection(['src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'])
  for key,value in original.items():
   if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(mixed.get(key),key)
 def test_whole_point_plus_exact_private_browser_witness_fixture_is_bounded(self):
  paths=m.DOCUMENTS_SCOPE|{'scripts/run-r00b-tests.py'}
  result=m.selection(sorted(paths));self.assertTrue(result['documents']);self.assertTrue(result['browser']);self.assertTrue(result['platform_foundation_only'])
  for key in ('r03a','r03b','r03c','r04a','r04b2b3','r06b1'):self.assertFalse(result.get(key),key)
  mixed=m.selection(sorted(paths|{'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'}));original=m.selection(['src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'])
  for key,value in original.items():
   if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(mixed.get(key),key)
 def test_unknown_or_near_prefix_executable_paths_are_not_whitelisted(self):
  for path in ('src/Modules/Documents/Enginia360.Documents/Unknown.cs','frontend/app/documents/unknown.ts','scripts/run-mvp07-copy.py','src/Unknown/Document.cs'):
   with self.assertRaises(ValueError):m.selection(['database/runtime/migrations/0045_documents_inventory.sql',path])
 def test_mixed_historical_producers_keep_all_original_flags_and_filters(self):
  for path in ('src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs','src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs','src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs'):
   before=m.selection([path]);after=m.selection(sorted(m.DOCUMENTS_SCOPE|{path}))
   for key,value in before.items():
    if isinstance(value,bool) and value and key!='platform_foundation_only':self.assertTrue(after.get(key),key)
   for token in before['api_filter'].split('|'):
    if token:self.assertIn(token,after['api_filter'])
   self.assertTrue(after['documents'])
 def test_shared_producer_adds_real_consumer_without_erasing_older_scopes(self):
  for path in sorted(m.DOCUMENTS_DIRECT):
   result=m.selection([path]);self.assertTrue(result['documents'],path);self.assertIn('DocumentInventoryTests',result['api_filter'])
 def test_sql_partitions_are_disjoint_exhaustive_and_bound_to_real_runner(self):
  import ast
  spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/run-mvp07-tests.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
  test_spec=importlib.util.spec_from_file_location('document_tests',ROOT/'scripts/test-mvp07-documents-inventory.py');tests=importlib.util.module_from_spec(test_spec);test_spec.loader.exec_module(tests)
  expected=['DocumentInventoryTests.'+name for name in unittest.defaultTestLoader.getTestCaseNames(tests.DocumentInventoryTests)]
  partitions=runner.sql_partitions();flat=[name for group in partitions for name in group]
  self.assertEqual(sorted(flat),expected);self.assertEqual(len(flat),len(set(flat)));self.assertTrue(all(partitions))
  source=(ROOT/'scripts/run-mvp07-tests.py').read_text()
  self.assertIn('for partition,cases in enumerate(partitions,1):',source);self.assertIn("*cases, '-v'",source)
  self.assertIn("assert int(sql_count.group(1))==len(cases)",source);self.assertIn('timeout=240',source)
  self.assertIn('assert executed==sum(map(len,partitions))',source)
 def test_exact_head_two_pools_unchanged_deadlines_pins_private_cleanup(self):
  workflow=(ROOT/'.github/workflows/ci.yml').read_text();job=workflow.split('  affected-documents:',1)[1].split('  affected-document-types:',1)[0]
  for token in ("github.event_name == 'workflow_dispatch'","needs.impact.outputs.documents == 'true'",'ref: ${{ github.sha }}','MVP07_POOL_SIZE=4','MVP07_POOL_SIZE=1','timeout 1500','timeout-minutes: 60','set -o pipefail','if-no-files-found: error',"printf 'TMPDIR=%s"):
   self.assertIn(token,job)
  self.assertNotIn('\n  push:',workflow)
  runner=(ROOT/'scripts/run-mvp07-tests.py').read_text()
  for token in ('DocumentInventoryTests','mvp07-documents-inventory.cjs','documents-quantity-provenance-readback.json','runtime-hardening.json','actual-runtime-catalog.json','assert len(hashes)==44','notExecuted','r00.cleanup(command, project)','capture_protected_runtime','verify_protected_runtime','Documents__Enabled: "true"','Workshop__Enabled: "false"','time.monotonic() + 420','timeout=240','timeout=360'):
   self.assertIn(token,runner)
if __name__=='__main__':unittest.main()
