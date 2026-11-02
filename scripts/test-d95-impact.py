#!/usr/bin/env python3
"""D95 finite owner projection and approved direct read consumers."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
impact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(impact)
PATHS = {'scripts/owner-external-supplier-role.py', 'scripts/test-d95-projection.py',
         'scripts/test-d95-impact.py', 'database/runtime/migrations/0035_external_supplier_projection.sql'}


class ImpactTests(unittest.TestCase):
    def test_projection_selects_security_real_sql_editor_and_direct_supplier_consumer(self):
        for path in sorted(PATHS):
            with self.subTest(path=path):
                try:
                    selected = impact.selection([path])
                except ValueError as error:
                    self.fail(str(error))
                for key in ('migrations', 'browser', 'ui01b', 'r04b2a', 'ui_build', 'ui_tests', 'r06_offline'):
                    self.assertTrue(selected[key], key)
                for name in ('MasterAuthorityEnforcementTests', 'CounterpartyArchitectureTests', 'PurchaseIntentTests'):
                    self.assertIn(name, selected['api_filter'])
                for key in ('full_architecture', 'r03c', 'r06a2', 'r04c2'):
                    self.assertFalse(selected[key], key)

    def test_complete_projection_increment_does_not_expand_to_unrelated_runtime(self):
        selected = impact.selection(sorted(PATHS | {'scripts/run-r00a-tests.py','scripts/run-ui01b-tests.py',
                     'migrator.runtime.Dockerfile','scripts/select-ci-impact.py','.github/workflows/ci.yml',
                     'database/runtime/manifest.json','docs/r06-migration-inventory.json','docs/r06-migration-inventory.md',
                     'tests/browser/d95-projection.cjs','docs/r02-d95-external-supplier-projection.md',
                     'docs/r04b1-supplier-role.md','docs/productization-plan.md','docs/productization-backlog.json'}))
        for key in ('browser','migrations','ui01b','r04b2a','ui_build','ui_tests','r06_offline'):
            self.assertTrue(selected[key], key)
        for key in ('r03a','r03a2','r03b','r03c','r04a','r04c1','r04c2','r06b1','r06a2','r05b0','r05b1','r04b2b3','full_architecture'):
            self.assertFalse(selected[key], key)
        # An unrelated executable producer cannot hide behind the bounded exception.
        outside = impact.selection(sorted(PATHS | {'src/Modules/Workshop/Enginia360.Workshop/EditorEndpoints.cs'}))
        self.assertTrue(outside['r03a'])

    def test_real_runtime_and_offline_security_checks_are_executed_not_merely_named(self):
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn('python3 -I scripts/test-d95-impact.py && python3 -I scripts/test-d95-projection.py OwnerInputTests', workflow)
        runner = (ROOT/'scripts/run-r00a-tests.py').read_text()
        self.assertIn("'scripts/test-d95-projection.py'", runner.split('FOUNDATION_SUITES =',1)[1].split('PURCHASING_SUITES',1)[0])
        docker = (ROOT/'migrator.runtime.Dockerfile').read_text()
        self.assertIn('scripts/test-d95-projection.py', docker)
        self.assertIn('scripts/owner-external-supplier-role.py', docker)
        editor = (ROOT/'scripts/run-ui01b-tests.py').read_text()
        self.assertIn('            d95_acceptance(command, query, state, fixture)', editor)
        self.assertIn("browser('before')", editor)
        self.assertIn("browser('after')", editor)

    def test_unmapped_writer_and_docs_cannot_silently_select_projection(self):
        with self.assertRaises(ValueError):
            impact.selection(['scripts/owner-unmapped-d95.py'])
        selected = impact.selection(['docs/r02-d95-external-supplier-projection.md'])
        self.assertFalse(selected['migrations'])
        self.assertFalse(selected['full_architecture'])


if __name__ == '__main__':
    unittest.main()
