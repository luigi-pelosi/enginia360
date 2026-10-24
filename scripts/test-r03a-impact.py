#!/usr/bin/env python3
"""R03.a fail-closed impact mapping: workshop workspace owners select r03a acceptance plus direct consumers only."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

OWNERS = (
    'src/Modules/Workshop/Enginia360.Workshop/CommercialEndpoints.cs',
    'src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs',
    'src/Modules/Workshop/Enginia360.Workshop/WorkshopDbContext.cs',
    'src/Modules/Workshop/Enginia360.Workshop/WorkshopBillingSources.cs',
    'src/Modules/Workshop/Enginia360.Workshop/AdministrativeEndpoints.cs',
    'src/Modules/Workshop/Enginia360.Workshop/WorkshopReservationLines.cs',
    'src/Modules/Workshop/Enginia360.Workshop.Contracts/Contracts.cs',
    'src/Modules/Workshop/Enginia360.Workshop.Contracts/EditorContracts.cs',
    'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs',
    'src/Modules/Inventory/Enginia360.Inventory/PickingEndpoints.cs',
    'src/Modules/Inventory/Enginia360.Inventory/CarcassReturnEndpoints.cs',
    'src/Modules/Inventory/Enginia360.Inventory.Contracts/Contracts.cs',
    'database/runtime/migrations/0018_workshop_order_workspace.sql',
    'scripts/run-r03a-tests.py', 'scripts/test-r03a-impact.py', 'scripts/test-r03a-contract.py',
    'tests/browser/r03a-acceptance.cjs', 'compose.r03a-test.yaml',
    'tests/Enginia360.Api.Tests/WorkshopEditorTests.cs', 'scripts/test-r03a-migration.py',
    'web/src/ui01/runtime/OrderWorkspace.tsx', 'web/src/ui01/runtime/OrderWorkspace.test.tsx', 'web/src/ui01/runtime/OrderList.tsx',
    'web/src/ui01/runtime/editorContracts.ts', 'web/src/ui01/runtime/editorMessages.ts', 'web/src/ui01/runtime/editorFixtures.ts',
)
CONSUMERS = ('WorkshopBoundaryTests', 'CommercialCalculationTests', 'WorkshopEditorTests', 'InstallationBoundaryTests',
             'CarcassBoundaryTests', 'InventoryArchitectureTests', 'AdministrationBoundaryTests',
             'BillingBoundaryTests', 'AccountingBoundaryTests')


class R03aImpact(unittest.TestCase):
    def test_every_owner_path_selects_r03a_acceptance_and_direct_consumers(self):
        for path in OWNERS:
            with self.subTest(path=path):
                result = module.selection([path])
                self.assertTrue(result['r03a'])
                self.assertTrue(result['migrations'])
                for name in CONSUMERS:
                    self.assertIn(name, result['api_filter'])
                self.assertFalse(result['full_architecture'])

    def test_every_path_changed_by_this_increment_is_mapped(self):
        import subprocess
        base = subprocess.run(['git', 'rev-parse', 'origin/main'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if not base:
            self.skipTest('no origin/main in this checkout')
        paths = subprocess.run(['git', 'diff', '--name-only', base, 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.split()
        result = module.selection(paths)
        self.assertEqual(result['changed_paths'], sorted(set(paths)))
        self.assertFalse(result['full_architecture'])
        # This guard also runs for later offline-only increments and on clean main.
        # Actual R03.a owners retain their positive acceptance contract above.
        if set(paths) & set(OWNERS):
            offline_wiring_only = result.get('r06_offline') and set(paths) <= module.R06_OFFLINE_FILES | module.R06_WIRING
            if not offline_wiring_only:
                self.assertTrue(result['r03a'] and result['ui01b'] and result['migrations'])

    def test_unrelated_paths_do_not_select_r03a(self):
        for path in ('docs/r03a-order-workspace.md', 'web/src/ui01/App.tsx', 'scripts/test-c00-consistency.py',
                     'src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs'):
            with self.subTest(path=path):
                self.assertFalse(module.selection([path]).get('r03a', False))

    def test_unknown_workshop_code_still_fails_closed(self):
        with self.assertRaises(ValueError):
            module.selection(['src/Modules/Planning/NewPolicy.cs'])

    def test_workflow_executes_r03a_acceptance_on_dispatch_only(self):
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('affected-r03a:', text)
        block = text.split('  affected-r03a:\n', 1)[1].split('\n  affected-', 1)[0].split('\n  runtime-migrations:', 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && needs.impact.outputs.r03a == 'true'", block)
        self.assertIn('timeout 600 python3 scripts/run-r03a-tests.py', block)
        self.assertIn('r03a: ${{ steps.selection.outputs.r03a }}', text)
        self.assertIn('python3 scripts/test-r03a-impact.py', text)
        self.assertIn('python3 scripts/test-r03a-contract.py', text)
        self.assertNotIn('  push:', text.split('concurrency:', 1)[0])

    def test_runner_is_covered_by_selection_mutation(self):
        # Removing a consumer from the mapping must be caught by this suite.
        self.assertIn('AccountingBoundaryTests', module.R03A_FILTER)
        self.assertIn('WorkshopEditorTests', module.R03A_FILTER)


if __name__ == '__main__':
    unittest.main()
