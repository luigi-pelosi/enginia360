#!/usr/bin/env python3
"""Offline tests of R05.a.6 owned order/proforma observations and D85 verdicts, not live provider compatibility."""
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
doctype = load('r05a6_document_type', 'scripts/r05a6_document_type.py')
closure = load('r05a5_closure', 'scripts/r05a5_closure.py')
recovery = load('r05a4_recovery', 'scripts/r05a4_recovery.py')
captures = load('r05a3_captures', 'scripts/r05a3_captures.py')
FIXTURES = ROOT / 'tests/fixtures/r05a6-owned-captures.json'
MATRIX = ROOT / 'docs/r05a6-evidence.json'
NO_MUTATIONS = False
def stock(q=2.0, reserved=0.0, available=2.0, ordered=6.0, forecast=8.0):
    return {'quantity': q, 'reservedByOrdersQty': reserved, 'availableQty': available, 'orderedToSuppliersQty': ordered, 'stockForecastQty': forecast}
def effect(**changes):
    value = {'before': stock(), 'after': stock(reserved=1.0, available=1.0, forecast=7.0), 'quantity': 1.0}
    value.update(changes)
    return value
def d85(**changes):
    value = {'fiscal_invoice_number_assigned': False, 'physical_stock_discharged': False, 'retrievable_without_server_id': True, 'readback_exact': True,
             'manual_conversion': 'UI_CONTROL_OBSERVED', 'prior_document_required': False, 'limits': ['reservation-reduces-available']}
    value.update(changes)
    return value
class StockEffectTests(unittest.TestCase):
    def test_reservation_without_physical_discharge(self):
        self.assertEqual(doctype.assess_stock_effect(effect()), 'RESERVES_NO_DISCHARGE')
    def test_no_change_and_physical_discharge_and_other_change(self):
        self.assertEqual(doctype.assess_stock_effect(effect(after=stock())), 'NO_STOCK_EFFECT')
        self.assertEqual(doctype.assess_stock_effect(effect(after=stock(q=1.0, available=1.0, forecast=7.0))), 'DISCHARGES_PHYSICAL')
        self.assertEqual(doctype.assess_stock_effect(effect(after=stock(ordered=5.0))), 'OTHER_CHANGE')
        self.assertEqual(doctype.assess_stock_effect(effect(after=stock(reserved=2.0, available=0.0, forecast=6.0))), 'OTHER_CHANGE')
    def test_invalid_records_are_rejected_not_guessed(self):
        bad = [effect(quantity=0), effect(quantity=True), effect(before={'quantity': 2.0}), effect(after={**stock(), 'availableQty': '1'}), effect(before=None)]
        for record in bad:
            with self.subTest(record=record), self.assertRaises(ValueError): doctype.assess_stock_effect(record)
class NumberingTests(unittest.TestCase):
    def test_type_specific_numbers(self):
        self.assertEqual(doctype.assess_numbering({'idDocumentType': 3, 'docNumber': '1', 'fiscal_invoice_number': '1659'}), 'ORDER_TYPE_NUMBER')
        self.assertEqual(doctype.assess_numbering({'idDocumentType': 33, 'docNumber': '2', 'fiscal_invoice_number': '1659'}), 'PROFORMA_TYPE_OWN_NUMBER')
        self.assertEqual(doctype.assess_numbering({'idDocumentType': 10, 'docNumber': '1659', 'fiscal_invoice_number': '1659'}), 'FISCAL_INVOICE_NUMBER')
    def test_collision_with_the_fiscal_number_is_detected(self):
        self.assertEqual(doctype.assess_numbering({'idDocumentType': 33, 'docNumber': '1659', 'fiscal_invoice_number': '1659'}), 'COLLIDES_WITH_FISCAL_NUMBER')
    def test_invalid_records_are_rejected(self):
        for record in ({'idDocumentType': '3', 'docNumber': '1', 'fiscal_invoice_number': '9'}, {'idDocumentType': 3, 'docNumber': '', 'fiscal_invoice_number': '9'},
                       {'idDocumentType': 3, 'docNumber': 1, 'fiscal_invoice_number': '9'}, {'idDocumentType': 99, 'docNumber': '1', 'fiscal_invoice_number': '9'}, {'idDocumentType': 3, 'docNumber': '1'}):
            with self.subTest(record=record), self.assertRaises(ValueError): doctype.assess_numbering(record)
class TypedLookupTests(unittest.TestCase):
    def samples(self): return json.loads(FIXTURES.read_text())
    def test_server_side_unique_order_lookup(self):
        r = doctype.assess_typed_lookup(closure.decode_order_headers(json.dumps(self.samples()['order-lookup-customer-name-status'])), 3, 'E360-SB-R05A6-20261027T131422Z-ORD')
        self.assertEqual(r, {'raw_total': 1, 'typed_matches': 1, 'verdict': 'UNIQUE_BY_SERVER_FILTER'})
    def test_mixed_invoice_list_is_unique_only_after_client_type_filter(self):
        r = doctype.assess_typed_lookup(closure.decode_order_headers(json.dumps(self.samples()['proforma-lookup-customer-name'])), 33, 'E360-SB-R05A6-20261027T131422Z-ORD')
        self.assertEqual(r, {'raw_total': 2, 'typed_matches': 1, 'verdict': 'UNIQUE_AFTER_CLIENT_TYPE_FILTER'})
    def test_empty_and_ambiguous_hold(self):
        empty = closure.decode_order_headers(json.dumps(self.samples()['order-lookup-reference-empty']))
        self.assertEqual(doctype.assess_typed_lookup(empty, 3, 'x')['verdict'], 'HOLD_NOT_FOUND')
        two = copy.deepcopy(self.samples()['proforma-lookup-customer-name']); two['documentsHeaders'].append({**two['documentsHeaders'][1], 'id': 202})
        two['metadata']['totalCount'] = 3
        self.assertEqual(doctype.assess_typed_lookup(closure.decode_order_headers(json.dumps(two)), 33, 'E360-SB-R05A6-20261027T131422Z-ORD')['verdict'], 'HOLD_AMBIGUOUS')
    def test_header_without_type_is_rejected(self):
        value = closure.decode_order_headers(json.dumps(self.samples()['order-lookup-customer-name-status'])); value['documentsHeaders'][0].pop('idDocumentType')
        with self.assertRaises(ValueError): doctype.assess_typed_lookup(value, 3, 'x')
class ReferenceRowDecoderTests(unittest.TestCase):
    def samples(self): return json.loads(FIXTURES.read_text())
    def test_proforma_readback_decodes_with_a_null_quantity_reference_row(self):
        value = doctype.decode_document(json.dumps(self.samples()['proforma-readback']))
        self.assertEqual([r['idPosType'] for r in value['document']['rows']], [5, 1]); self.assertIsNone(value['document']['rows'][0]['quantity'])
    def test_ordinary_documents_decode_exactly_as_before(self):
        s = self.samples()
        for name in ('order-readback', 'order-after-proforma'): self.assertEqual(doctype.decode_document(json.dumps(s[name])), captures.decode(json.dumps(s[name])))
    def test_null_quantity_is_accepted_only_on_pure_reference_rows(self):
        base = self.samples()['proforma-readback']
        def mutate(f):
            v = copy.deepcopy(base); f(v['document']['rows']); return v
        bad = [mutate(lambda r: r[1].update(quantity=None)), mutate(lambda r: r[0].update(idMaterial='owned-product-1')), mutate(lambda r: r[0].update(quantity=True)),
               mutate(lambda r: r[0].pop('quantity')), mutate(lambda r: r[0].update(idPosType=1)), mutate(lambda r: r[1].update(idPos=1))]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(ValueError): doctype.decode_document(json.dumps(item))
class D85VerdictTests(unittest.TestCase):
    def test_limits_or_prior_document_give_suitable_with_limits(self):
        self.assertEqual(doctype.assess_d85_type(d85()), 'SUITABLE-WITH-LIMITS')
        self.assertEqual(doctype.assess_d85_type(d85(limits=[], prior_document_required=True)), 'SUITABLE-WITH-LIMITS')
        self.assertEqual(doctype.assess_d85_type(d85(limits=[], manual_conversion='API_DOCUMENTED_ONLY')), 'SUITABLE-WITH-LIMITS')
    def test_clean_record_is_suitable(self):
        self.assertEqual(doctype.assess_d85_type(d85(limits=[])), 'SUITABLE')
    def test_each_hard_requirement_failure_is_unsuitable(self):
        for change in ({'fiscal_invoice_number_assigned': True}, {'physical_stock_discharged': True}, {'retrievable_without_server_id': False}, {'readback_exact': False}, {'manual_conversion': 'NONE'}):
            with self.subTest(change=change): self.assertEqual(doctype.assess_d85_type(d85(**change)), 'UNSUITABLE')
    def test_invalid_records_are_rejected(self):
        for change in ({'readback_exact': None}, {'manual_conversion': 'MAYBE'}, {'limits': 'x'}, {'prior_document_required': 1}):
            with self.subTest(change=change), self.assertRaises(ValueError): doctype.assess_d85_type(d85(**change))
    def test_recommendation_prefers_better_verdict_then_fewer_prerequisites(self):
        order = {'type': 'sales-order', 'verdict': 'SUITABLE-WITH-LIMITS', 'prior_document_required': False, 'manual_conversion': 'UI_CONTROL_OBSERVED'}
        proforma = {'type': 'proforma', 'verdict': 'SUITABLE-WITH-LIMITS', 'prior_document_required': True, 'manual_conversion': 'API_DOCUMENTED_ONLY'}
        self.assertEqual(doctype.recommend([proforma, order])['type'], 'sales-order')
        self.assertEqual(doctype.recommend([{**order, 'verdict': 'UNSUITABLE'}, proforma])['type'], 'proforma')
        self.assertEqual(doctype.recommend([{**order, 'verdict': 'SUITABLE'}, {**proforma, 'verdict': 'SUITABLE-WITH-LIMITS'}])['type'], 'sales-order')
        self.assertIsNone(doctype.recommend([{**order, 'verdict': 'UNSUITABLE'}, {**proforma, 'verdict': 'UNSUITABLE'}]))
        self.assertTrue(doctype.recommend([order, proforma])['owner_may_overrule'])
class RegressionTests(unittest.TestCase):
    """Passing on first run: existing decoders and assessors are reused unchanged."""
    def samples(self): return json.loads(FIXTURES.read_text())
    def test_existing_lookup_assessor_reads_the_order_key_record(self):
        record = {'precommitted_before_write': True, 'oracle_read_after_conclusion': True, 'oracle_id_equals_lookup_id': True, 'response_discarded': False, 'recovery_key': 'customer-name',
                  'lookups': [{'label': 'reference', 'totalCount': 0, 'exact_matches': 0, 'kind': 'freeText-reference'}, {'label': 'customer-name', 'totalCount': 1, 'exact_matches': 1, 'kind': 'freeText-customer-name'}]}
        self.assertEqual(closure.assess_lookup_set(record)['verdict'], 'RECOVERED_BY_PRECOMMITTED_KEY')
    def test_mixed_invoice_lookup_is_ambiguous_for_the_existing_assessor(self):
        record = {'precommitted_before_write': True, 'oracle_read_after_conclusion': True, 'oracle_id_equals_lookup_id': True, 'response_discarded': False, 'recovery_key': 'customer-name',
                  'lookups': [{'label': 'customer-name', 'totalCount': 2, 'exact_matches': 1, 'kind': 'freeText-customer-name'}]}
        self.assertEqual(closure.assess_lookup_set(record)['verdict'], 'HOLD_AMBIGUOUS')
    def test_existing_decoders_read_owned_projections(self):
        s = self.samples()
        self.assertEqual(captures.decode(json.dumps(s['order-readback']))['document']['docNumber'], '1')
        self.assertEqual(captures.decode(json.dumps(s['order-after-proforma']))['document']['docStatus'], 'CREATED')
        self.assertEqual(captures.decode(json.dumps(s['stock-after-order']))['stockReports'][0]['reservedByOrdersQty'], 1.0)
        with self.assertRaises(ValueError): recovery.decode_lookup(json.dumps(s['order-lookup-customer-name-status']), 'documentsHeaders')  # string-id decoder does not fit integer ids
    def test_existing_decoder_rejects_the_proforma_reference_row_null_quantity(self):
        with self.assertRaises(ValueError): captures.decode(json.dumps(self.samples()['proforma-readback']))
    def test_existing_link_assessor_detects_persisted_source_link(self):
        s = self.samples(); rows = s['proforma-readback']['document']['rows']
        record = {'sent_rows': [{'saleorderref': 101, 'saleorderposref': 1, 'quantity': 1.0}], 'receipt_rows': rows, 'order_row_status_before': ['CREATED'], 'order_row_status_after': ['CREATED'],
                  'order_status_before': 'CREATED', 'order_status_after': 'CREATED', 'stock_before': s['stock-after-order']['stockReports'][0], 'stock_after': s['stock-after-proforma']['stockReports'][0]}
        self.assertEqual(closure.assess_receipt_link(record), 'LINK_PERSISTED')
class EvidenceTests(unittest.TestCase):
    def matrix(self): return json.loads(MATRIX.read_text())
    def samples(self): return json.loads(FIXTURES.read_text())
    def test_claims_false_and_no_new_decision(self):
        d = self.matrix(); self.assertEqual(d['increment'], 'R05.a.6'); self.assertIsNone(d['new_decision'])
        self.assertTrue(d['claims']); self.assertTrue(all(v is False for v in d['claims'].values()))
        for key in ('server_idempotency', 'invoice_conversion_exercised', 'r04_complete', 'r05_complete', 'readiness', 'provider_compatibility', 'owner_decision_made'): self.assertIn(key, d['claims'])
    def test_recorded_verdicts_match_the_assessors(self):
        d = self.matrix(); p = d['points']
        def verdict(fn, record):
            try: return fn(record)
            except ValueError as error: self.fail('invalid recorded observation: %s' % error)
        order, pro = p['sales-order'], p['proforma']
        self.assertEqual(verdict(doctype.assess_stock_effect, order['stock_record']), 'RESERVES_NO_DISCHARGE')
        self.assertEqual(verdict(doctype.assess_stock_effect, pro['stock_record']), 'NO_STOCK_EFFECT')
        self.assertEqual(verdict(doctype.assess_numbering, order['numbering_record']), 'ORDER_TYPE_NUMBER')
        self.assertEqual(verdict(doctype.assess_numbering, pro['numbering_record']), 'PROFORMA_TYPE_OWN_NUMBER')
        self.assertEqual(verdict(closure.assess_lookup_set, order['lookup_record'])['verdict'], 'RECOVERED_BY_PRECOMMITTED_KEY')
        self.assertEqual(verdict(closure.assess_receipt_link, pro['link_record']), 'LINK_PERSISTED')
        self.assertEqual(verdict(doctype.assess_d85_type, order['d85_record']), order['verdict']); self.assertEqual(order['verdict'], 'SUITABLE-WITH-LIMITS')
        self.assertEqual(verdict(doctype.assess_d85_type, pro['d85_record']), pro['verdict']); self.assertEqual(pro['verdict'], 'SUITABLE-WITH-LIMITS')
        rec = d['recommendation']; self.assertTrue(rec['owner_may_overrule']); self.assertEqual(rec['evidence_class'], 'evidence-based-recommendation-not-decision')
        entries = [{'type': 'sales-order', **{k: order[k] for k in ('verdict',)}, 'prior_document_required': order['d85_record']['prior_document_required'], 'manual_conversion': order['d85_record']['manual_conversion']},
                   {'type': 'proforma', 'verdict': pro['verdict'], 'prior_document_required': pro['d85_record']['prior_document_required'], 'manual_conversion': pro['d85_record']['manual_conversion']}]
        self.assertEqual(doctype.recommend(entries)['type'], rec['type']); self.assertEqual(rec['type'], 'sales-order')
    def test_recorded_fixtures_feed_the_recorded_records(self):
        d = self.matrix(); s = self.samples(); p = d['points']
        before, after_order, after_pro = (s[n]['stockReports'][0] for n in ('stock-before-order', 'stock-after-order', 'stock-after-proforma'))
        self.assertEqual(p['sales-order']['stock_record']['before'], before); self.assertEqual(p['sales-order']['stock_record']['after'], after_order)
        self.assertEqual(p['proforma']['stock_record']['before'], after_order); self.assertEqual(p['proforma']['stock_record']['after'], after_pro)
        o, pf = s['order-readback']['document'], s['proforma-readback']['document']
        self.assertEqual((o['docStatus'], pf['docStatus']), ('CREATED', 'CREATED')); self.assertEqual(pf['idDocumentType'], 33); self.assertEqual(o['idDocumentType'], 3)
        self.assertEqual(p['sales-order']['numbering_record']['docNumber'], o['docNumber']); self.assertEqual(p['proforma']['numbering_record']['docNumber'], pf['docNumber'])
        self.assertEqual(s['order-after-proforma']['document']['docStatus'], 'CREATED')
        self.assertEqual(s['order-create-response']['idDocument'], 101); self.assertEqual(s['proforma-create-response']['idDocument'], 201)
        self.assertEqual(doctype.assess_typed_lookup(closure.decode_order_headers(json.dumps(s['proforma-lookup-customer-name'])), 33, p['proforma']['reference'])['verdict'], 'UNIQUE_AFTER_CLIENT_TYPE_FILTER')
        self.assertEqual(doctype.assess_typed_lookup(closure.decode_order_headers(json.dumps(s['order-lookup-customer-name-status'])), 3, p['sales-order']['reference'])['verdict'], 'UNIQUE_BY_SERVER_FILTER')
    def test_programmatic_counts_hashes_and_ledger(self):
        d = self.matrix(); ledger = d['ledger']; counts = ledger['counts']
        self.assertEqual(counts['write_intents'], len(ledger['writes'])); self.assertEqual(counts['verified_objects'], len(ledger['objects']))
        self.assertEqual(len({o['owned_alias'] for o in ledger['objects']}), len(ledger['objects']))
        self.assertEqual(d['run']['business_requests'], len(d['observations']))
        self.assertEqual(d['run']['post_requests'], sum(o['method'] == 'POST' for o in d['observations'])); self.assertEqual(d['run']['post_requests'], len(ledger['writes']))
        self.assertLessEqual(d['run']['post_requests'], d['run']['caps']['POST']); self.assertLessEqual(len(d['observations']), d['run']['caps']['business_requests'])
        self.assertEqual([o['seq'] for o in d['observations']], list(range(1, len(d['observations']) + 1)))
        for o in d['observations']:
            self.assertNotRegex(o['endpoint_template'], r'/(?:sales)/\d+/'); self.assertRegex(o['source_sha256'], r'^[a-f0-9]{64}$'); self.assertRegex(o['shape_sha256'], r'^[a-f0-9]{64}$')
        for w in ledger['writes']: self.assertEqual(w['state'], 'RESPONSE_OBSERVED_VERIFIED')
        for name, key in (('docs/r05a2-evidence.json', 'r05a2_matrix_sha256'), ('docs/r05a3-evidence.json', 'r05a3_matrix_sha256'), ('tests/fixtures/r05a3-owned-captures.json', 'r05a3_fixtures_sha256'),
                          ('docs/r05a4-evidence.json', 'r05a4_matrix_sha256'), ('tests/fixtures/r05a4-owned-captures.json', 'r05a4_fixtures_sha256'),
                          ('docs/r05a5-evidence.json', 'r05a5_matrix_sha256'), ('tests/fixtures/r05a5-owned-captures.json', 'r05a5_fixtures_sha256')):
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), d['historical'][key])
        self.assertTrue(d['historical']['r05a3_uncertain_intent_held_unchanged'] and d['historical']['r05a3_error_no_replay_intent_held_unchanged'])
    def test_sanitized_capture_hashes(self):
        d = self.matrix(); samples = self.samples()
        self.assertEqual(set(samples), {c['name'] for c in d['captures']})
        for c in d['captures']:
            digest = hashlib.sha256(json.dumps(samples[c['name']], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(digest, c['sanitized_sha256']); self.assertNotEqual(digest, c['source_sha256'])
            self.assertEqual(c['source_sha256'], next(o['source_sha256'] for o in d['observations'] if o['seq'] == c['source_seq']))
    def test_public_declaration_extracts_are_consistent_and_labelled(self):
        d = self.matrix(); pub = d['public_declaration']; self.assertRegex(pub['swagger_sha256'], r'^[a-f0-9]{64}$')
        self.assertIn(pub['swagger_sha256'], (ROOT / 'docs/r05a3-evidence.json').read_text())  # same acquired bytes as the R05.a.3 record; URL content is mutable
        for e in pub['extracts']:
            self.assertEqual(hashlib.sha256(json.dumps(e['extract'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(), e['extract_sha256']); self.assertTrue(e['pointer'].startswith(('/', 'reference page #')))
        ex = {e['name']: e['extract'] for e in pub['extracts']}
        self.assertEqual(ex['proforma-paths'], ['/sales/{id}/goodissuestoproformainvoice', '/sales/{id}/orderstoproformainvoice', '/sales/{id}/proformainvoicetoinvoice'])
        self.assertNotIn('simulation', ex['orderstoproformainvoice-parameters']); self.assertIn('simulation', ex['sales-orders-post-parameters'])
        self.assertEqual(ex['document-transformation-fields'], ['docDate', 'docNumber', 'idNumerator']); self.assertEqual(d['public_declaration']['direct_proforma_create_path_declared'], False)
        self.assertEqual(d['classes'], ['public-declaration', 'sandbox-observation', 'local-guard'])
    def test_optional_swagger_probe(self):
        path = os.environ.get('R05A6_SWAGGER_PATH')
        if not path: self.skipTest('private official swagger bytes not supplied; CI proves documentary consistency only')
        raw = Path(path).read_bytes(); d = self.matrix(); self.assertEqual(hashlib.sha256(raw).hexdigest(), d['public_declaration']['swagger_sha256'])
        s = json.loads(raw); ex = {e['name']: e['extract'] for e in d['public_declaration']['extracts']}
        self.assertEqual(sorted(p for p in s['paths'] if 'proforma' in p.lower()), ex['proforma-paths'])
        self.assertEqual(sorted(s['definitions']['DocumentTransformationApi']['properties']), ex['document-transformation-fields'])
        self.assertEqual(sorted(x['name'] for x in s['paths']['/sales/{id}/orderstoproformainvoice']['post']['parameters']), ex['orderstoproformainvoice-parameters'])
    def test_cli_mutations_reject_false_promotion(self):
        if NO_MUTATIONS: return
        mutations = [lambda d: d['claims'].__setitem__('invoice_conversion_exercised', True),
                     lambda d: d['claims'].__setitem__('owner_decision_made', True),
                     lambda d: d['ledger']['counts'].__setitem__('verified_objects', 0),
                     lambda d: d['points']['sales-order']['stock_record']['after'].__setitem__('quantity', 1.0),
                     lambda d: d['points']['sales-order']['d85_record'].__setitem__('physical_stock_discharged', True),
                     lambda d: [r.update(saleorderref=None, saleorderposref=None) for r in d['points']['proforma']['link_record']['receipt_rows']],
                     lambda d: d['points']['proforma']['numbering_record'].__setitem__('docNumber', '1659'),
                     lambda d: d['recommendation'].__setitem__('type', 'proforma'),
                     lambda d: d['observations'][0].__setitem__('source_sha256', '')]
        with tempfile.TemporaryDirectory(prefix='r05a6-', dir=os.environ.get('TMPDIR', tempfile.gettempdir())) as temp:
            for mutate in mutations:
                d = self.matrix(); mutate(d); path = Path(temp) / 'matrix.json'; path.write_text(json.dumps(d))
                result = subprocess.run([sys.executable, '-I', __file__, '--matrix', str(path), '--no-mutations'], cwd=ROOT, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 1); self.assertIn('FAIL:', result.stderr); self.assertNotIn('ERROR:', result.stderr)
if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--matrix', type=Path, default=MATRIX); parser.add_argument('--no-mutations', action='store_true')
    args, remaining = parser.parse_known_args(); MATRIX = args.matrix; NO_MUTATIONS = args.no_mutations
    unittest.main(argv=[sys.argv[0], *remaining])
