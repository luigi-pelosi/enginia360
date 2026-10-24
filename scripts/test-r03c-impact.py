#!/usr/bin/env python3
"""Exact bounded closure-panel impact; no unknown executable fallback, never the full architecture."""
import importlib.util
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
impact=importlib.util.module_from_spec(spec); spec.loader.exec_module(impact)
OWN=('scripts/run-r03c-tests.py','scripts/run-r03c-api-tests.py','scripts/test-r03c-impact.py','scripts/test-r03c-lifecycle.py','tests/browser/r03c-acceptance.cjs','compose.r03c-test.yaml','r03c-api-test.Dockerfile',
     'tests/Enginia360.Api.Tests/WorkshopClosureActionTests.cs','tests/Enginia360.Api.Tests/WorkshopClosureSnapshotTests.cs','simulator/administrative-simulator.py',
     'web/src/ui01/runtime/AdministrativeWorkspace.tsx','web/src/ui01/runtime/AdministrativeWorkspace.test.tsx','web/src/ui01/runtime/administrativeContracts.ts','web/src/ui01/runtime/administrativeFixtures.ts')
SHARED=('src/Modules/Workshop/Enginia360.Workshop/ClosureActionEndpoints.cs','src/Modules/Workshop/Enginia360.Workshop/AdministrativeEndpoints.cs','src/Modules/Workshop/Enginia360.Workshop.Contracts/ClosureActionContracts.cs',
        'src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs','src/Modules/Integrations/Enginia360.Integrations/IntegrationsModule.cs','src/Modules/Integrations/Enginia360.Integrations/AdministrativeDispatcher.cs',
        'src/Enginia360.Api/Program.cs','web/src/ui01/runtime/WorkshopRuntime.tsx','web/src/ui01/runtime/workshopApi.ts')
class ClosurePanelImpact(unittest.TestCase):
    def test_every_closure_path_selects_the_actual_runtime_and_direct_consumers(self):
        for path in OWN+SHARED:
            with self.subTest(path=path):
                try: selected=impact.selection([path])
                except ValueError as error: self.fail(str(error))
                self.assertTrue(selected.get('r03c',False),'closure runtime is not selected')
                self.assertFalse(selected['full_architecture'])
                self.assertTrue(selected['migrations'])
                self.assertIn('WorkshopClosure',selected['api_filter'])
                self.assertIn('AdministrationBoundaryTests',selected['api_filter'])
                if not path.startswith('src/Enginia360.Api/'): self.assertTrue(selected['ui01b'])
    def test_workshop_and_connector_producers_also_select_all_direct_consumers(self):
        for path in (SHARED[0],SHARED[1],SHARED[2],SHARED[4],SHARED[5]):
            with self.subTest(path=path):
                selected=impact.selection([path])
                for name in ('AdministrationBoundaryTests','WorkshopEditorTests','BillingBoundaryTests','AccountingBoundaryTests'):
                    self.assertIn(name,selected['api_filter'])
    def test_unrelated_documentation_does_not_select_the_closure_runtime(self):
        self.assertFalse(impact.selection(['docs/r03c-closure-panel.md']).get('r03c'))
        self.assertNotIn('AccountingBoundaryTests',impact.selection(['src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs'])['api_filter'],'registration only needs the administration boundary')
    def test_unmapped_executable_remains_fail_closed(self):
        with self.assertRaises(ValueError): impact.selection(['scripts/unknown-new-command.py'])
        with self.assertRaises(ValueError): impact.selection(['src/Modules/Unmapped/Thing.cs'])
    def test_closure_dispatch_is_pull_request_independent_and_executes_pool4_pool1_and_term_never_full_architecture(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('  affected-r03c:',workflow)
        section=workflow.split('  affected-r03c:',1)[1].split('  runtime-migrations:',1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && needs.impact.outputs.r03c == 'true'",section)
        for command in ('timeout 600 python3 scripts/run-r03c-api-tests.py','timeout 600 python3 scripts/run-r03c-tests.py','R03C_POOL_SIZE=1 timeout 600 python3 scripts/run-r03c-tests.py','timeout 300 python3 scripts/test-r03c-lifecycle.py'):
            self.assertIn(command,section)
        self.assertIn('python3 scripts/test-r03c-impact.py',workflow)
        self.assertIn('r03c: ${{ steps.selection.outputs.r03c }}',workflow)
        self.assertNotIn('push:',workflow)
        self.assertNotIn('full_architecture: true',section)
    def test_runtime_uses_the_isolated_simulator_never_a_live_url_or_published_port(self):
        compose=(ROOT/'compose.r03c-test.yaml').read_text()
        self.assertIn('ExternalAdministration__SimulatorBaseUrl: "http://admin-simulator:8080/"',compose)
        self.assertIn('internal: true',compose)
        self.assertNotIn('ports:',compose)
        self.assertNotIn('giobby.com',compose.lower())
        runner=(ROOT/'scripts/run-r03c-tests.py').read_text()
        self.assertIn("'--wait-timeout', '180'",runner); self.assertIn("timeout=480",runner)
        self.assertNotIn('TieredStopAtLevel',(ROOT/'compose.r00b-test.yaml').read_text())
if __name__=='__main__': unittest.main()
