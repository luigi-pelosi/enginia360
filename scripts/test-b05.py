#!/usr/bin/env python3
"""B05 finite synthetic case, real identity/HTTP/PostgreSQL."""
import importlib.util
import sys
import uuid
from pathlib import Path
spec = importlib.util.spec_from_file_location('b04', Path(__file__).with_name('test-b04.py'))
assert spec and spec.loader
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
SERVICE = '11111111-7777-0000-0000-000000000001'
PART = '11111111-7777-0000-0000-000000000002'

def variable():
    order = create_order()
    path = '/orders/' + order['id'] + '/lines'
    for kind, revision in [('Service', 0), ('Part', 1)]:
        payload = line_body(kind, revision) | {'quantity': '1.000000', 'unitPrice': '0.000001', 'discountPercent': '50.00'}
        status, row = b.call(path, method='POST', payload=payload)
        assert status == 201, ('variable half-micro line expected 201', status, row)
        assert row['netAmount'] == '0.000001', row
        assert b.call(path, method='POST', payload=payload | {'quantity': '1.0'}) == (200, row)
    status, state = b.call('/orders/' + order['id'] + '/commercial-summary')
    assert status == 200 and (state['netAmount'], state['taxAmount'], state['total']) == ('0.000002', '0.000000', '0.000002'), state
    print('PASS variable: real persisted half-micro lines round before aggregation; normalized retry')

def arithmetic():
    # Expected literals independently checked with Python Decimal, not the production helper.
    cases = [
        ('1', '0.000001', '50.01', '0.000000', '0.000000', '0.000000'),
        ('1', '0.000001', '49.99', '0.000001', '0.000000', '0.000001'),
        ('1', '0.000025', '0', '0.000025', '0.000006', '0.000031'),
        ('2.123456', '10.000001', '10.25', '19.058020', '4.192764', '23.250784'),
        ('0.000001', '0.000001', '0', '0.000000', '0.000000', '0.000000'),
        ('999999.999999', '999999.999999', '0', '999999999998.000000', '219999999999.560000', '1219999999997.560000'),
        ('1', '10.0', '100.00', '0.000000', '0.000000', '0.000000'),
        ('1', '0', '0.00', '0.000000', '0.000000', '0.000000'),
        ('1', '10.0', '10.0', '9.000000', '1.980000', '10.980000'),
    ]
    for quantity, price, discount, net, tax, total in cases:
        order = create_order()
        path = '/orders/' + order['id'] + '/lines'
        payload = line_body() | {'quantity': quantity, 'unitPrice': price, 'discountPercent': discount}
        status, row = b.call(path, method='POST', payload=payload)
        assert status == 201 and row['netAmount'] == net, (payload, status, row)
        status, state = b.call('/orders/' + order['id'] + '/commercial-summary')
        assert status == 200 and (state['netAmount'], state['taxAmount'], state['total']) == (net, tax, total), state
        assert state['lines'] == [row]
        assert b.call(path, method='POST', payload=payload) == (200, row)
        assert b.call(path, method='POST', payload=payload | {'discountPercent': '1.23'})[0] == 409
    # Each independent line tax would round down to zero; group tax must round up to a micro.
    order = create_order()
    for kind, revision in [('Service', 0), ('Part', 1)]:
        payload = line_body(kind, revision) | {'quantity': '1', 'unitPrice': '0.000002', 'discountPercent': '0'}
        assert b.call('/orders/' + order['id'] + '/lines', method='POST', payload=payload)[0] == 201
    state = b.call('/orders/' + order['id'] + '/commercial-summary')[1]
    assert (state['netAmount'], state['taxAmount'], state['total']) == ('0.000004', '0.000001', '0.000005'), state
    print('PASS arithmetic: nine persisted boundary cases with retry/conflict; group tax rounds once, not per line')

def catalog():
    status, rows = b.call('/catalog?legalEntityId='+b.A+'&siteId='+b.SITE)
    assert status == 200, ('tenant catalog expected 200', status, rows)
    assert [(x['id'], x['kind']) for x in rows] == [(SERVICE,'Service'),(PART,'Part')], rows
    assert all(set(x) == {'id','kind','label','version'} for x in rows), rows
    assert b.b02.request(b.BASE+'/api/v1/counterparties?legalEntityId='+b.B, b.alpha)[0] == 403
    print('PASS catalog: both tenant master identities selectable, company B management still denied')

def create_order():
    status, order = b.call('/orders', method='POST', payload=b.body())
    assert status == 201, (status, order)
    return order

def line_body(kind='Service', revision=0):
    return dict(id=str(uuid.uuid4()), catalogItemId=SERVICE if kind=='Service' else PART,
                catalogVersion=1, configurationVersion=1, expectedRevision=revision,
                quantity='1.50' if kind=='Service' else '1',
                unitPrice='55.00' if kind=='Service' else '95.00',
                discountPercent='10' if kind=='Service' else '5')

def service():
    order = create_order()
    payload = line_body()
    status, row = b.call('/orders/'+order['id']+'/lines', method='POST', payload=payload)
    assert status == 201, ('persisted Service expected 201',status,row)
    assert row['netAmount']=='74.250000' and row['quantity']=='1.5' and row['unitPrice']=='55'
    assert row['payerId']==b.PAYER and row['workingGroupId']==order['id']
    assert row['catalogLabel']=='Manodopera meccanica' and row['configurationVersion']==1
    assert b.call('/orders/'+order['id']+'/lines', method='POST', payload=payload)==(200,row)
    status, summary = b.call('/orders/'+order['id']+'/commercial-summary')
    assert status==200 and summary['lines']==[row] and summary['revision']==1, (status,summary)
    assert summary['netAmount']=='74.250000' and summary['taxAmount']=='16.335000' and summary['total']=='90.585000'
    print('PASS service: immutable commercial values, same working group, single payer, reread and retry')

def pair(order_id=None):
    order = create_order() if order_id is None else {'id':order_id}
    rows=[]
    for kind,revision,net in [('Service',0,'74.250000'),('Part',1,'90.250000')]:
        payload=line_body(kind,revision)
        status,row=b.call('/orders/'+order['id']+'/lines',method='POST',payload=payload)
        assert status==201, ('persisted '+kind+' expected 201',status,row)
        assert row['netAmount']==net and row['payerId']==b.PAYER and row['workingGroupId']==order['id']
        rows.append(row)
    status,summary=b.call('/orders/'+order['id']+'/commercial-summary')
    assert status==200 and summary['lines']==rows and summary['revision']==2, (status,summary)
    assert (summary['netAmount'],summary['taxAmount'],summary['total'])==('164.500000','36.190000','200.690000'), summary
    assert summary['currency']=='EUR' and summary['policy']=='Case001'
    print('PASS pair: 74.25 + 90.25, aggregated 22% = 36.19 not 36.20, total 200.69')
    return summary

def negatives():
    order=create_order(); path='/orders/'+order['id']+'/lines'; payload=line_body()
    beta=b.b02.login(b.BASE,'operatore-beta-sintetico','synthetic-beta-password')
    outsider=b.b02.login(b.BASE,'operatore-senza-membership','synthetic-no-membership')
    editor=b.b02.login(b.BASE,'operatore-alfa-senza-lettura','synthetic-no-read')
    assert b.b02.request(b.BASE+'/api/v1/workshop'+path,method='POST',payload=payload)[0]==401
    for token,expected in [(beta,404),(outsider,404),(editor,403)]:
        assert b.call(path,token,'POST',payload)[0]==expected
        assert b.call('/orders/'+order['id']+'/commercial-summary',token)[0]==404
    for token in [beta,outsider,editor]:
        assert b.call('/catalog?legalEntityId='+b.A+'&siteId='+b.SITE,token)[0]==403
    assert b.call('/catalog?legalEntityId='+b.B+'&siteId='+b.SITE)[0]==403
    for item in ['22222222-7777-0000-0000-000000000001',str(uuid.uuid4())]:
        assert b.call(path,method='POST',payload=payload|{'catalogItemId':item})[0]==404
    for fields in [{'catalogVersion':999},{'configurationVersion':999},{'expectedRevision':1}]:
        assert b.call(path,method='POST',payload=payload|fields)[0]==409,fields
    for fields in [{'id':str(uuid.UUID(int=0))},{'catalogItemId':str(uuid.UUID(int=0))},
        {'catalogVersion':0},{'configurationVersion':0},{'expectedRevision':-1},
        {'total':'0'},{'payerId':b.OWNER},{'tenantId':b.C},{'workingGroupId':str(uuid.uuid4())}]:
        assert b.call(path,method='POST',payload=payload|fields)[0]==400,fields
    for field,values in {
        'quantity':['0','-0','-1','1.0000000','1000000','1,50','1e0','9999999999999999999999999999999999',' 1.50',1.5,None],
        'unitPrice':['-0','-55','55.0000001','1000000','55,00','1e999','9999999999999999999999999999',55,None],
        'discountPercent':['10.001','100.01','101','-0','-1','1e1',10,None]
    }.items():
        for value in values:
            status,result=b.call(path,method='POST',payload=payload|{field:value})
            assert status==400,(field,value,status,result)
    assert b.call('/orders/'+order['id']+'/commercial-summary')[1]['lines']==[]
    status,row=b.call(path,method='POST',payload=payload|{'quantity':'1.500','unitPrice':'55.000000'})
    assert status==201 and row['netAmount']=='74.250000',(status,row)
    assert b.call(path,method='POST',payload=payload|{'id':str(uuid.uuid4()),'expectedRevision':1})[0]==409
    print('PASS negatives: exact auth, cross tenant and same tenant denied, tampered refs/totals, strict strings/scales/overflow, precision boundary equivalent fixed values, no partial writes')

def concurrent():
    from concurrent.futures import ThreadPoolExecutor
    order=create_order(); path='/orders/'+order['id']+'/lines'; payload=line_body()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:b.call(path,method='POST',payload=payload),range(8)))
    assert sorted(x[0] for x in results)==[200]*7+[201],results
    assert all(x[1]==results[0][1] for x in results)
    order=create_order();path='/orders/'+order['id']+'/lines'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda kind:b.call(path,method='POST',payload=line_body(kind)),['Service','Part']))
    assert sorted(x[0] for x in results)==[201,409],results
    state=b.call('/orders/'+order['id']+'/commercial-summary')[1]
    assert state['revision']==1 and len(state['lines'])==1
    kind='Part' if state['lines'][0]['kind']=='Service' else 'Service'
    assert b.call(path,method='POST',payload=line_body(kind,1))[0]==201
    assert b.call('/orders/'+order['id']+'/commercial-summary')[1]['total']=='200.690000'
    print('PASS concurrent: eight identical retries one insert; competing revision only one succeeds, explicit refresh succeeds')

def denied_scope():
    order=create_order()
    assert b.call('/orders/'+order['id']+'/lines',method='POST',payload=line_body())[0]==403
    assert b.call('/orders/'+order['id']+'/commercial-summary')[0]==200
    print('PASS independent line-add action/resource scope denial, authorized read retained')

HISTORY='11111111-8888-0000-0000-000000000001'
HISTORY_LINE='11111111-9999-0000-0000-000000000001'
def prepare_history():
    status,order=b.call('/orders',method='POST',payload=b.body()|{'id':HISTORY})
    assert status==201,(status,order)
    payload=line_body()|{'id':HISTORY_LINE}
    assert b.call('/orders/'+HISTORY+'/lines',method='POST',payload=payload)[0]==201
    print('PASS prepared immutable history reference')
def history():
    status,state=b.call('/orders/'+HISTORY+'/commercial-summary')
    assert status==200 and state['total']=='90.585000' and state['lines'][0]['catalogLabel']=='Manodopera meccanica'
    assert state['lines'][0]['catalogVersion']==1 and state['lines'][0]['configurationVersion']==1
    print('PASS history: master/configuration change or disabled capability does not rewrite saved line values')
def replay_history():
    payload=line_body()|{'id':HISTORY_LINE}
    status,row=b.call('/orders/'+HISTORY+'/lines',method='POST',payload=payload)
    assert status==200 and row['catalogVersion']==1, ('committed retry must return historical snapshot',status,row)
    print('PASS retry returns committed values even when master reference version changes')

def collision_and_pool():
    beta=b.b02.login(b.BASE,'operatore-beta-sintetico','synthetic-beta-password')
    order=create_order(); payload=line_body(); path='/orders/'+order['id']+'/lines'
    assert b.call(path,method='POST',payload=payload)[0]==201
    foreign=b.body()|{'legalEntityId':b.C,'siteId':'22222222-2222-2222-2222-222222220101',
        'documentTypeId':'22222222-5555-0000-0000-000000000001',
        'payerId':'22222222-3333-0000-0000-000000000001','vehicleId':'22222222-4444-0000-0000-000000000001'}
    status,other=b.call('/orders',beta,'POST',foreign);assert status==201
    assert b.call('/orders/'+other['id']+'/lines',beta,'POST',payload|{'catalogItemId':'22222222-7777-0000-0000-000000000001'})[0]==409
    assert b.call('/orders/'+other['id']+'/lines',beta,'POST',line_body()|{'catalogItemId':'22222222-7777-0000-0000-000000000001'})[0]==201
    pids=[]
    for token,own,hidden,company,site,ids in [(b.alpha,order,other,b.A,b.SITE,[SERVICE,PART]),
      (beta,other,order,b.C,foreign['siteId'],['22222222-7777-0000-0000-000000000001','22222222-7777-0000-0000-000000000002'])]*5:
        status,rows=b.call('/catalog?legalEntityId='+company+'&siteId='+site,token)
        assert status==200 and [x['id'] for x in rows]==ids
        assert b.call('/orders/'+own['id']+'/commercial-summary',token)[0]==200
        assert b.call('/orders/'+hidden['id']+'/commercial-summary',token)[0]==404
        pids.append(b.b02.request(b.BASE+'/api/v1/organization/database-session',token)[1]['backendPid'])
    assert len(set(pids))==1,pids
    print('PASS cross-tenant command collision controlled; ten alternating persisted catalog/line reads use one reset pooled connection')

def denied_read():
    order=create_order()
    assert b.call('/orders/'+order['id']+'/commercial-summary')[0]==404
    print('PASS same-tenant creator/add permission never implies exact orders.read')

def stale_policy():
    order=create_order()
    assert b.call('/orders/'+order['id']+'/lines',method='POST',payload=line_body())[0]==409
    history(); replay_history()
    print('PASS latest company line policy applies to next operation; old line snapshot remains readable/retryable')

def disabled():
    history()
    assert b.call('/orders/'+HISTORY+'/lines',method='POST',payload=line_body()|{'id':HISTORY_LINE})[0]==403
    print('PASS disabled capability rejects even a write retry, not authorized historical read')

if __name__ == '__main__':
    globals()[sys.argv[2]]()
