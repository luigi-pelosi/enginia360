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
            self.context.unroute_all(behavior='wait')
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

    def related(self, kind):
        return self.page.locator(f'[data-bp-related-editor={kind}]')

    def apply_related(self):
        self.page.locator('[data-action=apply-related]').click()
        expect(self.page.locator('[data-bp-related-editor]')).to_have_count(0)

    def test_05_bp_geography_completes_only_the_current_address_and_saves_explicitly(self):
        country = self.case.root.request('/api/data/countries', 'POST', {'name': 'Italia prova', 'iso_code': 'IT'})
        self.assertIn(country[0], (201, 409))
        country_id = country[1]['id'] if country[0] == 201 else next(item['id'] for item in self.case.root.request('/api/data/countries?pageSize=100')[1]['items'] if item['iso_code'] == 'IT')
        result = self.case.root.request('/api/data/cities', 'POST', {'country_id': country_id, 'name': 'Roma geografia prova', 'postal_code': '00123', 'province': 'RM'})
        self.assertIn(result[0], (201, 409))
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Nuovo Business Partner', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Partner autocompletamento')
        self.page.locator('[data-action=add-address]').click()
        self.page.locator('#bp-address-0-street').fill('Via manuale')
        self.page.locator('#bp-address-0-street_number').fill('17')
        city = self.page.locator('#bp-address-0-city')
        expect(city).to_have_attribute('role', 'combobox')
        with self.page.expect_response(lambda response: urlsplit(response.url).path == '/api/addresses/autocomplete' and 'field=city' in response.url) as found:
            city.fill('Roma geografia')
        self.assertEqual(found.value.status, 200)
        self.assertIn('resource=business-partners', found.value.url)
        expect(self.page.get_by_role('option', name='Roma geografia prova · 00123 · RM · Italia prova', exact=True)).to_be_visible()
        city.press('ArrowDown'); city.press('Enter')
        expect(city).to_have_value('Roma geografia prova')
        expect(self.page.locator('#bp-address-0-postal_code')).to_have_value('00123')
        expect(self.page.locator('#bp-address-0-province')).to_have_value('RM')
        expect(self.page.locator('#bp-address-0-street')).to_have_value('Via manuale')
        expect(self.page.locator('#bp-address-0-street_number')).to_have_value('17')

        postal = self.page.locator('#bp-address-0-postal_code')
        with self.page.expect_response(lambda response: urlsplit(response.url).path == '/api/addresses/autocomplete' and 'field=postal_code' in response.url) as postal_found:
            postal.fill('001')
        self.assertEqual(postal_found.value.status, 200)
        expect(self.page.get_by_role('option', name='Roma geografia prova · 00123 · RM · Italia prova', exact=True)).to_be_visible()
        postal.press('ArrowDown'); postal.press('Enter')
        expect(postal).to_have_value('00123')
        self.assertEqual(self.mutations, [], 'Nessuna scrittura alla selezione')
        self.apply_related()
        expect(self.page.locator('[data-bp-related-table=address]')).to_contain_text('Roma geografia prova')
        self.page.locator('[data-action=add-address]').click()
        expect(self.page.locator('#bp-address-1-city')).to_have_value('')
        self.page.locator('[data-action=cancel-related]').click()
        expect(self.page.locator('[data-bp-related-table=address] tbody tr')).to_have_count(1)
        with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith('/save')) as saved:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 201)
        row = self.case.read(saved.value.json())
        self.assertEqual(len(row['addresses']), 1)
        self.assertEqual((row['addresses'][0]['street'], row['addresses'][0]['street_number'], row['addresses'][0]['postal_code'], row['addresses'][0]['city']), ('Via manuale', '17', '00123', 'Roma geografia prova'))
        self.assertEqual(len(self.mutations), 1)

    def test_06_bp_geography_manual_fallback_remains_savable_on_mobile(self):
        row = self.case.create('Partner manuale mobile', addresses=[{'street': 'Via manuale', 'city': 'Roma', 'postal_code': '00100', 'province': 'RM', 'country_code': 'IT'}])
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.login()
        self.page.locator('[data-sidebar=trigger]').first.click()
        self.page.get_by_role('button', name='Business Partner', exact=True).click()
        self.page.get_by_role('button', name='Modifica Partner manuale mobile', exact=True).click()
        self.page.locator('[data-action=edit-address-0]').click()
        self.page.route('**/api/addresses/autocomplete?*', lambda route: route.fulfill(status=503, content_type='application/json', body='{"code":"server_error"}'))
        city = self.page.locator('#bp-address-0-city')
        with self.page.expect_response(lambda response: urlsplit(response.url).path == '/api/addresses/autocomplete'):
            city.fill('Località manuale')
        expect(self.page.locator('#bp-address-0-city-lookup-error')).to_contain_text('Puoi compilare a mano')
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as saved:
            self.apply_related()
        self.assertEqual(saved.value.status, 200)
        self.assertEqual(self.case.read(row)['addresses'][0]['city'], 'Località manuale')
        self.assertEqual(len(self.mutations), 1)

    def test_04_vat_rejection_names_the_field_and_keeps_edits_for_correction(self):
        row = self.case.create('Ricambi verifica messaggi')
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Modifica Ricambi verifica messaggi', exact=True).click()
        self.page.locator('[data-action=add-tax]').click()
        field = self.page.locator('#bp-tax-0-value')
        field.fill('IT12345678901')
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as rejected:
            self.page.locator('[data-action=apply-related]').click()
        self.assertEqual(rejected.value.status, 400)
        self.assertEqual(rejected.value.json(), {'code': 'invalid_italian_vat', 'field': 'taxIdentifiers[0].value'})
        expect(self.related('tax')).to_be_visible()
        expect(self.related('tax')).to_contain_text('Inserisci una partita IVA italiana di 11 cifre.')
        expect(field).to_have_attribute('aria-invalid', 'true')
        expect(field).to_have_attribute('aria-describedby', 'bp-tax-0-value-error')
        expect(self.page.locator('#bp-tax-0-value-error')).to_contain_text('Inserisci una partita IVA italiana di 11 cifre.')
        expect(field).to_have_value('IT12345678901')
        self.assertEqual(self.case.read(row)['tax_identifiers'], [])
        field.fill('12345678901')
        expect(field).not_to_have_attribute('aria-invalid', 'true')
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as accepted:
            self.apply_related()
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
        self.apply_related()
        self.page.locator('[data-action=add-address]').click()
        for name, value in {'street':'Via Roma', 'street_number':'1', 'postal_code':'00100', 'city':'Roma', 'province':'RM'}.items():
            self.page.locator('#bp-address-0-'+name).fill(value)
        self.page.locator('#bp-address-0-BILLING').check()
        self.page.locator('#bp-address-0-BILLING-default').check()
        self.apply_related()
        self.page.locator('[data-action=add-contact]').click()
        self.page.locator('#bp-contact-0-value').fill('ricambi@example.invalid')
        self.apply_related()
        self.assertEqual(len(self.mutations), 0)
        expect(self.page.get_by_role('button', name='Salva', exact=True)).to_have_count(1)
        with self.page.expect_response(lambda response: response.request.method=='POST' and urlsplit(response.url).path.endswith('/save')) as saved:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 201)
        row = saved.value.json()
        expect(self.page.get_by_role('button', name='Nuovo Business Partner', exact=True)).to_be_visible()
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
        self.apply_related()
        with self.page.expect_response(lambda response: response.request.method=='POST' and urlsplit(response.url).path.endswith('/save')) as duplicate:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(duplicate.value.status, 409)
        expect(self.related('tax')).to_be_visible()
        expect(self.related('tax')).to_contain_text('identificativo fiscale')
        self.page.locator('[data-action=cancel-related]').click()
        expect(self.page.locator('#bp-legal_name')).to_have_value('Bozza duplicata')
        self.page.get_by_role('button', name='Annulla', exact=True).click()
        self.page.get_by_role('button', name='Modifica Alfa Ricambi dimostrativa', exact=True).click()
        self.page.locator('#bp-status').click(); self.page.get_by_role('option', name='Archiviato', exact=True).click()
        self.page.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('button', name='Nuovo Business Partner', exact=True)).to_be_visible()
        expect(self.page.locator('tbody')).to_contain_text('Archiviato')
        self.assertEqual(self.case.read(row)['status'], 'ARCHIVED')
        self.assertEqual(self.page.get_by_role('button', name='Elimina Alfa Ricambi dimostrativa', exact=True).count(), 0)

    def test_07_related_tables_crud_is_compact_cancelable_and_atomic(self):
        row = self.case.create('Partner tabelle compatte',
            taxIdentifiers=[{'country_code': 'IT', 'identifier_type': 'VAT', 'value': '12345678901'}],
            addresses=[{'label': 'Fatturazione', 'street': 'Via Roma', 'street_number': '17', 'city': 'Roma', 'postal_code': '00100', 'province': 'RM', 'country_code': 'IT', 'usages': [{'usage': 'BILLING', 'is_default': True}]}],
            contactChannels=[{'channel_type': 'EMAIL', 'value': 'office@example.invalid', 'purpose': 'Ufficio', 'is_primary': True}])
        before = self.case.read(row)
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Modifica Partner tabelle compatte', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Identità ancora non salvata')
        action_columns = []
        for kind, text in [('tax', '12345678901'), ('address', '00100'), ('contact', 'office@example.invalid')]:
            table = self.page.locator(f'[data-bp-related-table={kind}]')
            expect(table).to_be_visible(); expect(table).to_contain_text(text)
            expect(table.locator('input,textarea,select')).to_have_count(0)
            expect(self.page.locator(f'[data-action=edit-{kind}-0]')).to_be_visible()
            expect(self.page.locator(f'[data-action=details-{kind}-0]')).to_be_visible()
            expect(self.page.locator(f'[data-action=remove-{kind}-0]')).to_be_visible()
            bounds = table.locator('tbody tr').bounding_box()
            self.assertLessEqual(bounds['height'], 120, 'Le righe devono restare compatte')
            header = table.locator('thead th').last
            cell = table.locator('tbody tr td').last
            action_columns.append(header.bounding_box())
            self.assertAlmostEqual(header.bounding_box()['width'], 120, delta=1)
            self.assertAlmostEqual(cell.bounding_box()['width'], 120, delta=1)
            self.assertEqual(header.evaluate('(el)=>getComputedStyle(el).textAlign'), 'right')
            last_button = cell.locator('button').last
            self.assertAlmostEqual(cell.bounding_box()['x'] + cell.bounding_box()['width'] - 8, last_button.bounding_box()['x'] + last_button.bounding_box()['width'], delta=1)
            for button in cell.locator('button').all():
                self.assertEqual(button.inner_text().strip(), '')
                self.assertTrue(button.get_attribute('aria-label'))
                self.assertEqual(button.get_attribute('title'), button.get_attribute('aria-label'))
        self.assertAlmostEqual(max(item['x'] for item in action_columns), min(item['x'] for item in action_columns), delta=1)
        self.page.screenshot(path=str(runner.EVIDENCE/'related-tables-desktop.png'), full_page=True)
        self.page.locator('[data-action=add-tax]').click()
        self.page.locator('#bp-tax-1-value').fill('99999999999')
        self.page.locator('[data-action=cancel-related]').click()
        expect(self.page.locator('[data-bp-related-table=tax]')).not_to_contain_text('99999999999')
        self.page.locator('[data-action=edit-tax-0]').click()
        self.page.locator('#bp-tax-0-value').fill('99999999999')
        self.page.keyboard.press('Escape')
        expect(self.related('tax')).to_have_count(0)
        expect(self.page.locator('[data-bp-related-table=tax]')).to_contain_text('12345678901')
        self.page.locator('[data-action=details-tax-0]').click()
        expect(self.page.locator('#bp-tax-0-value')).to_be_disabled()
        expect(self.related('tax').locator('[data-action=apply-related]')).to_have_count(0)
        self.page.keyboard.press('Escape')
        self.page.locator('[data-action=edit-contact-0]').click()
        self.page.locator('#bp-contact-0-value').fill('changed@example.invalid')
        self.page.locator('#bp-contact-0-value').press('Enter')
        expect(self.related('contact')).to_have_count(0)
        expect(self.page.locator('[data-bp-related-table=contact]')).to_contain_text('changed@example.invalid')
        detail = self.case.read(row)
        self.assertEqual(detail['contact_channels'][0]['value'], 'changed@example.invalid')
        self.assertEqual(detail['legal_name'], before['legal_name'], 'La riga non salva i dati principali pendenti')
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(self.mutations[0].post_data_json['values'], {})
        self.assertNotIn('addresses', self.mutations[0].post_data_json)
        self.assertNotIn('taxIdentifiers', self.mutations[0].post_data_json)
        for kind, field_id, value in [('tax', 'bp-tax-0-value', '98765432109'), ('address', 'bp-address-0-street', 'Via aggiornata')]:
            self.page.locator(f'[data-action=edit-{kind}-0]').click()
            self.page.locator('#'+field_id).fill(value)
            with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as edited:
                self.apply_related()
            self.assertEqual(edited.value.status, 200)
        detail = self.case.read(row)
        self.assertEqual(detail['tax_identifiers'][0]['value'], '98765432109')
        self.assertEqual(detail['addresses'][0]['street'], 'Via aggiornata')
        self.page.locator('[data-action=remove-address-0]').click()
        self.page.get_by_role('alertdialog').get_by_role('button', name='Annulla', exact=True).click()
        expect(self.page.locator('[data-bp-related-table=address]')).to_contain_text('Via aggiornata')
        for kind in ('tax', 'address', 'contact'):
            self.page.locator(f'[data-action=remove-{kind}-0]').click()
            expect(self.page.get_by_role('alertdialog')).to_be_visible()
            with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as removed:
                self.page.locator('[data-action=confirm-remove-related]').click()
            self.assertEqual(removed.value.status, 200)
            expect(self.page.get_by_role('alertdialog')).to_have_count(0)
            collection = {'tax': 'tax_identifiers', 'address': 'addresses', 'contact': 'contact_channels'}[kind]
            self.assertEqual(self.case.read(row)[collection], [], 'Rimozione persistita senza Salva generale')
        for kind in ('tax', 'address', 'contact'):
            self.assertAlmostEqual(self.page.locator(f'[data-bp-related-table={kind}] thead th').last.bounding_box()['width'], 120, delta=1)
        detail = self.case.read(row)
        self.assertEqual(detail['version'], before['version'] + 6)
        self.assertEqual(detail['legal_name'], before['legal_name'])
        self.assertEqual(len(self.mutations), 6)
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as saved:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 200)
        detail = self.case.read(row)
        self.assertEqual((detail['tax_identifiers'], detail['addresses'], detail['contact_channels']), ([], [], []))
        self.assertEqual(detail['version'], before['version'] + 7)
        self.assertEqual(detail['legal_name'], 'Identità ancora non salvata')
        self.assertEqual(len(self.mutations), 7)

    def test_11_related_conflict_preserves_row_and_parent_cancel_does_not_undo_commits(self):
        row = self.case.create('Partner concorrenza righe', contactChannels=[{'channel_type': 'EMAIL', 'value': 'original@example.invalid', 'purpose': 'Ufficio', 'is_primary': True}])
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Modifica Partner concorrenza righe', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Nome solo nella bozza')
        self.page.locator('[data-action=edit-contact-0]').click()
        self.page.locator('#bp-contact-0-value').fill('pending@example.invalid')
        status, external = self.case.update(row, {'legal_name': 'Nome modificato altrove'})
        self.assertEqual(status, 200)
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as rejected:
            self.page.locator('[data-action=apply-related]').click()
        self.assertEqual(rejected.value.status, 409)
        expect(self.related('contact')).to_be_visible()
        expect(self.page.locator('#bp-contact-0-value')).to_have_value('pending@example.invalid')
        expect(self.page.locator('#bp-legal_name')).to_have_value('Nome solo nella bozza')
        self.assertEqual(self.case.read(row), external)
        self.page.locator('[data-action=cancel-related]').click()
        self.page.locator('[data-action=remove-contact-0]').click()
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as rejected_delete:
            self.page.locator('[data-action=confirm-remove-related]').click()
        self.assertEqual(rejected_delete.value.status, 409)
        expect(self.page.get_by_role('alertdialog')).to_be_visible()
        self.assertEqual(self.case.read(row), external)
        self.page.get_by_role('alertdialog').get_by_role('button', name='Annulla', exact=True).click()
        self.page.get_by_role('button', name='Annulla', exact=True).click()
        self.page.reload(wait_until='networkidle'); self.navigate()
        self.page.get_by_role('button', name='Modifica Nome modificato altrove', exact=True).click()
        self.page.locator('[data-action=remove-contact-0]').click()
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path.endswith('/save')) as removed:
            self.page.locator('[data-action=confirm-remove-related]').click()
        self.assertEqual(removed.value.status, 200)
        expect(self.page.get_by_role('alertdialog')).to_have_count(0)
        self.page.get_by_role('button', name='Annulla', exact=True).click()
        self.page.reload(wait_until='networkidle'); self.navigate()
        self.page.get_by_role('button', name='Modifica Nome modificato altrove', exact=True).click()
        expect(self.page.locator('[data-action=remove-contact-0]')).to_have_count(0)
        detail = self.case.read(row)
        self.assertEqual(detail['contact_channels'], [])
        self.assertEqual(detail['version'], row['version'] + 2)
        self.assertEqual(detail['legal_name'], 'Nome modificato altrove')

    def test_08_reader_can_open_related_details_without_mutation_controls(self):
        row = self.case.create('Partner sola lettura', taxIdentifiers=[{'country_code': 'IT', 'identifier_type': 'VAT', 'value': '12345678901'}])
        reader, _ = self.case.actor(['business-partners.read'])
        cookies = next(handler.cookiejar for handler in reader.opener.handlers if hasattr(handler, 'cookiejar'))
        self.context.add_cookies([{'name': cookie.name, 'value': cookie.value, 'url': runner.ORIGIN} for cookie in cookies])
        self.page.goto(runner.ORIGIN, wait_until='networkidle')
        self.page.locator('nav').get_by_role('button', name='Business Partner', exact=True).click()
        self.page.get_by_role('button', name='Dettagli Partner sola lettura', exact=True).click()
        expect(self.page.locator('[data-action=add-tax]')).to_have_count(0)
        expect(self.page.locator('[data-action=edit-tax-0]')).to_have_count(0)
        expect(self.page.locator('[data-action=remove-tax-0]')).to_have_count(0)
        cell = self.page.locator('[data-bp-related-table=tax] tbody td').last
        self.assertAlmostEqual(cell.bounding_box()['width'], 120, delta=1)
        self.assertEqual(cell.locator('button').count(), 1)
        self.page.locator('[data-action=details-tax-0]').click()
        expect(self.page.locator('#bp-tax-0-value')).to_have_value('12345678901')
        expect(self.page.locator('#bp-tax-0-value')).to_be_disabled()
        expect(self.related('tax').locator('[data-action=apply-related]')).to_have_count(0)
        self.assertEqual(self.mutations, [])
        self.assertEqual(self.case.read(row)['version'], row['version'])

    def test_09_create_button_shares_responsive_page_heading(self):
        self.login()
        for locale, create, cancel in (('it', 'Nuovo Business Partner', 'Annulla'), ('en', 'New Business Partner', 'Cancel')):
            self.page.set_viewport_size({'width': 1440, 'height': 1000})
            self.context.add_cookies([{'name': 'locale', 'value': locale, 'url': runner.ORIGIN}])
            self.page.reload(wait_until='networkidle')
            self.page.locator('nav').get_by_role('button', name='Business Partner', exact=True).click()
            header = self.page.locator('#main .page-heading')
            button = header.get_by_role('button', name=create, exact=True)
            expect(header).to_have_count(1)
            expect(button).to_be_visible()
            for width in (1440, 1024, 390):
                self.page.set_viewport_size({'width': width, 'height': 1000})
                title = header.locator('h1').locator('..').bounding_box()
                action = button.bounding_box()
                bounds = header.bounding_box()
                if width >= 1024:
                    self.assertAlmostEqual(title['y'] + title['height']/2, action['y'] + action['height']/2, delta=1)
                self.assertAlmostEqual(action['x'] + action['width'], bounds['x'] + bounds['width'], delta=1)
                self.assertGreaterEqual(action['x'], bounds['x'])
                self.assertLessEqual(action['y'] + action['height'], bounds['y'] + bounds['height'] + 1)
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                self.page.screenshot(path=str(runner.EVIDENCE/f'heading-{locale}-{width}.png'))
            button.click()
            expect(self.page.locator('h1')).to_have_count(1)
            expect(self.page.get_by_text('La bozza può essere incompleta.', exact=False)).to_have_count(0)
            expect(self.page.get_by_text('Drafts may be incomplete.', exact=False)).to_have_count(0)
            expect(self.page.locator('#bp-status')).to_be_visible()
            expect(self.page.get_by_role('button', name=create, exact=True)).to_have_count(0)
            self.page.get_by_role('button', name=cancel, exact=True).click()
            expect(button).to_be_visible()
        self.assertEqual(self.mutations, [])

    def test_10_permission_routes_preserve_drafts_and_exact_assignments(self):
        catalog = self.case.root.request(f'/api/data/permissions?tenantId={self.case.tenant_id}&pageSize=100')[1]['items']
        ids = {row['code']: row['id'] for row in catalog}
        status, role = self.case.root.request(f'/api/data/roles?tenantId={self.case.tenant_id}', 'POST', {'name': 'Route permission role'})
        self.assertEqual(status, 201)
        links = f'/api/links/role-permissions/{role["id"]}?tenantId={self.case.tenant_id}'
        self.assertEqual(self.case.root.request(links, 'PUT', {'ids': [ids['companies.read']]})[0], 204)
        self.login()
        for locale, permissions, search in (('it', 'Permessi', 'Cerca'), ('en', 'Permissions', 'Search')):
            self.context.add_cookies([{'name': 'locale', 'value': locale, 'url': runner.ORIGIN}])
            self.page.reload(wait_until='networkidle')
            self.page.locator('nav').get_by_role('button', name=permissions, exact=True).click()
            self.page.get_by_role('textbox', name=search, exact=True).fill('business-partner-numbering')
            branch = self.page.locator('[data-permission-domain=administration]')
            expect(branch).to_be_visible()
            for key in ('settings', 'settings-master-data', 'settings-business-partners', 'business-partner-numbering'):
                branch = branch.locator(f'[data-permission-resource={key}]')
                expect(branch).to_be_visible()
            expect(branch.locator('[data-permission-code]')).to_have_count(2)
            expect(self.page.locator('[data-permission-domain=masterData]')).to_have_count(0)
            self.page.set_viewport_size({'width': 390, 'height': 1000})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)
            self.page.screenshot(path=str(runner.EVIDENCE/f'permission-routes-{locale}-mobile.png'))
            self.page.set_viewport_size({'width': 1440, 'height': 1000})
        self.page.locator('nav').get_by_role('button', name='Roles', exact=True).click()
        edit = self.page.get_by_role('button', name='Edit Route permission role', exact=True)
        for commit in (False, True):
            edit.click()
            dialog = self.page.get_by_role('dialog')
            dialog.get_by_role('textbox', name='Search Role permissions', exact=True).fill('business-partner-numbering.read')
            settings = dialog.locator('[data-permission-resource-checkbox=settings]')
            expect(settings).to_be_visible()
            settings.check()
            expect(settings).to_be_checked()
            expect(dialog.locator('[data-permission-resource-checkbox=settings-business-partners]')).to_be_checked()
            self.page.screenshot(path=str(runner.EVIDENCE/'permission-routes-role-draft.png'))
            self.assertEqual(self.case.root.request(links)[1]['ids'], [ids['companies.read']])
            if commit:
                dialog.get_by_role('button', name='Save', exact=True).click()
            else:
                dialog.get_by_role('button', name='Cancel', exact=True).click()
            expect(dialog).to_have_count(0)
        expected = {ids[code] for code in ids if code == 'companies.read' or code.startswith('settings.') or code.startswith('business-partner-numbering.')}
        self.assertEqual(set(self.case.root.request(links)[1]['ids']), expected)
        self.assertEqual(len(self.mutations), 1)

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
        self.page.locator('[data-action=add-tax]').click()
        dialog = self.related('tax')
        expect(dialog).to_be_visible()
        bounds = dialog.bounding_box()
        self.assertGreaterEqual(bounds['x'], 0)
        self.assertLessEqual(bounds['x'] + bounds['width'], 390)
        self.page.locator('#bp-tax-0-value').fill('12345678901')
        self.apply_related()
        expect(self.page.locator('[data-bp-related-table=tax]')).to_contain_text('12345678901')
        self.assertEqual(self.mutations, [])
        self.page.get_by_role('button', name='Save', exact=True).click()
        expect(self.page.get_by_role('button', name='New Business Partner', exact=True)).to_be_visible()
        expect(self.page.locator('tbody')).to_contain_text('Mobile partner')
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)


if __name__ == '__main__':
    unittest.main(defaultTest='BusinessPartnerBrowserTests')
