#!/usr/bin/env python3
"""Offline tests of R05.a.5 owned observations and closure verdicts, not live provider compatibility."""
import argparse
import copy
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
closure = load('r05a5_closure', 'scripts/r05a5_closure.py')
recovery = load('r05a4_recovery', 'scripts/r05a4_recovery.py')
captures = load('r05a3_captures', 'scripts/r05a3_captures.py')
FIXTURES = ROOT / 'tests/fixtures/r05a5-owned-captures.json'
MATRIX = ROOT / 'docs/r05a5-evidence.json'
NO_MUTATIONS = False
STOCK = {'quantity': 1.0, 'orderedToSuppliersQty': 2.0}
def sim(**changes):
    value = {'http_status': 200, 'business_error': 0, 'preview_document_id': None, 'preview_doc_number': '',
             'latest_id_before': 201, 'latest_id_after': 201, 'prefix_matches_after': 0,
             'stock_before': dict(STOCK), 'stock_after': dict(STOCK)}
    value.update(changes)
    return value
def lookups(**changes):
    value = {'precommitted_before_write': True, 'oracle_read_after_conclusion': True, 'oracle_id_equals_lookup_id': True, 'response_discarded': True,
             'lookups': [{'label': 'reference', 'totalCount': 0, 'exact_matches': 0, 'kind': 'freeText-reference'},
                         {'label': 'contact', 'totalCount': 0, 'exact_matches': 0, 'kind': 'idContact'},
                         {'label': 'vendor-name', 'totalCount': 1, 'exact_matches': 1, 'kind': 'freeText-vendor-name'}],
             'recovery_key': 'vendor-name'}
    value.update(changes)
    return value
def link(**changes):
    value = {'sent_rows': [{'saleorderref': 7, 'saleorderposref': 2, 'quantity': 1.0}],
             'receipt_rows': [{'saleorderref': None, 'saleorderposref': None, 'materialmovementref': None, 'quantity': 1.0}],
             'order_row_status_before': ['CREATED', 'CREATED'], 'order_row_status_after': ['CREATED', 'CREATED'],
             'order_status_before': 'CREATED', 'order_status_after': 'CREATED',
             'stock_before': {'quantity': 1.0, 'orderedToSuppliersQty': 6.0}, 'stock_after': {'quantity': 2.0, 'orderedToSuppliersQty': 6.0}}
    value.update(changes)
    return value
class SimulationTests(unittest.TestCase):
    def test_preview_without_persistence_is_non_persistent(self):
        self.assertEqual(closure.assess_simulation(sim()), 'NON_PERSISTENT_PREVIEW')
    def test_any_persistence_signal_stops_the_path(self):
        for change in ({'preview_document_id': 202}, {'preview_doc_number': '1660'}, {'latest_id_after': 202}, {'prefix_matches_after': 1},
                       {'stock_after': {'quantity': 0.0, 'orderedToSuppliersQty': 2.0}}):
            with self.subTest(change=change): self.assertEqual(closure.assess_simulation(sim(**change)), 'PERSISTED_OR_STOCK_CHANGED_STOP')
    def test_invalid_records_are_rejected_not_guessed(self):
        for change in ({'http_status': 500}, {'business_error': 1}, {'latest_id_before': '201'}, {'prefix_matches_after': True}, {'stock_after': {'quantity': 1.0}}):
            with self.subTest(change=change), self.assertRaises(ValueError): closure.assess_simulation(sim(**change))
class LookupTests(unittest.TestCase):
    def test_unique_precommitted_vendor_name_key_recovers_and_correlation_lookups_do_not(self):
        r = closure.assess_lookup_set(lookups())
        self.assertEqual(r['verdict'], 'RECOVERED_BY_PRECOMMITTED_KEY'); self.assertEqual(r['reliable'], ['vendor-name'])
        self.assertEqual(r['empty_not_absence'], ['reference', 'contact'])
    def test_ambiguous_or_unprepared_recovery_holds_or_is_rejected(self):
        two = lookups(); two['lookups'][2].update(totalCount=2, exact_matches=1)
        self.assertEqual(closure.assess_lookup_set(two)['verdict'], 'HOLD_AMBIGUOUS')
        none = lookups(lookups=[{'label': 'reference', 'totalCount': 0, 'exact_matches': 0, 'kind': 'freeText-reference'}], recovery_key='reference')
        self.assertEqual(closure.assess_lookup_set(none)['verdict'], 'HOLD_UNCERTAIN_NOT_ABSENCE')
        for change in ({'precommitted_before_write': False}, {'oracle_read_after_conclusion': False}, {'oracle_id_equals_lookup_id': False}, {'recovery_key': 'unknown'}):
            with self.subTest(change=change), self.assertRaises(ValueError): closure.assess_lookup_set(lookups(**change))
class ReceiptLinkTests(unittest.TestCase):
    def test_declared_link_fields_accepted_but_not_persisted(self):
        self.assertEqual(closure.assess_receipt_link(link()), 'LINK_NOT_PERSISTED_STANDALONE_RECEIPT')
    def test_persisted_link_or_source_state_change_is_detected(self):
        self.assertEqual(closure.assess_receipt_link(link(receipt_rows=[{'saleorderref': 7, 'saleorderposref': 2, 'materialmovementref': None, 'quantity': 1.0}])), 'LINK_PERSISTED')
        self.assertEqual(closure.assess_receipt_link(link(order_row_status_after=['CREATED', 'GOOD_PARTIAL_RECEIVED'])), 'LINK_PERSISTED')
    def test_invalid_records_are_rejected(self):
        for change in ({'sent_rows': []}, {'receipt_rows': []}, {'stock_after': {'quantity': 2.0}}, {'order_status_after': 5}):
            with self.subTest(change=change), self.assertRaises(ValueError): closure.assess_receipt_link(link(**change))
class OrderHeaderDecoderTests(unittest.TestCase):
    def samples(self): return json.loads(FIXTURES.read_text())
    def test_header_lookup_with_integer_identities_decodes_and_counts_exact_reference(self):
        value = closure.decode_order_headers(json.dumps(self.samples()['order-lookup-day-window']))
        self.assertEqual(value['metadata']['totalCount'], 3); self.assertEqual(len(value['documentsHeaders']), 3)
        self.assertEqual(closure.exact_reference_matches(value, 'E360-SB-R05A5-20261027T115822Z-PO-LOOKUP'), 1)
    def test_header_lookup_rejects_bad_envelope_identity_and_metadata(self):
        good = self.samples()['order-lookup-vendor-name']
        def mutate(f):
            v = copy.deepcopy(good); f(v); return v
        bad = [mutate(lambda v: v.update(responseCode=500)), mutate(lambda v: v['documentsHeaders'][0].update(id='101')),
               mutate(lambda v: v['documentsHeaders'].append(copy.deepcopy(v['documentsHeaders'][0]))), mutate(lambda v: v['documentsHeaders'][0].pop('reference')),
               mutate(lambda v: v['metadata'].update(totalCount=True)), mutate(lambda v: v.update(documentsHeaders={}))]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError): closure.decode_order_headers(json.dumps(item))
    def test_empty_header_lookup_is_valid_and_zero_matches(self):
        value = closure.decode_order_headers(json.dumps(self.samples()['order-lookup-window-now-minus-1h-empty']))
        self.assertEqual(closure.exact_reference_matches(value, 'x'), 0)
class RegressionTests(unittest.TestCase):
    """Passing on first run: existing decoders are reused unchanged."""
    def samples(self): return json.loads(FIXTURES.read_text())
    def test_existing_decoders_read_owned_projections(self):
        s = self.samples()
        self.assertEqual(recovery.decode_lookup(json.dumps(s['order-lookup-window-now-minus-1h-empty']), 'documentsHeaders')['metadata']['totalCount'], 0)
        with self.assertRaises(ValueError): recovery.decode_lookup(json.dumps(s['order-lookup-vendor-name']), 'documentsHeaders')  # string-id decoder does not fit integer order ids
        self.assertEqual(len(captures.decode(json.dumps(s['orderB-after-receipt']))['document']['rows']), 2)
        self.assertEqual(captures.decode(json.dumps(s['stock-after-receipt']))['stockReports'][0]['quantity'], 2.0)
    def test_simulation_preview_is_not_decodable_as_persisted_document(self):
        with self.assertRaises(ValueError): captures.decode(json.dumps(self.samples()['invoice-simulation-preview']))
class EvidenceTests(unittest.TestCase):
    def matrix(self): return json.loads(MATRIX.read_text())
    def test_claims_false_and_verdicts_match_assessors(self):
        d = self.matrix(); self.assertEqual(d['increment'], 'R05.a.5'); self.assertIsNone(d['new_decision'])
        self.assertTrue(d['claims']); self.assertTrue(all(v is False for v in d['claims'].values()))
        p = d['points']
        def verdict(fn, record):
            try: return fn(record)
            except ValueError as error: self.fail('invalid recorded observation: %s' % error)
        self.assertEqual(p['D79-draft']['verdict'], 'PROVEN-NEGATIVE-FOR-TESTED-PATHS'); self.assertEqual(p['D79-draft']['additional_numbered_invoices'], 0)
        self.assertEqual(verdict(closure.assess_simulation, p['D79-draft']['simulation_record']), 'NON_PERSISTENT_PREVIEW')
        self.assertEqual(verdict(closure.assess_lookup_set, p['order-correlation-lookup']['record'])['verdict'], 'RECOVERED_BY_PRECOMMITTED_KEY')
        self.assertEqual(p['order-correlation-lookup']['verdict'], 'RESOLVED')
        self.assertEqual(verdict(closure.assess_receipt_link, p['partial-receipt-api']['record']), 'LINK_NOT_PERSISTED_STANDALONE_RECEIPT')
        self.assertEqual(p['partial-receipt-api']['verdict'], 'PROVEN-NEGATIVE')
    def test_programmatic_counts_and_hashes(self):
        d = self.matrix(); ledger = d['ledger']; counts = ledger['counts']
        self.assertEqual(counts['write_intents'], len(ledger['writes'])); self.assertEqual(counts['verified_objects'], len(ledger['objects']))
        self.assertEqual(len({o['owned_alias'] for o in ledger['objects']}), len(ledger['objects']))
        self.assertEqual(d['run']['business_requests'], len(d['observations']))
        self.assertEqual(d['run']['post_requests'], sum(o['method'] == 'POST' for o in d['observations']))
        self.assertEqual(d['run']['post_requests'], len(ledger['writes']))
        self.assertLessEqual(d['run']['post_requests'], d['run']['caps']['POST']); self.assertLessEqual(len(d['observations']), d['run']['caps']['business_requests'])
        for o in d['observations']:
            self.assertNotRegex(o['endpoint_template'], r'/(?:vendors|orders|goodsreceipt)/\d+')
            if o.get('raw_capture_lost'): self.assertIsNone(o['source_sha256']); continue
            self.assertRegex(o['source_sha256'], r'^[a-f0-9]{64}$'); self.assertRegex(o['shape_sha256'], r'^[a-f0-9]{64}$')
        for name, key in (('docs/r05a4-evidence.json', 'r05a4_matrix_sha256'), ('tests/fixtures/r05a4-owned-captures.json', 'r05a4_fixtures_sha256'),
                          ('docs/r05a3-evidence.json', 'r05a3_matrix_sha256'), ('tests/fixtures/r05a3-owned-captures.json', 'r05a3_fixtures_sha256')):
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), d['historical'][key])
    def test_sanitized_capture_hashes(self):
        d = self.matrix(); samples = json.loads(FIXTURES.read_text())
        self.assertEqual(set(samples), {c['name'] for c in d['captures']})
        for c in d['captures']:
            digest = hashlib.sha256(json.dumps(samples[c['name']], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(digest, c['sanitized_sha256']); self.assertNotEqual(digest, c['source_sha256'])
            self.assertEqual(c['source_sha256'], next(o['source_sha256'] for o in d['observations'] if o['seq'] == c['source_seq']))
    def test_cli_mutations_reject_false_promotion(self):
        if NO_MUTATIONS: return
        mutations = [lambda d: d['claims'].__setitem__('persistent_draft_proved', True),
                     lambda d: d['claims'].__setitem__('server_idempotency', True),
                     lambda d: d['ledger']['counts'].__setitem__('verified_objects', 0),
                     lambda d: d['points']['D79-draft']['simulation_record'].__setitem__('stock_after', {'quantity': 0.0, 'orderedToSuppliersQty': 2.0}),
                     lambda d: d['points']['order-correlation-lookup']['record'].__setitem__('precommitted_before_write', False),
                     lambda d: d['points']['partial-receipt-api']['record']['receipt_rows'][0].__setitem__('saleorderref', 7),
                     lambda d: d['observations'][0].__setitem__('source_sha256', '')]
        with tempfile.TemporaryDirectory(prefix='r05a5-', dir=os.environ.get('TMPDIR', tempfile.gettempdir())) as temp:
            for mutate in mutations:
                d = self.matrix(); mutate(d); path = Path(temp) / 'matrix.json'; path.write_text(json.dumps(d))
                result = subprocess.run([sys.executable, '-I', __file__, '--matrix', str(path), '--no-mutations'], cwd=ROOT, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 1); self.assertIn('FAIL:', result.stderr); self.assertNotIn('ERROR:', result.stderr)
if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--matrix', type=Path, default=MATRIX); parser.add_argument('--no-mutations', action='store_true')
    args, remaining = parser.parse_known_args(); MATRIX = args.matrix; NO_MUTATIONS = args.no_mutations
    unittest.main(argv=[sys.argv[0], *remaining])
