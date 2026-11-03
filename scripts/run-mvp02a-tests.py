#!/usr/bin/env python3
"""Private ephemeral MVP-02.a tests; reuses CA-trusted OIDC fixture, never a supplied target."""
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
run = r00.run

def write_readonly_json(path, value):
    # The reused base fixture is deliberately readonly for nonroot mounts.
    if path.exists():
        path.chmod(0o600)
    try:
        path.write_text(json.dumps(value))
    finally:
        if path.exists():
            path.chmod(0o444)


def fixtures(state, secret):
    sql, identities = r00.fixtures(state, secret)
    realm = json.loads((state / 'realm.json').read_text())
    realm['clients'][0]['protocolMappers'] = [{'name': 'untrusted-role', 'protocol': 'openid-connect', 'protocolMapper': 'oidc-hardcoded-claim-mapper', 'config': {'claim.name': 'role', 'claim.value': 'SUPER ADMIN', 'jsonType.label': 'String', 'id.token.claim': 'true', 'access.token.claim': 'true'}}]
    write_readonly_json(state / 'realm.json', realm)
    fixture = json.loads((state / 'browser.json').read_text())
    fixture['authorityIdentity'] = identities[4]
    write_readonly_json(state / 'browser.json', fixture)
    return sql, identities

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sql-only', action='store_true')
    parser.add_argument('--sql-test', default='')
    args = parser.parse_args()
    project = 'enginia360-r00b-' + secrets.token_hex(6)
    before_volumes = r00.inventory('volume')
    before_running = set(run(['docker', 'ps', '-q', '--no-trunc']).splitlines())
    with tempfile.TemporaryDirectory(prefix='mvp02a-', dir=os.environ['TMPDIR']) as directory:
        state = Path(directory)
        values = {key: secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD', 'R00_OWNER_PASSWORD', 'R00_APP_PASSWORD', 'R00_CLIENT_SECRET')}
        values.update(R00_STATE=str(state), R00_POOL_SIZE=os.environ.get('MVP02A_POOL_SIZE', '4'))
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
        command = ['docker', 'compose', '--env-file', str(envfile), '-p', project, '-f', str(r00.CONFIG)]

        def interrupted(signum, frame):
            raise KeyboardInterrupt
        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        process = None
        try:
            run(command + ['build'], timeout=600)
            run(command + ['up', '-d', '--wait', '--wait-timeout', '180', 'postgres'] + ([] if args.sql_only else ['identity']), timeout=210)
            mounts = ['-v', str(ROOT / 'scripts') + ':/runtime/scripts:ro', '-v', str(ROOT / 'database/runtime') + ':/runtime/database/runtime:ro']
            testenv = dict(os.environ, PGPASSWORD=values['R00_INFRA_PASSWORD'], R00_OWNER_PASSWORD=values['R00_OWNER_PASSWORD'], R00_APP_PASSWORD=values['R00_APP_PASSWORD'])
            print('MVP02A SQL behavioral acceptance', flush=True)
            completed = subprocess.run(command + ['run', '--rm', '--no-deps', '-T', *mounts, '-e', 'R00_MIGRATION_TESTS=1', '-e', 'PGUSER=postgres', '-e', 'PGPASSWORD', '-e', 'R00_OWNER_USER=runtime_owner', '-e', 'R00_OWNER_PASSWORD', '-e', 'R00_APP_PASSWORD', '--entrypoint', 'python3', 'migrator', 'scripts/test-mvp02a-authority.py', *([args.sql_test] if args.sql_test else ['AuthorityTests', 'OwnerInputTests']), '-v'], env=testenv, cwd=ROOT, text=True, capture_output=True, timeout=240)
            print(completed.stdout + completed.stderr, flush=True)
            if completed.returncode:
                raise RuntimeError('SQL assertions failed')
            if args.sql_only:
                return
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
                print('MVP02A_OWNER ' + operation + ' exact replay/readback', flush=True)
            run(command + ['up', '-d', 'api', 'web'], timeout=120)
            ids = run(command + ['ps', '-q']).splitlines()
            for container in json.loads(run(['docker', 'inspect', *ids])):
                host = container['HostConfig']
                assert container['Config']['User'] not in ('', '0', 'root') and host['ReadonlyRootfs'] and (host['CapDrop'] == ['ALL']) and ('no-new-privileges:true' in host['SecurityOpt']) and (not host['PortBindings']) and (host['Memory'] > 0) and (host['NanoCpus'] > 0) and (host['PidsLimit'] > 0) and (not any((m['Type'] == 'volume' for m in container['Mounts'])))
            assert json.loads(run(['docker', 'network', 'inspect', project + '_runtime']))[0]['Internal']
            browser = command + ['run', '--rm', '--no-deps', '-T', '--entrypoint', 'sh', 'browser', '-c', 'mkdir -p "$HOME/.pki/nssdb" && certutil -N -d sql:$HOME/.pki/nssdb --empty-password && certutil -A -d sql:$HOME/.pki/nssdb -n runtime-ephemeral-ca -t C,, -i /run/tls/ca.crt && exec node mvp02a-authority.cjs']
            process = subprocess.Popen(browser, cwd=ROOT)
            deadline = time.monotonic() + 240
            while process.poll() is None:
                if time.monotonic() > deadline:
                    raise TimeoutError('authority browser deadline')
                request = control / 'request'
                if request.exists():
                    action = request.read_text()
                    request.unlink()
                    if action in ('grant', 'revoke'):
                        owner(action)
                    elif action == 'binding-loss':
                        run(query, input=f"""DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{identities[4]}';""")
                    elif action == 'store-deny':
                        run(query, input='REVOKE SELECT ON organization_access.platform_authority FROM runtime_app;')
                    elif action == 'store-restore':
                        run(query, input='GRANT SELECT ON organization_access.platform_authority TO runtime_app;')
                    elif action == 'readback':
                        assert run(query + ['-c', 'SELECT count(*) FROM organization_access.platform_authority_audit']).strip() == str(revision)
                        assert run(query + ['-c', f"""SELECT count(*) FROM organization_access.memberships WHERE "IdentitySubject"='{identities[4]}' """]).strip() == '0'
                    else:
                        raise ValueError('unknown authority control')
                    (control / 'ack').write_text(action)
                time.sleep(0.05)
            assert process.returncode == 0, 'authority Chromium failed'
            print('PASS MVP02A real TLS OIDC HTTP pool' + values['R00_POOL_SIZE'], flush=True)
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
    print('PASS MVP02A guarded cleanup; protected services and volumes unchanged', flush=True)
if __name__ == '__main__':
    main()
