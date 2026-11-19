"""Confronta vecchia baseline monolitica e nuova composizione, senza database live.

python3 tests/database/prove_business_partner_consolidation.py \
  --previous /percorso/before-foundation.sql --output /percorso/evidenze
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from dbbaseline import normalize_dump
from test_foundation import TABLES, table_schema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from database.sql_source import load_foundation_sql

CONTAINER = 'enginia360-bp-consolidation-proof'
SCOPE = 'business-partner-consolidation-proof'
IMAGE = 'postgres:18.6-alpine3.24@sha256:123b17998ccaf47e53b502e8c6a1e79afd8f579c6f3eec83c563da026f957395'


def docker(*args, **kwargs):
    return subprocess.run(['docker', *args], text=True, capture_output=True,
                          check=True, timeout=90, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    previous = args.previous.read_text()
    if '\\ir ' in previous or previous.count('CREATE TABLE ') != len(TABLES):
        raise ValueError('Attesa la baseline monolitica completa precedente')
    report = {'passed': False, 'image': IMAGE, 'container': CONTAINER}
    owned_id = None
    try:
        if subprocess.run(['docker', 'inspect', CONTAINER], capture_output=True).returncode == 0:
            raise RuntimeError('Nome container occupato: nessuna adozione o rimozione')
        owned_id = docker('run', '--detach', '--name', CONTAINER,
            '--label', 'enginia360.scope=' + SCOPE, '--network', 'none',
            '--read-only', '--user', 'postgres', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', '512m', '--cpus', '1',
            '--pids-limit', '128', '--shm-size', '64m',
            '--tmpfs', '/var/lib/postgresql:rw,noexec,nosuid,size=256m,uid=70,gid=70',
            '--tmpfs', '/var/run/postgresql:rw,noexec,nosuid,size=8m,uid=70,gid=70',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m,uid=70,gid=70',
            '--tmpfs', '/proof:rw,noexec,nosuid,size=8m,uid=70,gid=70',
            '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', IMAGE).stdout.strip()
        for _ in range(160):
            ready = subprocess.run(['docker', 'exec', CONTAINER, 'pg_isready', '-U', 'postgres'], capture_output=True)
            if ready.returncode == 0 and 'PostgreSQL init process complete' in docker('logs', CONTAINER).stdout:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('PostgreSQL non pronto')
        info = json.loads(docker('inspect', CONTAINER).stdout)[0]
        assert info['HostConfig']['NetworkMode'] == 'none' and not info['HostConfig']['PortBindings']
        assert info['HostConfig']['ReadonlyRootfs'] and all(m['Type'] == 'tmpfs' for m in info['Mounts'])
        (args.output / 'container.json').write_text(json.dumps(info, indent=2) + '\n')

        def sql(database, source):
            return docker('exec', '-i', CONTAINER, 'psql', '-X', '-qAt', '-U', 'postgres',
                          '-d', database, '-v', 'ON_ERROR_STOP=1', input=source).stdout.strip()

        sql('postgres', 'CREATE ROLE enginia360_app NOLOGIN; CREATE ROLE enginia360_proof_login LOGIN IN ROLE enginia360_app;')
        for database in ('before', 'after', 'stdin', 'phase2', 'enginia360'):
            docker('exec', CONTAINER, 'createdb', '-U', 'postgres', database)
        sql('before', previous)
        for filename in ('foundation.sql', 'masterdata_business_partner.sql'):
            docker('exec', '-i', CONTAINER, 'tee', '/proof/' + filename,
                   input=(ROOT / 'database' / filename).read_text())
        docker('exec', '-w', '/', CONTAINER, 'psql', '-X', '-qAt', '-U', 'postgres',
               '-d', 'after', '-v', 'ON_ERROR_STOP=1', '-f', '/proof/foundation.sql')
        expanded = load_foundation_sql()
        sql('stdin', expanded)
        sql('phase2', expanded)
        dumps = {}
        for database in ('before', 'after', 'stdin'):
            raw = docker('exec', CONTAINER, 'pg_dump', '-U', 'postgres', '-d', database,
                         '--schema-only', '--schema=foundation', '--schema=masterdata').stdout
            (args.output / (database + '-schema.sql')).write_text(raw)
            dumps[database] = normalize_dump(raw)
        delta = ''.join(difflib.unified_diff(dumps['before'].splitlines(True), dumps['after'].splitlines(True)))
        (args.output / 'schema.diff').write_text(delta)
        assert dumps['before'] == dumps['after'] == dumps['stdin'], 'Differenza semantica pg_dump: consultare schema.diff'
        expected = sorted(table_schema(name) + '.' + name for name in TABLES)
        inventory = sql('after', "SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('foundation','masterdata') ORDER BY 1").splitlines()
        assert inventory == expected and len(inventory) == 33
        assert all(sql('after', 'SELECT count(*) FROM ' + '.'.join('"'+part+'"' for part in table.split('.'))) == '0' for table in inventory)
        # Prove runtime esistenti, esplicitamente indirizzate al solo cluster effimero.
        import os
        env = dict(os.environ, BP_PHASE2_DATABASE_PROOF='1', BP_PHASE2_DATABASE_CONTAINER=CONTAINER,
                   ENGINIA360_BASELINE_PROOF='1', PYTHONPATH=str(ROOT / 'tests/database'))
        runtime = subprocess.run([sys.executable, 'backend/tests/business_partner_phase2_database_test.py'],
                                 cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
        (args.output / 'phase2-tests.log').write_text(runtime.stdout + runtime.stderr)
        assert runtime.returncode == 0 and 'Ran 5 tests' in runtime.stderr
        sql('enginia360', expanded)
        modules = ['test_foundation', 'test_optional_code_schema', 'test_commercial_organizations',
                   'test_required_site_addresses', 'test_site_classification', 'test_site_addresses',
                   'test_dbbaseline', 'test_portable_baseline', 'test_business_partner_source']
        command = ("import dbbaseline, unittest; "
                   f"dbbaseline.CONTAINER={CONTAINER!r}; dbbaseline.SCOPE={SCOPE!r}; "
                   f"suite=unittest.defaultTestLoader.loadTestsFromNames({modules!r}); "
                   "result=unittest.TextTestRunner(verbosity=2).run(suite); "
                   "raise SystemExit(not result.wasSuccessful())")
        core = subprocess.run([sys.executable, '-c', command], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=180)
        (args.output / 'core-tests.log').write_text(core.stdout + core.stderr)
        assert core.returncode == 0, 'Invarianti baseline fallite: consultare core-tests.log'
        report.update(passed=True, tables=inventory, table_count=len(inventory), zero_rows=True,
                      canonical_dump_sha256=hashlib.sha256(dumps['after'].encode()).hexdigest(),
                      normalization='Solo versioni pg_dump e nonce restrict/unrestrict; owner, ACL, vincoli, commenti e attributi funzione invariati',
                      file_and_stdin_equivalent=True, phase2_runtime_tests=5)
    finally:
        if owned_id:
            current = json.loads(docker('inspect', CONTAINER).stdout)[0]
            if current['Id'] != owned_id or current['Config']['Labels'].get('enginia360.scope') != SCOPE:
                raise RuntimeError('Cleanup rifiutato: identità o label differenti')
            docker('rm', '--force', owned_id)
            report['cleanup_absent'] = subprocess.run(['docker', 'inspect', CONTAINER], capture_output=True).returncode != 0
        (args.output / 'proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
