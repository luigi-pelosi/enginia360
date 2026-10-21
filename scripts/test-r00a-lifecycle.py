#!/usr/bin/env python3
"""Real Docker failure/TERM cleanup probes, without touching existing resources."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
DOCKER = shutil.which('docker')


def resources():
    result = {}
    for kind, args in [('containers',['ps','-aq']), ('networks',['network','ls','-q']), ('volumes',['volume','ls','-q'])]:
        result[kind] = set(subprocess.check_output([DOCKER,*args],text=True).splitlines())
    return result


def main():
    before = resources()
    with tempfile.TemporaryDirectory(prefix='r00a-lifecycle-', dir=os.environ['TMPDIR']) as directory:
        wrapper = Path(directory) / 'docker'
        wrapper.write_text(f'''#!{sys.executable}
import os,sys
if 'compose' in sys.argv and 'run' in sys.argv and sys.argv[-1]=='migrator':
    raise SystemExit(42)
os.execv({DOCKER!r},[{DOCKER!r},*sys.argv[1:]])
''')
        wrapper.chmod(0o700)
        env = dict(os.environ, PATH=directory+os.pathsep+os.environ['PATH'])
        result = subprocess.run([sys.executable,'scripts/run-r00a-tests.py'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
        assert result.returncode != 0, 'controlled first-migration failure did not fail the runner'
        assert '42' in result.stderr, 'failure probe failed before its intended runtime command'
        assert resources() == before, 'failure cleanup changed or leaked Docker resources'
        process = subprocess.Popen([sys.executable,'scripts/run-r00a-tests.py'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            found = False
            for _ in range(600):
                ids = set(subprocess.check_output([DOCKER,'ps','-q','--filter','name=enginia360-r00a-'],text=True).splitlines())
                if ids - before['containers']:
                    found = True
                    break
                if process.poll() is not None:
                    break
                time.sleep(0.1)
            assert found, 'TERM probe never reached a running ephemeral PostgreSQL container'
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=60)
            assert process.returncode != 0
            assert resources() == before, 'TERM cleanup changed or leaked Docker resources'
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=60)
    print('PASS R00.a actual Docker failure and SIGTERM cleanup; original containers/networks/volumes unchanged.')


if __name__ == '__main__':
    main()
