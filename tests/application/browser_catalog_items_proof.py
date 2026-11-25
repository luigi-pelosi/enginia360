"""Real-cookie/CSRF Chromium proof. All routes reach actual candidate images.

Stable selector contract: item-* (or data-testid). Missing UI controls fail,
never skip. The bounded dropped-response test commits once then aborts only
its response, so uncertain-write recovery is tested without a synthetic API.
"""
import json
import os
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qs, urlsplit
from catalog_items_helpers import fixture, require_fixture, ORIGIN
from test_catalog_items_http import CatalogItemsHttp

BROWSER_CASES = ('test_italian_atomic_children_drafts_refresh_conflict_reset',
                 'test_english_atomic_children_drafts_refresh_conflict_reset',
                 'test_status_permissions_and_inactive_reference_selector',
                 'test_uncertain_child_commit_menu_reset_never_replays',
                 'test_status_inline_creation_validation_atomic_and_table',
                 'test_new_item_type_default_matches_saved_payload',
                 'test_inline_physical_create_edit_clear_noop',
                 'test_inline_physical_invalid_is_atomic',
                 'test_empty_unit_select_italian',
                 'test_empty_unit_select_english')


def control(scope, ident):
    return scope.locator('#' + ident + ', [data-testid="' + ident + '"]')


class CatalogItemsBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state = require_fixture(browser=True)
        images = {}
        for container, image in ((fixture.API, os.environ.get('CATALOG_BROWSER_BACKEND_IMAGE', 'enginia360-backend:catalog-items-proof')), (fixture.WEB, os.environ.get('CATALOG_BROWSER_FRONTEND_IMAGE', 'enginia360-frontend:catalog-items-proof'))):
            actual = fixture.docker('inspect', '--format', '{{.Image}}', container).stdout.strip()
            candidate = fixture.docker('image', 'inspect', '--format', '{{.Id}}', image).stdout.strip()
            if actual != candidate:
                raise RuntimeError('Fixture image differs from candidate: ' + container)
            images[container] = actual
        (fixture.EVIDENCE / 'browser-images.json').write_text(json.dumps(images, indent=2))
        CatalogItemsHttp.setUpClass()
        from playwright.sync_api import sync_playwright
        executable = Path(os.environ.get('ENGINIA360_CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome'))
        if not executable.is_file():
            raise RuntimeError('Required Chromium executable absent: ' + str(executable))
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=str(executable), headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'browser'):
            cls.browser.close()
        if hasattr(cls, 'playwright'):
            cls.playwright.stop()

    def setUp(self):
        self.case = CatalogItemsHttp('test_atomic_create_full_root_and_child_version_identity')
        self.case.setUp()
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1050})
        self.context.set_default_timeout(15000)
        self.errors, self.mutations, self.responses = [], [], []
        self.drop_next_child_response = False
        self.committed_uncertain = None
        def forward(route):
            request = route.request
            url = urlsplit(request.url)
            if url.netloc != urlsplit(ORIGIN).netloc:
                self.errors.append('Blocked external browser target: ' + url.netloc)
                route.abort('blockedbyclient')
                return
            port = self.state['apiPort'] if url.path.startswith('/api/') else self.state['webPort']
            response = route.fetch(url=f'http://127.0.0.1:{port}' + url.path + ('?' + url.query if url.query else ''),
                                   headers={**request.all_headers(), 'host': url.netloc}, max_retries=2 if request.method == 'GET' else 0, max_redirects=0)
            if self.drop_next_child_response and request.method == 'POST' and re.fullmatch(r'/api/catalog/items/[^/]+/identifiers', url.path):
                self.drop_next_child_response = False
                self.committed_uncertain = {'status': response.status, 'root': response.json()}
                route.abort('failed')
            else:
                route.fulfill(response=response)
        self.context.route('**/*', forward)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        def request_event(request):
            if '/api/catalog/' in request.url and request.method in ('POST', 'PUT', 'DELETE'):
                self.mutations.append({'method': request.method, 'url': request.url, 'body': request.post_data_json if request.post_data else None})
        self.page.on('request', request_event)
        self.page.on('response', lambda response: self.responses.append({'method': response.request.method, 'url': response.url, 'status': response.status}) if '/api/catalog/' in response.url else None)
        self.context.tracing.start(screenshots=True, snapshots=True, sources=False)

    def tearDown(self):
        try:
            self.page.screenshot(path=str(fixture.EVIDENCE / (self._testMethodName + '.png')), full_page=True)
            (fixture.EVIDENCE / (self._testMethodName + '-events.json')).write_text(json.dumps({'pageErrors': self.errors, 'requests': self.mutations, 'responses': self.responses}, indent=2))
            self.context.tracing.stop(path=str(fixture.EVIDENCE / (self._testMethodName + '-trace.zip')))
            self.assertEqual(self.errors, [], 'Real browser JavaScript exceptions')
        finally:
            self.context.unroute_all(behavior='wait')
            self.context.close()

    def login(self, locale='it', credentials=None):
        from playwright.sync_api import expect
        self.locale = locale
        self.messages = json.loads((fixture.ROOT / 'frontend/messages' / (locale + '.json')).read_text())
        self.page.goto(ORIGIN, wait_until='networkidle')
        credentials = credentials or self.case.credentials
        self.page.locator('#username').fill(credentials['username'])
        self.page.locator('#password').fill(credentials['password'])
        self.page.locator('#tenant-code').fill(self.case.code)
        self.page.get_by_role('button', name='Accedi', exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        if locale == 'en':
            self.page.get_by_role('combobox', name='Lingua', exact=True).click()
            self.page.get_by_role('option', name='English', exact=True).click()
            expect(self.page.locator('nav')).to_contain_text(self.messages['resources']['catalog'])

    def app(self, key):
        return self.messages['app'][key]

    def button(self, text, scope=None):
        return (scope or self.page).get_by_role('button', name=text, exact=True)

    def navigate(self):
        from playwright.sync_api import expect
        nav = self.page.locator('nav')
        self.button(self.messages['resources']['catalog'], nav).click()
        self.button(self.messages['resources']['catalog-items']).click()
        expect(self.page.locator('#main')).to_contain_text(self.messages['resources']['catalog-items'])
        self.assertEqual(parse_qs(urlsplit(self.page.url).query).get('view'), ['catalog-items'])

    def dialog(self):
        from playwright.sync_api import expect
        dialog = self.page.get_by_test_id('catalog-item-editor')
        expect(dialog).to_be_visible()
        return dialog

    def row_dialog(self):
        from playwright.sync_api import expect
        dialog = self.page.get_by_test_id('catalog-item-row-editor')
        expect(dialog).to_be_visible()
        return dialog

    def field(self, name, scope=None):
        aliases = {'type_id': 'type', 'base_uom_id': 'base-uom', 'identifier_type': 'identifier-type', 'identifier-value': 'value'}
        if scope is None:
            scope = self.row_dialog() if name in ('identifier_type', 'identifier-value') else self.dialog()
        return control(scope, 'item-' + aliases.get(name, name.replace('_', '-')))

    def choose(self, name, value):
        field = self.field(name)
        if field.evaluate('(element) => element.tagName') == 'SELECT':
            field.select_option(value=value['id'])
        else:
            field.click()
            self.page.get_by_role('option', name=re.compile('^' + re.escape(value['name']) + r'(\s|$)')).first.click()

    def tab(self, name):
        control(self.dialog(), 'item-tab-' + name).click()

    def open(self, row):
        from playwright.sync_api import expect
        control(self.page, 'catalog-item-search').fill(row['name'])
        record = control(self.page, 'catalog-item-table').locator('tr[data-record-id="' + row['id'] + '"]')
        expect(record).to_have_count(1)
        record.get_by_role('button', name=re.compile('^' + re.escape(self.app('edit')) + r'\s')).click()
        self.tab('general')
        expect(self.field('name')).to_have_value(row['name'])

    def save_main(self, method='PUT', expected=200):
        with self.page.expect_response(lambda response: response.request.method == method and
            re.fullmatch(r'/api/catalog/items(?:/[^/]+)?', urlsplit(response.url).path) is not None) as saved:
            control(self.dialog(), 'item-save').click()
        self.assertEqual(saved.value.status, expected, saved.value.text())
        return saved.value

    def add_identifier(self, value, staged=False):
        from playwright.sync_api import expect
        self.tab('identifiers')
        control(self.dialog(), 'item-add-identifiers').click()
        self.field('identifier_type').click()
        self.page.get_by_role('option', name='OEM', exact=True).click()
        self.field('identifier-value').fill(value)
        if staged:
            control(self.row_dialog(), 'item-row-save').click()
            expect(self.page.get_by_test_id('catalog-item-row-editor')).to_have_count(0)
            return None
        with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith('/identifiers')) as saved:
            control(self.row_dialog(), 'item-row-save').click()
        self.assertEqual(saved.value.status, 200, saved.value.text())
        # La conferma comprende la rilettura autorevole e la chiusura del portale.
        expect(self.page.get_by_test_id('catalog-item-row-editor')).to_have_count(0)
        return saved.value

    def test_new_item_type_default_matches_saved_payload(self):
        from playwright.sync_api import expect
        self.login()
        self.navigate()
        control(self.page, 'catalog-item-new').click()
        field = self.field('type_id')
        expect(field).not_to_contain_text('__none__')
        field.click()
        selected = self.page.locator('[role="option"][aria-selected="true"]')
        expect(selected).to_have_count(1)
        selected_id = selected.get_attribute('data-value')
        self.assertTrue(selected_id)
        self.assertNotEqual(selected_id, '__none__')
        self.page.keyboard.press('Escape')
        self.field('name').fill('Default type browser proof')
        self.choose('category_id', self.case.category)
        self.choose('base_uom_id', self.case.base)
        saved = self.save_main('POST', 201)
        self.assertEqual(saved.request.post_data_json['values']['item_type_id'], selected_id)
        self.assertEqual(saved.json()['item_type_id'], selected_id)

    def assert_physical_inline(self):
        from playwright.sync_api import expect
        self.tab('physical')
        panel = self.dialog().locator('#item-panel-physical')
        for name in ('net_weight', 'gross_weight', 'length', 'width', 'height', 'weight_uom_id', 'dimension_uom_id'):
            expect(self.field(name)).to_be_visible()
        expect(panel.get_by_role('button', name=re.compile(r'^(Nuovo|Modifica|Elimina|New|Edit|Delete)'))).to_have_count(0)
        expect(self.page.get_by_test_id('catalog-item-row-editor')).to_have_count(0)

    def test_inline_physical_create_edit_clear_noop(self):
        from playwright.sync_api import expect
        from decimal import Decimal
        self.login()
        self.navigate()
        control(self.page, 'catalog-item-new').click()
        self.field('name').fill('Inline physical browser')
        self.choose('category_id', self.case.category)
        self.choose('base_uom_id', self.case.base)
        self.choose('type_id', self.case.good)
        self.assert_physical_inline()
        physical = self.case.physical()
        for name in ('net_weight', 'gross_weight', 'length', 'width', 'height'):
            self.field(name).fill(physical[name])
        for field, dimension in (('weight_uom_id', 'MASS'), ('dimension_uom_id', 'LENGTH')):
            self.choose(field, next(u for u in self.case.refs['units'] if u['dimension'] == dimension and u['is_base']))
        before = len(self.mutations)
        self.page.reload(wait_until='networkidle')
        expect(self.field('net_weight')).to_have_value('1.25')
        self.assertEqual(len(self.mutations), before)
        response = self.save_main('POST', 201)
        self.assertEqual(response.request.post_data_json['physicalData'], physical)
        row = response.json()
        self.assertEqual(self.case.req('items', row['id']), row)
        self.assertEqual(Decimal(row['physicalData']['net_weight']), Decimal('1.25'))
        self.open(row)
        self.assert_physical_inline()
        self.field('net_weight').fill('1.3')
        self.page.reload(wait_until='networkidle')
        expect(self.field('net_weight')).to_have_value('1.3')
        response = self.save_main()
        self.assertEqual(response.request.post_data_json['expectedVersion'], row['version'])
        self.assertEqual(response.request.post_data_json['physicalData']['net_weight'], '1.3')
        row = response.json()
        self.assertEqual(self.case.req('items', row['id']), row)
        self.assertEqual(Decimal(row['physicalData']['net_weight']), Decimal('1.3'))
        self.open(row)
        self.assert_physical_inline()
        for name in ('net_weight', 'gross_weight', 'length', 'width', 'height'):
            self.field(name).fill('')
        for name in ('weight_uom_id', 'dimension_uom_id'):
            self.field(name).click()
            self.page.get_by_role('option', name=self.messages['catalogItems']['none'], exact=True).click()
        response = self.save_main()
        self.assertEqual(response.request.post_data_json['expectedVersion'], row['version'])
        self.assertIsNone(response.request.post_data_json['physicalData'])
        row = response.json()
        self.assertIsNone(row['physicalData'])
        self.assertEqual(self.case.req('items', row['id']), row)
        self.open(row)
        self.assert_physical_inline()
        self.field('net_weight').fill('1')
        self.field('net_weight').fill('')
        response = self.save_main()
        self.assertNotIn('physicalData', response.request.post_data_json)
        self.assertIsNone(self.case.req('items', row['id'])['physicalData'])
        self.assertFalse(any('/physical-data' in r['url'] for r in self.mutations))

    def test_inline_physical_invalid_is_atomic(self):
        row = self.case.item()
        self.login()
        self.navigate()
        self.open(row)
        self.field('name').fill('Must not partially save')
        self.assert_physical_inline()
        self.field('net_weight').fill('-1')
        response = self.save_main(expected=400)
        self.assertEqual(response.request.post_data_json['expectedVersion'], row['version'])
        self.assertEqual(self.case.req('items', row['id']), row)

    def empty_unit_select(self, locale):
        from playwright.sync_api import expect
        row = self.case.item()
        self.login(locale)
        self.navigate()
        self.open(row)
        self.tab('units')
        control(self.dialog(), 'item-add-units').click()
        child = self.row_dialog()
        trigger = self.field('uom_id', child)
        before = len(self.mutations)
        control(child, 'item-row-save').click()
        alert = child.locator('[data-slot="select-error"]')
        expect(alert).to_be_visible(timeout=3000)
        self.page.screenshot(path=str(fixture.EVIDENCE / ('empty-unit-' + locale + '.png')))
        expect(alert).to_have_text(self.messages['errors']['field_required'])
        expect(trigger).to_have_attribute('aria-invalid', 'true')
        self.assertEqual(trigger.get_attribute('aria-describedby'), alert.get_attribute('id'))
        self.assertEqual(len(self.mutations), before)
        expect(trigger).to_be_focused()
        pack = self.case.pack()
        self.page.reload(wait_until='networkidle')
        child = self.row_dialog()
        trigger = self.field('uom_id', child)
        trigger.click()
        self.page.get_by_role('option', name=re.compile('^' + re.escape(pack['name']) + r'(\s|$)')).first.click()
        with self.page.expect_response(lambda r: r.request.method == 'POST' and urlsplit(r.url).path.endswith('/units')) as saved:
            control(child, 'item-row-save').click()
        self.assertEqual(saved.value.status, 200, saved.value.text())
        self.assertEqual(saved.value.request.post_data_json['expectedVersion'], row['version'])
        self.assertEqual(self.case.req('items', row['id']), saved.value.json())

    def test_empty_unit_select_italian(self):
        self.empty_unit_select('it')

    def test_empty_unit_select_english(self):
        self.empty_unit_select('en')

    def lifecycle(self, locale):
        from playwright.sync_api import expect
        self.login(locale)
        self.navigate()
        control(self.page, 'catalog-item-new').click()
        name = 'Browser ' + locale + ' atomic item'
        self.field('name').fill(name)
        self.choose('type_id', self.case.good)
        self.choose('category_id', self.case.category)
        self.choose('base_uom_id', self.case.base)
        self.field('status').click()
        self.page.get_by_role('option', name='Bozza' if locale == 'it' else 'Draft', exact=True).click()
        before = len(self.mutations)
        self.add_identifier('STAGED-' + locale, staged=True)
        self.assertEqual(len(self.mutations), before, 'New root children must remain local')
        self.page.reload(wait_until='networkidle')
        expect(self.dialog()).to_contain_text('STAGED-' + locale)
        self.tab('general')
        expect(self.field('name')).to_have_value(name)
        row = self.save_main('POST', 201).json()
        self.case.full(row)
        self.assertEqual((row['status'], len(row['identifiers'])), ('DRAFT', 1))
        self.open(row)
        draft = name + ' UNSAVED MAIN'
        self.field('name').fill(draft)
        response = self.add_identifier('PERSISTED-' + locale)
        changed = response.json()
        self.assertEqual(response.request.post_data_json['expectedVersion'], row['version'])
        self.assertEqual(changed['name'], name, 'Confirming child must not save general draft')
        self.assertEqual(len(changed['identifiers']), 2)
        self.case.full(changed)
        # Start a row editor, then recover it along with active tab and root draft.
        control(self.dialog(), 'item-add-identifiers').click()
        self.field('identifier-value').fill('ROW-DRAFT-' + locale)
        count = len(self.mutations)
        self.page.reload(wait_until='networkidle')
        expect(self.field('identifier-value')).to_have_value('ROW-DRAFT-' + locale)
        expect(control(self.dialog(), 'item-tab-identifiers')).to_have_attribute('aria-selected', 'true')
        self.assertEqual(len(self.mutations), count)
        control(self.row_dialog(), 'item-row-cancel').click()
        self.tab('general')
        expect(self.field('name')).to_have_value(draft)
        self.assertEqual(self.case.req('items', row['id']), changed)
        saved = self.save_main().json()
        self.assertEqual(saved['name'], draft)
        self.assertEqual(saved['version'], changed['version'] + 1)
        self.open(saved)
        self.field('name').fill('Protected stale draft ' + locale)
        winner = self.case.update('items', saved, {'description': 'Concurrent winner ' + locale})
        conflict = self.save_main(expected=409)
        self.assertEqual(conflict.request.post_data_json['expectedVersion'], saved['version'])
        expect(self.field('name')).to_have_value('Protected stale draft ' + locale)
        expect(self.button(self.app('save'), self.dialog())).to_be_disabled()
        self.assertEqual(self.case.req('items', row['id']), winner)
        count = len(self.mutations)
        self.page.reload(wait_until='networkidle')
        expect(self.field('name')).to_have_value('Protected stale draft ' + locale)
        expect(self.button(self.app('save'), self.dialog())).to_be_disabled()
        self.assertEqual(len(self.mutations), count)
        self.page.keyboard.press('Escape')
        control(self.page, 'catalog-item-search').fill('RESET FILTER')
        self.navigate()
        expect(control(self.page, 'catalog-item-search')).to_have_value('')
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.page.reload(wait_until='networkidle')
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(self.case.req('items', row['id']), winner)
        self.assertEqual(len(self.mutations), count)

    def test_italian_atomic_children_drafts_refresh_conflict_reset(self):
        self.lifecycle('it')

    def test_english_atomic_children_drafts_refresh_conflict_reset(self):
        self.lifecycle('en')

    def test_status_permissions_and_inactive_reference_selector(self):
        from playwright.sync_api import expect
        brand = self.case.create('brands', {'name': 'Browser inactive brand', 'is_active': True})
        row = self.case.item(brand_id=brand['id'])
        self.case.update('brands', brand, {'is_active': False})
        _, _, credentials = self.case.actor(['catalog-items.read', 'catalog-items.update'])
        self.login('it', credentials)
        self.navigate()
        self.open(row)
        expect(self.field('brand_id')).to_contain_text(brand['name'])
        self.field('name').fill(row['name'] + ' preserve inactive')
        changed = self.save_main().json()
        self.assertEqual(changed['brand_id'], brand['id'])
        self.open(changed)
        self.field('status').click()
        expect(self.page.get_by_role('option', name='Attivo', exact=True)).to_have_attribute('data-disabled', '')
        self.page.keyboard.press('Escape')
        self.page.keyboard.press('Escape')
        status, options = self.case.root.request(self.case.path('item-options'))
        self.assertEqual(status, 200)
        self.assertFalse(next(entry for entry in options['brands'] if entry['id'] == brand['id'])['is_active'])
        unassociated = self.case.item()
        self.open(unassociated)
        self.field('brand_id').click()
        expect(self.page.get_by_role('option', name=re.compile('^' + re.escape(brand['name'])))).to_have_count(0)
        self.page.keyboard.press('Escape')
        self.page.keyboard.press('Escape')
        self.assertFalse(any(urlsplit(request['url']).path.endswith('/status') for request in self.mutations))

    def test_status_inline_creation_validation_atomic_and_table(self):
        from playwright.sync_api import expect
        brand = self.case.create('brands', {'name': 'Browser table brand', 'is_active': True})
        self.login()
        self.navigate()
        control(self.page, 'catalog-item-new').click()
        expect(self.field('status')).to_have_text('Attivo')
        self.field('name').fill('Browser active atomic')
        before = len(self.mutations)
        control(self.dialog(), 'item-save').click()
        expect(self.field('category_id')).to_have_attribute('aria-invalid', 'true')
        self.assertEqual(len(self.mutations), before)
        self.choose('category_id', self.case.category)
        control(self.dialog(), 'item-save').click()
        expect(self.field('base_uom_id')).to_have_attribute('aria-invalid', 'true')
        self.assertEqual(len(self.mutations), before)
        self.choose('base_uom_id', self.case.base)
        self.choose('brand_id', brand)
        response = self.save_main('POST', 201)
        self.assertEqual(response.request.post_data_json['status'], 'ACTIVE')
        row = response.json()
        self.assertEqual(row['status'], 'ACTIVE')
        self.assertEqual(self.case.req('items', row['id']), row)
        table = control(self.page, 'catalog-item-table')
        expect(table.locator('thead th')).to_have_text(['Codice', 'Nome', 'Natura', 'Marchio', 'Stato', 'Azioni'])
        control(self.page, 'catalog-item-search').fill(row['name'])
        record = table.locator('tr[data-record-id="' + row['id'] + '"]')
        expect(record.locator('td').nth(3)).to_have_text(brand['name'])
        expect(record.locator('td').nth(4).locator('[data-slot="badge"]')).to_have_text('Attivo')
        self.open(row)
        self.field('name').fill('Browser inline inactive atomic')
        self.field('status').click()
        self.page.get_by_role('option', name='Inattivo', exact=True).click()
        response = self.save_main()
        self.assertEqual(response.request.post_data_json['status'], 'INACTIVE')
        self.assertEqual(response.request.post_data_json['expectedVersion'], row['version'])
        changed = response.json()
        self.assertEqual((changed['status'], changed['name']), ('INACTIVE', 'Browser inline inactive atomic'))
        self.assertEqual(self.case.req('items', row['id']), changed)
        self.assertFalse(any(urlsplit(r['url']).path.endswith('/status') for r in self.mutations))

        _, _, actor = self.case.actor(['catalog-items.read', 'catalog-items.create'])
        self.context.clear_cookies()
        self.login('it', actor)
        self.navigate()
        control(self.page, 'catalog-item-new').click()
        expect(self.field('status')).to_have_text('Bozza')
        self.field('status').click()
        expect(self.page.get_by_role('option', name='Attivo', exact=True)).to_have_attribute('data-disabled', '')
        self.page.keyboard.press('Escape')
        self.field('name').fill('Browser create-only draft')
        response = self.save_main('POST', 201)
        self.assertEqual(response.json()['status'], 'DRAFT')
        self.assertNotIn('status', response.request.post_data_json)

    def test_uncertain_child_commit_menu_reset_never_replays(self):
        from playwright.sync_api import expect
        row = self.case.item()
        self.login('it')
        self.navigate()
        self.open(row)
        self.field('name').fill('Unsaved during uncertain commit')
        self.tab('identifiers')
        control(self.dialog(), 'item-add-identifiers').click()
        self.field('identifier_type').click()
        self.page.get_by_role('option', name='OEM', exact=True).click()
        self.field('identifier-value').fill('UNCERTAIN-ONCE')
        self.drop_next_child_response = True
        with self.page.expect_event('requestfailed', predicate=lambda request: request.method == 'POST' and urlsplit(request.url).path.endswith('/identifiers')):
            control(self.row_dialog(), 'item-row-save').click()
        self.assertIsNotNone(self.committed_uncertain)
        self.assertEqual(self.committed_uncertain['status'], 200)
        persisted = self.case.req('items', row['id'])
        self.assertEqual(persisted['name'], row['name'])
        self.assertEqual(persisted['version'], row['version'] + 1)
        self.assertEqual([entry['value'] for entry in persisted['identifiers']], ['UNCERTAIN-ONCE'])
        count = len(self.mutations)
        expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
        expect(control(self.page, 'catalog-item-new')).to_be_disabled()
        expect(control(self.page, 'item-review')).to_be_visible()
        self.page.reload(wait_until='networkidle')
        expect(control(self.page, 'catalog-item-new')).to_be_disabled()
        expect(control(self.page, 'item-review')).to_be_visible()
        self.navigate()
        self.page.reload(wait_until='networkidle')
        expect(control(self.page, 'catalog-item-new')).to_be_disabled()
        expect(control(self.page, 'item-review')).to_be_visible()
        self.assertEqual(len(self.mutations), count, 'Uncertain write must not auto-retry on refresh/menu reset')
        self.assertEqual(self.case.req('items', row['id']), persisted)
        control(self.page, 'item-review').click()
        expect(control(self.page, 'item-acknowledge')).to_be_visible()
        expect(self.page.locator('#main')).to_contain_text('UNCERTAIN-ONCE')
        control(self.page, 'item-acknowledge').click()
        expect(control(self.page, 'item-review')).to_have_count(0)
        self.open(persisted)
        self.tab('identifiers')
        expect(self.dialog()).to_contain_text('UNCERTAIN-ONCE')
        self.assertEqual(sum(request['method'] == 'POST' and urlsplit(request['url']).path.endswith('/identifiers') for request in self.mutations), 1)


if __name__ == '__main__':
    unittest.main()
