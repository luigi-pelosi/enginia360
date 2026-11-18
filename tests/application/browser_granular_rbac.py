"""Percorsi Chromium autentici contro frontend e API della copia RBAC isolata."""
import json
import re
from pathlib import Path
import secrets
import sys
import unittest
from urllib.parse import urlsplit
import uuid

import run_isolated_rbac  # Imposta il solo trasporto locale di verifica.
from test_granular_rbac import GranularRbacTests
from playwright.sync_api import sync_playwright, expect

ORIGIN = run_isolated_rbac.ORIGIN
EVIDENCE = Path('/root/.hermes/cache/scratch/enginia360-rbac/browser')
EVIDENCE.mkdir(parents=True, exist_ok=True)


class BrowserRbacTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        GranularRbacTests.setUpClass()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',
            headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.fixture = GranularRbacTests()
        self.fixture.setUp()
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
        def forward(route):
            url = urlsplit(route.request.url)
            if url.netloc != 'vmi3659251.tailfcced0.ts.net:8080':
                raise RuntimeError('Host inatteso nella verifica isolata')
            target = 'http://127.0.0.1:18082' if url.path.startswith('/api/') else 'http://127.0.0.1:18083'
            response = route.fetch(url=target + url.path + ('?' + url.query if url.query else ''),
                                   headers={**route.request.all_headers(), 'host': url.netloc})
            route.fulfill(response=response)
        self.context.route(ORIGIN + '/**', forward)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

    def tearDown(self):
        try:
            self.page.screenshot(path=str(EVIDENCE / (self._testMethodName + '.png')), full_page=True)
            self.assertEqual(self.errors, [])
        finally:
            self.context.close()
            self.fixture.tearDown()

    def login(self, credentials, tenant_code=''):
        self.page.goto(ORIGIN, wait_until='networkidle')
        self.page.locator('#username').fill(credentials['username'])
        self.page.locator('#password').fill(credentials['password'])
        if tenant_code:
            self.page.locator('#tenant-code').fill(tenant_code)
        self.page.get_by_role('button', name='Accedi', exact=True).click()
        self.page.wait_for_function("document.querySelector('#current-password') || document.querySelector('[data-slot=sidebar-wrapper]')")
        if self.page.locator('#current-password').count():
            new = secrets.token_urlsafe(24)
            self.page.locator('#current-password').fill(credentials['password'])
            self.page.locator('#new-password').fill(new)
            self.page.locator('#confirm-password').fill(new)
            self.page.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()

    def actor(self, codes):
        user = self.fixture.user()
        role = self.fixture.role(codes)
        self.assertEqual(self.fixture.replace('user-roles', user['id'], [role['id']])[0], 204)
        password = secrets.token_urlsafe(24)
        self.assertEqual(self.fixture.root.request(f"/api/users/{user['id']}/password?tenantId={self.fixture.tenant['id']}",
                                                   'PUT', {'newPassword': password})[0], 204)
        self.login({'username': user['username'], 'password': password}, self.fixture.tenant['code'])
        return user, role

    def navigate(self, name):
        self.page.locator('nav').get_by_role('button', name=name, exact=True).click()

    def test_creator_can_create_without_update_delete_or_reset_controls(self):
        self.actor(['companies.read', 'companies.create'])
        self.navigate('Aziende')
        expect(self.page.get_by_role('button', name='Nuovo', exact=True).first).to_be_visible()
        self.page.get_by_role('button', name='Nuovo', exact=True).first.click()
        dialog = self.page.get_by_role('dialog')
        dialog.locator('#field-code').fill('browser-' + uuid.uuid4().hex[:8])
        dialog.locator('#field-name').fill('Società browser')
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        row = self.page.locator('tbody tr').filter(has_text='Società browser')
        expect(row).to_be_visible()
        expect(row.get_by_role('button', name='Dettagli Società browser', exact=True)).to_be_visible()
        self.assertEqual(row.get_by_role('button', name=re.compile('^(Modifica|Elimina|Imposta password) ')).count(), 0)

    def test_assigner_can_manage_roles_while_profile_is_read_only_and_refresh_revokes_controls(self):
        target = self.fixture.user()
        chosen = self.fixture.role(['companies.read'])
        _, own_role = self.actor(['users.read', 'roles.read', 'roles.assign'])
        self.navigate('Utenti')
        row = self.page.locator('tbody tr').filter(has_text=target['username'])
        row.get_by_role('button', name='Dettagli Operatore Verifica', exact=True).click()
        dialog = self.page.get_by_role('dialog')
        expect(dialog.locator('#field-first_name')).to_be_disabled()
        self.assertEqual(dialog.get_by_role('button', name='Salva', exact=True).count(), 0)
        section = dialog.locator('section').filter(has=self.page.get_by_role('heading', name='Ruoli utente', exact=True))
        choice = section.locator('.relation-option').filter(has_text=chosen['code']).get_by_role('checkbox')
        expect(choice).to_be_enabled()
        choice.check()
        section.get_by_role('button', name='Salva · Ruoli utente', exact=True).click()
        expect(section.locator('[role=status]')).to_be_visible()
        self.assertEqual(self.fixture.root.request(self.fixture.links('user-roles', target['id']))[1]['ids'], [chosen['id']])
        dialog.get_by_role('button', name='Annulla', exact=True).click()
        self.fixture.set_grants(own_role['id'], ['users.read', 'roles.read'])
        with self.page.expect_response(lambda response: urlsplit(response.url).path == '/api/session'):
            self.page.get_by_role('button', name='Aggiorna', exact=True).click()
        row.get_by_role('button', name='Dettagli Operatore Verifica', exact=True).click()
        dialog = self.page.get_by_role('dialog')
        choice = dialog.locator('.relation-option').filter(has_text=chosen['code']).get_by_role('checkbox')
        expect(choice).to_be_disabled()

    def test_permission_assignment_works_without_editing_the_role(self):
        target = self.fixture.role(['companies.read'])
        self.actor(['roles.read', 'permissions.read', 'roles.assign_permissions'])
        self.navigate('Ruoli')
        row = self.page.locator('tbody tr').filter(has_text=target['code'])
        row.get_by_role('button', name='Dettagli Ruolo verifica', exact=True).click()
        dialog = self.page.get_by_role('dialog')
        expect(dialog.locator('#field-name')).to_be_disabled()
        option = dialog.locator('.relation-option').filter(has_text='companies.create')
        expect(option.get_by_role('checkbox')).to_be_enabled()
        option.get_by_role('checkbox').check()
        dialog.get_by_role('button', name='Salva · Permessi del ruolo', exact=True).click()
        expect(dialog.locator('[role=status]')).to_be_visible()
        expected = {self.fixture.catalog[c]['id'] for c in ('companies.read','companies.create')}
        actual = self.fixture.root.request(self.fixture.links('role-permissions', target['id']))[1]['ids']
        self.assertEqual(set(actual), expected)

    def test_catalog_is_read_only_localized_and_mobile_has_no_overflow(self):
        self.login(GranularRbacTests.credentials)
        self.page.locator('#tenant-select').click()
        self.page.get_by_role('option', name='Verifica RBAC', exact=True).click()
        self.navigate('Permessi')
        expect(self.page.locator('.table-count')).to_contain_text('41')
        self.assertEqual(self.page.get_by_role('button', name='Nuovo', exact=True).count(), 0)
        self.page.get_by_role('textbox', name='Cerca', exact=True).fill('companies.read')
        row = self.page.locator('tbody tr').filter(has_text='companies.read')
        expect(row).to_be_visible()
        expect(row).to_contain_text(re.compile('aziend', re.IGNORECASE))
        self.assertEqual(row.get_by_role('button', name=re.compile('^(Modifica|Elimina) ')).count(), 0)
        row.get_by_role('button', name=re.compile('^Dettagli ')).click()
        dialog = self.page.get_by_role('dialog')
        expect(dialog.locator('#field-code')).to_be_disabled()
        self.assertEqual(dialog.get_by_role('button', name='Salva', exact=True).count(), 0)
        dialog.get_by_role('button', name='Annulla', exact=True).click()
        self.page.get_by_role('combobox', name='Lingua', exact=True).click()
        self.page.get_by_role('option', name='English', exact=True).click()
        expect(self.page.locator('html')).to_have_attribute('lang', 'en')
        self.page.locator('#tenant-select').click()
        self.page.get_by_role('option', name='Verifica RBAC', exact=True).click()
        self.navigate('Permissions')
        self.page.get_by_role('textbox', name='Search', exact=True).fill('companies.read')
        expect(self.page.locator('tbody tr').filter(has_text='companies.read')).to_contain_text(re.compile('compan', re.IGNORECASE))
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))


if __name__ == '__main__':
    unittest.main(defaultTest='BrowserRbacTests', argv=[sys.argv[0], *sys.argv[1:]], verbosity=2)
