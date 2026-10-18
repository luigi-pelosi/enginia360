#!/usr/bin/env python3
"""Non-destructive security probes for persistent synthetic B03 HTTPS."""
import importlib.util
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('b03', Path(__file__).with_name('test-b03.py'))
assert spec is not None and spec.loader is not None
b03 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b03)
call, login, request = b03.call, b03.login, b03.request
base = sys.argv[1]
beta = login(base, 'operatore-beta-sintetico', 'synthetic-beta-password')
outsider = login(base, 'operatore-senza-membership', 'synthetic-no-membership')
alpha_id = '11111111-3333-0000-0000-000000000001'
beta_id = '22222222-3333-0000-0000-000000000001'
for token, company, own, other in [(b03.alpha, b03.A, alpha_id, beta_id), (beta, b03.C, beta_id, alpha_id)] * 5:
    assert call('/'+own+'?legalEntityId='+company, token)[0] == 200
    assert call('/'+other+'?legalEntityId='+company, token)[0] == 404
assert call('?legalEntityId='+b03.C)[0] == 403
assert call('?legalEntityId='+b03.B, outsider)[0] == 403
assert call('/'+alpha_id+'?legalEntityId='+b03.B, outsider)[0] == 404
path = base+'/api/v1/counterparties?legalEntityId='+b03.A
assert request(path)[0] == 401
assert request(path, extra_headers={'X-Tenant-Id':'11111111-1111-1111-1111-111111111111','X-User-Id':'aaaaaaaa-0000-0000-0000-000000000001'})[0] == 401
bad = b03.alpha[:-1]+('A' if b03.alpha[-1]!='A' else 'B')
assert request(path, bad)[0] == 401
for company in [b03.A, b03.C, '00000000-0000-0000-0000-000000000000']:
    assert call('/'+alpha_id+'/destinations', method='POST', payload={'legalEntityId':company,'address':'Manipolazione sintetica'})[0] == 403
assert call('/'+beta_id+'/destinations', method='POST', payload={'legalEntityId':b03.B,'address':'ID altro tenant'})[0] == 404
for address in ['', ' ', 'x'*501, None]:
    assert call('/'+alpha_id+'/destinations', method='POST', payload={'legalEntityId':b03.B,'address':address})[0] == 400
assert call('/'+alpha_id+'/destinations', method='POST', payload={'legalEntityId':b03.B})[0] == 400
print('PASS persistent HTTPS: 10 alternating tenant reads, unauthorized membership/company, anonymous/spoofed identity, invalid JWT, manipulated IDs and invalid input; no diagnostic exposure or destructive SQL')
