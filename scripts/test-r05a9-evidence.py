#!/usr/bin/env python3
"""New valid owned campaign must be accepted; unsafe promotions rejected."""
import copy,importlib.util,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('receipt',ROOT/'scripts/r05a8_receipt.py')
assert spec is not None and spec.loader is not None
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
M=ROOT/'docs/r05a9-evidence.json';F=ROOT/'tests/fixtures/r05a9-owned-captures.json';D=ROOT/'docs/r05a9-isolated-receipt-contract.md'
class CampaignTests(unittest.TestCase):
 def test_valid_fresh_campaign_accepted(self):
  m.validate_artifacts(json.loads(M.read_text()),F.read_bytes(),D.read_text(),ROOT)
 def test_observed_q6_direct_detail_regression(self):
  f=json.loads(F.read_text());self.assertEqual(m.compare_receipt(f['sent'],f['receipt-detail'],902),{'matches':True,'fractional_q6_stress_observed':True})
 def test_negative_lookup_not_absence_regression(self):
  f=json.loads(F.read_text());self.assertEqual(m.assess_lookup(f['receipt-lookup'],f['sent']['reference'],f['sent']['idVendor'],f['receipt-detail'],True),'HOLD_NO_REPOST')
 def test_cli_refuses_false_promotions_and_ledger_scope_mutations(self):
  original=json.loads(M.read_text())
  cases=[('historical-gap',('limits','historical_gap'),'REPAIRED'),('new-budget',('authorization','new_order_explicitly_authorized'),False),('q6',('internal_source','received_quantity'),'0.123450'),('source-ownership',('authorization','existing_owned_vendor_material_only'),False),('history-zero',('authorization','internal_history_zero'),False),('stock-q6',('limits','stock_precision'),'EXACT_Q6'),('lookup-positive',('lookup','positive'),True),('empty-absence',('lookup','empty_proves_absence'),True),('page-full',('lookup','limit'),1),('per-order',('limits','erp_per_order_residual'),'KNOWN'),('native-link',('limits','native_link'),True),('runtime',('limits','runtime'),True),('replenish',('limits','cap_replenishment'),True),('redaction',('redaction',),'auth identifiers included'),('chronology',('ledger',17,'intent_utc'),'2099-01-01T00:00:00Z'),('caps',('authorization','caps','receipt_posts'),2),('calls',('counts','business_http_sent'),22)]
  with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as td:
   path=Path(td)/'matrix.json'
   for label,keys,value in cases:
    bad=copy.deepcopy(original);target=bad
    for key in keys[:-1]:target=target[key]
    target[keys[-1]]=value;path.write_text(json.dumps(bad))
    with self.subTest(label=label):
     p=subprocess.run([sys.executable,'-I',str(ROOT/'scripts/r05a8_receipt.py'),'--matrix',str(path),'--fixtures',str(F),'--doc',str(D)],capture_output=True,text=True)
     self.assertEqual(p.returncode,2,p.stdout+p.stderr)
 def test_doc_boundaries_fail_closed(self):
  for token in ['UNPROVEN_GET_ONLY_HELD','OPEN_NOT_REPAIRED','D93_DISTINCT_OWNER_GRANT','D90_NO_REPLENISHMENT','FULL_ARCHITECTURE_FALSE','Stock precision discrepancy']:
   with self.subTest(token=token),self.assertRaises(ValueError):m.validate_artifacts(json.loads(M.read_text()),F.read_bytes(),D.read_text().replace(token,''),ROOT)
 def test_projection_uses_aliases_not_live_config_ids(self):
  f=json.loads(F.read_text())
  def visit(value):
   if isinstance(value,dict):
    for key,item in value.items():
     if key=='idNumerator':self.assertEqual(item,71)
     if key=='docNumber':self.assertIn(item,{'','owned-order-number','owned-receipt-number'})
     visit(item)
   elif isinstance(value,list):
    for item in value:visit(item)
  visit(f)
 def test_finite_impact_and_workflow(self):
  s=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py');assert s and s.loader
  impact=importlib.util.module_from_spec(s);s.loader.exec_module(impact)
  files={'docs/r05a9-evidence.json','docs/r05a9-isolated-receipt-contract.md','tests/fixtures/r05a9-owned-captures.json','scripts/test-r05a9-evidence.py'}
  for file in files:
   with self.subTest(file=file):self.assertTrue(impact.selection({file})['r05a8_offline'])
  selected=impact.selection(files|{'scripts/r05a8_receipt.py','scripts/select-ci-impact.py','.github/workflows/ci.yml','docs/productization-plan.md','docs/productization-backlog.json','docs/r06-recovery-runbook.md'})
  for key,value in selected.items():
   if key not in {'r05a8_offline','r06_offline','changed_paths'}:self.assertFalse(value,key)
  with self.assertRaises(ValueError):impact.selection(files|{'scripts/r05a9_unknown.py'})
  mixed=impact.selection(files|{'src/Enginia360.Api/Program.cs'});self.assertTrue(mixed['browser']);self.assertTrue(mixed['migrations'])
  workflow=(ROOT/'.github/workflows/ci.yml').read_text();block=workflow.split('  affected-r05a8-offline:')[1].split('\n  affected-r05a7-offline:')[0]
  self.assertIn('python3 -I scripts/test-r05a9-evidence.py',block)
  for forbidden in ['secrets.','docker','curl','pip install']:self.assertNotIn(forbidden,block)
if __name__=='__main__':unittest.main()
