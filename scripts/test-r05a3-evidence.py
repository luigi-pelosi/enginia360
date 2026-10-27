#!/usr/bin/env python3
"""Offline tests of captured owned samples, not live provider compatibility."""
import argparse
import copy
import datetime
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('captures',ROOT/'scripts/r05a3_captures.py')
assert spec is not None and spec.loader is not None
captures=importlib.util.module_from_spec(spec);spec.loader.exec_module(captures)
FIXTURES=ROOT/'tests/fixtures/r05a3-owned-captures.json'
class CaptureTests(unittest.TestCase):
    def samples(self):return json.loads(FIXTURES.read_text())
    def test_provider_refusal_is_not_a_business_document(self):
        value=self.samples()['read-owned-order3'];value['errorCode']=2121003;value['responseCode']=500
        with self.assertRaises(ValueError):captures.decode(json.dumps(value))
    def test_duplicate_sku_line_identity_and_actual_nulls_survive(self):
        samples=self.samples();order=captures.decode(json.dumps(samples['read-owned-order3']))['document']
        self.assertEqual([r['idPos']for r in order['rows']],[1,2])
        self.assertEqual([r['quantity']for r in order['rows']],[1,2])
        self.assertEqual(len({r['idMaterial']for r in order['rows']}),1)
        receipt=captures.decode(json.dumps(samples['read-owned-linked-receipt2']))['document']
        self.assertEqual([r['idPos']for r in receipt['rows']],[1,3])
        self.assertIsNone(receipt['rows'][0]['idMaterial'])
        self.assertIsNone(receipt['rows'][1]['saleorderref'])
        self.assertIsNone(receipt['rows'][1]['saleorderposref'])
        self.assertEqual(receipt['rows'][1]['quantity'],2)
    def test_numeric_string_and_boolean_quantities_are_rejected(self):
        for bad in ('2',True,float('nan'),float('inf')):
            value=self.samples()['read-owned-linked-receipt2'];value['document']['rows'][1]['quantity']=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):captures.decode(json.dumps(value))
    def test_same_sku_cannot_replace_distinct_line_ids(self):
        value=self.samples()['read-owned-order3'];value['document']['rows'][1]['idPos']=1
        with self.assertRaises(ValueError):captures.decode(json.dumps(value))
    def test_stock_captured_sequence_not_inferred_from_empty_rows(self):
        samples=self.samples()
        for name,expected in [('stock-after-orderreport',(0,0,3)),('stock-after-receiptreport',(2,2,1)),('stock-after-invoice',(1,1,1))]:
            row=captures.decode(json.dumps(samples[name]))['stockReports'][0]
            self.assertEqual(tuple(row[k]for k in ('quantity','availableQty','orderedToSuppliersQty')),expected)
        self.assertEqual(samples['read-owned-order-after-receipt']['document']['docStatus'],'GOOD_PARTIAL_RECEIVED')
        self.assertEqual([r['docposstatus']for r in samples['read-owned-order-after-receipt']['document']['rows']],['CREATED','GOOD_RECEIVED'])
    def test_unsupported_shapes_are_rejected(self):
        for value in ({'responseCode':200,'errorCode':0},[],{'responseCode':200,'errorCode':0,'document':None}):
            with self.subTest(value=value),self.assertRaises(ValueError):captures.decode(json.dumps(value))
MATRIX=ROOT/'docs/r05a3-evidence.json'
NO_MUTATIONS=False
class EvidenceTests(unittest.TestCase):
    def matrix(self):return json.loads(MATRIX.read_text())
    def test_current_decision_guards_accept_authorized_D84(self):
        for command in (['scripts/test-c00-consistency.py'],['scripts/test-r04-authority.py','--check'],['scripts/test-r05a2-evidence.py','--no-mutations']):
            with self.subTest(command=command):
                result=subprocess.run([sys.executable,'-I',*command],cwd=ROOT,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr[-1600:])
    def test_owner_assertion_not_independent_guarantee_and_no_promotion(self):
        d=self.matrix()
        self.assertEqual(d['increment'],'R05.a.3');self.assertEqual(d['decision'],'D84')
        self.assertEqual(d['isolation']['quote'],'Confermo che la sandbox è scollegata da altri sistemi automatici, webhook ed esportazioni.')
        self.assertEqual(d['isolation']['class'],'owner-assertion')
        self.assertEqual(d['isolation']['gate'],'RESOLVED_BY_OWNER_ASSERTION')
        self.assertIs(d['isolation']['independent_technical_verification'],False)
        self.assertTrue(d['claims']);self.assertTrue(all(v is False for v in d['claims'].values()))
        inv=d['scenarios']['D79-persistent-sales-invoice-draft']
        self.assertEqual(inv['outcome'],'NOT_ESTABLISHED');self.assertEqual(inv['stock_effect'],-1)
        self.assertEqual(inv['fiscal_finality'],'NOT_INFERRED');self.assertFalse(inv['send_invoked'])
        recovery=d['scenarios']['lost-response-recovery']
        self.assertEqual(recovery['outcome'],'BLOCKED_PROVIDER_ERROR_UNCERTAIN_HOLD')
        self.assertEqual(recovery['replays'],0);self.assertFalse(recovery['successful_single_effect_proved'])
    def test_programmatic_owned_ledger_counts_and_source_hashes(self):
        d=self.matrix();ledger=d['ledger'];counts=ledger['counts']
        self.assertEqual(counts['write_intents'],len(ledger['writes']))
        self.assertEqual(counts['verified_objects'],len(ledger['objects']))
        self.assertEqual(counts['verified_business_aggregates'],6)
        self.assertEqual(counts['verified_implicit_contacts'],2)
        self.assertEqual(counts['verified_objects'],8)
        self.assertEqual(counts['uncertain_write_paths'],sum(w['state']=='UNCERTAIN'for w in ledger['writes']))
        self.assertEqual(counts['uncertain_write_paths'],1)
        self.assertEqual(len({o['owned_alias']for o in ledger['objects']}),8)
        self.assertEqual(len(d['observations']),d['acquisition_counts']['business_api_requests'])
        self.assertEqual(sum(o['method']=='POST'for o in d['observations']),6)
        for o in d['observations']:
            self.assertRegex(o['source_sha256'],r'^[a-f0-9]{64}$');self.assertRegex(o['shape_sha256'],r'^[a-f0-9]{64}$')
            self.assertNotEqual(o['source_sha256'],o['shape_sha256'])
            self.assertEqual(datetime.datetime.fromisoformat(o['utc']).utcoffset(),datetime.timedelta())
            self.assertIn('endpoint_template',o)
            self.assertNotRegex(o['endpoint_template'],r'/(?:sales|purchases)/\d+|/contacts/\d+|/vendors/\d+|/customers/\d+')
    def test_sanitized_capture_provenance_and_immutable_history(self):
        d=self.matrix();samples=json.loads(FIXTURES.read_text())
        self.assertEqual(set(samples),{c['name']for c in d['captures']})
        for c in d['captures']:
            value=samples[c['name']];captures.decode(json.dumps(value))
            digest=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            self.assertEqual(digest,c['sanitized_sha256']);self.assertNotEqual(digest,c['source_sha256'])
            self.assertEqual(c['source_sha256'],next(o['source_sha256']for o in d['observations']if o['seq']==c['source_seq']))
        historical=(ROOT/'docs/r05a2-evidence.json').read_bytes()
        self.assertEqual(hashlib.sha256(historical).hexdigest(),d['historical_r05a2_matrix_sha256'])
        register=(ROOT/'docs/foundation/01-glossary-and-domain-boundaries.md').read_bytes()
        start=register.index('### D1 —'.encode());prefix=register[start:start+d['historical_decisions_d1_d83_bytes']]
        self.assertEqual(hashlib.sha256(prefix).hexdigest(),d['historical_decisions_d1_d83_sha256'])
        ids=list(map(int,re.findall(r'^### D(\d+) —',register.decode(),re.M)))
        self.assertEqual(sorted(ids),list(range(1,91)))
    def test_cli_mutations_reject_false_promotion(self):
        if NO_MUTATIONS:return
        mutations=[lambda d:d['claims'].__setitem__('positive_adapter',True),
                   lambda d:d['isolation'].__setitem__('independent_technical_verification',True),
                   lambda d:d['ledger']['counts'].__setitem__('verified_objects',0),
                   lambda d:d['scenarios']['lost-response-recovery'].__setitem__('successful_single_effect_proved',True),
                   lambda d:d['scenarios']['D79-persistent-sales-invoice-draft'].__setitem__('outcome','PROVED'),
                   lambda d:d['observations'][0].__setitem__('source_sha256','')]
        with tempfile.TemporaryDirectory(prefix='r05a3-',dir=os.environ.get('TMPDIR',tempfile.gettempdir())) as temp:
            for mutate in mutations:
                d=self.matrix();mutate(d);path=Path(temp)/'matrix.json';path.write_text(json.dumps(d))
                result=subprocess.run([sys.executable,'-I',__file__,'--matrix',str(path),'--no-mutations'],cwd=ROOT,capture_output=True,text=True,timeout=60)
                self.assertEqual(result.returncode,1);self.assertIn('FAIL:',result.stderr);self.assertNotIn('ERROR:',result.stderr)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--matrix',type=Path,default=MATRIX);parser.add_argument('--no-mutations',action='store_true')
    args,remaining=parser.parse_known_args();MATRIX=args.matrix;NO_MUTATIONS=args.no_mutations
    unittest.main(argv=[sys.argv[0],*remaining])
