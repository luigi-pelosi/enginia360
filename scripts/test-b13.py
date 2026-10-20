#!/usr/bin/env python3
"""B13 real HTTP tracer: balanced F04 journal entry from a confirmed internal invoice."""
import importlib.util
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path

spec = importlib.util.spec_from_file_location('b10', Path(__file__).with_name('test-b10.py'))
assert spec and spec.loader
b10 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b10)
b = b10.b
base = sys.argv[1].rstrip('/')
b.BASE = base
TYPE = '11111111-7777-0000-0000-000000000010'
F04 = {'120100': ('200.69', '0'), '700100': ('0', '74.25'), '700200': ('0', '90.25'), '220100': ('0', '36.19')}


def invoices(path='', method='GET', body=None, token=None):
    return b.b02.request(base + '/api/v1/billing/workshop-invoices' + path, token or b.alpha, method, body)


def entries(path='', method='GET', body=None, token=None):
    return b.b02.request(base + '/api/v1/accounting/invoice-journal-entries' + path, token or b.alpha, method, body)


def confirmed_invoice(reference='FV-001/2026'):
    """Case 001 composition: service 74.25 + part 90.25 net, 36.19 aggregated tax, 200.69 total."""
    status, order = b.call('/orders', b.alpha, 'POST', b.body())
    assert status == 201, (status, order)
    status, service = b.call(b10.order_path(order) + '/lines', b.alpha, 'POST', b10.b06.b05.line_body('Service'))
    assert status == 201, (status, service)
    status, part = b.call(b10.order_path(order) + '/lines', b.alpha, 'POST',
                          b10.b06.b05.line_body('Part', 1) | {'catalogItemId': b10.b09.CARCASS_PART, 'quantity': '1'})
    assert status == 201, (status, part)
    status, reservation = b10.b06.inventory(b10.b06.path(order, part) + '/reservations', b.alpha, 'POST',
                                            b10.b06.command('1'))
    assert status == 201, (status, reservation)
    status, pick = b10.b06.inventory(b10.b07.url(order, part, reservation), b.alpha, 'POST', b10.b07.command('1'))
    assert status == 201, (status, pick)
    b10.b09.install(order, part, pick, '1', b.alpha)
    status, receipt = b10.b06.inventory(b10.b09.returns(order, part)[0], b.alpha, 'POST', b10.b09.command('1'))
    assert status == 201, (status, receipt)
    assert b10.b09.gate(order, b.alpha)[1]['status'] == 'Clear'
    status, summary = b.call(b10.order_path(order) + '/commercial-summary', b.alpha)
    assert status == 200 and summary['total'] == '200.690000', (status, summary)
    assert b10.close(order, summary['revision'])[0] == 201
    status, invoice = invoices('', 'POST', {'id': str(uuid.uuid4()), 'orderId': order['id'], 'documentTypeId': TYPE,
        'configurationVersion': 1, 'documentDate': '2026-10-20', 'currency': 'EUR', 'reference': reference})
    assert status == 201, (status, invoice)
    return invoice


def confirm(invoice):
    status, confirmation = invoices('/' + invoice['id'] + '/confirmation', 'POST',
                                    {'id': str(uuid.uuid4()), 'configurationVersion': 1})
    assert status == 201 and confirmation['status'] == 'Confirmed', (status, confirmation)
    return confirmation


invoice = confirm(confirmed_invoice())
assert invoice['summary']['total'] == '200.690000', invoice['summary']
assert invoice['journalEntryId'] is None, 'journal link exists before any posting'
entry_id = str(uuid.uuid4())
command = {'id': entry_id, 'invoiceId': invoice['id'], 'chartVersion': 1}
status, entry = entries('', 'POST', command)
assert status == 201, ('journal entry missing', status, entry)
posted = {line['accountCode']: (line['debit'], line['credit']) for line in entry['lines']}
assert set(posted) == set(F04), posted
for code, (debit, credit) in F04.items():
    assert Decimal(posted[code][0]) == Decimal(debit) and Decimal(posted[code][1]) == Decimal(credit), (code, posted[code])
assert entry['balanced'] and entry['difference'] == '0.000000'
assert Decimal(entry['totalDebit']) == Decimal(entry['totalCredit']) == Decimal('200.69')
assert entry['invoiceReference'] == 'FV-001/2026' and entry['invoiceId'] == invoice['id']
assert entry['orderId'] == invoice['orderId'] and entry['currency'] == 'EUR'
assert entry['invoiceLinkState'] == 'Linked'

status, replay = entries('', 'POST', command)
assert status == 200 and replay == entry, ('posting is not idempotent', status, replay)
status, readback = entries('/' + entry_id)
assert status == 200 and readback == entry
status, second = entries('', 'POST', {'id': str(uuid.uuid4()), 'invoiceId': invoice['id'], 'chartVersion': 1})
assert status == 409, ('invoice posted twice', status, second)
status, invoice_after = invoices('/' + invoice['id'])
assert status == 200 and invoice_after['journalEntryId'] == entry_id, ('invoice link missing', invoice_after)
assert invoice_after['summary'] == invoice['summary'] and invoice_after['status'] == 'Confirmed', 'confirmed invoice mutated by posting'

beta = b.b02.login(base, 'operatore-beta-sintetico', 'synthetic-beta-password')
assert entries('/' + entry_id, token=beta)[0] == 404, 'cross-tenant journal entry leaked'
assert entries('', 'POST', {'id': str(uuid.uuid4()), 'invoiceId': invoice['id'], 'chartVersion': 1}, token=beta)[0] == 404
for changed in [{'id': '00000000-0000-0000-0000-000000000000'}, {'chartVersion': 0}, {'extra': 1}]:
    assert entries('', 'POST', command | changed)[0] == 400, changed
assert entries('', 'POST', {'id': str(uuid.uuid4()), 'invoiceId': str(uuid.uuid4()), 'chartVersion': 1})[0] == 404
assert entries('', 'POST', {'id': str(uuid.uuid4()), 'invoiceId': invoice['id'], 'chartVersion': 9})[0] == 409
draft = confirmed_invoice('FV-DRAFT/2026')
assert entries('', 'POST', {'id': str(uuid.uuid4()), 'invoiceId': draft['id'], 'chartVersion': 1})[0] == 404, \
    'draft invoice must not be postable'
print(json.dumps({'entryId': entry_id, 'invoiceId': invoice['id'], 'orderId': invoice['orderId'],
                  'draftInvoiceId': draft['id']}))
print('PASS B13 balanced F04 journal entry, idempotent posting, invoice link, isolation, untrusted input and draft refusal')
