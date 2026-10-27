#!/usr/bin/env python3
"""Offline tests of R05.a.4 owned captures and recovery claims, not live provider compatibility."""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
recovery = load('r05a4_recovery', 'scripts/r05a4_recovery.py')
captures = load('r05a3_captures', 'scripts/r05a3_captures.py')
FIXTURES = ROOT / 'tests/fixtures/r05a4-owned-captures.json'
MATRIX = ROOT / 'docs/r05a4-evidence.json'
NO_MUTATIONS = False
def good(**changes):
    value = {'precommitted_key': 'E360-SB-R05A4-X-VENDOR-LOST', 'response_discarded': True, 'lookup_used_server_id': False,
             'lookup_total_count': 1, 'lookup_exact_matches': 1, 'oracle_read_after_lookup': True, 'oracle_id_equals_lookup_id': True}
    value.update(changes)
    return value
class DecoderTests(unittest.TestCase):
    def samples(self): return json.loads(FIXTURES.read_text())
    def test_vendor_lookup_requires_success_envelope_and_integer_metadata(self):
        value = self.samples()['vendor-lookup-normal']
        self.assertEqual(recovery.decode_lookup(json.dumps(value), 'vendors')['metadata']['totalCount'], 1)
        bad = [dict(value, responseCode=500, errorCode=2121003), dict(value, metadata=dict(value['metadata'], totalCount='1')),
               dict(value, metadata=dict(value['metadata'], totalCount=True)), dict(value, vendors={})]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError): recovery.decode_lookup(json.dumps(item), 'vendors')
    def test_vendor_lookup_rejects_missing_name_and_duplicate_identity(self):
        value = self.samples()['vendor-lookup-recovered-lost']
        nameless = json.loads(json.dumps(value)); del nameless['vendors'][0]['contact']['name']
        duplicate = json.loads(json.dumps(value)); duplicate['vendors'].append(json.loads(json.dumps(duplicate['vendors'][0])))
        for item in (nameless, duplicate):
            with self.subTest(item=item), self.assertRaises(ValueError): recovery.decode_lookup(json.dumps(item), 'vendors')
    def test_empty_header_lookup_is_valid_but_not_absence(self):
        value = recovery.decode_lookup(json.dumps(self.samples()['order-correlation-lookup-empty']), 'documentsHeaders')
        self.assertEqual(value['documentsHeaders'], []); self.assertEqual(value['metadata']['totalCount'], 0)
    def test_existing_decoder_still_reads_order_and_stock_ordered_change(self):
        s = self.samples()
        order = captures.decode(json.dumps(s['order-detail-lost-response']))['document']
        self.assertEqual([r['quantity'] for r in order['rows']], [1.0]); self.assertIsNone(order['rows'][0]['saleorderref'])
        before = captures.decode(json.dumps(s['stock-before-lost-order']))['stockReports'][0]
        after = captures.decode(json.dumps(s['stock-after-lost-order']))['stockReports'][0]
        self.assertEqual((before['orderedToSuppliersQty'], after['orderedToSuppliersQty']), (1.0, 2.0))
        self.assertEqual(before['quantity'], after['quantity'])
class RecoveryAssessmentTests(unittest.TestCase):
    def test_exact_unique_pre_recorded_match_after_discard_is_recovered(self):
        self.assertEqual(recovery.assess_recovery(good()), 'RECOVERED')
    def test_empty_lookup_holds_and_is_never_absence(self):
        self.assertEqual(recovery.assess_recovery(good(lookup_total_count=0, lookup_exact_matches=0, oracle_id_equals_lookup_id=None)), 'HOLD_UNCERTAIN_NOT_ABSENCE')
    def test_invalid_recovery_records_are_rejected(self):
        for change in ({'lookup_exact_matches': 2}, {'lookup_used_server_id': True}, {'response_discarded': False},
                       {'oracle_read_after_lookup': False}, {'oracle_id_equals_lookup_id': False}, {'precommitted_key': ''},
                       {'lookup_total_count': '1'}):
            with self.subTest(change=change), self.assertRaises(ValueError): recovery.assess_recovery(good(**change))
class EvidenceTests(unittest.TestCase):
    def matrix(self): return json.loads(MATRIX.read_text())
    def test_claims_stay_false_and_scenarios_are_limited(self):
        d = self.matrix(); self.assertEqual(d['increment'], 'R05.a.4'); self.assertIsNone(d['new_decision'])
        self.assertTrue(d['claims']); self.assertTrue(all(v is False for v in d['claims'].values()))
        v = d['scenarios']['vendor-lost-success-recovery']
        self.assertEqual(v['outcome'], 'RECOVERED_BY_PRE_RECORDED_NAME'); self.assertTrue(v['prerecorded_name_only'])
        self.assertTrue(v['lookup_before_oracle']); self.assertEqual(v['replays'], 0)
        self.assertEqual(recovery.assess_recovery(good(lookup_total_count=v['lookup']['totalCount'], lookup_exact_matches=v['lookup']['exact_matches'])), 'RECOVERED')
        o = d['scenarios']['order-lost-success-recovery']
        self.assertEqual(o['freeText_exact_correlation_lookup_matches'], 0); self.assertEqual(o['docdate_window_lookup_matches'], 0)
        self.assertEqual(o['ordered_delta'], o['ordered_after'] - o['ordered_before']); self.assertEqual(o['replays'], 0)
        self.assertIn('ORACLE', o['outcome'])
        self.assertEqual(d['scenarios']['api-partial-source-selection']['mutations_performed'], 0)
        self.assertEqual(d['scenarios']['D79-persistent-sales-invoice-draft']['outcome'], 'NOT_ESTABLISHED')
        self.assertEqual(d['scenarios']['D79-persistent-sales-invoice-draft']['additional_invoices_created'], 0)
    def test_programmatic_counts_hashes_and_historical_files(self):
        d = self.matrix(); ledger = d['ledger']; counts = ledger['counts']
        self.assertEqual(counts['write_intents'], len(ledger['writes'])); self.assertEqual(counts['verified_objects'], len(ledger['objects']))
        self.assertEqual(counts['verified_business_aggregates'], sum(o['kind'] != 'contacts' for o in ledger['objects']))
        self.assertEqual(counts['verified_embedded_contacts'], sum(o['kind'] == 'contacts' for o in ledger['objects']))
        self.assertEqual(len({o['owned_alias'] for o in ledger['objects']}), len(ledger['objects']))
        self.assertEqual(d['run']['business_requests'], len(d['observations']))
        self.assertEqual(d['run']['post_requests'], sum(o['method'] == 'POST' for o in d['observations']))
        self.assertLessEqual(d['run']['post_requests'], d['run']['caps']['POST']); self.assertLessEqual(len(d['observations']), d['run']['caps']['business_requests'])
        for o in d['observations']:
            self.assertRegex(o['source_sha256'], r'^[a-f0-9]{64}$'); self.assertRegex(o['shape_sha256'], r'^[a-f0-9]{64}$')
            self.assertNotRegex(o['endpoint_template'], r'/(?:vendors|orders)/\d+')
        for name, key in (('docs/r05a3-evidence.json', 'r05a3_matrix_sha256'), ('tests/fixtures/r05a3-owned-captures.json', 'r05a3_fixtures_sha256')):
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), d['historical'][key])
    def test_sanitized_capture_hashes_and_schema_pointers(self):
        d = self.matrix(); samples = json.loads(FIXTURES.read_text())
        self.assertEqual(set(samples), {c['name'] for c in d['captures']})
        for c in d['captures']:
            digest = hashlib.sha256(json.dumps(samples[c['name']], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(digest, c['sanitized_sha256']); self.assertNotEqual(digest, c['source_sha256'])
            self.assertEqual(c['source_sha256'], next(o['source_sha256'] for o in d['observations'] if o['seq'] == c['source_seq']))
        for claim in d['official_contract']['claims']:
            self.assertEqual(hashlib.sha256(json.dumps(claim['extract'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(), claim['extract_sha256'])
        swagger = os.environ.get('R05A4_SWAGGER')
        if swagger and Path(swagger).exists():
            raw = Path(swagger).read_bytes(); self.assertEqual(hashlib.sha256(raw).hexdigest(), d['official_contract']['swagger_sha256'])
            doc = json.loads(raw)
            for claim in d['official_contract']['claims']:
                value = doc
                for part in claim['pointer'][2:].split('/'):
                    part = part.replace('~1', '/').replace('~0', '~'); value = value[int(part)] if isinstance(value, list) else value[part]
                self.assertEqual(value, claim['extract'])
    def test_cli_mutations_reject_false_promotion(self):
        if NO_MUTATIONS: return
        mutations = [lambda d: d['claims'].__setitem__('server_idempotency', True),
                     lambda d: d['claims'].__setitem__('persistent_draft_proved', True),
                     lambda d: d['ledger']['counts'].__setitem__('verified_objects', 0),
                     lambda d: d['scenarios']['order-lost-success-recovery'].__setitem__('freeText_exact_correlation_lookup_matches', 1),
                     lambda d: d['scenarios']['vendor-lost-success-recovery'].__setitem__('lookup_before_oracle', False),
                     lambda d: d['scenarios']['D79-persistent-sales-invoice-draft'].__setitem__('outcome', 'PROVED'),
                     lambda d: d['observations'][0].__setitem__('source_sha256', '')]
        with tempfile.TemporaryDirectory(prefix='r05a4-', dir=os.environ.get('TMPDIR', tempfile.gettempdir())) as temp:
            for mutate in mutations:
                d = self.matrix(); mutate(d); path = Path(temp) / 'matrix.json'; path.write_text(json.dumps(d))
                result = subprocess.run([sys.executable, '-I', __file__, '--matrix', str(path), '--no-mutations'], cwd=ROOT, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 1); self.assertIn('FAIL:', result.stderr); self.assertNotIn('ERROR:', result.stderr)
if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--matrix', type=Path, default=MATRIX); parser.add_argument('--no-mutations', action='store_true')
    args, remaining = parser.parse_known_args(); MATRIX = args.matrix; NO_MUTATIONS = args.no_mutations
    unittest.main(argv=[sys.argv[0], *remaining])
