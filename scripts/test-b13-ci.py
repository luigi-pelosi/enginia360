#!/usr/bin/env python3
from pathlib import Path
workflow=Path('.github/workflows/ci.yml').read_text()
assert 'python3 scripts/test-b13-ci.py' in workflow
assert 'run: sh scripts/run-b13-tests.sh' in workflow,'CI must execute the real B13 accounting stack'
assert 'VITE_B13_TEST_UI=true' in workflow,'CI must build the private B13 UI'
runner=Path('scripts/run-b13-tests.sh').read_text()
for requirement in ['test-b13.py','test-b13-recovery.py','test-b13-audit.py','950_rls_test.sql',
                    'B13.runtime.test.tsx','990_rollback.sql','unexpected journal entry count','100_accounting.sql']:
    assert requirement in runner,requirement
compose=Path('compose.b13-test.yaml').read_text()
assert 'TechnicalAccounting__Enabled: "true"' in compose and './database/b13:/b13:ro' in compose
assert 'InternalBilling__Enabled: "true"' in compose,'technical accounting requires the internal invoice'
assert 'ports:' not in compose
host=Path('web/src/B05TestApp.tsx').read_text()
assert 'B13JournalEntry' in host and 'VITE_B13_TEST_UI' in host,'journal UI must be reachable from the order host'
print('PASS B13 CI selects real HTTP/DOM/scope/fault/RLS/audit/rollback acceptance')
