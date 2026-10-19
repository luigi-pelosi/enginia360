#!/usr/bin/env python3
"""B07 synthetic real HTTP acceptance; no persistent environment."""
import importlib.util
import sys
import uuid
from pathlib import Path
spec = importlib.util.spec_from_file_location('b06', Path(__file__).with_name('test-b06.py'))
assert spec and spec.loader
b06 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b06)
b = b06.b

def setup():
    order, line = b06.setup()
    url = b06.path(order, line)
    status, reservation = b06.inventory(url+'/reservations', method='POST', payload=b06.command())
    assert status == 201, (status, reservation)
    return order, line, reservation

def command(quantity='1'):
    return dict(id=str(uuid.uuid4()), quantity=quantity)

def smoke():
    import re
    from urllib.request import urlopen
    b06.smoke()
    with urlopen(b.BASE, timeout=10) as response:
        html = response.read().decode()
    bundles = []
    for script in re.findall(r'<script[^>]+src="([^"]+)"',html):
        with urlopen(b.BASE+script, timeout=10) as response:
            bundles.append(response.read().decode())
    assert any('Prelievo ricambio' in bundle for bundle in bundles), 'B07 private picking UI must actually be compiled'
    print('PASS B07 ready/system/HTML/compiled private picking bundle via nginx HTTP')

def url(order, line, reservation):
    return b06.path(order, line)+'/reservations/'+reservation['id']+'/picks'

def partial():
    order, line, reservation = setup()
    target = url(order, line, reservation)
    request = command()
    status, pick = b06.inventory(target, method='POST', payload=request)
    assert status == 201, ('explicit pick 1 of 2 reserved expected 201', status, pick)
    assert pick['reservationId'] == reservation['id'] and pick['quantity'] == '1', pick
    assert pick['orderId'] == order['id'] and pick['workingGroupId'] == order['id'] and pick['lineId'] == line['id'], pick
    assert pick['warehouseId'] == b06.WAREHOUSE and pick['pickingListId'] == request['id'], pick
    assert pick['originLocation'] == 'Stock A' and pick['placementLocation'] == 'Preparazione A' and pick['configurationVersion'] == 1, pick
    status, state = b06.inventory(target)
    assert status == 200 and (state['reserved'], state['picked'], state['remainingToPick']) == ('2', '1', '1'), (status, state)
    assert state['picks'] == [pick], state
    stock = b06.inventory(b06.path(order, line)+'?warehouseId='+b06.WAREHOUSE)[1]
    assert (stock['physical'], stock['available'], stock['reserved']) == ('2', '0', '2'), stock
    assert b06.inventory(target, method='POST', payload=request) == (200, pick)
    print('PASS B07 partial: 1 picked, 1 still reserved; physical 2 available 0; persisted provenance/list/placement; retry once; not installed')

def invalid():
    order, line, reservation = setup()
    target = url(order, line, reservation)
    for fields in [{'quantity': x} for x in ['0','-1','-0','1.0000001','1e0','1,2',' 1','1000000',None,1.5]] + [
        {'id': str(uuid.UUID(int=0))}, {'tenantId': b.C}, {'warehouseId': b06.WAREHOUSE}, {'placementLocation':'client location'}]:
        status, result = b06.inventory(target, method='POST', payload=command() | fields)
        assert status == 400, (fields, status, result)
    assert b06.inventory(target, method='POST', payload=command('3'))[0] == 409
    assert b06.inventory(target)[1]['picked'] == '0'
    assert b06.inventory(target, method='POST', payload=command('0.000001'))[0] == 201
    assert b06.inventory(target)[1]['remainingToPick'] == '1.999999'
    print('PASS B07 invalid: strict positive q6 and server-owned placement/scope; oversize rejected atomically, microquantity exact')

def idempotency():
    from concurrent.futures import ThreadPoolExecutor
    order, line, reservation = setup()
    target = url(order, line, reservation)
    request = command('0.5')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: b06.inventory(target, method='POST', payload=request), range(8)))
    assert sorted(x[0] for x in results) == [200]*7+[201], results
    assert all(x[1] == results[0][1] for x in results), results
    assert b06.inventory(target, method='POST', payload=request | {'quantity':'0.500000'}) == (200, results[0][1])
    assert b06.inventory(target, method='POST', payload=request | {'quantity':'0.6'})[0] == 409
    other_reservation = b06.command('0.5', b06.WAREHOUSE[:-1]+'2')
    status, other = b06.inventory(b06.path(order,line)+'/reservations', method='POST', payload=other_reservation)
    assert status == 201, (status, other)
    assert b06.inventory(url(order,line,other), method='POST', payload=request)[0] == 409
    assert b06.inventory(url(order,line,other))[1]['picked'] == '0'
    beta = b.b02.login(b.BASE,'operatore-beta-sintetico','synthetic-beta-password')
    payload = b.body() | {'legalEntityId':b.C,'siteId':'22222222-2222-2222-2222-222222220101','documentTypeId':'22222222-5555-0000-0000-000000000001','payerId':'22222222-3333-0000-0000-000000000001','vehicleId':'22222222-4444-0000-0000-000000000001'}
    status, foreign = b.call('/orders',beta,'POST',payload)
    assert status == 201, (status,foreign)
    status, foreign_line = b.call('/orders/'+foreign['id']+'/lines',beta,'POST',b06.b05.line_body('Part') | {'catalogItemId':'22222222-7777-0000-0000-000000000002','quantity':'3'})
    assert status == 201, (status,foreign_line)
    status, foreign_reservation = b06.inventory(b06.path(foreign,foreign_line)+'/reservations',beta,'POST',b06.command('2','22222222-2222-2222-2222-222222220101'))
    assert status == 201, (status,foreign_reservation)
    foreign_target = url(foreign,foreign_line,foreign_reservation)
    assert b06.inventory(foreign_target,beta,'POST',request)[0] == 409
    assert b06.inventory(foreign_target,beta)[1]['picked'] == '0'
    assert b06.inventory(foreign_target,beta,'POST',command('0.5'))[0] == 201
    print('PASS B07 idempotency: pool8 identical calls one persisted snapshot; changed quantity/reservation conflict')

def read_only():
    order,line,reservation = setup()
    target = url(order,line,reservation)
    assert b06.inventory(target)[0] == 200
    assert b06.inventory(target,method='POST',payload=command())[0] == 403
    print('PASS B07 exact read-only pick grant, create denied')

def create_only():
    order,line,reservation = setup()
    target = url(order,line,reservation)
    assert b06.inventory(target)[0] == 404
    assert b06.inventory(target,method='POST',payload=command())[0] == 201
    print('PASS B07 exact create-only pick grant, historical read not implied')

def references():
    order, line, reservation = setup()
    target = url(order, line, reservation)
    for username, password in [('operatore-beta-sintetico','synthetic-beta-password'),('operatore-senza-membership','synthetic-no-membership'),('operatore-alfa-senza-lettura','synthetic-no-read')]:
        token = b.b02.login(b.BASE, username, password)
        assert b06.inventory(target, token)[0] == 404
        assert b06.inventory(target, token, 'POST', command())[0] in (403,404)
    for wrong in [target.replace(order['id'],str(uuid.uuid4())), target.replace(line['id'],str(uuid.uuid4())), target.replace(reservation['id'],str(uuid.uuid4()))]:
        assert b06.inventory(wrong)[0] == 404
        assert b06.inventory(wrong, method='POST', payload=command())[0] == 404
    assert b.b02.request(b.BASE+'/api/v1/inventory'+target)[0] == 401
    assert b06.inventory(target)[1]['picked'] == '0'
    print('PASS B07 references: tenant/member/permission and exact order/line/reservation provenance denied, anonymous rejected')

def denied_scope():
    order, line, reservation = setup()
    target = url(order,line,reservation)
    assert b06.inventory(target)[0] == 404
    assert b06.inventory(target, method='POST', payload=command())[0] == 403
    print('PASS B07 same-tenant insufficient scope/action; reservation permissions do not grant picking')

def disabled_area():
    order, line, reservation = setup()
    target = url(order,line,reservation)
    status, pick = b06.inventory(target, method='POST', payload=command())
    assert status == 201 and pick['placementLocation'] is None and pick['configurationVersion'] == 2, (status,pick)
    assert pick['originLocation'] == 'Stock A' and pick['pickingListId'] == pick['id'], pick
    stock = b06.inventory(b06.path(order,line)+'?warehouseId='+b06.WAREHOUSE)[1]
    assert stock['physical'] == '2' and stock['available'] == '0', stock
    print('PASS B07 disabled area: no fake transit or consumption; list remains distinct, company policy version 2')

def prepare_history():
    import json, os
    order,line,reservation = setup()
    request = command()
    target = url(order,line,reservation)
    status, pick = b06.inventory(target, method='POST', payload=request)
    assert status == 201, (status,pick)
    Path(os.environ['B06_STATE_DIR'],'b06-history.json').write_text(json.dumps(dict(target=target, pick=pick,request=request)))

def history():
    import json, os
    fixture = json.loads(Path(os.environ['B06_STATE_DIR'],'b06-history.json').read_text())
    status, state = b06.inventory(fixture['target'])
    assert status == 200 and state['picks'] == [fixture['pick']], (status,state)
    assert b06.inventory(fixture['target'], method='POST', payload=fixture['request'])[0] == 403
    print('PASS B07 disabled capabilities preserve authorized immutable historical picking/location/config snapshot, forbid writes')

def concurrent():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    order, line, reservation = setup()
    target = url(order, line, reservation)
    barrier = Barrier(8)
    def pick(_):
        barrier.wait()
        return b06.inventory(target, method='POST', payload=command('1.5'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(pick, range(8)))
    assert sorted(x[0] for x in results) == [201]+[409]*7, results
    state = b06.inventory(target)[1]
    assert (state['picked'], state['remainingToPick']) == ('1.5', '0.5'), state
    print('PASS B07 concurrent: pool8 independent commands, reservation bound once, no connection starvation')

if __name__ == '__main__':
    b.BASE = sys.argv[1]
    b.alpha = b.b02.login(b.BASE, 'operatore-alfa-sintetico', 'synthetic-alpha-password')
    globals()[sys.argv[2]]()
