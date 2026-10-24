#!/usr/bin/env python3
"""Exact bounded own-time impact; no unknown executable fallback."""
import importlib.util
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
impact=importlib.util.module_from_spec(spec); spec.loader.exec_module(impact)
class OwnTimeImpact(unittest.TestCase):
    def test_own_time_paths_select_actual_runtime_and_direct_consumers(self):
        for path in ('src/Modules/Workshop/Enginia360.Workshop/ActualTimeEndpoints.cs','src/Modules/Workshop/Enginia360.Workshop.Contracts/ActualTimeContracts.cs','tests/Enginia360.Api.Tests/WorkshopOwnActualTimeTests.cs','scripts/run-r03b-tests.py','scripts/test-r03b-impact.py','scripts/test-r03b-migration.py','scripts/test-r03b-lifecycle.py','tests/browser/r03b-acceptance.cjs','compose.r03b-test.yaml','database/runtime/migrations/0022_workshop_own_actual_time.sql','web/src/ui01/runtime/OwnActualTime.tsx','web/src/ui01/runtime/actualTimeContracts.ts'):
            with self.subTest(path=path):
                try: selected=impact.selection([path])
                except ValueError as error: self.fail(str(error))
                self.assertTrue(selected.get('r03b',False),'own-time runtime is not selected')
                self.assertFalse(selected['full_architecture'])
                self.assertTrue(selected['migrations'])
                self.assertTrue(selected['ui01b'])
                self.assertIn('WorkshopOwnActualTimeTests',selected['api_filter'])
                self.assertIn('WorkshopEditorTests',selected['api_filter'])
                self.assertIn('BillingBoundaryTests',selected['api_filter'])
                self.assertIn('AccountingBoundaryTests',selected['api_filter'])
    def test_unmapped_executable_remains_fail_closed(self):
        with self.assertRaises(ValueError): impact.selection(['scripts/unknown-new-command.py'])
    def test_own_runtime_dispatch_executes_pool4_pool1_and_term_not_full_architecture(self):
        workflow=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('  affected-r03b:',workflow)
        section=workflow.split('  affected-r03b:',1)[1].split('  runtime-migrations:',1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch' && needs.impact.outputs.r03b == 'true'",section)
        self.assertIn('timeout 600 python3 scripts/run-r03b-tests.py',section)
        self.assertIn('R03B_POOL_SIZE=1 timeout 600 python3 scripts/run-r03b-tests.py',section)
        self.assertIn('timeout 300 python3 scripts/test-r03b-lifecycle.py',section)
        self.assertIn('python3 scripts/test-r03b-impact.py',workflow)
        self.assertNotIn('push:',workflow)
    def test_test_only_identity_avoids_observed_c2_cold_start_cost_without_relaxing_deadline(self):
        compose=(ROOT/'compose.r03b-test.yaml').read_text()
        self.assertIn('JAVA_OPTS_APPEND: "-XX:TieredStopAtLevel=1"',compose)
        runner=(ROOT/'scripts/run-r03b-tests.py').read_text()
        self.assertIn("'--wait-timeout','180'",runner)
        self.assertNotIn('TieredStopAtLevel',(ROOT/'compose.r00b-test.yaml').read_text())
if __name__=='__main__': unittest.main()
