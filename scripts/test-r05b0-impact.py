#!/usr/bin/env python3
"""R05.b.0 finite direct dependency selection and executed dispatch acceptance guards."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
impact = importlib.util.module_from_spec(spec); spec.loader.exec_module(impact)
OWN = ('compose.r05b0-test.yaml', 'scripts/run-r05b0-tests.py', 'scripts/test-r05b0-impact.py',
       'scripts/test-r05b0-lifecycle.py', 'tests/browser/r05b0-acceptance.cjs', 'tests/browser/r05b0-gaps.cjs', 'tests/browser/r05b0-simulator.py',
       'database/runtime/migrations/0025_administrative_bindings.sql',
       'src/Modules/Workshop/Enginia360.Workshop/AdministrativeBinding.cs')
DIRECT = ('src/Modules/Workshop/Enginia360.Workshop/AdministrativeEndpoints.cs',
          'src/Modules/Workshop/Enginia360.Workshop/WorkshopDbContext.cs',
          'src/Modules/Workshop/Enginia360.Workshop.Contracts/AdministrativeContracts.cs',
          'src/Modules/Integrations/Enginia360.Integrations/IntegrationsModule.cs',
          'src/Modules/Integrations/Enginia360.Integrations/AdministrativeDispatcher.cs',
          'src/Modules/Integrations/Enginia360.Integrations/AdministrativeRecovery.cs',
          'src/Enginia360.Api/Program.cs', 'database/runtime/manifest.json',
          'web/src/ui01/runtime/AdministrativeWorkspace.tsx', 'web/src/ui01/runtime/administrativeContracts.ts')
class BindingImpact(unittest.TestCase):
    def test_each_binding_path_requires_its_real_acceptance(self):
        for path in OWN + DIRECT:
            with self.subTest(path=path):
                try: selected = impact.selection([path])
                except ValueError as error: self.fail(str(error))
                self.assertTrue(selected.get('r05b0'), 'binding runtime absent')
                self.assertTrue(selected['migrations'])
                self.assertTrue(selected['r06_offline'])
                self.assertTrue(selected['r06b1'])
                self.assertFalse(selected['full_architecture'])
    @staticmethod
    def guard(workflow):
        """Return violations; the same predicate is mutation-tested below."""
        missing = []
        if '  affected-r05b0:' not in workflow: return ['job']
        section = workflow.split('  affected-r05b0:', 1)[1].split('\n  runtime-migrations:', 1)[0]
        if "github.event_name == 'workflow_dispatch' && needs.impact.outputs.r05b0 == 'true'" not in section: missing.append('dispatch-only')
        for name, command in (('pool4', 'timeout 600 python3 scripts/run-r05b0-tests.py'),
                              ('pool1', 'R05B0_POOL_SIZE=1 timeout 600 python3 scripts/run-r05b0-tests.py'),
                              ('term', 'timeout 300 python3 scripts/test-r05b0-lifecycle.py')):
            if command not in section: missing.append(name)
        if 'r05b0: ${{ steps.selection.outputs.r05b0 }}' not in workflow: missing.append('output')
        if 'python3 scripts/test-r05b0-impact.py' not in workflow: missing.append('check')
        if 'push:' in workflow or 'full_architecture: true' in section: missing.append('policy')
        return missing
    def test_dispatch_runs_both_pools_and_actual_term(self):
        self.assertEqual(self.guard((ROOT/'.github/workflows/ci.yml').read_text()), [])
    def test_guard_mutations_fail(self):
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        cases = {'job': workflow.replace('  affected-r05b0:', '  affected-removed:'),
                 'pool1': workflow.replace('R05B0_POOL_SIZE=1 timeout 600 python3 scripts/run-r05b0-tests.py', 'true'),
                 'term': workflow.replace('timeout 300 python3 scripts/test-r05b0-lifecycle.py', 'true'),
                 'check': workflow.replace('python3 scripts/test-r05b0-impact.py', 'true'),
                 'dispatch-only': workflow.replace("github.event_name == 'workflow_dispatch' && needs.impact.outputs.r05b0 == 'true'", "needs.impact.outputs.r05b0 == 'true'")}
        for name, mutated in cases.items():
            with self.subTest(name=name): self.assertIn(name, self.guard(mutated))
    def test_documentation_and_unknown_executables(self):
        self.assertFalse(impact.selection(['docs/r05b0-immutable-binding.md']).get('r05b0'))
        with self.assertRaises(ValueError): impact.selection(['scripts/unmapped-r05b0.py'])
if __name__ == '__main__': unittest.main()
