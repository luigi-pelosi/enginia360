#!/usr/bin/env python3
"""B10 synthetic HTTP tests: durable technical closure, owner-local administrative request/outbox,
simulated external destination (D37/D40) and administrative closure. Real identity/HTTP/SQL only.

The request/simulator contract is a technical design exercised by these tests, not a new fiscal,
identity or business-policy decision.
"""
import importlib.util
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

spec = importlib.util.spec_from_file_location('b09', Path(__file__).with_name('test-b09.py'))
assert spec and spec.loader
b09 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b09)
b, b06, b07, b08 = b09.b, b09.b06, b09.b07, b09.b08
SIMULATOR = 'http://admin-simulator:8080'
ALPHA_OPERATOR = 'aaaaaaaa-0000-0000-0000-000000000001'
BETA_COMPANY = {'legalEntityId': b.C, 'siteId': '22222222-2222-2222-2222-222222220101', 'documentTypeId': '22222222-5555-0000-0000-000000000001',
                'payerId': '22222222-3333-0000-0000-000000000001', 'vehicleId': '22222222-4444-0000-0000-000000000001'}
REFERENCE = re.compile(r'^AMM-SIM-[0-9]{6}$')


def sim(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(SIMULATOR + path, data=data, method='GET' if payload is None else 'POST',
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=10) as response: return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error: return error.code, json.loads(error.read() or b'null')


def mode(value):
    assert sim('/control/mode', {'mode': value}) == (200, {'mode': value})


def received(request_id):
    return [x for x in sim('/control/requests')[1]['requests'] if x['requestId'] == request_id]


def order_path(order):
    return '/orders/' + order['id']


def ready(token=None, beta=False):
    """Persisted order whose configured carcass requirement is satisfied (gate Clear)."""
    token = token or b.alpha
    if beta:
        order, line, pick = b09.setup(b09.BETA_CARCASS_PART, token=token, warehouse=b09.BETA_WAREHOUSE, company=BETA_COMPANY)
        b09.install(order, line, pick, '2', token)
        status, receipt = b06.inventory(b09.returns(order, line, b09.BETA_WAREHOUSE)[0], token, 'POST', b09.command('2', b09.BETA_WAREHOUSE))
        assert status == 201, (status, receipt)
    else:
        status, order = b.call('/orders', token, 'POST', b.body())
        assert status == 201, ('valid synthetic order', status, order)
        status, service = b.call(order_path(order) + '/lines', token, 'POST', b06.b05.line_body('Service'))
        assert status == 201, ('valid service line', status, service)
        status, line = b.call(order_path(order) + '/lines', token, 'POST', b06.b05.line_body('Part', 1) | {'catalogItemId': b09.CARCASS_PART, 'quantity': '2'})
        assert status == 201, ('valid carcass component line', status, line)
        status, reservation = b06.inventory(b06.path(order, line) + '/reservations', token, 'POST', b06.command('2'))
        assert status == 201, ('valid reservation', status, reservation)
        status, pick = b06.inventory(b07.url(order, line, reservation), token, 'POST', b07.command('2'))
        assert status == 201, ('valid picking', status, pick)
        b09.install(order, line, pick, '2', token)
        status, receipt = b06.inventory(b09.returns(order, line)[0], token, 'POST', b09.command('2'))
        assert status == 201, ('valid full-residual carcass receipt', status, receipt)
    assert b09.gate(order, token)[1]['status'] == 'Clear'
    status, summary = b.call(order_path(order) + '/commercial-summary', token)
    assert status == 200, (status, summary)
    return order, summary


def close(order, revision, token=None, command_id=None):
    return b.call(order_path(order) + '/technical-closure', token or b.alpha, 'POST', {'id': command_id or str(uuid.uuid4()), 'expectedRevision': revision})


def submit(order, revision, token=None, command_id=None):
    return b.call(order_path(order) + '/administrative-requests', token or b.alpha, 'POST', {'id': command_id or str(uuid.uuid4()), 'expectedRevision': revision})


def close_administratively(order, token=None, command_id=None):
    return b.call(order_path(order) + '/administrative-closure', token or b.alpha, 'POST', {'id': command_id or str(uuid.uuid4())})


def state(order, token=None):
    return b.call(order_path(order) + '/closure-state', token or b.alpha)


def history(order, token=None):
    return b.call(order_path(order) + '/administrative-requests', token or b.alpha)


def immutable(request):
    return {k: v for k, v in request.items() if k != 'delivery'}


def wait(order, predicate, token=None, seconds=30):
    deadline = time.monotonic() + seconds
    while True:
        status, rows = history(order, token)
        assert status == 200 and len(rows) == 1, (status, rows)
        if predicate(rows[0]): return rows[0]
        assert time.monotonic() < deadline, ('timed out waiting for dispatcher', rows)
        time.sleep(0.25)


def closed_and_requested(sim_mode, token=None, beta=False):
    mode(sim_mode)
    order, summary = ready(token, beta)
    status, closure = close(order, summary['revision'], token)
    assert status == 201, (status, closure)
    status, saved = submit(order, summary['revision'], token)
    assert status == 201, (status, saved)
    return order, summary, closure, saved


def smoke():
    import re as pattern
    from urllib.request import urlopen
    b09.smoke()
    with urlopen(b.BASE, timeout=10) as response: html = response.read().decode()
    bundles = []
    for script in pattern.findall(r'<script[^>]+src="([^"]+)"', html):
        with urlopen(b.BASE + script, timeout=10) as response: bundles.append(response.read().decode())
    assert any('Chiudi tecnicamente' in bundle and 'Invia al gestionale amministrativo' in bundle for bundle in bundles), 'B10 private UI must be compiled'
    assert sim('/health') == (200, {'status': 'ok'})
    print('PASS B10 ready/system/HTML/compiled private administration UI via nginx HTTP; simulator healthy on the private network')


def request():
    mode('receive')
    order, summary = ready()
    assert summary['revision'] == 2, summary
    path = order_path(order)
    assert submit(order, 2)[1]['code'] == 'technical_closure_required', 'no request before durable technical closure'
    status, closure = close(order, 2)
    assert status == 201, ('valid technical closure with carcass requirement satisfied', status, closure)
    assert (closure['orderId'], closure['revision'], closure['operatorId']) == (order['id'], 2, ALPHA_OPERATOR), closure
    command = {'id': str(uuid.uuid4()), 'expectedRevision': 2}
    status, saved = b.call(path + '/administrative-requests', method='POST', payload=command)
    assert status == 201, ('B10 must durably accept the authorized external administrative request; source workflow is valid', status, saved)
    assert saved['id'] == command['id'] and saved['orderId'] == order['id'], saved
    assert saved['status'] == 'Pending' and saved['externalReference'] is None and saved['rejectionCode'] is None, ('acquisition is not business confirmation D40', saved)
    assert saved['summary'] == summary, ('persisted source snapshot must retain q6 values and provenance', saved)
    assert (saved['destination'], saved['destinationVersion'], saved['contractVersion']) == ('External', 1, 1), saved
    assert (saved['legalEntityId'], saved['siteId'], saved['operatorId']) == (b.A, b.SITE, ALPHA_OPERATOR), saved
    status, retry = b.call(path + '/administrative-requests', method='POST', payload=command)
    assert status == 200 and immutable(retry) == immutable(saved), ('same-ID exact retry returns the immutable acquisition once', status, retry)
    acquired = wait(order, lambda x: x['delivery']['state'] == 'Received')
    assert immutable(acquired) == immutable(saved) and acquired['delivery']['attempts'] == 1, acquired
    status, closure_state = state(order)
    assert status == 200 and closure_state['status'] == 'AwaitingAdministrativeConfirmation', closure_state
    assert closure_state['technicalClosure'] == closure and closure_state['administrativeClosure'] is None, closure_state
    status, refused = close_administratively(order)
    assert status == 409 and refused['code'] == 'external_confirmation_required', ('received is not completed processing', status, refused)
    assert b.call(path + '/commercial-summary') == (200, summary), 'request must not rewrite workshop values'
    [remote] = received(saved['id'])
    assert remote['posts'] == 1 and remote['status'] == 'Received', remote
    payload = remote['payload']
    assert set(payload) == {'contractVersion', 'requestId', 'orderId', 'companyId', 'siteId', 'payerId', 'currency',
                            'netAmount', 'taxAmount', 'total', 'lines'}, payload
    assert (payload['orderId'], payload['companyId'], payload['siteId'], payload['payerId']) == (order['id'], b.A, b.SITE, summary['payerId']), payload
    assert (payload['netAmount'], payload['taxAmount'], payload['total'], payload['currency']) == (summary['netAmount'], summary['taxAmount'], summary['total'], 'EUR'), payload
    assert [x['lineId'] for x in payload['lines']] == [x['id'] for x in summary['lines']], payload
    assert all(set(x) == {'lineId', 'kind', 'catalogItemId', 'quantity', 'unitPrice', 'discountPercent', 'netAmount', 'taxRate', 'payerId'} for x in payload['lines']), payload
    serialized = json.dumps(payload)
    for forbidden in ['Manodopera', 'Componente sintetico', 'catalogLabel', 'Alfa', 'tenant', 'Bearer']:
        assert forbidden not in serialized, ('minimized technical payload, no labels/names/tenant/token', forbidden)
    assert sim('/control/complete/' + saved['id'], {})[0] == 200
    confirmed = wait(order, lambda x: x['status'] != 'Pending')
    assert confirmed['status'] == 'Confirmed' and REFERENCE.match(confirmed['externalReference']), confirmed
    assert confirmed['delivery']['state'] == 'Completed' and confirmed['summary'] == summary, confirmed
    assert received(saved['id'])[0]['posts'] == 1, 'completion found by status query, never a second submission'
    status, admin = close_administratively(order)
    assert status == 201 and (admin['orderId'], admin['requestId'], admin['externalReference']) == (order['id'], saved['id'], confirmed['externalReference']), (status, admin)
    status, closure_state = state(order)
    assert closure_state['status'] == 'AdministrativelyClosed' and closure_state['administrativeClosure'] == admin, closure_state
    assert history(order) == (200, [confirmed]), 'confirmed history is stable'
    print('PASS B10 closure -> request+outbox -> Received (still blocked) -> Completed with stable reference -> administrative closure; q6 snapshot, retry, minimized payload, one submission')


def complete():
    order, summary, _, saved = closed_and_requested('complete')
    confirmed = wait(order, lambda x: x['status'] != 'Pending')
    assert confirmed['status'] == 'Confirmed' and REFERENCE.match(confirmed['externalReference']), confirmed
    other, _, _, other_saved = closed_and_requested('complete')
    other_confirmed = wait(other, lambda x: x['status'] != 'Pending')
    assert other_confirmed['externalReference'] != confirmed['externalReference'], 'stable reference per request'
    assert history(order)[1] == [confirmed], 'reference stable on reread'
    assert [x['posts'] for x in received(saved['id']) + received(other_saved['id'])] == [1, 1]
    assert close_administratively(order)[0] == 201
    print('PASS B10 immediate completed processing confirms with distinct stable references; one submission each')


def reject():
    order, summary, closure, saved = closed_and_requested('reject')
    rejected = wait(order, lambda x: x['status'] != 'Pending')
    assert (rejected['status'], rejected['rejectionCode'], rejected['externalReference']) == ('Rejected', 'synthetic_refusal', None), rejected
    assert rejected['delivery']['state'] == 'Rejected', rejected
    time.sleep(2)
    assert received(saved['id'])[0]['posts'] == 1, 'business refusal is never retried'
    status, refused = close_administratively(order)
    assert status == 409 and refused['code'] == 'external_confirmation_required', (status, refused)
    status, closure_state = state(order)
    assert closure_state['status'] == 'AdministrativeRejected' and closure_state['technicalClosure'] == closure, 'refusal visible, technical facts preserved'
    assert b.call(order_path(order) + '/commercial-summary') == (200, summary)
    print('PASS B10 business refusal visible with code, not retried, administrative closure blocked, technical closure preserved')


def closure_gate():
    order, line, pick = b09.setup()
    b09.install(order, line, pick, '1')
    status, refused = close(order, 1)
    assert status == 409 and refused['code'] == 'technical_requirements_pending', ('carcass outstanding blocks durable closure', status, refused)
    assert refused['gate']['status'] == 'Blocked' and refused['gate']['requirements'][0]['outstanding'] == '1', refused
    assert state(order)[1]['status'] == 'Open'
    post, read = b09.returns(order, line)
    assert b06.inventory(post, method='POST', payload=b09.command('1'))[0] == 201
    assert close(order, 0)[1]['code'] == 'revision_changed'
    command_id = str(uuid.uuid4())
    status, closure = close(order, 1, command_id=command_id)
    assert status == 201, (status, closure)
    assert close(order, 1, command_id=command_id) == (200, closure), 'same command returns the original closure'
    assert close(order, 0, command_id=command_id)[0] == 409, 'changed replay refused'
    status, again = close(order, 1)
    assert status == 409 and again['code'] == 'already_closed', (status, again)
    status, late = b08.call(b08.target(order, line, pick), None, 'POST', b07.command('1'))
    assert status == 409 and late['code'] == 'order_technically_closed', ('closed order refuses later installation', status, late)
    status, added = b.call(order_path(order) + '/lines', method='POST', payload=b06.b05.line_body('Service', 1))
    assert status == 409 and added['code'] == 'order_technically_closed', (status, added)
    assert b09.gate(order)[1]['status'] == 'Clear' and b06.inventory(read)[1]['requiredInstalled'] == '1'
    assert state(order)[1]['status'] == 'TechnicallyClosed'
    print('PASS B10 durable technical closure refused while carcass outstanding, revision checked, idempotent, later installation/line refused')


def closure_race():
    order, line, pick = b09.setup()
    b09.install(order, line, pick, '1')
    post, read = b09.returns(order, line)
    assert b06.inventory(post, method='POST', payload=b09.command('1'))[0] == 201
    barrier = Barrier(2)
    def act(kind):
        barrier.wait()
        if kind == 'close': return close(order, 1)
        return b08.call(b08.target(order, line, pick), None, 'POST', b07.command('1'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        closed, installed = pool.map(act, ['close', 'install'])
    assert (closed[0], installed[0]) in ((201, 409), (409, 201)), ('exactly one side wins', closed, installed)
    if closed[0] == 201:
        assert installed[1]['code'] == 'order_technically_closed', installed
        assert b06.inventory(read)[1]['requiredInstalled'] == '1' and b09.gate(order)[1]['status'] == 'Clear'
    else:
        assert closed[1]['code'] == 'technical_requirements_pending', closed
        assert b06.inventory(read)[1]['outstanding'] == '1' and state(order)[1]['status'] == 'Open'
    print('PASS B10 concurrent late installation vs technical closure serialized; closed order never bypasses a new carcass requirement:', closed[0], installed[0])


def idempotency():
    mode('receive')
    order, summary = ready()
    with ThreadPoolExecutor(max_workers=8) as pool:
        closures = list(pool.map(lambda _: close(order, 2), range(8)))
    assert sorted(x[0] for x in closures) == [201] + [409] * 7, closures
    command = {'id': str(uuid.uuid4()), 'expectedRevision': 2}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: b.call(order_path(order) + '/administrative-requests', method='POST', payload=command), range(8)))
    assert sorted(x[0] for x in results) == [200] * 7 + [201], results
    saved = next(x[1] for x in results if x[0] == 201)
    assert all(immutable(x[1]) == immutable(saved) for x in results), results
    assert submit(order, 1, command_id=command['id'])[0] == 409, 'changed replay refused'
    status, second = submit(order, 2)
    assert status == 409 and second['code'] == 'already_requested', (status, second)
    wait(order, lambda x: x['delivery']['state'] == 'Received')
    assert [x['posts'] for x in received(saved['id'])] == [1]
    beta = b.b02.login(b.BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    beta_order, beta_summary = ready(beta, beta=True)
    assert close(beta_order, 1, beta)[0] == 201
    assert submit(beta_order, 1, beta, command['id'])[0] == 409, 'foreign-tenant ID collision refused without disclosure'
    assert history(beta_order, beta) == (200, [])
    with ThreadPoolExecutor(max_workers=8) as pool:
        admin = list(pool.map(lambda _: close_administratively(order), range(8)))
    assert all(x[0] == 409 and x[1]['code'] == 'external_confirmation_required' for x in admin), admin
    print('PASS B10 eight concurrent closures one effect; eight identical request retries one request/outbox/submission; changed, second and cross-tenant IDs refused')


def invalid():
    order, summary = ready()
    base = order_path(order)
    bad = [{'id': str(uuid.UUID(int=0))}, {'id': 'x'}, {'id': None}, {'expectedRevision': -1}, {'expectedRevision': '2'},
           {'expectedRevision': None}, {'tenantId': b.C}, {'status': 'Confirmed'}, {'externalReference': 'AMM-SIM-000001'}, {'summary': {}}]
    for route in ['/technical-closure', '/administrative-requests']:
        for fields in bad:
            status, _ = b.call(base + route, method='POST', payload={'id': str(uuid.uuid4()), 'expectedRevision': 2} | fields)
            assert status == 400, (route, fields, status)
    for fields in [{'id': str(uuid.UUID(int=0))}, {'id': 'x'}, {'requestId': str(uuid.uuid4())}, {'externalReference': 'AMM-SIM-000001'}]:
        assert b.call(base + '/administrative-closure', method='POST', payload={'id': str(uuid.uuid4())} | fields)[0] == 400, fields
    assert state(order)[1]['status'] == 'Open' and history(order) == (200, [])
    print('PASS B10 strict command IDs/revisions; server-owned tenant/status/reference/summary fields rejected atomically')


def references():
    order, summary, closure, saved = closed_and_requested('receive')
    for username, password in [('operatore-beta-sintetico', 'synthetic-beta-password'), ('operatore-senza-membership', 'synthetic-no-membership'),
                               ('operatore-alfa-senza-lettura', 'synthetic-no-read')]:
        token = b.b02.login(b.BASE, username, password)
        assert history(order, token)[0] == 404 and state(order, token)[0] == 404, username
        for result in [close(order, 2, token), submit(order, 2, token), close_administratively(order, token)]:
            assert result[0] in (403, 404), (username, result)
    unknown = {'id': str(uuid.uuid4())}
    for result in [history(unknown), state(unknown), close(unknown, 0), submit(unknown, 0), close_administratively(unknown)]:
        assert result[0] == 404, result
    for route in ['/technical-closure', '/administrative-requests', '/administrative-closure', '/closure-state']:
        url = b.BASE + '/api/v1/workshop' + order_path(order) + route
        assert b.b02.request(url)[0] in (401, 405), route
        assert b.b02.request(url, None, 'POST', {'id': str(uuid.uuid4()), 'expectedRevision': 2})[0] in (401, 405), route
    assert b.b02.request(b.BASE + '/api/v1/workshop' + order_path(order) + '/administrative-requests')[0] == 401
    assert [immutable(x) for x in history(order)[1]] == [immutable(saved)]
    print('PASS B10 tenant/member/no-read/unknown order denied without disclosure; anonymous 401; nothing recorded')


def denied_scope():
    order, summary = ready()
    assert close(order, 2)[0] == 403
    assert submit(order, 2)[0] == 403
    assert close_administratively(order)[0] == 403
    assert history(order)[0] == 404 and state(order)[0] == 404
    print('PASS B10 same-tenant missing exact closure/request action or wrong site/warehouse/common-edit grant')


def read_only():
    order, summary = ready()
    assert close(order, 2)[0] == 201
    assert submit(order, 2)[0] == 403
    assert history(order) == (200, []) and state(order)[1]['status'] == 'TechnicallyClosed'
    print('PASS B10 read permission cannot create an administrative request')


def create_only():
    mode('receive')
    order, summary = ready()
    assert close(order, 2)[0] == 201
    assert submit(order, 2)[0] == 201
    assert history(order)[0] == 404 and state(order)[0] == 404
    print('PASS B10 create permission does not imply administrative history read')


def capability_disabled():
    order, summary = ready()
    assert close(order, 2)[0] == 201, 'technical closure is profile-agnostic Workshop behavior'
    assert submit(order, 2)[0] == 403
    assert history(order) == (200, [])
    print('PASS B10 disabled external-administration capability forbids new requests; history and technical closure unaffected')


def destination_missing():
    order, summary = ready()
    assert close(order, 2)[0] == 201
    status, result = submit(order, 2)
    assert status == 409 and result['code'] == 'administrative_destination_missing', (status, result)
    assert history(order) == (200, [])
    print('PASS B10 missing company administrative destination is refused, never defaulted')


def state_file():
    import os
    return Path(os.environ['B06_STATE_DIR'], 'b10-history.json')


def version_before():
    order, summary, closure, saved = closed_and_requested('receive')
    state_file().write_text(json.dumps(dict(order=order, saved=saved)))
    print('PASS B10 version fixture: request snapshots destination v1')


def paused_prepare():
    order, summary, closure, saved = closed_and_requested('receive')
    wait(order, lambda x: x['delivery']['state'] == 'Received')
    state_file().write_text(json.dumps(dict(order=order, saved=saved)))


def paused_check():
    fixture = json.loads(state_file().read_text())
    assert sim('/control/complete/' + fixture['saved']['id'], {})[0] == 200
    time.sleep(3)
    current = history(fixture['order'])[1][0]
    assert current['status'] == 'Pending', ('disabled capability must suspend queued worker uses, not only new API commands', current)
    assert close_administratively(fixture['order'])[0] == 409
    print('PASS B10 disabled capability suspends queued dispatch/poll; authorized history remains readable')


def paused_resume():
    fixture = json.loads(state_file().read_text())
    confirmed = wait(fixture['order'], lambda x: x['status'] == 'Confirmed')
    assert confirmed['summary'] == fixture['saved']['summary']
    print('PASS B10 reenabled capability resumes queued work without resubmission or snapshot changes')


def version_after():
    fixture = json.loads(state_file().read_text())
    [old] = history(fixture['order'])[1]
    assert immutable(old) == immutable(fixture['saved']) and old['destinationVersion'] == 1, old
    order, summary, closure, saved = closed_and_requested('receive')
    assert saved['destinationVersion'] == 2, saved
    print('PASS B10 later destination customizing v2 applies only to later requests; v1 snapshot preserved (D9)')


def tenants():
    beta = b.b02.login(b.BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    mode('complete')
    alpha_order, _, _, alpha_saved = closed_and_requested('complete')
    beta_order, beta_summary, _, beta_saved = closed_and_requested('complete', beta, beta=True)
    alpha_done = wait(alpha_order, lambda x: x['status'] != 'Pending')
    beta_done = wait(beta_order, lambda x: x['status'] != 'Pending', beta)
    assert alpha_done['status'] == beta_done['status'] == 'Confirmed', (alpha_done, beta_done)
    assert received(beta_saved['id'])[0]['payload']['companyId'] == b.C
    assert received(alpha_saved['id'])[0]['payload']['companyId'] == b.A
    assert history(beta_order)[0] == 404 and history(alpha_order, beta)[0] == 404
    assert close_administratively(beta_order, beta)[0] == 201
    print('PASS B10 dispatcher processes each tenant under its own verified envelope; results never cross tenants')


def race_file(name):
    import os
    return Path(os.environ['B06_STATE_DIR'], f'b10-race-{name}.json')


def race_prepare():
    order, line, pick = b09.setup()
    b09.install(order, line, pick, '1')
    assert b06.inventory(b09.returns(order, line)[0], method='POST', payload=b09.command('1'))[0] == 201
    assert b09.gate(order)[1]['status'] == 'Clear'
    race_file('fixture').write_text(json.dumps(dict(order=order, line=line, pick=pick)))
    print('PASS B10 race fixture: one installation covered, gate Clear')


def race_close():
    fixture = json.loads(race_file('fixture').read_text())
    race_file('close').write_text(json.dumps(close(fixture['order'], 1)))


def race_install():
    fixture = json.loads(race_file('fixture').read_text())
    race_file('install').write_text(json.dumps(b08.call(b08.target(fixture['order'], fixture['line'], fixture['pick']), None, 'POST', b07.command('1'))))


def race_verify(first):
    fixture = json.loads(race_file('fixture').read_text())
    order, line = fixture['order'], fixture['line']
    closed, installed = json.loads(race_file('close').read_text()), json.loads(race_file('install').read_text())
    read = b09.returns(order, line)[1]
    if first == 'close':
        assert closed[0] == 201 and installed[0] == 409 and installed[1]['code'] == 'order_technically_closed', (closed, installed)
        assert b06.inventory(read)[1]['requiredInstalled'] == '1' and state(order)[1]['status'] == 'TechnicallyClosed'
    else:
        assert installed[0] == 201 and closed[0] == 409 and closed[1]['code'] == 'technical_requirements_pending', (closed, installed)
        assert closed[1]['gate']['requirements'][0]['outstanding'] == '1', closed
        assert b06.inventory(read)[1]['outstanding'] == '1' and state(order)[1]['status'] == 'Open'
    print(f'PASS B10 controlled interleaving {first} first: the later request sees the committed winner; no closure bypasses a new carcass requirement')


def race_verify_close_first():
    race_verify('close')


def race_verify_install_first():
    race_verify('install')


if __name__ == '__main__':
    b.BASE = sys.argv[1]
    b.alpha = b.b02.login(b.BASE, 'operatore-alfa-sintetico', 'synthetic-alpha-password')
    globals()[sys.argv[2]]()
