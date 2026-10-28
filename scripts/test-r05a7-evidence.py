#!/usr/bin/env python3
"""Offline tests of R05.a.7 owned purchase-order observations, not live provider compatibility."""
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
po = load('r05a7_purchase_order', 'scripts/r05a7_purchase_order.py')
FIXTURES = ROOT / 'tests/fixtures/r05a7-owned-captures.json'
MATRIX = ROOT / 'docs/r05a7-evidence.json'
NO_MUTATIONS = False
PREFIX = 'E360-SB-R05A7-20261028T155140Z'
def samples(): return json.loads(FIXTURES.read_text())
def text(name, mutate=None):
    value = copy.deepcopy(samples()[name])
    if mutate: mutate(value)
    return json.dumps(value)
def stock(q=2.0, reserved=1.0, available=1.0, ordered=6.0, forecast=7.0):
    return {'quantity': q, 'reservedByOrdersQty': reserved, 'availableQty': available, 'orderedToSuppliersQty': ordered, 'stockForecastQty': forecast}
def body(**changes):
    value = {'idDocumentType': 2, 'idDocumentTypeExt': 0, 'idOrderType': 1, 'idContact': None, 'idCustomer': None, 'idVendor': 'owned-vendor-A', 'docDate': '1793202000000',
             'docStatus': 'CREATED', 'docCurrency': 'EUR', 'idBu': 'U1', 'idNumerator': 1, 'note': PREFIX + ' note', 'internalNote': PREFIX, 'reference': PREFIX + '-PO', 'payments': [],
             'rows': [{'idMaterial': 'owned-product-1', 'idAttributeCombination': 0, 'idPosType': 1, 'description': PREFIX + ' line', 'quantity': 1, 'price': 12.345678, 'idVat': '22', 'idStorage': 'MB'}]}
    value.update(changes)
    return value

class DecoderTests(unittest.TestCase):
    def test_ack_is_only_an_identity_receipt(self):
        v = po.decode_ack(text('po-ack'))
        self.assertEqual(v['idDocument'], 301); self.assertNotIn('document', v)
    def test_ack_rejects_missing_or_non_integer_id_and_error_envelopes(self):
        for mutate in (lambda v: v.pop('idDocument'), lambda v: v.update(idDocument='301'), lambda v: v.update(idDocument=True), lambda v: v.update(errorCode=1), lambda v: v.update(document={})):
            with self.subTest(), self.assertRaises(ValueError): po.decode_ack(text('po-ack', mutate))
    def test_preview_has_no_identity_and_no_number(self):
        v = po.decode_preview(text('sim-vendor-preview'))
        self.assertIsNone(v['document']['id']); self.assertEqual(v['document']['docNumber'], '')
    def test_preview_rejects_a_persisted_document(self):
        with self.assertRaises(ValueError): po.decode_preview(text('po-readback'))
    def test_rejection_requires_error_envelope_and_message(self):
        v = po.decode_rejection(text('sim-contact-only-rejected')); self.assertEqual((v['responseCode'], v['errorCode']), (400, 324))
        for mutate in (lambda v: v.update(responseCode=200), lambda v: v.update(errorCode='324'), lambda v: v.pop('developerMessage')):
            with self.subTest(), self.assertRaises(ValueError): po.decode_rejection(text('sim-contact-only-rejected', mutate))
    def test_order_readback_decodes_with_exact_q6_price(self):
        v = po.decode_order(text('po-readback')); d = v['document']
        self.assertEqual((d['id'], d['idDocumentType'], d['idVendor'], d['idContact']), (301, 2, 'owned-vendor-A', 9001)); self.assertEqual(d['rows'][0]['price'], 12.345678)
    def test_order_readback_rejects_incomplete_or_wrongly_typed_documents(self):
        bad = [lambda v: v['document'].update(idDocumentType=3), lambda v: v['document'].update(idVendor=402), lambda v: v['document'].update(idContact='9001'),
               lambda v: v['document'].update(totalAmount='15.07'), lambda v: v['document'].update(reference=None), lambda v: v['document']['rows'][0].pop('price'),
               lambda v: v['document']['rows'][0].update(price=True), lambda v: v['document']['rows'][0].update(description=None), lambda v: v['document']['rows'].append(dict(v['document']['rows'][0])),
               lambda v: v['document'].update(rows=[]), lambda v: v['document'].update(id=None)]
        for mutate in bad:
            with self.subTest(), self.assertRaises(ValueError): po.decode_order(text('po-readback', mutate))
    def test_headers_decode_with_integer_ids_and_nullable_contact(self):
        v = po.decode_headers(text('po-lookup-vendor-name-status'))
        self.assertEqual([h['id'] for h in v['documentsHeaders']], [301, 201]); self.assertTrue(all(h['idContact'] is None for h in v['documentsHeaders']))
    def test_headers_reject_string_ids_missing_reference_key_and_bad_metadata(self):
        bad = [lambda v: v['documentsHeaders'][0].update(id='301'), lambda v: v['documentsHeaders'][0].pop('reference'), lambda v: v['documentsHeaders'][0].update(idVendor=None),
               lambda v: v['metadata'].update(totalCount='2'), lambda v: v['metadata'].pop('limit'), lambda v: v.pop('documentsHeaders'), lambda v: v['documentsHeaders'][0].update(idDocumentType=3)]
        for mutate in bad:
            with self.subTest(), self.assertRaises(ValueError): po.decode_headers(text('po-lookup-vendor-name-status', mutate))

class VendorIdentityTests(unittest.TestCase):
    def record(self, **changes):
        value = {'vendor_id': 'owned-vendor-A', 'contact_id': 9001, 'contact_vendor_id': 'owned-vendor-A', 'sent': {'idVendor': 'owned-vendor-A', 'idContact': None},
                 'order': {'idVendor': 'owned-vendor-A', 'idContact': 9001}, 'contact_only_rejected': True}
        value.update(changes)
        return value
    def test_string_vendor_id_is_required_and_contact_is_server_resolved(self):
        self.assertEqual(po.assess_vendor_identity(self.record()), 'VENDOR_STRING_ID_REQUIRED_CONTACT_SERVER_RESOLVED')
    def test_unproven_when_contact_only_was_not_rejected_or_mapping_differs(self):
        for changes in ({'contact_only_rejected': False}, {'order': {'idVendor': 'owned-vendor-A', 'idContact': 9002}}, {'order': {'idVendor': 'owned-vendor-B', 'idContact': 9001}},
                        {'contact_vendor_id': 'owned-vendor-B'}, {'sent': {'idVendor': 'owned-vendor-A', 'idContact': 9001}}):
            with self.subTest(changes=changes): self.assertEqual(po.assess_vendor_identity(self.record(**changes)), 'MAPPING_UNPROVEN')
    def test_invalid_records_are_rejected(self):
        for changes in ({'contact_id': True}, {'vendor_id': ''}, {'contact_only_rejected': None}, {'order': None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): po.assess_vendor_identity(self.record(**changes))

class PriceReadbackTests(unittest.TestCase):
    def doc(self): return json.loads(text('po-readback'))['document']
    def record(self, document=None, **changes):
        value = {'sent_price': 12.345678, 'quantity': 1.0, 'vat_rate': 22, 'document': document or self.doc()}
        value.update(changes)
        return value
    def test_row_price_is_preserved_while_header_totals_are_two_decimal_roundings(self):
        self.assertEqual(po.assess_price_readback(self.record()), {'row_price': 'Q6_PRESERVED', 'header_totals': 'ROUNDED_2DP_FROM_ROUNDED_NET'})
    def test_altered_row_price_and_inconsistent_totals_are_detected(self):
        d = self.doc(); d['rows'][0]['price'] = 12.35
        self.assertEqual(po.assess_price_readback(self.record(d))['row_price'], 'ROW_PRICE_ALTERED')
        d = self.doc(); d['totalAmount'] = 15.06
        self.assertEqual(po.assess_price_readback(self.record(d))['header_totals'], 'TOTALS_INCONSISTENT')
        d = self.doc(); d['taxableAmount'] = 12.345678
        self.assertEqual(po.assess_price_readback(self.record(d))['header_totals'], 'TOTALS_INCONSISTENT')
    def test_invalid_records_are_rejected(self):
        for changes in ({'sent_price': True}, {'quantity': 0}, {'vat_rate': '22'}, {'document': 'x'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): po.assess_price_readback(self.record(**changes))

class StockEffectTests(unittest.TestCase):
    def test_purchase_order_raises_only_ordered_and_forecast(self):
        self.assertEqual(po.assess_po_stock_effect({'before': stock(), 'after': stock(ordered=7.0, forecast=8.0), 'quantity': 1.0}), 'ORDERED_ONLY')
    def test_no_effect_physical_reservation_and_other_changes(self):
        self.assertEqual(po.assess_po_stock_effect({'before': stock(), 'after': stock(), 'quantity': 1.0}), 'NO_STOCK_EFFECT')
        self.assertEqual(po.assess_po_stock_effect({'before': stock(), 'after': stock(q=3.0, available=2.0, ordered=7.0, forecast=8.0), 'quantity': 1.0}), 'PHYSICAL_CHANGED')
        self.assertEqual(po.assess_po_stock_effect({'before': stock(), 'after': stock(reserved=2.0, available=0.0, ordered=7.0, forecast=7.0), 'quantity': 1.0}), 'RESERVATION_CHANGED')
        self.assertEqual(po.assess_po_stock_effect({'before': stock(), 'after': stock(ordered=8.0, forecast=9.0), 'quantity': 1.0}), 'OTHER_CHANGE')
    def test_invalid_records_are_rejected(self):
        for record in ({'before': stock(), 'after': stock(), 'quantity': 0}, {'before': {'quantity': 1.0}, 'after': stock(), 'quantity': 1.0}, {'before': stock(), 'after': {**stock(), 'availableQty': '1'}, 'quantity': 1.0},
                       {'before': None, 'after': stock(), 'quantity': 1.0}):
            with self.subTest(record=record), self.assertRaises(ValueError): po.assess_po_stock_effect(record)

class NonPersistenceTests(unittest.TestCase):
    def test_unchanged_vendor_list_and_stock_means_not_persisted(self):
        self.assertEqual(po.assess_nonpersistence({'ids_before': [201], 'ids_after': [201], 'stock_before': stock(), 'stock_after': stock()}), 'NOT_PERSISTED_BY_VENDOR_LIST_AND_STOCK')
    def test_any_change_is_flagged(self):
        self.assertEqual(po.assess_nonpersistence({'ids_before': [201], 'ids_after': [301, 201], 'stock_before': stock(), 'stock_after': stock()}), 'CHANGED')
        self.assertEqual(po.assess_nonpersistence({'ids_before': [201], 'ids_after': [201], 'stock_before': stock(), 'stock_after': stock(ordered=7.0)}), 'CHANGED')
    def test_invalid_records_are_rejected(self):
        for record in ({'ids_before': [201], 'ids_after': '201', 'stock_before': stock(), 'stock_after': stock()}, {'ids_before': [True], 'ids_after': [True], 'stock_before': stock(), 'stock_after': stock()}):
            with self.subTest(record=record), self.assertRaises(ValueError): po.assess_nonpersistence(record)

class LookupTests(unittest.TestCase):
    ref = PREFIX + '-PO'
    def page(self, name): return po.decode_headers(text(name))
    def test_vendor_name_page_is_unique_only_after_client_reference_filter(self):
        r = po.assess_lookup(self.page('po-lookup-vendor-name-status'), self.ref, 5)
        self.assertEqual(r, {'returned': 2, 'exact_matches': 1, 'total_count_equals_returned': True, 'page_full': False, 'verdict': 'UNIQUE_AFTER_CLIENT_REFERENCE_FILTER'})
    def test_empty_is_hold_not_absence(self):
        r = po.assess_lookup(self.page('po-lookup-reference-empty'), self.ref, 5)
        self.assertEqual((r['returned'], r['verdict']), (0, 'HOLD_NOT_FOUND'))
    def test_full_page_without_match_is_a_distinct_hold(self):
        r = po.assess_lookup(self.page('po-lookup-limit1-offset1'), self.ref, 1)
        self.assertEqual((r['returned'], r['exact_matches'], r['page_full'], r['verdict']), (1, 0, True, 'HOLD_PAGE_FULL_NOT_FOUND'))
    def test_first_page_of_one_finds_the_newest_order(self):
        r = po.assess_lookup(self.page('po-lookup-limit1-offset0'), self.ref, 1)
        self.assertEqual((r['exact_matches'], r['page_full'], r['verdict']), (1, True, 'UNIQUE_AFTER_CLIENT_REFERENCE_FILTER'))
    def test_duplicate_reference_is_ambiguous(self):
        v = self.page('po-lookup-vendor-name-status'); v['documentsHeaders'][1]['reference'] = self.ref
        self.assertEqual(po.assess_lookup(v, self.ref, 5)['verdict'], 'HOLD_AMBIGUOUS')
    def test_total_count_is_not_a_completeness_signal(self):
        v = self.page('po-lookup-limit1-offset0'); v['metadata']['totalCount'] = 9
        self.assertFalse(po.assess_lookup(v, self.ref, 1)['total_count_equals_returned'])
    def test_invalid_inputs_are_rejected(self):
        for reference, limit in (('', 5), (None, 5), (self.ref, 0), (self.ref, True)):
            with self.subTest(reference=reference, limit=limit), self.assertRaises(ValueError): po.assess_lookup(self.page('po-lookup-vendor-name-status'), reference, limit)

class RequestBodyTests(unittest.TestCase):
    def test_observed_required_body_is_accepted(self):
        self.assertEqual(po.assess_request_body(body(), PREFIX), 'OBSERVED_REQUIRED_FIELDS_PRESENT')
    def test_missing_wrong_type_or_unowned_bodies_are_rejected(self):
        def row(**c): return [{**body()['rows'][0], **c}]
        bad = [body(idVendor=None), body(idVendor=402), body(docDate=None), body(idBu=None), body(idNumerator='1'), body(payments=None), body(rows=[]), body(rows=row(price='12.345678')), body(rows=row(price=True)),
               body(rows=row(description='')), body(rows=row(idMaterial=None)), body(rows=row(idPosType=None)), body(rows=row(quantity=0)), body(reference='E360-SB-OTHER-PO'), body(note='plain'), body(idDocumentType=3)]
        for item in bad:
            with self.subTest(), self.assertRaises(ValueError): po.assess_request_body(item, PREFIX)
        missing = body(); missing.pop('idContact')
        with self.assertRaises(ValueError): po.assess_request_body(missing, PREFIX)
    def test_null_contact_is_part_of_the_observed_shape(self):
        self.assertEqual(po.assess_request_body(body(idContact=None), PREFIX), 'OBSERVED_REQUIRED_FIELDS_PRESENT')

class RedactionTests(unittest.TestCase):
    def test_the_committed_fixtures_have_no_findings(self):
        self.assertEqual(po.redaction_findings(samples()), [])
    def test_secrets_identifiers_and_free_text_are_flagged(self):
        for leaf in ('eyJhbGciOiJSUzI1NiJ9.abc.def', 'Bearer abc', 'user@example.com', 'https://app.example.com/x', 'Acme Refrigeration SRL', '10.0.0.1', 'sb-account', 'password=x'):
            v = {'a': [{'b': leaf}]}
            with self.subTest(leaf=leaf): self.assertEqual(len(po.redaction_findings(v)), 1)
    def test_owned_aliases_and_prefixed_synthetic_text_are_allowed(self):
        v = {'a': ['owned-vendor-A', PREFIX + '-PO', PREFIX + ' P3 line', 'CREATED', 'U1', 'EUR', '22', 'MB', 'Unica rata', 'docStatus input ignored warning present'], 'n': 5, 'f': 12.345678, 'z': None, 'b': True}
        self.assertEqual(po.redaction_findings(v), [])
    def test_keys_that_carry_secrets_are_flagged(self):
        for key in ('access_token', 'password', 'client_id', 'cid', 'Authorization', 'refresh_token'):
            with self.subTest(key=key): self.assertEqual(len(po.redaction_findings({key: 'x'})), 1)

MAY_RELY = {'idvendor-string-with-null-idcontact-accepted', 'ack-integer-iddocument-then-detail-readback', 'row-price-q6-readback-exact', 'purchase-order-stock-effect-ordered-only',
            'vendor-name-status-lookup-with-client-reference-filter'}
MUST_NOT_RELY = {'server-idempotency', 'exactly-once', 'receipt-link-order-reference', 'header-total-q6', 'totalcount-completeness', 'empty-lookup-is-absence', 'numeric-contact-only',
                 'price-in-list-header', 'docnumber-correlation', 'client-set-docstatus', 'numerator-by-document-type-filter', 'blind-replay-after-lost-response'}
CLAIM_KEYS = ('server_idempotency', 'exactly_once', 'receipt_link_proved', 'header_total_q6', 'lost_response_replay_authorized', 'connector_implemented', 'owner_decision_made',
              'r04_complete', 'r05_complete', 'readiness', 'provider_compatibility')
class EvidenceTests(unittest.TestCase):
    def matrix(self): return json.loads(MATRIX.read_text())
    def test_claims_false_and_no_new_decision(self):
        d = self.matrix(); self.assertEqual(d['increment'], 'R05.a.7'); self.assertIsNone(d['new_decision']); self.assertEqual(d['refs'], ['#124', '#44', '#45'])
        self.assertEqual(set(d['claims']), set(CLAIM_KEYS)); self.assertTrue(all(v is False for v in d['claims'].values()))
        self.assertEqual(d['classes'], ['public-declaration', 'sandbox-observation', 'local-guard'])
    def test_adapter_reliance_lists_are_exactly_the_observed_set(self):
        d = self.matrix(); self.assertEqual(set(d['adapter_may_rely_on']), MAY_RELY); self.assertEqual(set(d['adapter_must_not_rely_on']), MUST_NOT_RELY); self.assertFalse(MAY_RELY & MUST_NOT_RELY)
    def test_ledger_chronology_caps_prefix_and_counts(self):
        d = self.matrix(); self.assertEqual(po.assess_ledger(d), [])
        self.assertEqual(d['run']['caps'], {'persisted_POST': 3, 'simulation_POST': 2, 'business_requests': 45, 'lookup_limit': 5, 'min_interval_s': 0.5})
        self.assertRegex(d['run']['synthetic_prefix'], r'^E360-SB-R05A7-\d{8}T\d{6}Z$')
        for w in d['ledger']['writes']: self.assertIn(w['mode'], ('PERSISTED', 'SIMULATION'))
    def test_recorded_request_bodies_follow_the_observed_contract(self):
        d = self.matrix(); prefix = d['run']['synthetic_prefix']; bodies = d['request_bodies']
        for key in ('persisted', 'simulation-idvendor'):
            try: verdict = po.assess_request_body(bodies[key], prefix)
            except ValueError as error: self.fail('recorded request body %s violates the observed contract: %s' % (key, error))
            self.assertEqual(verdict, 'OBSERVED_REQUIRED_FIELDS_PRESENT')
        with self.assertRaises(ValueError): po.assess_request_body(bodies['simulation-contact-only'], prefix)  # the rejected variant lacks the string vendor id
        self.assertEqual(bodies['persisted']['rows'][0]['price'], 12.345678); self.assertEqual(bodies['persisted']['payments'], []); self.assertIsNone(bodies['persisted']['idContact'])
        self.assertEqual(bodies['persisted']['docDate'], 'epochmillis')
        for key, b in bodies.items(): self.assertEqual(hashlib.sha256(json.dumps(b, sort_keys=True, separators=(',', ':')).encode()).hexdigest(), d['request_body_sha256'][key])
    def test_recorded_points_match_the_assessors_and_fixtures(self):
        d = self.matrix(); s = samples(); p = d['points']
        v = p['vendor_identity']; self.assertEqual(po.assess_vendor_identity(v['record']), v['verdict']); self.assertEqual(v['verdict'], 'VENDOR_STRING_ID_REQUIRED_CONTACT_SERVER_RESOLVED')
        vendor = s['vendor-lookup-owned']['vendors'][0]; order = s['po-readback']['document']
        self.assertEqual((v['record']['vendor_id'], v['record']['contact_id'], v['record']['contact_vendor_id']), (vendor['id'], vendor['contact']['id'], vendor['contact']['idVendor']))
        self.assertEqual(v['record']['order'], {'idVendor': order['idVendor'], 'idContact': order['idContact']}); self.assertEqual(po.decode_rejection(json.dumps(s['sim-contact-only-rejected']))['errorCode'], 324)
        self.assertEqual(v['record']['sent'], {'idVendor': d['request_bodies']['persisted']['idVendor'], 'idContact': d['request_bodies']['persisted']['idContact']})
        pr = p['price_readback']; self.assertEqual(po.assess_price_readback({**pr['record'], 'document': order}), pr['verdict']); self.assertEqual(pr['verdict'], {'row_price': 'Q6_PRESERVED', 'header_totals': 'ROUNDED_2DP_FROM_ROUNDED_NET'})
        self.assertEqual(pr['record']['sent_price'], d['request_bodies']['persisted']['rows'][0]['price'])
        po.decode_order(json.dumps(s['po-readback'])); po.decode_ack(json.dumps(s['po-ack'])); self.assertEqual(s['po-ack']['idDocument'], order['id']); po.decode_preview(json.dumps(s['sim-vendor-preview']))
        st = p['stock_effect']; before, after, sim = (s[n]['stockReports'][0] for n in ('stock-before-p2', 'stock-after-po', 'stock-after-simulation'))
        self.assertEqual(st['before'], before); self.assertEqual(st['after'], after); self.assertEqual(po.assess_po_stock_effect({'before': before, 'after': after, 'quantity': st['quantity']}), st['verdict']); self.assertEqual(st['verdict'], 'ORDERED_ONLY')
        self.assertEqual(po.assess_po_stock_effect({'before': before, 'after': sim, 'quantity': 1.0}), 'NO_STOCK_EFFECT'); self.assertEqual(p['simulation']['stock_effect_verdict'], 'NO_STOCK_EFFECT')
        np_ = p['nonpersistence']; ids = lambda n: [h['id'] for h in s[n]['documentsHeaders']]
        self.assertEqual(np_['record'], {'ids_before': ids('orders-vendor-before'), 'ids_after': ids('orders-vendor-after-simulation'), 'stock_before': before, 'stock_after': sim})
        self.assertEqual(po.assess_nonpersistence(np_['record']), np_['verdict']); self.assertEqual(np_['verdict'], 'NOT_PERSISTED_BY_VENDOR_LIST_AND_STOCK')
        self.assertEqual(p['simulation']['contact_only']['errorCode'], 324); self.assertEqual(p['simulation']['contact_only']['http_status'], 400)
        ref = d['run']['synthetic_prefix'] + '-PO'; lk = p['lookup']
        for name, info in lk['pages'].items():
            r = po.assess_lookup(po.decode_headers(json.dumps(s[name])), ref, info['limit']); self.assertEqual(r['verdict'], info['verdict'], name)
        self.assertEqual({n: i['verdict'] for n, i in lk['pages'].items()}, {'po-lookup-vendor-name-status': 'UNIQUE_AFTER_CLIENT_REFERENCE_FILTER', 'po-lookup-limit1-offset0': 'UNIQUE_AFTER_CLIENT_REFERENCE_FILTER',
                                                                              'po-lookup-limit1-offset1': 'HOLD_PAGE_FULL_NOT_FOUND', 'po-lookup-reference-empty': 'HOLD_NOT_FOUND', 'po-lookup-idcontact-empty': 'HOLD_NOT_FOUND'})
        page = s['po-lookup-vendor-name-status']['documentsHeaders']; self.assertEqual([h['id'] for h in page], sorted((h['id'] for h in page), reverse=True)); self.assertTrue(lk['ordering_newest_first_observed'])
        self.assertEqual(lk['key_declared_before_oracle'], True); self.assertEqual(lk['oracle_after_lookup'], 'ack id compared after the lookup; ids equal')
        self.assertTrue(all(h['idContact'] is None for h in page)); self.assertEqual(sorted(i['totalCount'] for i in [s[n]['metadata'] for n in ('po-lookup-limit1-offset0', 'po-lookup-limit1-offset1')]), [1, 1])
    def test_programmatic_hashes_and_historical_pins(self):
        d = self.matrix(); samples_ = samples()
        self.assertEqual(set(samples_), {c['name'] for c in d['captures']})
        for c in d['captures']:
            digest = hashlib.sha256(json.dumps(samples_[c['name']], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(digest, c['sanitized_sha256']); self.assertNotEqual(digest, c['source_sha256']); self.assertRegex(c['source_sha256'], r'^[a-f0-9]{64}$')
            self.assertEqual(c['source_sha256'], next(o['source_sha256'] for o in d['observations'] if o['seq'] == c['source_seq']))
        for o in d['observations']:
            self.assertRegex(o['source_sha256'], r'^[a-f0-9]{64}$'); self.assertRegex(o['shape_sha256'], r'^[a-f0-9]{64}$'); self.assertNotRegex(o['endpoint_template'], r'/purchases/\d+/')
        for name, key in (('docs/r05a5-evidence.json', 'r05a5_matrix_sha256'), ('tests/fixtures/r05a5-owned-captures.json', 'r05a5_fixtures_sha256'), ('docs/r05a6-evidence.json', 'r05a6_matrix_sha256'),
                          ('tests/fixtures/r05a6-owned-captures.json', 'r05a6_fixtures_sha256')):
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), d['historical'][key])
        self.assertTrue(d['historical']['earlier_ledgers_and_intents_untouched'])
    def structured(self, value):
        prose = {'observed', 'note', 'limits', 'key', 'oracle_after_lookup', 'decoded_as'}
        if isinstance(value, dict): return {k: self.structured(v) for k, v in value.items() if k not in prose}
        if isinstance(value, list): return [self.structured(v) for v in value]
        return value
    def test_no_secret_or_foreign_data_in_committed_artifacts(self):
        d = self.matrix(); self.assertEqual(po.redaction_findings(samples()), [])
        self.assertEqual(po.redaction_findings(d['request_bodies']), []); self.assertEqual(po.redaction_findings(self.structured(d['points'])), [])
        blob = MATRIX.read_text() + (ROOT / 'docs/r05a7-sandbox-purchase-order-contract.md').read_text() + FIXTURES.read_text()
        for pattern in (r'eyJ[A-Za-z0-9_-]{8,}', r'(?i)bearer\s+[A-Za-z0-9._-]{8,}', r'[\w.+-]+@[\w-]+\.\w+', r'https?://\S+', r'(?i)"(access_token|refresh_token|password|client_id|cid|username)"\s*:'):
            self.assertIsNone(__import__('re').search(pattern, blob), pattern)
    def test_public_declaration_extracts_are_consistent_and_contrasted_with_observation(self):
        d = self.matrix(); pub = d['public_declaration']; self.assertRegex(pub['swagger_sha256'], r'^[a-f0-9]{64}$')
        self.assertEqual(pub['swagger_sha256'], json.loads((ROOT / 'docs/r05a6-evidence.json').read_text())['public_declaration']['swagger_sha256'])  # same acquired bytes as R05.a.6
        for e in pub['extracts']:
            self.assertEqual(hashlib.sha256(json.dumps(e['extract'], sort_keys=True, separators=(',', ':')).encode()).hexdigest(), e['extract_sha256']); self.assertTrue(e['pointer'].startswith('/'))
        ex = {e['name']: e['extract'] for e in pub['extracts']}
        self.assertEqual(ex['document-required'], ['docDate', 'idBu', 'idContact', 'idNumerator', 'payments', 'rows']); self.assertEqual(ex['row-required'], ['description', 'idMaterial', 'idPosType', 'price'])
        self.assertEqual(ex['purchase-orders-get-parameters'], ['docStatus', 'freeText', 'gtDocDateMillins', 'idContact', 'limit', 'neDocStatus', 'offset']); self.assertEqual(ex['purchase-orders-post-parameters'], ['body', 'simulation'])
        body = d['request_bodies']['persisted']
        self.assertIn('idContact', ex['document-required']); self.assertIsNone(body['idContact'])  # declared required, accepted as null when the string vendor id is sent: observation differs from declaration
        self.assertTrue(pub['observation_differs_from_declaration'])
    def test_optional_swagger_probe(self):
        path = os.environ.get('R05A7_SWAGGER_PATH')
        if not path: self.skipTest('private official swagger bytes not supplied; CI proves documentary consistency only')
        raw = Path(path).read_bytes(); d = self.matrix(); self.assertEqual(hashlib.sha256(raw).hexdigest(), d['public_declaration']['swagger_sha256'])
        s = json.loads(raw); ex = {e['name']: e['extract'] for e in d['public_declaration']['extracts']}
        self.assertEqual(sorted(s['definitions']['DocumentApi']['required']), ex['document-required']); self.assertEqual(sorted(s['definitions']['DocumentRowApi']['required']), ex['row-required'])
        self.assertEqual(sorted(x['name'] for x in s['paths']['/purchases/orders']['get']['parameters']), ex['purchase-orders-get-parameters'])
    def test_incidents_are_recorded_honestly(self):
        d = self.matrix(); self.assertTrue(d['incidents']); self.assertTrue(all(isinstance(x, str) and x for x in d['incidents']))
        self.assertTrue(d['remaining_blockers'])
    def test_cli_mutations_reject_false_promotion(self):
        if NO_MUTATIONS: return
        mutations = [lambda d: d['claims'].__setitem__('provider_compatibility', True),
                     lambda d: d['claims'].__setitem__('receipt_link_proved', True),
                     lambda d: d['claims'].__setitem__('lost_response_replay_authorized', True),
                     lambda d: d['adapter_may_rely_on'].append('server-idempotency'),
                     lambda d: d['adapter_must_not_rely_on'].remove('empty-lookup-is-absence'),
                     lambda d: d['ledger']['counts'].__setitem__('persisted_posts', 0),
                     lambda d: d['run']['caps'].__setitem__('persisted_POST', 9),
                     lambda d: d['run'].__setitem__('persisted_post_requests', 4),
                     lambda d: d['observations'][9].__setitem__('intent_written_utc', '9999-01-01T00:00:00+00:00'),
                     lambda d: d['ledger']['writes'][0].__setitem__('owned_prefix_in_body', False),
                     lambda d: d['ledger']['writes'][0].pop('flagged_simulation'),
                     lambda d: d['run'].__setitem__('synthetic_prefix', 'PROD-20261028'),
                     lambda d: d['request_bodies']['persisted'].__setitem__('reference', 'OTHER-PO'),
                     lambda d: d['request_bodies']['persisted']['rows'][0].__setitem__('price', 12.35),
                     lambda d: d['points']['stock_effect']['after'].__setitem__('quantity', 3.0),
                     lambda d: d['points']['stock_effect'].__setitem__('verdict', 'NO_STOCK_EFFECT'),
                     lambda d: d['points']['price_readback']['verdict'].__setitem__('header_totals', 'Q6_PRESERVED'),
                     lambda d: d['points']['vendor_identity']['record'].__setitem__('contact_only_rejected', False),
                     lambda d: d['points']['lookup']['pages']['po-lookup-reference-empty'].__setitem__('verdict', 'UNIQUE_AFTER_CLIENT_REFERENCE_FILTER'),
                     lambda d: d['incidents'].append('eyJhbGciOiJSUzI1NiJ9.payloadpart.signaturepart'),
                     lambda d: d['observations'][0].__setitem__('source_sha256', ''),
                     lambda d: d['historical'].__setitem__('r05a6_matrix_sha256', '0' * 64)]
        with tempfile.TemporaryDirectory(prefix='r05a7-', dir=os.environ.get('TMPDIR', tempfile.gettempdir())) as temp:
            for index, mutate in enumerate(mutations):
                d = self.matrix(); mutate(d); path = Path(temp) / 'matrix.json'; path.write_text(json.dumps(d))
                result = subprocess.run([sys.executable, '-I', __file__, '--matrix', str(path), '--no-mutations'], cwd=ROOT, capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 1, 'mutation %d was not rejected' % index); self.assertIn('FAIL:', result.stderr); self.assertNotIn('ERROR:', result.stderr)
if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--matrix', type=Path, default=MATRIX); parser.add_argument('--no-mutations', action='store_true')
    args, remaining = parser.parse_known_args(); MATRIX = args.matrix; NO_MUTATIONS = args.no_mutations
    unittest.main(argv=[sys.argv[0], *remaining])
