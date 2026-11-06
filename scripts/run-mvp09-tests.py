#!/usr/bin/env python3
"""Final-phase ONLY: one generated seven-domain journey, existing bounded TLS runner.
No supplied target; fixture-only identity/bootstrap is distinct from public D97/D98.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import uuid
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]
BASE = 'b00fdbafd3f91f6526caf18e75b79476ab02660f'
BROWSER = 'mvp09-integrated-acceptance.cjs'
spec = importlib.util.spec_from_file_location('mvp08_runner', ROOT/'scripts/run-mvp08-tests.py')
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def canonical(value):
    assert isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).int
    return value


def prepare_fixture(state, sql, identities):
    # Already-registered trusted delegate has a binding but must NOT be joined to
    # the old fixture tenant: published ordinary membership uniqueness is retained.
    fixture = json.loads((state/'browser.json').read_text())
    old = fixture['grantTargetMembershipId']
    line = f"INSERT INTO organization_access.memberships VALUES ('{old}','{fixture['contexts'][0]['tenantId']}','{identities[5]}');"
    assert sql.count(line) == 1
    return sql.replace(line, '')


def validate_journey(specification, facts):
    tenant = canonical(specification['ctx']['tenantId'])
    company = canonical(specification['ctx']['legalEntityId'])
    site = canonical(specification['ctx']['siteId'])
    warehouse = canonical(specification['ctx']['warehouseId'])
    member = canonical(specification['member']['membershipId'])
    assert facts['tenant']['Id'] == tenant
    assert facts['company']['Id'] == company and facts['company']['TenantId'] == tenant
    assert facts['site']['Id'] == site and facts['site']['LegalEntityId'] == company
    assert facts['warehouse']['Id'] == warehouse and facts['warehouse']['SiteId'] == site
    assert facts['membership']['Id'] == member and facts['membership']['TenantId'] == tenant
    assert len(facts['approval']) == 1 and len(facts['access']) == 1
    approved = [row for row in facts['onboardingAudit'] if row['Outcome']=='applied' and row['After'].get('membershipId')==member]
    assert len(approved)==1 and approved[0]['After']['enabled'] is False
    assert approved[0]['Authority']['kind']=='user-administration'
    enabled = [row for row in facts['accessAudit'] if row['Outcome']=='applied' and row['ResourceId']==member]
    assert len(enabled)==1 and enabled[0]['Before']['enabled'] is False and enabled[0]['After']['enabled'] is True
    assert facts['access'][0]['Enabled'] is True
    # Independent persisted identities, not a boolean from seven old suites.
    assert facts['supplier']['Id'] == specification['supplierId']
    assert facts['supplier']['TenantId'] == tenant and facts['supplier']['IsSupplier'] is True
    assert len(facts['destinations']) == 1
    assert facts['destinations'][0]['OwnerLegalEntityId'] == company
    assert {row['Id'] for row in facts['catalog']} == set(specification['catalogIds'])
    assert {row['Kind'] for row in facts['catalog']} == {'Part', 'Service'}
    assert {row['Effect'] for row in facts['types']} == {'Load', 'Unload', 'Transfer', 'None'}
    assert all(row['TenantId'] == tenant and row['LegalEntityId'] == company for row in facts['types'])
    headers = {row['Id']: row for row in facts['headers']}
    assert set(specification['effectDocuments'].values()) <= set(headers)
    assert all(headers[id]['State'] == 'Confirmed' for id in specification['effectDocuments'].values())
    for effect, id in specification['effectDocuments'].items():
        legs = [row for row in facts['ledger'] if row['DocumentId'] == id]
        expected = {'Load': [Decimal('2')], 'Unload': [Decimal('-1')],
                    'Transfer': [Decimal('-1'), Decimal('1')], 'None': []}[effect]
        assert sorted(Decimal(str(row['Quantity'])) for row in legs) == sorted(expected), effect
    assert all(headers[row['DocumentId']]['State'] == 'Confirmed' for row in facts['ledger'])
    for balance in facts['balances']:
        assert sum((Decimal(str(row['Quantity'])) for row in facts['ledger'] if all(row[k] == balance[k] for k in ('TenantId','LegalEntityId','SiteId','WarehouseId','CatalogItemId'))), Decimal(0)) == Decimal(str(balance['Quantity']))
    assert len(facts['origins']) == 32  # same real retained development journey
    grouped = [row for row in facts['origins'] if row['DocumentId'] == specification['groupedId']]
    assert len(grouped) == 2 and len({row['SourceTypeId'] for row in grouped}) == 2
    assert any(row['DocumentId'] == specification['hopId'] and row['SourceDocumentId'] == specification['groupedId'] for row in facts['origins'])
    assert len({row['CommandId'] for row in facts['audit']}) == len(facts['audit'])
    assert len(facts['delegations']) >= 1 and len(facts['roleAudit']) >= 1


def handle_control(action, *, state, evidence, query, command, mounts, identities, r00):
    if action == 'register-trusted':
        ctx = json.loads((evidence/'mvp09-created-context.json').read_text())
        for key in ('tenantId','legalEntityId','siteId','warehouseId'): canonical(ctx[key])
        target = str(uuid.uuid4())
        r00.run(query, input=f"INSERT INTO organization_access.memberships VALUES ('{target}','{ctx['tenantId']}','{identities[5]}');")
        row = json.loads(r00.run(query+['-c', f"SELECT row_to_json(m) FROM organization_access.memberships m WHERE \"Id\"='{target}'"]))
        assert row['TenantId'] == ctx['tenantId'] and row['IdentitySubject'] == identities[5]
        fixture = json.loads((state/'browser.json').read_text())
        fixture['contexts'][0] = ctx
        fixture['grantTargetMembershipId'] = target
        runner.write_readonly_json(state/'browser.json', fixture)
        (evidence/'mvp09-offline-trusted-registration.json').write_text(json.dumps(dict(fixtureOnly=True, synthetic=True, operativeGrants=[], delegationGranted=False, verification='generated fixture binding matched exactly; not real identity verification', membership=row), indent=2))
        return True
    if action == 'counterparty-master-setup':
        fixture = json.loads((state/'browser.json').read_text()); ctx = fixture['contexts'][0]
        payload = dict(commandId=str(uuid.uuid4()), domain='counterparties', tenantId=ctx['tenantId'], actorMembershipId=fixture['grantTargetMembershipId'], verificationReference=str(uuid.uuid4()), expectedVersion=0, direction='Enginia360ToExternal', sourceId=str(uuid.uuid4()), profileId=str(uuid.uuid4()), companyIds=[ctx['legalEntityId']])
        runner.write_readonly_json(state/'public/counterparty-authority.json', payload)
        for _ in range(2):
            output = r00.run(command+['run','--rm','--no-deps','-T',*mounts,'--entrypoint','python3','migrator','scripts/owner-master-authority.py','/run/tls/counterparty-authority.json'], timeout=45)
            assert 'exact history read back' in output
        (evidence/'mvp09-explicit-counterparty-authority.json').write_text(json.dumps(dict(fixtureOnly=True, setup=payload), indent=2))
        return True
    if action != 'integrated-readback':
        return False
    expected = json.loads((evidence/'mvp09-journey-spec.json').read_text())
    ctx = expected['ctx']; tenant = canonical(ctx['tenantId']); member = canonical(expected['member']['membershipId'])
    supplier = canonical(expected['supplierId']); company = canonical(ctx['legalEntityId'])
    catalog_ids = ','.join("'"+canonical(id)+"'" for id in expected['catalogIds'])
    scalar = {
        'tenant': ('organization_access.tenants', f'"Id"=\'{tenant}\''),
        'company': ('organization_access.legal_entities', f'"Id"=\'{company}\''),
        'site': ('organization_access.sites', f'"Id"=\'{canonical(ctx["siteId"])}\''),
        'warehouse': ('organization_access.warehouses', f'"Id"=\'{canonical(ctx["warehouseId"])}\''),
        'membership': ('organization_access.memberships', f'"Id"=\'{member}\''),
        'supplier': ('counterparties.counterparties', f'"Id"=\'{supplier}\''),
    }
    arrays = {
        'approval': ('organization_access.onboarding_requests', f'"Id"=\'{canonical(expected["requestId"])}\''),
        'access': ('organization_access.membership_access_state', f'"MembershipId"=\'{member}\''),
        'destinations': ('counterparties.destinations', f'"CounterpartyId"=\'{supplier}\''),
        'catalog': ('catalog.items', f'"Id" IN ({catalog_ids})'),
        'types': ('(SELECT d.*, v."Effect" FROM document_types.definitions d JOIN document_types.versions v ON v."DocumentTypeId"=d."Id" AND v."Revision"=d."Revision")', f'"TenantId"=\'{tenant}\''),
        'delegations': ('organization_access.organization_delegations', f'"TenantId"=\'{tenant}\''),
        'onboardingAudit': ('organization_access.onboarding_audit', f'"TenantId"=\'{tenant}\''),
        'accessAudit': ('organization_access.membership_access_audit', f'"TenantId"=\'{tenant}\''),
        'roleAudit': ('organization_access.tenant_role_audit', f'"TenantId"=\'{tenant}\''),
        **{key: ('documents.'+table, f'"TenantId"=\'{tenant}\'') for key,table in [('headers','headers'),('ledger','ledger'),('balances','balances'),('origins','origins'),('audit','command_audit')]},
    }
    fields = [f"'{key}',(SELECT to_jsonb(x) FROM {table} x WHERE {where})" for key,(table,where) in scalar.items()]
    fields += [f"'{key}',(SELECT coalesce(jsonb_agg(to_jsonb(x)), '[]'::jsonb) FROM {table} x WHERE {where})" for key,(table,where) in arrays.items()]
    facts = json.loads(r00.run(query+['-c','SELECT jsonb_build_object('+','.join(fields)+')']))
    (evidence/'mvp09-integrated-sql.json').write_text(json.dumps(facts, indent=2))
    validate_journey(expected, facts)
    # Same freshly approved identity through the REAL app-role SD/RLS boundary.
    settings = r00.verified_fixture_settings(query, member)
    id = canonical(expected['hopId']); site = canonical(ctx['siteId'])
    sql = f"SELECT documents.read('{company}','{site}',NULL,'{id}',NULL,NULL,NULL,NULL,NULL);"
    output = r00.run(query, input='BEGIN; SET LOCAL ROLE runtime_app; '+settings+sql+' ROLLBACK;')
    projection = json.loads(next(line for line in reversed(output.splitlines()) if line.startswith('{')))
    assert projection['detail']['id'] == id
    foreign = canonical(expected['foreignCompany'])
    denied = r00.run(query, input='BEGIN; SET LOCAL ROLE runtime_app; '+settings+f"SELECT documents.read('{foreign}',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL); ROLLBACK;")
    refusal = json.loads(next(line for line in reversed(denied.splitlines()) if line.startswith('{')))
    assert refusal['state'] == 'forbidden'
    (evidence/'mvp09-app-role-rls.json').write_text(json.dumps(dict(allowed=projection, denied=refusal, syntheticVerifiedPrincipal=True), indent=2))
    return True


if __name__ == '__main__':
    os.environ['MVP08_POOL_SIZE'] = os.environ.get('MVP09_POOL_SIZE', '4')
    runner.main(acceptance=sys.modules[__name__])
    print('PASS MVP09 complete integrated journey and guarded protected cleanup', flush=True)
