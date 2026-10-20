#!/usr/bin/env python3
from pathlib import Path
import re
workflow = Path('.github/workflows/ci.yml').read_text()
steps = re.split(r'^      - ', workflow, flags=re.MULTILINE)[1:]
assert any(re.search(r'^        run: sh scripts/run-b09-tests.sh$', step, re.MULTILINE) and 'timeout-minutes: 10' in step for step in steps), 'CI must invoke real B09 isolated HTTP/DOM/SQL acceptance'
assert 'python3 scripts/test-b09-ci.py' in workflow
assert 'VITE_B09_TEST_UI=true npm run build' in workflow
assert any('timeout-minutes: 2' in step and 'run: timeout 60 python3 scripts/test-b09-return-race-lifecycle.py' in step for step in steps)
runner = Path('scripts/run-b09-tests.sh').read_text()
for required in ['VITE_B09_HTTP_BASE', '950_rls_test.sql', '990_rollback.sql', 'test-b09-audit.py', 'test-b09-return-race.py', 'B04_POOL_SIZE=8',
                 'B04_POOL_SIZE=1', 'probe fault', 'probe recover', 'history', 'late_race', 'version_after', 'unconfigured_location']:
    assert required in runner, required
assert 'VITE_B09_TEST_UI: "true"' in Path('compose.b09-test.yaml').read_text()
for earlier in ['scripts/run-b06-tests.sh', 'scripts/run-b07-tests.sh', 'scripts/run-b08-tests.sh']:
    text = Path(earlier).read_text()
    assert '/b09/060_carcass.sql' in text and '/b09/990_rollback.sql' in text, earlier
print('PASS B09 CI selects ephemeral HTTP/DOM/SQL/RLS/audit/rollback, race lifecycle, private build, both pool sizes and earlier-runner schema')
