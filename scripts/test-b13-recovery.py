#!/usr/bin/env python3
"""B13 exact-scope, intermodule fault and recovery acceptance against the isolated stack."""
import json
import subprocess
import sys
import uuid
from pathlib import Path

MEMBER = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1'


def client():
    import importlib.util
    spec = importlib.util.spec_from_file_location('b10', Path(__file__).with_name('test-b10.py'))
    assert spec and spec.loader
    b10 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b10)
    b = b10.b
    b.BASE = sys.argv[1].rstrip('/')
    action = json.load(sys.stdin)

    def call(path='', method='GET', body=None):
        return b.b02.request(b.BASE + '/api/v1/accounting/invoice-journal-entries' + path, b.alpha, method, body)

    if action['kind'] != 'probe':
        raise AssertionError(action['kind'])
    result = []
    for item in action['requests']:
        if item.get('target') == 'billing':
            status, value = b.b02.request(b.BASE + '/api/v1/billing/workshop-invoices' + item.get('path', ''),
                                          b.alpha, item.get('method', 'GET'), item.get('body'))
        else:
            status, value = call(item.get('path', ''), item.get('method', 'GET'), item.get('body'))
        assert status == item['expected'], (item.get('label'), status, value)
        result.append(value)
    print(json.dumps(result))


if len(sys.argv) > 3 and sys.argv[3] == 'client':
    client()
    raise SystemExit()

project, runtime_path = sys.argv[1], sys.argv[2]
assert project.startswith('enginia360-b13-'), 'only isolated B13 projects are authorized'
runtime = [json.loads(line) for line in Path(runtime_path).read_text().splitlines() if line.startswith('{')][0]
pg = project + '-postgres-1'
image = 'python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710'


def sql(text):
    p = subprocess.run(['docker', 'exec', '-i', pg, 'psql', '-U', 'enginia360', '-d', 'enginia360', '-Atq',
                        '-v', 'ON_ERROR_STOP=1'], input=text, text=True, capture_output=True, timeout=20)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def probes(items):
    p = subprocess.run(['docker', 'run', '--rm', '-i', '--network', project + '_backend',
                        '-v', str(Path.cwd()) + ':/source:ro', '-w', '/source', image,
                        'python3', 'scripts/test-b13-recovery.py', 'http://web:8080', 'x', 'client'],
                       input=json.dumps({'kind': 'probe', 'requests': items}), text=True, capture_output=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


entry_id, invoice_id, draft_invoice = runtime['entryId'], runtime['invoiceId'], runtime['draftInvoiceId']
post = {'id': str(uuid.uuid4()), 'invoiceId': draft_invoice, 'chartVersion': 1}
# Confirm the second invoice first: an unconfirmed invoice is refused before authorization is even reached.
probes([{'target': 'billing', 'path': '/' + draft_invoice + '/confirmation', 'method': 'POST',
         'body': {'id': str(uuid.uuid4()), 'configurationVersion': 1}, 'expected': 201, 'label': 'confirm second invoice'}])


def requests(read=404, write=403):
    return [{'path': '/' + entry_id, 'expected': read, 'label': 'exact read scope'},
            {'method': 'POST', 'body': post, 'expected': write, 'label': 'exact post scope'}]


sql("CREATE TABLE public.b13_permissions_backup AS SELECT * FROM organization_access.company_permissions WHERE \"Permission\" LIKE 'accounting.%';")
try:
    for clause in ["\"Permission\"='not.accounting'", "\"SiteId\"='11111111-1111-1111-1111-111111110201'",
                   "\"WarehouseId\"='11111111-1111-1111-1111-111111110111'",
                   "\"LegalEntityId\"='11111111-1111-1111-1111-111111111102'"]:
        sql('DELETE FROM organization_access.company_permissions WHERE "Permission" LIKE \'accounting.%\' OR "Permission"=\'not.accounting\'; INSERT INTO organization_access.company_permissions SELECT * FROM public.b13_permissions_backup; UPDATE organization_access.company_permissions SET ' + clause + ' WHERE "Permission" LIKE \'accounting.%\';')
        probes(requests())
    sql('DELETE FROM organization_access.company_permissions WHERE "Permission" LIKE \'accounting.%\'; INSERT INTO organization_access.company_permissions SELECT * FROM public.b13_permissions_backup;')
    sql('UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "Capability"=\'internal-accounting\';')
    probes(requests(read=200))
finally:
    sql('DELETE FROM organization_access.company_permissions WHERE "Permission" LIKE \'accounting.%\' OR "Permission"=\'not.accounting\'; INSERT INTO organization_access.company_permissions SELECT * FROM public.b13_permissions_backup; DROP TABLE public.b13_permissions_backup; UPDATE organization_access.capability_activations SET "Enabled"=true WHERE "Capability"=\'internal-accounting\';')
print('PASS B13 exact action, wrong-site, warehouse-only and foreign-company scopes separately; disabled capability blocks posting and keeps authorized history readable')

# Real intermodule fault: Accounting commits, the Billing link insert is refused by privilege.
sql('REVOKE INSERT ON billing.invoice_journal_links FROM enginia360_app;')
try:
    pending = probes([{'method': 'POST', 'body': post, 'expected': 201, 'label': 'journal entry posted before link'}])[0]
    assert pending['invoiceLinkState'] == 'Pending', pending
    assert pending['balanced'] and pending['totalDebit'] == pending['totalCredit']
    assert sql('SELECT count(*) FROM accounting.journal_entries WHERE "Id"=\'' + post['id'] + '\';') == '1'
    assert sql('SELECT count(*) FROM billing.invoice_journal_links WHERE "InvoiceId"=\'' + draft_invoice + '\';') == '0'
    still = probes([{'target': 'billing', 'path': '/' + draft_invoice, 'expected': 200, 'label': 'confirmed invoice preserved'}])[0]
    assert still['status'] == 'Confirmed' and still['journalEntryId'] is None, still
finally:
    sql('GRANT INSERT ON billing.invoice_journal_links TO enginia360_app;')
recovered = probes([{'method': 'POST', 'body': post, 'expected': 200, 'label': 'exact retry completes link'},
                    {'path': '/' + post['id'], 'expected': 200},
                    {'target': 'billing', 'path': '/' + draft_invoice, 'expected': 200}])
assert recovered[0]['invoiceLinkState'] == 'Linked' and recovered[1] == recovered[0], recovered[:2]
assert recovered[2]['journalEntryId'] == post['id'], recovered[2]
assert sql('SELECT count(*) FROM accounting.journal_entries WHERE "InvoiceId"=\'' + draft_invoice + '\';') == '1'
assert sql('SELECT count(*) FROM accounting.journal_entry_lines WHERE "EntryId"=\'' + post['id'] + '\';') == '4'
print('PASS B13 intermodule link failure after the local commit stays visible and recoverable by exact retry, without double posting or deleting the confirmed invoice')

# Leave only the original tracer evidence for the aggregate count assertions.
sql('DELETE FROM billing.invoice_journal_links WHERE "InvoiceId"=\'' + draft_invoice + '\'; DELETE FROM accounting.journal_entry_lines WHERE "EntryId"=\'' + post['id'] + '\'; DELETE FROM accounting.journal_entries WHERE "Id"=\'' + post['id'] + '\';')
