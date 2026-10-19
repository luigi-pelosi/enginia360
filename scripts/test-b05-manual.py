#!/usr/bin/env python3
"""Persistent B05 probe: fresh API records only; no SQL/config changes."""
import importlib.util
import json
from pathlib import Path
spec = importlib.util.spec_from_file_location('b05', Path(__file__).with_name('test-b05.py'))
assert spec and spec.loader
b05 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b05)
b05.b.context_and_types()
b05.catalog()
b05.variable()
b05.arithmetic()
b05.service()
b05.pair()
b05.negatives()
b05.concurrent()
order = b05.create_order()
payload = b05.line_body() | {'quantity':'2.123456','unitPrice':'10.000001','discountPercent':'10.25'}
path = '/orders/' + order['id'] + '/lines'
status, row = b05.b.call(path, method='POST', payload=payload)
assert status == 201 and row['netAmount'] == '19.058020'
assert b05.b.call(path, method='POST', payload=payload) == (200,row)
status, summary = b05.b.call('/orders/'+order['id']+'/commercial-summary')
assert status == 200 and summary['total'] == '23.250784'
print('DURABILITY_REFERENCE '+json.dumps({'order':order,'summary':summary},sort_keys=True))
print('PASS persistent B05 HTTPS non-destructive acceptance; no diagnostics or permission mutations')
