#!/usr/bin/env python3
"""Offline R06.b.1 guard behaviors (no Docker). Each failure mode must fail closed."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT/path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lib = load('r06b1_restore', 'scripts/r06b1_restore.py')
PROJECT = 'enginia360-r00b-0123456789ab'
CONFIG = str(ROOT/'compose.r06b1-test.yaml')


def container(**override):
    value = {'Id': 'a' * 64, 'Name': '/' + PROJECT + '-postgres-1',
             'Config': {'User': '70:70', 'Labels': {'com.docker.compose.project': PROJECT,
                                                    'com.docker.compose.project.config_files': CONFIG}},
             'HostConfig': {'ReadonlyRootfs': True, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges:true'],
                            'PortBindings': {}, 'Memory': 1, 'NanoCpus': 1, 'PidsLimit': 1},
             'Mounts': [{'Type': 'bind'}], 'State': {'Paused': False}}
    for key, replacement in override.items():
        target = value
        parts = key.split('__')
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = replacement
    return value


class TargetGuardTests(unittest.TestCase):
    def test_only_the_random_ephemeral_project_pattern_is_accepted(self):
        lib.assert_ephemeral_project(PROJECT)
        for bad in ('enginia360', 'enginia360-r00b-0123456789a', 'enginia360-r00b-0123456789AB', PROJECT + '\n',
                    'x' + PROJECT, 'enginia360-r00b-0123456789abc', '', 'enginia360-r00b-../etc'):
            with self.subTest(project=bad), self.assertRaises(ValueError):
                lib.assert_ephemeral_project(bad)

    def test_exact_labelled_hardened_containers_are_accepted(self):
        lib.assert_exact_targets([container()], PROJECT, CONFIG)

    def test_protected_unlabelled_mismatched_and_unhardened_targets_are_refused(self):
        protected = 'b' * 64
        cases = {
            'protected id': [container(Id=protected)],
            'protected bootstrap name': [container(Name='/enginia360-api-1')],
            'wrong project': [container(Config__Labels={'com.docker.compose.project': 'enginia360',
                                                         'com.docker.compose.project.config_files': CONFIG})],
            'wrong config': [container(Config__Labels={'com.docker.compose.project': PROJECT,
                                                        'com.docker.compose.project.config_files': '/etc/other.yaml'})],
            'no labels': [container(Config__Labels={})],
            'volume mount': [container(Mounts=[{'Type': 'volume'}])],
            'host port': [container(HostConfig__PortBindings={'5432/tcp': [{'HostPort': '5432'}]})],
            'root user': [container(Config__User='0:0')],
            'writable rootfs': [container(HostConfig__ReadonlyRootfs=False)],
            'capabilities kept': [container(HostConfig__CapDrop=[])],
            'privilege escalation': [container(HostConfig__SecurityOpt=[])],
        }
        for label, containers in cases.items():
            with self.subTest(label), self.assertRaises(ValueError):
                lib.assert_exact_targets(containers, PROJECT, CONFIG, protected_ids=(protected,))

    def test_restore_into_a_non_empty_target_is_refused(self):
        lib.assert_empty_target({'domain_relations': 0, 'ledger_present': False, 'schemas': []})
        for summary in ({'domain_relations': 1, 'ledger_present': False, 'schemas': []},
                        {'domain_relations': 0, 'ledger_present': True, 'schemas': []},
                        {'domain_relations': 0, 'ledger_present': False, 'schemas': ['workshop']}):
            with self.subTest(summary=summary), self.assertRaises(ValueError):
                lib.assert_empty_target(summary)


class DumpIntegrityTests(unittest.TestCase):
    def archive(self, directory, data=b'PGDMP' + os.urandom(2048), mode=0o600):
        path = Path(directory)/'rehearsal.dump'
        path.write_bytes(data)
        path.chmod(mode)
        return path, hashlib.sha256(data).hexdigest()

    def test_intact_private_custom_archive_with_toc_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path, sha = self.archive(directory)
            lib.verify_dump(path, sha, toc='; Archive created\n1; 2615 1 SCHEMA - workshop runtime_owner')

    def test_corrupt_truncated_empty_public_or_tocless_archives_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            good, sha = self.archive(directory)
            data = good.read_bytes()
            toc = '1; 2615 1 SCHEMA - workshop runtime_owner'
            cases = {
                'truncated': (data[:-100], 0o600, toc),
                'bit flip': (data[:100] + bytes([data[100] ^ 1]) + data[101:], 0o600, toc),
                'empty': (b'', 0o600, toc),
                'wrong magic': (b'XXXXX' + data[5:], 0o600, toc),
                'mode 0644': (data, 0o644, toc),
                'empty toc': (data, 0o600, ''),
            }
            for label, (payload, mode, listing) in cases.items():
                with self.subTest(label):
                    path, _ = self.archive(directory, payload, mode)
                    with self.assertRaises(ValueError):
                        lib.verify_dump(path, sha, toc=listing)

    def test_dump_and_restore_flags_are_exact(self):
        dump, restore = lib.dump_argv(), lib.restore_argv()
        self.assertEqual(dump[0], 'pg_dump')
        self.assertIn('--format=custom', dump)
        self.assertEqual(restore[0], 'pg_restore')
        for flag in ('--exit-on-error', '--single-transaction'):
            self.assertIn(flag, restore)
        for command in (dump, restore):
            for forbidden in ('--clean', '--if-exists', '--create', '--no-owner', '--no-acl', '--no-privileges', '--no-policies',
                              '--disable-triggers', '--data-only', '--schema-only', '--enable-row-security', '--jobs', '-j', '-t', '-n',
                              '--table', '--schema', '--exclude-table', '--exclude-schema', '--no-comments'):
                self.assertNotIn(forbidden, command)
        self.assertNotIn('-f', dump)
        self.assertTrue(any(value.startswith(('-U', '--username')) or value == '-U' for value in dump))
        for command in (dump, restore):
            self.assertFalse(any(re.search(r'password', value, re.I) for value in command), 'credentials never in argv')


class ComparisonTests(unittest.TestCase):
    base = {'workshop.orders': {'rows': 2, 'sha256': 'a' * 64}, 'runtime_migrations.applied': {'rows': 24, 'sha256': 'b' * 64},
            'pgx_legacy.t': {'rows': 0, 'sha256': 'c' * 64}}

    def test_identical_snapshots_pass_and_every_difference_fails(self):
        self.assertEqual(lib.compare_table_snapshots(self.base, json.loads(json.dumps(self.base))), [])
        missing = {k: v for k, v in self.base.items() if k != 'workshop.orders'}
        unexpected = dict(self.base, **{'workshop.extra': {'rows': 0, 'sha256': 'd' * 64}})
        rows = dict(self.base, **{'workshop.orders': {'rows': 3, 'sha256': 'a' * 64}})
        cell = dict(self.base, **{'workshop.orders': {'rows': 2, 'sha256': 'e' * 64}})
        for label, after in (('missing', missing), ('unexpected', unexpected), ('rows', rows), ('cell', cell)):
            with self.subTest(label):
                self.assertTrue(lib.compare_table_snapshots(self.base, after), label)
        self.assertEqual({p.split(':')[0] for p in lib.compare_table_snapshots(self.base, missing)}, {'missing'})
        self.assertEqual({p.split(':')[0] for p in lib.compare_table_snapshots(self.base, unexpected)}, {'unexpected'})

    def test_dynamic_discovery_never_depends_on_a_count(self):
        grown = dict(self.base, **{'inventory.reservation_releases': {'rows': 1, 'sha256': 'f' * 64}})
        self.assertEqual(lib.compare_table_snapshots(grown, json.loads(json.dumps(grown))), [])
        self.assertTrue(lib.compare_table_snapshots(grown, self.base), 'a new table must be compared, not skipped')

    def test_only_literal_pg_and_information_schema_namespaces_are_excluded(self):
        for name in ('pg_catalog', 'pg_toast', 'pg_temp_3', 'information_schema'):
            self.assertTrue(lib.is_excluded_namespace(name), name)
        for name in ('pgx_legacy', 'public', 'runtime_migrations', 'workshop', 'pgpublic'):
            self.assertFalse(lib.is_excluded_namespace(name), name)
        sql = lib.discovery_sql()
        self.assertIn("!~ '^pg_'", sql)
        self.assertNotIn("LIKE 'pg_%'", sql.upper().replace('NOT LIKE', 'LIKE'))
        self.assertIn("relkind IN ('r','p')", sql)
        self.assertIn("relpersistence <> 't'", sql)
        self.assertNotIn('runtime_migrations', sql, 'the ledger is never excluded')

    def test_ledger_id_checksum_and_applied_at_must_be_identical(self):
        ledger = [('0001_a', 'a' * 64, '2026-10-24 10:00:00.123456+00'), ('0002_b', 'b' * 64, '2026-10-24 10:00:01.5+00')]
        self.assertEqual(lib.compare_ledger(ledger, list(ledger)), [])
        mutations = {
            'applied_at': [ledger[0], ('0002_b', 'b' * 64, '2026-10-24 10:00:01.6+00')],
            'checksum': [ledger[0], ('0002_b', 'c' * 64, ledger[1][2])],
            'missing': ledger[:1], 'extra': ledger + [('0003_c', 'c' * 64, '2026-10-24 10:00:02+00')],
            'order': list(reversed(ledger)), 'id': [ledger[0], ('0002_x', 'b' * 64, ledger[1][2])]}
        for label, after in mutations.items():
            with self.subTest(label):
                self.assertTrue(lib.compare_ledger(ledger, after), label)

    def test_catalog_fingerprint_categories_are_each_compared(self):
        before = {c: 'a' * 64 for c in ('relations', 'columns', 'constraints', 'policies', 'acl', 'owners', 'triggers', 'functions')}
        self.assertEqual(lib.compare_fingerprints(before, dict(before)), [])
        for category in before:
            with self.subTest(category):
                self.assertEqual(lib.compare_fingerprints(before, dict(before, **{category: 'b' * 64})), ['fingerprint:' + category])
        self.assertTrue(lib.compare_fingerprints(before, {k: v for k, v in before.items() if k != 'policies'}))

    def test_every_fingerprint_has_a_row_level_diagnostic_view(self):
        self.assertEqual(set(lib.FINGERPRINT_ROWS_SQL), set(lib.FINGERPRINT_SQL))
        for category, statement in lib.FINGERPRINT_ROWS_SQL.items():
            self.assertNotIn('sha256', statement, category)
            self.assertTrue(statement.startswith('SELECT x FROM ('), category)
        diff = lib.diff_rows(['a|1', 'b|2'], ['a|1', 'b|3'])
        self.assertEqual(diff, {'only_before': ['b|2'], 'only_after': ['b|3']})

    def test_effective_privileges_are_compared_not_the_null_versus_explicit_default_acl_encoding(self):
        # Real finding: pg_dump omits an ACL equal to the object default, so an explicit owner-only ACL
        # (relacl = {owner=arwdDxtm/owner}) restores as NULL. Both mean the same effective privileges.
        for needle in ('acldefault(', "coalesce(c.relacl", "coalesce(p.proacl", "coalesce(n.nspacl"):
            self.assertIn(needle, lib.FINGERPRINT_SQL['acl'])
        self.assertIn('regexp_replace', lib.FINGERPRINT_SQL['constraints'], 'CHECK deparse normalization must be explicit')
        self.assertIn("k.contype='c'", lib.FINGERPRINT_SQL['constraints'], 'only CHECK expressions are normalized; PK/FK/unique stay exact')

    def test_live_dispatcher_state_is_the_only_classified_post_readback_change(self):
        allowed = lib.DISPATCHER_STATE_TABLES
        self.assertEqual(allowed, {'integrations.administrative_dispatches'})
        self.assertEqual(lib.unclassified_changes(['hash:integrations.administrative_dispatches'], allowed), [])
        for change in (['rows:integrations.administrative_dispatches'], ['hash:workshop.orders'], ['missing:integrations.administrative_dispatches'],
                       ['hash:integrations.administrative_dispatches', 'hash:inventory.reservation_releases']):
            with self.subTest(change=change):
                self.assertTrue(lib.unclassified_changes(change, allowed))

    def test_markers_pre_must_be_present_and_post_dump_must_be_absent(self):
        lib.check_markers(pre_present=True, post_present=False)
        for pre, post in ((False, False), (True, True), (False, True)):
            with self.subTest(pre=pre, post=post), self.assertRaises(ValueError):
                lib.check_markers(pre_present=pre, post_present=post)


class ScratchMigrationTests(unittest.TestCase):
    def test_published_bytes_are_copied_unchanged_read_only_and_scratch_units_are_appended(self):
        source = ROOT/'database/runtime'
        published = json.loads((source/'manifest.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/'runtime'
            entries = lib.build_scratch_manifest(source, destination, [('scratch_fault', 'CREATE TABLE scratch_probe(a int); SELECT 1/0;'),
                                                                         ('scratch_sentinel', 'CREATE TABLE scratch_sentinel(a int);')])
            self.assertEqual(entries[:len(published)], published)
            self.assertEqual(len(entries), len(published) + 2)
            for number, entry in enumerate(entries, 1):
                self.assertTrue(entry['id'].startswith('%04d_' % number))
                payload = (destination/entry['path']).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), entry['sha256'])
            for entry in published:
                self.assertEqual((destination/entry['path']).read_bytes(), (source/entry['path']).read_bytes())
                self.assertEqual((destination/entry['path']).stat().st_mode & 0o222, 0, 'published scratch copies are read-only')
            self.assertEqual(json.loads((destination/'manifest.json').read_text()), entries)
            self.assertEqual(json.loads((source/'manifest.json').read_text()), published, 'published manifest untouched')

    def test_scratch_units_may_not_reuse_a_published_name_or_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            for bad in ('0001_organization_access', '../x', 'Bad Name', ''):
                with self.subTest(name=bad), self.assertRaises(ValueError):
                    lib.build_scratch_manifest(ROOT/'database/runtime', Path(directory)/bad.replace('/', '_'), [(bad, 'SELECT 1;')])

    def test_the_engine_accepts_the_scratch_manifest_checksums(self):
        engine = load('engine', 'scripts/apply-runtime-migrations.py')
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/'runtime'
            lib.build_scratch_manifest(ROOT/'database/runtime', destination, [('scratch_fault', 'SELECT 1/0;')])
            loaded = engine.load_manifest(destination/'manifest.json')
            self.assertEqual(loaded[-1]['id'].split('_', 1)[1], 'scratch_fault')


class ReportTests(unittest.TestCase):
    def test_timing_report_is_labelled_and_makes_no_recovery_claim(self):
        text = lib.timing_report({'populate': 1.5, 'quiesce': 0.1, 'recovery_to_usable_http': 12.25})
        self.assertIn('synthetic ephemeral single-host measurement', text)
        self.assertIn('NOT RPO/RTO/SLA/PITR/off-host/disaster-recovery evidence', text)
        self.assertIn('recovery_to_usable_http', text)
        self.assertNotIn('availability guarantee', text.lower())
        with self.assertRaises(ValueError):
            lib.timing_report({'populate': -1})
        with self.assertRaises(ValueError):
            lib.timing_report({})


class RunnerContractTests(unittest.TestCase):
    """The runner must really execute each step in order; strings in comments or dead code do not count."""
    STEPS = ('populate_cluster', 'quiesce', 'baseline', 'dump_cluster', 'post_dump_marker', 'destroy_cluster', 'fresh_cluster',
             'restore_cluster', 'compare_cold', 'migrator_noop', 'restart_services', 'authorized_readback', 'fault_injection')

    def runner_tree(self):
        path = ROOT/'scripts/run-r06b1-tests.py'
        self.assertTrue(path.exists(), 'runner missing')
        return ast.parse(path.read_text())

    def test_main_calls_every_step_in_order_and_guards_before_docker(self):
        tree = self.runner_tree()
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        found = sorted((c.lineno, c.col_offset, c.func.id) for c in ast.walk(main) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name))
        calls = [name for _, _, name in found]  # source order, not breadth-first walk order
        positions = [calls.index(step) for step in self.STEPS]
        self.assertEqual(positions, sorted(positions), 'steps out of order')
        self.assertLess(calls.index('assert_ephemeral_project'), calls.index('populate_cluster'))

    def test_archive_stream_is_binary_and_never_goes_through_the_text_helper(self):
        tree = self.runner_tree()
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'dump_cluster')
        keywords = [(k.arg, getattr(k.value, 'value', None)) for c in ast.walk(function) if isinstance(c, ast.Call) for k in c.keywords]
        self.assertNotIn(('text', True), keywords)
        names = [c.func.id for c in ast.walk(function) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)]
        self.assertNotIn('run', names, 'binary archive cannot use the text-mode run helper')
        self.assertIn('verify_dump', names)

    def test_destruction_removes_the_real_container_and_cleanup_uses_the_guarded_primitive(self):
        text = (ROOT/'scripts/run-r06b1-tests.py').read_text()
        tree = ast.parse(text)
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'destroy_cluster')
        source = ast.get_source_segment(text, function)
        self.assertIn("'rm', '-f'", source)
        self.assertIn('assert_exact_targets', source)
        self.assertIn('r00.cleanup(', text)
        self.assertNotIn('system prune', text)
        self.assertNotIn("'down'", text.replace("command + ['down'", '').replace('r00.cleanup', ''), 'no generic down outside guarded cleanup')
        self.assertNotIn('--volumes', text)


if __name__ == '__main__':
    unittest.main()
