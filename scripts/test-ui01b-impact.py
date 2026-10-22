#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('impact',ROOT/'scripts/select-ci-impact.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
class UI01bImpact(unittest.TestCase):
    def test_every_new_runtime_layer_selects_actual_editor_acceptance_and_direct_contracts(self):
        paths=['web/src/ui01/runtime/WorkshopRuntime.tsx','web/ui01-runtime.html','web/vite.ui01-runtime.config.ts','web/nginx.ui01b-test.conf','compose.ui01b-test.yaml','scripts/run-ui01b-tests.py','scripts/test-ui01b-wiring.py','scripts/test-ui01b-impact.py','tests/browser/ui01b-acceptance.cjs']
        for path in paths:
            with self.subTest(path=path):
                result=module.selection([path]); self.assertTrue(result.get('ui01b')); self.assertTrue(result['ui_tests']); self.assertTrue(result['ui_build']); self.assertTrue(result['migrations']); self.assertIn('WorkshopBoundaryTests',result['api_filter']); self.assertIn('CommercialCalculationTests',result['api_filter']); self.assertNotIn('AccountingBoundaryTests',result['api_filter']); self.assertFalse(result['full_architecture'])
    def test_workflow_executes_new_browser_not_merely_build_or_skip(self):
        text=(ROOT/'.github/workflows/ci.yml').read_text()
        self.assertIn("needs.impact.outputs.ui01b == 'true'",text)
        self.assertIn('timeout 600 python3 scripts/run-ui01b-tests.py',text)
        self.assertIn('npm run build:ui01-runtime',text)
        self.assertIn('python3 scripts/test-ui01b-impact.py',text)
    def test_static_prototype_and_docs_do_not_activate_editor(self):
        for path in ['web/src/ui01/WorkshopEditor.tsx','docs/ui01b-verification.md']:
            self.assertFalse(module.selection([path]).get('ui01b',False))
if __name__=='__main__': unittest.main()
