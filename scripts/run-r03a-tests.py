#!/usr/bin/env python3
"""Bounded actual R03.a Chromium/OIDC/API/PostgreSQL on guarded ephemeral R00 TLS primitives."""
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
r00.CONFIG = ROOT/'compose.r03a-test.yaml'
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
        data = {k:str(uuid.uuid4()) for k in ('documentTypeId','documentTypeNoPolicyId','payerId','holderId','vehicleId','serviceId','partId')}
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
        for kind in ('Service','Part'):
            statements.append(f"INSERT INTO catalog.items VALUES ('{data[kind.lower()+'Id']}','{tenant}','{registered_company}','{kind}','Synthetic {kind}',8);")
        if index == 0:
            warehouse=context['warehouseId']
            statements += [f"INSERT INTO organization_access.capability_activations VALUES ('{company}','inventory',true);",
                           f"INSERT INTO inventory.stock VALUES ('{tenant}','{company}','{site}','{warehouse}','{data['partId']}',50);",
                           f"INSERT INTO inventory.picking_policies VALUES ('{tenant}','{company}',1,true);",
                           f"INSERT INTO inventory.picking_locations VALUES ('{tenant}','{company}','{site}','{warehouse}','Stock A','Preparazione A');"]
            for action in ('inventory.reservations.create','inventory.picks.create'):
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
    evidence = Path(os.environ['TMPDIR'])/'r03a-evidence'
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
            print('R03A pinned build',flush=True); run(command+['build'],timeout=480)
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
                        elif action.startswith('hold-order-lock:'):
                            order_id=str(uuid.UUID(action.split(':',1)[1]))
                            holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
                            holder.stdin.write(f"SELECT pg_advisory_lock(hashtextextended('{order_id}',0));\n\\echo LOCKED\nSELECT pg_sleep(3);\n"); holder.stdin.flush(); holder.stdin.close()
                            while 'LOCKED' not in holder.stdout.readline(): pass
                            holders.append(holder)
                        elif action.startswith('permissions:'):
                            _, name, grants = action.split(':',2)
                            target=fixture['grantTargetMembershipId']; ctx0=fixture['contexts'][0]
                            run(query+['-c',f"""DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{target}' AND "Permission" LIKE 'workshop.%' AND "Permission"<>'workshop.orders.read';"""+''.join(f"""INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{ctx0['tenantId']}','{ctx0['legalEntityId']}','{g}',NULL,NULL);""" for g in grants.split(',') if g!='workshop.orders.read')])
                        else: raise ValueError('unknown R03.a lifecycle command')
                        print('R03A_LIFECYCLE '+action,flush=True)
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
            def sql(statement): return run(query+['-c',statement]).strip()
            order=result['order']
            revision=result['final']['revision']
            assert sql(f"""SELECT "CommercialRevision" FROM workshop.orders WHERE "Id"='{order}'""")==str(revision)
            assert sql(f"""SELECT count(*) FROM workshop.editor_commands WHERE "OrderId"='{order}'""")==str(revision),'one immutable receipt per applied revision'
            assert sql(f"""SELECT count(*)-count(DISTINCT "AppliedRevision") FROM workshop.editor_commands WHERE "OrderId"='{order}'""")=='0'
            assert sql(f"""SELECT count(*) FROM (SELECT "TargetKind","TargetId",count(*) c,max("Version") m FROM workshop.workspace_history WHERE "OrderId"='{order}' GROUP BY 1,2) x WHERE c<>m""")=='0','contiguous append-only versions'
            lines=result['lines']
            assert sql(f"""SELECT "State"||'|'||"Version" FROM workshop.commercial_lines WHERE "Id"='{lines['s2']}'""")=='Removed|2','Service tombstone kept, row not deleted'
            assert sql(f"""SELECT "State" FROM workshop.commercial_lines WHERE "Id"='{lines['p2']}'""")=='Active','Part removal was refused'
            assert sql(f"""SELECT count(*) FROM workshop.order_notes WHERE "Id"='{result['note']}' AND "State"='Removed' AND "Version"=3""")=='1'
            assert sql(f"""SELECT count(*) FROM workshop.working_groups WHERE "OrderId"='{order}' AND "State"='Removed'""")=='1'
            assert sql(f"""SELECT count(*) FROM workshop.commercial_lines WHERE "OrderId"='{order}' AND "WorkingGroupId"="OrderId" """)=='0','no row is attached to the legacy group'
            assert sql(f"""SELECT count(*) FROM workshop.commercial_lines WHERE "OrderId"='{order}' AND "CatalogItemId"=(SELECT "CatalogItemId" FROM workshop.commercial_lines WHERE "Id"='{lines['p1']}') AND "Kind"='Part'""")=='2','same Part catalog item twice with distinct ids'
            assert sql(f"""SELECT count(*) FROM workshop.editor_commands WHERE "CommandId"='{result['firstCommand']}'""")=='1'
            assert sql(f"""SELECT count(*) FROM workshop.editor_commands WHERE "CommandId"='{result['lost']}'""")=='1' and sql(f"""SELECT count(*) FROM workshop.workspace_history WHERE "CommandId"='{result['lost']}'""")=='1','lost response replay wrote exactly one fact'
            concurrent=result['concurrent']['order']
            assert sql(f"""SELECT "CommercialRevision"||'|'||(SELECT count(*) FROM workshop.editor_commands WHERE "OrderId"='{concurrent}') FROM workshop.orders WHERE "Id"='{concurrent}'""")=='5|5'
            q6=result['q6']
            assert sql(f"""SELECT count(*) FROM workshop.commercial_lines WHERE "OrderId"='{q6}'""")=='6' and sql(f"""SELECT "CommercialRevision" FROM workshop.orders WHERE "Id"='{q6}'""")=='8','rejected overflow consumed no revision and wrote no row'
            for row in run(query+['-A','-F','|','-c','SELECT "NetAmount","Quantity","UnitPrice","DiscountPercent" FROM workshop.commercial_lines']).strip().splitlines():
                net,quantity,price,discount=[Decimal(x) for x in row.split('|')]
                assert net==(quantity*price*(1-discount/100)).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP),'saved net differs from independent D67 oracle'
            closure=result['closure']
            assert sql(f"""SELECT "Revision" FROM workshop.technical_closures WHERE "OrderId"='{closure['order']}'""")==str(closure['revision']),'closure fixes the persisted revision'
            prov=result['prov']
            assert sql(f"""SELECT \"WorkingGroupId\" FROM inventory.reservations WHERE \"Id\"='{prov['rX']}'""")==prov['gX'] and sql(f"""SELECT \"WorkingGroupId\" FROM inventory.reservations WHERE \"Id\"='{prov['rY']}'""")==prov['gY']
            assert sql(f"""SELECT count(*) FROM inventory.picks WHERE \"ReservationId\" IN ('{prov['rX']}','{prov['rY']}') AND \"WorkingGroupId\"<>\"OrderId\" AND \"OrderId\"='{prov['order']}'""")=='2'
            ui=result['ui']
            assert sql(f"""SELECT \"CommercialRevision\" FROM workshop.orders WHERE \"Id\"='{ui['order']}'""")=='107' and sql(f"""SELECT count(*) FROM workshop.commercial_lines WHERE \"OrderId\"='{ui['order']}' AND \"State\"='Active'""")=='100'
            assert sql(f"""SELECT \"UnitPrice\" FROM workshop.commercial_lines WHERE \"Id\"='{ui['last']}'""")=='199.500000' and sql(f"""SELECT count(*) FROM workshop.workspace_history WHERE \"TargetId\"='{ui['last']}'""")=='2'
            assert sql("SELECT count(*) FROM workshop.line_policies")=='3','three synthetic contexts, one explicit policy each; migration seeded none'
            for screenshot in (state/'control').glob('*.png'): shutil.copyfile(screenshot,evidence/screenshot.name)
            (evidence/'result.json').write_text(json.dumps(result,indent=2))
            print('PASS R03A SQL receipts/history/tombstones/q6/revision/closure readback',flush=True)
        finally:
            for sig in previous: signal.signal(sig,signal.SIG_IGN)
            try: r00.cleanup(command,project)
            finally:
                for sig,handler in previous.items(): signal.signal(sig,handler)
    assert r00.inventory('volume')==before_volumes
    assert set(run(['docker','ps','-q','--no-trunc']).splitlines())==before_running
    print('PASS R03A protected running containers and retained volumes unchanged; no ephemeral resources leaked',flush=True)
if __name__=='__main__': main()
