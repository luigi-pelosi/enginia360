#!/usr/bin/env python3
"""UI01.b opt-in build and strict CSP contract."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class RuntimeWiring(unittest.TestCase):
    def test_editor_dispatch_executes_paused_database_term_cleanup(self):
        workflow = (ROOT/'.github/workflows/ci.yml').read_text().split('  affected-editor:\n')[1].split('  runtime-migrations:\n')[0]
        self.assertIn('timeout 300 python3 scripts/test-r00b-lifecycle.py --actual --editor', workflow)
    def test_separate_build_never_imports_prototype_into_bootstrap(self):
        self.assertIn('build:ui01-runtime', (ROOT/'web/package.json').read_text())
        self.assertIn('dist-ui01-runtime', (ROOT/'web/vite.ui01-runtime.config.ts').read_text())
        for path in ('web/src/App.tsx','web/src/main.tsx','web/index.html'):
            self.assertNotIn('ui01/runtime', (ROOT/path).read_text())
    def test_narrow_csp_static_css_and_per_response_style_nonce(self):
        text = (ROOT/'web/nginx.ui01b-test.conf').read_text()
        self.assertNotIn('unsafe-inline', text)
        self.assertIn("style-src 'self' 'nonce-$request_id'", text)
        self.assertIn('sub_filter __STYLE_NONCE__ $request_id', text)
        source = (ROOT/'web/src/ui01/runtime/main.tsx').read_text()
        self.assertIn('zeroRuntime: true', source)
        self.assertIn('antd/dist/antd.css', source)
        self.assertIn('csp={{ nonce }}', source)
if __name__ == '__main__': unittest.main()
