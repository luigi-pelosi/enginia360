#!/usr/bin/env python3
"""Non-destructive B06 HTTPS probe. Fresh API scenarios only, no SQL/reset/config.
Supply three newly INSERTed synthetic warehouse IDs (physical 2, 2, 3),
with exact Alfa read/create scopes. Never reuse occupied probe warehouses.
Canonical owner warehouses are not touched. A failed probe retains all records.
"""
import importlib.util
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from threading import Barrier

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('b06', Path(__file__).with_name('test-b06.py'))
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
b = m.b
warehouses = sys.argv[2:]
if warehouses and warehouses[0] == '--permissions':
    assert len(warehouses) == 3
    read_wh, create_wh = warehouses[1:]
    order, line = m.setup('3')
    url = m.path(order,line)
    assert m.inventory(url+'?warehouseId='+read_wh)[0] == 200
    assert m.inventory(url+'/reservations',method='POST',payload=m.command('1',read_wh))[0] == 403
    assert m.inventory(url+'?warehouseId='+create_wh)[0] == 404
    command = m.command('0.000001',create_wh)
    code, saved = m.inventory(url+'/reservations',method='POST',payload=command)
    assert code == 201
    assert m.inventory(url+'/reservations',method='POST',payload=command) == (200,saved)
    assert m.inventory(url+'?warehouseId='+create_wh)[0] == 404
    code, permission_state = m.inventory(url+'?warehouseId='+read_wh)
    assert code == 200 and permission_state['reservations'] == [] and permission_state['reserved'] == '0.000001' and permission_state['remaining'] == '2.999999'
    print('PASS independent exact read-only/create-only permission fixture; creation never confers stock/history read; hidden warehouse details absent, global remainder preserved')
    sys.exit(0)
assert len(warehouses) == 3 and len(set(warehouses)) == 3
assert m.WAREHOUSE not in warehouses and m.WAREHOUSE[:-1]+'2' not in warehouses
m.smoke()

def fresh(warehouse, physical, quantity='3'):
    order, line = m.setup(quantity)
    url = m.path(order, line)
    status, state = m.inventory(url+'?warehouseId='+warehouse)
    assert status == 200 and state['physical'] == state['available'] == physical
    assert state['reserved'] == '0' and state['remaining'] == quantity
    return order, line, url, state

def post(url, body):
    return m.inventory(url+'/reservations', method='POST', payload=body)

def state(url, wh):
    code, value = m.inventory(url+'?warehouseId='+wh)
    assert code == 200
    return value

order, line, url, before = fresh(warehouses[0], '2')
for value in ['0','-1','1.0000001','1e0','1,2','1000000',None,1.5]:
    assert post(url,m.command(warehouse=warehouses[0])|{'quantity':value})[0] == 400
assert post(url,m.command('3',warehouses[0]))[0] == 409
assert state(url,warehouses[0]) == before, 'insufficient must not auto-trim or write'
assert post(url,m.command('1',warehouses[0])|{'catalogVersion':999})[0] == 409
for wh in ['11111111-1111-1111-1111-111111100301','22222222-2222-2222-2222-222222220101']:
    assert post(url,m.command('1',wh))[0] == 403
    assert m.inventory(url+'?warehouseId='+wh)[0] == 404
request = m.command('2',warehouses[0])
code, reservation = post(url,request)
assert code == 201
assert post(url,request) == (200,reservation)
assert post(url,request|{'quantity':'1'})[0] == 409
saved = state(url,warehouses[0])
assert (saved['physical'],saved['available'],saved['reserved'],saved['remaining']) == ('2','0','2','1')
assert b.call('/orders/'+order['id']) == (200,order)
for username,password in [('operatore-beta-sintetico','synthetic-beta-password'),('operatore-senza-membership','synthetic-no-membership'),('operatore-alfa-senza-lettura','synthetic-no-read')]:
    token=b.b02.login(b.BASE,username,password)
    assert m.inventory(url+'?warehouseId='+warehouses[0],token)[0] == 404
    assert m.inventory(url+'/reservations',token,'POST',m.command('1',warehouses[0]))[0] in (403,404)
assert state(url,warehouses[0]) == saved
print('PASS q6 bounds, stale catalog, header/warehouse coherence, explicit 2/3, no-trim 3/2, immutable physical, retry/conflict, cross-tenant and history/action denials')
# Fresh pool, new order/line for every contender. No trigger, fixture mutation or reset.
rows=[fresh(warehouses[1],'2') for _ in range(4)]
barrier=Barrier(4)
def contender(row):
    barrier.wait(timeout=10)
    return post(row[2],m.command('1.5',warehouses[1]))
with ThreadPoolExecutor(max_workers=4) as pool:
    results=list(pool.map(contender,rows))
assert sorted(r[0] for r in results) == [201,409,409,409],results
race=state(rows[0][2],warehouses[1])
assert race['physical']=='2' and race['available']=='0.5'
assert sum(Decimal(state(r[2],warehouses[1])['reserved']) for r in rows)==Decimal('1.5')
print('PASS bounded four fresh-line concurrent commands; one 201, three 409; no oversubscription')
# Initial fresh fixture physical=3; no replenishment/update endpoint or stock modification.
extra_order,extra_line,extra_url,_=fresh(warehouses[2],'3')
for quantity in ['0.000001','1.999999','1']:
    command=m.command(quantity,warehouses[2])
    code,row=post(extra_url,command)
    assert code==201
    assert post(extra_url,command)==(200,row)
extra=state(extra_url,warehouses[2])
assert (extra['physical'],extra['available'],extra['reserved'],extra['remaining'])==('3','0','3','0')
assert post(extra_url,m.command('0.000001',warehouses[2]))[0]==409
print('PASS additional explicit partials on fresh initial fixture, exact q6 cumulative bound and retry')
print('DURABILITY_REFERENCE '+json.dumps(dict(order=order,line=line,request=request,reservation=reservation,state=saved,warehouse=warehouses[0]),sort_keys=True))
