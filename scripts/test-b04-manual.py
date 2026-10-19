#!/usr/bin/env python3
"""Persistent B04 acceptance: fresh orders only, no SQL or diagnostic access."""
import importlib.util
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location('b04', Path(__file__).with_name('test-b04.py'))
assert spec and spec.loader
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
b.context_and_types()
b.direct_order()
b.invalid_command_id()
b.concurrent_retry()
b.command_id_collision()
beta = b.b02.login(b.BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
outsider = b.b02.login(b.BASE, 'operatore-senza-membership', 'synthetic-no-membership')
editor = b.b02.login(b.BASE, 'operatore-alfa-senza-lettura', 'synthetic-no-read')
for token in [outsider, editor]:
    assert b.call('/orders', token, 'POST', b.body())[0] == 403
for changed, expected in [
    ({'legalEntityId':b.B},403), ({'legalEntityId':b.C},403),
    ({'siteId':'11111111-1111-1111-1111-111111110201'},403),
    ({'vehicleId':'22222222-4444-0000-0000-000000000001'},404),
    ({'payerId':'22222222-3333-0000-0000-000000000001'},404),
    ({'payerId':'99999999-0000-0000-0000-000000000001'},404),
    ({'vehicleId':'99999999-0000-0000-0000-000000000001'},404),
    ({'configurationVersion':999},409),
    ({'documentTypeId':'11111111-5555-0000-0000-000000000002'},409),
    ({'documentTypeId':'22222222-5555-0000-0000-000000000001'},409),
    ({'configurationVersion':0},400)]:
    assert b.call('/orders', method='POST', payload=b.body() | changed)[0] == expected, changed
for field in ['id','legalEntityId','siteId','payerId','vehicleId','documentTypeId']:
    for invalid in ['00000000-0000-0000-0000-000000000000','not-a-guid']:
        assert b.call('/orders', method='POST',payload=b.body() | {field:invalid})[0] == 400
assert b.b02.request(b.BASE+'/api/v1/counterparties?legalEntityId='+b.B,b.alpha)[0] == 403
status,saved=b.call('/orders',method='POST',payload=b.body() | {'tenantId':b.C,'vehicleHolderId':b.PAYER})
assert status==201 and saved['vehicleHolderId']==b.OWNER and saved['payerId']==b.PAYER
for token in [beta,outsider,editor]:assert b.call('/orders/'+saved['id'],token)[0]==404
other_payload=b.body() | {'legalEntityId':b.C,'siteId':'22222222-2222-2222-2222-222222220101','documentTypeId':'22222222-5555-0000-0000-000000000001','payerId':'22222222-3333-0000-0000-000000000001','vehicleId':'22222222-4444-0000-0000-000000000001'}
status,other=b.call('/orders',beta,'POST',other_payload)
assert status==201
for token,own,foreign in [(b.alpha,saved,other),(beta,other,saved)]*5:
    assert b.call('/orders/'+own['id'],token)==(200,own)
    assert b.call('/orders/'+foreign['id'],token)[0]==404
path=b.BASE+'/api/v1/workshop/contexts'
assert b.b02.request(path)[0]==401
assert b.b02.request(path,extra_headers={'X-Tenant-Id':b.A,'X-User-Id':'synthetic'})[0]==401
print('PASS persistent B04 HTTPS: fresh orders, exact company/site/type/version, distinct immutable payer/holder, invalid input/references/permissions, spoofing, ten alternating isolated reads; no SQL/diagnostics/older-project mutation')
print('Persisted reread reference:',saved['id'])
