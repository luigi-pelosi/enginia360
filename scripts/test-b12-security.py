#!/usr/bin/env python3
"""Additional B12 acceptance: exact scopes, historical snapshots, real RLS and controlled retry race."""
import json
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TENANT = '11111111-1111-1111-1111-111111111111'
COMPANY = '11111111-1111-1111-1111-111111111101'
MEMBER = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1'
TYPE = '11111111-7777-0000-0000-000000000010'

def client():
    import importlib.util
    spec = importlib.util.spec_from_file_location('b10', Path(__file__).with_name('test-b10.py'))
    assert spec and spec.loader
    b10 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b10)
    b = b10.b
    action = json.load(sys.stdin)
    def call(path='', method='GET', body=None):
        return b.b02.request(sys.argv[1] + '/api/v1/billing/workshop-invoices' + path, b.alpha, method, body)
    if action['kind'] == 'setup':
        status, order = b.call('/orders', b.alpha, 'POST', b.body())
        assert status == 201
        assert b.call(b10.order_path(order) + '/lines', b.alpha, 'POST', b10.b06.b05.line_body('Service'))[0] == 201
        status, summary = b.call(b10.order_path(order) + '/commercial-summary', b.alpha)
        assert status == 200 and b10.close(order, summary['revision'])[0] == 201
        result = {'id': str(uuid.uuid4()), 'orderId': order['id'], 'documentTypeId': TYPE,
                  'configurationVersion': 1, 'documentDate': '2026-10-20', 'currency': 'EUR', 'reference': 'TECH-RETRY'}
    elif action['kind'] == 'race':
        with ThreadPoolExecutor(max_workers=4) as pool:
            rows = list(pool.map(lambda _: call('', 'POST', action['body']), range(4)))
        codes = sorted(x[0] for x in rows)
        assert codes == [200, 200, 200, 201], ('same-ID concurrent retry was not idempotent', codes)
        assert all(x[1] == rows[0][1] for x in rows), 'same command returned differing documents'
        result = rows[0][1]
    elif action['kind'] == 'probe':
        result = []
        for item in action['requests']:
            status, value = call(item.get('path', ''), item.get('method', 'GET'), item.get('body'))
            assert status == item['expected'], (item.get('label'), status, value)
            result.append(value)
    else:
        raise AssertionError(action)
    print(json.dumps(result))

if len(sys.argv) > 2 and sys.argv[2] == 'client':
    client()
    raise SystemExit()

project = sys.argv[1]
assert project.startswith('enginia360-b12-'), 'only isolated B12 projects are authorized'
pg = project + '-postgres-1'
image = 'python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710'

def sql(text):
    p = subprocess.run(['docker','exec','-i',pg,'psql','-U','enginia360','-d','enginia360','-Atq','-v','ON_ERROR_STOP=1'],
                       input=text, text=True, capture_output=True, timeout=20)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()

def http(action):
    p = subprocess.run(['docker','run','--rm','-i','--network',project+'_backend','-v',str(Path.cwd())+':/source:ro',
                        '-w','/source',image,'python3','scripts/test-b12-security.py','http://web:8080','client'],
                       input=json.dumps(action), text=True, capture_output=True, timeout=45)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)

body = http({'kind':'setup'})
# Hold INSERT but not SELECT, so all retries observe no invoice before competing for insert.
lock = subprocess.Popen(['docker','exec','-i',pg,'psql','-U','enginia360','-d','enginia360','-Atq','-v','ON_ERROR_STOP=1'],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
assert lock.stdin and lock.stdout
lock.stdin.write('BEGIN; LOCK TABLE billing.invoices IN SHARE MODE;\n\\echo LOCKED\n'); lock.stdin.flush()
assert lock.stdout.readline().strip() == 'LOCKED'
with ThreadPoolExecutor(max_workers=1) as pool:
    future = pool.submit(http, {'kind':'race','body':body})
    try:
        deadline = time.monotonic()+25
        while int(sql("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND query LIKE '%INSERT INTO billing.invoices%';")) < 2:
            assert time.monotonic() < deadline, 'retry barrier did not observe competing inserts'
            time.sleep(.1)
    finally:
        lock.stdin.write('COMMIT;\n\\q\n'); lock.stdin.flush()
        lock.communicate(timeout=15)
    invoice = future.result()
print('PASS B12 controlled same-ID concurrent retry; four real competing inserts, one invoice')
invoice_id = invoice['id']
http({'kind':'probe','requests':[{'method':'POST','body':body | changed,'expected':400,'label':'untrusted invoice input'} for changed in [
    {'id':'00000000-0000-0000-0000-000000000000'}, {'reference':None}, {'currency':'USD'}, {'tenantId':TENANT}]]})
confirm = {'id':str(uuid.uuid4()),'configurationVersion':1}
def probes(items): return http({'kind':'probe','requests':items})
def requests(read=404, write=403):
    return [{'path':'/'+invoice_id,'expected':read,'label':'exact read scope'},
            {'method':'POST','body':body,'expected':write,'label':'exact create scope'},
            {'path':'/'+invoice_id+'/confirmation','method':'POST','body':confirm,'expected':write,'label':'exact confirm scope'}]
# Preserve only ephemeral fixtures and restore even on assertion failure.
sql("CREATE TABLE public.b12_permissions_backup AS SELECT * FROM organization_access.company_permissions WHERE \"Permission\" LIKE 'billing.%';")
try:
    for clause in ["\"Permission\"='not.billing'", "\"SiteId\"='11111111-1111-1111-1111-111111110201'",
                   "\"WarehouseId\"='11111111-1111-1111-1111-111111110111'", "\"LegalEntityId\"='11111111-1111-1111-1111-111111111102'"]:
        sql('DELETE FROM organization_access.company_permissions WHERE "MembershipId"=\''+MEMBER+'\' AND ("Permission" LIKE \'billing.%\' OR "Permission"=\'not.billing\'); INSERT INTO organization_access.company_permissions SELECT * FROM public.b12_permissions_backup; UPDATE organization_access.company_permissions SET '+clause+' WHERE "Permission" LIKE \'billing.%\';')
        probes(requests())
    sql('DELETE FROM organization_access.company_permissions WHERE "Permission" LIKE \'billing.%\'; INSERT INTO organization_access.company_permissions SELECT * FROM public.b12_permissions_backup;')
    sql('UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability"=\'internal-billing\';')
    probes(requests(read=200))
finally:
    sql('DELETE FROM organization_access.company_permissions WHERE "Permission" LIKE \'billing.%\' OR "Permission"=\'not.billing\'; INSERT INTO organization_access.company_permissions SELECT * FROM public.b12_permissions_backup; DROP TABLE public.b12_permissions_backup; UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability"=\'internal-billing\';')
print('PASS B12 exact action, wrong-site, warehouse-only and foreign-company scopes separately; disabled writes and historical read')
confirmed = probes([{'path':'/'+invoice_id+'/confirmation','method':'POST','body':confirm,'expected':201}])[0]
# Actual master edits after confirmation must not rewrite any serialized historical value.
sql('CREATE TABLE public.b12_party_backup AS SELECT * FROM counterparties.counterparties; CREATE TABLE public.b12_issuer_backup AS SELECT * FROM billing.issuer_profiles; UPDATE counterparties.counterparties SET "LegalName"=\'Changed synthetic recipient\',"FiscalIdentifier"=\'CHANGED\',"RegisteredOffice"=\'Changed\'; UPDATE billing.issuer_profiles SET "LegalName"=\'Changed synthetic issuer\',"FiscalIdentifier"=\'CHANGED\',"RegisteredOffice"=\'Changed\';')
try:
    readback = probes([{'path':'/'+invoice_id,'expected':200}, {'path':'/'+invoice_id+'/confirmation','method':'POST','body':confirm,'expected':200}])
    assert all(row == confirmed for row in readback), 'confirmed history changed with party master edits'
finally:
    sql('UPDATE counterparties.counterparties c SET "LegalName"=b."LegalName","FiscalIdentifier"=b."FiscalIdentifier","RegisteredOffice"=b."RegisteredOffice" FROM public.b12_party_backup b WHERE c."Id"=b."Id"; UPDATE billing.issuer_profiles c SET "LegalName"=b."LegalName","FiscalIdentifier"=b."FiscalIdentifier","RegisteredOffice"=b."RegisteredOffice" FROM public.b12_issuer_backup b WHERE c."LegalEntityId"=b."LegalEntityId" AND c."Version"=b."Version"; DROP TABLE public.b12_party_backup,public.b12_issuer_backup;')
print('PASS B12 actual master-data mutation preserves confirmed issuer, recipient, lines, values and references exactly')
fault_body = http({'kind':'setup'})
sql('REVOKE INSERT ON billing.invoices FROM enginia360_app;')
try:
    probes([{'method':'POST','body':fault_body,'expected':500,'label':'controlled intermodule failure'}])
    assert sql('SELECT count(*) FROM workshop.internal_billing_claims WHERE "InvoiceId"=\''+fault_body['id']+'\';') == '1'
    assert sql('SELECT count(*) FROM billing.invoices WHERE "Id"=\''+fault_body['id']+'\';') == '0'
finally:
    sql('GRANT INSERT ON billing.invoices TO enginia360_app;')
recovered = probes([{'method':'POST','body':fault_body,'expected':201}, {'method':'POST','body':fault_body,'expected':200}])
assert recovered[0] == recovered[1] and recovered[0]['destinationVersion'] == 1
sql('DELETE FROM billing.invoices WHERE "Id"=\''+fault_body['id']+'\'; DELETE FROM workshop.internal_billing_claims WHERE "InvoiceId"=\''+fault_body['id']+'\';')
print('PASS B12 actual intermodule fault after Workshop commit; stable claim recovered by exact retry with no duplicate')
# Extra rows belong solely to this test, so leave original acceptance count assertions unchanged.
sql('DELETE FROM billing.invoice_confirmations WHERE "InvoiceId"=\''+invoice_id+'\'; DELETE FROM billing.invoices WHERE "Id"=\''+invoice_id+'\'; DELETE FROM workshop.internal_billing_claims WHERE "InvoiceId"=\''+invoice_id+'\';')
