#!/usr/bin/env python3
"""Force competing production INSERTs behind an ephemeral fixture-only SQL gate."""
import json
import os
import re
import select
import subprocess
import sys
import time

project = sys.argv[1]
assert re.fullmatch(r'enginia360-b08-[0-9]+', project), 'Expected exact ephemeral runner project'
container = project + '-postgres-1'
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container], timeout=10))[0]
assert metadata['Config']['Labels']['com.docker.compose.project'] == project
assert metadata['Config']['Labels']['com.docker.compose.service'] == 'postgres'
assert set(metadata['NetworkSettings']['Networks']) == {project + '_backend'}
assert 'compose.b08-test.yaml' in metadata['Config']['Labels']['com.docker.compose.project.config_files']
assert metadata['HostConfig']['Tmpfs'].get('/var/lib/postgresql') is not None
assert not any(m['Type'] == 'volume' for m in metadata['Mounts'])
command = ['docker', 'exec', '-i', '-e',
           'PGOPTIONS=-c statement_timeout=10000 -c lock_timeout=5000 -c idle_session_timeout=45000',
           container, 'sh', '-c',
           'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -At']


def sql(text):
    return subprocess.run(command, input=text, text=True, capture_output=True, check=True, timeout=10).stdout


def ready(process):
    deadline = time.monotonic() + 10
    line = b''
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([process.stdout], [], [], remaining)[0]:
            raise TimeoutError('Database lock holder readiness timed out')
        byte = os.read(process.stdout.fileno(), 1)
        assert byte, 'Database lock holder exited unexpectedly'
        line += byte
        if byte == b'\n':
            if line.strip() == b'LOCKED': return
            line = b''


def release(process):
    process.stdin.write('SELECT pg_advisory_unlock(80881);\n\\q\n')
    process.stdin.flush()
    process.wait(timeout=5)


def reap(process):
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        cleanup('terminate child', process.terminate)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            cleanup('kill child', process.kill)
            process.wait(timeout=2)
    finally:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                cleanup('close child stream', stream.close)


holder = None
probe = None
probe_name = project + '-installation-race-probe'
probe_attempted = False
cleanup_errors = []
primary_error = None


def cleanup(label, action):
    try:
        action()
    except BaseException as error:
        cleanup_errors.append(label + ': ' + str(error))
        print('Race cleanup error:', label, repr(error), file=sys.stderr)


try:
    sql('''TRUNCATE inventory.consumptions, workshop.installations, inventory.picks, inventory.reservations; UPDATE inventory.stock SET "Physical"=2;
CREATE OR REPLACE FUNCTION workshop.test_insert_gate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN PERFORM pg_advisory_xact_lock_shared(80881); RETURN NEW; END $$;
DROP TRIGGER IF EXISTS test_insert_gate ON workshop.installations;
CREATE TRIGGER test_insert_gate BEFORE INSERT ON workshop.installations
FOR EACH ROW EXECUTE FUNCTION workshop.test_insert_gate();''')
    holder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
    assert holder.stdin is not None and holder.stdout is not None
    holder.stdin.write("SELECT pg_advisory_lock(80881);\nSELECT 'LOCKED';\n")
    holder.stdin.flush()
    ready(holder)
    probe_attempted = True
    probe = subprocess.Popen(['docker', 'run', '--name', probe_name, '--network', project + '_backend',
        '-v', os.getcwd() + ':/source:ro', '-w', '/source',
        'python:3.14.0-alpine3.22@sha256:8373231e1e906ddfb457748bfc032c4c06ada8c759b7b62d9c73ec2a3c56e710',
        'python3', 'scripts/test-b08.py', 'http://web:8080', 'concurrent'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.monotonic() + 30
    first = None
    maximum = 0
    while time.monotonic() < deadline:
        count = int(sql("SELECT count(*) FROM pg_stat_activity WHERE wait_event='advisory' AND query LIKE '%INSERT INTO workshop.installations%';").strip())
        maximum = max(maximum, count)
        if count and first is None: first = time.monotonic()
        if count >= 8 or (first and time.monotonic() - first > 3): break
        time.sleep(.05)
    print('Production INSERT sessions observed at gate:', maximum, flush=True)
    assert maximum >= 1, 'No production INSERT reached the fixture gate'
    release(holder)
    print(probe.communicate(timeout=60)[0])
    assert probe.returncode == 0, 'Installation oversubscription or unexpected HTTP outcome'
except BaseException as error:
    primary_error = error
    raise
finally:
    if holder is not None:
        if holder.poll() is None:
            cleanup('holder release', lambda: release(holder))
        cleanup('holder reap', lambda: reap(holder))
    if probe_attempted:
        cleanup('probe container removal', lambda: subprocess.run(
            ['docker', 'rm', '-f', probe_name], capture_output=True, text=True, check=True, timeout=10))
    if probe is not None:
        cleanup('probe reap', lambda: reap(probe))
    cleanup('trigger drop', lambda: sql('DROP TRIGGER IF EXISTS test_insert_gate ON workshop.installations;'))
    cleanup('function drop', lambda: sql('DROP FUNCTION IF EXISTS workshop.test_insert_gate();'))
    if cleanup_errors and primary_error is None:
        raise RuntimeError('Race cleanup failed: ' + '; '.join(cleanup_errors))
