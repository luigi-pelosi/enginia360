#!/usr/bin/env python3
"""Deterministic invalid-for-production reconciliation probes, never runtime data."""
import hashlib
import json
import re
import argparse
import sys
from decimal import Decimal, ROUND_HALF_UP, localcontext

FORMAT = 'SYNTH_INVALID_FOR_PRODUCTION_V1'
PREFIX = 'SYNTH-INVALID-FOR-PRODUCTION-'
Q6 = Decimal('0.000001')
IDENTIFIERS = ('source_id', 'internal_id', 'tenant_id', 'company_id', 'site_id', 'warehouse_id',
               'scope_id', 'order_id', 'working_group_id', 'payer_id', 'vehicle_owner_id', 'fiscal_identifier')
NUMBERS = ('quantity', 'unit_price', 'discount_percent', 'tax_rate', 'net_amount', 'physical_stock', 'reserved_stock')


def number(value, scale=6, maximum='999999999999.999999', positive=False):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,'+str(scale)+'})?', value):
        raise ValueError('invalid invariant decimal')
    parsed = Decimal(value)
    if parsed > Decimal(maximum) or (positive and parsed == 0):
        raise ValueError('decimal outside documented bounds')
    return parsed


def validate(dataset):
    """Only this finite probe format is accepted, never real migration input.

    Duplicates and cross-record mismatches stay visible to reconciliation.
    """
    if (not isinstance(dataset, dict) or set(dataset) != {'format', 'records'} or dataset['format'] != FORMAT
            or not isinstance(dataset['records'], list) or len(dataset['records']) > 10000):
        raise ValueError('invalid synthetic envelope')
    for row in dataset['records']:
        if not isinstance(row, dict) or set(row) != set(IDENTIFIERS+NUMBERS+('kind',)):
            raise ValueError('invalid synthetic record fields')
        for key in IDENTIFIERS:
            if not isinstance(row[key], str) or not re.fullmatch(PREFIX+r'[A-Z0-9-]{1,96}', row[key]):
                raise ValueError('non-synthetic identifier refused')
        if row['kind'] not in ('Service', 'Part') or row['tax_rate'] != '22.000000':
            raise ValueError('unsupported synthetic enum or tax profile')
        for field in NUMBERS:
            number(row[field], 2 if field == 'discount_percent' else 6,
                   '100' if field == 'discount_percent' else
                   '999999.999999' if field in ('quantity', 'unit_price') else '999999999999.999999',
                   field == 'quantity')


def line_net(quantity, price, discount):
    """D67: row HALF_UP6, not currency/settlement rounding."""
    with localcontext() as context:
        context.prec = 60
        quantity = number(quantity, maximum='999999.999999', positive=True)
        price = number(price, maximum='999999.999999')
        discount = number(discount, 2, '100')
        return format((quantity*price*(1-discount/100)).quantize(Q6, rounding=ROUND_HALF_UP), '.6f')


def amount_groups(records):
    """Isolate documents and sum rounded rows per payer/rate before group IVA."""
    with localcontext() as context:
        context.prec = 60
        bases = {}
        for row in records:
            key = tuple(row[k] for k in ('tenant_id', 'company_id', 'order_id', 'payer_id', 'tax_rate'))
            bases[key] = bases.get(key, Decimal(0))+Decimal(row['net_amount'])
        result = {}
        for key, net in sorted(bases.items()):
            tax = (net*Decimal(key[-1])/100).quantize(Q6, rounding=ROUND_HALF_UP)
            result['|'.join(key)] = {'net': format(net, '.6f'), 'tax': format(tax, '.6f'), 'total': format(net+tax, '.6f')}
        return result


def canonical(dataset):
    return (json.dumps(dataset, sort_keys=True, separators=(',', ':'), ensure_ascii=True)+'\n').encode('ascii')


def digest(dataset):
    return hashlib.sha256(canonical(dataset)).hexdigest()


def generate(seed):
    if type(seed) is not int or not 0 <= seed <= 4294967295:
        raise ValueError('seed must be an unsigned 32-bit integer')
    tag = hashlib.sha256(str(seed).encode('ascii')).hexdigest()[:12].upper()
    def identifier(role, number):
        return f'{PREFIX}{tag}-{role}-{number}'
    records = []
    for number in range(8):
        tenant, company, document = number//4, number//2, number//2
        row = {key: identifier(role, n) for key, role, n in (
            ('source_id', 'SOURCE', number), ('internal_id', 'INTERNAL', number),
            ('tenant_id', 'TENANT', tenant), ('company_id', 'COMPANY', company),
            ('site_id', 'SITE', company), ('warehouse_id', 'WAREHOUSE', company),
            ('scope_id', 'SCOPE', company), ('order_id', 'ORDER', document),
            ('working_group_id', 'GROUP', document), ('payer_id', 'PAYER', document),
            ('vehicle_owner_id', 'OWNER', document), ('fiscal_identifier', 'INVALID-TAX', number))}
        row.update(kind='Service' if number % 2 == 0 else 'Part', quantity='1.000000',
                   unit_price='0.000002', discount_percent='0.00', tax_rate='22.000000',
                   net_amount='0.000002', physical_stock='3.000001', reserved_stock='1.000001')
        if document == 1:
            row.update(unit_price='0.000001', discount_percent='50.00')
        elif document == 2:
            row.update(quantity='2.123456', unit_price='10.000001', discount_percent='10.25')
        elif document == 3:
            row.update(unit_price='82.50' if number % 2 == 0 else '95.00',
                       discount_percent='10.00' if number % 2 == 0 else '5.00')
        row['net_amount'] = line_net(row['quantity'], row['unit_price'], row['discount_percent'])
        records.append(row)
    return {'format': FORMAT, 'records': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--summary', action='store_true')
    args = parser.parse_args()
    try:
        dataset = generate(args.seed)
        validate(dataset)
        report = {'format': FORMAT, 'records': len(dataset['records']), 'sha256': digest(dataset),
                  'amount_groups': amount_groups(dataset['records']), 'proof': 'OFFLINE_TOOL_ONLY'}
        print(canonical(report if args.summary else dataset).decode('ascii'), end='')
        return 0
    except ValueError:
        print('synthetic generation refused: invalid seed or probe', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
