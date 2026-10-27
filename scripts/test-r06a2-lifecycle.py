#!/usr/bin/env python3
"""R06.a.2 lifecycle: offline runner guards, plus --actual TERM during a live ephemeral staging database."""
import ast
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
ACTUAL = '--actual' in sys.argv
if ACTUAL:
    sys.argv.remove('--actual')


def inventory():
    ids = subprocess.run(['docker', 'ps', '-aq', '--no-trunc'], capture_output=True, text=True, check=True, timeout=30).stdout.split()
    items = json.loads(subprocess.run(['docker', 'inspect', *ids], capture_output=True, text=True, check=True, timeout=30).stdout) if ids else []
    volumes = subprocess.run(['docker', 'volume', 'ls', '-q'], capture_output=True, text=True, check=True, timeout=30).stdout.split()
    return sorted((x['Id'], x['State']['StartedAt'], x['RestartCount'], x['State']['Status']) for x in items), sorted(volumes)


class RunnerGuards(unittest.TestCase):
    def runner(self):
        path = ROOT/'scripts/run-r06a2-tests.py'
        self.assertTrue(path.exists(), 'staging runner missing')
        return path.read_text()

    def test_runner_accepts_no_target_publishes_no_port_and_has_one_hold_hook(self):
        text = self.runner()
        tree = ast.parse(text)
        constants = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        for forbidden in ('system prune', 'compose', '--publish', '-p', '--volume', '-v', 'migrat'):
            self.assertNotIn(forbidden, constants)
        self.assertNotIn('sys.argv', text, 'no caller-supplied target')
        self.assertIn('R06A2_HOLD', (ROOT/'scripts/test-r06a2-storage.py').read_text())
        storage = (ROOT/'scripts/test-r06a2-storage.py').read_text()
        for required in ("'--network', 'none'", "'--read-only'", "'--cap-drop', 'ALL'", 'no-new-privileges:true', "'--memory'", "'--pids-limit'",
                         'assert_exact_targets', "'rm', '-f'", 'signal.SIGTERM'):
            self.assertIn(required, storage)
        for forbidden in ("'--publish'", "'-p'", "'--volume'", "'-v', '/", 'volume create', 'apply-runtime-migrations'):
            self.assertNotIn(forbidden, storage)


@unittest.skipUnless(ACTUAL, 'opt-in: real container TERM')
class ActualTerm(unittest.TestCase):
    def test_term_while_database_is_live_removes_exact_container_and_preserves_protected_inventory(self):
        before = inventory()
        env = dict(os.environ, R06A2_HOLD='1')
        process = subprocess.Popen([sys.executable, '-I', str(ROOT/'scripts/run-r06a2-tests.py')], cwd=ROOT, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            deadline = time.monotonic() + 120
            seen = False
            while time.monotonic() < deadline:
                line = process.stdout.readline()
                if 'R06A2_LIFECYCLE hold' in line:
                    seen = True
                    break
                if process.poll() is not None:
                    break
            self.assertTrue(seen, 'runner never reached the live-database hold')
            during = subprocess.run(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project.config_files=' + str(ROOT/'scripts/run-r06a2-tests.py')],
                                    capture_output=True, text=True, timeout=30).stdout.split()
            self.assertEqual(len(during), 1, 'exactly one labelled staging container must be live before TERM')
            process.send_signal(signal.SIGTERM)
            output, _ = process.communicate(timeout=60)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        self.assertNotEqual(process.returncode, 0, 'TERM is not success')
        after = subprocess.run(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project.config_files=' + str(ROOT/'scripts/run-r06a2-tests.py')],
                               capture_output=True, text=True, timeout=30).stdout.split()
        self.assertEqual(after, [], 'staging container leaked after TERM')
        self.assertEqual(inventory(), before)
        print('PASS R06A2 TERM exit=%s: live staging container removed; protected containers/StartedAt/25 volumes unchanged' % process.returncode, flush=True)

if __name__ == '__main__':
    unittest.main()
