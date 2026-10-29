#!/usr/bin/env python3
"""Offline evidence tests. Synthetic mutations test guards, NOT provider behaviour."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile
import os
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('receipt',ROOT/'scripts/r05a8_receipt.py')
assert spec is not None and spec.loader is not None
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
def fixtures():return json.loads((ROOT/'tests/fixtures/r05a8-owned-captures.json').read_text())
class DecoderTests(unittest.TestCase):
    def test_real_receipt_detail_preserves_identity_fields_and_null_links(self):
        v=r.decode_receipt(json.dumps(fixtures()['api-detail']))
        self.assertEqual(v['document']['id'],301)
        self.assertEqual(v['document']['rows'][0]['price'],1.0)
        self.assertIsNone(v['document']['rows'][0]['saleorderref'])
    def test_refuses_ack_order_missing_fields_invalid_q6_and_duplicate_positions(self):
        sample=fixtures()['api-detail']
        bad=[fixtures()['api-ack'],fixtures()['order-before']]
        for field in ['id','idDocumentType','idVendor','reference','idBu','idNumerator']:
            v=copy.deepcopy(sample);v['document'].pop(field);bad.append(v)
        for field in ['idPos','idPosType','idMaterial','quantity','price','description','idStorage','idVat']:
            v=copy.deepcopy(sample);v['document']['rows'][0].pop(field);bad.append(v)
        for field,values in {'price':[True,'1',float('nan'),float('inf'),1.0000001], 'quantity':[False,'1',0,-1,float('nan'),1.0000001], 'idPos':[True,'1'], 'idPosType':[True,'1']}.items():
            for value in values:
                v=copy.deepcopy(sample);v['document']['rows'][0][field]=value;bad.append(v)
        for field,value in [('id',True),('idVendor',1),('idDocumentType',False),('reference',None),('idBu',None),('idNumerator',True)]:
            v=copy.deepcopy(sample);v['document'][field]=value;bad.append(v)
        v=copy.deepcopy(sample);v['document']['rows'].append(copy.deepcopy(v['document']['rows'][0]));bad.append(v)
        for v in bad:
            with self.subTest(value_kind=type(v).__name__),self.assertRaises(ValueError):r.decode_receipt(json.dumps(v))
class ComparisonTests(unittest.TestCase):
    def test_retained_exact_row_fields_match_but_fractional_q6_is_not_observed(self):
        f=fixtures();result=r.compare_receipt(f['sent-comparison'],f['api-detail'],f['api-ack']['idDocument'])
        self.assertTrue(result['matches']);self.assertFalse(result['fractional_q6_stress_observed'])
    def test_every_identity_and_row_mismatch_refuses_confirmation(self):
        f=fixtures()
        for field,value in [('id',999),('idDocumentType',2),('idVendor','other-vendor'),('reference','other-ref'),('idBu','other-bu'),('idNumerator',999)]:
            v=copy.deepcopy(f['api-detail']);v['document'][field]=value
            with self.subTest(field=field):self.assertFalse(r.compare_receipt(f['sent-comparison'],v,301)['matches'])
        for field,value in [('price',1.000001),('quantity',0.5),('idMaterial','other'),('idStorage','other'),('description','other'),('idVat','other'),('idPosType',5)]:
            v=copy.deepcopy(f['api-detail']);v['document']['rows'][0][field]=value
            with self.subTest(field=field):self.assertFalse(r.compare_receipt(f['sent-comparison'],v,301)['matches'])
    def test_missing_detail_never_completes_from_ack(self):
        f=fixtures();self.assertFalse(r.compare_receipt(f['sent-comparison'],f['api-ack'],301)['matches'])

class LookupTests(unittest.TestCase):
    def test_historical_ui_lookup_is_not_precommitted_recovery(self):
        f=fixtures();d=f['ui-linked-detail']['document']
        self.assertEqual(r.assess_lookup(f['ui-ordinary-list'],d['reference'],d['idVendor'],f['ui-linked-detail'],False),'ORDINARY_MATCH_NOT_RECOVERY')
    def test_synthetic_precommit_mutation_exercises_bounded_match_only(self):
        f=fixtures();d=f['ui-linked-detail']['document']
        self.assertEqual(r.assess_lookup(f['ui-ordinary-list'],d['reference'],d['idVendor'],f['ui-linked-detail'],True),'BOUNDED_MATCH_NOT_PROVIDER_GUARANTEE')
    def test_empty_full_duplicate_wrong_detail_and_errors_hold_never_repost(self):
        f=fixtures();page=f['ui-ordinary-list'];d=f['ui-linked-detail']['document'];bad=[]
        v=copy.deepcopy(page);v['documentsHeaders']=[];bad.append((v,f['ui-linked-detail']))
        v=copy.deepcopy(page);v['documentsHeaders']*=5;bad.append((v,f['ui-linked-detail']))
        v=copy.deepcopy(page);v['documentsHeaders']*=2;bad.append((v,f['ui-linked-detail']))
        v=copy.deepcopy(page);v['metadata']['limit']=1;bad.append((v,f['ui-linked-detail']))
        v=copy.deepcopy(page);v['metadata']['offset']=5;bad.append((v,f['ui-linked-detail']))
        v=copy.deepcopy(page);v['responseCode']=500;bad.append((v,f['ui-linked-detail']))
        v=copy.deepcopy(page);v['errorCode']=9;bad.append((v,f['ui-linked-detail']))
        for key in ['id','idDocumentType','reference','idVendor','idBu','idNumerator']:
            v=copy.deepcopy(f['ui-linked-detail']);v['document'][key]=None;bad.append((page,v))
        bad.extend([(page,None),(None,None)])
        for page,detail in bad:
            with self.subTest():self.assertEqual(r.assess_lookup(page,d['reference'],d['idVendor'],detail,True),'HOLD_NO_REPOST')

class EvidenceTests(unittest.TestCase):
    def cli(self,matrix=None,captures=None,doc=None):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as tmp:
            p=Path(tmp);m=p/'matrix.json';f=p/'fixtures.json';d=p/'doc.md'
            m.write_text(json.dumps(matrix if matrix is not None else json.loads((ROOT/'docs/r05a8-evidence.json').read_text())))
            # Preserve exact fixture bytes on positive path; hash commits the original minimized artifact.
            f.write_text(json.dumps(captures) if captures is not None else (ROOT/'tests/fixtures/r05a8-owned-captures.json').read_text())
            d.write_text(doc if doc is not None else (ROOT/'docs/r05a8-sandbox-receipt-contract.md').read_text())
            return subprocess.run([sys.executable,'-I',str(ROOT/'scripts/r05a8_receipt.py'),'--matrix',str(m),'--fixtures',str(f),'--doc',str(d)],text=True,capture_output=True)
    def test_real_artifacts_are_consistent_not_complete(self):
        p=self.cli();self.assertEqual(p.returncode,0,p.stderr);self.assertIn('GET_ONLY_HELD',p.stdout);self.assertNotIn('COMPLETE',p.stdout)
    def test_cli_rejects_false_completion_and_guardrail_promotions(self):
        original=json.loads((ROOT/'docs/r05a8-evidence.json').read_text())
        for claim in original['claims']:
            m=copy.deepcopy(original);m['claims'][claim]=True
            with self.subTest(claim=claim):
                p=self.cli(matrix=m);self.assertEqual(p.returncode,2,p.stdout+p.stderr);self.assertNotIn('Traceback',p.stderr)
    def test_cli_rejects_counts_chronology_ownership_provenance_and_policy_changes(self):
        original=json.loads((ROOT/'docs/r05a8-evidence.json').read_text());bad=[]
        for k in ['business_requests','persisted_receipt_posts','simulation_posts','objects_created']:
            m=copy.deepcopy(original);m['new_run'][k]=1;bad.append(m)
        for k in original['new_run']['caps']:
            m=copy.deepcopy(original);m['new_run']['caps'][k]+=1;bad.append(m)
        for key,value in [('seq',999),('acquired_utc','2026-10-27T12:05:00+00:00'),('source_sha256','0'*64),('projection_sha256','0'*64),('ownership','arbitrary-preexisting-object'),('pointer_types',{})]:
            m=copy.deepcopy(original);m['provenance'][0][key]=value;bad.append(m)
        m=copy.deepcopy(original);m['provenance'].append(copy.deepcopy(m['provenance'][0]));bad.append(m)
        m=copy.deepcopy(original);m['provenance'].pop();bad.append(m)
        for k,value in [('recovery','COMPLETED'),('per_order_residual',5),('request_reference_shared_with_source_order',False),('stock_ordered_after',5)]:
            m=copy.deepcopy(original);m['observations'][k]=value;bad.append(m)
        m=copy.deepcopy(original);m['receipt_policy']={'overreceipt_allowed':True};bad.append(m)
        m=copy.deepcopy(original);m['historical_ledgers']['R05a5']='0'*64;bad.append(m)
        path=next(iter(original['historical_files']));m=copy.deepcopy(original);m['historical_files'][path]='0'*64;bad.append(m)
        for m in bad:
            with self.subTest():
                p=self.cli(matrix=m);self.assertEqual(p.returncode,2,p.stdout+p.stderr);self.assertNotIn('Traceback',p.stderr)
    def test_cli_rejects_fixture_fabrication_and_private_field_injection(self):
        for key in ['access_token','companyName','vendorData','destEmail','client_id']:
            f=fixtures();f['api-detail']['document'][key]='synthetic-forbidden-sentinel'
            with self.subTest(key=key):
                p=self.cli(captures=f);self.assertEqual(p.returncode,2,p.stdout+p.stderr)
        f=fixtures();f['api-detail']['document']['rows'][0]['price']=12.345678
        p=self.cli(captures=f);self.assertEqual(p.returncode,2,p.stdout+p.stderr)
    def test_cli_refuses_boundary_removal_and_false_document_promotions(self):
        original=(ROOT/'docs/r05a8-sandbox-receipt-contract.md').read_text()
        for token in ['READ_ONLY_REPROJECTION','GET_ONLY_HELD','FRACTIONAL_Q6_UNPROVEN','ORDINARY_LOOKUP_NOT_RECOVERY','PER_ORDER_RESIDUAL_UNKNOWN','D82_ERP_ONLY','D86_INTERNAL_SOURCE_LINK','D93_DISTINCT_OWNER_GRANT','D90_NO_REPLENISHMENT','D91_FROZEN_PRICE','D92_NO_EXPANSION','R04_R05_OPEN','NO_RUNTIME','NO_READINESS','FULL_ARCHITECTURE_FALSE','PARTIAL_3_2_APPROVED','OTHER_QUANTITY_OVERRECEIPT_WAREHOUSE_PRICING_FISCAL_UNDECIDED']:
            with self.subTest(token=token):
                p=self.cli(doc=original.replace(token,'REMOVED',1));self.assertEqual(p.returncode,2,p.stdout+p.stderr)
        for claim in ['R04_COMPLETE=true','R05_COMPLETE=true','RECEIPT_Q6_PROVEN=true','RECOVERY_PRECOMMITTED=true','LOCAL_STOCK_WRITER=true']:
            with self.subTest(claim=claim):self.assertEqual(self.cli(doc=original+'\n'+claim).returncode,2)

class AdditionalGuardTests(unittest.TestCase):
    def test_matrix_redaction_metadata_cannot_carry_extra_private_values(self):
        original=json.loads((ROOT/'docs/r05a8-evidence.json').read_text())
        for key in ['access_token','client_id','username','cid']:
            m=copy.deepcopy(original);m['redaction'][key]='synthetic-forbidden-sentinel'
            with self.subTest(key=key):self.assertEqual(EvidenceTests().cli(matrix=m).returncode,2)
    def test_q6_synthetic_mutation_is_not_a_new_provider_observation(self):
        f=fixtures();sent=f['sent-comparison'];detail=f['api-detail']
        sent['rows'][0]['price']=12.345678;detail['document']['rows'][0]['price']=12.345678
        self.assertEqual(r.compare_receipt(sent,detail,301),{'matches':True,'fractional_q6_stress_observed':True})
        # Original immutable owned capture still has price1, not the synthetic value.
        self.assertEqual(fixtures()['api-detail']['document']['rows'][0]['price'],1.0)

if __name__=='__main__':unittest.main()
