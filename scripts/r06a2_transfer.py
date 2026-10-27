#!/usr/bin/env python3
"""Staging-only transport wrapper. The accepted R06.a.1 dataset contract is unchanged."""
from collections import Counter
import importlib.util
import json
import re
from pathlib import Path


def load(filename):
    spec = importlib.util.spec_from_file_location(filename, Path(__file__).with_name(filename))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


synthetic = load('r06_synthetic.py')
reconciler = load('r06_reconcile.py')
FORMAT = 'R06A2_STAGING_ONLY_V1'
AUTHORITY = 'STAGING_PROBES_ONLY_NO_DOMAIN_AUTHORITY'
SCOPE_FIELDS = ('tenant_id', 'company_id', 'site_id', 'warehouse_id', 'scope_id')
MAX_BYTES = 2_000_000
MAX_RECORDS = 1000
HEADER = {'format', 'source_system', 'batch_id', 'revision', 'context', 'counts', 'dataset', 'sha256'}
ID_PATTERN = re.compile(synthetic.PREFIX + r'[A-Z0-9-]{1,96}')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def exact_q6(value, scale=6):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,11})\.[0-9]{' + str(scale) + '}', value):
        raise ValueError('numeric value is not a canonical decimal string')


def parse(payload):
    """Validate every untrusted byte before any storage call. Returns the unchanged document."""
    if not isinstance(payload, bytes) or len(payload) > MAX_BYTES:
        raise ValueError('envelope exceeds staging bound')
    try:
        document = json.loads(payload.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=lambda c: (_ for _ in ()).throw(ValueError('non-finite')))
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('malformed envelope') from None
    if not isinstance(document, dict) or set(document) != HEADER or document['format'] != FORMAT:
        raise ValueError('unsupported version or fields')
    for key in ('source_system', 'batch_id'):
        if not isinstance(document[key], str) or not ID_PATTERN.fullmatch(document[key]):
            raise ValueError('non-synthetic source identity')
    if type(document['revision']) is not int or not 1 <= document['revision'] <= 1_000_000:
        raise ValueError('invalid revision')
    dataset = document['dataset']
    if not isinstance(dataset, dict) or set(dataset) != {'format', 'records'} or not isinstance(dataset['records'], list):
        raise ValueError('invalid dataset')
    if len(dataset['records']) > MAX_RECORDS:
        raise ValueError('record limit exceeded')
    synthetic.validate(dataset)
    for row in dataset['records']:
        for key in synthetic.NUMBERS:
            exact_q6(row[key], 2 if key == 'discount_percent' else 6)
    records = dataset['records']
    for key in ('source_id', 'internal_id'):
        if len({row[key] for row in records}) != len(records):
            raise ValueError('duplicate identity')
    if [r['source_id'] for r in records] != sorted(r['source_id'] for r in records):
        raise ValueError('records must be canonical source order')
    counts = document['counts']
    if counts != {'records': len(records), 'by_kind': dict(sorted(Counter(r['kind'] for r in records).items()))}:
        raise ValueError('count mismatch')
    context = document['context']
    if not isinstance(context, dict) or set(context) != {'authority', 'scopes'}:
        raise ValueError('invalid context')
    if context['authority'] != AUTHORITY:
        raise ValueError('authority mismatch')
    if context['scopes'] != [dict(zip(SCOPE_FIELDS, s)) for s in sorted({tuple(r[k] for k in SCOPE_FIELDS) for r in records})]:
        raise ValueError('scope mismatch')
    if document['sha256'] != synthetic.digest({k: v for k, v in document.items() if k != 'sha256'}):
        raise ValueError('checksum mismatch')
    return document


def envelope(dataset):
    records = sorted(dataset['records'], key=lambda r: r['source_id'])
    normalized = [dict(row, **{k: format(synthetic.number(row[k]), '.2f' if k == 'discount_percent' else '.6f')
                              for k in synthetic.NUMBERS}) for row in records]
    result = {'format': FORMAT, 'source_system': synthetic.PREFIX + 'PROBE-GENERATOR-7',
              'batch_id': synthetic.PREFIX + 'BATCH-7', 'revision': 1,
              'context': {'authority': AUTHORITY, 'scopes': [dict(zip(SCOPE_FIELDS, scope)) for scope in sorted({
                  tuple(row[k] for k in SCOPE_FIELDS) for row in records})]},
              'counts': {'records': len(records), 'by_kind': dict(sorted(Counter(r['kind'] for r in records).items()))},
              'dataset': {'format': synthetic.FORMAT, 'records': normalized}}
    result['sha256'] = synthetic.digest(result)
    return result
