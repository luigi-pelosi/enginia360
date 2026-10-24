#!/usr/bin/env python3
"""Compare synthetic probes in memory. No importer, API or migration writes."""
from collections import Counter
import argparse
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('r06_synthetic', Path(__file__).with_name('r06_synthetic.py'))
assert spec and spec.loader
synthetic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(synthetic)


def compare(source, target):
    synthetic.validate(source)
    synthetic.validate(target)
    def normalized(rows):
        return sorted((dict(row, **{field: format(synthetic.number(row[field]), '.2f' if field == 'discount_percent' else '.6f')
                                   for field in synthetic.NUMBERS}) for row in rows), key=lambda row: row['source_id'])
    left, right = normalized(source['records']), normalized(target['records'])
    left_keys, right_keys = {r['source_id'] for r in left}, {r['source_id'] for r in right}
    duplicates = []
    for side, rows in (('source', left), ('target', right)):
        for key in ('source_id', 'internal_id'):
            counts = Counter(row[key] for row in rows)
            duplicates.extend({'side': side, 'key': key, 'value': value, 'count': count}
                              for value, count in sorted(counts.items()) if count > 1)
    left_index, right_index = {r['source_id']: r for r in left}, {r['source_id']: r for r in right}
    ambiguous = {d['value'] for d in duplicates if d['key'] == 'source_id'}
    shared = sorted((left_keys & right_keys)-ambiguous)
    provenance = [{'source_id': key, 'expected': left_index[key]['internal_id'], 'observed': right_index[key]['internal_id']}
                  for key in shared if left_index[key]['internal_id'] != right_index[key]['internal_id']]
    scope = [{'source_id': key, 'field': field, 'expected': left_index[key][field], 'observed': right_index[key][field]}
             for key in shared for field in ('tenant_id', 'company_id', 'site_id', 'warehouse_id', 'scope_id')
             if left_index[key][field] != right_index[key][field]]
    roles = [{'source_id': key, 'field': field, 'expected': left_index[key][field], 'observed': right_index[key][field]}
             for key in shared for field in ('payer_id', 'vehicle_owner_id')
             if left_index[key][field] != right_index[key][field]]
    other_fields = ('order_id', 'working_group_id', 'fiscal_identifier', 'kind', 'quantity', 'unit_price', 'discount_percent', 'tax_rate')
    fields = [{'source_id': key, 'field': field, 'expected': left_index[key][field], 'observed': right_index[key][field]}
              for key in shared for field in other_fields if left_index[key][field] != right_index[key][field]]
    deltas = {}
    for field, category in (('net_amount', 'amount_delta'), ('physical_stock', 'physical_stock_delta'),
                            ('reserved_stock', 'reserved_stock_delta')):
        deltas[category] = []
        for key in shared:
            expected, observed = synthetic.number(left_index[key][field]), synthetic.number(right_index[key][field])
            if expected != observed:
                deltas[category].append({'source_id': key, 'expected': format(expected, '.6f'),
                                         'observed': format(observed, '.6f'), 'delta': format(observed-expected, '.6f')})
    return {'ok': left == right and not duplicates, 'matched': len(shared),
            **deltas,
            'amount_groups': {'source': synthetic.amount_groups(left), 'target': synthetic.amount_groups(right)},
            'duplicate': duplicates,
            'provenance_mismatch': provenance,
            'scope_mismatch': scope,
            'role_mismatch': roles, 'field_mismatch': fields,
            'missing': sorted(left_keys-right_keys), 'unexpected': sorted(right_keys-left_keys),
            'counts': {'source': len(left), 'target': len(right), 'by_kind': {
                'source': dict(sorted(Counter(r['kind'] for r in left).items())),
                'target': dict(sorted(Counter(r['kind'] for r in right).items()))}},
            'proof': 'OFFLINE_TOOL_ONLY_NOT_MIGRATION_IDEMPOTENCE'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def read_probe(path):
    with Path(path).open('rb') as stream:
        payload = stream.read(10_000_001)
    if len(payload) > 10_000_000:
        raise ValueError('probe file exceeds offline bound')
    return json.loads(payload, object_pairs_hook=unique_object)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    try:
        report = compare(read_probe(args.source), read_probe(args.target))
        print(json.dumps(report, sort_keys=True))
        return 0 if report['ok'] else 1
    except (ValueError, TypeError, KeyError, OSError, UnicodeError):
        print('offline reconciliation refused: invalid synthetic input; no input content logged', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
