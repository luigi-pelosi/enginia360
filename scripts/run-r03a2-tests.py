#!/usr/bin/env python3
"""Bounded actual R03.a Chromium/OIDC/API/PostgreSQL on guarded ephemeral R00 TLS primitives."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import select
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from decimal import Decimal, ROUND_HALF_UP

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r00_helpers', ROOT/'scripts/run-r00b-tests.py')
r00 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r00)
r00.CONFIG = ROOT/'compose.r03a2-test.yaml'
run = r00.run

def marker(process, expected):
    """Bounded raw-fd readiness; never wait on an unbounded TextIO readline."""
    deadline = time.monotonic() + 5
    pending = b''
    while process.poll() is None and time.monotonic() < deadline:
        if select.select([process.stdout], [], [], 0.1)[0]:
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                break
            pending += chunk
            if expected in pending:
                return pending.decode()
    raise TimeoutError('SQL barrier readiness not observed')


def fixtures(state, secret, stock_setup=True):
    sql, identities = r00.fixtures(state, secret)
    browser = json.loads((state/'browser.json').read_text())
    browser['workshop'] = []
    browser['poolSize'] = int(os.environ.get('R03A2_POOL_SIZE','4'))
    statements = [sql]
    for index, context in enumerate(browser['contexts']):
        tenant, company, site = [context[k] for k in ('tenantId','legalEntityId','siteId')]
        membership = browser['adminMembershipId'] if index == 0 else None
        # Own fixture IDs only; no application provisioning or foreign-module SQL.
        member = f'(SELECT "Id" FROM organization_access.memberships WHERE "IdentitySubject"=\'{identities[index]}\')'
        data = {k:str(uuid.uuid4()) for k in ('documentTypeId','documentTypeNoPolicyId','payerId','holderId','vehicleId','serviceId','partId','alternatePartId','invoiceTypeId')}
        browser['workshop'].append(data)
        statements.append(f"INSERT INTO organization_access.capability_activations VALUES ('{company}','workshop',true);")
        for action in ('workshop.orders.read','workshop.orders.create','workshop.lines.add','workshop.lines.edit','workshop.lines.remove','workshop.notes.write','workshop.groups.write','workshop.orders.complete-technical','counterparties.read'):
            statements.append(f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}',{member},'{tenant}','{company}','{action}',NULL,NULL);")
        statements += [f"INSERT INTO counterparties.counterparties VALUES ('{data[k]}','{tenant}','Synthetic {k}','SYNTHETIC','Synthetic office');" for k in ('payerId','holderId')]
        registered_company = browser['deniedContexts'][0]['legalEntityId'] if index == 0 else company
        statements += [f"INSERT INTO vehicles.vehicles VALUES ('{data['vehicleId']}','{tenant}','{registered_company}','{data['holderId']}','Synthetic vehicle');",
                       f"INSERT INTO vehicles.vehicles VALUES ('{uuid.uuid4()}','{tenant}','{company}','{data['holderId']}','Other vehicle');",
                       f"INSERT INTO workshop.document_types VALUES ('{data['documentTypeId']}','{tenant}','{company}',7,'Synthetic document',true);",
                       f"INSERT INTO workshop.line_policies VALUES ('{tenant}','{company}','{data['documentTypeId']}',9,'Case001',true,true);",
                       f"INSERT INTO workshop.document_types VALUES ('{data['documentTypeNoPolicyId']}','{tenant}','{company}',3,'Synthetic without line policy',true);"]
        statements.append(f"INSERT INTO catalog.items VALUES ('{data['alternatePartId']}','{tenant}','{registered_company}','Part','Synthetic alternate Part',11);")
        for kind in ('Service','Part'):
            statements.append(f"INSERT INTO catalog.items VALUES ('{data[kind.lower()+'Id']}','{tenant}','{registered_company}','{kind}','Synthetic {kind}',8);")
        for capability in ('internal-billing','internal-accounting','external-administration'):
            statements.append(f"INSERT INTO organization_access.capability_activations VALUES ('{company}','{capability}',true);")
        for action in ('workshop.installations.create','workshop.installations.read','billing.invoices.create','billing.invoices.read','billing.invoices.confirm','accounting.journal-entries.post','accounting.journal-entries.read','workshop.administrative-requests.create','workshop.administrative-requests.read'):
            statements.append(f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}',{member},'{tenant}','{company}','{action}',NULL,NULL);")
        destination='Internal' if index==0 else 'External'
        statements.append(f"INSERT INTO workshop.administrative_destinations VALUES ('{tenant}','{company}',13,'{destination}');")
        if index == 0:
            statements += [f"INSERT INTO billing.document_types VALUES ('{tenant}','{company}','{data['invoiceTypeId']}',6,'SYNTHETIC',true,true);",
                           f"INSERT INTO billing.issuer_profiles VALUES ('{tenant}','{company}',6,'Synthetic issuer','SYNTHETIC','Synthetic address');",
                           f"INSERT INTO workshop.carcass_policies VALUES ('{tenant}','{company}','{data['documentTypeId']}','{data['partId']}',3,true);",
                           f"INSERT INTO inventory.carcass_locations VALUES ('{tenant}','{company}','{site}','{context['warehouseId']}',4,'Dedicated carcass');"]
            for n,purpose in enumerate(('Receivable','ServiceRevenue','PartRevenue','TaxPayable')):
                statements.append(f"INSERT INTO accounting.chart_accounts VALUES ('{tenant}','{company}',5,'{purpose}','{1100+n}','Synthetic {purpose}');")
            warehouse=context['warehouseId']
            statements += [f"INSERT INTO organization_access.capability_activations VALUES ('{company}','inventory',true);",
                           f"INSERT INTO inventory.stock VALUES ('{tenant}','{company}','{site}','{warehouse}','{data['partId']}',50);",
                           f"INSERT INTO inventory.picking_policies VALUES ('{tenant}','{company}',1,true);",
                           f"INSERT INTO inventory.picking_locations VALUES ('{tenant}','{company}','{site}','{warehouse}','Stock A','Preparazione A');"]
            for action in ('inventory.reservations.create','inventory.picks.create','inventory.picks.read','inventory.consumptions.create','inventory.consumptions.read','inventory.carcass-returns.create','inventory.carcass-returns.read'):
                statements.append(f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}',{member},'{tenant}','{company}','{action}','{site}','{warehouse}');")
            statements.append(f"INSERT INTO organization_access.common_edit_permissions VALUES ('{browser['adminMembershipId']}','{tenant}');")
            browser['privateDestinationId'], browser['publishedDestinationId'] = str(uuid.uuid4()), str(uuid.uuid4())
            for key, published in (('privateDestinationId', 'false'), ('publishedDestinationId', 'true')):
                statements.append(f"INSERT INTO counterparties.destinations VALUES ('{browser[key]}','{tenant}','{data['payerId']}','{registered_company}','Synthetic destination',{published});")
            statements.append(f"INSERT INTO organization_access.memberships VALUES ('{uuid.uuid4()}','{tenant}','{identities[4]}');")
            for n in range(51):
                statements += [f"INSERT INTO counterparties.counterparties VALUES ('{uuid.uuid4()}','{tenant}','Page {n:02d}','SYNTHETIC','Synthetic office');",
                               f"INSERT INTO vehicles.vehicles VALUES ('{uuid.uuid4()}','{tenant}','{registered_company}','{data['holderId']}','Page {n:02d}');",
                               f"INSERT INTO catalog.items VALUES ('{uuid.uuid4()}','{tenant}','{registered_company}','Service','Page {n:02d}',8);"]
            for action in ('workshop.orders.read','counterparties.read'):
                statements.append(f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{browser['grantTargetMembershipId']}','{tenant}','{company}','{action}',NULL,NULL);")
    # Explicit synthetic owner-verified company STOCK setup; unrelated to master authority.
    if stock_setup:
        context=browser['contexts'][0]
        statements.append(f"SET ROLE runtime_owner; BEGIN; SELECT set_config('app.tenant_id','{context['tenantId']}',true); SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{context['tenantId']}','{context['legalEntityId']}','{browser['adminMembershipId']}','{uuid.uuid4()}','Enginia360ToExternal','{uuid.uuid4()}','{uuid.uuid4()}'); COMMIT; RESET ROLE;")
    # R00 seals its completed fixture read-only. Extend it as its owner, then reseal before any mount.
    (state/'browser.json').chmod(0o600)
    (state/'browser.json').write_text(json.dumps(browser))
    (state/'browser.json').chmod(0o444)
    return '\n'.join(statements)

def main():
    if not os.environ.get('TMPDIR'): raise ValueError('private TMPDIR required')
    if os.environ.get('R03A2_POOL_SIZE','4') not in ('1','4'): raise ValueError('pool acceptance is explicitly 1 or 4')
    if not (ROOT/'web/dist-ui01-runtime/ui01-runtime.html').exists(): raise ValueError('build:ui01-runtime required')
    project = 'enginia360-r00b-' + secrets.token_hex(6)
    before_volumes = r00.inventory('volume')
    before_running = set(run(['docker','ps','-q','--no-trunc']).splitlines())
    evidence = Path(os.environ['TMPDIR'])/('r03a2-evidence-pool'+os.environ.get('R03A2_POOL_SIZE','4'))
    evidence.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=project+'-',dir=os.environ['TMPDIR']) as directory:
        state = Path(directory)
        values = {key:secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD','R00_OWNER_PASSWORD','R00_APP_PASSWORD','R00_CLIENT_SECRET')}
        values.update(R00_STATE=str(state),R00_POOL_SIZE=os.environ.get('R03A2_POOL_SIZE','4'))
        envfile = state/'runtime.env'; envfile.write_text(''.join(k+'='+v+'\n' for k,v in values.items())); envfile.chmod(0o600)
        run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=Ephemeral UI01b CA','-addext','basicConstraints=critical,CA:TRUE','-keyout',str(state/'ca.key'),'-out',str(state/'ca.crt')])
        (state/'ca.key').chmod(0o600)
        (state/'public').mkdir(); (state/'public/ca.crt').write_bytes((state/'ca.crt').read_bytes())
        for service,host,uid in [('postgres','postgres',70),('api','api.r00.test',1654),('web','app.r00.test',101),('identity','idp.r00.test',1000)]: r00.certificate(state,service,host,uid)
        (state/'postgres/pg_hba.conf').write_text('local all all trust\nhostnossl all all all reject\nhostssl all all all scram-sha-256\n')
        sql = fixtures(state,values['R00_CLIENT_SECRET'])
        (state/'control').mkdir(); (state/'control').chmod(0o777)
        command=['docker','compose','--env-file',str(envfile),'-p',project,'-f',str(r00.CONFIG)]
        def interrupted(signum,frame): raise KeyboardInterrupt
        previous={sig:signal.signal(sig,interrupted) for sig in (signal.SIGINT,signal.SIGTERM)}
        try:
            print('R03A pinned build',flush=True); run(command+['build'],timeout=480)
            run(command+['up','-d','--wait','--wait-timeout','180','postgres','identity'],timeout=210)
            run(command+['run','--rm','--no-deps','-T','migrator'],timeout=90)
            query=command+['exec','-T','postgres','psql','-X','-qAt','-U','postgres','-d','runtime','-v','ON_ERROR_STOP=1']
            assert run(query+['-c','SELECT count(*) FROM runtime_migrations.applied']).strip()=='22'
            assert run(query+['-c','SELECT count(*) FROM workshop.orders']).strip()=='0'
            run(query,input=sql)
            run(command+['up','-d','api','web'],timeout=120)
            ids=run(command+['ps','-q']).splitlines()
            for c in json.loads(run(['docker','inspect',*ids])):
                h=c['HostConfig']; assert c['Config']['User'] not in ('','0','root') and h['ReadonlyRootfs']; assert h['CapDrop']==['ALL'] and 'no-new-privileges:true' in h['SecurityOpt']; assert not h['PortBindings'] and not any(m['Type']=='volume' for m in c['Mounts']); assert h['Memory']>0 and h['NanoCpus']>0 and h['PidsLimit']>0
            assert json.loads(run(['docker','network','inspect',project+'_runtime']))[0]['Internal']
            holders=[]
            process = subprocess.Popen(command+['run','--rm','--no-deps','-T','browser'],cwd=ROOT)
            deadline = time.monotonic()+240
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline: raise TimeoutError('editor browser deadline')
                    request = state/'control/request'
                    if request.exists():
                        action = request.read_text(); request.unlink()
                        fixture=json.loads((state/'browser.json').read_text())
                        if action == 'database-outage': run(command+['pause','postgres'],timeout=30)
                        elif action == 'database-recover': run(command+['unpause','postgres'],timeout=30)
                        elif action.startswith('hold-line:'):
                            tenant, line = [str(uuid.UUID(x)) for x in action.split(':')[1:]]
                            holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
                            holders.append(holder)
                            holder.stdin.write(f"SET statement_timeout='5s'; SELECT pg_advisory_lock(hashtextextended('inventory:line:{tenant}:{line}',0));\nSELECT pg_backend_pid();\n\\echo LOCKED\n"); holder.stdin.flush()
                            output=marker(holder,b'LOCKED').splitlines()
                            holder_pid=int([x for x in output if x.isdigit()][-1])
                        elif action.startswith('wait-line:'):
                            required=int(action.split(':')[1]); stop=time.monotonic()+10
                            while True:
                                count=int(run(query+['-c',f"SELECT count(DISTINCT w.pid) FROM pg_locks w JOIN pg_locks h ON (w.database,w.classid,w.objid,w.objsubid)=(h.database,h.classid,h.objid,h.objsubid) WHERE w.locktype='advisory' AND NOT w.granted AND h.granted AND h.pid={holder_pid}"]).strip())
                                if count>=required: break
                                if time.monotonic()>stop: raise TimeoutError('expected PostgreSQL advisory waiters absent')
                                time.sleep(0.02)
                            print(f'BARRIER observed {count} separate-connection advisory waiters',flush=True)
                        elif action == 'release-line':
                            holder.stdin.write('\\q\n'); holder.stdin.flush(); holder.stdin.close(); holder.wait(timeout=5)
                        elif action.startswith('hold-order-lock:'):
                            order_id=str(uuid.UUID(action.split(':',1)[1]))
                            holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
                            holders.append(holder)
                            holder.stdin.write(f"SET statement_timeout='5s'; SELECT pg_advisory_lock(hashtextextended('{order_id}',0));\n\\echo LOCKED\nSELECT pg_sleep(3);\n"); holder.stdin.flush(); holder.stdin.close()
                            marker(holder,b'LOCKED')
                        elif action.startswith('permissions:'):
                            _, name, grants = action.split(':',2)
                            target=fixture['grantTargetMembershipId']; ctx0=fixture['contexts'][0]
                            run(query+['-c',f"""DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{target}' AND "Permission" LIKE 'workshop.%' AND "Permission"<>'workshop.orders.read';"""+''.join(f"""INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{ctx0['tenantId']}','{ctx0['legalEntityId']}','{g}',NULL,NULL);""" for g in grants.split(',') if g!='workshop.orders.read')])
                        else: raise ValueError('unknown R03.a lifecycle command')
                        print('R03A_LIFECYCLE '+action,flush=True)
                        (state/'control/ack.tmp').write_text(action); (state/'control/ack.tmp').replace(state/'control/ack')
                    time.sleep(0.1)
                if process.returncode: raise RuntimeError('editor Chromium acceptance failed')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)
            result=json.loads((state/'control/result.json').read_text())
            def sql(statement): return run(query+['-c',statement]).strip()
            print('R03A2 runtime checks: '+str(len(result['checks'])),flush=True)
            def scalar(statement): return run(query+['-c',statement]).strip()
            # Exact projections, immutable receipts, append-only contiguous history and current source revision.
            assert scalar(f"SELECT \"State\"||'|'||\"Version\" FROM workshop.commercial_lines WHERE \"Id\"='{result['line']}'")=='Removed|4'
            assert scalar(f"SELECT \"State\"||'|'||\"Version\" FROM workshop.commercial_lines WHERE \"Id\"='{result['uiPart']}'")=='Removed|4'
            assert scalar('SELECT count(*) FROM (SELECT "TargetKind","TargetId",count(*) c,max("Version") m FROM workshop.workspace_history GROUP BY 1,2) h WHERE c<>m')=='0'
            assert scalar('SELECT count(*) FROM workshop.orders o WHERE o."CommercialRevision"<>(SELECT count(*) FROM workshop.editor_commands e WHERE e."OrderId"=o."Id")')=='0'
            assert scalar(f"SELECT count(*) FROM workshop.workspace_history WHERE \"CommandId\"='{result['lostCommand']}'")=='1'
            assert scalar(f"SELECT count(*) FROM workshop.editor_commands WHERE \"CommandId\"='{result['lostCommand']}'")=='1'
            for table,key in [('inventory.reservations','reservationId'),('inventory.picks','pickId'),('workshop.installations','installId'),('inventory.carcass_returns','carcassId')]:
                assert scalar(f"SELECT \"WorkingGroupId\"||'|'||\"Quantity\" FROM {table} WHERE \"Id\"='{result[key]}'")==result['rg']+'|2.000000'
                assert result['rg']!=result['race']
            for table,key in [('inventory.reservations','r2'),('inventory.picks','pk2'),('workshop.installations','in2'),('inventory.carcass_returns','ca2')]:
                assert scalar(f"SELECT \"WorkingGroupId\"||'|'||\"Quantity\" FROM {table} WHERE \"Id\"='{result[key]}'")==result['secondGroup']+'|1.000000'
            assert scalar(f"SELECT count(*) FROM inventory.consumptions WHERE \"InstallationId\"='{result['installId']}' AND \"Quantity\"=2")=='1'
            invoice=json.loads(scalar(f"SELECT to_jsonb(i) FROM billing.invoices i WHERE \"Id\"='{result['invoiceId']}'"))
            assert invoice['Summary']==result['snapshot'] and invoice['SourceRevision']==result['rev']
            assert scalar(f"SELECT \"Revision\" FROM workshop.technical_closures WHERE \"OrderId\"='{result['race']}'")==str(result['rev'])
            assert scalar(f"SELECT count(*) FROM accounting.journal_entries WHERE \"Id\"='{result['journalId']}' AND \"TotalDebit\"=\"TotalCredit\"")=='1'
            assert scalar(f"SELECT sum(\"Debit\")=sum(\"Credit\") FROM accounting.journal_entry_lines WHERE \"EntryId\"='{result['journalId']}'")=='t'
            external=json.loads(scalar(f"SELECT \"Summary\" FROM workshop.administrative_requests WHERE \"Id\"='{result['externalId']}'"))
            assert external==result['externalSummary']
            assert scalar(f"SELECT count(*) FROM workshop.workspace_history WHERE \"TargetId\"='{result['fl']}'")=='2','hidden command collision rolled back its history'
            tenant=json.loads((state/'browser.json').read_text())['contexts'][0]['tenantId']
            for function in ('inventory.line_has_commitments(uuid,uuid)','workshop.reservation_line(uuid,uuid,uuid)'):
                assert scalar(f"SELECT NOT prosecdef AND proconfig IS NOT NULL AND NOT EXISTS (SELECT 1 FROM aclexplode(proacl) a WHERE a.grantee=0) FROM pg_proc WHERE oid='{function}'::regprocedure")=='t'
                assert scalar(f"SELECT has_function_privilege('runtime_app','{function}','EXECUTE')")=='t'
            for table in ('workshop.commercial_lines','workshop.workspace_history','workshop.editor_commands','inventory.reservations','billing.invoices','accounting.journal_entries'):
                assert scalar(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='{table}'::regclass")=='t'
                assert scalar(f"SELECT has_table_privilege('runtime_app','{table}','DELETE') OR has_table_privilege('runtime_app','{table}','TRUNCATE')")=='f'
            for table in ('billing.invoices','billing.invoice_confirmations','accounting.journal_entries','accounting.journal_entry_lines'):
                assert scalar(f"SELECT has_table_privilege('runtime_app','{table}','UPDATE')")=='f'
            raw=f"SET ROLE runtime_app; SELECT set_config('app.tenant_id','{tenant}',false); UPDATE workshop.commercial_lines SET \"Quantity\"=9,\"Version\"=\"Version\"+1 WHERE \"Id\"='{result['ual']}';"
            refused=subprocess.run(query+['-c',raw],cwd=ROOT,capture_output=True,text=True,timeout=20)
            assert refused.returncode!=0 and 'active_material_commitments' in refused.stderr,'no raw app bypass of the active fence'
            assert scalar(f"SELECT \"Quantity\"||'|'||\"Version\" FROM workshop.commercial_lines WHERE \"Id\"='{result['ual']}'")=='4.000000|2'
            run(command+['run','--rm','--no-deps','-T','migrator'],timeout=90)
            entries=json.loads((ROOT/'database/runtime/manifest.json').read_text())
            applied=dict(row.split('|') for row in scalar("SELECT id||'|'||checksum FROM runtime_migrations.applied ORDER BY id").splitlines())
            assert applied=={e['id']:e['sha256'] for e in entries}
            print('PASS SQL public-function/RLS/minimal-grants/raw-fence/rollback/history/versions/sourceRevision/q6/provenance/internal+external snapshot/idempotent journal and migrations',flush=True)

            for screenshot in (state/'control').glob('*.png'): shutil.copyfile(screenshot,evidence/screenshot.name)
            (evidence/'result.json').write_text(json.dumps(result,indent=2))
            print('PASS R03A2 completed declared runtime and SQL assertions',flush=True)
        finally:
            for sig in previous: signal.signal(sig,signal.SIG_IGN)
            for holder in locals().get('holders',[]):
                if holder.poll() is None:
                    holder.terminate()
                    try: holder.wait(timeout=5)
                    except subprocess.TimeoutExpired: holder.kill(); holder.wait(timeout=5)
                for stream in (holder.stdin, holder.stdout, holder.stderr):
                    if stream is not None and not stream.closed: stream.close()
            try: r00.cleanup(command,project)
            finally:
                for sig,handler in previous.items(): signal.signal(sig,handler)
    assert r00.inventory('volume')==before_volumes
    assert set(run(['docker','ps','-q','--no-trunc']).splitlines())==before_running
    print('PASS R03A protected running containers and retained volumes unchanged; no ephemeral resources leaked',flush=True)
if __name__=='__main__': main()
