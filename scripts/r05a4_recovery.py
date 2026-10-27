#!/usr/bin/env python3
"""Offline decoder/validator of owned R05.a.4 recovery captures, not a provider adapter.

Order and stock captures reuse scripts/r05a3_captures.py. No network, retry,
idempotency inference or absence conclusion from an empty lookup.
"""
import json

def _count(value):
    return type(value) is int and value >= 0

def decode_lookup(text, key):
    value = json.loads(text)
    if not isinstance(value, dict) or value.get('responseCode') != 200 or value.get('errorCode') != 0:
        raise ValueError('successful captured business envelope required')
    rows, meta = value.get(key), value.get('metadata')
    if not isinstance(rows, list) or not isinstance(meta, dict) or not all(_count(meta.get(k)) for k in ('totalCount', 'offset', 'limit')):
        raise ValueError('captured lookup list and integer metadata required')
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] in ids:
            raise ValueError('distinct string row identity required')
        ids.add(row['id'])
        if key == 'vendors' and not isinstance((row.get('contact') or {}).get('name'), str):
            raise ValueError('captured contact name required')
    return value

def assess_recovery(record):
    if not isinstance(record.get('precommitted_key'), str) or not record['precommitted_key']:
        raise ValueError('pre-recorded correlation required')
    if record.get('response_discarded') is not True or record.get('lookup_used_server_id') is not False:
        raise ValueError('response must be discarded and lookup must not use the server identity')
    total, exact = record.get('lookup_total_count'), record.get('lookup_exact_matches')
    if not _count(total) or not _count(exact) or exact > total:
        raise ValueError('integer lookup counts required')
    if exact > 1:
        raise ValueError('ambiguous recovery: hold')
    if exact == 0:
        return 'HOLD_UNCERTAIN_NOT_ABSENCE'
    if record.get('oracle_read_after_lookup') is not True or record.get('oracle_id_equals_lookup_id') is not True:
        raise ValueError('oracle must be compared after lookup and agree')
    return 'RECOVERED'
