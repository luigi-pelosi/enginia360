#!/usr/bin/env python3
"""Actual browser-child TERM cleanup, plus unit guards for exact target and paused resources."""
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

ROOT=Path(__file__).resolve().parents[1]
R03A='--r03a' in sys.argv
EDITOR='--editor' in sys.argv or R03A
RUNNER=ROOT/('scripts/run-r03a-tests.py' if R03A else 'scripts/run-ui01b-tests.py' if EDITOR else 'scripts/run-r00b-tests.py')
MARKER=b'R03A_LIFECYCLE database-outage' if R03A else b'UI01B_LIFECYCLE database-outage' if EDITOR else b'R00B_LIFECYCLE database-outage'
spec=importlib.util.spec_from_file_location('r00b_runner',RUNNER)
assert spec is not None and spec.loader is not None
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
if EDITOR:
    # The editor runner reuses R00.b cleanup/inventory primitives against its own Compose file.
    base = getattr(runner, 'r00')
    for name in ('cleanup', 'inventory', 'CONFIG'):
        setattr(runner, name, getattr(base, name))


class CleanupGuardTests(unittest.TestCase):
    def test_protected_project_is_rejected_before_docker(self):
        with patch.object(runner,'run') as command:
            with self.assertRaises(ValueError):
                runner.cleanup(['docker','compose'],'enginia360')
            command.assert_not_called()

    def test_term_probe_observes_marker_without_waiting_for_more_output(self):
        real_popen = subprocess.Popen
        # A single write makes TextIOWrapper read ahead both lines. The child must
        # receive TERM before its short ordinary-success exit, without new output.
        child = "import os,time; os.write(1,b'PASS previous check\\nR00B_LIFECYCLE database-outage\\n'); time.sleep(0.8)"
        def start(*args, **kwargs):
            return real_popen([sys.executable, '-c', child], **kwargs)
        with patch.object(subprocess, 'Popen', side_effect=start), \
             patch.object(runner, 'inventory', return_value=set()), \
             patch.object(runner, 'run', return_value=''):
            actual_term_probe()

    def test_exact_labelled_paused_container_is_unpaused_before_removal(self):
        project='enginia360-r00b-0123456789ab'
        calls=[]
        removed=False
        def command(args,**kwargs):
            nonlocal removed
            calls.append(args)
            if args[:2]==['docker','inspect']:
                return json.dumps([{'Config':{'Labels':{'com.docker.compose.project':project,
                    'com.docker.compose.project.config_files':str(runner.CONFIG)}},'State':{'Paused':True},'Id':'exact-container'}])
            if args[:3]==['docker','ps','-aq']:
                return '' if removed else 'exact-container\n'
            if args[:3]==['docker','rm','-f']:
                removed=True
            return ''
        with patch.object(runner,'run',side_effect=command):
            runner.cleanup(['docker','compose','-p',project],project)
        self.assertIn(['docker','unpause','exact-container'],calls)
        unpause=calls.index(['docker','unpause','exact-container'])
        remove=next(index for index,args in enumerate(calls) if args[:3]==['docker','rm','-f'])
        self.assertLess(unpause,remove)


def actual_term_probe():
    before_volumes=runner.inventory('volume')
    before_running=set(runner.run(['docker','ps','-q','--no-trunc']).splitlines())
    process=subprocess.Popen([sys.executable,str(RUNNER)],cwd=ROOT,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,bufsize=0)
    deadline=time.monotonic()+240
    terminated=False
    pending=b''
    try:
        assert process.stdout is not None
        while process.poll() is None and time.monotonic()<deadline:
            if select.select([process.stdout],[],[],0.2)[0]:
                # Never mix select(fd) with a read-ahead TextIOWrapper: a complete
                # lifecycle marker may already be buffered while the fd is quiet.
                pending=(pending+os.read(process.stdout.fileno(),65536))[-8192:]
                if MARKER in pending:
                    process.send_signal(signal.SIGTERM)
                    terminated=True
                    break
        if not terminated:
            raise RuntimeError('actual paused-database/browser probe point not reached')
        process.communicate(timeout=45)
        assert process.returncode != 0, 'TERM must not become a successful acceptance run'
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=45)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=10)
                raise RuntimeError('runner failed bounded TERM cleanup')
    assert runner.inventory('volume')==before_volumes
    assert set(runner.run(['docker','ps','-q','--no-trunc']).splitlines())==before_running
    assert not runner.run(['docker','ps','-aq','--filter','label=com.docker.compose.project.config_files='+str(runner.CONFIG)]).strip()
    print('PASS actual '+('R03.a workspace' if R03A else 'UI01.b editor' if EDITOR else 'R00.b')+' TERM while PostgreSQL paused and Chromium alive; child/resources removed, protected inventory unchanged.')


if __name__=='__main__':
    if '--actual' in sys.argv:
        actual_term_probe()
    else:
        unittest.main()
