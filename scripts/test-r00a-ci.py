#!/usr/bin/env python3
"""Ensure CI really selects the R00.a PostgreSQL suite, never an offline skip."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def validate_ci(text):
    assert 'run: timeout 600 sh scripts/run-r00a-tests.sh' in text, 'R00.a runtime runner not selected in CI'
    assert 'python3 scripts/test-r00a-ci.py' in text, 'R00.a CI selection test missing'
    assert 'run: timeout 180 python3 scripts/test-r00a-lifecycle.py' in text, 'R00.a failure cleanup probes missing'

import importlib.util

class RunnerSafetyTests(unittest.TestCase):
    def test_cleanup_refuses_protected_or_ambiguous_project_names(self):
        path = ROOT / 'scripts/run-r00a-tests.py'
        self.assertTrue(path.exists(), 'guarded ephemeral lifecycle runner missing')
        spec = importlib.util.spec_from_file_location('r00a_runner', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in ('enginia360', 'enginia360-b02-manual', '', 'enginia360-r00a-../escape', 'enginia360-r00a-abc'):
            with self.assertRaises(ValueError):
                module.validate_project(name)
        module.validate_project('enginia360-r00a-0123456789ab')

import ast

def validate_runner(text):
    constants = {node.value for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert 'R00_MIGRATION_TESTS=1' in constants, 'real PostgreSQL test opt-in missing'
    assert 'scripts/test-r00-migrations.py' in constants, 'migration suite invocation missing'
    assert 'R00_POOL_CONNECTION' in constants, 'real Npgsql pool suite missing'

class CiSelectionTests(unittest.TestCase):
    def test_ci_runs_real_bounded_migrations(self):
        validate_ci((ROOT / '.github/workflows/ci.yml').read_text())
        runner = ROOT / 'scripts/run-r00a-tests.sh'
        self.assertTrue(runner.exists(), 'R00.a ephemeral runner missing')
        text = (ROOT / 'scripts/run-r00a-tests.py').read_text()
        validate_runner(text)
        self.assertNotIn("'compose.yaml'", text)
        self.assertIn('com.docker.compose.project', text)
        for literal in ('R00_MIGRATION_TESTS=1', 'scripts/test-r00-migrations.py', 'R00_POOL_CONNECTION'):
            with self.assertRaises(AssertionError):
                validate_runner(text.replace(literal, 'removed'))

    def test_removing_runner_or_guard_from_ci_is_detected(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        for command in ('run: timeout 600 sh scripts/run-r00a-tests.sh', 'python3 scripts/test-r00a-ci.py'):
            with self.assertRaises(AssertionError):
                validate_ci(text.replace(command, 'echo removed'))

if __name__ == '__main__':
    unittest.main()
