#!/usr/bin/env python3
from pathlib import Path
workflow=Path('.github/workflows/ci.yml').read_text()
assert 'python3 scripts/test-b12-ci.py' in workflow
assert 'run: sh scripts/run-b12-tests.sh' in workflow,'CI must execute real B12 invoice stack'
runner=Path('scripts/run-b12-tests.sh').read_text()
for requirement in ['test-b12.py','test-b12-security.py','test-b12-audit.py','950_rls_test.sql','B12.runtime.test.tsx','990_rollback.sql','unexpected invoice count']:
    assert requirement in runner,requirement
compose=Path('compose.b12-test.yaml').read_text()
assert 'InternalBilling__Enabled: "true"' in compose and './database/b12:/b12:ro' in compose
assert 'ports:' not in compose
host=Path('web/src/B05TestApp.tsx').read_text()
assert 'B12Invoice' in host and 'VITE_B12_TEST_UI' in host, 'internal invoice UI must be reachable from the order host'
print('PASS B12 CI selects real HTTP/DOM/concurrency/audit/rollback acceptance')
