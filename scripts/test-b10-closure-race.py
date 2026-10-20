#!/usr/bin/env python3
"""Force both interleavings of technical closure vs a late installation behind the real order lock.

A fixture-only session holds the order's advisory lock; the two production requests queue on it in a
chosen order and PostgreSQL grants the lock in queue order after release. Ephemeral runner project only.
"""
import json
import os
import re
import select
import subprocess
import sys
import time

project, state, first = sys.argv[1], sys.argv[2], sys.argv[3]
assert re.fullmatch(r'enginia360-b10-[0-9]+', project), 'Expected exact ephemeral runner project'
assert first in ('close', 'install')
second = 'install' if first == 'close' else 'close'
container = project + '-postgres-1'
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container], timeout=10))[0]
assert metadata['Config']['Labels']['com.docker.compose.project'] == project
assert metadata['Config']['Labels']['com.docker.compose.service'] == 'postgres'
assert set(metadata['NetworkSettings']['Networks']) == {project + '_backend'}
assert 'compose.b10-test.yaml' in metadata['Config']['Labels']['com.docker.compose.project.config_files']
assert metadata['HostConfig']['Tmpfs'].get('/var/lib/postgresql') is not None
command = ['docker', 'exec', '-i', '-e', 'PGOPTIONS=-c statement_timeout=10000 -c lock_timeout=5000 -c idle_session_timeout=45000',
           container, 'sh', '-c', 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -At']
image = 'python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710'


def sql(text):
    return subprocess.run(command, input=text, text=True, capture_output=True, check=True, timeout=10).stdout


def run_probe(name, behavior, background=False):
    args = ['docker', 'run', '--name', name, '--network', project + '_backend', '-e', 'B06_STATE_DIR=/evidence',
            '-v', state + ':/evidence', '-v', os.getcwd() + ':/source:ro', '-w', '/source', image,
            'python3', 'scripts/test-b10.py', 'http://web:8080', behavior]
    if background: return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)
    print(result.stdout + result.stderr, end='')
    assert result.returncode == 0, behavior


def waiting():
    return int(sql("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type='Lock' AND wait_event='advisory';").strip())


def until(count):
    deadline = time.monotonic() + 30
    while waiting() < count:
        assert time.monotonic() < deadline, 'Production request never queued on the order lock'
        time.sleep(.05)


holder, probes, names, errors = None, [], [], []
try:
    run_probe(project + '-race-prepare', 'race_prepare')
    with open(os.path.join(state, 'b10-race-fixture.json')) as handle: order = json.load(handle)['order']['id']
    holder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    holder.stdin.write(f"SELECT pg_advisory_lock(hashtextextended('{order}', 0));\nSELECT 'LOCKED';\n")
    holder.stdin.flush()
    deadline, line = time.monotonic() + 10, b''
    while line.strip() != b'LOCKED':
        if line.endswith(b'\n'): line = b''
        remaining = deadline - time.monotonic()
        assert remaining > 0 and select.select([holder.stdout], [], [], remaining)[0], 'Lock holder not ready'
        byte = os.read(holder.stdout.fileno(), 1)
        assert byte, 'Lock holder exited unexpectedly'
        line += byte
    for position, kind in enumerate([first, second], start=1):
        names.append(f'{project}-race-{kind}')
        probes.append(run_probe(names[-1], 'race_' + kind, background=True))
        until(position)
    print('Production requests queued on the order lock in order:', first, second, flush=True)
    holder.stdin.write(f"SELECT pg_advisory_unlock(hashtextextended('{order}', 0));\n\\q\n")
    holder.stdin.flush()
    holder.wait(timeout=10)
    for probe in probes:
        print(probe.communicate(timeout=60)[0], end='')
        assert probe.returncode == 0
    run_probe(project + '-race-verify', 'race_verify_' + first + '_first')
finally:
    if holder is not None and holder.poll() is None:
        holder.kill()
        holder.wait(timeout=5)
    for name in names:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=10)
    for probe in probes:
        if probe.poll() is None: probe.kill()
    for leftover in ['fixture', 'close', 'install']:
        path = os.path.join(state, f'b10-race-{leftover}.json')
        if os.path.exists(path): os.remove(path)
