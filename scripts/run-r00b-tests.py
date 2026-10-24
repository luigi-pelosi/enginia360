#!/usr/bin/env python3
"""Only random, labelled, private and ephemeral R00.b targets; no supplied target."""
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
manifest_count = str(len(json.loads((ROOT/'database/runtime/manifest.json').read_text())))
CONFIG = ROOT / 'compose.r00b-test.yaml'
# Pinned helper used only to apply container-side ownership; hosted runners cannot chown directly.
OWNERSHIP_IMAGE = 'python:3.14.3-alpine3.23@sha256:faee120f7885a06fcc9677922331391fa690d911c020abb9e8025ff3d908e510'


def run(args, *, capture=True, timeout=180, input=None, env=None):
    result = subprocess.run(args, cwd=ROOT, env=env, input=input, text=True,
                            capture_output=capture, timeout=timeout)
    if result.returncode:
        # Print only diagnostic lines; credential-bearing arguments/input are never emitted.
        diagnostic = (result.stderr or '')[-4000:]
        diagnostic = re.sub(r'https?://[^\\s]+', '[redacted-url]', diagnostic)
        print(diagnostic, flush=True)
        raise RuntimeError('bounded subprocess failed (exit %d)' % result.returncode)
    return result.stdout if capture else ''


def inventory(kind):
    return set(run(['docker', kind, 'ls', '-q']).splitlines())


def cleanup(command, project):
    if not re.fullmatch(r'enginia360-r00b-[0-9a-f]{12}', project):
        raise ValueError('refusing non-ephemeral target')
    ids = run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project]).splitlines()
    if ids:
        containers = json.loads(run(['docker', 'inspect', *ids]))
        for container in containers:
            labels = container['Config']['Labels']
            if labels.get('com.docker.compose.project') != project or labels.get('com.docker.compose.project.config_files') != str(CONFIG):
                raise ValueError('cleanup label/config mismatch')
        for container in containers:
            if container['State']['Paused']:
                run(['docker','unpause',container['Id']],timeout=30)
        run(['docker', 'rm', '-f', *ids], timeout=60)
    run(command + ['down', '--volumes', '--remove-orphans'], timeout=60)
    for kind, args in [('container', ['ps', '-aq']), ('network', ['network', 'ls', '-q']), ('volume', ['volume', 'ls', '-q'])]:
        if run(['docker', *args, '--filter', 'label=com.docker.compose.project=' + project]).strip():
            raise RuntimeError('ephemeral ' + kind + ' leaked')


def own(state, relative, uid):
    run(['docker','run','--rm','--read-only','--cap-drop=ALL','--cap-add=CHOWN','--security-opt=no-new-privileges:true',
         '--network','none','--memory=64m','--pids-limit=16','--user','0:0',
         '-v',str(state)+'/'+relative+':/key',OWNERSHIP_IMAGE,
         'chown',str(uid)+':'+str(uid),'/key'],timeout=60)


def certificate(state, service, hostname, uid):
    directory = state / service
    directory.mkdir(mode=0o755)
    key = directory / (service + '.key')
    request = state / (service + '.csr')
    extensions = state / (service + '.ext')
    extensions.write_text('subjectAltName=DNS:' + hostname + '\nextendedKeyUsage=serverAuth\n')
    run(['openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=' + hostname,
         '-keyout', str(key), '-out', str(request)])
    run(['openssl', 'x509', '-req', '-in', str(request), '-CA', str(state/'ca.crt'), '-CAkey', str(state/'ca.key'),
         '-CAcreateserial', '-days', '1', '-sha256', '-extfile', str(extensions), '-out', str(directory/(service+'.crt'))])
    key.chmod(0o400)
    own(state, service+'/'+key.name, uid)
    (directory/'ca.crt').write_bytes((state/'ca.crt').read_bytes())


def fixtures(state, secret):
    users = []
    browser = {'users': [], 'contexts': [], 'deniedContexts':[], 'clientSecret':secret}
    sql = []
    internal_ids = []
    issuer = 'https://idp.r00.test:8443/realms/runtime'
    for index in range(6):
        internal, subject = str(uuid.uuid4()), str(uuid.uuid4())
        internal_ids.append(internal)
        user = {'id': subject, 'username': 'synthetic-' + secrets.token_hex(6), 'enabled': True,
                'firstName':'Synthetic', 'lastName':'Acceptance', 'email':secrets.token_hex(8)+'@example.invalid','emailVerified':True,
                'credentials': [{'type': 'password', 'value': secrets.token_hex(20), 'temporary': False}]}
        users.append(user)
        browser['users'].append({'username': user['username'], 'password': user['credentials'][0]['value']})
        if index != 3:
            sql.append(f"INSERT INTO organization_access.external_identity_bindings VALUES ('{internal}','{issuer}','{subject}');")
        if index > 2:
            continue
        tenant, company, site, warehouse, membership = [str(uuid.uuid4()) for _ in range(5)]
        browser['contexts'].append({'tenantId':tenant,'legalEntityId':company,'siteId':site,'warehouseId':warehouse})
        sql += [f"INSERT INTO organization_access.tenants VALUES ('{tenant}','Synthetic runtime tenant');",
                f"INSERT INTO organization_access.legal_entities VALUES ('{company}','{tenant}','Synthetic company');",
                f"INSERT INTO organization_access.sites VALUES ('{site}','{company}','{tenant}','Synthetic site');",
                f"INSERT INTO organization_access.warehouses VALUES ('{warehouse}','{site}','{company}','{tenant}','Synthetic warehouse');",
                f"INSERT INTO organization_access.memberships VALUES ('{membership}','{tenant}','{internal}');",
                f"INSERT INTO organization_access.capability_activations VALUES ('{company}','organization-context',true);"]
        for permission in ['read'] + ([] if index == 1 else ['write']):
            sql.append(f"INSERT INTO organization_access.membership_scopes VALUES ('{uuid.uuid4()}','{membership}','{tenant}','{company}','{site}','{warehouse}','organization-context.{permission}');")
        if index == 0:
            browser['adminMembershipId'] = membership
            for missing_scope in ('company','site','warehouse'):
                other_company = str(uuid.uuid4()) if missing_scope == 'company' else company
                other_site = str(uuid.uuid4()) if missing_scope in ('company','site') else site
                other_warehouse = str(uuid.uuid4())
                if other_company != company:
                    sql.append(f"INSERT INTO organization_access.legal_entities VALUES ('{other_company}','{tenant}','Synthetic ungranted company');")
                if other_site != site:
                    sql.append(f"INSERT INTO organization_access.sites VALUES ('{other_site}','{other_company}','{tenant}','Synthetic ungranted site');")
                sql.append(f"INSERT INTO organization_access.warehouses VALUES ('{other_warehouse}','{other_site}','{other_company}','{tenant}','Synthetic ungranted warehouse');")
                browser['deniedContexts'].append({'tenantId':tenant,'legalEntityId':other_company,'siteId':other_site,'warehouseId':other_warehouse})
    # Synthetic already-trusted target: no grant and no delegation authority.
    context = browser['contexts'][0]
    tenant,company,site,warehouse = [context[k] for k in ('tenantId','legalEntityId','siteId','warehouseId')]
    target = str(uuid.uuid4())
    browser['grantTargetMembershipId'] = target
    sql.append(f"INSERT INTO organization_access.memberships VALUES ('{target}','{tenant}','{internal_ids[5]}');")
    browser['mandates'] = []
    now=datetime.now(timezone.utc)
    owner_actor=str(uuid.uuid4())
    for action in ('read','write'):
        mandate = str(uuid.uuid4())
        browser['mandates'].append(mandate)
        payload={'operation':'create','ownerActorId':owner_actor,'mandateId':mandate,'tenantId':tenant,
                 'adminMembershipId':browser['adminMembershipId'],'legalEntityId':company,'siteId':site,'warehouseId':warehouse,
                 'action':'organization-context.'+action,'validFrom':(now-timedelta(minutes=1)).isoformat(),'validUntil':(now+timedelta(hours=1)).isoformat()}
        path=state/('mandate-'+mandate+'.json')
        path.write_text(json.dumps(payload))
        path.chmod(0o444)
    realm = {'realm':'runtime','enabled':True,'sslRequired':'all','registrationAllowed':False,
             'clients':[{'clientId':'runtime-browser','secret':secret,'publicClient':False,
                         'standardFlowEnabled':True,'directAccessGrantsEnabled':False,'implicitFlowEnabled':False,
                         'serviceAccountsEnabled':False,'fullScopeAllowed':False,'defaultClientScopes':[],
                         'redirectUris':['https://app.r00.test:8443/signin-oidc'],
                         'webOrigins':[], 'attributes':{'pkce.code.challenge.method':'S256'}}], 'users':users}
    (state/'realm.json').write_text(json.dumps(realm))
    (state/'browser.json').write_text(json.dumps(browser))
    # Files mounted for nonroot identity/browser; parent scratch remains private to the owner.
    (state/'realm.json').chmod(0o444)
    (state/'browser.json').chmod(0o444)
    return '\n'.join(sql), internal_ids


def main():
    scratch = os.environ.get('TMPDIR')
    if not scratch:
        raise ValueError('private TMPDIR required')
    project = 'enginia360-r00b-' + secrets.token_hex(6)
    before_volumes = inventory('volume')
    before_running = set(run(['docker','ps','-q','--no-trunc']).splitlines())
    with tempfile.TemporaryDirectory(prefix=project+'-', dir=scratch) as directory:
        state = Path(directory)
        values = {key:secrets.token_hex(24) for key in ['R00_INFRA_PASSWORD','R00_OWNER_PASSWORD','R00_APP_PASSWORD','R00_CLIENT_SECRET']}
        values.update(R00_STATE=str(state), R00_POOL_SIZE='1')
        envfile = state/'runtime.env'
        envfile.write_text(''.join(key+'='+value+'\n' for key,value in values.items()))
        envfile.chmod(0o600)
        run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=Ephemeral R00 acceptance CA',
             '-addext','basicConstraints=critical,CA:TRUE','-keyout',str(state/'ca.key'),'-out',str(state/'ca.crt')])
        (state/'ca.key').chmod(0o600)
        (state/'public').mkdir()
        (state/'public'/'ca.crt').write_bytes((state/'ca.crt').read_bytes())
        for service, host, uid in [('postgres','postgres',70),('api','api.r00.test',1654),('web','app.r00.test',101),('identity','idp.r00.test',1000)]:
            certificate(state,service,host,uid)
        (state/'postgres'/'pg_hba.conf').write_text('local all all trust\nhostnossl all all all reject\nhostssl all all all scram-sha-256\n')
        sql, internal_ids = fixtures(state,values['R00_CLIENT_SECRET'])
        control = state/'control'
        control.mkdir()
        control.chmod(0o777)  # private per-run scratch; the nonroot browser writes lifecycle requests here
        command = ['docker','compose','--env-file',str(envfile),'-p',project,'-f',str(CONFIG)]
        def interrupted(signum, frame):
            raise KeyboardInterrupt
        previous = {sig:signal.signal(sig,interrupted) for sig in (signal.SIGINT,signal.SIGTERM)}
        try:
            print('R00.b build pinned services', flush=True)
            run(command+['build'],timeout=480)
            print('R00.b start TLS PostgreSQL/identity and apply empty migrations', flush=True)
            run(command+['up','-d','--wait','--wait-timeout','180','postgres','identity'],timeout=210)
            run(command+['run','--rm','--no-deps','-T','migrator'],timeout=90)
            query = command+['exec','-T','postgres','psql','-X','-qAt','-U','postgres','-d','runtime','-v','ON_ERROR_STOP=1']
            assert run(query+['-c','SELECT count(*) FROM runtime_migrations.applied']).strip() == manifest_count
            empty = """DO $$ DECLARE r record; n bigint; BEGIN FOR r IN SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT IN ('pg_catalog','information_schema','runtime_migrations') LOOP EXECUTE format('SELECT count(*) FROM %I.%I',r.schemaname,r.tablename) INTO n; IF n <> 0 THEN RAISE EXCEPTION 'business data before fixture'; END IF; END LOOP; END $$;"""
            run(query, input=empty)
            run(query, input=sql)
            def owner_mandate(mandate,operation):
                source=state/('mandate-'+mandate+'.json')
                payload=json.loads(source.read_text())
                payload['operation']=operation
                source.chmod(0o600)
                source.write_text(json.dumps(payload))
                source.chmod(0o444)
                output=run(command+['run','--rm','--no-deps','-T','-v',str(source)+':/run/mandate.json:ro','--entrypoint','python3','migrator','scripts/owner-operative-mandate.py','/run/mandate.json'],timeout=45)
                assert 'committed and exact state read back' in output
                print('R01B_OWNER_PROCEDURE '+operation+' verified',flush=True)
            for mandate in json.loads((state/'browser.json').read_text())['mandates']:
                owner_mandate(mandate,'create')
            run(command+['up','-d','api','web'],timeout=120)
            ids = run(command+['ps','-q']).splitlines()
            for container in json.loads(run(['docker','inspect',*ids])):
                host = container['HostConfig']
                assert container['Config']['User'] not in ('','0','root') and host['ReadonlyRootfs']
                assert host['CapDrop'] == ['ALL'] and 'no-new-privileges:true' in host['SecurityOpt']
                assert host['Memory'] > 0 and host['NanoCpus'] > 0 and host['PidsLimit'] > 0
                assert not host['PortBindings'] and not any(m['Type']=='volume' for m in container['Mounts'])
            assert json.loads(run(['docker','network','inspect',project+'_runtime']))[0]['Internal']
            print('R00.b actual Chromium core acceptance',flush=True)
            # Browser output contains only named assertions, never auth URLs/tokens/HAR.
            process = subprocess.Popen(command+['run','--rm','--no-deps','-T','browser'],cwd=ROOT)
            deadline = time.monotonic()+240
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Chromium acceptance deadline')
                    request = control/'request'
                    if request.exists():
                        action = request.read_text()
                        request.unlink()
                        if action == 'database-outage':
                            run(command+['pause','postgres'],timeout=30)
                        elif action == 'database-recover':
                            run(command+['unpause','postgres'],timeout=30)
                        elif action == 'identity-outage':
                            run(command+['pause','identity'],timeout=30)
                        elif action == 'identity-recover':
                            run(command+['unpause','identity'],timeout=30)
                        elif action == 'api-restart':
                            run(command+['restart','api'],timeout=60)
                        elif action in ('capability-disable', 'capability-remove', 'capability-restore'):
                            company = json.loads((state/'browser.json').read_text())['contexts'][0]['legalEntityId']
                            if action == 'capability-disable':
                                statement = f"UPDATE organization_access.capability_activations SET \"Enabled\"=false WHERE \"LegalEntityId\"='{company}' AND \"Capability\"='organization-context';"
                            elif action == 'capability-remove':
                                statement = f"DELETE FROM organization_access.capability_activations WHERE \"LegalEntityId\"='{company}' AND \"Capability\"='organization-context';"
                            else:
                                statement = f"INSERT INTO organization_access.capability_activations VALUES ('{company}','organization-context',true);"
                            run(query, input=statement)
                        elif action in ('read-revoke','read-restore','write-revoke','write-restore'):
                            permission, operation = action.split('-')
                            membership = f"SELECT \"Id\" FROM organization_access.memberships WHERE \"IdentitySubject\"='{internal_ids[0]}'"
                            if operation == 'revoke':
                                statement = f"DELETE FROM organization_access.membership_scopes WHERE \"MembershipId\"=({membership}) AND \"Permission\"='organization-context.{permission}';"
                            else:
                                context = json.loads((state/'browser.json').read_text())['contexts'][0]
                                tenant,company,site,warehouse = [context[k] for k in ('tenantId','legalEntityId','siteId','warehouseId')]
                                statement = f"INSERT INTO organization_access.membership_scopes VALUES ('{uuid.uuid4()}',({membership}),'{tenant}','{company}','{site}','{warehouse}','organization-context.{permission}');"
                            run(query, input=statement)
                        elif action == 'mandate-revoke':
                            mandates = json.loads((state/'browser.json').read_text())['mandates']
                            for mandate in mandates:
                                owner_mandate(mandate,'revoke')
                        elif action == 'binding-revoke':
                            run(query,input="DELETE FROM organization_access.external_identity_bindings WHERE \"InternalIdentityId\"='"+internal_ids[2]+"';")
                        else:
                            raise ValueError('unknown browser lifecycle command')
                        print('R00B_LIFECYCLE '+action,flush=True)
                        (control/'ack').write_text(action)
                    time.sleep(0.1)
                if process.returncode:
                    raise RuntimeError('Chromium acceptance failed')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            assert run(query+['-c','SELECT count(*) FROM organization_access.context_notes']).strip() == '3'
            assert run(query+['-c',"SELECT count(*) FROM pg_stat_activity WHERE usename='runtime_app'"]).strip() == '1'
            logs = run(command+['logs','--no-color','api','web','identity'])
            for value in list(values.values())[:4]:
                assert value not in logs, 'secret in service logs'
            assert 'code=synthetic' not in logs
            print('PASS R00.b core TLS/Chromium acceptance',flush=True)
        except Exception:
            diagnostics = run(command+['logs','--no-color','--tail','25','identity','api','web'])
            for key in ('R00_INFRA_PASSWORD','R00_OWNER_PASSWORD','R00_APP_PASSWORD','R00_CLIENT_SECRET'):
                value = values[key]
                diagnostics = diagnostics.replace(value, '[redacted]')
            diagnostics = re.sub(r'(https?://[^?\s]+)\?[^\s]*', r'\1?[redacted]', diagnostics)
            print(diagnostics,flush=True)
            raise
        finally:
            for sig in previous:
                signal.signal(sig,signal.SIG_IGN)
            try:
                cleanup(command,project)
            finally:
                for sig,handler in previous.items():
                    signal.signal(sig,handler)
    assert inventory('volume') == before_volumes
    assert set(run(['docker','ps','-q','--no-trunc']).splitlines()) == before_running
    print('PASS R00.b guarded cleanup; protected running containers and retained volumes unchanged.',flush=True)


if __name__ == '__main__':
    main()
