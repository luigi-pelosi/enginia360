"""Chromium reale Catalogo: navigazione completa, bozze, conflitti e due lingue.

Solo fixture enginia360-catalog-proof. Nessuna risposta API simulata.
ID attesi: catalog-new/search/table e catalog-<campo> (anche data-testid).
"""
import json
import os
import re
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit

from catalog_helpers import configure_fixture
import test_catalog_http as http


def control(scope, ident):
    return scope.locator('#' + ident + ', [data-testid="' + ident + '"]').first


@unittest.skipUnless(os.environ.get('ENGINIA360_CATALOG_PROOF') == '1' and os.environ.get('ENGINIA360_CATALOG_STATE'), 'Richiede runner browser Catalogo isolato')
class CatalogBrowserProof(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.fixture = configure_fixture()
        cls.state = json.loads(Path(os.environ['ENGINIA360_CATALOG_STATE']).read_text())
        if cls.state['scope'] != cls.fixture.SCOPE or not all(cls.fixture.verify_target(n) for n in (cls.fixture.DB, cls.fixture.API, cls.fixture.WEB)):
            raise RuntimeError('Fixture browser Catalogo incompleta/fuori scope')
        http.CatalogHttp.setUpClass()
        cls.playwright = sync_playwright().start()
        executable = os.environ.get('ENGINIA360_CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome')
        cls.browser = cls.playwright.chromium.launch(executable_path=executable, headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'browser'):
            cls.browser.close()
        if hasattr(cls, 'playwright'):
            cls.playwright.stop()

    def setUp(self):
        self.case = http.CatalogHttp('test_optimistic_conflicts_for_all_three_resources')
        self.case.setUp()
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
        self.context.set_default_timeout(15000)
        self.errors, self.mutations = [], []
        def forward(route):
            url = urlsplit(route.request.url)
            if url.netloc != urlsplit(self.fixture.ORIGIN).netloc:
                raise RuntimeError('Host esterno non ammesso')
            port = self.state['apiPort'] if url.path.startswith('/api/') else self.state['webPort']
            response = route.fetch(url=f'http://127.0.0.1:{port}' + url.path + ('?' + url.query if url.query else ''),
                                   headers={**route.request.all_headers(), 'host': url.netloc},
                                   max_retries=2 if route.request.method == 'GET' else 0)
            route.fulfill(response=response)
        self.context.route(self.fixture.ORIGIN + '/**', forward)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.on('request', lambda r: self.mutations.append((r.method, r.url)) if '/api/catalog/' in r.url and r.method in ('POST', 'PUT', 'DELETE') else None)
        self.context.tracing.start(screenshots=True, snapshots=True, sources=False)

    def tearDown(self):
        try:
            self.page.screenshot(path=str(self.fixture.EVIDENCE / (self._testMethodName + '.png')), full_page=True)
            (self.fixture.EVIDENCE / (self._testMethodName + '-events.json')).write_text(json.dumps({'pageErrors': self.errors, 'catalogRequests': self.mutations}, indent=2))
            self.context.tracing.stop(path=str(self.fixture.EVIDENCE / (self._testMethodName + '-trace.zip')))
            self.assertEqual(self.errors, [], 'Eccezioni JavaScript nel browser reale')
        finally:
            self.context.unroute_all(behavior='wait')
            self.context.close()

    def labels(self, locale):
        return json.loads((self.fixture.ROOT / 'frontend/messages' / (locale + '.json')).read_text())

    def login(self, locale, credentials=None):
        from playwright.sync_api import expect
        self.locale = locale
        self.messages = self.labels('it')
        self.page.goto(self.fixture.ORIGIN, wait_until='networkidle')
        credentials = credentials or self.case.credentials
        self.page.locator('#username').fill(credentials['username'])
        self.page.locator('#password').fill(credentials['password'])
        self.page.locator('#tenant-code').fill(self.case.code)
        self.page.get_by_role('button', name='Accedi', exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        if locale == 'en':
            self.page.get_by_role('combobox', name='Lingua', exact=True).click()
            self.page.get_by_role('option', name='English', exact=True).click()
            expect(self.page.locator('nav')).to_contain_text('Settings')
        self.messages = self.labels(locale)

    def app(self, key):
        return self.messages['app'][key]

    def resource_label(self, resource):
        # Le traduzioni sono la fonte dei nomi accessibili, non stringhe duplicate nei test.
        return self.messages['resources'][resource]

    def button(self, name, scope=None):
        return (scope or self.page).get_by_role('button', name=name, exact=True)

    def navigate(self, resource):
        from playwright.sync_api import expect
        nav = self.page.locator('nav')
        if resource == 'categories':
            expect(nav).to_contain_text(self.app('masterData'))
            self.button(self.resource_label('catalog'), nav).click()
            self.button(self.resource_label('catalog-' + resource)).click()
        else:
            self.button(self.resource_label('settings'), nav).click()
            self.button(self.app('system' if resource == 'units' else 'masterData')).click()
            if resource != 'units':
                self.button(self.resource_label('settings-catalog'), self.page.locator('#main')).click()
            self.button(self.resource_label('catalog-' + resource)).click()
        expect(self.page.locator('#main')).to_contain_text(self.resource_label('catalog-' + resource))
        self.assertEqual(parse_qs(urlsplit(self.page.url).query).get('view'), ['catalog-' + resource])

    def dialog(self):
        from playwright.sync_api import expect
        dialog = self.page.get_by_role('dialog')
        expect(dialog).to_be_visible()
        return dialog

    def field(self, field, scope=None):
        return control(scope or self.page, 'catalog-' + field)

    def save(self, resource, method, expected):
        from playwright.sync_api import expect
        dialog = self.dialog()
        with self.page.expect_response(lambda r: r.request.method == method and urlsplit(r.url).path.startswith('/api/catalog/' + resource)) as saved:
            self.button(self.app('save'), dialog).click()
        self.assertEqual(saved.value.status, expected, saved.value.text())
        if expected < 300:
            expect(self.page.get_by_role('dialog')).to_have_count(0)
        return saved.value

    def compact(self, dialog, label):
        box = dialog.bounding_box()
        self.assertIsNotNone(box)
        self.assertLessEqual(box['width'], 960, 'Dialog Catalogo non compatto')
        self.assertLessEqual(box['height'], 900, 'Dialog fuori dal viewport utile')
        self.assertGreaterEqual(box['x'], 0)
        self.assertGreaterEqual(box['y'], 0)
        self.assertLessEqual(box['x'] + box['width'], 1440)
        self.assertLessEqual(box['y'] + box['height'], 1000)
        dialog.screenshot(path=str(self.fixture.EVIDENCE / f'{self.locale}-{label}-dialog.png'))

    def editor_lifecycle(self, resource):
        from playwright.sync_api import expect
        self.navigate(resource)
        control(self.page, 'catalog-new').click()
        dialog = self.dialog()
        name_label = dialog.locator('label[for="catalog-name"]')
        expect(name_label).to_contain_text('*')
        expect(name_label.locator('span[aria-hidden="true"]')).to_be_visible()
        self.assertTrue(self.field('name', dialog).evaluate('(input) => input.required'))
        switch = self.field('is_active', dialog)
        geometry = switch.evaluate('''control => {
            const row = control.closest('.switch-field');
            const a = row.getBoundingClientRect(), b = row.parentElement.getBoundingClientRect();
            return {row:a.width, grid:b.width, border:getComputedStyle(row).borderTopWidth};
        }''')
        self.assertAlmostEqual(geometry['row'], geometry['grid'], delta=1)
        self.assertEqual(geometry['border'], '1px')
        name = f'Catalogo {self.locale} {resource}'
        self.field('name', dialog).fill(name)
        if resource == 'units':
            self.field('code', dialog).fill('B' + self.locale.upper())
        self.compact(dialog, resource + '-create')
        before = len(self.mutations)
        self.page.reload(wait_until='networkidle')
        dialog = self.dialog()
        expect(self.field('name', dialog)).to_have_value(name)
        self.assertEqual(len(self.mutations), before, 'Il refresh non deve salvare automaticamente')
        response = self.save(resource, 'POST', 201)
        created = response.json()
        self.assertEqual(self.case.req(resource, created['id'])['name'], name)
        search = control(self.page, 'catalog-search')
        search.fill(name)
        table = control(self.page, 'catalog-table')
        row = table.locator('tbody tr').filter(has_text=name)
        expect(row).to_have_count(1)
        row.get_by_role('button', name=re.compile('^' + re.escape(self.app('edit')) + r'\s')).click()
        dialog = self.dialog()
        self.field('name', dialog).fill(name + ' modificato')
        if resource == 'units':
            for field in ('dimension', 'factor_to_base', 'is_base'):
                expect(self.field(field, dialog)).to_be_disabled()
        elif resource == 'types':
            expect(self.field('kind', dialog)).to_be_disabled()
        self.page.reload(wait_until='networkidle')
        expect(self.field('name', self.dialog())).to_have_value(name + ' modificato')
        self.compact(self.dialog(), resource + '-edit')
        updated_response = self.save(resource, 'PUT', 200)
        self.assertEqual(updated_response.request.post_data_json['expectedVersion'], created['version'])
        updated = self.case.req(resource, created['id'])
        self.assertEqual(updated['name'], name + ' modificato')
        search.fill(name)
        table.locator('tbody tr').filter(has_text=name).get_by_role('button', name=re.compile('^' + re.escape(self.app('edit')) + r'\s')).click()
        self.field('name', self.dialog()).fill(name + ' bozza locale')
        winner = self.case.update(resource, updated, {'name': name + ' vincitore esterno'})
        self.page.reload(wait_until='networkidle')
        expect(self.field('name', self.dialog())).to_have_value(name + ' bozza locale')
        # Il recupero confronta la revisione originale prima di consentire scritture.
        recovered = self.dialog()
        expect(self.button(self.app('save'), recovered)).to_be_disabled()
        expect(recovered).to_contain_text(self.messages['catalog']['stale'])
        expect(recovered).to_contain_text(self.messages['catalog']['original'])
        expect(recovered).to_contain_text(self.messages['catalog']['current'])
        expect(recovered).to_contain_text(name + ' vincitore esterno')
        self.assertEqual(self.case.req(resource, created['id']), winner)
        self.page.screenshot(path=str(self.fixture.EVIDENCE / f'{self.locale}-{resource}-recovered-stale.png'), full_page=True)
        self.button(self.messages['catalog']['discardReload'], recovered).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        row = control(self.page, 'catalog-table').locator('tbody tr').filter(has_text=name)
        row.get_by_role('button', name=re.compile('^' + re.escape(self.app('edit')) + r'\s')).click()
        self.field('name', self.dialog()).fill(name + ' concorrente locale')
        # Una modifica concorrente dopo l'apertura esercita il vero PUT 409.
        newest = self.case.update(resource, winner, {'name': name + ' vincitore finale'})
        conflict = self.save(resource, 'PUT', 409)
        self.assertEqual(conflict.request.post_data_json['expectedVersion'], winner['version'])
        expect(self.field('name', self.dialog())).to_have_value(name + ' concorrente locale')
        expect(self.button(self.app('save'), self.dialog())).to_be_disabled()
        expect(self.dialog()).to_contain_text(name + ' vincitore finale')
        self.assertEqual(self.case.req(resource, created['id']), newest)
        self.page.screenshot(path=str(self.fixture.EVIDENCE / f'{self.locale}-{resource}-conflict.png'), full_page=True)
        self.page.keyboard.press('Escape')
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        control(self.page, 'catalog-search').fill('filtro da azzerare')
        self.navigate(resource)
        expect(control(self.page, 'catalog-search')).to_have_value('')
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.page.reload(wait_until='networkidle')
        expect(control(self.page, 'catalog-search')).to_have_value('')
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        print(f'Chromium {self.locale}: {resource} navigazione/create/edit/refresh/409/reset verificati', flush=True)

    def numbering_navigation(self):
        from playwright.sync_api import expect
        with self.page.expect_response(lambda r: r.request.method == 'GET' and urlsplit(r.url).path == '/api/catalog/numbering') as loaded:
            self.navigate('numbering')
        self.assertEqual(loaded.value.status, 200, loaded.value.text())
        workspace = self.page.locator('[data-catalog-workspace="catalog-numbering"]')
        for width in (1440, 390):
            self.page.set_viewport_size({'width': width, 'height': 1000})
            heading = workspace.locator('.page-heading').bounding_box()
            card = workspace.locator('[data-slot="card"]').first.bounding_box()
            self.assertAlmostEqual(card['y'] - (heading['y'] + heading['height']), 16, delta=1)
        self.page.set_viewport_size({'width': 1440, 'height': 1000})
        before = self.case.req('numbering', kind='GOOD')
        service_before = self.case.req('numbering', kind='SERVICE')
        prefix = self.field('prefix')
        if not prefix.count() or not prefix.is_visible() or prefix.is_disabled():
            control(self.page, 'catalog-table').locator('tr[data-record-id="GOOD"]').get_by_role('button', name=re.compile('^' + re.escape(self.app('edit')) + r'\s')).click()
        scope = self.dialog()
        if self.page.get_by_role('dialog').count():
            self.compact(scope, 'numbering-edit')
        self.field('prefix', scope).fill('UI-' + self.locale.upper() + '-')
        self.page.reload(wait_until='networkidle')
        scope = self.dialog()
        expect(self.field('prefix', scope)).to_have_value('UI-' + self.locale.upper() + '-')
        with self.page.expect_response(lambda r: r.request.method == 'PUT' and urlsplit(r.url).path == '/api/catalog/numbering') as saved:
            self.button(self.app('save'), scope).click()
        self.assertEqual(saved.value.status, 200, saved.value.text())
        self.assertEqual(saved.value.request.post_data_json['version'], before['version'])
        updated = self.case.req('numbering', kind='GOOD')
        self.assertEqual(updated['prefix'], 'UI-' + self.locale.upper() + '-')
        self.assertEqual(updated['version'], before['version'] + 1)
        self.assertEqual(self.case.req('numbering', kind='SERVICE'), service_before)
        self.page.screenshot(path=str(self.fixture.EVIDENCE / f'{self.locale}-numbering.png'), full_page=True)
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        control(self.page, 'catalog-table').locator('tr[data-record-id="GOOD"]').get_by_role('button', name=re.compile('^' + re.escape(self.app('edit')) + r'\s')).click()
        self.field('prefix', self.dialog()).fill('UNSAVED-RESET-')
        before_reset = len(self.mutations)
        self.page.keyboard.press('Escape')
        control(self.page, 'catalog-search').fill('reset-numbering-filter')
        self.navigate('numbering')
        expect(control(self.page, 'catalog-search')).to_have_value('')
        self.page.reload(wait_until='networkidle')
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), before_reset)
        self.assertEqual(self.case.req('numbering', kind='GOOD'), updated)
        print(f'Chromium {self.locale}: percorso impostazioni/numerazione, bozza refresh e salvataggio HTTP verificati', flush=True)

    def conversion_navigation(self):
        from decimal import Decimal
        from playwright.sync_api import expect
        source = self.case.unit(name='Browser source ' + self.locale, decimal_places=12)
        target = self.case.unit(name='Browser target ' + self.locale, decimal_places=2)
        self.navigate('units')
        control(self.page, 'catalog-search').fill(source['name'])
        row = control(self.page, 'catalog-table').locator('tr[data-record-id="' + source['id'] + '"]')
        row.get_by_role('button', name=self.messages['catalog']['convert'] + ' ' + source['name'], exact=True).click()
        dialog = self.dialog()
        self.field('target', dialog).click()
        self.page.get_by_role('option', name=target['name'] + ' (' + target['code'] + ')', exact=True).click()
        self.field('quantity', dialog).fill('1.005')
        self.page.reload(wait_until='networkidle')
        dialog = self.dialog()
        expect(self.field('quantity', dialog)).to_have_value('1.005')
        expect(self.field('target', dialog)).to_contain_text(target['name'])
        before = len(self.mutations)
        with self.page.expect_response(lambda r: '/convert' in r.url and r.request.method == 'POST') as converted:
            self.button(self.messages['catalog']['convert'], dialog).click()
        self.assertEqual(converted.value.status, 200, converted.value.text())
        body = converted.value.json()
        self.assertEqual(Decimal(body['quantity']), Decimal('1.01'))
        self.assertEqual(Decimal(body['unroundedQuantity']), Decimal('1.005'))
        self.assertTrue(body['rounded'])
        expect(dialog.locator('[role=status]')).to_contain_text(body['quantity'])
        self.assertEqual(len(self.mutations), before + 1)
        dialog.screenshot(path=str(self.fixture.EVIDENCE / f'{self.locale}-conversion-rounded.png'))
        self.field('quantity', dialog).fill('-1.005')
        expect(dialog.locator('[role=status]')).to_have_count(0)
        with self.page.expect_response(lambda r: '/convert' in r.url and r.request.method == 'POST') as negative:
            self.button(self.messages['catalog']['convert'], dialog).click()
        self.assertEqual(negative.value.status, 200)
        self.assertEqual(Decimal(negative.value.json()['quantity']), Decimal('-1.01'))
        self.button(self.app('close'), dialog.locator('[data-slot=dialog-footer]')).click()
        self.navigate('units')
        self.page.reload(wait_until='networkidle')
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(self.case.req('units', source['id']), source)
        self.assertEqual(self.case.req('units', target['id']), target)
        print(f'Chromium {self.locale}: conversion UI +/- midpoint, refresh, invalidation, no unit mutation verified', flush=True)

    def dialog_geometry(self):
        from playwright.sync_api import expect
        self.navigate('categories')
        control(self.page, 'catalog-new').click()
        dialog = self.dialog()
        self.field('name', dialog).fill('Geometry draft ' + self.locale)
        dialog.evaluate('(el) => Promise.all(el.getAnimations().map(a => a.finished))')
        original = dialog.bounding_box()
        header = dialog.locator('[data-slot=dialog-header]').bounding_box()
        self.page.mouse.move(header['x'] + 30, header['y'] + 8)
        self.page.mouse.down()
        self.page.mouse.move(header['x'] + 100, header['y'] + 48, steps=10)
        self.page.mouse.up()
        moved = dialog.bounding_box()
        self.assertGreater(moved['x'] - original['x'], 40)
        self.assertGreater(moved['y'] - original['y'], 20)
        grip = dialog.locator('[data-dialog-resize]')
        grip.scroll_into_view_if_needed()
        box = grip.bounding_box()
        self.page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
        self.page.mouse.down()
        self.page.mouse.move(box['x'] + box['width']/2 + 90, box['y'] + box['height']/2 + 45, steps=10)
        self.page.mouse.up()
        resized = dialog.bounding_box()
        self.assertGreater(resized['width'] - moved['width'], 50)
        self.assertGreater(resized['height'] - moved['height'], 20)
        self.compact(dialog, 'drag-resize')
        expect(self.field('name', dialog)).to_have_value('Geometry draft ' + self.locale)
        before = len(self.mutations)
        self.page.set_viewport_size({'width': 390, 'height': 844})
        dialog.evaluate('(el) => Promise.all(el.getAnimations().map(a => a.finished))')
        mobile = dialog.bounding_box()
        self.assertGreaterEqual(mobile['x'], 0)
        self.assertLessEqual(mobile['x'] + mobile['width'], 390)
        self.assertLessEqual(mobile['y'] + mobile['height'], 844)
        expect(self.field('name', dialog)).to_have_value('Geometry draft ' + self.locale)
        dialog.screenshot(path=str(self.fixture.EVIDENCE / f'{self.locale}-dialog-mobile.png'))
        self.button(self.app('cancel'), dialog).click()
        self.assertEqual(len(self.mutations), before)
        self.page.set_viewport_size({'width': 1440, 'height': 1000})
        print(f'Chromium {self.locale}: shared dialog drag/resize/mobile geometry and draft retention verified', flush=True)

    def test_ordinary_child_only_navigation(self):
        from playwright.sync_api import expect
        grants = ['catalog-' + resource + '.read' for resource in ('units', 'categories', 'types', 'numbering')]
        actor, _, credentials = self.case.actor(grants)
        self.login('it', credentials)
        for resource in ('categories', 'types', 'units', 'numbering'):
            self.navigate(resource)
            expect(control(self.page, 'catalog-table')).to_be_visible()
            expect(control(self.page, 'catalog-new')).to_have_count(0)
            expect(self.page.get_by_role('button', name=re.compile('^' + re.escape(self.app('edit')) + r'\s'))).to_have_count(0)
            self.page.reload(wait_until='networkidle')
            expect(control(self.page, 'catalog-table')).to_be_visible()
        self.assertEqual(self.mutations, [])
        for resource in ('settings', 'settings-system', 'settings-master-data', 'catalog'):
            self.assertFalse(any(g.startswith(resource + '.') for g in grants))
        print('Chromium ordinary read-only child grants: all four real navigation paths + refresh, no parent grants/writes verified', flush=True)

    def test_units_only_system_navigation(self):
        from playwright.sync_api import expect
        _, _, credentials = self.case.actor(['catalog-units.read'])
        self.login('it', credentials)
        self.navigate('units')
        main = self.page.locator('#main')
        expect(main).to_contain_text(self.app('system'))
        expect(control(self.page, 'catalog-table')).to_be_visible()
        self.page.reload(wait_until='networkidle')
        expect(control(self.page, 'catalog-table')).to_be_visible()
        self.button(self.app('system'), main).first.click()
        expect(main.get_by_role('button', name=self.resource_label('catalog-units'), exact=True)).to_be_visible()
        self.assertEqual(parse_qs(urlsplit(self.page.url).query).get('view'), ['settings-system'])
        self.assertEqual(self.mutations, [])

    def lifecycle(self, locale):
        self.login(locale)
        for resource in ('categories', 'types', 'units'):
            with self.subTest(locale=locale, resource=resource):
                self.editor_lifecycle(resource)
        self.numbering_navigation()
        self.conversion_navigation()
        self.dialog_geometry()
        self.assertFalse(any('/api/catalog/items' in url for _, url in self.mutations), 'Fase 2 fuori scope')

    def test_italiano_navigation_editors_refresh_conflict_reset(self):
        self.lifecycle('it')

    def test_english_navigation_editors_refresh_conflict_reset(self):
        self.lifecycle('en')


if __name__ == '__main__':
    unittest.main()
