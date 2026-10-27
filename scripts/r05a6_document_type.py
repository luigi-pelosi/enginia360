#!/usr/bin/env python3
"""Offline D85 document-type assessors for owned R05.a.6 observations, not a provider adapter.

Inputs are minimized owned observations. No network, retry, conversion or idempotency inference:
every verdict is limited to the exact tested request shapes. Stock, header and link decoding is
reused from the earlier R05.a.x modules.
"""

import importlib.util
import json
from pathlib import Path

def _load_captures():
    spec = importlib.util.spec_from_file_location('r05a3_captures', Path(__file__).with_name('r05a3_captures.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_STOCK_KEYS = ('quantity', 'reservedByOrdersQty', 'availableQty', 'orderedToSuppliersQty', 'stockForecastQty')
ORDER_TYPE, PROFORMA_TYPE, INVOICE_TYPE = 3, 33, 10
_RANK = {'SUITABLE': 0, 'SUITABLE-WITH-LIMITS': 1, 'UNSUITABLE': 2}
_CONVERSION = ('UI_CONTROL_OBSERVED', 'API_DOCUMENTED_ONLY', 'NONE')

def _num(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)

def _stock(value):
    if not isinstance(value, dict) or not all(_num(value.get(k)) for k in _STOCK_KEYS):
        raise ValueError('numeric stock quantities required')
    return {k: value[k] for k in _STOCK_KEYS}

def assess_stock_effect(record):
    """Classify a stock report pair for one document of the given quantity (reservation is not physical discharge)."""
    qty = record.get('quantity')
    if not _num(qty) or qty <= 0:
        raise ValueError('positive numeric document quantity required')
    before, after = _stock(record.get('before')), _stock(record.get('after'))
    if before == after:
        return 'NO_STOCK_EFFECT'
    if after['quantity'] < before['quantity']:
        return 'DISCHARGES_PHYSICAL'
    reserved_only = (after['quantity'] == before['quantity'] and after['orderedToSuppliersQty'] == before['orderedToSuppliersQty']
                     and after['reservedByOrdersQty'] == before['reservedByOrdersQty'] + qty
                     and after['availableQty'] == before['availableQty'] - qty and after['stockForecastQty'] == before['stockForecastQty'] - qty)
    return 'RESERVES_NO_DISCHARGE' if reserved_only else 'OTHER_CHANGE'

def assess_numbering(record):
    kind, number, fiscal = record.get('idDocumentType'), record.get('docNumber'), record.get('fiscal_invoice_number')
    if type(kind) is not int or kind not in (ORDER_TYPE, PROFORMA_TYPE, INVOICE_TYPE):
        raise ValueError('known integer document type required')
    if not isinstance(number, str) or not number or not isinstance(fiscal, str) or not fiscal:
        raise ValueError('string document numbers required')
    if kind == INVOICE_TYPE:
        return 'FISCAL_INVOICE_NUMBER'
    if number == fiscal:
        return 'COLLIDES_WITH_FISCAL_NUMBER'
    return 'ORDER_TYPE_NUMBER' if kind == ORDER_TYPE else 'PROFORMA_TYPE_OWN_NUMBER'

def assess_typed_lookup(value, id_document_type, reference):
    """Count headers of one document type with the exact reference in a decoded header list (use decode_order_headers first)."""
    rows = value['documentsHeaders']
    if any(type(row.get('idDocumentType')) is not int for row in rows):
        raise ValueError('integer document type required on every header')
    typed = sum(row['idDocumentType'] == id_document_type and row['reference'] == reference for row in rows)
    raw = value['metadata']['totalCount']
    if typed == 0:
        verdict = 'HOLD_NOT_FOUND'
    elif typed > 1:
        verdict = 'HOLD_AMBIGUOUS'
    else:
        verdict = 'UNIQUE_BY_SERVER_FILTER' if raw == 1 else 'UNIQUE_AFTER_CLIENT_TYPE_FILTER'
    return {'raw_total': raw, 'typed_matches': typed, 'verdict': verdict}

def assess_d85_type(record):
    for key in ('fiscal_invoice_number_assigned', 'physical_stock_discharged', 'retrievable_without_server_id', 'readback_exact', 'prior_document_required'):
        if type(record.get(key)) is not bool:
            raise ValueError('boolean %s required' % key)
    if record.get('manual_conversion') not in _CONVERSION:
        raise ValueError('known manual conversion evidence class required')
    limits = record.get('limits')
    if not isinstance(limits, list) or not all(isinstance(x, str) for x in limits):
        raise ValueError('limits list of strings required')
    if (record['fiscal_invoice_number_assigned'] or record['physical_stock_discharged'] or not record['retrievable_without_server_id']
            or not record['readback_exact'] or record['manual_conversion'] == 'NONE'):
        return 'UNSUITABLE'
    if limits or record['prior_document_required'] or record['manual_conversion'] != 'UI_CONTROL_OBSERVED':
        return 'SUITABLE-WITH-LIMITS'
    return 'SUITABLE'

def recommend(entries):
    """Evidence-based preference, never an owner decision: better verdict, then no prerequisite document, then observed UI conversion."""
    usable = [e for e in entries if e['verdict'] != 'UNSUITABLE']
    if not usable:
        return None
    best = min(usable, key=lambda e: (_RANK[e['verdict']], e['prior_document_required'], e['manual_conversion'] != 'UI_CONTROL_OBSERVED'))
    return {'type': best['type'], 'owner_may_overrule': True, 'evidence_class': 'evidence-based-recommendation-not-decision'}

def decode_document(text):
    """Decode a captured document, tolerating null quantity only on pure reference rows (idPosType 5, no material); other rules are the R05.a.3 decoder's."""
    value = json.loads(text)
    doc = value.get('document') if isinstance(value, dict) else None
    if not isinstance(doc, dict) or not isinstance(doc.get('rows'), list):
        return _load_captures().decode(text)
    kept = []
    for row in doc['rows']:
        if isinstance(row, dict) and row.get('idPosType') == 5 and 'quantity' in row and row['quantity'] is None:
            if row.get('idMaterial') is not None or type(row.get('idPos')) is not int:
                raise ValueError('null quantity is allowed only on a pure reference row')
            continue
        kept.append(row)
    stripped = dict(value, document=dict(doc, rows=kept))
    _load_captures().decode(json.dumps(stripped))
    ids = [row['idPos'] for row in doc['rows']]
    if len(set(ids)) != len(ids):
        raise ValueError('distinct integer row identity required; SKU is not identity')
    return value
