#!/usr/bin/env python3
"""Actual PostgreSQL staging proof. No opt-in skips: this file always runs a real DB."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'scripts/run-r06a2-tests.py'


def load(name):
    path = ROOT/'scripts'/name
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name.replace('.py', ''), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


synth = load('r06_synthetic.py')
guards = load('r06b1_restore.py')


def command(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=60, **kwargs).stdout.strip()


def protected():
    ids = command(['docker', 'ps', '-aq', '--no-trunc']).split()
    items = json.loads(command(['docker', 'inspect', *ids])) if ids else []
    return {'containers': sorted((x['Id'], x['State']['StartedAt'], x['RestartCount'], x['State']['Status']) for x in items),
            'volumes': sorted(command(['docker', 'volume', 'ls', '-q']).split())}


class Fixture:
    """Isolated staging schema only. Never installs any application migration."""
    def __enter__(self):
        self.before = protected()
        self.name = 'enginia360-r00b-' + secrets.token_hex(6)
        guards.assert_ephemeral_project(self.name)
        image = (ROOT/'postgres.runtime.Dockerfile').read_text().splitlines()[0].split()[1]
        self.id = command(['docker', 'run', '-d', '--name', self.name, '--network', 'none', '--user', '70:70', '--read-only',
                          '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--memory', '512m', '--cpus', '1',
                          '--pids-limit', '128', '--log-opt', 'max-size=5m', '--log-opt', 'max-file=2',
                          '--label', 'com.docker.compose.project=' + self.name,
                          '--label', 'com.docker.compose.project.config_files=' + str(CONFIG),
                          '--tmpfs', '/var/lib/postgresql:rw,noexec,nosuid,size=256m,uid=70,gid=70,mode=0700',
                          '--tmpfs', '/var/run/postgresql:rw,noexec,nosuid,size=8m,uid=70,gid=70',
                          '-e', 'PGDATA=/var/lib/postgresql/18/docker', '-e', 'POSTGRES_DB=r06a2_staging',
                          '-e', 'POSTGRES_HOST_AUTH_METHOD=trust', image])
        try:
            deadline = time.monotonic() + 45
            while True:
                try:
                    self.sql('SELECT 1;')
                    break
                except subprocess.CalledProcessError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.2)
            self.guard()
            self.sql('''CREATE SCHEMA r06a2_staging;
CREATE TABLE r06a2_staging.source (source_id text PRIMARY KEY, payload jsonb NOT NULL);
CREATE TABLE r06a2_staging.configuration (singleton boolean PRIMARY KEY CHECK(singleton), value jsonb NOT NULL);
CREATE TABLE r06a2_staging.batches (
 source_system text NOT NULL, batch_id text NOT NULL, revision integer NOT NULL,
 hash text NOT NULL, header jsonb NOT NULL, imported_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(source_system,batch_id,revision));
CREATE TABLE r06a2_staging.imported (
 source_system text NOT NULL, batch_id text NOT NULL, revision integer NOT NULL,
 source_id text NOT NULL, internal_id text NOT NULL, batch_hash text NOT NULL, payload jsonb NOT NULL,
 PRIMARY KEY(source_system,batch_id,revision,source_id), UNIQUE(source_system,batch_id,revision,internal_id),
 FOREIGN KEY(source_system,batch_id,revision) REFERENCES r06a2_staging.batches);
CREATE TABLE r06a2_staging.audit (
 source_system text NOT NULL, batch_id text NOT NULL, revision integer NOT NULL, hash text NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(source_system,batch_id,revision),
 FOREIGN KEY(source_system,batch_id,revision) REFERENCES r06a2_staging.batches);''')
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def argv(self):
        return ['docker', 'exec', '-i', self.id, 'psql', '-X', '-qAt', '-U', 'postgres', '-d', 'r06a2_staging', '-v', 'ON_ERROR_STOP=1']

    def guard(self):
        item = json.loads(command(['docker', 'inspect', self.id]))[0]
        guards.assert_exact_targets([item], self.name, CONFIG, protected_ids=[v[0] for v in self.before['containers']])
        assert item['HostConfig']['NetworkMode'] == 'none'
        assert item['HostConfig']['Memory'] > 0 and item['HostConfig']['NanoCpus'] > 0 and item['HostConfig']['PidsLimit'] > 0

    def sql(self, statement):
        return command(self.argv(), input=statement)

    def __exit__(self, *args):
        self.guard()
        command(['docker', 'rm', '-f', self.id])
        assert not command(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + self.name])
        assert protected() == self.before, 'protected container IDs/StartedAt/restarts/status or retained volumes changed'
        print('PASS R06A2 exact cleanup and protected inventory unchanged', flush=True)


def literal(value):
    return "convert_from(decode('" + json.dumps(value, separators=(',', ':')).encode().hex() + "','hex'),'UTF8')::jsonb"


class Storage(unittest.TestCase):
    fixture = None

    def setUp(self):
        self.db = self.fixture
        self.db.sql('TRUNCATE r06a2_staging.audit,r06a2_staging.imported,r06a2_staging.batches,r06a2_staging.source,r06a2_staging.configuration;')
        self.dataset = synth.generate(7)
        # Accepted V1 discount remains scale2; all other decimals are canonical q6.
        for row in self.dataset['records']:
            for key in synth.NUMBERS:
                row[key] = format(synth.number(row[key]), '.2f' if key == 'discount_percent' else '.6f')
            self.db.sql('INSERT INTO r06a2_staging.source VALUES (' + "'" + row['source_id'] + "'," + literal(row) + ');')
        self.tool = load('r06a2_storage.py')

    def export(self):
        self.assertIsNotNone(self.tool, 'stored-source exporter / transactional importer missing')
        return self.tool.export_source(self.db.sql)

    def configure(self, envelope):
        self.db.sql('INSERT INTO r06a2_staging.configuration VALUES (true,' + literal(envelope['context']) + ');')

    def snapshot(self):
        return self.db.sql("SELECT jsonb_build_array((SELECT jsonb_agg(t) FROM r06a2_staging.batches t), (SELECT jsonb_agg(t) FROM r06a2_staging.imported t), (SELECT jsonb_agg(t) FROM r06a2_staging.audit t));")

    def test_02_exact_replay_no_extra_rows_or_audit(self):
        envelope = self.export()
        self.configure(envelope)
        payload = synth.canonical(envelope)
        self.tool.import_bytes(self.db.sql, payload)
        before = self.snapshot()
        error = None
        try:
            self.tool.import_bytes(self.db.sql, payload)
        except Exception as ex:
            error = type(ex).__name__
        self.assertIsNone(error, 'exact replay must be accepted without writes')
        self.assertEqual(self.snapshot(), before, 'including audit timestamps and row contents')
        self.assertEqual(self.db.sql('SELECT count(*) FROM r06a2_staging.audit;'), '1')
        print('PASS R06A2 exact replay: imported=8 batches=1 audit=1 timestamps unchanged', flush=True)

    def test_03_changed_content_under_same_key_refused_atomically(self):
        envelope = self.export()
        self.configure(envelope)
        self.tool.import_bytes(self.db.sql, synth.canonical(envelope))
        before = self.snapshot()
        changed = copy.deepcopy(envelope)
        changed['dataset']['records'][-1]['net_amount'] = '90.260000'
        changed['sha256'] = synth.digest({k: v for k, v in changed.items() if k != 'sha256'})
        with self.assertRaisesRegex(ValueError, 'refused'):
            self.tool.import_bytes(self.db.sql, synth.canonical(changed))
        self.assertEqual(self.snapshot(), before)
        print('PASS R06A2 conflicting replay refused atomically; full target/audit unchanged', flush=True)

    def test_04_invalid_input_rejected_before_any_storage_call(self):
        envelope = self.export()
        self.configure(envelope)
        before = self.snapshot()
        calls = []

        def counting(statement):
            calls.append(statement)
            return self.db.sql(statement)
        bad = []
        for field, value in (('format', 'R06A2_STAGING_ONLY_V2'),):
            bad.append(dict(copy.deepcopy(envelope), **{field: value}))
        numeric = copy.deepcopy(envelope)
        numeric['dataset']['records'][0]['quantity'] = '1e2'
        bad.append(numeric)
        for document in bad:
            document['sha256'] = synth.digest({k: v for k, v in document.items() if k != 'sha256'})
            with self.assertRaises(ValueError):
                self.tool.import_bytes(counting, synth.canonical(document))
        with self.assertRaises(ValueError):
            self.tool.import_bytes(counting, b'{' + b' ' * 2_000_001 + b'}')
        self.assertEqual(calls, [], 'untrusted input must be rejected before the first storage statement')
        self.assertEqual(self.snapshot(), before)
        print('PASS R06A2 unsupported version/numeric/oversize rejected with zero storage statements', flush=True)

    def test_05_scope_or_authority_mismatch_with_target_configuration_is_held_without_writes(self):
        envelope = self.export()
        payload = synth.canonical(envelope)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'refused'):
            self.tool.import_bytes(self.db.sql, payload)  # target has no configured scope/authority: never infer one
        self.assertEqual(self.snapshot(), before)
        for label, context in (('missing scope', dict(envelope['context'], scopes=envelope['context']['scopes'][:-1])),
                               ('foreign scope', dict(envelope['context'], scopes=envelope['context']['scopes'] + [dict(envelope['context']['scopes'][0], scope_id=synth.PREFIX + 'OTHER')])),
                               ('other authority', dict(envelope['context'], authority='ERP_AUTHORITATIVE'))):
            with self.subTest(label):
                self.db.sql('TRUNCATE r06a2_staging.configuration; INSERT INTO r06a2_staging.configuration VALUES (true,' + literal(context) + ');')
                with self.assertRaisesRegex(ValueError, 'refused'):
                    self.tool.import_bytes(self.db.sql, payload)
                self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.db.sql('SELECT count(*) FROM r06a2_staging.configuration;'), '1', 'refusal never switches configuration')
        print('PASS R06A2 absent/different configured scope or authority refused; no automatic switch, zero writes', flush=True)

    # REGRESSIONS 06-09: written after the implementation; they passed against unchanged code and are not RED evidence.
    def test_06_fault_after_partial_writes_rolls_back_whole_batch(self):
        envelope = self.export()
        self.configure(envelope)
        before = self.snapshot()
        self.db.sql('''CREATE FUNCTION r06a2_staging.fixture_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'FIXTURE_FAULT'; END $$;
CREATE TRIGGER fixture_fault BEFORE INSERT ON r06a2_staging.audit FOR EACH ROW EXECUTE FUNCTION r06a2_staging.fixture_fault();''')
        try:
            with self.assertRaisesRegex(ValueError, 'refused'):
                self.tool.import_bytes(self.db.sql, synth.canonical(envelope))
        finally:
            self.db.sql('DROP TRIGGER fixture_fault ON r06a2_staging.audit; DROP FUNCTION r06a2_staging.fixture_fault();')
        self.assertEqual(self.snapshot(), before, 'batch and 8 imported rows were written before the fault and must be rolled back')
        self.tool.import_bytes(self.db.sql, synth.canonical(envelope))
        self.assertEqual(self.db.sql('SELECT count(*) FROM r06a2_staging.imported;'), '8')
        print('PASS R06A2 fixture-only audit fault after batch+8 row inserts: zero rows remain; clean retry imports 8', flush=True)

    def test_07_imported_rows_trace_source_identity_batch_revision_and_hash(self):
        envelope = self.export()
        self.configure(envelope)
        self.tool.import_bytes(self.db.sql, synth.canonical(envelope))
        rows = self.db.sql("SELECT count(*) FROM r06a2_staging.imported WHERE source_system=" + "'" + envelope['source_system'] + "'" +
                           " AND batch_id='" + envelope['batch_id'] + "' AND revision=1 AND batch_hash='" + envelope['sha256'] +
                           "' AND source_id=payload->>'source_id' AND internal_id=payload->>'internal_id';")
        self.assertEqual(rows, '8')
        self.assertEqual(self.db.sql("SELECT hash FROM r06a2_staging.batches;"), envelope['sha256'])
        schemas = self.db.sql("SELECT string_agg(DISTINCT n.nspname,',' ORDER BY n.nspname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind IN ('r','p') AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema';")
        self.assertEqual(schemas, 'r06a2_staging', 'no production domain/ledger table exists or was written')
        tables = self.db.sql("SELECT string_agg(c.relname,',' ORDER BY c.relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname='r06a2_staging';")
        self.assertEqual(tables, 'audit,batches,configuration,imported,source', 'no stock-event/document table is created')
        print('PASS R06A2 8 imported rows carry source_system/batch/revision/source_id/hash; only staging schema tables exist', flush=True)

    def test_08_target_tampering_is_caught_by_existing_reconciler_per_record(self):
        envelope = self.export()
        self.configure(envelope)
        self.tool.import_bytes(self.db.sql, synth.canonical(envelope))
        self.db.sql("UPDATE r06a2_staging.imported SET payload=jsonb_set(jsonb_set(payload,'{net_amount}','\"74.260000\"'),'{physical_stock}','\"4.000001\"') WHERE source_id=payload->>'source_id' AND source_id=(SELECT min(source_id) FROM r06a2_staging.imported);")
        exported = self.tool.export_target(self.db.sql, envelope)
        report = load('r06_reconcile.py').compare(envelope['dataset'], exported['dataset'])
        self.assertFalse(report['ok'])
        self.assertEqual([d['delta'] for d in report['physical_stock_delta']], ['1.000000'])
        self.assertEqual(len(report['amount_delta']), 1)
        self.assertEqual(report['matched'], 8)
        print('PASS R06A2 stored target tamper reported by r06_reconcile: amount_delta=1 physical_stock_delta=1.000000', flush=True)

    def test_09_simultaneous_identical_imports_write_once(self):
        import threading
        envelope = self.export()
        self.configure(envelope)
        payload = synth.canonical(envelope)
        results = []
        barrier = threading.Barrier(4)

        def worker():
            barrier.wait()
            try:
                self.tool.import_bytes(self.db.sql, payload)
                results.append('ok')
            except Exception as error:
                results.append(type(error).__name__)
        threads = [threading.Thread(target=worker) for _ in range(4)]
        [t.start() for t in threads]
        [t.join(60) for t in threads]
        self.assertEqual(results, ['ok'] * 4)
        self.assertEqual(self.db.sql('SELECT (SELECT count(*) FROM r06a2_staging.batches)||\'/\'||(SELECT count(*) FROM r06a2_staging.imported)||\'/\'||(SELECT count(*) FROM r06a2_staging.audit);'), '1/8/1')
        print('PASS R06A2 four simultaneous identical imports on separate backends: batches=1 imported=8 audit=1', flush=True)

    def test_01_actual_stored_source_target_roundtrip(self):
        self.assertEqual(self.db.sql('SELECT count(*) FROM r06a2_staging.source;'), '8')
        envelope = self.export()
        self.db.sql('INSERT INTO r06a2_staging.configuration VALUES (true,' + literal(envelope['context']) + ');')
        self.tool.import_bytes(self.db.sql, synth.canonical(envelope))
        exported = self.tool.export_target(self.db.sql, envelope)
        report = load('r06_reconcile.py').compare(envelope['dataset'], exported['dataset'])
        self.assertTrue(report['ok'], report)
        self.assertEqual(report['counts']['target'], 8)
        self.assertEqual(self.db.sql('SELECT count(*) FROM r06a2_staging.imported;'), '8')
        self.assertEqual(exported, envelope)
        print('PASS R06A2 stored source=8 imported=8 reconciliation matched=8; provenance/amounts/physical/reserved equal', flush=True)


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    with Fixture() as fixture:
        Storage.fixture = fixture
        if os.environ.get('R06A2_HOLD') == '1':  # lifecycle probe: keep the live database until TERM
            print('R06A2_LIFECYCLE hold', flush=True)
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                time.sleep(.2)
            raise TimeoutError('lifecycle probe was never terminated')
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Storage))
    return 0 if result.wasSuccessful() else 1

if __name__ == '__main__':
    raise SystemExit(main())
