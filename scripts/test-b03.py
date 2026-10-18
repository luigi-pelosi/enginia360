#!/usr/bin/env python3
"""B03 real HTTP behavior probes; synthetic identities only."""
import sys
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('b02', Path(__file__).with_name('test-b02.py'))
assert spec is not None and spec.loader is not None
b02 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b02)
login, request = b02.login, b02.request

A = '11111111-1111-1111-1111-111111111101'
B = '11111111-1111-1111-1111-111111111102'
C = '22222222-2222-2222-2222-222222222201'
BASE = sys.argv[1]
alpha = login(BASE, 'operatore-alfa-sintetico', 'synthetic-alpha-password')

def call(path, token=alpha, method='GET', payload=None):
    return request(BASE + '/api/v1/counterparties' + path, token, method, payload)

def shared_identity():
    status, one = call('?legalEntityId=' + A)
    assert status == 200, ('shared identity list expected 200', status, one)
    status, two = call('?legalEntityId=' + B)
    assert status == 200 and len(one) == 1 and one == two, (status, one, two)
    assert set(one[0]) == {'id', 'tenantId', 'legalName', 'fiscalIdentifier', 'registeredOffice'}
    assert call('/' + one[0]['id'] + '?legalEntityId=' + A) == (200, one[0])
    print('PASS shared_identity: A/B same persisted D36 identity')

def private_destination():
    _, rows = call('?legalEntityId=' + B)
    counterparty = rows[0]['id']
    status, dest = call('/' + counterparty + '/destinations', method='POST', payload={'legalEntityId': B, 'address': 'Destinazione sintetica riservata', 'published': True, 'tenantId': '22222222-2222-2222-2222-222222222222', 'ownerLegalEntityId': A})
    assert status == 201, ('private destination create expected 201', status, dest)
    assert dest['published'] is False and dest['ownerLegalEntityId'] == B
    assert call('/' + counterparty + '/destinations?legalEntityId=' + B)[1] and dest in call('/' + counterparty + '/destinations?legalEntityId=' + B)[1]
    assert dest not in call('/' + counterparty + '/destinations?legalEntityId=' + A)[1]
    assert call('/destinations/' + dest['id'] + '?legalEntityId=' + A)[0] == 404
    assert call('/destinations/' + dest['id'] + '?legalEntityId=' + B) == (200, dest)
    beta = login(BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    assert call('/destinations/' + dest['id'] + '?legalEntityId=' + C, beta)[0] == 404
    print('PASS private_destination: real create, company-private list/direct-ID, cross-tenant exclusion')

def publication():
    _, rows = call('?legalEntityId=' + B)
    _, dest = call('/' + rows[0]['id'] + '/destinations', method='POST', payload={'legalEntityId': B, 'address': 'Pubblicazione sintetica'})
    path = '/destinations/' + dest['id'] + '/publication'
    editor = login(BASE, 'operatore-alfa-senza-lettura', 'synthetic-no-read')
    assert call(path, editor, 'POST', {'legalEntityId': B})[0] == 403, 'common edit plus site/warehouse grants must not publish'
    assert call(path, alpha, 'POST', {'legalEntityId': A})[0] in (403, 404)
    assert call('/destinations/' + dest['id'] + '?legalEntityId=' + A)[0] == 404
    status, published = call(path, method='POST', payload={'legalEntityId': B})
    assert status == 200, ('owner-company publication expected 200', status, published)
    assert published['id'] == dest['id'] and published['published'] is True
    assert call('/destinations/' + dest['id'] + '?legalEntityId=' + A) == (200, published)
    assert published in call('/' + rows[0]['id'] + '/destinations?legalEntityId=' + A)[1]
    beta = login(BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    assert call('/destinations/' + dest['id'] + '?legalEntityId=' + C, beta)[0] == 404
    assert call(path, beta, 'POST', {'legalEntityId': C})[0] in (403, 404)
    print('PASS publication: owner company permission, common-edit/site/warehouse denied, A visible only after explicit publication, cross-tenant denied')

def common_edit():
    _, rows = call('?legalEntityId=' + B)
    cp = rows[0]
    update = {'legalEntityId': B, 'legalName': 'Modifica comune sintetica', 'fiscalIdentifier': 'SYNTHETIC-EDIT', 'registeredOffice': 'Sede sintetica aggiornata'}
    assert call('/' + cp['id'], method='PUT', payload=update)[0] == 403, 'publication permission does not confer common editing'
    assert call('/' + cp['id'] + '?legalEntityId=' + B) == (200, cp)
    editor = login(BASE, 'operatore-alfa-senza-lettura', 'synthetic-no-read')
    status, saved = call('/' + cp['id'], editor, 'PUT', update)
    assert status == 200, ('specific common editor expected 200', status, saved)
    assert saved['id'] == cp['id'] and saved['legalName'] == update['legalName']
    assert call('/' + cp['id'] + '?legalEntityId=' + A) == (200, saved)
    _, dest = call('/' + cp['id'] + '/destinations', method='POST', payload={'legalEntityId': B, 'address': 'Test edit non pubblica'})
    assert call('/destinations/' + dest['id'] + '/publication', editor, 'POST', {'legalEntityId': B})[0] == 403
    assert call('/destinations/' + dest['id'] + '?legalEntityId=' + A)[0] == 404
    assert call('/' + cp['id'], editor, 'PUT', update | {'legalEntityId': C})[0] == 403
    assert call('/22222222-3333-0000-0000-000000000001', editor, 'PUT', update)[0] == 404
    for name in ['legalName', 'fiscalIdentifier', 'registeredOffice']:
        assert call('/' + cp['id'], editor, 'PUT', update | {name: ' '})[0] == 400
    print('PASS common_edit: distinct specific edit permission, shared identity updated once, no publication implication, input validation')

def company_choices():
    editor = login(BASE, 'operatore-alfa-senza-lettura', 'synthetic-no-read')
    status, companies = call('/companies', editor)
    assert status == 200, ('B03-specific companies expected 200', status, companies)
    assert [x['legalEntityId'] for x in companies] == [B]
    assert call('/' + '11111111-3333-0000-0000-000000000001' + '?legalEntityId=' + A, editor)[0] == 404
    assert call('?legalEntityId=' + A, editor)[0] == 403
    print('PASS company_choices: B03-specific permission, not B02 context capability, no same-tenant unauthorized company')

def search_identity():
    assert call('?legalEntityId=' + A + '&search=impossible-synthetic-query') == (200, []), 'search must filter common identity'
    _, rows = call('?legalEntityId=' + A)
    import urllib.parse
    assert call('?legalEntityId=' + B + '&search=' + urllib.parse.quote(rows[0]['legalName'])) == (200, rows)
    assert call('?legalEntityId=' + A + '&search=' + 'x'*201)[0] == 400
    print('PASS search_identity: scoped parameterized common search and bounded input')

def isolation_and_pool():
    beta = login(BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    outsider = login(BASE, 'operatore-senza-membership', 'synthetic-no-membership')
    editor = login(BASE, 'operatore-alfa-senza-lettura', 'synthetic-no-read')
    alpha_id='11111111-3333-0000-0000-000000000001'
    beta_id='22222222-3333-0000-0000-000000000001'
    pids=[]
    for token,company,own,other in [(alpha,A,alpha_id,beta_id),(beta,C,beta_id,alpha_id)]*5:
        assert call('/'+own+'?legalEntityId='+company,token)[0]==200
        assert call('/'+other+'?legalEntityId='+company,token)[0]==404
        status, session=request(BASE+'/api/v1/organization/database-session',token)
        assert status==200
        pids.append(session['backendPid'])
    assert len(set(pids))==1,pids
    assert call('?legalEntityId='+C)[0]==403
    assert call('?legalEntityId='+B,outsider)[0]==403
    assert call('/'+alpha_id+'?legalEntityId='+B,outsider)[0]==404
    assert call('/'+alpha_id+'?legalEntityId='+A,editor)[0]==404
    assert request(BASE+'/api/v1/counterparties?legalEntityId='+A)[0]==401
    assert request(BASE+'/api/v1/counterparties?legalEntityId='+A,extra_headers={'X-Tenant-Id':'11111111-1111-1111-1111-111111111111','X-User-Id':'aaaaaaaa-0000-0000-0000-000000000001'})[0]==401
    for company in [A,C,'00000000-0000-0000-0000-000000000000']:
        assert call('/'+alpha_id+'/destinations',method='POST',payload={'legalEntityId':company,'address':'Manipolazione sintetica'})[0]==403
    assert call('/'+beta_id+'/destinations',method='POST',payload={'legalEntityId':B,'address':'ID altro tenant'})[0]==404
    for address in ['', ' ', 'x'*501]:
        assert call('/'+alpha_id+'/destinations',method='POST',payload={'legalEntityId':B,'address':address})[0]==400
    for payload in [{'legalEntityId':B}, {'legalEntityId':B,'address':None}]:
        assert call('/'+alpha_id+'/destinations',method='POST',payload=payload)[0]==400
    print('PASS isolation_and_pool: 10 alternating real B03 tenant reads, same physical pooled PID, missing membership, spoofed headers, manipulated IDs and invalid input')

if __name__ == '__main__':
    globals()[sys.argv[2] if len(sys.argv) > 2 else 'shared_identity']()
