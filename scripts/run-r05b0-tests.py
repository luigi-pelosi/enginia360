#!/usr/bin/env python3
"""Bounded actual R03.c Chromium/OIDC/API/PostgreSQL acceptance with an isolated synthetic administrative simulator.

Guarded ephemeral R00 TLS primitives: internal network, no published port, no retained volume. The simulator is the
deterministic in-memory protocol-v1 stand-in on the private network; there is no Giobby, no real data, no deployment."""
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

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r03b_helpers', ROOT/'scripts/run-r03b-tests.py')
r03b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r03b)
r00 = r03b.r00
r00.CONFIG = ROOT/'compose.r05b0-test.yaml'
run = r00.run
marker = r03b.marker
POOL = os.environ.get('R05B0_POOL_SIZE', '4')
SIMULATOR_CONTROL = ('import json,sys,urllib.request\n'
                     'req=urllib.request.Request("http://127.0.0.1:8080"+sys.argv[1],data=(sys.argv[2].encode() if len(sys.argv)>2 else None),'
                     'headers={"Content-Type":"application/json"},method="POST" if len(sys.argv)>2 else "GET")\n'
                     'print(urllib.request.urlopen(req,timeout=5).read().decode())\n')


def fixtures(state, secret):
    os.environ['R03B_POOL_SIZE'] = POOL
    sql = r03b.fixtures(state, secret)
    browser = json.loads((state/'browser.json').read_text())
    context = browser['contexts'][0]
    tenant, company = context['tenantId'], context['legalEntityId']
    member = browser['adminMembershipId']
    extra = [f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{member}','{tenant}','{company}','{action}',NULL,NULL);"
             for action in ('workshop.orders.complete-administrative', 'workshop.administrative-requests.reconcile')]
    # The pilot company declares the external administrative destination; version 13 (Internal) of the shared fixture is superseded.
    extra.append(f"INSERT INTO workshop.administrative_destinations VALUES ('{tenant}','{company}',14,'External');")
    return sql + '\n' + '\n'.join(extra)


def main():
    if not os.environ.get('TMPDIR'): raise ValueError('private TMPDIR required')
    if POOL not in ('1', '4'): raise ValueError('pool acceptance is explicitly 1 or 4')
    if not (ROOT/'web/dist-ui01-runtime/ui01-runtime.html').exists(): raise ValueError('build:ui01-runtime required')
    project = 'enginia360-r00b-' + secrets.token_hex(6)
    before_volumes = r00.inventory('volume')
    before_running = set(run(['docker', 'ps', '-q', '--no-trunc']).splitlines())
    evidence = Path(os.environ['TMPDIR'])/('r05b0-logs/evidence-pool'+POOL)
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=project+'-', dir=os.environ['TMPDIR']) as directory:
        state = Path(directory)
        values = {key: secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD', 'R00_OWNER_PASSWORD', 'R00_APP_PASSWORD', 'R00_CLIENT_SECRET')}
        values.update(R00_STATE=str(state), R00_POOL_SIZE=POOL)
        envfile = state/'runtime.env'; envfile.write_text(''.join(k+'='+v+'\n' for k, v in values.items())); envfile.chmod(0o600)
        run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=Ephemeral UI01b CA', '-addext', 'basicConstraints=critical,CA:TRUE', '-keyout', str(state/'ca.key'), '-out', str(state/'ca.crt')])
        (state/'ca.key').chmod(0o600)
        (state/'public').mkdir(); (state/'public/ca.crt').write_bytes((state/'ca.crt').read_bytes())
        for service, host, uid in [('postgres', 'postgres', 70), ('api', 'api.r00.test', 1654), ('web', 'app.r00.test', 101), ('identity', 'idp.r00.test', 1000)]: r00.certificate(state, service, host, uid)
        (state/'postgres/pg_hba.conf').write_text('local all all trust\nhostnossl all all all reject\nhostssl all all all scram-sha-256\n')
        sql = fixtures(state, values['R00_CLIENT_SECRET'])
        (state/'control').mkdir(); (state/'control').chmod(0o777)
        command = ['docker', 'compose', '--env-file', str(envfile), '-p', project, '-f', str(r00.CONFIG)]

        def interrupted(signum, frame): raise KeyboardInterrupt
        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        holders = []
        try:
            print('R03C pinned build', flush=True); run(command+['build'], timeout=480)
            run(command+['up', '-d', '--wait', '--wait-timeout', '180', 'postgres', 'identity', 'admin-simulator', 'simulator-b'], timeout=210)
            run(command+['run', '--rm', '--no-deps', '-T', 'migrator'], timeout=90)
            query = command+['exec', '-T', 'postgres', 'psql', '-X', '-qAt', '-U', 'postgres', '-d', 'runtime', '-v', 'ON_ERROR_STOP=1']
            assert run(query+['-c', 'SELECT count(*) FROM runtime_migrations.applied']).strip() == str(len(json.loads((ROOT/'database/runtime/manifest.json').read_text())))
            assert run(query+['-c', 'SELECT count(*) FROM workshop.orders']).strip() == '0'
            run(query, input=sql)
            run(command+['up', '-d', 'api', 'web'], timeout=120)
            ids = run(command+['ps', '-q']).splitlines()
            for c in json.loads(run(['docker', 'inspect', *ids])):
                h = c['HostConfig']; assert c['Config']['User'] not in ('', '0', 'root') and h['ReadonlyRootfs']; assert h['CapDrop'] == ['ALL'] and 'no-new-privileges:true' in h['SecurityOpt']; assert not h['PortBindings'] and not any(m['Type'] == 'volume' for m in c['Mounts']); assert h['Memory'] > 0 and h['NanoCpus'] > 0 and h['PidsLimit'] > 0
            assert json.loads(run(['docker', 'network', 'inspect', project+'_runtime']))[0]['Internal']

            def simulator(path, body=None, service="admin-simulator"):
                args = command+['exec', '-T', service, 'python3', '-I', '-c', SIMULATOR_CONTROL, path] + ([body] if body is not None else [])
                return json.loads(run(args, timeout=30))
            process = subprocess.Popen(command+['run', '--rm', '--no-deps', '-T', 'browser'], cwd=ROOT)
            deadline = time.monotonic()+330
            try:
                while process.poll() is None:
                    if time.monotonic() >= deadline: raise TimeoutError('closure browser deadline')
                    request = state/'control/request'
                    if request.exists():
                        action = request.read_text(); request.unlink()
                        fixture = json.loads((state/'browser.json').read_text())
                        ctx0 = fixture['contexts'][0]
                        if action == 'hold-dispatch' and POOL == '1':
                            # A held physical worker connection deliberately saturates a one-slot pool.
                            # Pool1 proves completion, not contention: gate discovery in the isolated fixture,
                            # preserving/restoring its exact original definition (same rehearsal primitive as R06).
                            definition = run(query+['-c', "SELECT pg_get_functiondef('workshop.pending_administrative_outbox(integer,integer)'::regprocedure)"])
                            (state/'discovery.sql').write_text(definition)
                            run(query+['-c', '''CREATE OR REPLACE FUNCTION workshop.pending_administrative_outbox(max_items integer, scan_offset integer)
                                RETURNS TABLE ("TenantId" uuid, "RequestId" uuid) LANGUAGE sql STABLE SECURITY DEFINER
                                SET search_path=pg_catalog,pg_temp AS $$ SELECT NULL::uuid,NULL::uuid WHERE false $$;'''])
                        elif action == 'release-dispatch' and POOL == '1':
                            run(query, input=(state/'discovery.sql').read_text())
                        elif action == 'hold-dispatch':
                            holder = subprocess.Popen(query+['-f', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                            holders.append(holder)
                            holder.stdin.write('BEGIN; LOCK TABLE integrations.administrative_dispatches IN SHARE ROW EXCLUSIVE MODE;\n\\echo LOCKED\n'); holder.stdin.flush()
                            marker(holder, b'LOCKED')
                        elif action == 'release-dispatch':
                            holder.stdin.write('COMMIT;\n\\q\n'); holder.stdin.flush(); holder.stdin.close(); holder.wait(timeout=5)
                        elif action.startswith(('restart:', 'crash:')):
                            target = action.split(':', 1)[1]
                            assert target in ('A', 'B', 'Unknown', 'Missing', 'Path', 'Equivalent')
                            if action.startswith('crash:'): run(command+['kill', '-s', 'SIGKILL', 'api'], timeout=20)
                            values['R05B0_PROTOCOL'] = 'Unknown' if target == 'Unknown' else 'SimulatorV1'
                            values['R05B0_BASE_URL'] = '' if target == 'Missing' else ('http://ADMIN-SIMULATOR:8080/' if target == 'Equivalent' else 'http://' + ('simulator-b' if target == 'B' else 'admin-simulator') + ':8080/' + ('other/' if target == 'Path' else ''))
                            envfile.write_text(''.join(k+'='+v+'\n' for k, v in values.items()))
                            run(command+['up', '-d', '--no-deps', '--force-recreate', 'api'], timeout=60)
                            run(command+['restart', 'web'], timeout=30)  # nginx resolves the recreated API at startup.
                        elif action == 'historical-request':
                            data = json.loads((state/'control/historical.json').read_text())
                            order_id, request_id = str(uuid.UUID(data['order'])), str(uuid.UUID(data['requestId']))
                            summary = json.dumps(data['summary']).replace("'", "''")
                            run(query+['-c', f'''BEGIN; SELECT set_config('app.tenant_id','{ctx0['tenantId']}',true);
                                INSERT INTO workshop.administrative_requests
                                  ("Id","TenantId","OrderId","LegalEntityId","SiteId","Destination","DestinationVersion","ContractVersion","Revision","NetAmount","TaxAmount","Total","Currency","Summary","RequestedAt","OperatorId")
                                SELECT '{request_id}',o."TenantId",o."Id",o."LegalEntityId",o."SiteId",'External',14,1,2,
                                  (j->>'netAmount')::numeric,(j->>'taxAmount')::numeric,(j->>'total')::numeric,'EUR',j,clock_timestamp(),r."OperatorId"
                                FROM workshop.orders o CROSS JOIN (SELECT '{summary}'::jsonb j) s
                                CROSS JOIN LATERAL (SELECT "OperatorId" FROM workshop.administrative_requests LIMIT 1) r WHERE o."Id"='{order_id}';
                                INSERT INTO workshop.administrative_outbox SELECT "Id","TenantId","RequestedAt" FROM workshop.administrative_requests WHERE "Id"='{request_id}'; COMMIT;'''])
                        elif action == 'refuse-historical-backfill':
                            data = json.loads((state/'control/historical.json').read_text())
                            request_id = str(uuid.UUID(data['requestId']))
                            attempt = subprocess.run(query+['-c', f'''BEGIN; SET LOCAL ROLE runtime_app; SELECT set_config('app.tenant_id','{ctx0['tenantId']}',true);
                                INSERT INTO workshop.administrative_bindings SELECT "Id","TenantId","OrderId","LegalEntityId","SiteId","DestinationVersion","ContractVersion","RequestedAt","OperatorId",'SimulatorV1',1,repeat('a',64)
                                FROM workshop.administrative_requests WHERE "Id"='{request_id}'; ROLLBACK;'''], cwd=ROOT, capture_output=True, text=True, timeout=20)
                            assert attempt.returncode != 0, 'historical requests MUST refuse retroactive binding assignment'
                        elif action == 'logs-safe':
                            logs = run(command+['logs', '--no-color', 'api'])
                            assert 'http://admin-simulator' not in logs and 'http://simulator-b' not in logs, 'connector URL must not appear in application logs'
                        elif action == 'traffic':
                            (state/'control/traffic.json').write_text(json.dumps({name: simulator('/control/traffic', service=service)['traffic'] for name, service in [('A','admin-simulator'),('B','simulator-b')]}))
                        elif action == 'remote-effects':
                            (state/'control/effects.json').write_text(json.dumps(simulator('/control/requests')['requests']))
                        elif action == 'wait-inflight':
                            stop = time.monotonic()+10
                            while simulator('/control/inflight')['requestId'] is None:
                                if time.monotonic() > stop: raise TimeoutError('receiver commit/inflight boundary absent')
                                time.sleep(0.05)
                        elif action.startswith('simulator:'):
                            mode = action.split(':', 1)[1]; assert mode in ('complete', 'receive', 'reject', 'unavailable', 'lost-response', 'hold-response')
                            simulator('/control/mode', json.dumps({'mode': mode}))
                        elif action == 'simulator-complete':
                            for entry in simulator('/control/requests')['requests']:
                                if entry['status'] == 'Received': simulator('/control/complete/'+entry['requestId'], '{}')
                        elif action.startswith('capability:'):
                            _, name, enabled = action.split(':'); assert name in ('external-administration', 'workshop') and enabled in ('true', 'false')
                            run(query+['-c', f"UPDATE organization_access.capability_activations SET \"Enabled\"={enabled} WHERE \"LegalEntityId\"='{ctx0['legalEntityId']}' AND \"Capability\"='{name}';"])
                        elif action.startswith('destination:'):
                            _, kind, version = action.split(':'); assert kind in ('External', 'Internal') and version.isdigit()
                            run(query+['-c', f"INSERT INTO workshop.administrative_destinations VALUES ('{ctx0['tenantId']}','{ctx0['legalEntityId']}',{int(version)},'{kind}');"])
                        elif action.startswith('admin-create:'):
                            enabled = action.split(':')[1]
                            assert enabled in ('true', 'false')
                            if enabled == 'false':
                                saved = run(query+['-c', f'''SELECT row_to_json(p) FROM organization_access.company_permissions p WHERE "MembershipId"='{fixture['adminMembershipId']}' AND "Permission"='workshop.administrative-requests.create';''']).strip()
                                assert saved
                                (state/'create-grant.json').write_text(saved)
                                run(query+['-c', f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{fixture['adminMembershipId']}' AND "Permission"='workshop.administrative-requests.create';'''])
                            else:
                                saved = (state/'create-grant.json').read_text().replace("'", "''")
                                run(query+['-c', f'''INSERT INTO organization_access.company_permissions SELECT * FROM jsonb_populate_record(NULL::organization_access.company_permissions,'{saved}'::jsonb);'''])
                        elif action.startswith('permissions:'):
                            _, name, grants = action.split(':', 2)
                            target = fixture['grantTargetMembershipId']
                            run(query+['-c', f"""DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{target}' AND "Permission" LIKE 'workshop.%' AND "Permission"<>'workshop.orders.read';"""+''.join(f"""INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{target}','{ctx0['tenantId']}','{ctx0['legalEntityId']}','{g}',NULL,NULL);""" for g in grants.split(',') if g and g != 'workshop.orders.read')])
                        elif action.startswith(('hold-order:',)):
                            lock = str(uuid.UUID(action.split(':', 1)[1]))
                            holder = subprocess.Popen(query+['-f', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
                            holders.append(holder)
                            holder.stdin.write(f"SET statement_timeout='20s'; SELECT pg_advisory_lock(hashtextextended('{lock}',0));\nSELECT pg_backend_pid();\n\\echo LOCKED\n"); holder.stdin.flush()
                            output = marker(holder, b'LOCKED').splitlines()
                            holder_pid = int([x for x in output if x.isdigit()][-1])
                        elif action.startswith('wait-order:'):
                            required = int(action.split(':')[1]); stop = time.monotonic()+10
                            while True:
                                count = int(run(query+['-c', f"SELECT count(DISTINCT w.pid) FROM pg_locks w JOIN pg_locks h ON (w.database,w.classid,w.objid,w.objsubid)=(h.database,h.classid,h.objid,h.objsubid) WHERE w.locktype='advisory' AND NOT w.granted AND h.granted AND h.pid={holder_pid}"]).strip())
                                if count >= required: break
                                if time.monotonic() > stop: raise TimeoutError('expected PostgreSQL advisory waiters absent')
                                time.sleep(0.02)
                            print(f'BARRIER observed {count} separate-connection advisory waiters', flush=True)
                        elif action == 'release-order':
                            holder.stdin.write('\\q\n'); holder.stdin.flush(); holder.stdin.close(); holder.wait(timeout=5)
                        else: raise ValueError('unknown R03.c lifecycle command')
                        print('R03C_LIFECYCLE '+action.split(':')[0], flush=True)
                        (state/'control/ack.tmp').write_text(action); (state/'control/ack.tmp').replace(state/'control/ack')
                    time.sleep(0.1)
                if process.returncode: raise RuntimeError('closure Chromium acceptance failed')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)
            result = json.loads((state/'control/result.json').read_text())
            (evidence/'result.json').write_text(json.dumps(result, indent=2))
            print('PASS R05B0 real A/B queued binding proof', flush=True)
        except BaseException:
            for item in (state/'control').glob('failure-*'): shutil.copyfile(item, evidence/item.name)
            diagnostic = subprocess.run(command+['logs', '--no-color', '--tail', '100', 'identity', 'api', 'postgres', 'admin-simulator'], cwd=ROOT, capture_output=True, text=True, timeout=20)
            text = diagnostic.stdout+diagnostic.stderr
            for key, value in values.items():
                if key.endswith(('PASSWORD', 'SECRET')): text = text.replace(value, '[redacted]')
            for user in json.loads((state/'browser.json').read_text())['users']: text = text.replace(user['password'], '[redacted]')
            (evidence/'failure-diagnostics.log').write_text(text)
            (evidence/'failure-diagnostics.log').chmod(0o600)
            print(text[-3500:], flush=True)
            raise
        finally:
            for sig in previous: signal.signal(sig, signal.SIG_IGN)
            for holder in holders:
                if holder.poll() is None:
                    holder.terminate()
                    try: holder.wait(timeout=5)
                    except subprocess.TimeoutExpired: holder.kill(); holder.wait(timeout=5)
                for stream in (holder.stdin, holder.stdout, holder.stderr):
                    if stream is not None and not stream.closed: stream.close()
            try:
                r00.cleanup(command, project)
                assert r00.inventory('volume') == before_volumes
                assert set(run(['docker', 'ps', '-q', '--no-trunc']).splitlines()) == before_running
            finally:
                for sig, handler in previous.items(): signal.signal(sig, handler)
    assert r00.inventory('volume') == before_volumes
    assert set(run(['docker', 'ps', '-q', '--no-trunc']).splitlines()) == before_running
    print('PASS R03C protected running containers and retained volumes unchanged; no ephemeral resources leaked', flush=True)


if __name__ == '__main__':
    main()
