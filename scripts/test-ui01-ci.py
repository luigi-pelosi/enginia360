#!/usr/bin/env python3
"""UI01.a guard: the prototype build is verified in CI and stays out of the default public bundle."""
from pathlib import Path

workflow = Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
package = Path('web/package.json').read_text(encoding='utf-8')
index_html = Path('web/index.html').read_text(encoding='utf-8')
prototype_html = Path('web/ui01.html').read_text(encoding='utf-8')
app = Path('web/src/App.tsx').read_text(encoding='utf-8')
main = Path('web/src/main.tsx').read_text(encoding='utf-8')

assert 'npm run build:ui01' in workflow, 'CI must build the UI01.a prototype explicitly'
assert '"build:ui01"' in package and 'vite.ui01.config.ts' in package
assert '"antd": "6.6.7"' in package, 'antd must stay pinned exactly'
assert 'ui01' not in index_html, 'the default public entry must not load the prototype'
assert 'ui01' not in app and 'ui01' not in main, 'default bootstrap routing must not reference the prototype'
assert '/src/ui01/main.tsx' in prototype_html
for flag in ('VITE_B02_TEST_UI=true npm run build', 'VITE_B05_TEST_UI=true npm run build', 'VITE_B10_TEST_UI=true npm run build'):
    assert flag in workflow, f'existing private UI build must be preserved: {flag}'
print('UI01.a CI guard: OK')
