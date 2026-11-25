"""Real Chromium geometry over actual Catalog component trees (mock API/UI primitives)."""
import json
import os
from pathlib import Path
import subprocess
import unittest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
NODE = os.environ.get('NODE', '/root/.hermes/tools/node-26.7.0-linux-x64/bin/node')
CHROMIUM = os.environ.get('CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome')

class CatalogSpacing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run = subprocess.run([NODE, '--experimental-strip-types', 'tests/catalog-spacing-render.ts'], cwd=ROOT/'frontend', capture_output=True, text=True, check=True)
        cls.data = json.loads(run.stdout)
        cls.p = sync_playwright().start()
        cls.browser = cls.p.chromium.launch(executable_path=CHROMIUM, headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.p.stop()

    def test_catalog_heading_has_same_gap_as_general_list(self):
        for width in (1440, 390):
            page = self.browser.new_page(viewport={'width':width,'height':900})
            # General list uses the real .workspace parent and direct heading/card siblings.
            reference = '<section class="workspace"><div class="page-heading"><h1>Tipi di magazzino</h1><button>Nuovo</button></div><div class="card"><div class="table-toolbar">Tabella</div></div></section>'
            page.set_content('<style>'+self.data['css']+'</style>'+reference)
            measure = """() => { const h=document.querySelector('.page-heading').getBoundingClientRect(); const c=document.querySelector('.table-toolbar').parentElement.getBoundingClientRect(); return {gap:c.top-h.bottom, heading:h.toJSON(), card:c.toJSON(), button:!!document.querySelector('.page-heading button'), width:document.documentElement.clientWidth}; }"""
            ref = page.evaluate(measure)
            self.assertAlmostEqual(ref['gap'],16,delta=.1)
            for resource, markup in self.data['pages'].items():
                with self.subTest(width=width, resource=resource):
                    page.set_content('<style>'+self.data['css']+'</style><section class="workspace">'+markup+'</section>')
                    result=page.evaluate(measure)
                    print(json.dumps({'viewport':width,'resource':resource,'referenceGap':ref['gap'],'gap':result['gap'],'button':result['button'],'heading':result['heading'],'card':result['card']}))
                    self.assertAlmostEqual(result['gap'],ref['gap'],delta=.1)
                    self.assertEqual(result['button'],resource!='catalog-numbering')
                    self.assertGreaterEqual(result['heading']['left'],0)
                    self.assertLessEqual(result['heading']['right'],width)
            page.close()

if __name__=='__main__': unittest.main(verbosity=2)
