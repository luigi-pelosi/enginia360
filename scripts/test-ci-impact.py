#!/usr/bin/env python3
"""Owner policy: deterministic changed-file impact, never blanket architecture delivery."""
import ast
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT/'scripts/select-ci-impact.py'


def select(paths):
    assert SELECTOR.exists(), 'deterministic change-impact selector missing'
    result = subprocess.run([sys.executable,str(SELECTOR),'--paths-json',json.dumps(paths)],cwd=ROOT,text=True,capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr)
    return json.loads(result.stdout)


def validate_workflow(text):
    trigger = text.split('concurrency:',1)[0]
    assert '  push:' not in trigger
    assert '  pull_request:' in trigger
    assert 'full_architecture:' in trigger and 'default: false' in trigger
    assert 'python3 scripts/select-ci-impact.py' in text
    assert 'python3 scripts/test-ci-impact.py' in text
    assert 'run: timeout 600 python3 scripts/run-r00b-tests.py' in text
    assert "needs.impact.outputs.browser == 'true'" in text
    assert "needs.impact.outputs.migrations == 'true'" in text
    for job in ('runtime-migrations','verify'):
        block = text.split('  '+job+':\n',1)[1]
        header = block.split('    steps:',1)[0]
        assert "if: github.event_name == 'workflow_dispatch' && inputs.full_architecture" in header, 'legacy architecture must require explicit exception'
    assert 'npm run build:ui01' in text
    assert 'dotnet test tests/Enginia360.Api.Tests -c Release --no-restore --filter "$API_FILTER"' in text


class ImpactTests(unittest.TestCase):
    def test_shared_master_search_owners_select_actual_editor_and_scoped_api(self):
        for path in ('src/Modules/Vehicles/Enginia360.Vehicles/VehiclesModule.cs',
                     'src/Modules/Vehicles/Enginia360.Vehicles.Contracts/Contracts.cs',
                     'src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs',
                     'src/Modules/Catalog/Enginia360.Catalog.Contracts/Contracts.cs',
                     'src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs',
                     'src/Modules/Workshop/Enginia360.Workshop/WorkshopModule.cs'):
            result = select([path])
            self.assertTrue(result['ui01b'])
            self.assertTrue(result['migrations'])
            self.assertIn('WorkshopBoundaryTests', result['api_filter'])
            self.assertIn('CounterpartyArchitectureTests', result['api_filter'])
            self.assertNotIn('AccountingBoundaryTests', result['api_filter'])
            self.assertFalse(result['full_architecture'])

    def test_browser_auth_selects_its_security_and_direct_dependencies_only(self):
        selection = select(['src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs'])
        self.assertTrue(selection['browser'])
        self.assertTrue(selection['migrations'])
        self.assertTrue(selection['ui_build'])
        self.assertFalse(selection['ui_tests'])
        self.assertIn('BrowserSessionTests',selection['api_filter'])
        self.assertIn('ExternalIdentityAuthenticationTests',selection['api_filter'])
        self.assertNotIn('AccountingBoundaryTests',selection['api_filter'])
        self.assertFalse(selection['full_architecture'])

    def test_selector_workflow_and_dependency_changes_cannot_skip_new_acceptance(self):
        for path in ['scripts/select-ci-impact.py','.github/workflows/ci.yml','src/Enginia360.Api/packages.lock.json',
                     'scripts/apply-runtime-migrations.py','tests/browser/package-lock.json','web/nginx.r00b-test.conf']:
            with self.subTest(path=path):
                selection = select([path])
                self.assertTrue(selection['browser'])
                self.assertTrue(selection['migrations'])

    def test_r01_own_context_and_shell_select_real_revocation_acceptance(self):
        for path in ('src/Enginia360.Api/OrganizationAccess/OrganizationAccessModule.cs',
                     'web/runtime-access.html','web/runtime-access.js','tests/browser/acceptance.cjs',
                     'scripts/run-r00b-tests.py'):
            with self.subTest(path=path):
                result = select([path])
                self.assertTrue(result['browser'])
                self.assertTrue(result['migrations'])
                self.assertTrue(result['ui_build'])
                self.assertIn('AuthorizedContextContractTests', result['api_filter'])
                self.assertNotIn('AccountingBoundaryTests', result['api_filter'])
                self.assertFalse(result['full_architecture'])

    def test_limited_grant_ownership_and_root_tool_select_security_acceptance(self):
        for path in ('src/Enginia360.Api/OrganizationAccess/LimitedGrantAdministration.cs',
                     'scripts/owner-operative-mandate.py','scripts/test-r01b-grants.py',
                     'tests/Enginia360.Api.Tests/LimitedGrantAdministrationTests.cs'):
            result=select([path])
            self.assertTrue(result['browser'])
            self.assertTrue(result['migrations'])
            self.assertIn('LimitedGrantAdministrationTests',result['api_filter'])
            self.assertNotIn('AccountingBoundaryTests',result['api_filter'])
            self.assertFalse(result['full_architecture'])

    def test_new_grant_sql_and_pool_cases_are_executable_targeted_dependencies(self):
        text=(ROOT/'scripts/run-r00a-tests.py').read_text()
        def validate(source):
            suite_loops=[node for node in ast.walk(ast.parse(source)) if isinstance(node,ast.For)
                         and isinstance(node.target,ast.Name) and node.target.id=='suite']
            self.assertEqual(len(suite_loops),1)
            self.assertIn('scripts/test-r01b-grants.py',ast.literal_eval(suite_loops[0].iter))
            self.assertIn('FullyQualifiedName~LimitedGrantAdministrationTests',(ROOT/'runtime-pool-test.Dockerfile').read_text())
            copy=next(line for line in (ROOT/'migrator.runtime.Dockerfile').read_text().splitlines() if line.startswith('COPY scripts/'))
            self.assertIn('scripts/test-r01b-grants.py',copy.split())
            self.assertIn('scripts/owner-operative-mandate.py',copy.split())
        validate(text)
        with self.assertRaises(AssertionError):
            validate(text.replace(", 'scripts/test-r01b-grants.py'",''))

    def test_documentation_guard_change_runs_in_impact_without_architecture(self):
        result = select(['scripts/test-c00-consistency.py'])
        self.assertEqual(result['api_filter'], '')
        self.assertFalse(result['browser'])
        self.assertFalse(result['full_architecture'])

    def test_docs_only_do_not_select_blanket_runtime(self):
        selection = select(['docs/r00b-browser-session.md'])
        self.assertFalse(selection['browser'])
        self.assertFalse(selection['migrations'])
        self.assertEqual(selection['api_filter'],'')
        self.assertFalse(selection['full_architecture'])

    def test_ui_source_selects_ui_tests_without_historical_backend_suites(self):
        selection = select(['web/src/ui01/App.tsx'])
        self.assertTrue(selection['ui_tests'])
        self.assertFalse(selection['browser'])
        self.assertEqual(selection['api_filter'],'')

    def test_selection_is_stable_deduplicated_and_unknown_code_fails_closed(self):
        paths = ['web/runtime-access.js','src/Enginia360.Api/Program.cs']
        self.assertEqual(select(paths),select(list(reversed(paths))+paths))
        with self.assertRaises(ValueError):
            select(['src/Modules/Unknown/NewPolicy.cs'])
        with self.assertRaises(ValueError):
            select(['../outside'])

    def test_workflow_has_actual_bounded_browser_runner_and_explicit_full_exception(self):
        text = (ROOT/'.github/workflows/ci.yml').read_text()
        validate_workflow(text)
        for original in ['run: timeout 600 python3 scripts/run-r00b-tests.py',"needs.impact.outputs.browser == 'true'",'python3 scripts/select-ci-impact.py']:
            with self.assertRaises(AssertionError):
                validate_workflow(text.replace(original,'removed'))


if __name__ == '__main__':
    unittest.main()
