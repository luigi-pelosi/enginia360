#!/usr/bin/env python3
from pathlib import Path
workflow=Path('.github/workflows/ci.yml').read_text()
assert 'python3 scripts/test-b14-ci.py' in workflow
for n in range(2,15):
    assert f'run: sh scripts/run-b{n:02d}-tests.sh' in workflow, ('earlier acceptance removed', n)
for script in ['test-b14-diagnostics-unit.py', 'test-b14-restore-contract.py']:
    assert script in workflow, script
assert 'run: sh scripts/run-b14-tests.sh' in workflow,'CI must execute the real B14 joint verification and restore rehearsal'
runner=Path('scripts/run-b14-tests.sh').read_text()
for requirement in ['test-b14.py','test-b14-restore.py','test-b14-diagnostics.py','B13.runtime.test.tsx',
                    'B14.runtime.test.tsx','/b12/950_rls_test.sql','/b13/950_rls_test.sql',
                    '990_rollback.sql','100_accounting.sql']:
    assert requirement in runner,requirement
assert 'docker volume ls -q --filter "name=^${project}_"' in runner,'cleanup must assert the ephemeral volume is gone'
compose=Path('compose.b14-test.yaml').read_text()
for requirement in ['TechnicalAccounting__Enabled: "true"','InternalBilling__Enabled: "true"',
                    'VITE_B13_TEST_UI: "true"','VITE_B10_TEST_UI: "true"']:
    assert requirement in compose,requirement
assert 'ports:' not in compose
restore=Path('scripts/test-b14-restore.py').read_text()
assert "project.startswith('enginia360-b14-')" in restore,'the restore rehearsal must refuse non-ephemeral projects'
assert 'not a production RTO' in restore,'the measurement must stay declared as a rehearsal'
operations=Path('docs/b14-operations.md').read_text()
for requirement in ['run-b14-tests.sh','pg_dump','pg_restore','OPE03','OPE04','OPE05']:
    assert requirement in operations,requirement
print('PASS B14 CI selects the joint-path, diagnostics, isolation, restore rehearsal and guarded rollback acceptance')
