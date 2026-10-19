#!/usr/bin/env python3
"""Offline failure injection into the actual race controller; no Docker access."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

PROJECT = 'enginia360-b06-123456'


class LifecycleTests(unittest.TestCase):
    def exercise(self, failure=None, cleanup_failure: bool | str = False):
        calls, children = [], []
        original = (subprocess.TimeoutExpired('injected', 10) if failure in ('sql_timeout', 'completion_timeout')
                    else TimeoutError('injected ready timeout') if failure in ('ready_timeout', 'ready_empty')
                    else RuntimeError('injected ' + str(failure)))
        metadata = {'Config': {'Labels': {'com.docker.compose.project': PROJECT,
            'com.docker.compose.service': 'postgres',
            'com.docker.compose.project.config_files': 'compose.b06-test.yaml'}},
            'NetworkSettings': {'Networks': {PROJECT + '_backend': {}}},
            'HostConfig': {'Tmpfs': {'/var/lib/postgresql': ''}}, 'Mounts': []}

        class Child:
            def __init__(self, holder):
                self.holder, self.returncode, self.reaped = holder, None, False
                class Input(io.StringIO):
                    def write(stream, text):
                        if cleanup_failure == 'release' and 'unlock' in text:
                            raise BrokenPipeError('release cleanup injected')
                        return super().write(text)
                self.stdin = Input()
                self.stderr = io.StringIO()
                read, write = os.pipe()
                os.write(write, b'LOCKED\n')
                os.close(write)
                self.stdout = os.fdopen(read)
            def wait(self, timeout=None):
                assert timeout and timeout <= 10
                if failure in ('stuck', 'terminate_error') and self.returncode is None:
                    raise subprocess.TimeoutExpired('child', timeout)
                self.returncode, self.reaped = 0, True
                return 0
            def communicate(self, timeout=None):
                assert timeout and timeout <= 60
                if not self.holder and failure in ('completion', 'completion_timeout') and self.returncode is None:
                    raise original
                self.wait(timeout=min(timeout, 10))
                return ('probe passed', '')
            def poll(self):
                return self.returncode
            def terminate(self):
                calls.append('terminate')
                if failure == 'terminate_error': raise RuntimeError('terminate injected')
                if failure != 'stuck': self.returncode = -15
            def kill(self):
                calls.append('kill')
                self.returncode = -9

        def start(command, **kwargs):
            holder = command[1] == 'exec'
            if failure == ('startup' if holder else 'probe_startup'): raise original
            child = Child(holder)
            children.append(child)
            return child

        def sql(command, **kwargs):
            if command[1:3] == ['rm', '-f']:
                calls.append('probe container removed')
                if cleanup_failure == 'remove': raise RuntimeError('remove cleanup injected')
                self.assertLessEqual(kwargs['timeout'], 10)
                return subprocess.CompletedProcess(command, 0, '')
            text = kwargs['input']
            calls.append(text)
            self.assertIsNotNone(kwargs.get('timeout'), 'SQL execution must be bounded')
            self.assertLessEqual(kwargs['timeout'], 10)
            if text.startswith('DROP'):
                if cleanup_failure is True: raise RuntimeError('cleanup injected')
            elif 'CREATE OR REPLACE' in text and failure in ('creation', 'sql_timeout'): raise original
            elif 'pg_stat_activity' in text:
                if failure in ('observer', 'stuck', 'terminate_error'): raise original
                return subprocess.CompletedProcess(command, 0, '0' if failure == 'assertion' else '8')
            return subprocess.CompletedProcess(command, 0, '')

        error = None
        namespace = None
        stderr = io.StringIO()
        try:
            with patch('sys.argv', ['controller', PROJECT]), patch('subprocess.check_output', return_value=json.dumps([metadata]).encode()), patch('subprocess.run', side_effect=sql), patch('subprocess.Popen', side_effect=start), patch('select.select', side_effect=original if failure in ('ready', 'ready_timeout') else lambda r,w,x,t: ([],[],[]) if failure == 'ready_empty' else (r,[],[])), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                namespace = runpy.run_path(str(Path(__file__).with_name('test-b06-stock-race.py')), run_name='__main__')
        except BaseException as caught:
            error = caught
        finally:
            try:
                for child in children:
                    self.assertTrue(all(stream.closed for stream in (child.stdin, child.stdout, child.stderr)),
                                    'Controller must close streams before fixture cleanup')
            finally:
                for child in children:
                    for stream in (child.stdin, child.stdout, child.stderr): stream.close()
        self.assertTrue(any(text.startswith('DROP TRIGGER') for text in calls), calls)
        self.assertTrue(any('DROP FUNCTION' in text for text in calls), calls)
        if children and not children[-1].holder:
            self.assertIn('probe container removed', calls)
        self.assertTrue(all(child.reaped for child in children), 'all started children must be reaped')
        if failure:
            self.assertIsInstance(error, AssertionError if failure == 'assertion' else type(original))
            if failure not in ('assertion', 'ready_empty'): self.assertIs(error, original)
        elif cleanup_failure: self.assertIsInstance(error, RuntimeError)
        else: self.assertIsNone(error)
        if cleanup_failure: self.assertIn('cleanup injected', stderr.getvalue())
        if failure == 'stuck': self.assertIn('kill', calls)
        if not failure: return namespace

    def test_retained_project_names_are_rejected_before_any_docker_call(self):
        for project in ('enginia360-b06-manual', 'enginia360-b06-acceptance',
                        'enginia360-b06-123-suffix', 'enginia360-b05-123'):
            with self.subTest(project=project), patch('sys.argv', ['controller', project]), \
                    patch('subprocess.check_output') as inspect, patch('subprocess.run') as sql:
                with self.assertRaises(AssertionError):
                    runpy.run_path(str(Path(__file__).with_name('test-b06-stock-race.py')), run_name='__main__')
                inspect.assert_not_called()
                sql.assert_not_called()

    def test_creation_failure(self): self.exercise('creation')
    def test_holder_startup_failure(self): self.exercise('startup')
    def test_holder_ready_failure(self): self.exercise('ready')
    def test_probe_startup_failure(self): self.exercise('probe_startup')
    def test_observer_failure(self): self.exercise('observer')
    def test_gate_assertion_failure(self): self.exercise('assertion')
    def test_probe_completion_failure(self): self.exercise('completion')
    def test_cleanup_errors_preserve_original(self): self.exercise('observer', True)
    def test_release_error_preserves_original(self): self.exercise('observer', 'release')
    def test_container_removal_error_preserves_original(self): self.exercise('observer', 'remove')
    def test_cleanup_only_failure_is_reported(self): self.exercise(cleanup_failure=True)
    def test_stuck_child_killed_and_reaped(self): self.exercise('stuck')
    def test_terminate_error_still_kills_and_reaps(self): self.exercise('terminate_error')
    def test_sql_timeout(self): self.exercise('sql_timeout')
    def test_ready_timeout(self): self.exercise('ready_timeout')
    def test_completion_timeout(self): self.exercise('completion_timeout')
    def test_ready_select_expiration(self): self.exercise('ready_empty')
    def test_success(self): self.exercise()
    def test_real_child_readiness_has_no_unbounded_readline(self):
        import ast
        tree = ast.parse(Path(__file__).read_text())
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                             and node.func.attr == 'readline' for node in ast.walk(tree)),
                         'Real-child readiness must use the bounded controller helper')

    def test_real_stubborn_child_is_killed_and_reaped(self):
        namespace = self.exercise()
        child = subprocess.Popen([sys.executable, '-c',
            'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("LOCKED", flush=True); time.sleep(120)'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            assert namespace is not None and child.stdout is not None
            namespace['ready'](child)
            namespace['reap'](child)
            self.assertEqual(child.returncode, -9)
            self.assertIsNotNone(child.poll(), 'Controller must reap the actual process')
            for stream in (child.stdin, child.stdout, child.stderr):
                self.assertIsNotNone(stream)
                assert stream is not None
                self.assertTrue(stream.closed, 'Controller must close every actual process pipe')
        finally:
            if child.poll() is None: child.kill()
            child.wait(timeout=2)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None: stream.close()

    def test_real_silent_child_readiness_times_out_and_is_reaped(self):
        namespace = self.exercise()
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert namespace is not None
            started = time.monotonic()
            with self.assertRaisesRegex(TimeoutError, 'readiness timed out'):
                namespace['ready'](child)
            self.assertLess(time.monotonic() - started, 12)
            self.assertIsNone(child.poll(), 'Silent child must still be alive at timeout')
        finally:
            if child.poll() is None: child.kill()
            child.wait(timeout=2)
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None: stream.close()


if __name__ == '__main__': unittest.main()
