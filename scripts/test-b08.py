#!/usr/bin/env python3
"""B08 synthetic HTTP tests against isolated nginx/API/identity/PostgreSQL."""
import importlib.util
import sys
import uuid
from pathlib import Path
spec = importlib.util.spec_from_file_location('b07', Path(__file__).with_name('test-b07.py'))
assert spec and spec.loader
b07 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b07)
b06, b = b07.b06, b07.b

def setup(quantity='2'):
    order, line, reservation = b07.setup()
    status, pick = b06.inventory(b07.url(order,line,reservation), method='POST', payload=b07.command(quantity))
    assert status == 201, (status,pick)
    return order,line,reservation,pick

def target(order,line,pick):
    return '/orders/'+order['id']+'/lines/'+line['id']+'/picks/'+pick['id']+'/installations'

def call(url, token=None, method='GET', payload=None):
    return b.call(url, token or b.alpha, method, payload)

def smoke():
    import re
    from urllib.request import urlopen
    b07.smoke()
    with urlopen(b.BASE,timeout=10) as response: html=response.read().decode()
    bundles=[]
    for script in re.findall(r'<script[^>]+src="([^"]+)"',html):
        with urlopen(b.BASE+script,timeout=10) as response: bundles.append(response.read().decode())
    assert any('Installazione ricambio' in bundle for bundle in bundles),'B08 private UI must actually be compiled'
    print('PASS B08 ready/system/HTML/compiled private installation UI via nginx HTTP')

def partial():
    order,line,reservation,pick = setup()
    url = target(order,line,pick)
    request = b07.command('1')
    status, result = call(url,method='POST',payload=request)
    assert status == 201, ('explicit install 1 of 2 picked must succeed',status,result)
    assert result['installation']['id'] == request['id'] and result['installation']['quantity'] == '1', result
    installation = result['installation']
    assert installation['pickId'] == pick['id'] and installation['reservationId'] == reservation['id'],installation
    assert (installation['orderId'],installation['lineId'],installation['workingGroupId']) == (order['id'],line['id'],order['id']),installation
    assert installation['warehouseId'] == b06.WAREHOUSE and installation['legalEntityId'] == order['legalEntityId'] and installation['siteId'] == order['siteId'],installation
    assert installation['catalogItemId'] == pick['catalogItemId'] and installation['catalogVersion'] == pick['catalogVersion'],installation
    assert installation['pickingConfigurationVersion'] == pick['configurationVersion'] and installation['documentTypeId'] == order['documentTypeId'],installation
    assert installation['configurationVersion'] == order['configurationVersion'] and installation['operatorId'] == 'aaaaaaaa-0000-0000-0000-000000000001',installation
    assert installation['installedAt'] >= pick['pickedAt'],installation
    assert result['consumption']['installationId'] == request['id'] and result['consumption']['quantity'] == '1', result
    assert result['stockEffect'] == 'Consumed', result
    status, state = call(url)
    assert status == 200 and (state['picked'],state['installed'],state['remainingToInstall']) == ('2','1','1'), (status,state)
    assert state['installations'] == [result], state
    stock = b06.inventory(b06.path(order,line)+'?warehouseId='+b06.WAREHOUSE)[1]
    assert (stock['physical'],stock['available'],stock['reserved']) == ('1','0','2'), stock
    assert stock['activeCommitted'] == '1' and stock['consumed'] == '1', stock
    assert call(url,method='POST',payload=request) == (200,result)
    stock2 = b06.inventory(b06.path(order,line)+'?warehouseId='+b06.WAREHOUSE)[1]
    assert stock2 == stock, stock2
    print('PASS B08 explicit partial installation: installed/consumed 1, picked-not-installed 1; physical 1 active commitment 1 available 0; retry exact snapshot once')


def invalid():
    order,line,reservation,pick = setup()
    url = target(order,line,pick)
    for fields in [{'quantity':q} for q in ['0','-1','1.0000001','1e0','NaN','Infinity','1,5',' 1','1000000',None,1.5]] + [{'id':str(uuid.UUID(int=0))},{'tenantId':b.C},{'warehouseId':b06.WAREHOUSE},{'installedAt':'2026-01-01T00:00:00Z'}]:
        status, result = call(url,method='POST',payload=b07.command() | fields)
        assert status == 400, (fields,status,result)
    assert call(url,method='POST',payload=b07.command('3'))[0] == 409
    assert call(url)[1]['installed'] == '0'
    status, result = call(url,method='POST',payload=b07.command('0.000001'))
    assert status == 201, (status,result)
    state = call(url)[1]
    assert (state['installed'],state['remainingToInstall']) == ('0.000001','1.999999'), state
    stock = b06.inventory(b06.path(order,line)+'?warehouseId='+b06.WAREHOUSE)[1]
    assert (stock['physical'],stock['available'],stock['activeCommitted']) == ('1.999999','0','1.999999'),stock
    print('PASS B08 strict finite positive q6; empty ID/server fields/overpick atomically rejected; exact microquantity')

def concurrent():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    order,line,reservation,pick = setup()
    url = target(order,line,pick)
    barrier = Barrier(8)
    def install(_):
        barrier.wait()
        return call(url,method='POST',payload=b07.command('1.5'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(install,range(8)))
    assert sorted(x[0] for x in results) == [201]+[409]*7, results
    state = call(url)[1]
    assert (state['installed'],state['remainingToInstall']) == ('1.5','0.5'),state
    stock = b06.inventory(b06.path(order,line)+'?warehouseId='+b06.WAREHOUSE)[1]
    assert (stock['physical'],stock['available'],stock['activeCommitted']) == ('0.5','0','0.5'), stock
    print('PASS B08 concurrent independent commands: bound once, physical and active commitment exact')

def idempotency():
    from concurrent.futures import ThreadPoolExecutor
    order,line,reservation,pick = setup()
    url = target(order,line,pick)
    request = b07.command('0.5')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _:call(url,method='POST',payload=request),range(8)))
    assert sorted(x[0] for x in results) == [200]*7+[201],results
    saved = results[0][1]
    assert all(x[1] == saved for x in results),results
    assert call(url,method='POST',payload=request|{'quantity':'0.500000'}) == (200,saved)
    assert call(url,method='POST',payload=request|{'quantity':'0.6'})[0] == 409
    assert call(url)[1]['installed'] == '0.5'
    # No stock can be freed by consuming an already committed part.
    other_order,other_line = b06.setup()
    response = b06.inventory(b06.path(other_order,other_line)+'/reservations',method='POST',payload=b06.command('0.000001'))
    assert response[0] == 409 and response[1]['code'] == 'insufficient_available',response
    other_reservation = b06.inventory(b06.path(order,line)+'/reservations',method='POST',payload=b06.command('0.5',b06.WAREHOUSE[:-1]+'2'))
    assert other_reservation[0] == 201,other_reservation
    other_pick = b06.inventory(b07.url(order,line,other_reservation[1]),method='POST',payload=b07.command('0.5'))
    assert other_pick[0] == 201,other_pick
    assert call(target(order,line,other_pick[1]),method='POST',payload=request)[0] == 409
    beta=b.b02.login(b.BASE,'operatore-beta-sintetico','synthetic-beta-password')
    payload=b.body() | {'legalEntityId':b.C,'siteId':'22222222-2222-2222-2222-222222220101','documentTypeId':'22222222-5555-0000-0000-000000000001','payerId':'22222222-3333-0000-0000-000000000001','vehicleId':'22222222-4444-0000-0000-000000000001'}
    status,foreign=b.call('/orders',beta,'POST',payload)
    assert status == 201,(status,foreign)
    status,foreign_line=b.call('/orders/'+foreign['id']+'/lines',beta,'POST',b06.b05.line_body('Part')|{'catalogItemId':'22222222-7777-0000-0000-000000000002','quantity':'3'})
    assert status == 201,(status,foreign_line)
    status,foreign_reservation=b06.inventory(b06.path(foreign,foreign_line)+'/reservations',beta,'POST',b06.command('2','22222222-2222-2222-2222-222222220101'))
    assert status == 201,(status,foreign_reservation)
    status,foreign_pick=b06.inventory(b07.url(foreign,foreign_line,foreign_reservation),beta,'POST',b07.command('2'))
    assert status == 201,(status,foreign_pick)
    foreign_url=target(foreign,foreign_line,foreign_pick)
    assert call(foreign_url,beta,'POST',request)[0] == 409
    assert call(foreign_url,beta)[1]['installed'] == '0'
    assert call(foreign_url,beta,'POST',b07.command('0.5'))[0] == 201
    print('PASS B08 identical retries exact timestamps, conflicting quantity/pick/tenant ID replay refused; no freed stock availability')

def references():
    order,line,reservation,pick = setup()
    url = target(order,line,pick)
    for username,password in [('operatore-beta-sintetico','synthetic-beta-password'),('operatore-senza-membership','synthetic-no-membership'),('operatore-alfa-senza-lettura','synthetic-no-read')]:
        token=b.b02.login(b.BASE,username,password)
        assert call(url,token)[0] == 404
        assert call(url,token,'POST',b07.command())[0] in (403,404)
    for wrong in [url.replace(order['id'],str(uuid.uuid4())),url.replace(line['id'],str(uuid.uuid4())),url.replace(pick['id'],str(uuid.uuid4()))]:
        assert call(wrong)[0] == 404
        assert call(wrong,method='POST',payload=b07.command())[0] == 404
    assert b.b02.request(b.BASE+'/api/v1/workshop'+url)[0] == 401
    assert call(url)[1]['installed'] == '0'
    print('PASS B08 tenant/member/action/provenance rejected; anonymous 401; no installation/consumption')

def denied_scope():
    order,line,reservation,pick = setup()
    url = target(order,line,pick)
    assert call(url)[0] == 404
    assert call(url,method='POST',payload=b07.command())[0] in (403,404)
    print('PASS B08 same-tenant missing exact installation/consumption action or site/warehouse combination')

def read_only():
    order,line,reservation,pick = setup()
    url=target(order,line,pick)
    assert call(url)[0] == 200
    assert call(url,method='POST',payload=b07.command())[0] in (403,404)
    print('PASS B08 read-only permission cannot install/consume')

def create_only():
    order,line,reservation,pick = setup()
    url=target(order,line,pick)
    assert call(url)[0] == 404
    assert call(url,method='POST',payload=b07.command())[0] == 201
    print('PASS B08 create permission does not imply historical read')

def fault():
    import os,json
    order,line,reservation,pick = setup()
    url = target(order,line,pick)
    request = b07.command('1')
    status,result = call(url,method='POST',payload=request)
    assert status == 202 and result['stockEffect'] == 'Pending' and result['consumption'] is None,(status,result)
    assert call(url,method='POST',payload=request) == (202,result)
    assert call(url)[1]['installations'] == [result]
    stock = b06.inventory(b06.path(order,line)+'?warehouseId='+b06.WAREHOUSE)[1]
    assert (stock['physical'],stock['activeCommitted'],stock['available']) == ('2','2','0'),stock
    Path(os.environ['B06_STATE_DIR'],'b08-history.json').write_text(json.dumps(dict(url=url,request=request,result=result,stockurl=b06.path(order,line)+'?warehouseId='+b06.WAREHOUSE)))
    print('PASS B08 injected stock failure AFTER technical commit: installation durable Pending; physical and commitment unchanged')

def recover():
    import os,json
    fixture=json.loads(Path(os.environ['B06_STATE_DIR'],'b08-history.json').read_text())
    status,result=call(fixture['url'],method='POST',payload=fixture['request'])
    assert status == 200 and result['stockEffect'] == 'Consumed',(status,result)
    assert result['installation'] == fixture['result']['installation'],result
    assert call(fixture['url'],method='POST',payload=fixture['request']) == (200,result)
    assert call(fixture['url'])[1]['installed'] == '1'
    stock=b06.inventory(fixture['stockurl'])[1]
    assert (stock['physical'],stock['activeCommitted'],stock['available']) == ('1','1','0'),stock
    fixture['result']=result
    Path(os.environ['B06_STATE_DIR'],'b08-history.json').write_text(json.dumps(fixture))
    print('PASS B08 restart/retry recovery retains technical timestamp/source/operator; stock consumed once')

def history():
    import os,json
    fixture=json.loads(Path(os.environ['B06_STATE_DIR'],'b08-history.json').read_text())
    assert call(fixture['url'])[1]['installations'] == [fixture['result']]
    assert call(fixture['url'],method='POST',payload=fixture['request'])[0] in (403,404)
    print('PASS B08 disabled capabilities preserve authorized historical snapshot and forbid new writes')

if __name__ == '__main__':
    b.BASE = sys.argv[1]
    b.alpha = b.b02.login(b.BASE,'operatore-alfa-sintetico','synthetic-alpha-password')
    globals()[sys.argv[2]]()
