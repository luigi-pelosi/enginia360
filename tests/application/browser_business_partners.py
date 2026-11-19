"""Browser reale BP su immagini candidate e database effimero del runner.

Origine logica HTTPS via inoltro loopback: nessuna attestazione TLS.
"""
import http.client
import json
import os
from pathlib import Path
import unittest
import urllib.request
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect
import run_business_partner_proof as runner

STATE = json.loads((runner.EVIDENCE/'state.json').read_text())
os.environ.update(ENGINIA360_BP_PROOF='1', ENGINIA360_TEST_BASE=runner.ORIGIN,
                  ENGINIA360_TEST_ORIGIN=runner.ORIGIN, ENGINIA360_TEST_CREDENTIALS=STATE['credentials'])
class IsolatedTransport(urllib.request.HTTPSHandler):
    def https_open(self, request):
        if request.host != urlsplit(runner.ORIGIN).netloc:
            raise RuntimeError('Host estraneo alla prova')
        return self.do_open(lambda host, **kwargs: http.client.HTTPConnection('127.0.0.1', STATE['apiPort'], **kwargs), request)
original_opener = urllib.request.build_opener
urllib.request.build_opener = lambda *handlers: original_opener(IsolatedTransport(), *handlers)
from test_business_partners import BusinessPartnerTests


class BusinessPartnerBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not runner.verify_target(runner.DB) or not runner.verify_target(runner.API) or not runner.verify_target(runner.WEB):
            raise RuntimeError('Ambiente isolato BP mancante')
        BusinessPartnerTests.setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome', headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.case = BusinessPartnerTests('test_01_metadata_and_default_automatic_numbering')
        self.case.setUp()
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
        def forward(route):
            url = urlsplit(route.request.url)
            if url.netloc != urlsplit(runner.ORIGIN).netloc:
                raise RuntimeError('Host esterno non ammesso')
            port = STATE['apiPort'] if url.path.startswith('/api/') else STATE['webPort']
            response = route.fetch(url=f'http://127.0.0.1:{port}'+url.path+('?' + url.query if url.query else ''), headers={**route.request.all_headers(), 'host': url.netloc})
            route.fulfill(response=response)
        self.context.route(runner.ORIGIN+'/**', forward)
        self.page = self.context.new_page()
        self.errors = []
        self.mutations = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('request', lambda request: self.mutations.append(request) if request.method in ('POST', 'PUT', 'DELETE') and urlsplit(request.url).path.endswith('/save') else None)

    def tearDown(self):
        try:
            self.page.screenshot(path=str(runner.EVIDENCE/(self._testMethodName+'.png')), full_page=True)
            self.assertEqual(self.errors, [])
        finally:
            self.context.close()

    def login(self):
        self.page.goto(runner.ORIGIN, wait_until='networkidle')
        self.page.locator('#username').fill(self.case.credentials['username'])
        self.page.locator('#password').fill(self.case.credentials['password'])
        self.page.locator('#tenant-code').fill(self.case.code)
        self.page.get_by_role('button', name='Accedi', exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()

    def navigate(self):
        self.page.locator('nav').get_by_role('button', name='Business Partner', exact=True).click()
        expect(self.page.get_by_role('button', name='Nuovo Business Partner', exact=True)).to_be_visible()

    def test_04_vat_rejection_names_the_field_and_keeps_edits_for_correction(self):
        row = self.case.create('Ricambi verifica messaggi')
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Modifica Ricambi verifica messaggi', exact=True).click()
        self.page.locator('[data-action=add-tax]').click()
        field = self.page.locator('#bp-tax-0-value')
        field.fill('IT12345678901')
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as rejected:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(rejected.value.status, 400)
        self.assertEqual(rejected.value.json(), {'code': 'invalid_italian_vat', 'field': 'taxIdentifiers[0].value'})
        expect(self.page.locator('[data-slot=alert]')).to_contain_text('Identificativo fiscale 1 — Partita IVA')
        expect(self.page.locator('[data-slot=alert]')).to_contain_text('11 cifre, senza il prefisso IT')
        expect(field).to_have_attribute('aria-invalid', 'true')
        expect(field).to_have_attribute('aria-describedby', 'bp-tax-0-value-error')
        expect(self.page.locator('#bp-tax-0-value-error')).to_contain_text('11 cifre, senza il prefisso IT')
        expect(field).to_have_value('IT12345678901')
        self.assertEqual(self.case.read(row)['tax_identifiers'], [])
        field.fill('12345678901')
        expect(field).not_to_have_attribute('aria-invalid', 'true')
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as accepted:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(accepted.value.status, 200)
        detail = self.case.read(row)
        self.assertEqual(detail['tax_identifiers'][0]['normalized_value'], '12345678901')
        self.assertEqual(detail['version'], row['version'] + 1)
        self.assertEqual(detail['code'], row['code'])

    def test_01_complete_single_save_cancel_duplicate_and_archival(self):
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Nuovo Business Partner', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Alfa Ricambi dimostrativa')
        self.page.locator('[data-action=add-tax]').click()
        self.page.locator('#bp-tax-0-value').fill('12345678901')
        self.page.locator('[data-action=add-address]').click()
        for name, value in {'street':'Via Roma', 'street_number':'1', 'postal_code':'00100', 'city':'Roma', 'province':'RM'}.items():
            self.page.locator('#bp-address-0-'+name).fill(value)
        self.page.locator('#bp-address-0-BILLING').check()
        self.page.locator('#bp-address-0-BILLING-default').check()
        self.page.locator('[data-action=add-contact]').click()
        self.page.locator('#bp-contact-0-value').fill('ricambi@example.invalid')
        self.assertEqual(len(self.mutations), 0)
        expect(self.page.get_by_role('button', name='Salva', exact=True)).to_have_count(1)
        with self.page.expect_response(lambda response: response.request.method=='POST' and urlsplit(response.url).path.endswith('/save')) as saved:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 201)
        row = saved.value.json()
        expect(self.page.locator('tbody')).to_contain_text('Alfa Ricambi dimostrativa')
        self.assertEqual(len(self.mutations), 1)
        detail = self.case.read(row)
        self.assertEqual((len(detail['tax_identifiers']), len(detail['addresses']), len(detail['contact_channels'])), (1,1,1))
        self.assertEqual(detail['code'], 'BP-000001')
        self.page.get_by_role('button', name='Modifica Alfa Ricambi dimostrativa', exact=True).click()
        expect(self.page.locator('#bp-legal_name')).to_have_value('Alfa Ricambi dimostrativa')
        self.page.locator('#bp-legal_name').fill('Non salvata')
        self.page.get_by_role('button', name='Annulla', exact=True).click()
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(self.case.read(row)['legal_name'], 'Alfa Ricambi dimostrativa')
        self.page.get_by_role('button', name='Nuovo Business Partner', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Bozza duplicata')
        self.page.locator('[data-action=add-tax]').click(); self.page.locator('#bp-tax-0-value').fill('12345678901')
        with self.page.expect_response(lambda response: response.request.method=='POST' and urlsplit(response.url).path.endswith('/save')) as duplicate:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(duplicate.value.status, 409)
        expect(self.page.locator('#bp-legal_name')).to_have_value('Bozza duplicata')
        expect(self.page.locator('[data-slot=alert]')).to_be_visible()
        self.page.get_by_role('button', name='Annulla', exact=True).click()
        self.page.get_by_role('button', name='Modifica Alfa Ricambi dimostrativa', exact=True).click()
        self.page.locator('#bp-status').click(); self.page.get_by_role('option', name='Archiviato', exact=True).click()
        self.page.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.locator('tbody')).to_contain_text('Archiviato')
        self.assertEqual(self.case.read(row)['status'], 'ARCHIVED')
        self.assertEqual(self.page.get_by_role('button', name='Elimina Alfa Ricambi dimostrativa', exact=True).count(), 0)

    def test_02_numbering_configuration_real_save_then_frozen(self):
        self.login()
        self.page.locator('nav').get_by_role('button', name='Impostazioni', exact=True).click()
        expect(self.page.get_by_role('button', name='Numerazione Business Partner', exact=True)).to_have_count(0)
        self.page.get_by_role('button', name='Anagrafiche', exact=True).click()
        expect(self.page.locator('h1')).to_have_text('Anagrafiche')
        self.page.locator('#main').get_by_role('button', name='Business Partner', exact=True).click()
        expect(self.page.locator('h1')).to_have_text('Business Partner')
        self.page.get_by_role('button', name='Numerazione', exact=True).click()
        expect(self.page.locator('h1')).to_have_text('Numerazione')
        expect(self.page.locator('.eyebrow')).to_contain_text('Impostazioni')
        expect(self.page.locator('.eyebrow')).to_contain_text('Anagrafiche')
        expect(self.page.locator('.eyebrow')).to_contain_text('Business Partner')
        self.page.get_by_role('button', name='Torna ai Business Partner', exact=True).click()
        expect(self.page.locator('h1')).to_have_text('Business Partner')
        self.page.get_by_role('button', name='Numerazione', exact=True).click()
        expect(self.page.locator('#bp-numbering-prefix')).to_have_value('BP-')
        self.page.locator('#bp-numbering-prefix').fill('PART-')
        self.page.locator('#bp-numbering-padding').fill('4')
        self.page.locator('#bp-numbering-nextNumber').fill('50')
        self.page.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.locator('p[role=status]')).to_have_text('Modifiche salvate')
        config = self.case.root.request(self.case.numbering())[1]
        self.assertEqual((config['prefix'], config['padding'], config['nextNumber']), ('PART-',4,50))
        row = self.case.create('Codice configurato')
        self.assertEqual(row['code'], 'PART-0050')
        self.page.locator('#bp-numbering-prefix').fill('NO-')
        self.page.get_by_role('button', name='Salva', exact=True).click()
        # La revisione è cambiata dopo l'allocazione: prima conflitto, poi ricarica e blocco.
        expect(self.page.locator('[data-slot=alert]')).to_be_visible()
        self.page.get_by_role('button', name='Ricarica configurazione salvata', exact=True).click()
        expect(self.page.locator('#bp-numbering-prefix')).to_have_value('PART-')
        self.page.locator('#bp-numbering-prefix').fill('NO-')
        self.page.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.locator('[data-slot=alert]')).to_be_visible()
        expect(self.page.locator('#bp-numbering-prefix')).to_be_disabled()
        self.assertEqual(self.case.root.request(self.case.numbering())[1]['prefix'], 'PART-')

    def test_03_mobile_english_creation(self):
        self.context.add_cookies([{'name':'locale','value':'en','url':runner.ORIGIN}])
        self.page.set_viewport_size({'width':390,'height':844})
        self.page.goto(runner.ORIGIN, wait_until='networkidle')
        self.page.locator('#username').fill(self.case.credentials['username']); self.page.locator('#password').fill(self.case.credentials['password']); self.page.locator('#tenant-code').fill(self.case.code)
        self.page.get_by_role('button', name='Sign in', exact=True).click()
        # Il login ripristina la lingua preferita italiana: selezione esplicita dopo accesso.
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        self.context.add_cookies([{'name':'locale','value':'en','url':runner.ORIGIN}]); self.page.reload(wait_until='networkidle')
        trigger = self.page.locator('[data-sidebar=trigger]').first
        trigger.click()
        self.page.get_by_role('button', name='Business Partner', exact=True).click()
        self.page.get_by_role('button', name='New Business Partner', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Mobile partner')
        self.page.get_by_role('button', name='Save', exact=True).click()
        expect(self.page.locator('tbody')).to_contain_text('Mobile partner')
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)


if __name__ == '__main__':
    unittest.main(defaultTest='BusinessPartnerBrowserTests')
