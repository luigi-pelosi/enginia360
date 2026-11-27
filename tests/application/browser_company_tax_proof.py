"""Finite Chromium Phase3 acceptance against actual labelled candidate APIs.

Proxy routing forwards every request to real loopback containers. The sole fault
injection drops an already committed response; it never fabricates an API body.
"""
import json
import os
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

from tax_helpers import configure_fixture
from test_company_tax_http import CompanyTaxHttp
from browser_tax_proof import TaxBrowser
from browser_taxclassification_proof import TaxClassificationBrowser


class CompanyTaxBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        CompanyTaxHttp.setUpClass()
        cls.fixture = configure_fixture('enginia360-company-tax-proof')
        cls.fixture.EVIDENCE = Path(os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'])
        cls.state = json.loads(Path(os.environ['ENGINIA360_TAX_STATE']).read_text())
        if cls.state['scope'] != 'enginia360-company-tax-proof' or not cls.fixture.verify_target(cls.fixture.WEB):
            raise RuntimeError('Isolated CompanyTax candidate frontend unavailable')
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=os.environ.get('ENGINIA360_CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome'), headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.case = getattr(self, 'http_case_class', CompanyTaxHttp)(getattr(self, 'http_case_name', 'test_activation_utc_coverage_and_historical_suspension'))
        self.case.setUp()
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
        self.context.set_default_timeout(15000)
        self.errors, self.mutations, self.responses = [], [], []
        self.drop_path = None
        def forward(route):
            url = urlsplit(route.request.url)
            if url.netloc != urlsplit(self.fixture.ORIGIN).netloc:
                route.abort('blockedbyclient')
                self.errors.append('Out-of-fixture request: ' + url.netloc)
                return
            port = self.state['apiPort'] if url.path.startswith('/api/') else self.state['webPort']
            response = route.fetch(url=f'http://127.0.0.1:{port}' + url.path + ('?' + url.query if url.query else ''), headers={**route.request.all_headers(), 'host': url.netloc}, max_retries=2 if route.request.method == 'GET' else 0)
            if self.drop_path == url.path and route.request.method == getattr(self, 'drop_method', 'POST'):
                self.drop_path = None
                self.assertIn(response.status, (200, 201), response.text())
                route.abort('failed')
            else:
                route.fulfill(response=response)
        self.context.route('**/*', forward)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        def requested(request):
            path = urlsplit(request.url).path
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and path.startswith(('/api/tax/', '/api/data/companies')):
                self.mutations.append({'method': request.method, 'path': path, 'body': request.post_data_json})
        self.page.on('request', requested)
        self.page.on('response', lambda response: self.responses.append({'path': urlsplit(response.url).path, 'status': response.status, 'method': response.request.method}) if '/api/tax/' in response.url else None)
        self.context.tracing.start(screenshots=True, snapshots=True, sources=False)

    tearDown = TaxClassificationBrowser.tearDown
    login = TaxBrowser.login
    button = TaxBrowser.button
    window_geometry = TaxClassificationBrowser.window_geometry

    def company_navigation(self):
        from playwright.sync_api import expect
        self.page.locator('nav').get_by_role('button', name=self.messages['resources']['companies'], exact=True).click()
        expect(self.page.get_by_role('heading', name=self.messages['resources']['companies'], exact=True)).to_be_visible()

    def open_company(self, company=None, readonly=False):
        from playwright.sync_api import expect
        company = company or self.case.company
        self.company_navigation()
        self.page.locator('.search-box input').fill(company['name'])
        row = self.page.locator('tbody tr').filter(has_text=company['name'])
        row.get_by_role('button', name=re.compile('^' + re.escape(self.messages['app']['details' if readonly else 'edit']) + r'(?:\s|$)')).click()
        expect(self.page.locator('#company-tab-general')).to_be_visible()
        expect(self.page.locator('#field-name')).to_have_value(company['name'])

    def tab(self, taxation=True):
        from playwright.sync_api import expect
        self.page.locator('#company-tab-' + ('taxation' if taxation else 'general')).click()
        if taxation:
            expect(self.page.locator('#company-tax-section')).to_be_visible()
            expect(self.page.locator('#company-tax-section')).to_have_attribute('aria-busy', 'false')

    def select_country(self, field='establishment_country_id', iso='IT'):
        self.page.locator('#company-tax-' + field).click()
        self.page.get_by_role('option', name=re.compile('^' + re.escape(iso) + r'\s')).click()

    def editor(self, action='create', root=None, registration=None):
        from playwright.sync_api import expect
        suffix = '' if action == 'create' else '-' + (registration or root)['id']
        self.page.locator('#company-tax-' + action + suffix).click()
        dialog = self.page.locator('#company-tax-editor')
        expect(dialog).to_be_visible()
        return dialog

    def save_tax(self, suffix, expected=201):
        from playwright.sync_api import expect
        with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith(suffix)) as saved:
            self.page.locator('#company-tax-save').click()
        self.assertEqual(saved.value.status, expected, saved.value.text())
        if expected in (200, 201):
            expect(self.page.locator('#company-tax-editor')).to_have_count(0)
        return saved.value.json()

    def fill_registration(self, profile=False):
        self.page.locator('#company-tax-tax_identifier').fill(self.case.identifier())
        self.page.locator('#company-tax-registration-valid_from').fill(self.case.start)
        if profile:
            # New roots always expose a mandatory profile; additional registration
            # keeps its independent opt-in profile control.
            checkbox = self.page.locator('#company-tax-include-profile')
            if checkbox.count():
                checkbox.check()
            self.page.locator('#company-tax-profile-valid_from').fill(self.case.start)

    def create_ui(self, registration=False, profile=False):
        self.editor()
        self.select_country()
        self.fill_registration(True)
        return self.save_tax('/configurations')

    def general_save(self, method='PUT', expected=200):
        with self.page.expect_response(lambda response: response.request.method == method and urlsplit(response.url).path.startswith('/api/data/companies') and urlsplit(response.url).path.endswith('/save')) as saved:
            self.page.locator('button[form="record-form"]').click()
        self.assertEqual(saved.value.status, expected, saved.value.text())
        return saved.value.json()

    def staged(self, locale):
        from playwright.sync_api import expect
        self.login(locale)
        self.company_navigation()
        self.page.locator('.page-heading').get_by_role('button', name=self.messages['app']['new'], exact=True).click()
        self.page.locator('#field-name').fill('Staged company ' + self.case.code)
        self.tab()
        dialog = self.editor()
        self.window_geometry(dialog)
        self.select_country()
        self.fill_registration(True)
        self.page.locator('#company-tax-save').click()
        expect(self.page.get_by_test_id('company-tax-staged')).to_have_count(1)
        self.assertEqual(self.mutations, [], 'Staging must issue no fiscal or parent POST')
        self.page.reload(wait_until='networkidle')
        expect(self.page.get_by_test_id('company-tax-staged')).to_have_count(1)
        self.tab(False)
        created = self.general_save('POST', 201)
        roots = self.case.req(self.case.list_route(created))['items']
        self.assertEqual((len(roots), roots[0]['status'], roots[0]['version']), (1, 'DRAFT', 1))
        self.assertEqual(len(roots[0]['registrations'][0]['profiles']), 1)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(len(self.mutations[0]['body']['taxConfigurations']), 1)

    def test_italian_new_company_staged_single_atomic_post_refresh(self):
        self.staged('it')

    def test_english_new_company_staged_single_atomic_post_refresh(self):
        self.staged('en')

    def lifecycle(self, locale):
        self.login(locale)
        self.open_company()
        self.tab()
        root = self.create_ui()
        self.editor('register', root)
        self.select_country('country_id', 'DE')
        self.fill_registration()
        self.page.locator('#company-tax-tax_identifier').fill(self.case.identifier('DE'))
        root = self.save_tax('/registrations')
        registration = next(r for r in root['registrations'] if r['country_id'] == self.case.countries['DE']['id'])
        self.editor('assign', root, registration)
        self.page.locator('#company-tax-profile-valid_from').fill(self.case.start)
        root = self.save_tax('/regimes')
        self.editor('activate', root)
        root = self.save_tax('/activate', 200)
        self.assertEqual(root['status'], 'ACTIVE')
        self.case.resolve(registration, new=True)
        self.editor('schedule', root, registration)
        self.page.locator('#company-tax-profile-valid_from').fill(self.case.future)
        root = self.save_tax('/regimes/schedule', 200)
        self.assertEqual(len(next(r for r in root['registrations'] if r['id'] == registration['id'])['profiles']), 2)
        self.editor('suspend', root)
        root = self.save_tax('/suspend', 200)
        self.case.resolve(registration, new=True, expected=409)
        self.editor('close', root, registration)
        self.page.locator('#company-tax-close-date').fill(self.case.later)
        root = self.save_tax('/close', 200)
        self.assertEqual(next(r for r in root['registrations'] if r['id'] == registration['id'])['valid_to'], self.case.later)
        self.assertEqual(self.case.read(root), root)
        self.assertEqual(root['version'], 1 + len(('register', 'assign', 'activate', 'schedule', 'suspend', 'close')))
        self.assertEqual(self.case.company_read(), self.case.company)

    def test_italian_existing_register_assign_activate_schedule_suspend_close(self):
        self.lifecycle('it')

    def test_english_existing_register_assign_activate_schedule_suspend_close(self):
        self.lifecycle('en')

    def test_readonly_company_scope_no_catalog_grants_no_mutations(self):
        from playwright.sync_api import expect
        root = self.case.create([self.case.registration()])
        actor, role, credentials = self.case.actor(['companies.read', 'company-tax-configurations.read'])
        self.case.assign_companies(role, [self.case.company])
        self.login(credentials=credentials)
        self.open_company(readonly=True)
        self.tab()
        expect(self.page.locator('[data-company-tax-id="' + root['id'] + '"]')).to_contain_text(root['registrations'][0]['tax_identifier'])
        for selector in ('#company-tax-create', '[id^="company-tax-register-"]', '[id^="company-tax-assign-"]', '[id^="company-tax-schedule-"]'):
            expect(self.page.locator(selector)).to_have_count(0)
        self.assertEqual(self.mutations, [])
        self.assertFalse(any(r['path'] in ('/api/tax/regimes', '/api/tax/types') for r in self.responses))
        self.case.assign_companies(role, [])
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('[data-company-tax-id]')).to_have_count(0)

    def test_independent_unsaved_general_draft_after_fiscal_commit_refresh_and_save(self):
        from playwright.sync_api import expect
        self.login()
        self.open_company()
        self.page.locator('#field-name').fill('Unsaved general ' + self.case.code)
        self.tab()
        root = self.create_ui(True, True)
        self.assertEqual(self.case.company_read(), self.case.company)
        self.tab(False)
        expect(self.page.locator('#field-name')).to_have_value('Unsaved general ' + self.case.code)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#field-name')).to_have_value('Unsaved general ' + self.case.code)
        self.general_save()
        self.assertEqual(self.case.company_read()['name'], 'Unsaved general ' + self.case.code)
        self.assertEqual(self.case.read(root), root)
        self.assertNotIn('taxConfigurations', self.mutations[-1]['body'])

    def test_stale_recovered_child_keeps_original_expected_version_and_general_draft(self):
        from playwright.sync_api import expect
        root = self.case.create([self.case.registration()])
        registration = root['registrations'][0]
        self.login()
        self.open_company()
        self.page.locator('#field-name').fill('Frozen general draft')
        self.tab()
        self.editor('schedule', root, registration)
        self.page.locator('#company-tax-profile-valid_from').fill(self.case.later)
        updated = self.case.assign(root, registration, schedule=True, valid_from=self.case.future)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#company-tax-save')).to_be_disabled()
        recovery = self.page.evaluate("Object.entries(sessionStorage).filter(([key])=>key.startsWith('company-tax:v1:')).map(([key,value])=>({key,value:JSON.parse(value)}))")
        own = next(x['value'] for x in recovery if (x['value'].get('editor') or {}).get('rootId') == root['id'])
        self.assertEqual(own['editor']['expectedVersion'], 1)
        self.assertTrue(own['stale'])
        self.assertEqual(self.case.read(root), updated)
        self.assertEqual(self.mutations, [])

    def test_committed_response_drop_no_replay_refresh_menu_review(self):
        from playwright.sync_api import expect
        root = self.case.create([self.case.registration()])
        self.login('en')
        self.open_company()
        self.tab()
        self.editor('activate', root)
        self.drop_path = '/api/tax/company-configurations/' + root['id'] + '/activate'
        self.page.locator('#company-tax-save').click()
        expect(self.page.locator('#company-tax-review')).to_be_visible()
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#company-tax-review')).to_be_visible()
        self.page.get_by_role('dialog').get_by_role('button', name=self.messages['app']['cancel'], exact=True).click()
        self.open_company()
        self.tab()
        expect(self.page.locator('#company-tax-review')).to_be_visible()
        self.page.locator('#company-tax-review').click()
        self.page.locator('#company-tax-acknowledge').click()
        expect(self.page.locator('#company-tax-review')).to_have_count(0)
        self.assertEqual(self.case.read(root)['version'], 2)
        self.assertEqual(len(self.mutations), 1, 'Never replay an uncertain command')
        self.assertEqual(self.mutations[0]['body']['expectedVersion'], 1)

    def test_open_session_revocation_preflight_blocks_write(self):
        from playwright.sync_api import expect
        root = self.case.create([self.case.registration()])
        actor, role, credentials = self.case.actor(['companies.read', 'companies.update', 'company-tax-configurations.read', 'company-tax-configurations.activate'])
        self.case.assign_companies(role, [self.case.company])
        self.login(credentials=credentials)
        self.open_company()
        self.tab()
        self.editor('activate', root)
        self.case.assign_companies(role, [])
        self.page.locator('#company-tax-save').click()
        expect(self.page.locator('#company-tax-editor [role="alert"]')).to_be_visible()
        self.assertEqual(self.case.read(root), root)
        self.assertEqual(self.mutations, [])

    def regimes(self, locale):
        from playwright.sync_api import expect
        _, _, credentials = self.case.actor(['tax-regimes.read'])
        self.login(locale, credentials)
        self.page.locator('nav').get_by_role('button', name=self.messages['resources']['settings'], exact=True).click()
        self.button('masterData').click()
        self.page.get_by_role('button', name=self.messages['resources']['tax-management'], exact=True).click()
        self.page.get_by_test_id('tax-tab-regimes').click()
        table = self.page.locator('#tax-regime-table')
        expect(table).to_be_visible()
        expect(table).to_contain_text('ORDINARY')
        expect(table.get_by_role('button', name=re.compile('^' + re.escape(self.messages['app']['edit'])))).to_have_count(0)
        self.assertEqual(self.mutations, [])
        self.assertTrue(any(r['path'] == '/api/tax/regimes' and r['status'] == 200 for r in self.responses))
        self.assertFalse(any(r['path'] in ('/api/tax/types', '/api/tax/codes', '/api/tax/nature-codes') for r in self.responses))

    def test_italian_readonly_regime_catalog(self):
        self.regimes('it')

    def test_english_readonly_regime_catalog(self):
        self.regimes('en')
