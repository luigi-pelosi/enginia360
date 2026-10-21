#!/usr/bin/env python3
"""Bounded R00.a acceptance. No supplied project/target and no persistent volume."""
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def validate_project(project):
    if not re.fullmatch(r'enginia360-r00a-[0-9a-f]{12}', project):
        raise ValueError('refusing non-ephemeral R00.a target')


def run(args, *, env=None, capture=False, timeout=180):
    return subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=capture,
                          check=True, timeout=timeout)


def inventory(kind):
    return set(run(['docker', kind, 'ls', '-q'], capture=True).stdout.splitlines())


def cleanup(command, project):
    validate_project(project)
    ids = run(['docker', 'ps', '-aq', '--filter', f'label=com.docker.compose.project={project}'], capture=True).stdout.splitlines()
    if ids:
        for container in json.loads(run(['docker', 'inspect', *ids], capture=True).stdout):
            labels = container['Config']['Labels']
            if labels.get('com.docker.compose.project') != project or labels.get('com.docker.compose.project.config_files') != str(ROOT / 'compose.r00a-test.yaml'):
                raise ValueError('cleanup target label/config mismatch')
        run(['docker', 'rm', '-f', *ids], capture=True, timeout=60)
    run(command + ['down', '--volumes', '--remove-orphans'], capture=True, timeout=60)
    for kind, args in [('container', ['ps', '-aq']), ('network', ['network', 'ls', '-q']), ('volume', ['volume', 'ls', '-q'])]:
        if run(['docker', *args, '--filter', f'label=com.docker.compose.project={project}'], capture=True).stdout.strip():
            raise RuntimeError(f'R00.a {kind} leaked after cleanup')


def main():
    scratch = os.environ.get('TMPDIR')
    if not scratch:
        raise ValueError('TMPDIR must identify private ephemeral scratch')
    project = 'enginia360-r00a-' + secrets.token_hex(6)
    validate_project(project)
    before_volumes = inventory('volume')
    before_containers = set(run(['docker', 'ps', '-q', '--no-trunc'], capture=True).stdout.splitlines())
    with tempfile.TemporaryDirectory(prefix=project+'-', dir=scratch) as directory:
        state = Path(directory)
        values = {'R00_DB_NAME': 'runtime', 'R00_OWNER_USER': 'runtime_owner', 'R00_APP_USER': 'runtime_app'}
        values.update({key: secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD','R00_OWNER_PASSWORD','R00_APP_PASSWORD')})
        envfile = state / 'runtime.env'
        descriptor = os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(''.join(f'{key}={value}\n' for key, value in values.items()))
        command = ['docker', 'compose', '--env-file', str(envfile), '-p', project, '-f', str(ROOT / 'compose.r00a-test.yaml')]
        env = dict(os.environ, **values, PGPASSWORD=values['R00_INFRA_PASSWORD'])
        def interrupted(signum, frame):
            raise KeyboardInterrupt
        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            run(command + ['build'], capture=True, timeout=240)
            run(command + ['up', '-d', '--wait', '--wait-timeout', '120', 'postgres'])
            container = run(command + ['ps', '-q', 'postgres'], capture=True).stdout.strip()
            config = json.loads(run(['docker', 'inspect', container], capture=True).stdout)[0]
            host = config['HostConfig']
            assert config['Config']['User'] == '70:70' and host['ReadonlyRootfs']
            assert host['CapDrop'] == ['ALL'] and 'no-new-privileges:true' in host['SecurityOpt']
            assert host['Memory'] > 0 and host['NanoCpus'] > 0 and host['PidsLimit'] > 0
            assert host['LogConfig']['Config'] == {'max-file':'2','max-size':'5m'}
            assert not host['PortBindings'] and not any(m['Type']=='volume' for m in config['Mounts'])
            assert '/var/lib/postgresql' in host['Tmpfs']
            network = json.loads(run(['docker','network','inspect',project+'_runtime'],capture=True).stdout)[0]
            assert network['Internal']
            for _ in range(2):
                run(command + ['run', '--rm', '--no-deps', '-T', 'migrator'])
            query = ['exec','-T','postgres','psql','-X','-qAt','-U','postgres','-d','runtime','-v','ON_ERROR_STOP=1','-c']
            assert run(command+query+["SELECT count(*) FROM runtime_migrations.applied"],capture=True).stdout.strip() == '14'
            assert run(command+query+["SHOW data_directory"],capture=True).stdout.strip() == '/var/lib/postgresql/18/docker'
            run(command + ['run', '--rm', '--no-deps', '-T', '--entrypoint', 'python3',
                '-e', 'R00_MIGRATION_TESTS=1', '-e', 'PGUSER=postgres', '-e', 'PGPASSWORD',
                '-e', 'R00_OWNER_USER', '-e', 'R00_OWNER_PASSWORD', '-e', 'R00_APP_PASSWORD',
                'migrator', 'scripts/test-r00-migrations.py', '-v'], env=env)
            pool_image = project + '-pool'
            run(['docker', 'build', '-f', 'runtime-pool-test.Dockerfile', '-t', pool_image, '.'], capture=True, timeout=240)
            env['R00_POOL_CONNECTION'] = f"Host=postgres;Database=runtime;Username={values['R00_APP_USER']};Password={values['R00_APP_PASSWORD']};Timeout=5"
            env['R00_POOL_ADMIN_CONNECTION'] = f"Host=postgres;Database=runtime;Username=postgres;Password={values['R00_INFRA_PASSWORD']};Timeout=5"
            run(['docker','run','--rm','--name',project+'-pool','--label','com.docker.compose.project='+project,
                 '--label','com.docker.compose.project.config_files='+str(ROOT/'compose.r00a-test.yaml'),
                 '--network',project+'_runtime','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
                 '--memory=768m','--cpus=1','--pids-limit=128','--log-opt=max-size=5m','--log-opt=max-file=2',
                 '--tmpfs','/tmp:rw,noexec,nosuid,size=128m,uid=1654,gid=1654',
                 '-e','R00_POOL_CONNECTION','-e','R00_POOL_ADMIN_CONNECTION',pool_image],env=env,timeout=120)
            run(command + ['stop', 'postgres'])
            run(command + ['up', '-d', '--wait', '--wait-timeout', '120', 'postgres'])
            run(command + ['run', '--rm', '--no-deps', '-T', 'migrator'])
            assert run(command+query+["SELECT count(*) FROM runtime_migrations.applied"],capture=True).stdout.strip() == '14'
            logs = run(command + ['logs', '--no-color', 'postgres'], capture=True).stdout
            for key in ('R00_INFRA_PASSWORD','R00_OWNER_PASSWORD','R00_APP_PASSWORD'):
                assert values[key] not in logs, 'secret found in server log'
        finally:
            for sig in previous:
                signal.signal(sig, signal.SIG_IGN)
            try:
                cleanup(command, project)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
    assert inventory('volume') == before_volumes, 'volume inventory changed'
    assert set(run(['docker','ps','-q','--no-trunc'],capture=True).stdout.splitlines()) == before_containers, 'pre-existing running containers changed'
    print('PASS R00.a PostgreSQL migrations, lifecycle, hardening and guarded cleanup; protected containers/volumes unchanged.')


if __name__ == '__main__':
    main()
