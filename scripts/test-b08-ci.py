#!/usr/bin/env python3
from pathlib import Path
import re
import shlex
workflow = Path('.github/workflows/ci.yml').read_text()
steps = re.split(r'^      - ', workflow, flags=re.MULTILINE)[1:]
assert any(re.search(r'^        run: sh scripts/run-b08-tests.sh$', step, re.MULTILINE) for step in steps), 'CI must invoke real B08 isolated HTTP/DOM/SQL acceptance'
assert 'python3 scripts/test-b08-ci.py' in workflow
assert 'VITE_B08_TEST_UI=true npm run build' in workflow
assert any('timeout-minutes: 2' in step and 'run: timeout 60 python3 scripts/test-b08-installation-race-lifecycle.py' in step for step in steps)
runner = Path('scripts/run-b08-tests.sh').read_text()
for required in ['VITE_B08_HTTP_BASE', '950_rls_test.sql', '990_rollback.sql', 'test-b08-audit.py', 'test-b08-installation-race.py', 'B04_POOL_SIZE=8', 'B04_POOL_SIZE=1', 'probe fault', 'probe recover', 'history']:
    assert required in runner, required
assert 'VITE_B08_TEST_UI: "true"' in Path('compose.b08-test.yaml').read_text()
print('PASS B08 CI selects ephemeral HTTP/DOM/SQL/RLS/audit/rollback, race lifecycle, private build and both pool sizes')
