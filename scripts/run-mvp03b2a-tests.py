#!/usr/bin/env python3
"""Private ephemeral MVP03.b.2a tests; reuses CA-trusted OIDC fixture, never a supplied target."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import tempfile
import time
import uuid
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r00', ROOT / 'scripts/run-r00b-tests.py')
assert spec and spec.loader
r00 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r00)
r00.CONFIG = ROOT / 'compose.mvp02c-test.yaml'
run = r00.run

def write_readonly_json(path, value):
    if path.exists():
        path.chmod(384)
    try:
        path.write_text(json.dumps(value))
    finally:
        if path.exists():
            path.chmod(292)

def fixtures(state, secret):
    spec = importlib.util.spec_from_file_location('backend_fixture', ROOT / 'scripts/run-mvp02b-tests.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.fixtures(state, secret)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', required=True)
    args = parser.parse_args()
    evidence = Path(args.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    evidence.chmod(511)
    project = 'enginia360-r00b-' + secrets.token_hex(6)
    before_volumes = r00.inventory('volume')
    before_running = set(run(['docker', 'ps', '-q', '--no-trunc']).splitlines())
    protected=json.loads(run(['docker','inspect',*sorted(before_running)])) if before_running else []
    protected_snapshot={c['Id']:c['State']['StartedAt'] for c in protected}
    (evidence/'preexisting-containers.json').write_text(json.dumps(protected_snapshot,indent=2))
    with tempfile.TemporaryDirectory(prefix='mvp03b2a-', dir=os.environ['TMPDIR']) as directory:
        state = Path(directory)
        values = {key: secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD', 'R00_OWNER_PASSWORD', 'R00_APP_PASSWORD', 'R00_CLIENT_SECRET')}
        values.update(R00_STATE=str(state), R00_POOL_SIZE=os.environ.get('MVP03B2A_POOL_SIZE', '4'), MVP02C_EVIDENCE=str(evidence))
        envfile = state / 'runtime.env'
        envfile.write_text(''.join((k + '=' + v + '\n' for k, v in values.items())))
        envfile.chmod(384)
        run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=Ephemeral acceptance CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-keyout', str(state / 'ca.key'), '-out', str(state / 'ca.crt')])
        (state / 'ca.key').chmod(384)
        (state / 'public').mkdir()
        (state / 'public/ca.crt').write_bytes((state / 'ca.crt').read_bytes())
        for service, host, uid in [('postgres', 'postgres', 70), ('api', 'api.r00.test', 1654), ('web', 'app.r00.test', 101), ('identity', 'idp.r00.test', 1000)]:
            r00.certificate(state, service, host, uid)
        (state / 'postgres/pg_hba.conf').write_text('local all all trust\nhostnossl all all all reject\nhostssl all all all scram-sha-256\n')
        sql, identities = fixtures(state, values['R00_CLIENT_SECRET'])
        control = state / 'control'
        control.mkdir()
        control.chmod(511)
        config = state / 'membership-acceptance.yaml'
        config.write_text(r00.CONFIG.read_text().replace('      Authentication__ValidIssuer:', '      Authentication__Authority: https://idp.r00.test:8443/realms/runtime\n      Authentication__ValidIssuer:'))
        config.chmod(0o444)
        r00.CONFIG = config
        command = ['docker', 'compose', '--project-directory', str(ROOT), '--env-file', str(envfile), '-p', project, '-f', str(r00.CONFIG)]

        def interrupted(signum, frame):
            raise KeyboardInterrupt
        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        process = None
        try:
            run(command + ['build'], timeout=600)
            run(command + ['up', '-d', '--wait', '--wait-timeout', '180', 'postgres', 'identity'], timeout=210)
            mounts = ['-v', str(ROOT / 'scripts') + ':/runtime/scripts:ro', '-v', str(ROOT / 'database/runtime') + ':/runtime/database/runtime:ro']
            print('MVP03B2A SQL membership authorization and physical barriers', flush=True)
            testenv = dict(os.environ, PGPASSWORD=values['R00_INFRA_PASSWORD'], R00_OWNER_PASSWORD=values['R00_OWNER_PASSWORD'], R00_APP_PASSWORD=values['R00_APP_PASSWORD'])
            completed = subprocess.run(command + ['run', '--rm', '--no-deps', '-T', *mounts, '-e', 'R00_MIGRATION_TESTS=1', '-e', 'PGUSER=postgres', '-e', 'PGPASSWORD', '-e', 'R00_OWNER_USER=runtime_owner', '-e', 'R00_OWNER_PASSWORD', '-e', 'R00_APP_PASSWORD', '--entrypoint', 'python3', 'migrator', 'scripts/test-mvp03b2a-membership.py', 'MembershipAccessTests', '-v'], env=testenv, cwd=ROOT, text=True, capture_output=True, timeout=240)
            (evidence / 'sql-tests.log').write_text(completed.stdout + completed.stderr + '\nexit=' + str(completed.returncode))
            print(completed.stdout + completed.stderr, flush=True)
            if completed.returncode:
                raise RuntimeError('tenant membership SQL assertions failed')
            run(command + ['run', '--rm', '--no-deps', '-T', *mounts, 'migrator'], timeout=90)
            query = command + ['exec', '-T', 'postgres', 'psql', '-X', '-qAt', '-U', 'postgres', '-d', 'runtime', '-v', 'ON_ERROR_STOP=1']
            run(query, input=sql)
            binding = json.loads(run(query + ['-c', f"""SELECT row_to_json(b) FROM organization_access.external_identity_bindings b WHERE "InternalIdentityId"='{identities[4]}' """]).strip())
            revision = 0

            def owner(operation):
                nonlocal revision
                payload = dict(commandId=str(uuid.uuid4()), operation=operation, internalIdentityId=binding['InternalIdentityId'], issuer=binding['Issuer'], subject=binding['Subject'], verificationReference=str(uuid.uuid4()), expectedRevision=revision)
                path = state / 'public/authority.json'
                write_readonly_json(path, payload)
                for _ in range(2):
                    result = run(command + ['run', '--rm', '--no-deps', '-T', *mounts, '--entrypoint', 'python3', 'migrator', 'scripts/owner-platform-authority.py', '/run/tls/authority.json'], timeout=45)
                    assert 'exact immutable audit read back' in result
                revision += 1
                print('MVP03B2A_OWNER ' + operation + ' exact replay/readback', flush=True)
            # Execute singleton-owner classes in distinct invocations. Never
            # parallelize them against one platform-authority slot.
            image = project + '-membership-api'
            run(['docker','build','-f','runtime-pool-test.Dockerfile','-t',image,'.'], timeout=600)
            api_env = dict(os.environ,
                R00_POOL_CONNECTION='Host=postgres;Database=runtime;Username=runtime_app;Password='+values['R00_APP_PASSWORD']+';SSL Mode=VerifyFull;Root Certificate=/run/tls/ca.crt;Timeout=5;Command Timeout=15',
                R00_POOL_ADMIN_CONNECTION='Host=postgres;Database=runtime;Username=postgres;Password='+values['R00_INFRA_PASSWORD']+';SSL Mode=VerifyFull;Root Certificate=/run/tls/ca.crt;Timeout=5;Command Timeout=15')
            for suite in ('MembershipAccessTests','CounterpartyMembershipFenceTests','WorkshopMembershipFenceTests','BusinessMembershipFenceTests'):
                invocation=['docker','run','--rm','--label','com.docker.compose.project='+project,
                    '--label','com.docker.compose.project.config_files='+str(config),
                    '--network',project+'_runtime','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
                    '--memory=1024m','--cpus=2','--pids-limit=256','--log-opt=max-size=5m','--log-opt=max-file=2',
                    '--tmpfs','/tmp:rw,noexec,nosuid,size=128m,uid=1654,gid=1654',
                    '-v',str(state/'public')+':/run/tls:ro','-v',str(evidence)+':/evidence:rw',
                    '-e','R00_POOL_CONNECTION','-e','R00_POOL_ADMIN_CONNECTION','--entrypoint','dotnet',image,
                    'test','tests/Enginia360.Api.Tests','-c','Release','--no-build','--no-restore',
                    '--filter','FullyQualifiedName~'+suite,'--logger','trx;LogFileName='+suite+'.trx','--results-directory','/evidence']
                completed=subprocess.run(invocation,env=api_env,cwd=ROOT,text=True,capture_output=True,timeout=360)
                (evidence/(suite+'.log')).write_text(completed.stdout+completed.stderr+'\nexit='+str(completed.returncode))
                print(completed.stdout+completed.stderr,flush=True)
                if completed.returncode: raise RuntimeError('membership owning suite failed: '+suite)
                import xml.etree.ElementTree as ET
                trx=ET.parse(evidence/(suite+'.trx'))
                counters=trx.find('.//{*}Counters')
                assert counters is not None and int(counters.attrib['total'])>0
                assert int(counters.attrib['executed'])==int(counters.attrib['total'])
                assert int(counters.attrib.get('failed','0'))==0 and int(counters.attrib.get('notExecuted','0'))==0
                assert int(counters.attrib['passed'])==int(counters.attrib['total']),suite
            # Actual post-migration catalog, not a source-only SD/RLS inventory.
            catalog=run(query+['-c',"SELECT jsonb_build_object('functions',(SELECT jsonb_agg(jsonb_build_object('name',p.oid::regprocedure::text,'definer',p.prosecdef,'appExecute',has_function_privilege('runtime_app',p.oid,'EXECUTE'),'definition',pg_get_functiondef(p.oid))) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname IN ('organization_access','counterparties','catalog','vehicles','workshop','inventory','billing','accounting','integrations') AND p.prokind='f'),'policies',(SELECT jsonb_agg(to_jsonb(x)) FROM pg_policies x))"])
            (evidence/'actual-runtime-catalog.json').write_text(catalog)
            runtime_catalog=json.loads(catalog)
            # Exact historical catalog inventory, including overloads; neither a
            # regex over migrations nor a count can detect an unexpected ingress.
            historical_sd = '''catalog.purchase_intent_quote(uuid,uuid,uuid,uuid)
catalog.set_supplier_purchase_price(uuid,uuid,uuid,uuid,integer,integer,integer,integer,text)
catalog.supplier_purchase_price_state(uuid,uuid,uuid)
counterparties.common_edit_state(uuid,uuid)
counterparties.edit_common(uuid,uuid,uuid,integer,integer,text,text,text)
counterparties.purchase_suppliers(uuid)
counterparties.read_giobby_vendor_identity(uuid,uuid)
counterparties.set_supplier_role(uuid,uuid,uuid,integer,integer,boolean)
inventory.accept_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,integer,integer,integer,text,jsonb)
inventory.create_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,jsonb)
inventory.create_receipt_intent(uuid,uuid,text,jsonb)
inventory.pending_purchase_dispatch(integer,integer)
inventory.pending_receipt_dispatch(integer,integer)
inventory.purchase_intent_state(uuid,uuid,uuid)
inventory.read_purchase_dispatch(uuid,uuid,uuid)
inventory.read_receipt_dispatch(uuid,uuid,uuid)
inventory.receipt_sources(uuid,uuid,uuid)
inventory.receipt_state(uuid)
inventory.record_purchase_outcome(uuid,uuid,uuid,text)
inventory.record_receipt_outcome(uuid,uuid,uuid,text)
organization_access.administrative_request_authorized(uuid,uuid,text,uuid,uuid)
organization_access.command_operative_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)
organization_access.command_organization(uuid,jsonb)
organization_access.command_organization_delegation(uuid,jsonb)
organization_access.command_tenant_role(uuid,jsonb)
organization_access.company_stock_profile(uuid,uuid)
organization_access.current_membership_access(uuid)
organization_access.current_tenant_role_scopes()
organization_access.grant_administration()
organization_access.inventory_new_return_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean)
organization_access.inventory_release_authorized(uuid,uuid,text,uuid,uuid,uuid,boolean)
organization_access.read_master_authority(uuid)
organization_access.read_organization(uuid)
organization_access.read_organization_delegations(uuid)
organization_access.read_organization_workspace()
organization_access.read_tenant_roles(uuid)
workshop.pending_administrative_outbox(integer,integer)
workshop.pending_administrative_outbox(integer)'''.splitlines()
            additions = {'organization_access.command_membership_access(uuid,jsonb)',
                'workshop.read_accepted_administrative_request(uuid,uuid)',
                'workshop.record_accepted_administrative_outcome(uuid,uuid,text,text,text)',
                'organization_access.read_onboarding(uuid)',
                'organization_access.begin_onboarding(uuid)',
                'organization_access.pending_onboarding_status(uuid,uuid)',
                'organization_access.command_onboarding(uuid,jsonb)'}
            executable_sd = {f['name'] for f in runtime_catalog['functions'] if f['definer'] and f['appExecute']}
            assert len(historical_sd) == len(set(historical_sd)) == 38
            assert executable_sd == set(historical_sd) | additions, executable_sd.symmetric_difference(set(historical_sd) | additions)
            accepted_sd = {name for name in executable_sd if name.startswith(('inventory.pending_', 'inventory.read_', 'inventory.record_', 'workshop.pending_', 'workshop.read_accepted_', 'workshop.record_accepted_'))}
            (evidence/'exact-sd-classification.json').write_text(json.dumps(dict(historical=sorted(historical_sd),added=sorted(additions),acceptedWork=sorted(accepted_sd),userDerived=sorted(executable_sd-accepted_sd)),indent=2))
            acl = run(query+['-c', "SELECT jsonb_agg(jsonb_build_object('schema',n.nspname,'table',c.relname,'column',a.attname,'select',has_column_privilege('runtime_app',c.oid,a.attnum,'SELECT'),'insert',has_column_privilege('runtime_app',c.oid,a.attnum,'INSERT'),'update',has_column_privilege('runtime_app',c.oid,a.attnum,'UPDATE'),'delete',has_table_privilege('runtime_app',c.oid,'DELETE'),'truncate',has_table_privilege('runtime_app',c.oid,'TRUNCATE')) ORDER BY n.nspname,c.relname,a.attnum) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped WHERE c.relkind='r' AND n.nspname IN ('organization_access','counterparties','catalog','vehicles','workshop','inventory','billing','accounting','integrations')"])
            (evidence/'actual-runtime-column-acl.json').write_text(acl)
            for row in json.loads(acl):
                if row['schema']=='organization_access' and row['table'] in ('membership_access_state','membership_access_audit','membership_access_snapshot_fence'):
                    assert not any(row[k] for k in ('select','insert','update','delete','truncate')),row
            owners=run(query+['-c', "SELECT jsonb_agg(jsonb_build_object('function',p.oid::regprocedure::text,'owner',r.rolname,'superuser',r.rolsuper,'bypassRls',r.rolbypassrls,'settings',p.proconfig)) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner WHERE p.prosecdef AND n.nspname IN ('organization_access','counterparties','catalog','vehicles','workshop','inventory','billing','accounting','integrations')"])
            (evidence/'actual-sd-owners.json').write_text(owners)
            # The published envelope-only NOLOGIN reader intentionally has
            # BYPASSRLS. Classify its exact five functions and fifteen column
            # grants instead of imposing a false blanket no-bypass assertion.
            envelope_functions={'workshop.pending_administrative_outbox(integer)',
                'workshop.pending_administrative_outbox(integer,integer)',
                'inventory.pending_purchase_dispatch(integer,integer)',
                'inventory.pending_receipt_dispatch(integer,integer)',
                'inventory.receipt_source_company(uuid)'}
            bypass_functions=set()
            for row in json.loads(owners):
                assert not row['superuser'],row
                if row['bypassRls']:
                    assert row['owner']=='enginia360_outbox_reader',row
                    bypass_functions.add(row['function'])
                assert any(setting.startswith('search_path=') for setting in (row['settings'] or [])),row
            assert bypass_functions==envelope_functions,bypass_functions
            reader=run(query+['-c', "SELECT jsonb_build_object('login',rolcanlogin,'superuser',rolsuper,'createRole',rolcreaterole,'createDb',rolcreatedb,'replication',rolreplication) FROM pg_roles WHERE rolname='enginia360_outbox_reader'"])
            assert json.loads(reader)==dict(login=False,superuser=False,createRole=False,createDb=False,replication=False)
            reader_acl=run(query+['-c', "SELECT jsonb_agg(jsonb_build_object('table',n.nspname||'.'||c.relname,'column',a.attname,'select',has_column_privilege('enginia360_outbox_reader',c.oid,a.attnum,'SELECT'),'insert',has_column_privilege('enginia360_outbox_reader',c.oid,a.attnum,'INSERT'),'update',has_column_privilege('enginia360_outbox_reader',c.oid,a.attnum,'UPDATE'),'delete',has_table_privilege('enginia360_outbox_reader',c.oid,'DELETE'),'truncate',has_table_privilege('enginia360_outbox_reader',c.oid,'TRUNCATE'))) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped WHERE c.relkind='r' AND n.nspname IN ('organization_access','counterparties','catalog','vehicles','workshop','inventory','billing','accounting','integrations')"])
            (evidence/'accepted-envelope-reader-acl.json').write_text(reader_acl)
            expected_columns={
                (table,column) for table,columns in {
                    'workshop.administrative_outbox':['TenantId','RequestId','CreatedAt'],
                    'workshop.administrative_outcomes':['RequestId'],
                    'inventory.purchase_intents':['TenantId','LegalEntityId','Id','CreatedAt'],
                    'inventory.purchase_intent_prices':['IntentId'],
                    'inventory.purchase_intent_outcomes':['IntentId'],
                    'inventory.receipt_intents':['Id','TenantId','LegalEntityId','CreatedAt'],
                    'inventory.receipt_outcomes':['ReceiptId'],
                }.items() for column in columns}
            assert {(r['table'],r['column']) for r in json.loads(reader_acl) if r['select']}==expected_columns
            assert not any(r[k] for r in json.loads(reader_acl) for k in ('insert','update','delete','truncate'))
            for function in runtime_catalog['functions']:
                if '_before_access(' in function['name']:
                    assert not function['appExecute'],'private original executable: '+function['name']
            required={
                'organization_access':('membership_scopes','common_edit_permissions','company_permissions','delegation_mandates','delegated_scopes'),
                'counterparties':('counterparties','destinations'),
                'catalog':('items','supplier_purchase_price_history'),
                'vehicles':('vehicles',),
                'inventory':('stock','reservations','picking_policies','picking_locations','picks','consumptions','carcass_locations','carcass_returns','carcass_return_installations','reservation_releases','new_part_returns','purchase_intents','purchase_intent_outbox','purchase_intent_prices','purchase_intent_outcomes','receipt_intents','receipt_outbox','receipt_outcomes'),
                'billing':('document_types','issuer_profiles','invoices','invoice_confirmations','invoice_journal_links'),
                'accounting':('chart_accounts','journal_entries','journal_entry_lines'),
                'workshop':('orders','document_types','line_policies','carcass_policies','commercial_lines','working_groups','order_notes','editor_commands','workspace_history','technical_closures','installations','administrative_destinations','administrative_requests','administrative_bindings','administrative_outbox','administrative_outcomes','administrative_closures','internal_billing_claims','own_actual_time_streams','own_actual_time_entries','own_actual_time_commands','own_actual_time_versions','actual_time_group_references')}
            for schema,tables in required.items():
                for table in tables:
                    policy=[p for p in runtime_catalog['policies'] if p['schemaname']==schema and p['tablename']==table and p['policyname']=='membership_access_current']
                    assert len(policy)==1 and policy[0]['permissive']=='RESTRICTIVE',(schema,table)
                    expected_predicate='organization_access.current_membership_access("TenantId")'
                    assert policy[0]['qual']==policy[0]['with_check']==expected_predicate,(schema,table,policy)
                    assert policy[0]['roles']==['runtime_app'],(schema,table,policy)
                    assert policy[0]['cmd']=='ALL',(schema,table,policy)
            assert {(p['schemaname'],p['tablename']) for p in runtime_catalog['policies'] if p['policyname']=='membership_access_current'}=={(schema,table) for schema,tables in required.items() for table in tables}
            forced=run(query+['-c',"SELECT jsonb_agg(jsonb_build_object('schema',n.nspname,'table',c.relname,'force',c.relforcerowsecurity,'rls',c.relrowsecurity)) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r'"])
            (evidence/'actual-runtime-force-rls.json').write_text(forced)
            table_flags={(r['schema'],r['table']):r for r in json.loads(forced)}
            for schema,tables in required.items():
                for table in tables:
                    assert table_flags[schema,table]['force'] and table_flags[schema,table]['rls'],(schema,table)

            # Published migration immutability is verified here, never while
            # implementing the point. New0040 is not part of the old ledger.
            import hashlib
            published=json.loads(subprocess.check_output(['git','show','2bad821b46b29d5ebb0556461f0eb3b3a61df280:database/runtime/manifest.json'],cwd=ROOT,text=True))
            hashes={}
            for entry in published:
                path='database/runtime/'+entry['path']
                original=subprocess.check_output(['git','show','2bad821b46b29d5ebb0556461f0eb3b3a61df280:'+path],cwd=ROOT)
                current=(ROOT/path).read_bytes();assert current==original,path
                hashes[path]=hashlib.sha256(current).hexdigest()
            assert len(hashes)==39
            (evidence/'published-migration-hashes.json').write_text(json.dumps(hashes,indent=2))
            (evidence/'candidate.json').write_text(json.dumps(dict(head=run(['git','rev-parse','HEAD']).strip(),pool=values['R00_POOL_SIZE'],validationPhase='final',operationalReadiness=False),indent=2))
            run(command + ['up', '-d', 'api', 'next', 'web'], timeout=120)
            ids = run(command + ['ps', '-q']).splitlines()
            inspected = json.loads(run(['docker', 'inspect', *ids]))
            metadata = []
            for container in inspected:
                host = container['HostConfig']
                metadata.append(dict(service=container['Config']['Labels']['com.docker.compose.service'], user=container['Config']['User'], readonly=host['ReadonlyRootfs'], capDrop=host['CapDrop'], securityOpt=host['SecurityOpt'], portBindings=host['PortBindings'], memory=host['Memory'], cpus=host['NanoCpus'], pids=host['PidsLimit'], mountTypes=[m['Type'] for m in container['Mounts']]))
                assert container['Config']['User'] not in ('', '0', 'root') and host['ReadonlyRootfs'] and (host['CapDrop'] == ['ALL']) and ('no-new-privileges:true' in host['SecurityOpt']) and (not host['PortBindings']) and (host['Memory'] > 0) and (host['NanoCpus'] > 0) and (host['PidsLimit'] > 0) and (not any((m['Type'] == 'volume' for m in container['Mounts'])))
            assert json.loads(run(['docker', 'network', 'inspect', project + '_runtime']))[0]['Internal']
            (evidence / 'runtime-hardening.json').write_text(json.dumps(dict(containers=metadata, internalNetwork=True, pool=values['R00_POOL_SIZE']), indent=2))
            browser = command + ['run', '--rm', '--no-deps', '-T', '--entrypoint', 'sh', 'browser', '-c', 'mkdir -p "$HOME/.pki/nssdb" && certutil -N -d sql:$HOME/.pki/nssdb --empty-password && certutil -A -d sql:$HOME/.pki/nssdb -n runtime-ephemeral-ca -t C,, -i /run/tls/ca.crt && exec node mvp03b2a-membership.cjs']
            process = subprocess.Popen(browser, cwd=ROOT)
            deadline = time.monotonic() + 420
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError('authority browser deadline')
                request = control / 'request'
                if request.exists():
                    # The browser is a one-shot container; inspect it while its first
                    # control request proves it is alive, not only the five services.
                    browser_ids = run(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + project, '--filter', 'label=com.docker.compose.service=browser']).splitlines()
                    assert len(browser_ids) == 1, 'one owned browser must be alive'
                    browser_container = json.loads(run(['docker', 'inspect', browser_ids[0]]))[0]
                    host = browser_container['HostConfig']
                    assert browser_container['Config']['User'] == '1001:1001'
                    assert host['ReadonlyRootfs'] and host['CapDrop'] == ['ALL'] and 'no-new-privileges:true' in host['SecurityOpt']
                    assert not host['PortBindings'] and host['Memory'] > 0 and host['NanoCpus'] > 0 and host['PidsLimit'] > 0
                    assert not any(m['Type'] == 'volume' for m in browser_container['Mounts'])
                    if not any(row['service'] == 'browser' for row in metadata):
                        metadata.append(dict(service='browser', user=browser_container['Config']['User'], readonly=host['ReadonlyRootfs'], capDrop=host['CapDrop'], securityOpt=host['SecurityOpt'], portBindings=host['PortBindings'], memory=host['Memory'], cpus=host['NanoCpus'], pids=host['PidsLimit'], mountTypes=[m['Type'] for m in browser_container['Mounts']]))
                        (evidence / 'runtime-hardening.json').write_text(json.dumps(dict(containers=metadata, internalNetwork=True, pool=values['R00_POOL_SIZE']), indent=2))
                    action = request.read_text()
                    request.unlink()
                    if action in ('grant', 'revoke'):
                        owner(action)
                    elif action == 'membership-audit-readback':
                        expected = json.loads((control / 'expected.json').read_text())
                        ids=expected['commands']
                        assert all(__import__('re').fullmatch('[0-9a-f-]{36}',key) for key in ids)
                        rows=json.loads(run(query+['-c',"SELECT coalesce(jsonb_agg(to_jsonb(a)),'[]') FROM organization_access.membership_access_audit a WHERE \"Outcome\"='applied' AND \"CommandId\"=ANY(ARRAY["+','.join("'"+key+"'::uuid" for key in ids)+"])"]))
                        assert sorted(row['CommandId'] for row in rows)==sorted(ids)
                        assert all(row['ResourceId']==row['After']['membershipId'] and row['OccurredAt'] and row['Authority'] for row in rows)
                        (evidence/'membership-sql-readback.json').write_text(json.dumps(rows,indent=2))
                    else:
                        raise ValueError('unknown role acceptance control')
                    (control / 'ack').write_text(action)
                time.sleep(0.05)
            assert process.returncode == 0, 'authority Chromium failed'
            print('PASS MVP03B2A real TLS OIDC HTTP and Next SSR pool' + values['R00_POOL_SIZE'], flush=True)
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for sig in previous:
                signal.signal(sig, signal.SIG_IGN)
            try:
                r00.cleanup(command, project)
                if run(['docker','image','ls','-q',project+'-membership-api']).strip():
                    run(['docker','image','rm',project+'-membership-api'], timeout=45)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
    assert r00.inventory('volume') == before_volumes
    after_running=set(run(['docker','ps','-q','--no-trunc']).splitlines())
    observed=json.loads(run(['docker','inspect',*sorted(before_running)])) if before_running else []
    after_snapshot={c['Id']:c['State']['StartedAt'] for c in observed}
    (evidence/'postexisting-containers.json').write_text(json.dumps(after_snapshot,indent=2))
    (evidence/'unrelated-running-diff.json').write_text(json.dumps(dict(added=sorted(after_running-before_running),removed=sorted(before_running-after_running)),indent=2))
    assert after_snapshot==protected_snapshot,'pre-existing container identity/start changed'
    assert not set(run(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project]).splitlines()),'owned cleanup incomplete'
    import hashlib
    digests={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(evidence.iterdir()) if path.is_file() and path.name!='artifact-sha256.json'}
    (evidence/'artifact-sha256.json').write_text(json.dumps(dict(head=run(['git','rev-parse','HEAD']).strip(),tree=run(['git','rev-parse','HEAD^{tree}']).strip(),files=digests),indent=2))
    print('PASS MVP03B2A guarded cleanup; protected services and volumes unchanged', flush=True)
if __name__ == '__main__':
    main()