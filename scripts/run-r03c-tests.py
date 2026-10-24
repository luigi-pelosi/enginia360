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
r00.CONFIG = ROOT/'compose.r03c-test.yaml'
run = r00.run
marker = r03b.marker
POOL = os.environ.get('R03C_POOL_SIZE', '4')
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
    evidence = Path(os.environ['TMPDIR'])/('r03c-evidence-pool'+POOL)
    evidence.mkdir(exist_ok=True)
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
            run(command+['up', '-d', '--wait', '--wait-timeout', '180', 'postgres', 'identity', 'admin-simulator'], timeout=210)
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

            def simulator(path, body=None):
                args = command+['exec', '-T', 'admin-simulator', 'python3', '-I', '-c', SIMULATOR_CONTROL, path] + ([body] if body is not None else [])
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
                        if action.startswith('simulator:'):
                            mode = action.split(':', 1)[1]; assert mode in ('complete', 'receive', 'reject', 'unavailable', 'lost-response')
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
            fixture = json.loads((state/'browser.json').read_text())
            print('R03C runtime checks: '+str(len(result['checks'])), flush=True)

            def scalar(statement): return run(query+['-c', statement]).strip()
            tenant = fixture['contexts'][0]['tenantId']
            # Technical closure: exactly one fact per closed order, frozen at the CommercialRevision the UI read.
            for key, revision in result['technical'].items():
                assert scalar(f'SELECT count(*)||\'/\'||min("Revision") FROM workshop.technical_closures WHERE "OrderId"=\'{result["orders"][key]}\'') == f'1/{revision}', key
            assert scalar(f'SELECT count(*) FROM workshop.technical_closures WHERE "OrderId"=\'{result["orders"]["blocked"]}\'') == '1'
            assert scalar(f'SELECT count(*) FROM workshop.administrative_requests WHERE "OrderId" IN (\'{result["orders"]["main"]}\',\'{result["orders"]["rejected"]}\',\'{result["orders"]["lost"]}\')') == '3'
            assert scalar(f'SELECT count(*) FROM workshop.administrative_outbox WHERE "RequestId" IN (\'{result["requests"]["main"]}\',\'{result["requests"]["rejected"]}\',\'{result["requests"]["lost"]}\')') == '3'
            assert scalar(f'SELECT count(*) FROM workshop.administrative_requests WHERE "OrderId" IN (\'{result["orders"]["technicalOnly"]}\',\'{result["orders"]["matrix"]}\',\'{result["orders"]["internal"]}\',\'{result["orders"]["capabilityOff"]}\',\'{result["orders"]["blocked"]}\')') == '0'
            # The pinned multigroup q6 snapshot equals what the editor showed at closure (two groups, repeated Service/Part, revision above row count).
            snapshot = json.loads(scalar(f'SELECT "Summary" FROM workshop.administrative_requests WHERE "Id"=\'{result["requests"]["main"]}\''))
            snapshot['lines'].sort(key=lambda l: l['id'])
            assert snapshot == result['mainSnapshot'] and snapshot['revision'] == result['technical']['main'] and len(snapshot['lines']) == 4 and snapshot['revision'] > 4
            assert len({l['workingGroupId'] for l in snapshot['lines']}) == 2 and result['orders']['main'] not in {l['workingGroupId'] for l in snapshot['lines']}
            assert scalar(f'SELECT "Revision"||\'/\'||"DestinationVersion"||\'/\'||"Destination" FROM workshop.administrative_requests WHERE "Id"=\'{result["requests"]["main"]}\'') == f'{result["technical"]["main"]}/14/External'
            # Business outcomes: Received/Completed delivery alone never became a Workshop outcome; one Confirmed with a stable reference.
            assert scalar(f'SELECT "Status"||\'/\'||"ExternalReference" FROM workshop.administrative_outcomes WHERE "RequestId"=\'{result["requests"]["main"]}\'') == 'Confirmed/'+result['reference']
            assert scalar(f'SELECT count(*) FROM workshop.administrative_closures WHERE "OrderId"=\'{result["orders"]["main"]}\' AND "RequestId"=\'{result["requests"]["main"]}\' AND "ExternalReference"=\'{result["reference"]}\'') == '1'
            assert scalar(f'SELECT "Status"||\'/\'||"RejectionCode" FROM workshop.administrative_outcomes WHERE "RequestId"=\'{result["requests"]["rejected"]}\'') == 'Rejected/synthetic_refusal'
            assert scalar(f'SELECT count(*) FROM workshop.administrative_closures WHERE "OrderId"=\'{result["orders"]["rejected"]}\'') == '0'
            assert scalar(f'SELECT count(*) FROM workshop.administrative_closures WHERE "TenantId"=\'{tenant}\'') == '1', 'only the Workshop-confirmed main order is administratively closed'
            assert scalar(f'SELECT count(*) FROM integrations.administrative_reconciliations WHERE "RequestId"=\'{result["requests"]["main"]}\'') == '1'
            assert scalar(f'SELECT "State" FROM integrations.administrative_dispatches WHERE "RequestId"=\'{result["requests"]["main"]}\'') == 'Completed'
            # Simulator remote effect: exactly one effect per stable request id, including the lost-response request.
            effects = {e['requestId']: e for e in simulator('/control/requests')['requests']}
            for key in ('main', 'rejected', 'lost'):
                assert effects[result['requests'][key]]['payload']['requestId'] == result['requests'][key]
            assert effects[result['requests']['lost']]['status'] == 'Completed' and effects[result['requests']['lost']]['posts'] == 1, 'status lookup, never a blind resubmission'
            assert scalar(f'SELECT "State" FROM integrations.administrative_dispatches WHERE "RequestId"=\'{result["requests"]["lost"]}\'') == 'Completed'
            # Internal path preserved: Billing claim and balanced Accounting, never an external request.
            assert scalar(f'SELECT count(*) FROM workshop.internal_billing_claims WHERE "OrderId"=\'{result["orders"]["internal"]}\'') == '1'
            assert scalar(f'SELECT "TotalDebit"=\"TotalCredit\" FROM accounting.journal_entries WHERE "Id"=\'{result["journalId"]}\'') == 't'
            # Append-only facts: the application role can neither rewrite nor delete closure facts.
            prefix = f"BEGIN; SET LOCAL ROLE runtime_app; SELECT set_config('app.tenant_id','{tenant}',true);"
            for statement in (f'UPDATE workshop.technical_closures SET "Revision"="Revision"+1 WHERE "OrderId"=\'{result["orders"]["main"]}\';',
                              f'DELETE FROM workshop.administrative_closures WHERE "OrderId"=\'{result["orders"]["main"]}\';',
                              f'UPDATE workshop.administrative_outcomes SET "Status"=\'Rejected\' WHERE "RequestId"=\'{result["requests"]["main"]}\';'):
                attempt = subprocess.run(query+['-c', prefix+statement+' ROLLBACK;'], cwd=ROOT, capture_output=True, text=True, timeout=20)
                assert attempt.returncode != 0, 'application role must not rewrite closure facts: '+statement
            run(command+['run', '--rm', '--no-deps', '-T', 'migrator'], timeout=90)
            entries = json.loads((ROOT/'database/runtime/manifest.json').read_text())
            applied = dict(row.split('|') for row in scalar("SELECT id||'|'||checksum FROM runtime_migrations.applied ORDER BY id").splitlines())
            assert applied == {e['id']: e['sha256'] for e in entries}
            print('PASS SQL closure facts/pinned snapshot/outcomes/simulator single effect/internal path/append-only/manifest checksums', flush=True)
            for screenshot in (state/'control').glob('*.png'): shutil.copyfile(screenshot, evidence/screenshot.name)
            (evidence/'result.json').write_text(json.dumps(result, indent=2))
            print('PASS R03C completed declared runtime and SQL assertions', flush=True)
        except BaseException:
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
