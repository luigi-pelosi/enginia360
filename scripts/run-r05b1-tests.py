#!/usr/bin/env python3
"""Reuse R05.b.0's exact cleanup, TLS, OIDC, SQL and lifecycle boundaries with a Giobby-protocol fake."""
import importlib.util
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('binding', ROOT/'scripts/run-r05b0-tests.py')
assert spec and spec.loader
binding = importlib.util.module_from_spec(spec); spec.loader.exec_module(binding)
binding.SPEC = 'r05b1-acceptance.cjs'
binding.r00.CONFIG = ROOT/'compose.r05b1-test.yaml'
original = binding.fixtures
def fixtures(state, secret):
    sql = original(state, secret)
    fixture = json.loads((state/'browser.json').read_text())
    ctx, data = fixture['contexts'][0], fixture['workshop'][0]
    for service, name in [('giobby-a', 'admin-simulator'), ('giobby-b', 'simulator-b')]: binding.r00.certificate(state, service, name, 65534)
    token = state/'token'; token.write_text('synthetic-runtime-token'); token.chmod(0o400); binding.r00.own(state, 'token', 1654)
    host = {'TenantId': ctx['tenantId'], 'LegalEntityId': ctx['legalEntityId'], 'SiteId': ctx['siteId'],
            'AllowedHosts': ['admin-simulator', 'simulator-b'], 'TokenFile': '/run/giobby-token', 'CompanyId': 101, 'Cid': 'SYNTH-CID-A',
            'Storage': 'MB', 'BusinessUnit': 'U1', 'Numerator': 1,
            'Customers': {data['payerId']: {'Id': 'owned-customer-1', 'ContactId': 9001, 'LookupName': 'Owned synthetic customer'}},
            'Materials': {data['serviceId']: 'owned-product-1'}, 'Taxes': {'22.000000': '22'}}
    (state/'giobby.json').write_text(json.dumps({'ExternalAdministration': {'Giobby': host}}))
    return sql
binding.fixtures = fixtures
if __name__ == '__main__': binding.main()
