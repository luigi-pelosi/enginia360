#!/usr/bin/env python3
"""R06.b.1 TERM lifecycle: unit guards plus an actual TERM while pg_dump, pg_restore or Chromium is in flight.

  python3 scripts/test-r06b1-lifecycle.py            unit guards only (offline)
  python3 scripts/test-r06b1-lifecycle.py --actual dump|restore|browser
"""
import importlib.util
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT/'scripts/run-r06b1-tests.py'
PROBE_DEADLINE_SECONDS = 400
MARKERS = {'dump': b'R06B1_LIFECYCLE hold-dump', 'restore': b'R06B1_LIFECYCLE hold-restore', 'browser': b'R06B1_LIFECYCLE hold-browser'}


def load_runner(hold=''):
    os.environ['R06B1_HOLD'] = hold
    spec = importlib.util.spec_from_file_location('r06b1_runner_under_test', RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner()

    def test_protected_project_is_rejected_before_docker(self):
        with patch.object(self.runner.r00, 'run') as command:
            for project in ('enginia360', 'enginia360-r00b-0123456789a', 'enginia360-r00b-0123456789ab; rm'):
                with self.assertRaises(ValueError):
                    self.runner.r00.cleanup(['docker', 'compose'], project)
            command.assert_not_called()

    def test_cleanup_is_bound_to_this_runners_compose_file(self):
        self.assertEqual(self.runner.r00.CONFIG, ROOT/'compose.r06b1-test.yaml')
        project = 'enginia360-r00b-0123456789ab'
        labels = {'com.docker.compose.project': project, 'com.docker.compose.project.config_files': str(ROOT/'compose.r04c1-test.yaml')}
        def command(args, **kwargs):
            if args[:2] == ['docker', 'inspect']:
                return json.dumps([{'Config': {'Labels': labels}, 'State': {'Paused': False}, 'Id': 'someone-elses'}])
            if args[:3] == ['docker', 'ps', '-aq']:
                return 'someone-elses\n'
            raise AssertionError('no removal may follow a config mismatch: ' + repr(args))
        with patch.object(self.runner.r00, 'run', side_effect=command), self.assertRaises(ValueError):
            self.runner.r00.cleanup(['docker', 'compose', '-p', project], project)

    def test_exact_labelled_paused_container_is_unpaused_before_removal(self):
        project = 'enginia360-r00b-0123456789ab'
        calls, removed = [], False
        def command(args, **kwargs):
            nonlocal removed
            calls.append(args)
            if args[:2] == ['docker', 'inspect']:
                return json.dumps([{'Config': {'Labels': {'com.docker.compose.project': project, 'com.docker.compose.project.config_files': str(self.runner.CONFIG)}},
                                    'State': {'Paused': True}, 'Id': 'exact'}])
            if args[:3] == ['docker', 'ps', '-aq']:
                return '' if removed else 'exact\n'
            if args[:3] == ['docker', 'rm', '-f']:
                removed = True
            return ''
        with patch.object(self.runner.r00, 'run', side_effect=command):
            self.runner.r00.cleanup(['docker', 'compose', '-p', project], project)
        self.assertLess(calls.index(['docker', 'unpause', 'exact']), next(i for i, a in enumerate(calls) if a[:3] == ['docker', 'rm', '-f']))

    def test_unknown_hold_and_missing_scratch_are_refused(self):
        with self.assertRaises(ValueError):
            load_runner('everything')
        load_runner('')

    def test_runner_accepts_no_target_argument(self):
        text = RUNNER.read_text()
        self.assertNotIn('sys.argv', text)
        self.assertNotIn('argparse', text)
        for name in ('R06B1_PROJECT', 'R06B1_CONTAINER', 'R06B1_DATABASE_URL', 'R06B1_VOLUME'):
            self.assertNotIn(name, text)


def actual_term_probe(phase):
    runner = load_runner(phase)
    before = {'volumes': runner.r00.inventory('volume'), 'running': set(runner.run(['docker', 'ps', '-q', '--no-trunc']).splitlines()),
              'all': set(runner.run(['docker', 'ps', '-aq', '--no-trunc']).splitlines())}
    env = dict(os.environ, R06B1_HOLD=phase)
    process = subprocess.Popen([sys.executable, str(RUNNER)], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    deadline = time.monotonic() + PROBE_DEADLINE_SECONDS
    terminated, pending = False, b''
    try:
        assert process.stdout is not None
        while process.poll() is None and time.monotonic() < deadline:
            if select.select([process.stdout], [], [], 0.2)[0]:
                # Raw fd reads only: a TextIOWrapper may already hold the marker while the fd is quiet.
                pending = (pending + os.read(process.stdout.fileno(), 65536))[-16384:]
                if MARKERS[phase] in pending:
                    started = time.monotonic()
                    process.send_signal(signal.SIGTERM)
                    terminated = True
                    break
        if not terminated:
            raise RuntimeError('in-flight %s probe point not reached: %s' % (phase, pending[-400:].decode(errors='replace')))
        process.communicate(timeout=60)
        elapsed = time.monotonic() - started
        assert process.returncode != 0, 'TERM must not become a successful rehearsal'
        assert elapsed < 55, 'cleanup relied on kill escalation'
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=10)
                raise RuntimeError('runner failed bounded TERM cleanup')
    after = {'volumes': runner.r00.inventory('volume'), 'running': set(runner.run(['docker', 'ps', '-q', '--no-trunc']).splitlines()),
             'all': set(runner.run(['docker', 'ps', '-aq', '--no-trunc']).splitlines())}
    assert after == before, 'protected inventory or leaked containers differ after TERM'
    assert not runner.run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project.config_files=' + str(runner.CONFIG)]).strip()
    assert not runner.run(['docker', 'network', 'ls', '-q', '--filter', 'name=enginia360-r00b-']).strip(), 'ephemeral network leaked'
    leftovers = subprocess.run(['pgrep', '-af', 'compose.*r06b1-test'], capture_output=True, text=True).stdout
    assert 'r06b1' not in leftovers.replace('pgrep', ''), 'orphan compose child: ' + leftovers
    print('PASS actual R06.b.1 TERM while %s in flight in %.1fs; children and exact ephemeral resources removed; protected inventory unchanged.' % (phase, elapsed))


if __name__ == '__main__':
    if '--actual' in sys.argv:
        actual_term_probe(sys.argv[sys.argv.index('--actual') + 1])
    else:
        unittest.main()
