#!/usr/bin/env python3
"""Finite R04.b.1 supplier-role impact: direct runtime acceptance, no ERP traffic, no full architecture run."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT/'scripts/select-ci-impact.py')
impact = importlib.util.module_from_spec(spec); spec.loader.exec_module(impact)
OWN = {'database/runtime/migrations/0027_supplier_role.sql', 'scripts/owner-supplier-vendor-identity.py',
       'scripts/test-r04b1-supplier.py', 'scripts/test-r04b1-impact.py',
       'src/Modules/Counterparties/Enginia360.Counterparties/SupplierEndpoints.cs'}


class Impact(unittest.TestCase):
    def test_supplier_paths_require_actual_editor_api_postgresql_and_migration_acceptance(self):
        for path in sorted(OWN):
            with self.subTest(path=path):
                try: selected = impact.selection([path])
                except ValueError as error: self.fail(str(error))
                self.assertTrue(selected['ui01b'], 'editor API/PostgreSQL acceptance absent')
                self.assertTrue(selected['migrations'], 'migration/RLS/pool acceptance absent')
                if not path.endswith('.cs'): self.assertTrue(selected['browser'])
                self.assertIn('MasterAuthorityEnforcementTests', selected['api_filter'])
                self.assertFalse(selected['full_architecture'])

    def test_role_ui_and_its_existing_common_edit_consumers_select_finite_acceptance(self):
        for path in ('web/src/ui01/runtime/MasterAuthority.tsx', 'web/src/ui01/runtime/MasterAuthority.test.tsx',
                     'tests/browser/ui01b-acceptance.cjs', 'scripts/run-ui01b-tests.py'):
            with self.subTest(path=path):
                selected = impact.selection([path])
                for key in ('ui01b', 'migrations', 'ui_tests', 'ui_build'):
                    self.assertTrue(selected[key], key)
                self.assertIn('MasterAuthorityEnforcementTests', selected['api_filter'])
                self.assertIn('CounterpartyArchitectureTests', selected['api_filter'])
                self.assertFalse(selected['full_architecture'])
                self.assertFalse(selected['r03c'], 'no speculative closure architecture gate')

    def test_workflow_runs_both_pools_and_the_offline_owner_input_guard(self):
        workflow = (ROOT/'.github/workflows/ci.yml').read_text()
        editor = workflow.split('  affected-editor:', 1)[1].split('\n  affected-r03a:', 1)[0]
        self.assertIn('run: timeout 600 python3 scripts/run-ui01b-tests.py', editor)
        self.assertIn('run: UI01B_POOL_SIZE=1 timeout 600 python3 scripts/run-ui01b-tests.py', editor)
        self.assertIn('timeout-minutes: 30', editor)
        self.assertIn('python3 scripts/test-r04b1-impact.py', workflow)
        self.assertIn('python3 -I scripts/test-r04b1-supplier.py OwnerInputTests', workflow)
        self.assertNotIn('push:', workflow)
        runner = (ROOT/'scripts/run-ui01b-tests.py').read_text()
        self.assertIn("os.environ.get('UI01B_POOL_SIZE','4') not in ('1','4')", runner)

    def test_isolated_migration_runner_executes_the_sql_suite_and_ships_the_owner_tool(self):
        self.assertIn('scripts/test-r04b1-supplier.py', (ROOT/'scripts/run-r00a-tests.py').read_text())
        docker = (ROOT/'migrator.runtime.Dockerfile').read_text()
        for name in ('scripts/test-r04b1-supplier.py', 'scripts/owner-supplier-vendor-identity.py'):
            self.assertIn(name, docker)

    def test_migration_0027_is_appended_and_every_published_checksum_matches(self):
        manifest = json.loads((ROOT/'database/runtime/manifest.json').read_text())
        self.assertEqual(manifest[26]['id'], '0027_supplier_role')
        self.assertGreaterEqual(len(manifest), 27)  # 0028+ are later appended units; the 0027 entry and every checksum stay fixed
        for entry in manifest:
            self.assertEqual(hashlib.sha256((ROOT/'database/runtime'/entry['path']).read_bytes()).hexdigest(), entry['sha256'], entry['id'])

    def test_docs_only_and_unknown_executable(self):
        self.assertFalse(impact.selection(['docs/r04b1-supplier-role.md']).get('ui01b'))
        with self.assertRaises(ValueError): impact.selection(['scripts/unmapped-r04b1.py'])


if __name__ == '__main__': unittest.main()
