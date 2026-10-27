#!/usr/bin/env python3
"""Finite sales-order adapter impact, no account traffic in CI."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import tempfile
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
impact = importlib.util.module_from_spec(spec); spec.loader.exec_module(impact)
OWN = {'scripts/test-r05b1-impact.py', 'scripts/run-r05b1-tests.py', 'tests/browser/r05b1-acceptance.cjs',
       'tests/browser/r05b1-giobby.py', 'compose.r05b1-test.yaml', 'scripts/test-r05b1-lifecycle.py',
       'tests/Enginia360.Api.Tests/GiobbySalesOrderTests.cs',
       'src/Modules/Integrations/Enginia360.Integrations/GiobbySalesOrderConnector.cs',
       'src/Modules/Integrations/Enginia360.Integrations/GiobbyHost.cs',
       'database/runtime/migrations/0026_giobby_binding_kind.sql'}
DIRECT = {'src/Modules/Integrations/Enginia360.Integrations/SimulatorConnector.cs',
          'src/Modules/Workshop/Enginia360.Workshop.Contracts/ClosureActionContracts.cs',
          'scripts/run-r05b0-tests.py', 'compose.r05b0-test.yaml',
          'web/src/ui01/runtime/administrativeContracts.test.ts'}
class Impact(unittest.TestCase):
    def test_fixture_secret_ownership_does_not_require_a_root_ci_runner(self):
        spec = importlib.util.spec_from_file_location('adapter_runner', ROOT/'scripts/run-r05b1-tests.py')
        assert spec and spec.loader
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state/'browser.json').write_text(json.dumps({'contexts': [{'tenantId':'synthetic','legalEntityId':'synthetic','siteId':'synthetic'}], 'workshop':[{'payerId':'synthetic','serviceId':'synthetic'}]}))
            with patch.object(runner, 'original', return_value='synthetic-sql'), patch.object(runner.binding.r00, 'certificate'), patch.object(runner.binding.r00, 'own') as own, patch('os.chown', side_effect=PermissionError('nonroot hosted runner')):
                try: self.assertEqual(runner.fixtures(state, 'synthetic-secret'), 'synthetic-sql')
                except PermissionError: self.fail('token fixture requires a root host instead of the established bounded ownership helper')
                own.assert_called_once_with(state, 'token', 1654)
    def test_exact_head_dispatch_runs_both_pools_and_term_without_provider_credentials(self):
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('  affected-r05b1:', workflow)
        section = workflow.split('  affected-r05b1:', 1)[1].split('\n  runtime-migrations:', 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && needs.impact.outputs.r05b1 == 'true'", section)
        for command in ('timeout 600 python3 scripts/run-r05b1-tests.py', 'R05B0_POOL_SIZE=1 timeout 600 python3 scripts/run-r05b1-tests.py', 'timeout 300 python3 scripts/test-r05b1-lifecycle.py'):
            self.assertIn(command, section)
        self.assertIn('r05b1: ${{ steps.selection.outputs.r05b1 }}', workflow)
        self.assertIn('python3 scripts/test-r05b1-impact.py', workflow)
        self.assertNotIn('push:', workflow)
        self.assertNotIn('secrets.', section)
    def test_adapter_paths_require_actual_bounded_runtime_and_regressions(self):
        for path in sorted(OWN | DIRECT):
            with self.subTest(path=path):
                try: selected = impact.selection([path])
                except ValueError as error: self.fail(str(error))
                self.assertTrue(selected.get('r05b1'), 'Giobby protocol runtime absent')
                self.assertTrue(selected['ui_build'])
                self.assertTrue(selected['migrations'])
                self.assertIn('GiobbySalesOrderTests', selected['api_filter'])
                self.assertFalse(selected['full_architecture'])
    def test_docs_only_and_unknown_executable(self):
        self.assertFalse(impact.selection(['docs/r05b1-giobby-sales-order-adapter.md']).get('r05b1'))
        with self.assertRaises(ValueError): impact.selection(['scripts/unmapped-r05b1.py'])
if __name__ == '__main__': unittest.main()
