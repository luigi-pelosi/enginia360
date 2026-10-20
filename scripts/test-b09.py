#!/usr/bin/env python3
"""B09 synthetic HTTP tests: D73 full-residual carcass return and technical-closure gate."""
import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path
spec = importlib.util.spec_from_file_location('b08', Path(__file__).with_name('test-b08.py'))
assert spec and spec.loader
b08 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b08)
b07, b06, b = b08.b07, b08.b06, b08.b
CARCASS_PART = '11111111-7777-0000-0000-000000000003'
BETA_CARCASS_PART = '22222222-7777-0000-0000-000000000003'
BETA_WAREHOUSE = '22222222-2222-2222-2222-222222220101'
OTHER_WAREHOUSE = '11111111-1111-1111-1111-111111100102'
SITE_ONLY_WAREHOUSE = '11111111-1111-1111-1111-111111100301'

def setup(item=CARCASS_PART, picked='2', token=None, warehouse=b06.WAREHOUSE, company=None):
    token = token or b.alpha
    payload = b.body() if company is None else b.body() | company
    status, order = b.call('/orders', token, 'POST', payload)
    assert status == 201, (status, order)
    status, line = b.call('/orders/'+order['id']+'/lines', token, 'POST', b06.b05.line_body('Part') | {'catalogItemId': item, 'quantity': '3'})
    assert status == 201, (status, line)
    status, reservation = b06.inventory(b06.path(order, line)+'/reservations', token, 'POST', b06.command(picked, warehouse))
    assert status == 201, (status, reservation)
    status, pick = b06.inventory(b07.url(order, line, reservation), token, 'POST', b07.command(picked))
    assert status == 201, (status, pick)
    return order, line, pick

def install(order, line, pick, quantity='1', token=None):
    status, result = b08.call(b08.target(order, line, pick), token, 'POST', b07.command(quantity))
    assert status == 201 and result['stockEffect'] == 'Consumed', (status, result)
    return result['installation']

def returns(order, line, warehouse=b06.WAREHOUSE):
    return b06.path(order, line)+'/carcass-returns', b06.path(order, line)+'/carcass-returns?warehouseId='+warehouse

def command(quantity='2', warehouse=b06.WAREHOUSE, description='Carcassa sostituita sintetica'):
    return dict(id=str(uuid.uuid4()), warehouseId=warehouse, quantity=quantity, description=description)

def gate(order, token=None):
    return b.call('/orders/'+order['id']+'/technical-closure-gate', token or b.alpha)

def stock(order, line, item_warehouse=b06.WAREHOUSE):
    status, value = b06.inventory(b06.path(order, line)+'?warehouseId='+item_warehouse)
    assert status == 200, (status, value)
    return value['physical'], value['available'], value['activeCommitted'], value['consumed']

def smoke():
    import re
    from urllib.request import urlopen
    b08.smoke()
    with urlopen(b.BASE, timeout=10) as response: html = response.read().decode()
    bundles = []
    for script in re.findall(r'<script[^>]+src="([^"]+)"', html):
        with urlopen(b.BASE+script, timeout=10) as response: bundles.append(response.read().decode())
    assert any('Rientro carcassa' in bundle for bundle in bundles), 'B09 private UI must actually be compiled'
    print('PASS B09 ready/system/HTML/compiled private carcass-return UI via nginx HTTP')

def full():
    order, line, pick = setup()
    first, second = install(order, line, pick), install(order, line, pick)
    assert first['carcassReturnRequired'] is True and first['carcassPolicyVersion'] == 1, first
    post, read = returns(order, line)
    status, closure = gate(order)
    assert status == 200 and closure['status'] == 'Blocked', ('two installed with required carcass block technical closure', status, closure)
    assert closure['requirements'] == [dict(lineId=line['id'], catalogItemId=CARCASS_PART, requiredInstalled='2', returned='0', outstanding='2')], closure
    before = stock(order, line)
    for partial in ['1', '1.999999', '3', '2.000001']:
        status, result = b06.inventory(post, method='POST', payload=command(partial))
        assert status == 409 and result['code'] == 'must_cover_outstanding' and result['outstanding'] == '2', (partial, status, result)
    status, state = b06.inventory(read)
    assert status == 200 and (state['requiredInstalled'], state['returned'], state['outstanding']) == ('2', '0', '2') and state['returns'] == [], (status, state)
    request = command('2.000000')
    status, saved = b06.inventory(post, method='POST', payload=request)
    assert status == 201, ('one command returns all remaining 2', status, saved)
    assert (saved['id'], saved['orderId'], saved['workingGroupId'], saved['lineId']) == (request['id'], order['id'], order['id'], line['id']), saved
    assert (saved['quantity'], saved['description'], saved['warehouseId'], saved['catalogItemId']) == ('2', request['description'], b06.WAREHOUSE, CARCASS_PART), saved
    assert (saved['location'], saved['locationConfigurationVersion']) == ('Carcasse A', 1), saved
    assert saved['operatorId'] == 'aaaaaaaa-0000-0000-0000-000000000001' and saved['receivedAt'] >= second['installedAt'], saved
    assert sorted(saved['installations'], key=lambda x: x['installationId']) == sorted([
        dict(installationId=first['id'], quantity='1', carcassPolicyVersion=1),
        dict(installationId=second['id'], quantity='1', carcassPolicyVersion=1)], key=lambda x: x['installationId']), saved
    status, state = b06.inventory(read)
    assert (state['requiredInstalled'], state['returned'], state['outstanding']) == ('2', '2', '0') and state['returns'] == [saved], state
    assert stock(order, line) == before, ('carcass never restores new-part physical/availability', before, stock(order, line))
    status, closure = gate(order)
    assert status == 200 and closure['status'] == 'Clear' and closure['requirements'][0]['outstanding'] == '0', closure
    assert b06.inventory(post, method='POST', payload=request) == (200, saved)
    status, result = b06.inventory(post, method='POST', payload=command('2'))
    assert status == 409 and result['code'] == 'nothing_outstanding', (status, result)
    print('PASS B09 D73: partial/excess refused whole; one command returns all 2 linked installations; location A v1; gate Blocked -> Clear; stock unchanged; retry once')

def late():
    order, line, pick = setup()
    first = install(order, line, pick)
    post, read = returns(order, line)
    request = command('1')
    status, saved = b06.inventory(post, method='POST', payload=request)
    assert status == 201 and [x['installationId'] for x in saved['installations']] == [first['id']], (status, saved)
    assert gate(order)[1]['status'] == 'Clear'
    late_install = install(order, line, pick)
    status, closure = gate(order)
    assert closure['status'] == 'Blocked' and closure['requirements'][0]['outstanding'] == '1', closure
    assert b06.inventory(post, method='POST', payload=request) == (200, saved), 'retry never extends an accepted return'
    status, result = b06.inventory(post, method='POST', payload=command('2'))
    assert status == 409 and result['outstanding'] == '1', (status, result)
    status, second = b06.inventory(post, method='POST', payload=command('1'))
    assert status == 201 and [x['installationId'] for x in second['installations']] == [late_install['id']], (status, second)
    state = b06.inventory(read)[1]
    assert (state['requiredInstalled'], state['returned'], state['outstanding']) == ('2', '2', '0') and len(state['returns']) == 2, state
    assert gate(order)[1]['status'] == 'Clear'
    print('PASS B09 late installation reopens exact residual; old retry unchanged; new full command covers only the late installation')

def late_race():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    order, line, pick = setup()
    first = install(order, line, pick)
    post, read = returns(order, line)
    barrier = Barrier(2)
    def act(kind):
        barrier.wait()
        if kind == 'return': return b06.inventory(post, method='POST', payload=command('1'))
        return b08.call(b08.target(order, line, pick), None, 'POST', b07.command('1'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        returned, installed = pool.map(act, ['return', 'install'])
    assert installed[0] == 201, installed
    state = b06.inventory(read)[1]
    if returned[0] == 201:
        assert [x['installationId'] for x in returned[1]['installations']] == [first['id']], returned
        assert (state['returned'], state['outstanding']) == ('1', '1'), state
    else:
        assert returned[0] == 409 and returned[1]['outstanding'] == '2', returned
        assert (state['returned'], state['outstanding']) == ('0', '2'), state
    assert state['requiredInstalled'] == '2' and gate(order)[1]['status'] == 'Blocked', state
    print('PASS B09 concurrent late install/return serialized: exact linked set or whole refusal, never trimmed or double counted:', returned[0])

def invalid():
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, read = returns(order, line)
    cases = [{'quantity': q} for q in ['0', '-2', '2.0000001', '2e0', 'NaN', '2,0', ' 2', '1000000', None, 2]]
    cases += [{'description': d} for d in ['', ' ', ' x', 'x ', 'a\nb', 'a\u0000b', 'x'*201, None, 5]]
    cases += [{'id': str(uuid.UUID(int=0))}, {'warehouseId': str(uuid.UUID(int=0))}, {'tenantId': b.C}, {'location': 'Altro'},
              {'installations': []}, {'receivedAt': '2026-01-01T00:00:00Z'}, {'operatorId': str(uuid.uuid4())}]
    for fields in cases:
        status, result = b06.inventory(post, method='POST', payload=command() | fields)
        assert status == 400, (fields, status, result)
    status, state = b06.inventory(read)
    assert (state['returned'], state['outstanding']) == ('0', '2'), state
    assert b06.inventory(post, method='POST', payload=command('2', description='x'*200))[0] == 201
    print('PASS B09 strict q6/description/server-owned fields rejected atomically; 200-char description accepted')

def unrequired():
    order, line, pick = setup(item=b06.b05.PART)
    installation = install(order, line, pick, '2')
    assert installation['carcassReturnRequired'] is False and installation['carcassPolicyVersion'] is None, installation
    post, read = returns(order, line)
    status, result = b06.inventory(post, method='POST', payload=command('2'))
    assert status == 409 and result['code'] == 'nothing_outstanding', (status, result)
    status, closure = gate(order)
    assert status == 200 and closure == dict(orderId=order['id'], status='Clear', requirements=[]), closure
    print('PASS B09 unconfigured part imposes no carcass gate (D30), and no optional return is fabricated')

def idempotency():
    from concurrent.futures import ThreadPoolExecutor
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, read = returns(order, line)
    request = command('2')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: b06.inventory(post, method='POST', payload=request), range(8)))
    assert sorted(x[0] for x in results) == [200]*7+[201], results
    saved = next(x[1] for x in results if x[0] == 201)
    assert all(x[1] == saved for x in results), results
    for fields in [{'quantity': '1'}, {'description': 'Diversa'}, {'warehouseId': OTHER_WAREHOUSE}]:
        assert b06.inventory(post, method='POST', payload=request | fields)[0] == 409, fields
    assert b06.inventory(read)[1]['returns'] == [saved]
    beta = b.b02.login(b.BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    beta_order, beta_line, beta_pick = setup(BETA_CARCASS_PART, token=beta, warehouse=BETA_WAREHOUSE, company={
        'legalEntityId': b.C, 'siteId': '22222222-2222-2222-2222-222222220101', 'documentTypeId': '22222222-5555-0000-0000-000000000001',
        'payerId': '22222222-3333-0000-0000-000000000001', 'vehicleId': '22222222-4444-0000-0000-000000000001'})
    install(beta_order, beta_line, beta_pick, '2', beta)
    beta_post, beta_read = returns(beta_order, beta_line, BETA_WAREHOUSE)
    assert b06.inventory(beta_post, beta, 'POST', request | {'warehouseId': BETA_WAREHOUSE})[0] == 409
    assert b06.inventory(beta_read, beta)[1]['returned'] == '0'
    assert b06.inventory(beta_post, beta, 'POST', command('2', BETA_WAREHOUSE))[0] == 201
    print('PASS B09 identical concurrent retries one effect; changed quantity/description/warehouse and cross-tenant ID replay refused')

def concurrent():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    order, line, pick = setup()
    install(order, line, pick, '1')
    install(order, line, pick, '1')
    post, read = returns(order, line)
    barrier = Barrier(8)
    def act(_):
        barrier.wait()
        return b06.inventory(post, method='POST', payload=command('2'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(act, range(8)))
    assert sorted(x[0] for x in results) == [201]+[409]*7, results
    state = b06.inventory(read)[1]
    assert (state['returned'], state['outstanding']) == ('2', '0') and len(state['returns']) == 1, state
    print('PASS B09 eight independent full-residual commands: exactly one accepted, linked installations covered once')

def references():
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, read = returns(order, line)
    for username, password in [('operatore-beta-sintetico', 'synthetic-beta-password'), ('operatore-senza-membership', 'synthetic-no-membership'), ('operatore-alfa-senza-lettura', 'synthetic-no-read')]:
        token = b.b02.login(b.BASE, username, password)
        assert b06.inventory(read, token)[0] == 404
        assert b06.inventory(post, token, 'POST', command())[0] in (403, 404)
        assert gate(order, token)[0] == 404
    for wrong in [post.replace(order['id'], str(uuid.uuid4())), post.replace(line['id'], str(uuid.uuid4()))]:
        assert b06.inventory(wrong+'?warehouseId='+b06.WAREHOUSE)[0] == 404
        assert b06.inventory(wrong, method='POST', payload=command())[0] == 404
    assert b.call('/orders/'+str(uuid.uuid4())+'/technical-closure-gate')[0] == 404
    for warehouse in [SITE_ONLY_WAREHOUSE, BETA_WAREHOUSE, str(uuid.uuid4())]:
        assert b06.inventory(post, method='POST', payload=command('2', warehouse))[0] in (403, 404), warehouse
        assert b06.inventory(post+'?warehouseId='+warehouse)[0] == 404, warehouse
    service_order = b06.b05.create_order()
    status, service = b.call('/orders/'+service_order['id']+'/lines', method='POST', payload=b06.b05.line_body('Service'))
    assert status == 201, (status, service)
    assert b06.inventory(b06.path(service_order, service)+'/carcass-returns', method='POST', payload=command())[0] == 400
    for path in ['/api/v1/inventory'+read, '/api/v1/workshop/orders/'+order['id']+'/technical-closure-gate']:
        assert b.b02.request(b.BASE+path)[0] == 401, path
    assert b.b02.request(b.BASE+'/api/v1/inventory'+post, None, 'POST', command())[0] == 401
    assert b06.inventory(read)[1]['returned'] == '0' and gate(order)[1]['status'] == 'Blocked'
    print('PASS B09 tenant/member/action/order/line/warehouse/kind provenance rejected; anonymous 401; no return recorded')

def other_warehouse():
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, _ = returns(order, line, OTHER_WAREHOUSE)
    status, saved = b06.inventory(post, method='POST', payload=command('2', OTHER_WAREHOUSE))
    assert status == 201 and (saved['location'], saved['warehouseId']) == ('Carcasse B', OTHER_WAREHOUSE), (status, saved)
    assert b06.inventory(returns(order, line)[1])[1]['returns'] == [], 'returns listed only for the authorized receiving warehouse'
    assert b06.inventory(returns(order, line, OTHER_WAREHOUSE)[1])[1]['returns'] == [saved]
    print('PASS B09 receiving warehouse of header site is explicit with its own dedicated location; line residual shared')

def denied_scope():
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, read = returns(order, line)
    assert b06.inventory(read)[0] == 404
    assert b06.inventory(post, method='POST', payload=command())[0] in (403, 404)
    assert gate(order)[1]['status'] == 'Blocked'
    print('PASS B09 same-tenant missing exact carcass action or site/warehouse combination')

def read_only():
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, read = returns(order, line)
    assert b06.inventory(read)[0] == 200
    assert b06.inventory(post, method='POST', payload=command())[0] in (403, 404)
    print('PASS B09 read-only permission cannot record a carcass return')

def create_only():
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, read = returns(order, line)
    assert b06.inventory(read)[0] == 404
    assert b06.inventory(post, method='POST', payload=command())[0] == 201
    print('PASS B09 create permission does not imply historical read')

def unconfigured_location():
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, read = returns(order, line)
    status, result = b06.inventory(post, method='POST', payload=command())
    assert status == 409 and result['code'] == 'carcass_configuration_missing', (status, result)
    assert b06.inventory(read)[1]['returned'] == '0'
    print('PASS B09 missing or non-dedicated carcass location is refused, never defaulted to a new-part location')

def state_file():
    return Path(os.environ['B06_STATE_DIR'], 'b09-history.json')

def version_before():
    order, line, pick = setup()
    first = install(order, line, pick)
    state_file().write_text(json.dumps(dict(order=order, line=line, pick=pick, first=first)))
    print('PASS B09 version fixture: first installation snapshots carcass policy v1 required')

def version_after():
    fixture = json.loads(state_file().read_text())
    order, line, pick, first = fixture['order'], fixture['line'], fixture['pick'], fixture['first']
    second = install(order, line, pick)
    assert (second['carcassPolicyVersion'], second['carcassReturnRequired']) == (2, False), second
    state = b08.call(b08.target(order, line, pick))[1]
    assert [x['installation'] for x in state['installations'] if x['installation']['id'] == first['id']] == [first], 'v1 snapshot is immutable'
    status, closure = gate(order)
    assert closure['status'] == 'Blocked' and closure['requirements'][0]['requiredInstalled'] == '1', closure
    post, read = returns(order, line)
    assert b06.inventory(post, method='POST', payload=command('2'))[1]['outstanding'] == '1'
    status, saved = b06.inventory(post, method='POST', payload=command('1'))
    assert status == 201 and (saved['location'], saved['locationConfigurationVersion']) == ('Carcasse A2', 2), saved
    assert [x['installationId'] for x in saved['installations']] == [first['id']], saved
    assert gate(order)[1]['status'] == 'Clear'
    fixture['saved'] = saved
    fixture['request'] = None
    state_file().write_text(json.dumps(fixture))
    print('PASS B09 later customizing v2 applies only to later installation/return; v1 obligation and links preserved (D9)')

def fault():
    order, line, pick = setup()
    install(order, line, pick, '2')
    post, read = returns(order, line)
    request = command('2')
    status, _ = b06.inventory(post, method='POST', payload=request)
    assert status == 500, status
    assert b06.inventory(read)[1]['returned'] == '0'
    state_file().write_text(json.dumps(dict(order=order, line=line, request=request)))
    print('PASS B09 injected failure after return INSERT rolls back return and links atomically')

def recover():
    fixture = json.loads(state_file().read_text())
    post, read = returns(fixture['order'], fixture['line'])
    status, saved = b06.inventory(post, method='POST', payload=fixture['request'])
    assert status == 201 and saved['quantity'] == '2', (status, saved)
    assert gate(fixture['order'])[1]['status'] == 'Clear'
    fixture['saved'] = saved
    state_file().write_text(json.dumps(fixture))
    print('PASS B09 same command after fault/restart records the full return once')

def history():
    fixture = json.loads(state_file().read_text())
    post, read = returns(fixture['order'], fixture['line'])
    assert b06.inventory(read)[1]['returns'] == [fixture['saved']]
    assert gate(fixture['order'])[1]['status'] == 'Clear'
    assert b06.inventory(post, method='POST', payload=command('2'))[0] in (403, 404)
    print('PASS B09 disabled capabilities preserve authorized return history and gate; new returns forbidden')

if __name__ == '__main__':
    b.BASE = sys.argv[1]
    b.alpha = b.b02.login(b.BASE, 'operatore-alfa-sintetico', 'synthetic-alpha-password')
    globals()[sys.argv[2]]()
