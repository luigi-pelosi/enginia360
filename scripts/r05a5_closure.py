#!/usr/bin/env python3
"""Offline closure assessors for owned R05.a.5 observations, not a provider adapter.

Inputs are minimized owned observations. No network, retry, idempotency or draft inference:
every verdict is limited to the exact tested request shapes.
"""

def _count(value):
    return type(value) is int and value >= 0

def _stock(value):
    if not isinstance(value, dict) or any(isinstance(value.get(k), bool) or not isinstance(value.get(k), (int, float)) for k in ('quantity', 'orderedToSuppliersQty')):
        raise ValueError('numeric stock quantity and ordered quantity required')
    return value['quantity'], value['orderedToSuppliersQty']

def assess_simulation(record):
    if record.get('http_status') != 200 or record.get('business_error') != 0:
        raise ValueError('successful captured simulation envelope required')
    if not all(type(record.get(k)) is int for k in ('latest_id_before', 'latest_id_after')) or not _count(record.get('prefix_matches_after')):
        raise ValueError('integer list identities and prefix count required')
    persisted = (record.get('preview_document_id') is not None or record.get('preview_doc_number') not in ('', None)
                 or record['latest_id_after'] != record['latest_id_before'] or record['prefix_matches_after'] != 0
                 or _stock(record.get('stock_before')) != _stock(record.get('stock_after')))
    return 'PERSISTED_OR_STOCK_CHANGED_STOP' if persisted else 'NON_PERSISTENT_PREVIEW'

def assess_lookup_set(record):
    if record.get('precommitted_before_write') is not True or record.get('oracle_read_after_conclusion') is not True:
        raise ValueError('key must be pre-recorded and oracle read only after the lookup conclusion')
    items = {item['label']: item for item in record.get('lookups', [])}
    key = items.get(record.get('recovery_key'))
    if key is None:
        raise ValueError('declared recovery key must be one of the executed lookups')
    for item in items.values():
        if not _count(item.get('totalCount')) or not _count(item.get('exact_matches')) or item['exact_matches'] > item['totalCount']:
            raise ValueError('integer lookup counts required')
    empty = [label for label, item in items.items() if item['totalCount'] == 0]
    if key['totalCount'] > 1 or key['exact_matches'] > 1:
        verdict = 'HOLD_AMBIGUOUS'
    elif key['exact_matches'] == 0:
        verdict = 'HOLD_UNCERTAIN_NOT_ABSENCE'
    else:
        if record.get('oracle_id_equals_lookup_id') is not True:
            raise ValueError('oracle must agree with the lookup identity')
        verdict = 'RECOVERED_BY_PRECOMMITTED_KEY'
    return {'verdict': verdict, 'reliable': [label for label, item in items.items() if item['totalCount'] == 1 and item['exact_matches'] == 1],
            'empty_not_absence': empty}

def assess_receipt_link(record):
    sent, got = record.get('sent_rows'), record.get('receipt_rows')
    if not isinstance(sent, list) or not sent or not isinstance(got, list) or not got:
        raise ValueError('sent and returned receipt rows required')
    for key in ('order_status_before', 'order_status_after'):
        if not isinstance(record.get(key), str):
            raise ValueError('order status string required')
    rows_before, rows_after = record.get('order_row_status_before'), record.get('order_row_status_after')
    if not isinstance(rows_before, list) or not isinstance(rows_after, list) or len(rows_before) != len(rows_after):
        raise ValueError('source row states required')
    _stock(record.get('stock_before')); _stock(record.get('stock_after'))
    linked = any(row.get('saleorderref') is not None or row.get('saleorderposref') is not None or row.get('materialmovementref') is not None for row in got)
    source_changed = rows_before != rows_after or record['order_status_before'] != record['order_status_after']
    return 'LINK_PERSISTED' if linked or source_changed else 'LINK_NOT_PERSISTED_STANDALONE_RECEIPT'

def decode_order_headers(text):
    """Order header lookups carry integer document identities, unlike the string-id vendor lookup decoder."""
    import json
    value = json.loads(text)
    if not isinstance(value, dict) or value.get('responseCode') != 200 or value.get('errorCode') != 0:
        raise ValueError('successful captured business envelope required')
    rows, meta = value.get('documentsHeaders'), value.get('metadata')
    if not isinstance(rows, list) or not isinstance(meta, dict) or not all(_count(meta.get(k)) for k in ('totalCount', 'offset', 'limit')):
        raise ValueError('captured header list and integer metadata required')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] in ids or not isinstance(row.get('reference'), str):
            raise ValueError('distinct integer header identity and string reference required')
        ids.add(row['id'])
    return value

def exact_reference_matches(value, reference):
    return sum(row['reference'] == reference for row in value['documentsHeaders'])
