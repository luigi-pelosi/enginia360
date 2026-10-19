#!/usr/bin/env python3
"""B04 runtime acceptance must not silently skip in CI."""
from pathlib import Path
workflow = Path('.github/workflows/ci.yml').read_text()
assert 'sh scripts/run-b04-tests.sh' in workflow, 'CI must invoke isolated B04 acceptance runner'
runner = Path('scripts/run-b04-tests.sh').read_text()
for required in ['VITE_B04_HTTP_BASE', '950_rls_test.sql', '990_rollback.sql', 'test-b04-audit.py', 'B04_POOL_SIZE=8']:
    assert required in runner, f'B04 runner must execute {required}'
print('PASS B04 CI selects HTTP/DOM/RLS/audit/rollback acceptance')
