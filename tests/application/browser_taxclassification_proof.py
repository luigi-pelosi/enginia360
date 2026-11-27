"""Chromium Phase 2 acceptance: actual UI, APIs and persisted readback; no mocks."""
import json
import os
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qs, urlsplit

from tax_helpers import configure_fixture
from test_taxclassification_http import TaxClassificationHttp
from browser_tax_proof import TaxBrowser


class TaxClassificationBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        TaxClassificationHttp.setUpClass()
        cls.fixture = configure_fixture('enginia360-taxclassification-proof')
        cls.state = json.loads(Path(os.environ['ENGINIA360_TAX_STATE']).read_text())
        if not cls.fixture.verify_target(cls.fixture.WEB):
            raise RuntimeError('Isolated candidate frontend unavailable')
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=os.environ.get('ENGINIA360_CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome'), headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.case = TaxClassificationHttp('test_item_lifecycle')
        self.case.setUp()
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
        self.context.set_default_timeout(12000)
        self.errors, self.mutations, self.responses = [], [], []
        self.drop_path = None
        def forward(route):
            url = urlsplit(route.request.url)
            if url.netloc != urlsplit(self.fixture.ORIGIN).netloc:
                raise RuntimeError('Destination outside isolated classification fixture')
            port = self.state['apiPort'] if url.path.startswith('/api/') else self.state['webPort']
            response = route.fetch(url=f'http://127.0.0.1:{port}' + url.path + ('?' + url.query if url.query else ''),
                                   headers={**route.request.all_headers(), 'host': url.netloc},
                                   max_retries=2 if route.request.method == 'GET' else 0)
            if self.drop_path == url.path and route.request.method == 'POST':
                self.drop_path = None
                self.assertIn(response.status, (200, 201), response.text())
                route.abort('failed')
            else:
                route.fulfill(response=response)
        self.context.route(self.fixture.ORIGIN + '/**', forward)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        def request_event(request):
            path = urlsplit(request.url).path
            if request.method in ('POST', 'PUT', 'DELETE') and path.startswith(('/api/tax/', '/api/catalog/', '/api/data/business-partners')):
                self.mutations.append({'method': request.method, 'path': path, 'body': request.post_data_json})
        self.page.on('request', request_event)
        self.page.on('response', lambda response: self.responses.append({'path': urlsplit(response.url).path, 'status': response.status}) if '/api/tax/' in response.url else None)
        self.context.tracing.start(screenshots=True, snapshots=True, sources=False)

    def tearDown(self):
        try:
            self.page.screenshot(path=str(self.fixture.EVIDENCE / (self._testMethodName + '.png')), full_page=True)
            (self.fixture.EVIDENCE / (self._testMethodName + '-events.json')).write_text(json.dumps({'errors': self.errors, 'mutations': self.mutations, 'responses': self.responses}, indent=2))
            self.context.tracing.stop(path=str(self.fixture.EVIDENCE / (self._testMethodName + '-trace.zip')))
            self.assertEqual(self.errors, [], 'Real JavaScript exceptions')
        finally:
            self.context.unroute_all(behavior='wait')
            self.context.close()

    login = TaxBrowser.login
    button = TaxBrowser.button

    def tax_navigation(self, kind='item'):
        from playwright.sync_api import expect
        self.page.locator('nav').get_by_role('button', name=self.messages['resources']['settings'], exact=True).click()
        self.button('masterData').click()
        self.page.get_by_role('button', name=self.messages['resources']['tax-management'], exact=True).click()
        self.page.get_by_test_id('tax-tab-' + kind + '-classifications').click()
        expect(self.page.locator('#taxclass-table')).to_be_visible()

    def admin_editor(self, code='UI_CLASS', name='UI classification'):
        from playwright.sync_api import expect
        self.page.locator('#taxclass-new').click()
        dialog = self.page.locator('#taxclass-editor')
        expect(dialog).to_be_visible()
        dialog.locator('#taxclass-name').fill(name)
        dialog.locator('#taxclass-code').fill(code)
        return dialog

    def save_admin(self, method='POST', expected=201):
        with self.page.expect_response(lambda response: response.request.method == method and re.fullmatch(r'/api/tax/(item|partner)-classifications(?:/[0-9a-f-]+)?', urlsplit(response.url).path) is not None) as saved:
            self.page.locator('[form="taxclass-editor-form"]').click()
        self.assertEqual(saved.value.status, expected, saved.value.text())
        return saved.value.json()

    def window_geometry(self, dialog):
        before = dialog.bounding_box()
        header = dialog.locator('[data-slot="dialog-header"]').bounding_box()
        self.page.mouse.move(header['x'] + 120, header['y'] + 8)
        self.page.mouse.down()
        self.page.mouse.move(header['x'] + 150, header['y'] + 28, steps=8)
        self.page.mouse.up()
        moved = dialog.bounding_box()
        self.assertGreater(moved['x'], before['x'] + 15)
        grip = dialog.locator('[data-dialog-resize]').bounding_box()
        self.page.mouse.move(grip['x'] + grip['width'] / 2, grip['y'] + grip['height'] / 2)
        self.page.mouse.down()
        self.page.mouse.move(grip['x'] - 60, grip['y'] + 20, steps=8)
        self.page.mouse.up()
        self.assertLess(dialog.bounding_box()['width'], moved['width'] - 30)

    def admin_lifecycle(self, locale, kind):
        from playwright.sync_api import expect
        self.login(locale)
        self.tax_navigation(kind)
        dialog = self.admin_editor()
        self.window_geometry(dialog)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#taxclass-name')).to_have_value('UI classification')
        self.assertEqual(self.mutations, [])
        created = self.save_admin()
        expect(self.page.locator('#taxclass-editor')).to_have_count(0)
        self.assertEqual(self.case.req(kind + '-classifications/' + created['id'])['name'], 'UI classification')
        row = self.page.locator('#taxclass-table tbody tr').filter(has_text='UI_CLASS')
        row.get_by_role('button', name=self.messages['app']['edit'] + ' UI classification', exact=True).click()
        expect(self.page.locator('#taxclass-code')).to_be_disabled()
        self.page.locator('#taxclass-name').fill('UI changed')
        changed = self.save_admin('PUT', 200)
        expect(self.page.locator('#taxclass-editor')).to_have_count(0)
        self.assertEqual(changed['version'], 2)
        row = self.page.locator('#taxclass-table tbody tr').filter(has_text='UI_CLASS')
        row.get_by_role('button', name=self.messages['taxClassification']['deactivate'] + ' UI changed', exact=True).click()
        self.button('deactivate', self.page.get_by_role('dialog'), 'taxClassification').click()
        expect(row).to_contain_text(self.messages['taxClassification']['inactive'])
        row.get_by_role('button', name=self.messages['taxClassification']['reactivate'] + ' UI changed', exact=True).click()
        self.button('reactivate', self.page.get_by_role('dialog'), 'taxClassification').click()
        expect(row).to_contain_text(self.messages['taxClassification']['active'])
        self.page.locator('#taxclass-search').fill('Recovered filter')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#taxclass-search')).to_have_value('Recovered filter')
        self.tax_navigation(kind)
        expect(self.page.locator('#taxclass-search')).to_have_value('')
        self.assertEqual(self.case.req(kind + '-classifications/' + created['id'])['version'], 4)

    def test_italian_item_admin_crud_refresh_menu_dialog(self):
        self.admin_lifecycle('it', 'item')

    def test_english_partner_admin_crud_refresh_menu_dialog(self):
        self.admin_lifecycle('en', 'partner')

    def test_explicit_templates_both_resources(self):
        from playwright.sync_api import expect
        self.login()
        for kind, count in (('item', 10), ('partner', 3)):
            self.tax_navigation(kind)
            self.assertEqual(self.case.req(kind + '-classifications')['total'], 0)
            self.page.locator('#taxclassinstall').click()
            with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith('/templates/install')) as saved:
                self.page.locator('#taxclass-install-form').get_by_role('button', name=self.messages['taxClassification']['install'], exact=True).click()
            self.assertEqual(saved.value.status, 200, saved.value.text())
            self.assertEqual(saved.value.json()['installed'], count)
            expect(self.page.locator('#taxclass-install-form')).to_have_count(0)
            self.assertEqual(self.case.req(kind + '-classifications')['total'], count)

    def test_dropped_admin_response_no_replay_refresh_review(self):
        from playwright.sync_api import expect
        self.login()
        self.tax_navigation()
        self.admin_editor('UI_UNCERTAIN')
        self.drop_path = '/api/tax/item-classifications'
        self.page.locator('[form="taxclass-editor-form"]').click()
        expect(self.page.get_by_text(self.messages['taxClassification']['uncertain'], exact=True)).to_be_visible()
        self.page.reload(wait_until='networkidle')
        expect(self.page.get_by_text(self.messages['taxClassification']['uncertain'], exact=True)).to_be_visible()
        self.assertEqual(self.case.req('item-classifications')['total'], 1)
        self.button('review', group='taxClassification').click()
        self.button('acknowledge', group='taxClassification').click()
        expect(self.page.get_by_text(self.messages['taxClassification']['uncertain'], exact=True)).to_have_count(0)
        self.assertEqual(len([m for m in self.mutations if m['path'] == '/api/tax/item-classifications' and m['method'] == 'POST']), 1)

    def subject_navigation(self, kind):
        from playwright.sync_api import expect
        nav = self.page.locator('nav')
        if kind == 'item':
            nav.get_by_role('button', name=self.messages['resources']['catalog'], exact=True).click()
            self.page.get_by_role('button', name=self.messages['resources']['catalog-items'], exact=True).click()
            expect(self.page.locator('#catalog-item-table')).to_be_visible()
        else:
            nav.get_by_role('button', name=self.messages['resources']['business-partners'], exact=True).click()
            expect(self.page.locator('#main')).to_contain_text(self.messages['resources']['business-partners'])

    def subject_tab(self, kind, tab):
        self.page.locator(('#item-tab-' if kind == 'item' else '#bp-tab-') + tab).click()

    def subject_name(self, kind):
        return self.page.locator('#item-name' if kind == 'item' else '#bp-legal_name')

    def open_subject(self, kind, subject):
        from playwright.sync_api import expect
        self.subject_navigation(kind)
        if kind == 'item':
            self.page.locator('#catalog-item-search').fill(subject['name'])
            row = self.page.locator('#catalog-item-table tr[data-record-id="' + subject['id'] + '"]')
            row.get_by_role('button', name=re.compile('^' + re.escape(self.messages['app']['edit']) + r'\s')).click()
        else:
            row = self.page.locator('tr').filter(has_text=subject['legal_name'])
            row.get_by_role('button', name=re.compile('^' + re.escape(self.messages['app']['edit']) + r'\s')).click()
        self.subject_tab(kind, 'general')
        expect(self.subject_name(kind)).to_have_value(subject['name' if kind == 'item' else 'legal_name'])

    def save_subject(self, kind, method='PUT', expected=200):
        with self.page.expect_response(lambda response: response.request.method == method and
                                       (re.fullmatch(r'/api/catalog/items(?:/[^/]+)?', urlsplit(response.url).path) is not None if kind == 'item' else urlsplit(response.url).path.endswith('/save'))) as saved:
            if kind == 'item':
                self.page.locator('#item-save').click()
                if method == 'POST':
                    self.page.locator('#item-activation-confirm').click()
            else:
                self.page.locator('form[aria-busy]').get_by_role('button', name=self.messages['app']['save'], exact=True).click()
        self.assertEqual(saved.value.status, expected, saved.value.text())
        return saved.value.json()

    def profile_editor(self, operation='assign', date='2026-01-01'):
        from playwright.sync_api import expect
        self.page.locator('#tax-profile-' + operation).click()
        dialog = self.page.get_by_test_id('tax-profile-editor')
        expect(dialog).to_be_visible()
        dialog.locator('#tax-profile-valid_from').fill(date)
        return dialog

    def existing_profile(self, locale, kind, drop=False):
        from playwright.sync_api import expect
        classification = self.case.classification(kind)
        subject = self.case.subject(kind)
        self.login(locale)
        self.open_subject(kind, subject)
        self.subject_name(kind).fill('Unsaved general draft')
        self.subject_tab(kind, 'taxation')
        expect(self.page.locator('#tax-profile-history')).to_contain_text(self.messages['taxProfiles']['empty'])
        self.profile_editor()
        if drop:
            self.drop_path = '/api/tax/' + self.case.profiles(kind, subject)
            self.page.locator('#tax-profile-save').click()
            expect(self.page.locator('#tax-profile-review')).to_be_visible()
            self.page.reload(wait_until='networkidle')
            expect(self.page.locator('#tax-profile-review')).to_be_visible()
            self.page.locator('#tax-profile-review').click()
            self.page.locator('#tax-profile-acknowledge').click()
        else:
            with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith('/profiles')) as saved:
                self.page.locator('#tax-profile-save').click()
            self.assertEqual(saved.value.status, 201, saved.value.text())
        expect(self.page.get_by_test_id('tax-profile-editor')).to_have_count(0)
        history = self.case.req(self.case.profiles(kind, subject))
        self.assertEqual((history['version'], history['total']), (1, 1))
        self.assertEqual(self.case.subject_read(kind, subject), subject)
        self.profile_editor('schedule', '2027-01-01')
        with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith('/schedule')) as scheduled:
            self.page.locator('#tax-profile-save').click()
        self.assertEqual(scheduled.value.status, 200, scheduled.value.text())
        expect(self.page.get_by_test_id('tax-profile-editor')).to_have_count(0)
        self.subject_tab(kind, 'general')
        expect(self.subject_name(kind)).to_have_value('Unsaved general draft')
        self.page.reload(wait_until='networkidle')
        expect(self.subject_name(kind)).to_have_value('Unsaved general draft')
        changed = self.save_subject(kind)
        self.assertEqual(changed['version'], subject['version'] + 1)
        self.assertEqual(self.case.req(self.case.profiles(kind, subject))['version'], 2)
        self.assertEqual(len([m for m in self.mutations if m['path'].endswith('/profiles') and m['method'] == 'POST']), 1)

    def test_italian_existing_item_independent_profile_and_draft(self):
        self.existing_profile('it', 'item')

    def test_english_existing_partner_dropped_profile_recovery(self):
        self.existing_profile('en', 'partner', True)

    def staged_profile(self, kind, locale):
        from playwright.sync_api import expect
        classification = self.case.classification(kind)
        # Provision real reference catalog data before entering the UI, never an item/partner.
        payload = self.case.subject_payload(kind)
        self.login(locale)
        self.subject_navigation(kind)
        if kind == 'item':
            self.page.locator('#catalog-item-new').click()
            self.subject_tab(kind, 'general')
            self.subject_name(kind).fill('Staged fiscal item')
            for selector, row in (('#item-category-id', self.case.item_refs['category']),
                                  ('#item-base-uom', next(x for x in self.case.item_refs['units'] if x['dimension'] == 'COUNT' and x['is_base']))):
                self.page.locator(selector).click()
                self.page.get_by_role('option', name=re.compile('^' + re.escape(row['name']) + r'(\s|$)')).first.click()
        else:
            self.page.get_by_role('button', name=self.messages['businessPartners']['new'], exact=True).click()
            self.subject_name(kind).fill('Staged fiscal partner')
        self.subject_tab(kind, 'taxation')
        self.profile_editor()
        self.page.locator('#tax-profile-save').click()
        expect(self.page.get_by_test_id('tax-profile-editor')).to_have_count(0)
        expect(self.page.locator('#tax-profile-history')).to_contain_text(classification['code'])
        self.assertEqual(self.mutations, [], 'Staging must not issue a write')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tax-profile-history')).to_contain_text(classification['code'])
        created = self.save_subject(kind, 'POST', 201)
        history = self.case.req(self.case.profiles(kind, created))
        self.assertEqual((history['version'], history['total']), (1, 1))
        self.assertEqual(history['items'][0]['classification_code'], classification['code'])
        posts = [m for m in self.mutations if m['method'] == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertEqual(len(posts[0]['body']['taxProfiles']), 1)

    def test_italian_new_item_staged_atomic_creation(self):
        self.staged_profile('item', 'it')

    def test_english_new_partner_staged_atomic_creation(self):
        self.staged_profile('partner', 'en')

    def test_readonly_profile_own_permissions_no_catalog_grants(self):
        from playwright.sync_api import expect
        classification = self.case.classification('item')
        subject = self.case.subject('item')
        self.case.write_profile('item', subject, classification)
        actor, role, credentials = self.case.actor(['catalog-items.read', 'tax-item-profiles.read'])
        self.login(credentials=credentials)
        self.subject_navigation('item')
        self.page.locator('#catalog-item-search').fill(subject['name'])
        row = self.page.locator('#catalog-item-table tr[data-record-id="' + subject['id'] + '"]')
        row.get_by_role('button', name=re.compile('^' + re.escape(self.messages['app']['details']) + r'\s')).click()
        self.subject_tab('item', 'taxation')
        expect(self.page.locator('#tax-profile-history')).to_contain_text(classification['code'])
        expect(self.page.locator('#tax-profile-assign')).to_have_count(0)
        expect(self.page.locator('#tax-profile-schedule')).to_have_count(0)
        self.assertEqual(self.mutations, [])
        self.assertFalse(any(r['path'] in ('/api/tax/types', '/api/tax/item-classifications') for r in self.responses))
