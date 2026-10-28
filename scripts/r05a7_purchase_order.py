#!/usr/bin/env python3
"""Offline R05.a.7 purchase-order assessors for owned sandbox observations, not a provider adapter.

Inputs are minimized owned observations. No network, retry, idempotency or receipt-link inference:
every verdict is limited to the exact tested request shapes. Empty or truncated lookups are holds, never absence.
"""
import datetime
import json
import math
import re
from decimal import Decimal, ROUND_HALF_UP

PO_TYPE = 2
_STOCK_KEYS = ('quantity', 'reservedByOrdersQty', 'availableQty', 'orderedToSuppliersQty', 'stockForecastQty')

def _num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def _int(value):
    return type(value) is int

def _str(value):
    return isinstance(value, str) and value != ''

def _envelope(text, code=200, error=0):
    value = json.loads(text)
    if not isinstance(value, dict) or value.get('responseCode') != code or value.get('errorCode') != error:
        raise ValueError('expected business envelope %s/%s' % (code, error))
    return value

def decode_ack(text):
    value = _envelope(text)
    if 'document' in value or not _int(value.get('idDocument')):
        raise ValueError('acknowledgement must carry only an integer document id')
    return value

def _rows(doc, persisted):
    rows = doc.get('rows')
    if not isinstance(rows, list) or not rows:
        raise ValueError('document rows required')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not _num(row.get('price')) or not _num(row.get('quantity')) or not isinstance(row.get('description'), str) or not _str(row.get('idMaterial')):
            raise ValueError('row price, quantity, description and material required')
        if persisted:
            if not _int(row.get('idPos')) or row['idPos'] in ids:
                raise ValueError('distinct integer row identity required; SKU is not identity')
            ids.add(row['idPos'])

def decode_preview(text):
    value = _envelope(text)
    doc = value.get('document')
    if not isinstance(doc, dict) or doc.get('id') is not None or doc.get('docNumber') != '':
        raise ValueError('a simulation preview has no id and no number')
    _rows(doc, False)
    return value

def decode_rejection(text):
    value = json.loads(text)
    if (not isinstance(value, dict) or not _int(value.get('responseCode')) or value['responseCode'] < 400 or not _int(value.get('errorCode')) or value['errorCode'] == 0
            or not _str(value.get('developerMessage'))):
        raise ValueError('rejection envelope with integer error code and message required')
    return value

def decode_order(text):
    value = _envelope(text)
    doc = value.get('document')
    if (not isinstance(doc, dict) or not _int(doc.get('id')) or doc.get('idDocumentType') != PO_TYPE or not _str(doc.get('idVendor')) or not _int(doc.get('idContact'))
            or not _str(doc.get('reference')) or not _str(doc.get('docStatus'))):
        raise ValueError('persisted purchase order identity, type, vendor, contact, reference and status required')
    for key in ('totalAmount', 'taxableAmount', 'vatAmount'):
        if not _num(doc.get(key)):
            raise ValueError('numeric %s required' % key)
    _rows(doc, True)
    return value

def decode_headers(text):
    value = _envelope(text)
    rows, meta = value.get('documentsHeaders'), value.get('metadata')
    if not isinstance(rows, list) or not isinstance(meta, dict) or not all(_int(meta.get(k)) for k in ('totalCount', 'offset', 'limit')):
        raise ValueError('header list with integer metadata required')
    for row in rows:
        if (not isinstance(row, dict) or not _int(row.get('id')) or row.get('idDocumentType') != PO_TYPE or not _str(row.get('idVendor')) or 'reference' not in row
                or not (row['reference'] is None or isinstance(row['reference'], str)) or not (row.get('idContact') is None or _int(row.get('idContact')))):
            raise ValueError('typed header with integer id, vendor string and reference key required')
    return value

def assess_vendor_identity(record):
    if not isinstance(record, dict) or not _str(record.get('vendor_id')) or not _str(record.get('contact_vendor_id')) or not _int(record.get('contact_id')) \
            or type(record.get('contact_only_rejected')) is not bool or not isinstance(record.get('sent'), dict) or not isinstance(record.get('order'), dict):
        raise ValueError('vendor identity record incomplete')
    sent, order = record['sent'], record['order']
    ok = (record['contact_only_rejected'] and sent.get('idVendor') == record['vendor_id'] and sent.get('idContact') is None
          and order.get('idVendor') == record['vendor_id'] and order.get('idContact') == record['contact_id'] and record['contact_vendor_id'] == record['vendor_id'])
    return 'VENDOR_STRING_ID_REQUIRED_CONTACT_SERVER_RESOLVED' if ok else 'MAPPING_UNPROVEN'

def _cents(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def assess_price_readback(record):
    if not isinstance(record, dict) or not _num(record.get('sent_price')) or not _num(record.get('quantity')) or record['quantity'] <= 0 or not _num(record.get('vat_rate')) \
            or not isinstance(record.get('document'), dict):
        raise ValueError('price readback record incomplete')
    doc = record['document']
    rows = doc.get('rows')
    if not isinstance(rows, list) or len(rows) != 1 or not _num(rows[0].get('price')):
        raise ValueError('exactly one priced row required')
    row = 'Q6_PRESERVED' if rows[0]['price'] == record['sent_price'] else 'ROW_PRICE_ALTERED'
    for key in ('totalAmount', 'taxableAmount', 'vatAmount'):
        if not _num(doc.get(key)):
            raise ValueError('numeric %s required' % key)
    net = _cents(Decimal(str(record['sent_price'])) * Decimal(str(record['quantity'])))
    vat = _cents(net * Decimal(str(record['vat_rate'])) / 100)
    consistent = _cents(doc['taxableAmount']) == net == Decimal(str(doc['taxableAmount'])) and Decimal(str(doc['vatAmount'])) == vat and Decimal(str(doc['totalAmount'])) == net + vat
    return {'row_price': row, 'header_totals': 'ROUNDED_2DP_FROM_ROUNDED_NET' if consistent else 'TOTALS_INCONSISTENT'}

def _stock(value):
    if not isinstance(value, dict) or not all(_num(value.get(k)) for k in _STOCK_KEYS):
        raise ValueError('numeric stock quantities required')
    return {k: value[k] for k in _STOCK_KEYS}

def assess_po_stock_effect(record):
    qty = record.get('quantity') if isinstance(record, dict) else None
    if not _num(qty) or qty <= 0:
        raise ValueError('positive numeric document quantity required')
    before, after = _stock(record.get('before')), _stock(record.get('after'))
    if before == after:
        return 'NO_STOCK_EFFECT'
    if after['quantity'] != before['quantity']:
        return 'PHYSICAL_CHANGED'
    if after['reservedByOrdersQty'] != before['reservedByOrdersQty'] or after['availableQty'] != before['availableQty']:
        return 'RESERVATION_CHANGED'
    ordered = after['orderedToSuppliersQty'] == before['orderedToSuppliersQty'] + qty and after['stockForecastQty'] == before['stockForecastQty'] + qty
    return 'ORDERED_ONLY' if ordered else 'OTHER_CHANGE'

def assess_nonpersistence(record):
    ids = []
    for key in ('ids_before', 'ids_after'):
        value = record.get(key) if isinstance(record, dict) else None
        if not isinstance(value, list) or not all(_int(x) for x in value):
            raise ValueError('integer id lists required')
        ids.append(value)
    same = ids[0] == ids[1] and _stock(record.get('stock_before')) == _stock(record.get('stock_after'))
    return 'NOT_PERSISTED_BY_VENDOR_LIST_AND_STOCK' if same else 'CHANGED'

def assess_lookup(value, reference, limit):
    if not _str(reference) or not _int(limit) or limit <= 0:
        raise ValueError('reference and positive integer limit required')
    rows = value['documentsHeaders']
    matches = sum(row['reference'] == reference for row in rows)
    full = len(rows) >= limit
    if matches == 0:
        verdict = 'HOLD_PAGE_FULL_NOT_FOUND' if full else 'HOLD_NOT_FOUND'
    else:
        verdict = 'UNIQUE_AFTER_CLIENT_REFERENCE_FILTER' if matches == 1 else 'HOLD_AMBIGUOUS'
    return {'returned': len(rows), 'exact_matches': matches, 'total_count_equals_returned': value['metadata']['totalCount'] == len(rows), 'page_full': full, 'verdict': verdict}

def assess_request_body(body, prefix):
    if not isinstance(body, dict) or not _str(prefix):
        raise ValueError('request body object and prefix required')
    if body.get('idDocumentType') != PO_TYPE or 'idContact' not in body or not _str(body.get('idVendor')):
        raise ValueError('purchase order type, idContact key and string idVendor required')
    if not _str(body.get('docDate')) or not _str(body.get('idBu')) or not _int(body.get('idNumerator')) or not isinstance(body.get('payments'), list):
        raise ValueError('docDate, idBu, idNumerator and payments required')
    if not isinstance(body.get('reference'), str) or not body['reference'].startswith(prefix) or prefix not in str(body.get('note')):
        raise ValueError('owned prefix required on reference and note')
    rows = body.get('rows')
    if not isinstance(rows, list) or not rows:
        raise ValueError('rows required')
    for row in rows:
        if (not isinstance(row, dict) or not _str(row.get('description')) or not _str(row.get('idMaterial')) or not _int(row.get('idPosType')) or not _num(row.get('price'))
                or not _num(row.get('quantity')) or row['quantity'] <= 0):
            raise ValueError('row description, material, position type, numeric price and positive quantity required')
    return 'OBSERVED_REQUIRED_FIELDS_PRESENT'

_FORBIDDEN_KEYS = re.compile(r'(?i)^(access_token|refresh_token|password|client_id|cid|authorization|username|token|secret)$')
_ALLOWED_LEAF = re.compile(r'^(|E360-SB-R05A\d-\d{8}T\d{6}Z[-A-Za-z0-9 ;]*|owned-[A-Za-z0-9-]+|[A-Z][A-Z0-9_]{0,60}|[A-Z]{1,3}[0-9]{1,3}|[0-9]{1,13}|Unica rata|docStatus input ignored warning present|'
                           r'Errore nelle righe del documento: Il campo Fornitore è obbligatorio|[A-Za-z]+Qty|[A-Za-z]+)$')
_FORBIDDEN_LEAF = re.compile(r'(?i)(eyJ[A-Za-z0-9_-]{8,}|bearer\s|@|://|password|secret|token|\b\d{1,3}(\.\d{1,3}){3}\b)')

def redaction_findings(value, path=''):
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if _FORBIDDEN_KEYS.match(str(key)):
                found.append('%s/%s: forbidden key' % (path, key))
            found.extend(redaction_findings(item, '%s/%s' % (path, key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(redaction_findings(item, '%s/%d' % (path, index)))
    elif isinstance(value, str):
        if _FORBIDDEN_LEAF.search(value) or not _ALLOWED_LEAF.match(value):
            found.append('%s: string outside the owned-alias allowlist' % path)
    return found

def _seconds(iso):
    return datetime.datetime.fromisoformat(iso).timestamp()

def assess_ledger(matrix):
    """Return a list of ledger problems (empty means consistent): chronology, caps, ownership and counts."""
    problems = []
    run, ledger, obs = matrix['run'], matrix['ledger'], matrix['observations']
    caps = run['caps']
    posts = [o for o in obs if o['method'] == 'POST']
    persisted = [o for o in posts if o['mode'] == 'PERSISTED']
    simulated = [o for o in posts if o['mode'] == 'SIMULATION']
    if [o['seq'] for o in obs] != list(range(1, len(obs) + 1)):
        problems.append('observation sequence is not contiguous')
    if len(obs) != run['business_requests'] or len(persisted) != run['persisted_post_requests'] or len(simulated) != run['simulation_post_requests']:
        problems.append('request counts do not match observations')
    if len(persisted) > caps['persisted_POST'] or len(simulated) > caps['simulation_POST'] or len(obs) > caps['business_requests']:
        problems.append('cap exceeded')
    if len(ledger['writes']) != len(posts) or ledger['counts'] != {'write_intents': len(posts), 'persisted_posts': len(persisted), 'simulation_posts': len(simulated), 'verified_objects': len(ledger['objects'])}:
        problems.append('ledger counts are not derived from observations')
    previous = ''
    for o in obs:
        if not (o['intent_written_utc'] < o['response_recorded_utc']):
            problems.append('seq %s: intent not recorded before the response' % o['seq'])
        if o['method'] == 'POST' and _seconds(o['response_recorded_utc']) - _seconds(o['intent_written_utc']) < 0.1:
            problems.append('seq %s: write response not separated from its intent' % o['seq'])
        if o['intent_written_utc'] < previous:
            problems.append('seq %s: out of chronological order' % o['seq'])
        previous = o['intent_written_utc']
        if o['method'] != 'GET' and o['mode'] not in ('PERSISTED', 'SIMULATION'):
            problems.append('seq %s: write without declared mode' % o['seq'])
    by_seq = {o['seq']: o for o in obs}
    for w in ledger['writes']:
        o = by_seq.get(w['seq'])
        if o is None or o['method'] != 'POST' or o['mode'] != w['mode']:
            problems.append('write %s has no matching POST observation' % w.get('seq'))
            continue
        if w['state'] != 'RESPONSE_OBSERVED' or not w.get('owned_prefix_in_body') or not re.fullmatch(r'[a-f0-9]{64}', w.get('intent_body_sha256', '')):
            problems.append('write %s lacks recorded state, owned prefix or intent hash' % w['seq'])
        if w['mode'] == 'SIMULATION' and not w.get('flagged_simulation'):
            problems.append('simulation POST %s is not flagged' % w['seq'])
    for obj in ledger['objects']:
        create = by_seq.get(obj['create_seq'])
        if create is None or create['mode'] != 'PERSISTED' or obj['readback_seq'] <= obj['create_seq']:
            problems.append('object %s is not a verified persisted create followed by a readback' % obj.get('owned_alias'))
    if not run['synthetic_prefix'].startswith('E360-SB-'):
        problems.append('prefix is not the owned E360-SB prefix')
    return problems
