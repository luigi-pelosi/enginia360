"""Chromium TaxManagement reale: layout, bozze, programmazione, RBAC e incertezza."""
import json
import os
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qs, urlsplit

from tax_helpers import configure_fixture
from test_tax_http import TaxHttp


@unittest.skipUnless(os.environ.get('ENGINIA360_TAX_PROOF') == '1', 'Richiede fixture TaxManagement isolata')
class TaxBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.fixture = configure_fixture()
        cls.state = json.loads(Path(os.environ['ENGINIA360_TAX_STATE']).read_text())
        TaxHttp.setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=os.environ.get('ENGINIA360_CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome'), headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.case = TaxHttp('test_global_catalogs_full_and_no_implicit_tenant_templates')
        self.case.setUp()
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
        self.context.set_default_timeout(15000)
        self.errors, self.mutations = [], []
        self.drop_create = False
        def forward(route):
            url = urlsplit(route.request.url)
            if url.netloc != urlsplit(self.fixture.ORIGIN).netloc:
                raise RuntimeError('Destinazione fuori scope browser TaxManagement')
            port = self.state['apiPort'] if url.path.startswith('/api/') else self.state['webPort']
            response = route.fetch(url=f'http://127.0.0.1:{port}' + url.path + ('?' + url.query if url.query else ''),
                                   headers={**route.request.all_headers(), 'host': url.netloc},
                                   max_retries=2 if route.request.method == 'GET' else 0)
            if self.drop_create and route.request.method == 'POST' and url.path == '/api/tax/codes':
                self.drop_create = False
                self.assertEqual(response.status, 201, response.text())
                route.abort('failed')
            else:
                route.fulfill(response=response)
        self.context.route(self.fixture.ORIGIN + '/**', forward)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.on('request', lambda req: self.mutations.append((req.method, req.url)) if '/api/tax/' in req.url and req.method in ('POST', 'PUT', 'DELETE') else None)
        self.messages = json.loads((self.fixture.ROOT / 'frontend/messages/it.json').read_text())

    def tearDown(self):
        try:
            self.page.screenshot(path=str(self.fixture.EVIDENCE / (self._testMethodName + '.png')), full_page=True)
            (self.fixture.EVIDENCE / (self._testMethodName + '-events.json')).write_text(json.dumps({'errors': self.errors, 'mutations': self.mutations}, indent=2))
            self.assertEqual(self.errors, [])
        finally:
            self.context.unroute_all(behavior='wait')
            self.context.close()

    def login(self, locale='it', credentials=None):
        from playwright.sync_api import expect
        creds = credentials or self.case.credentials
        self.page.goto(self.fixture.ORIGIN, wait_until='networkidle')
        self.page.locator('#username').fill(creds['username'])
        self.page.locator('#password').fill(creds['password'])
        self.page.locator('#tenant-code').fill(self.case.code)
        self.page.get_by_role('button', name='Accedi', exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        if locale == 'en':
            self.page.get_by_role('combobox', name='Lingua', exact=True).click()
            self.page.get_by_role('option', name='English', exact=True).click()
            expect(self.page.locator('nav')).to_contain_text('Settings')
        self.messages = json.loads((self.fixture.ROOT / f'frontend/messages/{locale}.json').read_text())

    def button(self, key, scope=None, group='app'):
        return (scope or self.page).get_by_role('button', name=self.messages[group][key], exact=True)

    def navigate(self):
        from playwright.sync_api import expect
        self.page.locator('nav').get_by_role('button', name=self.messages['resources']['settings'], exact=True).click()
        self.button('masterData').click()
        self.page.get_by_role('button', name=self.messages['resources']['tax-management'], exact=True).click()
        expect(self.page.locator('#tax-table')).to_be_visible()
        expect(self.page.locator('[data-tax-management]')).to_contain_text(self.messages['resources']['tax-management'])
        self.assertIn(parse_qs(urlsplit(self.page.url).query)['view'][0], ('tax-management', 'tax-codes'))

    def editor(self):
        from playwright.sync_api import expect
        dialog = self.page.locator('#tax-editor')
        expect(dialog).to_be_visible()
        return dialog

    def version_dialog(self):
        return self.page.get_by_role('dialog').filter(has=self.page.locator('#tax-rate'))

    def staged_create(self, name='IVA browser', code='VAT_BROWSER'):
        from playwright.sync_api import expect
        self.page.locator('#tax-new').click()
        dialog = self.editor()
        dialog.locator('#tax-name').fill(name)
        dialog.locator('#tax-code').fill(code)
        dialog.get_by_test_id('tax-editor-versions').click()
        dialog.locator('#tax-add-version').click()
        version = self.version_dialog()
        version.locator('#tax-valid_from').fill('2026-01-01')
        self.button('save', version).click()
        expect(version).to_have_count(0)
        return self.editor()

    def save_root(self, expected=201):
        with self.page.expect_response(lambda res: res.request.method in ('POST', 'PUT') and re.match(r'^/api/tax/codes(?:/[0-9a-f-]+)?$', urlsplit(res.url).path) is not None) as response:
            self.editor().locator('[form="tax-editor-form"]').click()
        self.assertEqual(response.value.status, expected, response.value.text())
        return response.value.json()

    def lifecycle(self, locale):
        from playwright.sync_api import expect
        self.login(locale)
        self.navigate()
        self.page.get_by_test_id('tax-tab-types').click()
        expect(self.page.locator('#tax-table')).to_contain_text('VAT')
        self.page.get_by_test_id('tax-tab-nature-codes').click()
        expect(self.page.locator('#tax-table')).to_contain_text('N6.9')
        self.page.get_by_test_id('tax-tab-codes').click()
        dialog = self.staged_create()
        self.page.reload(wait_until='networkidle')
        dialog = self.editor()
        dialog.get_by_test_id('tax-editor-general').click()
        expect(dialog.locator('#tax-name')).to_have_value('IVA browser')
        self.assertEqual(len(self.mutations), 0)
        created = self.save_root()
        expect(self.page.locator('#tax-editor')).to_have_count(0)
        row = self.page.locator('#tax-table tbody tr').filter(has_text='VAT_BROWSER')
        expect(row).to_contain_text('22.000000%')
        row.get_by_role('button', name=self.messages['app']['edit'] + ' IVA browser', exact=True).click()
        dialog = self.editor()
        dialog.locator('#tax-name').fill('Metadati non ancora salvati')
        dialog.get_by_test_id('tax-editor-versions').click()
        dialog.locator('#tax-add-version').click()
        version = self.version_dialog()
        version.locator('#tax-rate').fill('23')
        version.locator('#tax-valid_from').fill('2027-01-01')
        with self.page.expect_response(lambda res: res.request.method == 'POST' and urlsplit(res.url).path.endswith('/versions')) as response:
            self.button('save', version).click()
        self.assertEqual(response.value.status, 200, response.value.text())
        expect(version).to_have_count(0)
        dialog = self.editor()
        dialog.get_by_test_id('tax-editor-general').click()
        expect(dialog.locator('#tax-name')).to_have_value('Metadati non ancora salvati')
        authoritative = self.case.req('codes/' + created['id'])
        self.assertEqual(authoritative['name'], 'IVA browser')
        self.assertEqual(len(authoritative['versions']), 2)
        self.page.reload(wait_until='networkidle')
        expect(self.editor().locator('#tax-name')).to_have_value('Metadati non ancora salvati')
        updated = self.save_root(200)
        self.assertEqual(updated['name'], 'Metadati non ancora salvati')
        self.assertEqual(updated['version'], authoritative['version'] + 1)
        row = self.page.locator('#tax-table tbody tr').filter(has_text='VAT_BROWSER')
        row.get_by_role('button', name=self.messages['app']['details'] + ' ' + updated['name'], exact=True).click()
        dialog = self.editor()
        dialog.get_by_test_id('tax-editor-audit').click()
        expect(dialog).to_contain_text(self.messages['tax']['actions']['schedule'])
        self.button('cancel', dialog).click()
        expect(self.page.locator('#tax-editor')).to_have_count(0)
        row.get_by_role('button', name=self.messages['tax']['deactivate'] + ' ' + updated['name'], exact=True).click()
        self.button('deactivate', self.page.get_by_role('dialog'), 'tax').click()
        expect(row).to_contain_text(self.messages['tax']['inactive'])
        self.page.locator('#tax-search').fill('filtro recuperato')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tax-search')).to_have_value('filtro recuperato')
        self.navigate()
        expect(self.page.locator('#tax-search')).to_have_value('')

    def test_italian_lifecycle_and_recovery(self):
        self.lifecycle('it')

    def test_english_lifecycle_and_recovery(self):
        self.lifecycle('en')

    def test_exempt_nature_selection_and_dialog_window(self):
        from playwright.sync_api import expect
        self.login()
        self.navigate()
        self.page.locator('#tax-new').click()
        dialog = self.editor()
        dialog.locator('#tax-name').fill('Esente browser')
        dialog.locator('#tax-code').fill('VAT_EXEMPT_UI')
        dialog.locator('#tax-country_id').click()
        self.page.get_by_role('option', name='Italia (IT)', exact=True).click()
        before = dialog.bounding_box()
        header = dialog.locator('[data-slot="dialog-header"]').bounding_box()
        self.page.mouse.move(header['x'] + 120, header['y'] + 8)
        self.page.mouse.down()
        self.page.mouse.move(header['x'] + 150, header['y'] + 28, steps=8)
        self.page.mouse.up()
        after = dialog.bounding_box()
        self.assertGreater(after['x'], before['x'] + 15)
        grip = dialog.locator('[data-dialog-resize]').bounding_box()
        self.page.mouse.move(grip['x'] + grip['width'] / 2, grip['y'] + grip['height'] / 2)
        self.page.mouse.down()
        self.page.mouse.move(grip['x'] - 60, grip['y'] + 20, steps=8)
        self.page.mouse.up()
        self.assertLess(dialog.bounding_box()['width'], after['width'] - 30)
        dialog.get_by_test_id('tax-editor-versions').click()
        dialog.locator('#tax-add-version').click()
        version = self.version_dialog()
        version.locator('#tax-treatment').click()
        self.page.get_by_role('option', name=self.messages['tax']['EXEMPT'], exact=True).click()
        expect(version.locator('#tax-rate')).to_have_value('0')
        expect(version.locator('#tax-tax_nature_code_id')).to_contain_text('N4')
        version.locator('#tax-valid_from').fill('2026-01-01')
        self.button('save', version).click()
        created = self.save_root()
        self.assertEqual(created['versions'][0]['tax_nature_code'], 'N4')
        self.assertEqual(created['versions'][0]['treatment'], 'EXEMPT')

    def test_explicit_italian_templates_install_from_ui(self):
        from playwright.sync_api import expect
        self.login()
        self.navigate()
        self.button('installTemplates', group='tax').click()
        dialog = self.page.get_by_role('dialog')
        dialog.locator('#tax-install-date').fill('2026-01-01')
        with self.page.expect_response(lambda res: res.request.method == 'POST' and urlsplit(res.url).path.endswith('/templates/install')) as response:
            self.button('install', dialog, 'tax').click()
        self.assertEqual(response.value.status, 200, response.value.text())
        self.assertEqual(response.value.json()['installed'], 14)
        expect(dialog).to_have_count(0)
        expect(self.page.locator('#tax-table')).to_contain_text('VAT_STANDARD')
        self.assertEqual(self.case.req('codes')['total'], 14)

    def test_read_only_code_permission_does_not_require_catalog_grants(self):
        from playwright.sync_api import expect
        row = self.case.create()
        _, _, credentials = self.case.actor(['tax-codes.read'])
        self.login(credentials=credentials)
        self.navigate()
        expect(self.page.locator('#tax-table')).to_contain_text(row['code'])
        expect(self.page.locator('#tax-new')).to_have_count(0)
        expect(self.page.get_by_test_id('tax-tab-types')).to_have_count(0)
        expect(self.page.get_by_test_id('tax-tab-nature-codes')).to_have_count(0)
        self.assertEqual(self.page.locator('[data-tax-management] [role="alert"]').count(), 0)
        self.page.locator('#tax-table').get_by_role('button', name=self.messages['app']['details'] + ' ' + row['name'], exact=True).click()
        expect(self.editor().locator('#tax-name')).to_be_disabled()
        expect(self.editor().locator('[form="tax-editor-form"]')).to_have_count(0)

    def test_recovered_stale_draft_never_adopts_new_revision(self):
        from playwright.sync_api import expect
        row = self.case.create()
        self.login()
        self.navigate()
        self.page.locator('#tax-table').get_by_role('button', name=self.messages['app']['edit'] + ' ' + row['name'], exact=True).click()
        self.editor().locator('#tax-name').fill('Bozza obsoleta browser')
        current = self.case.update(row, {'name': 'Vincitore concorrente'})
        self.page.reload(wait_until='networkidle')
        expect(self.editor().locator('#tax-name')).to_have_value('Bozza obsoleta browser')
        expect(self.editor().locator('[form="tax-editor-form"]')).to_be_disabled()
        expect(self.editor()).to_contain_text(self.messages['tax']['tax_stale_version'])
        self.assertEqual(self.case.req('codes/' + row['id']), current)
        self.assertEqual(self.mutations, [])

    def test_lost_create_response_blocks_replay_across_refresh_and_menu(self):
        from playwright.sync_api import expect
        self.login()
        self.navigate()
        self.staged_create(code='VAT_UNCERTAIN')
        self.drop_create = True
        self.editor().locator('[form="tax-editor-form"]').click()
        expect(self.page.get_by_text(self.messages['tax']['uncertain'], exact=True)).to_be_visible()
        self.page.reload(wait_until='networkidle')
        expect(self.page.get_by_text(self.messages['tax']['uncertain'], exact=True)).to_be_visible()
        self.navigate()
        expect(self.page.get_by_text(self.messages['tax']['uncertain'], exact=True)).to_be_visible()
        expect(self.page.locator('#tax-new')).to_have_count(0)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(self.case.req('codes', search='VAT_UNCERTAIN')['total'], 1)
        self.button('review', group='tax').click()
        self.button('acknowledge', group='tax').click()
        expect(self.page.get_by_text(self.messages['tax']['uncertain'], exact=True)).to_have_count(0)
        expect(self.page.locator('#tax-new')).to_be_enabled()
        self.assertEqual(len(self.mutations), 1)
