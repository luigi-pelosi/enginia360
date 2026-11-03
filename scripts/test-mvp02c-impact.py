#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('impact', ROOT / 'scripts/select-ci-impact.py')
assert spec and spec.loader
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FILES = {'frontend/app/organization/page.tsx', 'frontend/components/organization-workspace.tsx', 'frontend/lib/organization.ts', 'frontend/lib/private-backend.ts', 'frontend/tests/organization.test.tsx', 'frontend/tests/private-backend.test.ts', 'scripts/run-mvp02c-tests.py', 'scripts/test-mvp02c-impact.py', 'tests/browser/mvp02c-organization.cjs', 'compose.mvp02c-test.yaml', 'tests/fixtures/nginx.mvp02c.conf'}

class ImpactTests(unittest.TestCase):

    def test_finite_new_ui_selects_real_auth_and_organization_consumers(self):
        for p in FILES:
            with self.subTest(path=p):
                r = m.selection([p])
                self.assertTrue(r['authenticated_organization'])
                self.assertTrue(r['frontend'])
                self.assertTrue(r['organization_administration'])
                self.assertTrue(r['browser'])
                self.assertIn('BrowserSessionTests', r['api_filter'])
                self.assertFalse(r['full_architecture'])
                self.assertFalse(r['ui01b'])

    def test_bounded_ui_composition_keeps_foundation_partition_not_unrelated_erp(self):
        r = m.selection(sorted(FILES | {'frontend/app/globals.css', 'frontend/components/shell.tsx', 'frontend/app/domains/[domain]/page.tsx', 'frontend/package.json', 'scripts/select-ci-impact.py', '.github/workflows/ci.yml', 'docs/mvp-delivery-plan.md', 'docs/mvp02c-authenticated-organization.md'}))
        self.assertTrue(r['platform_foundation_only'])

    def test_ci_executes_exact_auth_ui_runtime_both_pools_and_retains_evidence(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assertIn('      authenticated_organization:', text)
        self.assertIn('scripts/test-mvp02c-impact.py', text)
        self.assertIn('  affected-authenticated-organization:', text)
        job = text.split('  affected-authenticated-organization:', 1)[1].split('\n  affected-', 1)[0]
        for token in ["github.event_name == 'workflow_dispatch'", "needs.impact.outputs.authenticated_organization == 'true'", 'scripts/run-mvp02c-tests.py', 'MVP02C_POOL_SIZE=1', 'actions/upload-artifact@v4', '--evidence-dir']:
            self.assertIn(token, job)

    def test_ui_runtime_has_no_skip_acceptance_switch(self):
        runner = (ROOT / 'scripts/run-mvp02c-tests.py').read_text()
        self.assertNotIn('--sql-only', runner)
        self.assertNotIn('--sql-test', runner)

    def test_shared_direct_producers_retain_authenticated_ui_consumer(self):
        for path in ('frontend/app/globals.css','frontend/components/shell.tsx','frontend/package-lock.json','frontend/Dockerfile','src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs','src/Enginia360.Api/PlatformAdministration/OrganizationAdministration.cs','scripts/run-r00b-tests.py','database/runtime/migrations/0037_organization_administration.sql'):
            with self.subTest(path=path):
                self.assertTrue(m.selection([path]).get('authenticated_organization',False))
        self.assertFalse(m.selection(['.github/workflows/ci.yml']).get('authenticated_organization',False))
        self.assertFalse(m.selection(['frontend/app/page.tsx']).get('authenticated_organization',False))

    def test_mixed_retains_consumers(self):
        r = m.selection(['frontend/lib/organization.ts', 'src/Modules/Inventory/Enginia360.Inventory/InventoryModule.cs'])
        self.assertTrue(r['authenticated_organization'])
        self.assertTrue(r['r04a'])

    def test_unmapped_paths_refused(self):
        for p in ['frontend/app/other/page.tsx', 'frontend/lib/unmapped-auth.ts', 'tests/fixtures/unmapped-auth.js']:
            with self.assertRaises(ValueError):
                m.selection([p])
if __name__ == '__main__':
    unittest.main()
