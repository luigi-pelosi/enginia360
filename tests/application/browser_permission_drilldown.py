"""Drill-down permessi: Chromium e API reali della sola copia isolata."""
import http.client
import json
import os
from pathlib import Path
import secrets
import sys
import unittest
import urllib.request
from urllib.parse import urlsplit
import uuid

ORIGIN = 'https://vmi3659251.tailfcced0.ts.net:8080'
PRIVATE = Path('/root/.config/enginia360/permission-drilldown')
EVIDENCE = Path('/root/.hermes/cache/scratch/enginia360-permission-drilldown/browser')
EVIDENCE.mkdir(parents=True, exist_ok=True)
os.environ.update(ENGINIA360_TEST_BASE=ORIGIN, ENGINIA360_TEST_ORIGIN=ORIGIN)


class IsolatedTransport(urllib.request.HTTPSHandler):
    def https_open(self, request):
        assert request.host == urlsplit(ORIGIN).netloc
        return self.do_open(lambda host, **kwargs: http.client.HTTPConnection('127.0.0.1', 18084, **kwargs), request)


original = urllib.request.build_opener
urllib.request.build_opener = lambda *handlers: original(IsolatedTransport(), *handlers)
from test_api import Client
from playwright.sync_api import sync_playwright, expect


class PermissionDrilldownBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.credentials = json.loads((PRIVATE / 'bootstrap.json').read_text())
        cls.client = Client()
        status, session = cls.client.login(cls.credentials)
        assert status == 200
        if session['mustChangePassword']:
            updated = secrets.token_urlsafe(28)
            assert cls.client.request('/api/auth/password', 'PUT', {
                'currentPassword': cls.credentials['password'], 'newPassword': updated,
            })[0] == 204
            cls.credentials['password'] = updated
            (PRIVATE / 'bootstrap.json').write_text(json.dumps(cls.credentials))
            cls.client.token = None
        status, cls.tenant = cls.client.request('/api/data/tenants', 'POST', {
            'code': 'drilldown-' + uuid.uuid4().hex, 'name': 'Verifica drill-down',
        })
        assert status == 201
        status, catalog = cls.client.request('/api/data/permissions?tenantId=' + cls.tenant['id'] + '&pageSize=100')
        assert status == 200 and len(catalog['items']) == 41
        cls.catalog = {row['code']: row['id'] for row in catalog['items']}
        status, cls.role = cls.client.request('/api/data/roles?tenantId=' + cls.tenant['id'], 'POST', {
            'code': 'drilldown-role', 'name': 'Ruolo drill-down',
        })
        assert status == 201
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',
            headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        path = '/api/links/role-permissions/' + cls.role['id'] + '?tenantId=' + cls.tenant['id']
        assert cls.client.request(path, 'PUT', {'ids': []})[0] == 204
        assert cls.client.request('/api/data/roles/' + cls.role['id'] + '?tenantId=' + cls.tenant['id'], 'DELETE')[0] == 204
        assert cls.client.request('/api/data/tenants/' + cls.tenant['id'], 'DELETE')[0] == 204

    def setUp(self):
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
        def forward(route):
            url = urlsplit(route.request.url)
            assert url.netloc == urlsplit(ORIGIN).netloc
            port = 18084 if url.path.startswith('/api/') else 18085
            response = route.fetch(url=f'http://127.0.0.1:{port}' + url.path + ('?' + url.query if url.query else ''),
                                   headers={**route.request.all_headers(), 'host': url.netloc})
            route.fulfill(response=response)
        self.context.route(ORIGIN + '/**', forward)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.goto(ORIGIN, wait_until='networkidle')
        self.page.locator('#username').fill(self.credentials['username'])
        self.page.locator('#password').fill(self.credentials['password'])
        self.page.get_by_role('button', name='Accedi', exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        self.select_tenant()

    def tearDown(self):
        try:
            self.page.screenshot(path=str(EVIDENCE / (self._testMethodName + '.png')), full_page=True)
            self.assertEqual(self.errors, [])
        finally:
            self.context.close()

    def select_tenant(self):
        self.page.locator('#tenant-select').click()
        self.page.get_by_role('option', name='Verifica drill-down', exact=True).click()

    def catalog_page(self):
        self.page.locator('nav').get_by_role('button', name='Permessi', exact=True).click()
        expect(self.page.locator('.table-count')).to_contain_text('41')

    def expand(self, locator):
        summary = locator.locator(':scope > summary')
        summary.click()
        expect(locator).to_have_attribute('open', '')

    def test_catalog_drills_from_three_domains_to_resources_and_exact_operations(self):
        self.catalog_page()
        domains = self.page.locator('[data-permission-domain]')
        expect(domains).to_have_count(3)
        for domain, count in [('organization', 8), ('warehouse', 12), ('administration', 21)]:
            branch = self.page.locator(f'[data-permission-domain="{domain}"]')
            self.assertIsNone(branch.get_attribute('open'), 'I domini partono chiusi')
            expect(branch.locator(':scope > summary')).to_contain_text(str(count))
        branch = self.page.locator('[data-permission-domain="organization"]')
        self.expand(branch)
        companies = branch.locator('[data-permission-resource="companies"]')
        self.assertIsNone(companies.get_attribute('open'))
        companies.locator(':scope > summary').focus()
        self.page.keyboard.press('Enter')
        expect(companies).to_have_attribute('open', '')
        leaves = companies.locator('[data-permission-code]')
        self.assertEqual(leaves.evaluate_all('(nodes) => nodes.map(n => n.dataset.permissionCode)'),
                         ['companies.read','companies.create','companies.update','companies.delete'])
        leaf = companies.locator('[data-permission-code="companies.read"]')
        expect(leaf).to_be_visible()
        leaf.get_by_role('button').click()
        dialog = self.page.get_by_role('dialog')
        expect(dialog.locator('#field-code')).to_have_value('companies.read')
        expect(dialog.locator('#field-code')).to_be_disabled()
        self.assertEqual(dialog.get_by_role('button', name='Salva', exact=True).count(), 0)
        dialog.get_by_role('button', name='Annulla', exact=True).click()
        self.assertEqual(self.page.get_by_role('button', name='Nuovo', exact=True).count(), 0)
        self.assertEqual(self.page.locator('[data-permission-code]').count(), 41)

    def test_search_opens_matching_domains_and_resources_in_both_languages(self):
        self.catalog_page()
        search = self.page.get_by_role('textbox', name='Cerca', exact=True)
        search.fill('Warehouse')
        expect(self.page.locator('.table-count')).to_contain_text('12')
        expect(self.page.locator('[data-permission-domain]')).to_have_count(1)
        expect(self.page.locator('[data-permission-domain="warehouse"]')).to_have_attribute('open', '')
        expect(self.page.locator('[data-permission-code]')).to_have_count(12)
        search.fill('users.reset_password')
        expect(self.page.locator('[data-permission-code]')).to_have_count(1)
        expect(self.page.locator('[data-permission-code="users.reset_password"]')).to_be_visible()
        search.fill('nessun-risultato')
        expect(self.page.locator('[data-permission-domain]')).to_have_count(0)
        expect(self.page.get_by_text('Nessun risultato', exact=True)).to_be_visible()
        search.fill('')
        expect(self.page.locator('[data-permission-domain]')).to_have_count(3)
        self.page.get_by_role('combobox', name='Lingua', exact=True).click()
        self.page.get_by_role('option', name='English', exact=True).click()
        expect(self.page.locator('html')).to_have_attribute('lang', 'en')
        self.select_tenant()
        self.page.locator('nav').get_by_role('button', name='Permissions', exact=True).click()
        self.page.get_by_role('textbox', name='Search', exact=True).fill('Organizzazione')
        expect(self.page.locator('.table-count')).to_contain_text('8')
        expect(self.page.locator('[data-permission-domain="organization"] > summary')).to_contain_text('Organization')
        self.assertEqual(self.page.locator('[data-permission-code]').count(), 8)
        self.page.set_viewport_size({'width':390,'height':844})
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))

    def test_role_picker_keeps_hidden_selections_and_persists_exact_ids(self):
        self.page.locator('nav').get_by_role('button', name='Ruoli', exact=True).click()
        self.page.get_by_role('button', name='Modifica Ruolo drill-down', exact=True).click()
        dialog = self.page.get_by_role('dialog')
        section = dialog.locator('section').filter(has=self.page.get_by_role('heading', name='Permessi del ruolo', exact=True))
        expect(section.locator('[data-permission-domain]')).to_have_count(3)
        search = section.get_by_role('textbox')
        search.fill('companies.read')
        first = section.locator('[data-permission-code="companies.read"]').get_by_role('checkbox')
        expect(first).to_be_enabled()
        first.check()
        search.fill('warehouses.update')
        second = section.locator('[data-permission-code="warehouses.update"]').get_by_role('checkbox')
        expect(second).to_be_enabled()
        second.check()
        search.fill('companies.read')
        expect(section.locator('[data-permission-code="companies.read"]').get_by_role('checkbox')).to_be_checked()
        section.get_by_role('button', name='Salva · Permessi del ruolo', exact=True).click()
        expect(section.locator('[role=status]')).to_be_visible()
        path = '/api/links/role-permissions/' + self.role['id'] + '?tenantId=' + self.tenant['id']
        self.assertEqual(set(self.client.request(path)[1]['ids']), {self.catalog['companies.read'], self.catalog['warehouses.update']})
        dialog.get_by_role('button', name='Annulla', exact=True).click()
        self.page.get_by_role('button', name='Modifica Ruolo drill-down', exact=True).click()
        section = self.page.get_by_role('dialog').locator('section').filter(has=self.page.get_by_role('heading', name='Permessi del ruolo', exact=True))
        section.get_by_role('textbox').fill('warehouses.update')
        expect(section.locator('[data-permission-code="warehouses.update"]').get_by_role('checkbox')).to_be_checked()


if __name__ == '__main__':
    unittest.main(defaultTest='PermissionDrilldownBrowserTests', verbosity=2)
