#!/usr/bin/env python3
from pathlib import Path
import re
import shlex
workflow = Path('.github/workflows/ci.yml').read_text()
steps = re.split(r'^      - ', workflow, flags=re.MULTILINE)[1:]
assert any(re.search(r'^        run: sh scripts/run-b07-tests.sh$', step, re.MULTILINE) for step in steps), 'CI must invoke real B07 isolated HTTP/DOM/SQL acceptance'
assert 'python3 scripts/test-b07-ci.py' in workflow
assert 'VITE_B07_TEST_UI=true npm run build' in workflow
assert any('timeout-minutes: 2' in step and 'run: timeout 60 python3 scripts/test-b07-picking-race-lifecycle.py' in step for step in steps)
runner = Path('scripts/run-b07-tests.sh').read_text()
for required in ['VITE_B07_HTTP_BASE', '950_rls_test.sql', '990_rollback.sql', 'test-b07-audit.py', 'test-b07-picking-race.py', 'B04_POOL_SIZE=8', 'B04_POOL_SIZE=1', 'disabled_area', 'history']:
    assert required in runner, required
assert 'VITE_B07_TEST_UI: "true"' in Path('compose.b07-test.yaml').read_text()
print('PASS B07 CI selects ephemeral HTTP/DOM/SQL/RLS/audit/rollback, race lifecycle, private build and both pool sizes')
