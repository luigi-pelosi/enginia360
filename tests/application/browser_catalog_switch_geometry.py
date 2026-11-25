"""Chromium geometry of actual catalog component trees; UI primitives/API are fixtures."""
import json
import subprocess
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2]
NODE='/root/.hermes/tools/node-26.7.0-linux-x64/bin/node'
CHROME='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome'
class SwitchGeometry(unittest.TestCase):
 def test_geometry(self):
  data=json.loads(subprocess.check_output([NODE,'--experimental-strip-types','tests/catalog-switch-render.ts'],cwd=ROOT/'frontend',text=True))
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=CHROME,args=['--no-sandbox'])
   for width in (1440,390):
    page=browser.new_page(viewport={'width':width,'height':900})
    for key,markup in data['pages'].items():
     with self.subTest(width=width,form=key):
      page.set_content('<style>'+data['css']+'</style><main style="width:min(100% - 32px,640px);margin:auto">'+markup+'</main>')
      result=page.evaluate('''() => {const grid=document.querySelector('.grid');const field=document.querySelector('#catalog-is_active').parentElement;const r=x=>{const b=x.getBoundingClientRect();return {left:b.left,right:b.right,width:b.width}}; const s=getComputedStyle(field);return {grid:r(grid),field:r(field),border:s.borderTopWidth,display:s.display,disabled:document.querySelector('#catalog-is_active').disabled};}''')
      print(json.dumps({'viewport':width,'form':key,**result}))
      self.assertAlmostEqual(result['grid']['left'],result['field']['left'],delta=.1)
      self.assertAlmostEqual(result['grid']['right'],result['field']['right'],delta=.1)
      self.assertEqual(result['border'],'1px');self.assertEqual(result['display'],'flex')
      self.assertEqual(result['disabled'],key.endswith(':true'))
    page.close()
   browser.close()
if __name__=='__main__':unittest.main(verbosity=2)
