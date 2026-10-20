#!/usr/bin/env python3
from pathlib import Path
import re
workflow = Path('.github/workflows/ci.yml').read_text()
steps = re.split(r'^      - ', workflow, flags=re.MULTILINE)[1:]
assert any(re.search(r'^        run: sh scripts/run-b10-tests.sh$', step, re.MULTILINE) and 'timeout-minutes: 10' in step for step in steps), 'CI must invoke real B10 isolated HTTP/DOM/SQL acceptance'
assert 'python3 scripts/test-b10-ci.py' in workflow
assert 'VITE_B10_TEST_UI=true npm run build' in workflow
runner = Path('scripts/run-b10-tests.sh').read_text()
for required in ['VITE_B10_HTTP_BASE', 'VITE_B10_SIMULATOR', '950_rls_test.sql', '990_rollback.sql', 'test-b10-audit.py', 'B04_POOL_SIZE=8',
                 'B04_POOL_SIZE=1', 'closure_race', 'test-b10-closure-race.py', 'denied_scope', 'read_only', 'create_only', 'capability_disabled', 'destination_missing',
                 'version_after', 'reject', 'tenants', 'len(items)==5']:
    assert required in runner, required
compose = Path('compose.b10-test.yaml').read_text()
for required in ['VITE_B10_TEST_UI: "true"', 'read_only: true', 'cap_drop: [ALL]', 'no-new-privileges:true', 'networks: [backend]', '@sha256:']:
    assert required in compose, required
assert 'ports:' not in compose
for earlier in ['scripts/run-b05-tests.sh', 'scripts/run-b06-tests.sh', 'scripts/run-b07-tests.sh', 'scripts/run-b08-tests.sh', 'scripts/run-b09-tests.sh']:
    assert '/b10/070_administration.sql' in Path(earlier).read_text(), earlier
print('PASS B10 CI selects ephemeral HTTP/DOM/SQL/RLS/audit/rollback, simulator hardening, private build, both pool sizes and earlier-runner schema')
