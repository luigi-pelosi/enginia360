#!/usr/bin/env python3
"""B06 synthetic acceptance through real Keycloak/HTTP/PostgreSQL."""
import importlib.util
import os
import sys
import uuid
from pathlib import Path
spec = importlib.util.spec_from_file_location('b05', Path(__file__).with_name('test-b05.py'))
assert spec and spec.loader
b05 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b05)
b = b05.b
WAREHOUSE = '11111111-1111-1111-1111-111111100101'
def setup(quantity='3', kind='Part'):
    order = b05.create_order()
    status, line = b.call('/orders/'+order['id']+'/lines', method='POST', payload=b05.line_body(kind)|{'quantity':quantity})
    assert status == 201, (status,line)
    return order, line

def inventory(path, token=None, method='GET', payload=None):
    return b.b02.request(b.BASE+'/api/v1/inventory'+path, b.alpha if token is None else token, method, payload)

def path(order,line):
    return '/orders/'+order['id']+'/lines/'+line['id']

def command(quantity='2', warehouse=WAREHOUSE):
    return dict(id=str(uuid.uuid4()),warehouseId=warehouse,quantity=quantity,catalogVersion=1)

def partial():
    order,line=setup(); url=path(order,line)
    status,before=inventory(url+'?warehouseId='+WAREHOUSE)
    assert status==200, ('B06 persisted reservation state expected 200',status,before)
    assert (before['physical'],before['available'],before['reserved'],before['remaining'])==('2','2','0','3'), before
    request=command()
    status,row=inventory(url+'/reservations',method='POST',payload=request)
    assert status==201, ('explicit partial reservation expected 201',status,row)
    status,after=inventory(url+'?warehouseId='+WAREHOUSE)
    assert status==200 and (after['physical'],after['available'],after['reserved'],after['remaining'])==('2','0','2','1'), after
    assert b.call('/orders/'+order['id'])[0]==200
    assert inventory(url+'/reservations',method='POST',payload=request)[0]==200
    print('PASS partial: explicitly reserve 2 of 3; physical unchanged; available 0; remaining 1; identical retry')

def uncovered():
    order,line=setup(); url=path(order,line)
    status,result=inventory(url+'/reservations',method='POST',payload=command('3'))
    assert status==409 and result['code']=='insufficient_available', ('uncovered request must have no effects',status,result)
    state=inventory(url+'?warehouseId='+WAREHOUSE)[1]
    assert (state['physical'],state['available'],state['reserved'],state['remaining'])==('2','2','0','3'),state
    assert b.call('/orders/'+order['id'])[0]==200
    assert inventory(url+'/reservations',method='POST',payload=command('2'))[0]==201
    print('PASS uncovered: request 3 not trimmed to 2; no effects, order readable, explicit request 2 succeeds')

def remaining():
    order,line=setup('1');url=path(order,line)
    status,result=inventory(url+'/reservations',method='POST',payload=command('2'))
    assert status==409 and result['code']=='exceeds_remaining', ('line remaining bound',status,result)
    assert inventory(url+'/reservations',method='POST',payload=command('0.6'))[0]==201
    status,result=inventory(url+'/reservations',method='POST',payload=command('0.5'))
    assert status==409 and result['code']=='exceeds_remaining',(status,result)
    assert inventory(url+'/reservations',method='POST',payload=command('0.4'))[0]==201
    state=inventory(url+'?warehouseId='+WAREHOUSE)[1]
    assert (state['reserved'],state['remaining'],state['physical'],state['available'])==('1','0','2','1'),state
    print('PASS remaining: every explicitly requested partial is bounded by cumulative unreserved line quantity')

def invalid():
    order,line=setup();url=path(order,line)
    for fields in [{'quantity':'-1'},{'quantity':'0'},{'quantity':'-0'},{'quantity':'1.0000001'},
        {'quantity':'1e0'},{'quantity':'1,2'},{'quantity':' 1'},{'quantity':'1000000'},
        {'quantity':None},{'quantity':1.5},{'id':str(uuid.UUID(int=0))},
        {'warehouseId':str(uuid.UUID(int=0))},{'catalogVersion':0},{'tenantId':b.C}]:
        status,row=inventory(url+'/reservations',method='POST',payload=command('1')|fields)
        assert status==400, ('strict positive q6 command required',fields,status,row)
    assert inventory(url+'/reservations',method='POST',payload=command('0.000001'))[0]==201
    state=inventory(url+'?warehouseId='+WAREHOUSE)[1]
    assert state['available']=='1.999999' and state['reserved']=='0.000001' and state['remaining']=='2.999999',state
    print('PASS invalid: 14 malformed commands rejected without effects; six-decimal microquantity exact')

def denied_scope():
    order,line=setup();url=path(order,line)
    status,row=inventory(url+'/reservations',method='POST',payload=command('1'))
    assert status==403, ('valid membership without exact inventory action/scope must be denied',status,row)
    assert inventory(url+'?warehouseId='+WAREHOUSE)[0]==404
    assert b.call('/orders/'+order['id'])[0]==200
    print('PASS denied_scope: real valid membership, wrong action/resource rejected; workshop read retained')

def references():
    order,line=setup();url=path(order,line)
    status,row=inventory(url+'/reservations',method='POST',payload=command('1')|{'catalogVersion':999})
    assert status==409, ('stale catalog reference rejected',status,row)
    service_order,service_line=setup(kind='Service')
    assert inventory(path(service_order,service_line)+'/reservations',method='POST',payload=command('1'))[0]==400
    assert inventory(path(service_order,service_line)+'?warehouseId='+WAREHOUSE)[0]==400
    for wh in [str(uuid.uuid4()),'11111111-1111-1111-1111-111111100301','22222222-2222-2222-2222-222222220101']:
        assert inventory(url+'/reservations',method='POST',payload=command('1',wh))[0]==403
        assert inventory(url+'?warehouseId='+wh)[0]==404
    assert inventory('/orders/'+str(uuid.uuid4())+'/lines/'+line['id']+'/reservations',method='POST',payload=command('1'))[0]==404
    for username,password in [('operatore-beta-sintetico','synthetic-beta-password'),('operatore-senza-membership','synthetic-no-membership'),('operatore-alfa-senza-lettura','synthetic-no-read')]:
        token=b.b02.login(b.BASE,username,password)
        assert inventory(url+'?warehouseId='+WAREHOUSE,token)[0]==404
        assert inventory(url+'/reservations',token,'POST',command('1'))[0] in (403,404)
    assert b.b02.request(b.BASE+'/api/v1/inventory'+url+'?warehouseId='+WAREHOUSE)[0]==401
    assert inventory(url+'?warehouseId='+WAREHOUSE)[1]['reserved']=='0'
    print('PASS references: stale version, services, other tenant/company/site warehouses, wrong order and identities denied without stock disclosure/effects')

def idempotency():
    from concurrent.futures import ThreadPoolExecutor
    order,line=setup();url=path(order,line);request=command('1')
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:inventory(url+'/reservations',method='POST',payload=request),range(8)))
    assert sorted(x[0] for x in results)==[200]*7+[201],results
    assert all(x[1]==results[0][1] for x in results),results
    assert inventory(url+'/reservations',method='POST',payload=request|{'quantity':'1.000000'})==(200,results[0][1])
    for fields in [{'quantity':'0.5'},{'warehouseId':WAREHOUSE[:-1]+'2'},{'catalogVersion':2}]:
        status,row=inventory(url+'/reservations',method='POST',payload=request|fields)
        assert status==409, ('changed payload under stable command ID must conflict',fields,status,row)
    other,otherline=setup()
    assert inventory(path(other,otherline)+'/reservations',method='POST',payload=request)[0]==409
    beta=b.b02.login(b.BASE,'operatore-beta-sintetico','synthetic-beta-password')
    payload=b.body()|{'legalEntityId':b.C,'siteId':'22222222-2222-2222-2222-222222220101','documentTypeId':'22222222-5555-0000-0000-000000000001','payerId':'22222222-3333-0000-0000-000000000001','vehicleId':'22222222-4444-0000-0000-000000000001'}
    status,foreign=b.call('/orders',beta,'POST',payload);assert status==201,(status,foreign)
    status,foreignline=b.call('/orders/'+foreign['id']+'/lines',beta,'POST',b05.line_body('Part')|{'catalogItemId':'22222222-7777-0000-0000-000000000002','quantity':'3'})
    assert status==201,(status,foreignline)
    assert inventory(path(foreign,foreignline)+'/reservations',beta,'POST',request|{'warehouseId':'22222222-2222-2222-2222-222222220101'})[0]==409
    assert inventory(path(foreign,foreignline)+'?warehouseId=22222222-2222-2222-2222-222222220101',beta)[1]['reserved']=='0'
    print('PASS idempotency: eight simultaneous identical commands once, normalized retry, changed payload/order and foreign tenant ID collision controlled')

def concurrent_line():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    order,line=setup('1');url=path(order,line);barrier=Barrier(8)
    def reserve(i):
        barrier.wait()
        return inventory(url+'/reservations',method='POST',payload=command('0.75',WAREHOUSE if i%2==0 else WAREHOUSE[:-1]+'2'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(reserve,range(8)))
    assert sorted(x[0] for x in results)==[201]+[409]*7, ('line must not overreserve across valid warehouses',results)
    state=inventory(url+'?warehouseId='+WAREHOUSE)[1]
    assert state['reserved']=='0.75' and state['remaining']=='0.25',state
    print('PASS concurrent_line: pool8 simultaneous distinct commands on two valid warehouses, cumulative bound global to line')

def concurrent_stock():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    rows=[setup('3') for _ in range(8)];barrier=Barrier(8)
    def reserve(pair):
        barrier.wait()
        return inventory(path(*pair)+'/reservations',method='POST',payload=command('1.5'))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(reserve,rows))
    assert sorted(x[0] for x in results)==[201]+[409]*7, ('stock pool must serialize all orders',results)
    state=inventory(path(*rows[0])+'?warehouseId='+WAREHOUSE)[1]
    assert state['available']=='0.5' and state['physical']=='2',state
    print('PASS concurrent_stock: pool8 distinct lines/orders compete for same stock, exactly one commitment')

def smoke():
    import json
    from urllib.request import urlopen
    with urlopen(b.BASE+'/health/ready', timeout=10) as response:
        assert response.status==200
    with urlopen(b.BASE+'/api/v1/system/status', timeout=10) as response:
        assert json.load(response)['product']=='Enginia360'
    with urlopen(b.BASE, timeout=10) as response:
        html=response.read().decode()
    import re
    scripts=re.findall(r'<script[^>]+src="([^"]+)"',html)
    assert scripts, html
    bundles=[]
    for script in scripts:
        with urlopen(b.BASE+script, timeout=10) as response:
            bundles.append(response.read().decode())
    assert any('Prenotazione ricambio' in bundle for bundle in bundles), 'B06 private UI must actually be compiled'
    print('PASS B06 nginx HTTP smoke: ready, system contract, HTML and compiled private UI bundle')

def read_only():
    order,line=setup();url=path(order,line)
    assert inventory(url+'?warehouseId='+WAREHOUSE)[0]==200
    assert inventory(url+'/reservations',method='POST',payload=command('0.5'))[0]==403
    print('PASS exact read-only grant permits read, denies creation')

def create_only():
    order,line=setup();url=path(order,line)
    assert inventory(url+'?warehouseId='+WAREHOUSE)[0]==404
    assert inventory(url+'/reservations',method='POST',payload=command('0.5'))[0]==201
    print('PASS exact create-only grant permits creation, does not confer stock read')

def prepare_warehouse_history():
    import json
    order,line=setup();url=path(order,line)
    assert inventory(url+'/reservations',method='POST',payload=command('0.5',WAREHOUSE[:-1]+'2'))[0]==201
    Path(os.environ['B06_STATE_DIR'], 'b06-history.json').write_text(json.dumps(dict(order=order,line=line)))
    print('PASS prepared second warehouse reservation')

def restricted_warehouse_history():
    import json
    fixture=json.loads(Path(os.environ['B06_STATE_DIR'], 'b06-history.json').read_text());url=path(fixture['order'],fixture['line'])
    status,state=inventory(url+'?warehouseId='+WAREHOUSE)
    assert status==200 and state['reserved']=='0.5' and state['remaining']=='2.5',(status,state)
    assert state['reservations']==[],('unauthorized warehouse reservation detail disclosed',state)
    assert inventory(url+'?warehouseId='+WAREHOUSE[:-1]+'2')[0]==404
    print('PASS historical detail restricted to exact authorized warehouse; line residual preserved')

def prepare_history():
    import json
    order,line=setup();url=path(order,line);request=command('1')
    assert inventory(url+'/reservations',method='POST',payload=request)[0]==201
    Path(os.environ['B06_STATE_DIR'], 'b06-history.json').write_text(json.dumps(dict(order=order,line=line,request=request)))
    print('PASS prepare historical reservation')

def history():
    import json
    fixture=json.loads(Path(os.environ['B06_STATE_DIR'], 'b06-history.json').read_text());url=path(fixture['order'],fixture['line'])
    status,state=inventory(url+'?warehouseId='+WAREHOUSE)
    assert status==200 and state['reserved']=='1' and state['remaining']=='2', (status,state)
    assert state['reservations'][0]['catalogVersion']==1, state
    assert inventory(url+'/reservations',method='POST',payload=command('0.5'))[0]==403
    print('PASS history reads independent of disabled inventory/workshop capabilities')

def prepare_replenishment():
    import json
    order,line=setup();url=path(order,line);request=command('3')
    assert inventory(url+'/reservations',method='POST',payload=request)[0]==409
    Path(os.environ['B06_STATE_DIR'], 'b06-retry.json').write_text(json.dumps(dict(order=order,line=line,request=request)))
    print('PASS insufficient request retained for technical replenishment retry')

def replenished():
    import json
    fixture=json.loads(Path(os.environ['B06_STATE_DIR'], 'b06-retry.json').read_text());url=path(fixture['order'],fixture['line'])
    status,row=inventory(url+'/reservations',method='POST',payload=fixture['request'])
    assert status==201,(status,row)
    state=inventory(url+'?warehouseId='+WAREHOUSE)[1]
    assert (state['physical'],state['available'],state['reserved'],state['remaining'])==('3','0','3','0'),state
    assert inventory(url+'/reservations',method='POST',payload=fixture['request'])[0]==200
    print('PASS same command retry after isolated technical replenishment; no procurement policy')

def warehouses():
    status, rows = inventory('/warehouses?legalEntityId='+b.A+'&siteId=11111111-1111-1111-1111-111111110101')
    assert status == 200 and WAREHOUSE in [x['id'] for x in rows], ('authorized warehouse choices',status,rows)
    print('PASS authorized warehouse choices')

if __name__=='__main__':
    b.BASE=sys.argv[1]
    b.alpha=b.b02.login(b.BASE,'operatore-alfa-sintetico','synthetic-alpha-password')
    globals()[sys.argv[2]]()
