#!/usr/bin/env python3
"""Private synthetic B04 real HTTP acceptance, one tracer per invocation."""
import importlib.util
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('b02', Path(__file__).with_name('test-b02.py'))
assert spec is not None and spec.loader is not None
b02 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b02)
BASE = sys.argv[1]
A = '11111111-1111-1111-1111-111111111101'
B = '11111111-1111-1111-1111-111111111102'
C = '22222222-2222-2222-2222-222222222201'
SITE = '11111111-1111-1111-1111-111111110101'
PAYER = '11111111-3333-0000-0000-000000000001'
VEHICLE = '11111111-4444-0000-0000-000000000001'
OWNER = '11111111-3333-0000-0000-000000000002'
TYPE = '11111111-5555-0000-0000-000000000001'
alpha = b02.login(BASE, 'operatore-alfa-sintetico', 'synthetic-alpha-password')

def call(path, token=alpha, method='GET', payload=None):
    return b02.request(BASE + '/api/v1/workshop' + path, token, method, payload)

def body():
    import uuid
    return dict(id=str(uuid.uuid4()), legalEntityId=A, siteId=SITE,
                documentTypeId=TYPE, configurationVersion=1,
                payerId=PAYER, vehicleId=VEHICLE)

def direct_order():
    status, vehicles = call('/vehicles?legalEntityId=' + A + '&siteId=' + SITE)
    assert status == 200, ('tenant-wide vehicle selector expected 200', status, vehicles)
    assert vehicles == [{'id': VEHICLE, 'label': 'Veicolo sintetico altra società'}], vehicles
    payload = body()
    status, created = call('/orders', method='POST', payload=payload)
    assert status == 201, ('direct work order expected 201', status, created)
    assert created['payerId'] == PAYER and created['vehicleHolderId'] == OWNER
    assert created['configurationVersion'] == 1 and created['siteId'] == SITE
    assert created['isCustomerOrder'] is True
    assert call('/orders/' + created['id']) == (200, created)
    assert call('/orders', method='POST', payload=payload) == (200, created)
    assert call('/orders', method='POST', payload=payload | {'payerId': OWNER})[0] == 409
    print('PASS direct_order: tenant-wide minimal selector, persisted direct customer order, distinct payer/holder, config version, reread/retry/conflict')

def isolation_and_references():
    beta = b02.login(BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    outsider = b02.login(BASE, 'operatore-senza-membership', 'synthetic-no-membership')
    editor = b02.login(BASE, 'operatore-alfa-senza-lettura', 'synthetic-no-read')
    query = '?legalEntityId=' + A + '&siteId=' + SITE
    assert call('/vehicles'+query, outsider)[0] == 403
    assert call('/orders', outsider, 'POST', body())[0] == 403
    assert call('/orders', editor, 'POST', body())[0] == 403
    assert b02.request(BASE+'/api/v1/workshop/vehicles'+query)[0] == 401
    assert b02.request(BASE+'/api/v1/workshop/vehicles'+query, extra_headers={'X-Tenant-Id':A,'X-User-Id':'synthetic'})[0] == 401
    for changed in [
        {'legalEntityId': C}, {'legalEntityId': B},
        {'siteId':'11111111-1111-1111-1111-111111110201'},
        {'siteId':'22222222-2222-2222-2222-222222220201'}]:
        assert call('/orders', method='POST', payload=body() | changed)[0] == 403, changed
    for changed in [
        {'vehicleId':'22222222-4444-0000-0000-000000000001'},
        {'payerId':'22222222-3333-0000-0000-000000000001'},
        {'vehicleId':'99999999-0000-0000-0000-000000000001'},
        {'payerId':'99999999-0000-0000-0000-000000000001'}]:
        assert call('/orders', method='POST', payload=body() | changed)[0] == 404, changed
    for changed in [{'configurationVersion':999}, {'documentTypeId':'11111111-5555-0000-0000-000000000002'},
                    {'documentTypeId':'22222222-5555-0000-0000-000000000001'}]:
        assert call('/orders', method='POST', payload=body() | changed)[0] == 409, changed
    for field in ['id','legalEntityId','siteId','payerId','vehicleId','documentTypeId']:
        assert call('/orders', method='POST', payload=body() | {field:'00000000-0000-0000-0000-000000000000'})[0] == 400
        assert call('/orders', method='POST', payload=body() | {field:'not-a-guid'})[0] == 400
    assert call('/orders', method='POST', payload=body() | {'configurationVersion':0})[0] == 400
    # B04's alpha fixture has no Counterparties/Workshop management grant on B.
    assert b02.request(BASE+'/api/v1/counterparties?legalEntityId='+B, alpha)[0] == 403
    status, created = call('/orders', method='POST', payload=body() | {'tenantId':'22222222-2222-2222-2222-222222222222','vehicleHolderId':PAYER})
    assert status == 201 and created['vehicleHolderId'] == OWNER
    assert call('/orders/'+created['id'], beta)[0] == 404
    assert call('/orders/'+created['id'], outsider)[0] == 404
    assert call('/orders/'+created['id'], editor)[0] == 404
    # Two real persisted orders alternate over the same single physical pooled connection.
    beta_body = body() | {'legalEntityId':C,'siteId':'22222222-2222-2222-2222-222222220101',
        'documentTypeId':'22222222-5555-0000-0000-000000000001',
        'payerId':'22222222-3333-0000-0000-000000000001','vehicleId':'22222222-4444-0000-0000-000000000001'}
    status, other = call('/orders', beta, 'POST', beta_body)
    assert status == 201, (status, other)
    pids = []
    for token,own,foreign,company,site in [(alpha,created,other,A,SITE),
        (beta,other,created,C,beta_body['siteId'])]*5:
        assert call('/orders/'+own['id'], token) == (200,own)
        assert call('/orders/'+foreign['id'], token)[0] == 404
        choices = call('/vehicles?legalEntityId='+company+'&siteId='+site,token)
        assert choices[0] == 200 and choices[1][0]['id'] == own['vehicleId']
        session = b02.request(BASE+'/api/v1/organization/database-session',token)
        assert session[0] == 200
        pids.append(session[1]['backendPid'])
    assert len(set(pids)) == 1, pids
    print('PASS isolation_and_references: valid same-tenant missing action/company/site, cross-tenant/unknown IDs, malformed IDs, disabled/unknown config, no CRUD escalation, spoofing, 10 alternating RLS/pool reads')

def denied_scope():
    assert call('/vehicles?legalEntityId='+A+'&siteId='+SITE)[0] == 403
    assert call('/orders', method='POST', payload=body())[0] == 403
    print('PASS denied_scope: valid membership with insufficient exact action/resource scope')

def denied_read():
    status, saved = call('/orders', method='POST', payload=body())
    assert status == 201, (status,saved)
    assert call('/orders/'+saved['id'])[0] == 404, 'same-tenant creator without exact read action must not retrieve by ID'
    assert call('/orders/11111111-6666-0000-0000-000000000001')[0] == 404
    print('PASS denied_read: valid same-tenant create scope does not confer read-by-ID')

def historical_read():
    # Before changing capability/configuration, runner creates this known immutable reference.
    history_id = '11111111-6666-0000-0000-000000000001'
    status, saved = call('/orders/'+history_id)
    assert status == 200 and saved['configurationVersion'] == 1 and saved['payerId'] == PAYER, (status,saved)
    assert call('/orders', method='POST', payload=body())[0] in (403,409)
    print('PASS historical_read: disabled capability/new config blocks writes but retains authorized old version')

def prepare_history():
    status, saved = call('/orders', method='POST', payload=body() | {'id':'11111111-6666-0000-0000-000000000001'})
    assert status in (200,201), (status,saved)
    print('PASS prepare_history: persisted version-1 order for non-retroactivity checks')

def command_id_collision():
    beta = b02.login(BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    payload = body()
    assert call('/orders', method='POST', payload=payload)[0] == 201
    foreign = payload | {'legalEntityId':C,'siteId':'22222222-2222-2222-2222-222222220101',
        'documentTypeId':'22222222-5555-0000-0000-000000000001',
        'payerId':'22222222-3333-0000-0000-000000000001','vehicleId':'22222222-4444-0000-0000-000000000001'}
    status, result = call('/orders', beta, 'POST', foreign)
    assert status == 409, ('colliding untrusted command id must not produce database failure or expose foreign row', status, result)
    assert call('/orders/'+payload['id'], beta)[0] == 404
    print('PASS command_id_collision: cross-tenant identifier collision controlled, no disclosure')

def concurrent_retry():
    from concurrent.futures import ThreadPoolExecutor
    payload = body()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _:call('/orders', method='POST', payload=payload), range(8)))
    assert sorted(x[0] for x in results) == [200]*7+[201], results
    assert all(x[1] == results[0][1] for x in results)
    print('PASS concurrent_retry: 8 identical simultaneous requests, one creation and one resource')

def superseded_configuration():
    # Runner installs a newer disabled version immediately before this probe.
    status, result = call('/orders', method='POST', payload=body())
    assert status == 409, ('superseded configuration must not create new orders', status, result)
    print('PASS superseded_configuration: stale version cannot bypass current direct-creation policy')

def context_and_types():
    status, contexts = call('/contexts')
    assert status == 200, ('workshop contexts expected 200', status, contexts)
    assert any(x['legalEntityId'] == A and x['siteId'] == SITE for x in contexts)
    status, types = call('/document-types?legalEntityId=' + A + '&siteId=' + SITE)
    assert status == 200 and types == [
        {'id': TYPE, 'name': 'Commessa diretta sintetica', 'version': 1, 'directCreationEnabled': True},
        {'id': '11111111-5555-0000-0000-000000000002', 'name': 'Commessa non diretta sintetica', 'version': 1, 'directCreationEnabled': False}], (status, types)
    print('PASS context_and_types: server-authorized contexts and latest company type version')

def invalid_command_id():
    status, response = call('/orders', method='POST', payload=body() | {'id': '00000000-0000-0000-0000-000000000000'})
    assert status == 400, ('empty command ID must be a controlled 400', status, response)
    print('PASS invalid_command_id: empty command identifier rejected before persistence')

if __name__ == '__main__':
    globals()[sys.argv[2] if len(sys.argv) > 2 else 'direct_order']()
