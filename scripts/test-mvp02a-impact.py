#!/usr/bin/env python3
"""Finite platform authority selection; unknown adjacent producers stay fail closed."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT / 'scripts/select-ci-impact.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FILES = {'src/Enginia360.Api/PlatformAdministration/PlatformAuthority.cs', 'scripts/owner-platform-authority.py', 'scripts/test-mvp02a-authority.py', 'scripts/run-mvp02a-tests.py', 'scripts/test-mvp02a-impact.py', 'tests/browser/mvp02a-authority.cjs', 'database/runtime/migrations/0036_platform_authority.sql'}

class ImpactTests(unittest.TestCase):

    def test_each_path_selects_authority_and_auth_regressions(self):
        for path in FILES:
            with self.subTest(path=path):
                result = m.selection([path])
                self.assertTrue(result['platform_authority'])
                self.assertTrue(result['browser'])
                self.assertIn('ExternalIdentityAuthenticationTests', result['api_filter'])
                self.assertFalse(result['full_architecture'])

    def test_finite_wiring_does_not_select_historical_erp(self):
        result = m.selection(sorted(FILES | {'src/Enginia360.Api/OrganizationAccess/OrganizationAccessModule.cs', 'migrator.runtime.Dockerfile', 'database/runtime/manifest.json', 'scripts/select-ci-impact.py', '.github/workflows/ci.yml', 'docs/mvp02a-platform-authority.md', 'docs/mvp-backlog.json', 'docs/mvp-delivery-plan.md', 'docs/mvp01-frontend.md', 'docs/r06-migration-inventory.json', 'docs/r06-migration-inventory.md'}))
        self.assertTrue(result['platform_authority'])
        self.assertTrue(result['migrations'])
        self.assertFalse(result['ui01b'])
        self.assertFalse(result['r04b2b3'])

    def test_ci_executes_new_runtime_and_retains_evidence(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('  affected-platform-authority:', workflow)
        job = workflow.split('  affected-platform-authority:', 1)[1].split('\n  affected-', 1)[0]
        self.assertIn("github.event_name == 'workflow_dispatch'", job)
        self.assertIn("needs.impact.outputs.platform_authority == 'true'", job)
        self.assertIn('scripts/run-mvp02a-tests.py', job)
        self.assertIn('MVP02A_POOL_SIZE=1', job)
        self.assertIn('actions/upload-artifact@v4', job)
        self.assertIn('R00_MIGRATION_SUITE=foundation', job)
        self.assertIn('scripts/test-mvp02a-impact.py', workflow)

    def test_finite_offline_scope_runs_inventory_without_unrelated_erp_guards(self):
        result = m.selection(sorted(FILES | {'docs/r06-migration-inventory.json'}))
        self.assertFalse(result['r06_offline'])
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('  affected-platform-offline:', workflow)
        job = workflow.split('  affected-platform-offline:', 1)[1].split('\n  affected-', 1)[0]
        self.assertIn('scripts/test-r06-inventory.py', job)
        self.assertIn('scripts/test-r06-readiness.py', job)
        self.assertNotIn('scripts/test-r04-authority.py', job)

    def test_unknown_authority_producer_denied(self):
        with self.assertRaises(ValueError):
            m.selection(['src/Enginia360.Api/PlatformAdministration/Unknown.cs'])

    def test_mixed_real_producer_keeps_consumers(self):
        result = m.selection(['scripts/owner-platform-authority.py', 'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'])
        self.assertTrue(result['platform_authority'])
        self.assertTrue(result['r04a'])
if __name__ == '__main__':
    unittest.main()
