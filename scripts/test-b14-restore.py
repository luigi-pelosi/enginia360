#!/usr/bin/env python3
"""B14 OPE03 rehearsal: real backup, destroyed synthetic data store, measured restore and readback.

Synthetic ephemeral project only. The measurement is a rehearsal on test data, not a production
RTO or availability guarantee for the single bootstrap host.
"""
import json
import hashlib
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path


def client():
    import importlib.util
    spec = importlib.util.spec_from_file_location('b10', Path(__file__).with_name('test-b10.py'))
    assert spec and spec.loader
    b10 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b10)
    b = b10.b
    b.BASE = sys.argv[1].rstrip('/')
    action = json.load(sys.stdin)
    beta = b.b02.login(b.BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    result = {}
    entry = b.b02.request(b.BASE + '/api/v1/accounting/invoice-journal-entries/' + action['entryId'], b.alpha)
    invoice = b.b02.request(b.BASE + '/api/v1/billing/workshop-invoices/' + action['invoiceId'], b.alpha)
    external = b.b02.request(b.BASE + '/api/v1/workshop/orders/' + action['externalOrderId'] + '/closure-state', beta)
    for name, (status, value) in {'entry': entry, 'invoice': invoice, 'external': external}.items():
        assert status == 200, (name, status, value)
        result[name] = value
    print(json.dumps(result))


if len(sys.argv) > 3 and sys.argv[3] == 'client':
    client()
    raise SystemExit()

project, runtime_path = sys.argv[1], sys.argv[2]
assert project.startswith('enginia360-b14-'), 'only isolated B14 projects are authorized'
assert re.fullmatch(r'enginia360-b14-[0-9]+', project), 'exact ephemeral project required'
runtime = [json.loads(line) for line in Path(runtime_path).read_text().splitlines() if line.startswith('{')][0]
pg = project + '-postgres-1'
api = project + '-api-1'
volume = project + '_postgres_data'
image = 'python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710'
scratch = Path(sys.argv[2]).parent
dump = scratch / 'b14-backup.dump'
report = scratch.parent / (project + '-restore-measurement.json')
compose = ['docker', 'compose', '--env-file', str(scratch / 'runtime.env'), '-p', project]
# Exactly the runner overlays, ending in compose.b14-test.yaml.
for suffix in ['02','03','04','05','06','07','08','09','10','12','13','14']:
    compose += ['-f', 'compose.b' + suffix + '-test.yaml']


def run(args, **kw):
    p = subprocess.run(args, capture_output=True, text=True, timeout=kw.pop('timeout', 120), **kw)
    assert p.returncode == 0, (args[:4], p.stderr[-2000:])
    return p.stdout


def sql(text, container=None):
    p = subprocess.run(['docker', 'exec', '-i', container or pg, 'psql', '-U', 'enginia360', '-d', 'enginia360',
                        '-Atq', '-v', 'ON_ERROR_STOP=1'], input=text, text=True, capture_output=True, timeout=30)
    assert p.returncode == 0, p.stderr[-2000:]
    return p.stdout.strip()


def readback():
    p = subprocess.run(['docker', 'run', '--rm', '-i', '--label', 'com.docker.compose.project=' + project, '--network', project + '_backend',
                        '-v', str(Path.cwd()) + ':/source:ro', '-w', '/source', image,
                        'python3', 'scripts/test-b14-restore.py', 'http://web:8080', 'x', 'client'],
                       input=json.dumps(runtime), text=True, capture_output=True, timeout=90)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def persisted_state():
    tables = sql("SELECT quote_ident(n.nspname)||'.'||quote_ident(c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname IN ('organization_access','counterparties','vehicles','catalog','workshop','inventory','integrations','billing','accounting') ORDER BY 1;").splitlines()
    return {table: sql('SELECT coalesce(jsonb_agg(value ORDER BY value::text),\'[]\'::jsonb) FROM (SELECT to_jsonb(t) AS value FROM ' + table + ' t) s;') for table in tables}


before_http = readback()
before_sql_state = persisted_state()
before_state_hash = digest({'http': before_http, 'sql': before_sql_state})
source_revision = run(['git', 'rev-parse', 'HEAD']).strip()
labels = json.loads(run(['docker', 'inspect', pg]))[0]['Config']['Labels']
assert labels['com.docker.compose.project'] == project
pg_info = json.loads(run(['docker', 'inspect', pg]))[0]
assert '/var/lib/postgresql' in pg_info['HostConfig']['Tmpfs'], 'expected ephemeral tmpfs data store'
before_counts = sql("SELECT count(*) FROM accounting.journal_entries, billing.invoices;")
assert before_counts and int(before_counts) > 0, before_counts
# pg_dump does not include cluster roles. Recreate only the known non-login,
# restricted outbox policy role, never credentials or arbitrary roles.
assert sql("SELECT (NOT rolcanlogin AND NOT rolsuper AND rolbypassrls)::text FROM pg_roles WHERE rolname='enginia360_outbox_reader';") == 'true'

# 1. Backup of the synthetic database only; the dump stays in the ephemeral scratch directory.
started = time.monotonic()
with dump.open('wb') as handle:
    p = subprocess.run(['docker', 'exec', pg, 'pg_dump', '-U', 'enginia360', '-d', 'enginia360', '-Fc'],
                       stdout=handle, stderr=subprocess.PIPE, timeout=180)
assert p.returncode == 0, p.stderr[-2000:]
backup_seconds = round(time.monotonic() - started, 3)
assert dump.stat().st_size > 10_000, dump.stat().st_size
dump.chmod(0o600)

# 2. Destroy the data store exactly like losing the synthetic volume, never a retained one.
assert volume.startswith('enginia360-b14-') and volume.endswith('_postgres_data'), volume
retained = run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).split()
protected = [name for name in retained if not name.startswith('enginia360-b14-')]
dump_sha256 = hashlib.sha256(dump.read_bytes()).hexdigest()
old_container_id = run(['docker', 'inspect', '--format', '{{.Id}}', pg]).strip()
run(compose + ['stop', 'api', 'web', 'postgres'], timeout=180)
run(compose + ['rm', '-f', 'postgres'], timeout=120)
# PostgreSQL uses tmpfs: deleting the container destroys its entire data store.
assert old_container_id not in run(['docker', 'ps', '-aq', '--no-trunc']).split()
assert volume not in run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).split(), 'destroyed volume still present'

# 3. Measured recovery: fresh cluster, restore, application restart, authenticated readback.
recovery_started = time.monotonic()
run(compose + ['up', '-d', '--wait', '--wait-timeout', '180', 'postgres'], timeout=300)
new_container_id = run(['docker', 'inspect', '--format', '{{.Id}}', pg]).strip()
assert new_container_id != old_container_id
assert hashlib.sha256(dump.read_bytes()).hexdigest() == dump_sha256
assert sql("SELECT to_regnamespace('accounting') IS NULL;") == 't', 'fresh cluster already contains domain data'
sql('CREATE ROLE enginia360_outbox_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT BYPASSRLS;')
with dump.open('rb') as handle:
    p = subprocess.run(['docker', 'exec', '-i', pg, 'pg_restore', '-U', 'enginia360', '-d', 'enginia360',
                        '--clean', '--if-exists', '--exit-on-error'],
                       stdin=handle, capture_output=True, timeout=300)
assert p.returncode == 0, p.stderr[-3000:]
run(compose + ['up', '-d', '--wait', '--wait-timeout', '180', 'api', 'web'], timeout=300)
after_http = readback()
after_sql_state = persisted_state()
assert after_sql_state == before_sql_state, 'restored persisted table content differs'
recovery_seconds = round(time.monotonic() - recovery_started, 3)
after_counts = sql("SELECT count(*) FROM accounting.journal_entries, billing.invoices;")

assert after_http == before_http, 'restored application state differs from the backup state'
assert after_counts == before_counts, (before_counts, after_counts)
assert sql("SELECT pg_get_userbyid(proowner) FROM pg_proc WHERE oid='workshop.pending_administrative_outbox(integer)'::regprocedure;") == 'enginia360_outbox_reader', 'restore changed the bounded outbox function owner'
assert sql('SELECT count(*) FROM pg_class c JOIN pg_namespace s ON c.relnamespace=s.oid '
           "WHERE s.nspname IN ('accounting','billing','workshop','inventory','integrations') "
           'AND c.relkind=%s AND c.relrowsecurity AND c.relforcerowsecurity;' % "'r'") == sql(
    'SELECT count(*) FROM pg_class c JOIN pg_namespace s ON c.relnamespace=s.oid '
    "WHERE s.nspname IN ('accounting','billing','workshop','inventory','integrations') AND c.relkind='r';"), \
    'restored tables lost forced row-level security'
still_protected = [name for name in run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).split()
                   if not name.startswith('enginia360-b14-')]
assert still_protected == protected, (protected, still_protected)

report.write_text(json.dumps({
    'scope': 'Synthetic ephemeral rehearsal on test data; not a production RTO, RPO or availability guarantee',
    'project': project, 'backup_seconds': backup_seconds, 'dump_bytes': dump.stat().st_size,
    'recovery_seconds': recovery_seconds, 'restored_rows_match': True,
    'protected_volumes_unchanged': len(protected),
    'dump_sha256': dump_sha256, 'before_state_hash': before_state_hash,
    'after_state_hash': digest({'http': after_http, 'sql': after_sql_state}), 'source_revision': source_revision,
    'source_files_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path('scripts/test-b14-restore.py'), Path('scripts/run-b14-tests.sh'), Path('src/Enginia360.Api/Program.cs')]},
    'restored_tables': len(after_sql_state),
    'old_container_id': old_container_id, 'new_container_id': new_container_id,
    'counts_before': before_counts, 'counts_after': after_counts,
}, indent=2) + '\n')
dump.unlink()
print(json.dumps({'backupSeconds': backup_seconds, 'recoverySeconds': recovery_seconds}))
print('PASS B14 real backup, destroyed synthetic tmpfs data store, measured restore and authenticated readback identical to the backup state')
