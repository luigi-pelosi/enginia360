#!/usr/bin/env python3
from pathlib import Path
workflow=Path('.github/workflows/ci.yml').read_text()
assert 'run: sh scripts/run-b11-tests.sh' in workflow,'CI must execute real B11 continuity/reconciliation stack'
assert 'python3 scripts/test-b11-ci.py' in workflow
runner=Path('scripts/run-b10-tests.sh').read_text()
for requirement in ['SIGKILL api','restart_verify','fairness_test','lease_verify','recovery_denied','recovery_negatives','B11.runtime.test.tsx','test-b11-audit.py','/b11/990_rollback.sql','/b11/950_rls_test.sql']:
 assert requirement in runner,requirement
assert 'B10_BEHAVIOR=b11' in Path('scripts/run-b11-tests.sh').read_text()
assert 'B11_FORCE_API_RECREATE' in Path('scripts/run-b11-tests.sh').read_text()
assert runner.index('--capture >') < runner.index('compose kill -s SIGKILL api'), 'real audit must be captured before container replacement discards its local log'
print('PASS B11 CI selects real receiver faults, process restart, lease fencing, fairness, scopes/RLS, DOM, audit and guarded rollback')
