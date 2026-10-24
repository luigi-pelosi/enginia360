#!/usr/bin/env python3
"""R06.b.1 opt-in EPHEMERAL current-runtime restore rehearsal (synthetic data, single host).

Cluster A is populated only through existing authorized APIs, dumped (custom format), really destroyed,
and a fresh cluster B (different system_identifier, infrastructure roles only) is restored from the archive.
Timings are a synthetic ephemeral single-host measurement: NOT RPO/RTO/SLA/PITR/off-host/disaster-recovery evidence.
The runner accepts no target (project, endpoint, container, volume) from its caller.
"""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


lib = load('r06b1_restore', 'scripts/r06b1_restore.py')
r03b = load('r03b_donor', 'scripts/run-r03b-tests.py')
r00 = r03b.r00
CONFIG = ROOT/'compose.r06b1-test.yaml'
r00.CONFIG = CONFIG  # the guarded cleanup primitive now only accepts this runner's own compose file
run = r00.run
assert_ephemeral_project = lib.assert_ephemeral_project
assert_exact_targets = lib.assert_exact_targets
assert_empty_target = lib.assert_empty_target
verify_dump = lib.verify_dump
HOLD = os.environ.get('R06B1_HOLD', '')  # lifecycle-probe hook: keeps one real child alive until TERM
if HOLD not in ('', 'browser', 'dump', 'restore'):
    raise ValueError('unknown lifecycle hold')


class Rig:
    """Everything the runner created; all destructive operations derive from these registered objects."""

    def __init__(self, project, state, command, values, protected):
        self.project, self.state, self.command, self.values, self.protected = project, state, command, values, protected
        self.query = command + ['exec', '-T', 'postgres', 'psql', '-X', '-qAt', '-U', 'postgres', '-d', 'runtime', '-v', 'ON_ERROR_STOP=1']
        self.children = []
        self.marks = {}
        self.timings = {}
        self.evidence = {'checks': []}
        self.fixture = None

    @contextlib.contextmanager
    def phase(self, name):
        started = time.monotonic()
        try:
            yield
        finally:
            self.timings[name] = round(time.monotonic() - started, 3)

    def check(self, name):
        self.evidence['checks'].append(name)
        print('PASS R06B1 ' + name, flush=True)


def sql(rig, statement):
    return run(rig.query + ['-c', statement]).strip()


def attempt(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, capture_output=True, timeout=kwargs.pop('timeout', 90), **kwargs)


def container_ids(rig, service=None):
    args = rig.command + ['ps', '-aq'] + ([service] if service else [])
    return run(args).split()


def inspect(ids):
    return json.loads(run(['docker', 'inspect', *ids])) if ids else []


def system_identifier(rig):
    return sql(rig, 'SELECT system_identifier FROM pg_control_system()')


def target_summary(rig):
    relations = int(sql(rig, "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND c.relkind IN ('r','p','v','m','S','f')"))
    ledger = sql(rig, "SELECT to_regclass('runtime_migrations.applied') IS NOT NULL") == 't'
    schemas = sql(rig, "SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN ('information_schema','public') ORDER BY 1").splitlines()
    return {'domain_relations': relations, 'ledger_present': ledger, 'schemas': schemas}


def ledger_rows(rig):
    rows = sql(rig, "SELECT id||'|'||checksum||'|'||applied_at::text FROM runtime_migrations.applied ORDER BY id").splitlines()
    return [tuple(row.split('|')) for row in rows]


def snapshot_tables(rig):
    """Dynamic per-table count + sha256 over EVERY discovered table in one read-only REPEATABLE READ snapshot."""
    names = sql(rig, lib.discovery_sql()).splitlines()
    script = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;\nSET TimeZone='UTC'; SET DateStyle='ISO,YMD';\n"
    script += ''.join(lib.table_digest_sql(name) + ';\n' for name in names) + 'COMMIT;\n'
    result = {}
    for line in run(rig.query, input=script).splitlines():
        if '|' in line:
            name, rows, digest = line.split('|')
            result[name] = {'rows': int(rows), 'sha256': digest}
    if sorted(result) != sorted(names):
        raise RuntimeError('snapshot did not cover every discovered table')
    return result


def snapshot_fingerprints(rig):
    return {category: sql(rig, statement) for category, statement in lib.FINGERPRINT_SQL.items()}


def fingerprint_rows(rig, categories):
    return {category: sql(rig, lib.FINGERPRINT_ROWS_SQL[category]).splitlines() for category in categories}


def expected_tables():
    inventory = load('r06_inventory_runtime', 'scripts/r06_inventory.py')
    return set(inventory.definitions(ROOT/'database/runtime/manifest.json')) | {'runtime_migrations.applied'}


def protected_state():
    names = ('enginia360-api-1', 'enginia360-web-1')
    state = {}
    for item in json.loads(run(['docker', 'inspect', *names])) if all(run(['docker', 'ps', '-q', '--filter', 'name=^' + n + '$']).strip() for n in names) else []:
        state[item['Name']] = (item['Id'], item['State']['StartedAt'], item['RestartCount'])
    return {'volumes': r00.inventory('volume'), 'running': set(run(['docker', 'ps', '-q', '--no-trunc']).splitlines()),
            'all': set(run(['docker', 'ps', '-aq', '--no-trunc']).splitlines()), 'bootstrap': state}


def harden_check(rig):
    ids = container_ids(rig)
    assert_exact_targets(inspect(ids), rig.project, CONFIG, protected_ids=tuple(rig.protected['running']))
    network = json.loads(run(['docker', 'network', 'inspect', rig.project + '_runtime']))[0]
    assert network['Internal']


def hold_until_term(marker):
    print('R06B1_LIFECYCLE ' + marker, flush=True)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        time.sleep(0.2)
    raise TimeoutError('lifecycle probe was never terminated')


def start_holder(rig, statement):
    holder = subprocess.Popen(rig.query + ['-f', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    rig.children.append(holder)
    holder.stdin.write(statement + '\nSELECT pg_backend_pid();\n\\echo LOCKED\n')
    holder.stdin.flush()
    r03b.marker(holder, b'LOCKED')
    return holder


def run_browser(rig, phase):
    """One real Chromium run (new browser, no state shared with earlier phases) bounded by a monotonic deadline."""
    process = subprocess.Popen(rig.command + ['run', '--rm', '--no-deps', '-T', '-e', 'R06B1_PHASE=' + phase, 'browser'], cwd=ROOT)
    rig.children.append(process)
    deadline = time.monotonic() + 280
    try:
        held = HOLD == 'browser' and phase == 'seed'
        if held:
            start_holder(rig, "SELECT pg_advisory_lock(hashtextextended('r06b1:probe',0));")
            time.sleep(8)
            hold_until_term('hold-browser')
        while process.poll() is None:
            if time.monotonic() > deadline:
                raise TimeoutError('browser phase deadline: ' + phase)
            time.sleep(0.2)
        if process.returncode:
            raise RuntimeError('Chromium phase failed: ' + phase)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def stop_children(rig):
    for child in rig.children:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream is not None and not stream.closed:
                with contextlib.suppress(Exception):
                    stream.close()
    rig.children.clear()


def apply_migrator(rig, extra=()):
    return attempt(rig.command + ['run', '--rm', '--no-deps', '-T'] + list(extra) + ['migrator'], timeout=120)


def populate_cluster(rig):
    """A: init-only roles -> real migrator on the exact manifest -> fixtures -> real browser/API commands."""
    command, state = rig.command, rig.state
    manifest = json.loads((ROOT/'database/runtime/manifest.json').read_text())
    with rig.phase('A_init_only'):
        run(command + ['up', '-d', '--wait', '--wait-timeout', '180', 'postgres', 'identity'], timeout=210)
        summary = target_summary(rig)
        assert summary == {'domain_relations': 0, 'ledger_present': False, 'schemas': []}, 'init-only cluster must have no domain relations or ledger'
        rig.evidence['A'] = {'container': container_ids(rig, 'postgres')[0], 'system_identifier': system_identifier(rig)}
        rig.evidence['roles_init'] = snapshot_fingerprints(rig)['roles']
        rig.check('A is init-only: roles/ACL only, zero domain relations, no ledger')
    with rig.phase('A_migrate'):
        assert apply_migrator(rig).returncode == 0
        ledger = ledger_rows(rig)
        assert [(row[0], row[1]) for row in ledger] == [(e['id'], e['sha256']) for e in manifest], 'ledger must be the exact current manifest'
        empty = snapshot_tables(rig)
        assert set(empty) == expected_tables(), 'discovered tables differ from the manifest inventory + ledger'
        assert all(v['rows'] == 0 for name, v in empty.items() if name != 'runtime_migrations.applied')
        assert apply_migrator(rig).returncode == 0
        assert ledger_rows(rig) == ledger, 'second apply must be a no-op including applied_at'
        rig.evidence['manifest_units'] = len(manifest)
        rig.evidence['tables'] = len(empty)
        rig.check('real migrator applied exactly %d manifest units; %d tables discovered dynamically, all empty; second apply no-op' % (len(manifest), len(empty)))
    with rig.phase('A_fixtures_services'):
        run(rig.query, input=rig.values['fixture_sql'])
        run(command + ['up', '-d', 'api', 'web'], timeout=120)
        harden_check(rig)
        rig.check('hardened ephemeral topology: nonroot/read-only/cap_drop, no host ports or volumes, internal network')
    with rig.phase('A_populate_via_apis'):
        run_browser(rig, 'seed')
        seeded = json.loads((state/'control/seed.json').read_text())
        rig.evidence['seed'] = seeded
        rig.check('cluster A populated only through authorized APIs (%d recorded receipts)' % len(seeded['receipts']))


def quiesce(rig):
    run(rig.command + ['stop', 'api', 'web'], timeout=90)
    deadline = time.monotonic() + 15
    while sql(rig, "SELECT count(*) FROM pg_stat_activity WHERE usename='runtime_app'") != '0':
        if time.monotonic() > deadline:
            raise TimeoutError('application connections still open')
        time.sleep(0.2)
    first = snapshot_tables(rig)
    time.sleep(2)
    assert snapshot_tables(rig) == first, 'database not quiescent'
    rig.check('API/web stopped, zero application backends, two snapshots identical (quiescent)')


def baseline(rig):
    seeded = rig.evidence['seed']
    rig.baseline = {'tables': snapshot_tables(rig), 'ledger': ledger_rows(rig), 'fingerprints': snapshot_fingerprints(rig)}
    rig.baseline['fingerprint_rows'] = fingerprint_rows(rig, lib.FINGERPRINT_SQL)
    assert set(rig.baseline['tables']) == expected_tables()
    marker = seeded['ids']['markerOrder']
    assert sql(rig, f'SELECT count(*) FROM workshop.orders WHERE "Id"=\'{marker}\'') == '1'
    lib.check_markers(pre_present=True, post_present=False)
    rig.check('SQL baseline: %d tables, %d ledger rows, %d catalog fingerprints, pre-dump marker present' % (len(rig.baseline['tables']), len(rig.baseline['ledger']), len(rig.baseline['fingerprints'])))


def dump_cluster(rig):
    path = rig.state/'dumps'/'rehearsal.dump'
    path.parent.mkdir(mode=0o700, exist_ok=True)
    argv = rig.command + ['exec', '-T', 'postgres'] + lib.dump_argv()
    holder = None
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as out:
        if HOLD == 'dump':
            holder = start_holder(rig, "BEGIN; LOCK TABLE runtime_migrations.applied IN ACCESS EXCLUSIVE MODE;")
        process = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=subprocess.PIPE)
        rig.children.append(process)
        if holder is not None:
            deadline = time.monotonic() + 30
            while sql(rig, "SELECT count(*) FROM pg_stat_activity WHERE application_name='pg_dump' AND wait_event_type='Lock'") == '0':
                if time.monotonic() > deadline:
                    raise TimeoutError('pg_dump never blocked on the held lock')
                time.sleep(0.2)
            hold_until_term('hold-dump')
        _, stderr = process.communicate(timeout=120)
    if process.returncode:
        raise RuntimeError('pg_dump failed: ' + stderr.decode()[-500:])
    payload = path.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    listing = subprocess.run(rig.command + ['exec', '-T', 'postgres', 'pg_restore', '--list'], cwd=ROOT, input=payload, capture_output=True, timeout=60)
    assert listing.returncode == 0, 'pg_restore --list rejected the archive'
    toc = listing.stdout.decode()
    verify_dump(path, sha, toc)
    for table in rig.baseline['tables']:
        schema, name = table.split('.')
        assert re.search(r'TABLE DATA %s %s ' % (re.escape(schema.strip('"')), re.escape(name.strip('"'))), toc), 'TOC lacks data for ' + table
    rig.dump = {'path': path, 'sha256': sha, 'bytes': len(payload), 'toc_entries': len([l for l in toc.splitlines() if l and not l.startswith(';')])}
    rig.evidence['dump'] = {'sha256': sha, 'bytes': len(payload), 'toc_entries': rig.dump['toc_entries'], 'mode': '0600', 'location': 'outside PGDATA, private scratch'}
    # Corrupt and truncated COPIES must be detected; the pristine archive is never modified.
    detected = []
    for label, damaged in (('truncated', payload[:-4096]), ('bit-flip', payload[:2000] + bytes([payload[2000] ^ 0xFF]) + payload[2001:])):
        copy = rig.state/'dumps'/(label + '.dump')
        copy.write_bytes(damaged)
        copy.chmod(0o600)
        try:
            verify_dump(copy, sha, toc)
        except ValueError:
            detected.append(label)
        tool = subprocess.run(rig.command + ['exec', '-T', 'postgres', 'pg_restore', '--file=/dev/null'], cwd=ROOT, input=damaged, capture_output=True, timeout=60)
        rig.evidence['dump'][label + '_pg_restore_rc'] = tool.returncode
        copy.unlink()
    assert detected == ['truncated', 'bit-flip']
    rig.check('binary custom-format dump: sha256 %s, %d bytes, TOC covers every table; corrupt/truncated copies detected' % (sha[:12], len(payload)))


def post_dump_marker(rig):
    run(rig.command + ['start', 'api', 'web'], timeout=120)
    run_browser(rig, 'marker2')
    marker = json.loads((rig.state/'control/marker2.json').read_text())['order']
    rig.post_marker = marker
    assert sql(rig, f'SELECT count(*) FROM workshop.orders WHERE "Id"=\'{marker}\'') == '1'
    run(rig.command + ['stop', 'api', 'web'], timeout=90)
    after = snapshot_tables(rig)
    assert lib.compare_table_snapshots(rig.baseline['tables'], after), 'post-dump marker must make A differ from the dump'
    rig.check('post-dump marker committed in A after the dump (must be absent after restore)')


def destroy_cluster(rig):
    ids = container_ids(rig, 'postgres')
    assert len(ids) == 1
    containers = inspect(ids)
    assert_exact_targets(containers, rig.project, CONFIG, protected_ids=tuple(rig.protected['running']))
    assert not [m for m in containers[0]['Mounts'] if m['Type'] == 'volume'] and not containers[0]['HostConfig']['PortBindings']
    assert ids[0] == rig.evidence['A']['container'] or ids[0].startswith(rig.evidence['A']['container'][:12])
    assert not container_ids(rig, 'api') or all(not c['State']['Running'] for c in inspect(container_ids(rig, 'api')))
    run(['docker', 'rm', '-f', ids[0]], timeout=60)
    remaining = run(['docker', 'ps', '-aq', '--no-trunc']).split()
    assert ids[0] not in remaining, 'cluster A container still exists'
    assert not run(['docker', 'volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + rig.project]).strip()
    rig.evidence['A']['destroyed_container'] = ids[0]
    rig.marks['destroyed'] = time.monotonic()
    rig.check('cluster A container and tmpfs PGDATA really destroyed; no volume remains')


def fresh_cluster(rig):
    run(rig.command + ['up', '-d', '--wait', '--wait-timeout', '120', '--no-deps', 'postgres'], timeout=150)
    new = container_ids(rig, 'postgres')
    assert len(new) == 1 and new[0] != rig.evidence['A']['container'], 'cluster B must be a new container'
    b_id = system_identifier(rig)
    assert b_id != rig.evidence['A']['system_identifier'], 'cluster B must have a different system_identifier'
    summary = target_summary(rig)
    assert_empty_target(summary)
    fingerprints = snapshot_fingerprints(rig)
    assert fingerprints['roles'] == rig.baseline['fingerprints']['roles'], 'roles must come from the infrastructure bootstrap, identical to A'
    assert fingerprints['database'] == rig.baseline['fingerprints']['database']
    rig.evidence['B'] = {'container': new[0], 'system_identifier': b_id, 'pre_restore': summary}
    harden_check(rig)
    rig.check('cluster B is a new cluster (system_identifier %s != %s), infrastructure roles only, zero domain relations' % (b_id, rig.evidence['A']['system_identifier']))


def restore_cluster(rig):
    assert_empty_target(target_summary(rig))
    path = rig.dump['path']
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == rig.dump['sha256'], 'archive changed before restore'
    # While B is half-built nothing else may migrate it: hold the engine's own advisory lock for the whole restore.
    guard = start_holder(rig, "SELECT pg_advisory_lock(hashtextextended('enginia360.runtime_migrations.v1', 0));")
    process = subprocess.Popen(rig.command + ['exec', '-T', 'postgres'] + lib.restore_argv(), cwd=ROOT, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rig.children.append(process)
    process.stdin.write(payload[:4096])
    process.stdin.flush()
    if HOLD == 'restore':
        hold_until_term('hold-restore')
    stdout, stderr = process.communicate(input=payload[4096:], timeout=240)
    guard.stdin.write('\\q\n')
    guard.stdin.flush()
    guard.wait(timeout=10)
    if process.returncode:
        raise RuntimeError('pg_restore failed: ' + stderr.decode()[-1500:])
    rig.evidence['restore'] = {'exit_code': 0, 'flags': lib.restore_argv()[1:]}
    # A second restore into the now non-empty B must be refused before it starts.
    try:
        assert_empty_target(target_summary(rig))
    except ValueError:
        pass
    else:
        raise AssertionError('non-empty B was not refused')
    rig.check('pg_restore (--exit-on-error --single-transaction) exit 0; a second restore into non-empty B is refused')


def compare_cold(rig):
    after = {'tables': snapshot_tables(rig), 'ledger': ledger_rows(rig), 'fingerprints': snapshot_fingerprints(rig)}
    problems = (lib.compare_table_snapshots(rig.baseline['tables'], after['tables']) + lib.compare_ledger(rig.baseline['ledger'], after['ledger'])
                + lib.compare_fingerprints(rig.baseline['fingerprints'], after['fingerprints']))
    if problems:
        for problem in problems:
            if problem.startswith('fingerprint:'):
                category = problem.split(':', 1)[1]
                diff = json.dumps(lib.diff_rows(rig.baseline['fingerprint_rows'][category], fingerprint_rows(rig, [category])[category]))
                evidence = Path(os.environ['TMPDIR'])/'r06b1-evidence'
                evidence.mkdir(exist_ok=True)
                (evidence/('fingerprint-diff-' + category + '.json')).write_text(diff)
                print('FINGERPRINT %s %s' % (category, diff[:1500]), flush=True)
        raise AssertionError('cold comparison failed: ' + ', '.join(problems[:20]))
    seeded = rig.evidence['seed']
    pre = sql(rig, f'SELECT count(*) FROM workshop.orders WHERE "Id"=\'{seeded["ids"]["markerOrder"]}\'') == '1'
    post = sql(rig, f'SELECT count(*) FROM workshop.orders WHERE "Id"=\'{rig.post_marker}\'') != '0'
    lib.check_markers(pre_present=pre, post_present=post)
    rig.cold = after
    rig.evidence['cold_comparison'] = {'tables': len(after['tables']), 'rows': sum(v['rows'] for v in after['tables'].values()),
                                       'ledger_rows': len(after['ledger']), 'fingerprint_categories': sorted(after['fingerprints'])}
    rig.check('cold comparison: %d tables count+sha256 identical, ledger id/checksum/applied_at identical, %d catalog fingerprints identical, pre marker present, post-dump marker absent' % (len(after['tables']), len(after['fingerprints'])))


def migrator_noop(rig):
    for attempt_number in (1, 2):
        result = apply_migrator(rig)
        assert result.returncode == 0, result.stderr.decode()[-500:]
        assert ledger_rows(rig) == rig.baseline['ledger'], 'migrator mutated the restored ledger'
        assert snapshot_tables(rig) == rig.baseline['tables'], 'migrator mutated restored data'
    rig.check('real migrator on B is a verified no-op twice (ledger and every table unchanged)')


def restart_services(rig, pool=None):
    if pool is None:
        run(rig.command + ['start', 'api', 'web'], timeout=120)
        return
    envfile = rig.state/'runtime.env'
    envfile.write_text(re.sub(r'R00_POOL_SIZE=\d+', 'R00_POOL_SIZE=' + pool, envfile.read_text()))
    run(rig.command + ['up', '-d', '--no-deps', '--force-recreate', 'api'], timeout=120)
    run(rig.command + ['restart', 'web'], timeout=60)


def rls_checks(rig):
    fixture = rig.fixture
    a, f = fixture['contexts'][0]['tenantId'], fixture['contexts'][1]['tenantId']
    admin, other = fixture['adminMembershipId'], fixture['grantTargetMembershipId']
    expected = {
        'orders_a': sql(rig, f'SELECT count(*) FROM workshop.orders WHERE "TenantId"=\'{a}\''),
        'orders_f': sql(rig, f'SELECT count(*) FROM workshop.orders WHERE "TenantId"=\'{f}\''),
        'own_admin': sql(rig, f'SELECT count(*) FROM workshop.own_actual_time_entries WHERE "TenantId"=\'{a}\' AND "MembershipId"=\'{admin}\''),
        'own_other': sql(rig, f'SELECT count(*) FROM workshop.own_actual_time_entries WHERE "TenantId"=\'{a}\' AND "MembershipId"=\'{other}\'')}
    assert int(expected['orders_a']) > 0 and int(expected['orders_f']) > 0 and expected['own_admin'] == '1' and expected['own_other'] == '1'
    def tx(tenant=None, actor=None, query='SELECT 1'):
        body = 'BEGIN;'
        if tenant:
            body += f"SELECT set_config('app.tenant_id','{tenant}',true);"
        if actor:
            body += f"SELECT set_config('app.workshop_actor_membership_id','{actor}',true);"
        return body + f'SELECT {query};COMMIT;\n'
    orders, own = 'count(*) FROM workshop.orders', 'count(*) FROM workshop.own_actual_time_entries'
    # One physical backend, as with a pool of size 1: context must reset at every commit.
    steps = [('role', None, None, None), ('noctx_orders', None, None, orders), ('a_orders', a, None, orders), ('after_commit_orders', None, None, orders),
             ('f_orders', f, None, orders), ('a_own_admin', a, admin, own), ('a_own_other', a, other, own), ('a_own_noactor', a, None, own),
             ('f_own_admin', f, admin, own), ('after_own', None, None, own)]
    script = "SELECT 'role='||current_user||'|super='||rolsuper||'|bypass='||rolbypassrls FROM pg_roles WHERE rolname=current_user;\n"
    for label, tenant, actor, query in steps[1:]:
        script += tx(tenant, actor, f"'{label}='||(SELECT {query})") if tenant else f"SELECT '{label}='||(SELECT {query});\n"
    result = run(rig.command + ['exec', '-T', 'postgres', 'psql', '-X', '-qAt', '-U', 'runtime_app', '-d', 'runtime', '-v', 'ON_ERROR_STOP=1'], input=script)
    values = dict(line.split('=', 1) for line in result.splitlines() if '=' in line and not line.startswith('role='))
    assert result.splitlines()[0] == 'role=runtime_app|super=false|bypass=false', result.splitlines()[0]
    assert values['noctx_orders'] == '0' and values['after_commit_orders'] == '0' and values['after_own'] == '0', values
    assert values['a_orders'] == expected['orders_a'] and values['f_orders'] == expected['orders_f'], values
    assert values['a_own_admin'] == '1' and values['a_own_other'] == '1' and values['a_own_noactor'] == '0' and values['f_own_admin'] == '0', values
    for forbidden in ('INSERT INTO runtime_migrations.applied VALUES (\'x\',repeat(\'a\',64))', 'UPDATE runtime_migrations.applied SET checksum=checksum',
                      'DELETE FROM runtime_migrations.applied', 'TRUNCATE runtime_migrations.applied', 'SET ROLE runtime_owner', 'CREATE TABLE public.escape(a int)'):
        denied = attempt(rig.command + ['exec', '-T', 'postgres', 'psql', '-X', '-qAt', '-U', 'runtime_app', '-d', 'runtime', '-v', 'ON_ERROR_STOP=1', '-c', forbidden])
        assert denied.returncode != 0, 'runtime_app must be denied: ' + forbidden
    assert sql(rig, 'SELECT count(*) FROM runtime_migrations.applied') == str(len(rig.baseline['ledger']))
    rig.check('real runtime_app (not superuser, not BYPASSRLS): tenant/own-time RLS per transaction, context reset on one backend, ledger read-only, no role escalation')


@contextlib.contextmanager
def paused_dispatcher(rig):
    """Scratch-only gate at Claim's unconditional INSERT, before any retry UPDATE.

    AdministrativeDispatcher.Claim always executes INSERT ... ON CONFLICT DO NOTHING
    first, including for existing RequestIds. PostgreSQL checks INSERT permission even
    on a conflict. No product configuration, migration, payload or retry state changes.
    SELECT and column UPDATE permissions are untouched. Fail closed on privilege drift.
    """
    harden_check(rig)
    assert sql(rig, "SELECT count(*) FROM pg_stat_activity WHERE usename='runtime_app'") == '0'
    acl = snapshot_fingerprints(rig)['acl']
    privilege = "SELECT has_table_privilege('runtime_app','integrations.administrative_dispatches','INSERT')"
    assert sql(rig, privilege) == 't'
    sql(rig, 'REVOKE INSERT ON integrations.administrative_dispatches FROM runtime_app')
    try:
        assert sql(rig, privilege) == 'f', 'dispatcher INSERT remains possible via another grant'
        # Real conflict-path statement: must fail before it could mutate even an existing row.
        denied = attempt(rig.command + ['exec', '-T', 'postgres', 'psql', '-X', '-qAt', '-U', 'runtime_app', '-d', 'runtime', '-v', 'ON_ERROR_STOP=1', '-c',
                         'INSERT INTO integrations.administrative_dispatches SELECT * FROM integrations.administrative_dispatches LIMIT 0 ON CONFLICT DO NOTHING'])
        assert denied.returncode != 0 and b'permission denied for table administrative_dispatches' in denied.stderr
        assert snapshot_tables(rig) == rig.baseline['tables'], 'pause changed persisted content'
        rig.evidence['dispatcher_pause'] = {'gate': 'scratch-only REVOKE INSERT at unconditional Claim INSERT', 'denied_exit': denied.returncode,
                                            'strict_all_columns': True, 'product_configuration_changed': False}
        rig.check('actual dispatcher INSERT gate denied to runtime_app before service restart; all table content unchanged')
        yield
    finally:
        # authorized_readback stops both services before returning; cleanup still runs on failure.
        run(rig.command + ['stop', 'api', 'web'], timeout=90)
        sql(rig, 'GRANT INSERT ON integrations.administrative_dispatches TO runtime_app')
        assert sql(rig, privilege) == 't'
        assert snapshot_fingerprints(rig)['acl'] == acl, 'temporary dispatcher gate did not restore the exact ACL'
        rig.check('temporary dispatcher gate removed; exact pre-gate ACL restored')


def authorized_readback(rig):
    expected = {k: rig.evidence['seed'][k] for k in ('ids', 'receipts', 'baseline')}
    (rig.state/'control/expected.json').write_text(json.dumps(expected))
    for pool in ('4', '1'):
        if pool == '1':
            restart_services(rig, pool='1')
        with rig.phase('readback_pool' + pool):
            run_browser(rig, 'readback')
            rls_checks(rig)
        rig.check('authorized HTTP readback with API pool size %s: projection, receipts, own-time isolation, release history' % pool)
        if pool == '4':
            rig.marks['usable'] = time.monotonic()
    run(rig.command + ['stop', 'api', 'web'], timeout=90)
    final = snapshot_tables(rig)
    changed = lib.compare_table_snapshots(rig.baseline['tables'], final)
    rig.evidence['post_readback_delta'] = changed
    assert not changed, 'readback/replay changed persisted state: ' + ', '.join(changed)
    assert ledger_rows(rig) == rig.baseline['ledger']
    rig.check('readback and exact replays changed no row, count or column in ANY table; dispatcher paused; ledger unchanged')


def fault_injection(rig):
    """Scratch-manifest-only failure: published files and the ledger prefix are never modified."""
    prefix = ledger_rows(rig)
    tables = snapshot_tables(rig)
    root = rig.state/'scratch-manifests'
    root.mkdir(exist_ok=True)

    def apply_scratch(directory):
        return attempt(rig.command + ['run', '--rm', '--no-deps', '-T', '-v', str(directory) + ':/scratch:ro', 'migrator', '--manifest', '/scratch/manifest.json'], timeout=120)
    n = len(prefix)
    fail_dir = root/'fail'
    lib.build_scratch_manifest(ROOT/'database/runtime', fail_dir, [('scratch_fault', 'CREATE TABLE public.scratch_probe(a int); INSERT INTO public.scratch_probe VALUES (1); SELECT 1/0;'),
                                                                   ('scratch_sentinel', 'CREATE TABLE public.scratch_sentinel(a int);')])
    failed = apply_scratch(fail_dir)
    assert failed.returncode != 0, 'the injected SQL failure must fail the engine'
    assert ledger_rows(rig) == prefix, 'ledger prefix changed after the failed unit'
    assert sql(rig, "SELECT to_regclass('public.scratch_probe') IS NULL AND to_regclass('public.scratch_sentinel') IS NULL") == 't', 'failed unit leaked DDL or the sentinel ran'
    assert sql(rig, "SELECT count(*) FROM pg_locks WHERE locktype='advisory'") == '0', 'advisory lock not released'
    assert snapshot_tables(rig) == tables
    rig.check('injected scratch failure: engine exit %d, unit rolled back, ledger prefix (%d rows incl. applied_at) intact, sentinel not run, lock released' % (failed.returncode, n))
    fix_dir = root/'fix'
    lib.build_scratch_manifest(ROOT/'database/runtime', fix_dir, [('scratch_forward_fix', 'CREATE TABLE public.scratch_probe(a int); INSERT INTO public.scratch_probe VALUES (1);'),
                                                                  ('scratch_sentinel', 'CREATE TABLE public.scratch_sentinel(a int);')])
    assert apply_scratch(fix_dir).returncode == 0
    fixed = ledger_rows(rig)
    assert fixed[:n] == prefix and len(fixed) == n + 2
    append_dir = root/'append'
    lib.build_scratch_manifest(ROOT/'database/runtime', append_dir, [('scratch_forward_fix', 'CREATE TABLE public.scratch_probe(a int); INSERT INTO public.scratch_probe VALUES (1);'),
                                                                     ('scratch_sentinel', 'CREATE TABLE public.scratch_sentinel(a int);'),
                                                                     ('scratch_append_only', 'CREATE TABLE public.scratch_appended(a int);')])
    assert apply_scratch(append_dir).returncode == 0
    appended = ledger_rows(rig)
    assert appended[:n + 2] == fixed and len(appended) == n + 3
    assert apply_scratch(append_dir).returncode == 0 and ledger_rows(rig) == appended, 'append-only forward fix second apply must be a no-op'
    # Drift in the published prefix is refused before any new DDL on a disposable copy of the manifest.
    drift = root/'drift'
    lib.build_scratch_manifest(ROOT/'database/runtime', drift, [('scratch_after_drift', 'CREATE TABLE public.scratch_must_not_exist(a int);')])
    document = json.loads((drift/'manifest.json').read_text())
    document[0]['sha256'] = '0' * 64
    drift.chmod(0o755)
    (drift/'manifest.json').chmod(0o644)
    (drift/'manifest.json').write_text(json.dumps(document))
    refused = apply_scratch(drift)
    assert refused.returncode != 0 and sql(rig, "SELECT to_regclass('public.scratch_must_not_exist') IS NULL") == 't'
    assert ledger_rows(rig) == appended
    # The pre-failure archive is still intact and its ledger is exactly the published prefix.
    verify_dump(rig.dump['path'], rig.dump['sha256'], 'x')
    listing = subprocess.run(rig.command + ['exec', '-T', 'postgres', 'pg_restore', '--data-only', '--table=applied', '--schema=runtime_migrations', '--file=-'],
                             cwd=ROOT, input=rig.dump['path'].read_bytes(), capture_output=True, timeout=60).stdout.decode()
    archived = [tuple(line.split('\t')) for line in re.search(r'COPY runtime_migrations\.applied \(id, checksum, applied_at\) FROM stdin;\n(.*?)\n\\\.', listing, re.S).group(1).splitlines()]
    assert [(r[0], r[1]) for r in sorted(archived)] == [(r[0], r[1]) for r in prefix], 'pre-failure dump ledger differs from the published prefix'
    rig.evidence['fault_injection'] = {'published_prefix_rows': n, 'failed_exit': failed.returncode, 'forward_fix_rows': len(fixed), 'append_rows': len(appended),
                                       'drift_refused_exit': refused.returncode, 'dump_ledger_rows': len(archived)}
    rig.check('forward-fix scratch units applied append-only (+2, +1), second apply no-op, checksum drift refused, pre-failure dump ledger == published prefix')


def write_report(rig, started):
    total = time.monotonic() - started
    usable = rig.marks['usable'] - rig.marks['destroyed']
    timings = dict(rig.timings, total_rehearsal=round(total, 3), recovery_after_destruction_to_usable_http=round(usable, 3))
    print(lib.timing_report(timings), flush=True)
    report = dict(rig.evidence, label=lib.LABEL, disclaimer=lib.DISCLAIMER, timings=timings,
                  baseline_tables={k: v for k, v in rig.baseline['tables'].items()}, ledger_rows=len(rig.baseline['ledger']),
                  protected_before={k: sorted(v) if isinstance(v, set) else v for k, v in rig.protected.items()})
    report['seed'] = {k: v for k, v in rig.evidence['seed'].items() if k in ('checks',)}
    directory = Path(os.environ['TMPDIR'])/'r06b1-evidence'
    directory.mkdir(exist_ok=True)
    (directory/'report.json').write_text(json.dumps(report, indent=2, default=str))
    (directory/'report.json').chmod(0o600)


def main():
    if not os.environ.get('TMPDIR'):
        raise ValueError('private TMPDIR required')
    if not (ROOT/'web/dist-ui01-runtime/ui01-runtime.html').exists():
        raise ValueError('build:ui01-runtime required')
    project = 'enginia360-r00b-' + secrets.token_hex(6)
    assert_ephemeral_project(project)
    started = time.monotonic()
    protected = protected_state()
    with tempfile.TemporaryDirectory(prefix=project + '-', dir=os.environ['TMPDIR']) as directory:
        state = Path(directory)
        values = {key: secrets.token_hex(24) for key in ('R00_INFRA_PASSWORD', 'R00_OWNER_PASSWORD', 'R00_APP_PASSWORD', 'R00_CLIENT_SECRET')}
        envfile = state/'runtime.env'
        envfile.write_text(''.join(k + '=' + v + '\n' for k, v in dict(values, R00_STATE=str(state), R00_POOL_SIZE='4').items()))
        envfile.chmod(0o600)
        run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1', '-subj', '/CN=Ephemeral R06 CA', '-addext', 'basicConstraints=critical,CA:TRUE',
             '-keyout', str(state/'ca.key'), '-out', str(state/'ca.crt')])
        (state/'ca.key').chmod(0o600)
        (state/'public').mkdir()
        (state/'public/ca.crt').write_bytes((state/'ca.crt').read_bytes())
        for service, host, uid in [('postgres', 'postgres', 70), ('api', 'api.r00.test', 1654), ('web', 'app.r00.test', 101), ('identity', 'idp.r00.test', 1000)]:
            r00.certificate(state, service, host, uid)
        (state/'postgres/pg_hba.conf').write_text('local all all trust\nhostnossl all all all reject\nhostssl all all all scram-sha-256\n')
        os.environ['R03B_POOL_SIZE'] = '4'
        fixture_sql = r03b.fixtures(state, values['R00_CLIENT_SECRET'])
        fixture = json.loads((state/'browser.json').read_text())
        ctx = fixture['contexts'][0]
        for action in ('reservations.read', 'reservations.release'):
            fixture_sql += f"\nINSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{fixture['adminMembershipId']}','{ctx['tenantId']}','{ctx['legalEntityId']}','inventory.{action}','{ctx['siteId']}','{ctx['warehouseId']}');"
        (state/'control').mkdir()
        (state/'control').chmod(0o777)
        command = ['docker', 'compose', '--env-file', str(envfile), '-p', project, '-f', str(CONFIG)]
        rig = Rig(project, state, command, dict(values, fixture_sql=fixture_sql), protected)
        rig.fixture = fixture

        def interrupted(signum, frame):
            raise KeyboardInterrupt

        previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            if not HOLD:
                with rig.phase('real_postgres_comparison_guards'):
                    run([sys.executable, 'scripts/test-r06b1-guards.py', '--actual'], timeout=120)
                rig.check('real PostgreSQL CHECK/ACL and strict readback mutation regressions executed')
            with rig.phase('build'):
                run(command + ['build'], timeout=480)
            populate_cluster(rig)
            with rig.phase('quiesce'):
                quiesce(rig)
            with rig.phase('baseline'):
                baseline(rig)
            with rig.phase('dump'):
                dump_cluster(rig)
            with rig.phase('post_dump_marker'):
                post_dump_marker(rig)
            with rig.phase('destroy_A'):
                destroy_cluster(rig)
            with rig.phase('fresh_B'):
                fresh_cluster(rig)
            with rig.phase('restore_B'):
                restore_cluster(rig)
            with rig.phase('compare_cold'):
                compare_cold(rig)
            with rig.phase('migrator_noop'):
                migrator_noop(rig)
            with paused_dispatcher(rig):
                with rig.phase('restart_services'):
                    restart_services(rig)
                authorized_readback(rig)
            with rig.phase('fault_injection'):
                fault_injection(rig)
            write_report(rig, started)
            print('PASS R06B1 completed (synthetic ephemeral single-host measurement; not RPO/RTO/SLA/PITR/DR evidence)', flush=True)
        except BaseException:
            try:
                diagnostics = subprocess.run(command + ['logs', '--no-color', '--tail', '40', 'api', 'postgres', 'identity'], cwd=ROOT, capture_output=True, timeout=30).stdout.decode()
                for value in values.values():
                    diagnostics = diagnostics.replace(value, '[redacted]')
                print(re.sub(r'(https?://[^?\s]+)\?[^\s]*', r'\1?[redacted]', diagnostics)[-3500:], flush=True)
            except Exception:
                pass
            raise
        finally:
            for sig in previous:
                signal.signal(sig, signal.SIG_IGN)
            try:
                stop_children(rig)
                r00.cleanup(command, project)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
    after = protected_state()
    assert after == protected, 'protected inventory (volumes, containers, bootstrap start times) changed'
    print('PASS R06B1 protected running/all containers, 25 retained volumes and bootstrap StartedAt/RestartCount unchanged; no ephemeral resource leaked', flush=True)


if __name__ == '__main__':
    main()
