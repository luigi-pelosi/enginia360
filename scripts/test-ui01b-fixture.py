#!/usr/bin/env python3
"""Run as an unprivileged user: extending R00 fixture must not rely on root bypassing mode0444."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ui01b',ROOT/'scripts/run-ui01b-tests.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
class FixturePermissions(unittest.TestCase):
    def test_extends_readonly_base_fixture_before_mounting_readonly_for_browser(self):
        self.assertNotEqual(os.geteuid(),0,'test must exercise real nonroot permissions')
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)
            sql=module.fixtures(state,'synthetic-test-only')
            value=json.loads((state/'browser.json').read_text())
            self.assertEqual(len(value['workshop']),3)
            self.assertIn('workshop.document_types',sql)
            self.assertEqual((state/'browser.json').stat().st_mode & 0o777,0o444)
if __name__=='__main__': unittest.main()
