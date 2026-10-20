#!/usr/bin/env python3
from pathlib import Path
workflow=Path('.github/workflows/ci.yml').read_text()
assert 'python3 scripts/test-b12-ci.py' in workflow
assert 'run: sh scripts/run-b12-tests.sh' in workflow,'CI must execute real B12 invoice stack'
runner=Path('scripts/run-b12-tests.sh').read_text()
for requirement in ['test-b12.py','B12.runtime.test.tsx','Billing audit','990_rollback.sql','unexpected invoice count']:
    assert requirement in runner,requirement
compose=Path('compose.b12-test.yaml').read_text()
assert 'InternalBilling__Enabled: "true"' in compose and './database/b12:/b12:ro' in compose
assert 'ports:' not in compose
print('PASS B12 CI selects real HTTP/DOM/concurrency/audit/rollback acceptance')
