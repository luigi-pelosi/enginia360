#!/usr/bin/env python3
"""Bounded actual UI01.b Chromium/OIDC/API/PostgreSQL on guarded ephemeral R00 TLS primitives."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
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
r00.CONFIG = ROOT/'compose.ui01b-test.yaml'
run = r00.run

def fixtures(state, secret):
    sql, identities = r00.fixtures(state, secret)
    browser = json.loads((state/'browser.json').read_text())
    browser['workshop'] = []
    statements = [sql]
    for index, context in enumerate(browser['contexts']):
        tenant, company, site = [context[k] for k in ('tenantId','legalEntityId','siteId')]
        membership = browser['adminMembershipId'] if index == 0 else None
        # Own fixture IDs only; no application provisioning or foreign-module SQL.
        member = f'(SELECT "Id" FROM organization_access.memberships WHERE "IdentitySubject"=\'{identities[index]}\')'
        data = {k:str(uuid.uuid4()) for k in ('documentTypeId','payerId','holderId','vehicleId','serviceId','partId')}
        browser['workshop'].append(data)
        statements.append(f"INSERT INTO organization_access.capability_activations VALUES ('{company}','workshop',true);")
        for action in ('workshop.orders.read','workshop.orders.create','workshop.lines.add','workshop.groups.write','counterparties.read'):
            statements.append(f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}',{member},'{tenant}','{company}','{action}',NULL,NULL);")
        statements += [f"INSERT INTO counterparties.counterparties VALUES ('{data[k]}','{tenant}','Synthetic {k}','SYNTHETIC','Synthetic office');" for k in ('payerId','holderId')]
        registered_company = browser['deniedContexts'][0]['legalEntityId'] if index == 0 else company
        statements += [f"INSERT INTO vehicles.vehicles VALUES ('{data['vehicleId']}','{tenant}','{registered_company}','{data['holderId']}','Synthetic vehicle');",
                       f"INSERT INTO vehicles.vehicles VALUES ('{uuid.uuid4()}','{tenant}','{company}','{data['holderId']}','Other vehicle');",
                       f"INSERT INTO workshop.document_types VALUES ('{data['documentTypeId']}','{tenant}','{company}',7,'Synthetic document',true);",
                       f"INSERT INTO workshop.line_policies VALUES ('{tenant}','{company}','{data['documentTypeId']}',9,'Case001',true);"]
        for kind in ('Service','Part'):
            statements.append(f"INSERT INTO catalog.items VALUES ('{data[kind.lower()+'Id']}','{tenant}','{registered_company}','{kind}','Synthetic {kind}',8);")
        if index == 0:
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
    # R00 seals its completed fixture read-only. Extend it as its owner, then reseal before any mount.
    (state/'browser.json').chmod(0o600)
    (state/'browser.json').write_text(json.dumps(browser))
    (state/'browser.json').chmod(0o444)
    return '\n'.join(statements)

def main():
    if not os.environ.get('TMPDIR'): raise ValueError('private TMPDIR required')
    if not (ROOT/'web/dist-ui01-runtime/ui01-runtime.html').exists(): raise ValueError('build:ui01-runtime required')
    project = 'enginia360-r00b-' + secrets.token_hex(6)
    before_volumes = r00.inventory('volume')
    before_running = set(run(['docker','ps','-q','--no-trunc']).splitlines())
    evidence = Path(os.environ['TMPDIR'])/'ui01b-evidence'
    evidence.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=project+'-',dir=os.environ['TMPDIR']) as directory:
        state = Path(directory)
        values = {key:secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD','R00_OWNER_PASSWORD','R00_APP_PASSWORD','R00_CLIENT_SECRET')}
        values.update(R00_STATE=str(state),R00_POOL_SIZE='4')
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
            print('UI01B pinned build',flush=True); run(command+['build'],timeout=480)
            run(command+['up','-d','--wait','--wait-timeout','180','postgres','identity'],timeout=210)
            run(command+['run','--rm','--no-deps','-T','migrator'],timeout=90)
            query=command+['exec','-T','postgres','psql','-X','-qAt','-U','postgres','-d','runtime','-v','ON_ERROR_STOP=1']
            assert run(query+['-c','SELECT count(*) FROM runtime_migrations.applied']).strip()=='19'
            assert run(query+['-c','SELECT count(*) FROM workshop.orders']).strip()=='0'
            run(query,input=sql)
            run(command+['up','-d','api','web'],timeout=120)
            ids=run(command+['ps','-q']).splitlines()
            for c in json.loads(run(['docker','inspect',*ids])):
                h=c['HostConfig']; assert c['Config']['User'] not in ('','0','root') and h['ReadonlyRootfs']; assert h['CapDrop']==['ALL'] and 'no-new-privileges:true' in h['SecurityOpt']; assert not h['PortBindings'] and not any(m['Type']=='volume' for m in c['Mounts']); assert h['Memory']>0 and h['NanoCpus']>0 and h['PidsLimit']>0
            assert json.loads(run(['docker','network','inspect',project+'_runtime']))[0]['Internal']
            authority_version=0
            process = subprocess.Popen(command+['run','--rm','--no-deps','-T','browser'],cwd=ROOT)
            deadline = time.monotonic()+240
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline: raise TimeoutError('editor browser deadline')
                    request = state/'control/request'
                    if request.exists():
                        action = request.read_text(); request.unlink()
                        if action == 'database-outage': run(command+['pause','postgres'],timeout=30)
                        elif action == 'database-recover': run(command+['unpause','postgres'],timeout=30)
                        elif action in ('authority-local','authority-external'):
                            # Synthetic setup deliberately invokes the real bounded owner tool over verified TLS.
                            fixture=json.loads((state/'browser.json').read_text())
                            setup=dict(commandId=str(uuid.uuid4()),tenantId=fixture['contexts'][0]['tenantId'],actorMembershipId=fixture['adminMembershipId'],verificationReference=str(uuid.uuid4()),expectedVersion=authority_version,domain='counterparties',direction='Enginia360ToExternal' if action=='authority-local' else 'ExternalToEnginia360',sourceId=str(uuid.uuid4()),profileId=str(uuid.uuid4()),companyIds=[fixture['contexts'][0]['legalEntityId']])
                            if (state/'public/authority.json').exists(): (state/'public/authority.json').chmod(0o600)
                            (state/'public/authority.json').write_text(json.dumps(setup)); (state/'public/authority.json').chmod(0o444)
                            run(command+['run','--rm','--no-deps','-T','--entrypoint','python3','migrator','scripts/owner-master-authority.py','/run/tls/authority.json'],timeout=40)
                            authority_version+=1
                        else: raise ValueError('unknown editor lifecycle command')
                        print('UI01B_LIFECYCLE '+action,flush=True)
                        (state/'control/ack').write_text(action)
                    time.sleep(0.1)
                if process.returncode: raise RuntimeError('editor Chromium acceptance failed')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)
            result=json.loads((state/'control/result.json').read_text())
            order,summary=result['order'],result['summary']
            fixture=json.loads((state/'browser.json').read_text())
            common=result['common']; assert common['id']==order['payerId'] and str(uuid.UUID(common['id']))==common['id']
            assert run(query+['-c',f'''SELECT "LegalName" FROM counterparties.counterparties WHERE "Id"='{common['id']}';''']).strip()==common['legalName']=='Synthetic edited payer'
            assert run(query+['-c',f'''SELECT "CounterpartyId"::text||'|'||"ActorMembershipId"::text||'|'||"AuthorityVersion"::text||'|'||"Revision"::text FROM counterparties.common_edit_history;''']).strip()==common['id']+'|'+fixture['adminMembershipId']+'|2|1'
            assert run(query+['-c','SELECT count(*) FROM counterparties.common_edit_history']).strip()=='1'
            assert run(query+['-c','SELECT count(*) FROM organization_access.master_authority_history']).strip()=='2'
            assert run(query+['-c',f'''SELECT "SourceId"::text||'|'||"ProfileId"::text||'|'||"Direction" FROM organization_access.master_authority_history WHERE "Version"=2;''']).strip()==result['authority']['sourceId']+'|'+result['authority']['profileId']+'|Enginia360ToExternal'
            print('PASS R02B SQL explicit source/profile authority versions=2; immutable edit history=1, exact actor/revision; uncertain replay made no duplicate',flush=True)
            assert run(query+['-c','SELECT count(*) FROM workshop.orders']).strip()=='1'
            assert run(query+['-c','SELECT count(*) FROM workshop.commercial_lines']).strip()=='2'
            expected=[]
            for l in summary['lines']:
                net=(Decimal(l['quantity'])*Decimal(l['unitPrice'])*(1-Decimal(l['discountPercent'])/100)).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)
                assert str(net)==l['netAmount']; expected.append(net)
                saved=run(query+['-c',f'''SELECT "NetAmount"::text||'|'||"Quantity"::text||'|'||"UnitPrice"::text||'|'||"DiscountPercent"::text FROM workshop.commercial_lines WHERE "Id"='{l['id']}';''']).strip().split('|')
                assert Decimal(saved[0])==net and Decimal(saved[1])==Decimal(l['quantity']) and Decimal(saved[2])==Decimal(l['unitPrice']) and Decimal(saved[3])==Decimal(l['discountPercent'])
            net=sum(expected); tax=(net*Decimal('.22')).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)
            assert Decimal(summary['netAmount'])==net and Decimal(summary['taxAmount'])==tax and Decimal(summary['total'])==net+tax
            assert run(query+['-c',f'''SELECT "PayerId"::text||'|'||"VehicleHolderId"::text FROM workshop.orders WHERE "Id"='{order['id']}';''']).strip()==order['payerId']+'|'+order['vehicleHolderId']
            for screenshot in (state/'control').glob('*.png'): shutil.copyfile(screenshot,evidence/screenshot.name)
            (evidence/'result.json').write_text(json.dumps(result,indent=2))
            print('PASS UI01B SQL exact orders=1 lines=2; q6 D67 snapshots/tax/payer-holder readback',flush=True)
        finally:
            for sig in previous: signal.signal(sig,signal.SIG_IGN)
            try: r00.cleanup(command,project)
            finally:
                for sig,handler in previous.items(): signal.signal(sig,handler)
    assert r00.inventory('volume')==before_volumes
    assert set(run(['docker','ps','-q','--no-trunc']).splitlines())==before_running
    print('PASS UI01B protected running containers and retained volumes unchanged; no ephemeral resources leaked',flush=True)
if __name__=='__main__': main()
