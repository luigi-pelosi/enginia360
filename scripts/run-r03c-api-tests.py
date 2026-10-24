#!/usr/bin/env python3
"""Bounded R03.c API-against-PostgreSQL acceptance (closure read model, grants, snapshot consistency).

Guarded ephemeral R00.a primitives only: private internal network, no published port, no retained volume."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r00a_helpers', ROOT / 'scripts/run-r00a-tests.py')
r00a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r00a)
run = r00a.run


def main():
    scratch = os.environ.get('TMPDIR')
    if not scratch:
        raise ValueError('TMPDIR must identify private ephemeral scratch')
    project = 'enginia360-r00a-' + secrets.token_hex(6)
    r00a.validate_project(project)
    before_volumes = r00a.inventory('volume')
    before_containers = set(run(['docker', 'ps', '-q', '--no-trunc'], capture=True).stdout.splitlines())
    with tempfile.TemporaryDirectory(prefix=project + '-', dir=scratch) as directory:
        state = Path(directory)
        values = {'R00_DB_NAME': 'runtime', 'R00_OWNER_USER': 'runtime_owner', 'R00_APP_USER': 'runtime_app'}
        values.update({key: secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD', 'R00_OWNER_PASSWORD', 'R00_APP_PASSWORD')})
        envfile = state / 'runtime.env'
        descriptor = os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(''.join(f'{k}={v}\n' for k, v in values.items()))
        command = ['docker', 'compose', '--env-file', str(envfile), '-p', project, '-f', str(ROOT / 'compose.r00a-test.yaml')]
        env = dict(os.environ, **values, PGPASSWORD=values['R00_INFRA_PASSWORD'])

        def interrupted(signum, frame):
            raise KeyboardInterrupt
        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            run(command + ['build'], capture=True, timeout=240)
            run(command + ['up', '-d', '--wait', '--wait-timeout', '120', 'postgres'])
            run(command + ['run', '--rm', '--no-deps', '-T', 'migrator'])
            expected = str(len(json.loads((ROOT / 'database/runtime/manifest.json').read_text())))
            applied = run(command + ['exec', '-T', 'postgres', 'psql', '-X', '-qAt', '-U', 'postgres', '-d', 'runtime', '-c',
                                     'SELECT count(*) FROM runtime_migrations.applied'], capture=True).stdout.strip()
            assert applied == expected, (applied, expected)
            image = project + '-r03c'
            run(['docker', 'build', '-f', 'r03c-api-test.Dockerfile', '-t', image, '.'], capture=True, timeout=300)
            env['R00_POOL_CONNECTION'] = f"Host=postgres;Database=runtime;Username={values['R00_APP_USER']};Password={values['R00_APP_PASSWORD']};Timeout=5"
            env['R00_POOL_ADMIN_CONNECTION'] = f"Host=postgres;Database=runtime;Username=postgres;Password={values['R00_INFRA_PASSWORD']};Timeout=5"
            run(['docker', 'run', '--rm', '--name', project + '-r03c', '--label', 'com.docker.compose.project=' + project,
                 '--label', 'com.docker.compose.project.config_files=' + str(ROOT / 'compose.r00a-test.yaml'),
                 '--network', project + '_runtime', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges:true',
                 '--memory=768m', '--cpus=1', '--pids-limit=128', '--log-opt=max-size=5m', '--log-opt=max-file=2',
                 '--tmpfs', '/tmp:rw,noexec,nosuid,size=128m,uid=1654,gid=1654',
                 '-e', 'R00_POOL_CONNECTION', '-e', 'R00_POOL_ADMIN_CONNECTION', image], env=env, timeout=240)
            print('PASS R03.c API/PostgreSQL closure acceptance', flush=True)
        finally:
            for sig in previous:
                signal.signal(sig, signal.SIG_IGN)
            try:
                r00a.cleanup(command, project)
                run(['docker', 'rmi', '-f', project + '-r03c'], capture=True)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
    assert r00a.inventory('volume') == before_volumes, 'volume inventory changed'
    assert set(run(['docker', 'ps', '-q', '--no-trunc'], capture=True).stdout.splitlines()) == before_containers, 'pre-existing running containers changed'
    print('PASS protected containers and retained volumes unchanged')


if __name__ == '__main__':
    main()
