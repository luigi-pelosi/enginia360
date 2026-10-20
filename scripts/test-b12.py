#!/usr/bin/env python3
"""B12 real HTTP tracer for the internal technical invoice."""
import importlib.util
import json
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

spec = importlib.util.spec_from_file_location('b10', Path(__file__).with_name('test-b10.py'))
assert spec and spec.loader
b10 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b10)
b = b10.b

base = sys.argv[1].rstrip('/')
b.BASE = base
order, summary = b10.ready()
status, closure = b10.close(order, summary['revision'])
assert status == 201, (status, closure)
invoice_id = str(uuid.uuid4())
status, invoice = b.b02.request(base + '/api/v1/billing/workshop-invoices', b.alpha, 'POST', {
    'id': invoice_id,
    'orderId': order['id'],
    'documentTypeId': '11111111-7777-0000-0000-000000000010',
    'configurationVersion': 1,
    'documentDate': '2026-10-20',
    'currency': 'EUR',
    'reference': 'FV-001/2026',
})
assert status == 201, ('draft invoice missing', status, invoice)
assert invoice['id'] == invoice_id and invoice['orderId'] == order['id']
assert invoice['status'] == 'Draft' and invoice['summary'] == summary, json.dumps({'invoice': invoice, 'expectedSummary': summary}, sort_keys=True)
status, replay = b.b02.request(base + '/api/v1/billing/workshop-invoices', b.alpha, 'POST', {
    'id': invoice_id,
    'orderId': order['id'],
    'documentTypeId': '11111111-7777-0000-0000-000000000010',
    'configurationVersion': 1,
    'documentDate': '2026-10-20',
    'currency': 'EUR',
    'reference': 'FV-001/2026',
})
assert status == 200 and replay == invoice, ('draft replay is not idempotent', status, replay)
status, readback = b.b02.request(base + '/api/v1/billing/workshop-invoices/' + invoice_id, b.alpha)
assert status == 200 and readback == invoice
beta = b.b02.login(base, 'operatore-beta-sintetico', 'synthetic-beta-password')
status, hidden = b.b02.request(base + '/api/v1/billing/workshop-invoices/' + invoice_id, beta)
assert status == 404, ('cross-tenant invoice leaked', status, hidden)

confirmation_id = str(uuid.uuid4())
status, stale_configuration = b.b02.request(base + '/api/v1/billing/workshop-invoices/' + invoice_id + '/confirmation', b.alpha, 'POST', {
    'id': str(uuid.uuid4()),
    'configurationVersion': 2,
})
assert status == 409, ('stale confirmation configuration accepted', status, stale_configuration)
status, confirmed = b.b02.request(base + '/api/v1/billing/workshop-invoices/' + invoice_id + '/confirmation', b.alpha, 'POST', {
    'id': confirmation_id,
    'configurationVersion': 1,
})
assert status == 201, ('confirmation failed', status, confirmed)
assert confirmed['status'] == 'Confirmed' and confirmed['summary'] == summary
assert confirmed['issuer']['legalName'] == 'Società sintetica Alfa S.r.l.'
assert confirmed['recipient']['id'] == order['payerId']
status, confirmation_replay = b.b02.request(base + '/api/v1/billing/workshop-invoices/' + invoice_id + '/confirmation', b.alpha, 'POST', {
    'id': confirmation_id,
    'configurationVersion': 1,
})
assert status == 200 and confirmation_replay == confirmed
status, duplicate = b.b02.request(base + '/api/v1/billing/workshop-invoices/' + invoice_id + '/confirmation', b.alpha, 'POST', {
    'id': str(uuid.uuid4()),
    'configurationVersion': 1,
})
assert status == 409, ('second confirmation accepted', status, duplicate)
status, final_readback = b.b02.request(base + '/api/v1/billing/workshop-invoices/' + invoice_id, b.alpha)
assert status == 200 and final_readback == confirmed

status, concurrent_order = b.call('/orders', b.alpha, 'POST', b.body())
assert status == 201
status, _ = b.call(b10.order_path(concurrent_order) + '/lines', b.alpha, 'POST', b10.b06.b05.line_body('Service'))
assert status == 201
status, concurrent_summary = b.call(b10.order_path(concurrent_order) + '/commercial-summary', b.alpha)
assert status == 200
assert b10.close(concurrent_order, concurrent_summary['revision'])[0] == 201
barrier_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
barrier = Barrier(2)
def create_once(command_id):
    barrier.wait()
    return b.b02.request(base + '/api/v1/billing/workshop-invoices', b.alpha, 'POST', {
        'id': command_id, 'orderId': concurrent_order['id'],
        'documentTypeId': '11111111-7777-0000-0000-000000000010', 'configurationVersion': 1,
        'documentDate': '2026-10-20', 'currency': 'EUR', 'reference': 'FV-CONCURRENT/2026'})[0]
with ThreadPoolExecutor(max_workers=2) as pool:
    outcomes = sorted(pool.map(create_once, barrier_ids))
assert outcomes == [201, 409], ('concurrent allocation was not singular', outcomes)
print('PASS B12 draft, idempotent confirmation, tenant isolation, immutable q6 and singular concurrent allocation')
