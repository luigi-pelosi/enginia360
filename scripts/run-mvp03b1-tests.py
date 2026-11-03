#!/usr/bin/env python3
"""Private ephemeral MVP03.b.1 tests; reuses CA-trusted OIDC fixture, never a supplied target."""
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
    with tempfile.TemporaryDirectory(prefix='mvp03b1-', dir=os.environ['TMPDIR']) as directory:
        state = Path(directory)
        values = {key: secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD', 'R00_OWNER_PASSWORD', 'R00_APP_PASSWORD', 'R00_CLIENT_SECRET')}
        values.update(R00_STATE=str(state), R00_POOL_SIZE=os.environ.get('MVP03B1_POOL_SIZE', '4'), MVP02C_EVIDENCE=str(evidence))
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
        config = state / 'role-acceptance.yaml'
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
            print('MVP03B1 SQL role authorization and physical barriers', flush=True)
            testenv = dict(os.environ, PGPASSWORD=values['R00_INFRA_PASSWORD'], R00_OWNER_PASSWORD=values['R00_OWNER_PASSWORD'], R00_APP_PASSWORD=values['R00_APP_PASSWORD'])
            completed = subprocess.run(command + ['run', '--rm', '--no-deps', '-T', *mounts, '-e', 'R00_MIGRATION_TESTS=1', '-e', 'PGUSER=postgres', '-e', 'PGPASSWORD', '-e', 'R00_OWNER_USER=runtime_owner', '-e', 'R00_OWNER_PASSWORD', '-e', 'R00_APP_PASSWORD', '--entrypoint', 'python3', 'migrator', 'scripts/test-mvp03b1-roles.py', 'RoleTests', '-v'], env=testenv, cwd=ROOT, text=True, capture_output=True, timeout=240)
            (evidence / 'sql-tests.log').write_text(completed.stdout + completed.stderr + '\nexit=' + str(completed.returncode))
            print(completed.stdout + completed.stderr, flush=True)
            if completed.returncode:
                raise RuntimeError('tenant role SQL assertions failed')
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
                print('MVP02C_OWNER ' + operation + ' exact replay/readback', flush=True)
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
            browser = command + ['run', '--rm', '--no-deps', '-T', '--entrypoint', 'sh', 'browser', '-c', 'mkdir -p "$HOME/.pki/nssdb" && certutil -N -d sql:$HOME/.pki/nssdb --empty-password && certutil -A -d sql:$HOME/.pki/nssdb -n runtime-ephemeral-ca -t C,, -i /run/tls/ca.crt && exec node mvp03b1-roles.cjs']
            process = subprocess.Popen(browser, cwd=ROOT)
            deadline = time.monotonic() + 420
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError('authority browser deadline')
                request = control / 'request'
                if request.exists():
                    action = request.read_text()
                    request.unlink()
                    if action in ('grant', 'revoke'):
                        owner(action)
                    elif action == 'role-audit-readback':
                        expected = json.loads((control / 'expected.json').read_text())
                        rows = json.loads(run(query + ['-c', 'SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY "CommandId"),\'[]\') FROM organization_access.tenant_role_audit a WHERE "Outcome"=\'applied\'']))
                        assert sorted(row['CommandId'] for row in rows) == sorted(expected['commands'])
                        assert all(row['ResourceId'] == row['After']['resourceId'] and row['OccurredAt'] and row['Authority'] for row in rows)
                        assert run(query + ['-c', 'SELECT count(*) FROM organization_access.context_notes']).strip() == str(expected['notes'])
                        (evidence / 'role-sql-readback.json').write_text(json.dumps(dict(applied=rows, notes=expected['notes']), indent=2))
                        print('PASS MVP03B1 exact SQL effect/audit readback:' + str(len(rows)) + ' applied rows', flush=True)
                    else:
                        raise ValueError('unknown role acceptance control')
                    (control / 'ack').write_text(action)
                time.sleep(0.05)
            assert process.returncode == 0, 'authority Chromium failed'
            print('PASS MVP03B1 real TLS OIDC HTTP and Next SSR pool' + values['R00_POOL_SIZE'], flush=True)
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
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
    assert r00.inventory('volume') == before_volumes
    assert set(run(['docker', 'ps', '-q', '--no-trunc']).splitlines()) == before_running
    print('PASS MVP03B1 guarded cleanup; protected services and volumes unchanged', flush=True)
if __name__ == '__main__':
    main()