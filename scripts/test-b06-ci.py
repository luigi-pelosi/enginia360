#!/usr/bin/env python3
from pathlib import Path
import re
import shlex


def selects_bounded_lifecycle(text):
    # Inspect an executable step, not arbitrary mentions/comments in YAML.
    for block in re.split(r'^      - ', text, flags=re.MULTILINE)[1:]:
        run = re.search(r'^        run: ([^\n]+)$', block, re.MULTILINE)
        limit = re.search(r'^        timeout-minutes: ([1-9][0-9]*)$', block, re.MULTILINE)
        if run and limit and int(limit[1]) <= 2:
            if shlex.split(run[1], comments=True) == ['timeout', '60', 'python3', 'scripts/test-b06-stock-race-lifecycle.py']:
                return True
    return False


assert not selects_bounded_lifecycle('      - name: comment only\n        timeout-minutes: 1\n        run: echo ok # timeout 60 python3 scripts/test-b06-stock-race-lifecycle.py\n')
assert not selects_bounded_lifecycle('      - name: unbounded\n        run: timeout 60 python3 scripts/test-b06-stock-race-lifecycle.py\n')
workflow = Path('.github/workflows/ci.yml').read_text()
assert selects_bounded_lifecycle(workflow), 'CI must execute bounded offline lifecycle step'
assert 'sh scripts/run-b06-tests.sh' in workflow, 'CI must invoke real isolated B06 runner'
assert 'VITE_B06_TEST_UI=true npm run build' in workflow, 'CI must build B06 private UI'
runner = Path('scripts/run-b06-tests.sh').read_text()
for required in ['VITE_B06_HTTP_BASE', '950_rls_test.sql', '990_rollback.sql', 'test-b06-audit.py', 'B04_POOL_SIZE=8', 'B04_POOL_SIZE=1']:
    assert required in runner, required
assert 'printf \'TMPDIR=%s' in workflow
print('PASS B06 CI selects isolated HTTP/DOM/RLS/audit/rollback and both pool sizes')
