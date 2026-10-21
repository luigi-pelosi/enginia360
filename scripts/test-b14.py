#!/usr/bin/env python3
"""B14 joint-path tracer: the same Workshop logic serves the internal and the external destination."""
import importlib.util
import json
import sys
import uuid
from decimal import Decimal
from pathlib import Path

spec = importlib.util.spec_from_file_location('b13', Path(__file__).with_name('test-b13.py'))
assert spec and spec.loader


def load(name):
    loaded = importlib.util.spec_from_file_location(name, Path(__file__).with_name('test-' + name + '.py'))
    assert loaded and loaded.loader
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    return module


base = sys.argv[1].rstrip('/')
b10 = load('b10')
b = b10.b
b.BASE = base
TYPE = '11111111-7777-0000-0000-000000000010'
routes = []


def invoices(path='', method='GET', body=None):
    routes.append(('billing', method, '/api/v1/billing/workshop-invoices' + ('/{id}' if path else '')))
    return b.b02.request(base + '/api/v1/billing/workshop-invoices' + path, b.alpha, method, body)


def entries(path='', method='GET', body=None):
    routes.append(('accounting', method, '/api/v1/accounting/invoice-journal-entries' + ('/{id}' if path else '')))
    return b.b02.request(base + '/api/v1/accounting/invoice-journal-entries' + path, b.alpha, method, body)


def workshop_order(token, beta=False):
    """One technically closable order per destination, built by the identical Workshop surface."""
    if beta:
        order, summary = b10.ready(token, beta=True)
    else:
        status, order = b.call('/orders', token, 'POST', b.body())
        assert status == 201, (status, order)
        assert b.call(b10.order_path(order) + '/lines', token, 'POST', b10.b06.b05.line_body('Service'))[0] == 201
        status, part = b.call(b10.order_path(order) + '/lines', token, 'POST',
                              b10.b06.b05.line_body('Part', 1) | {'catalogItemId': b10.b09.CARCASS_PART, 'quantity': '1'})
        assert status == 201, (status, part)
        status, reservation = b10.b06.inventory(b10.b06.path(order, part) + '/reservations', token, 'POST',
                                                b10.b06.command('1'))
        assert status == 201, (status, reservation)
        status, pick = b10.b06.inventory(b10.b07.url(order, part, reservation), token, 'POST', b10.b07.command('1'))
        assert status == 201, (status, pick)
        b10.b09.install(order, part, pick, '1', token)
        assert b10.b06.inventory(b10.b09.returns(order, part)[0], token, 'POST', b10.b09.command('1'))[0] == 201
        status, summary = b.call(b10.order_path(order) + '/commercial-summary', token)
        assert status == 200, (status, summary)
    routes.append(('workshop', 'POST', '/api/v1/workshop/orders'))
    status, closure = b10.close(order, summary['revision'], token)
    assert status == 201, (status, closure)
    routes.append(('workshop', 'POST', '/api/v1/workshop/orders/{id}/technical-closure'))
    return order, summary


# Internal administrative destination: technical invoice and balanced journal entry.
internal_order, internal_summary = workshop_order(b.alpha)
assert internal_summary['total'] == '200.690000', internal_summary
status, invoice = invoices('', 'POST', {'id': str(uuid.uuid4()), 'orderId': internal_order['id'],
    'documentTypeId': TYPE, 'configurationVersion': 1, 'documentDate': '2026-10-20', 'currency': 'EUR',
    'reference': 'FV-B14/2026'})
assert status == 201, (status, invoice)
status, confirmed = invoices('/' + invoice['id'] + '/confirmation', 'POST',
                             {'id': str(uuid.uuid4()), 'configurationVersion': 1})
assert status == 201 and confirmed['status'] == 'Confirmed', (status, confirmed)
entry_id = str(uuid.uuid4())
status, entry = entries('', 'POST', {'id': entry_id, 'invoiceId': invoice['id'], 'chartVersion': 1})
assert status == 201 and entry['balanced'] and entry['invoiceLinkState'] == 'Linked', (status, entry)
assert Decimal(entry['totalDebit']) == Decimal(entry['totalCredit']) == Decimal('200.69'), entry
assert {line['accountCode'] for line in entry['lines']} == {'120100', '700100', '700200', '220100'}, entry
# The internal path must not create an external administrative request for the same order.
assert b10.history(internal_order, b.alpha) == (200, []), 'internal destination produced an external request'

# External simulated destination of a different company: same Workshop surface, administrative closure.
b10.mode('complete')
beta = b.b02.login(base, 'operatore-beta-sintetico', 'synthetic-beta-password')
external_order, external_summary = workshop_order(beta, beta=True)
status, request = b10.submit(external_order, external_summary['revision'], beta)
assert status == 201 and request['destination'] == 'External', (status, request)
external = b10.wait(external_order, lambda x: x['status'] != 'Pending', beta)
assert external['status'] == 'Confirmed' and external['externalReference'], external
status, administrative = b10.close_administratively(external_order, beta)
assert status == 201, (status, administrative)
status, closure_state = b10.state(external_order, beta)
assert closure_state['status'] == 'AdministrativelyClosed', closure_state
# The external path must not create an internal invoice for the same order.
assert invoices('', 'POST', {'id': str(uuid.uuid4()), 'orderId': external_order['id'], 'documentTypeId': TYPE,
    'configurationVersion': 1, 'documentDate': '2026-10-20', 'currency': 'EUR', 'reference': 'FV-X/2026'})[0] == 404

# Anonymous and foreign membership cannot read either internal resource.
for route in ['/api/v1/billing/workshop-invoices/' + invoice['id'],
              '/api/v1/accounting/invoice-journal-entries/' + entry_id]:
    assert b.b02.request(base + route)[0] == 401
    assert b.b02.request(base + route, beta)[0] == 404
assert b.b02.request(base + '/api/v1/accounting/invoice-journal-entries', b.alpha, 'POST',
                      {'id': str(uuid.UUID(int=0)), 'invoiceId': invoice['id'], 'chartVersion': 1})[0] == 400
print('PASS B14 real anonymous/foreign-tenant resource reads and malformed posting are denied')

workshop_routes = {route for module, method, route in routes if module == 'workshop'}
assert workshop_routes == {'/api/v1/workshop/orders', '/api/v1/workshop/orders/{id}/technical-closure'}, workshop_routes
print(json.dumps({'internalOrderId': internal_order['id'], 'invoiceId': invoice['id'], 'entryId': entry_id,
                  'externalOrderId': external_order['id'], 'externalRequestId': request['id'],
                  'externalReference': external['externalReference']}))
print('PASS B14 both administrative destinations driven by the same Workshop endpoints, with no cross-contamination')
