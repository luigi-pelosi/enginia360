#!/usr/bin/env python3
"""B05 acceptance is selected, never silently omitted by CI."""
from pathlib import Path
workflow = Path('.github/workflows/ci.yml').read_text()
assert 'sh scripts/run-b05-tests.sh' in workflow, 'CI must invoke isolated B05 acceptance runner'
runner = Path('scripts/run-b05-tests.sh').read_text()
for required in ['VITE_B05_HTTP_BASE', '950_rls_test.sql', '990_rollback.sql', 'test-b05-audit.py', 'B04_POOL_SIZE=8']:
    assert required in runner, f'B05 runner must execute {required}'
assert 'VITE_B05_TEST_UI=true npm run build' in workflow
print('PASS B05 CI selects HTTP/DOM/RLS/audit/rollback acceptance')
