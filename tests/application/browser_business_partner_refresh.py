"""Chromium acceptance of BP draft recovery against the isolated proof runner."""
import unittest
from playwright.sync_api import expect
from browser_business_partners import BusinessPartnerBrowserTests


class RefreshBrowserTests(BusinessPartnerBrowserTests):
    def test_refresh_new_draft_and_open_related_without_writes(self):
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Nuovo Business Partner', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Bozza refresh isolata')
        self.page.locator('[data-action=add-contact]').click()
        self.page.locator('#bp-contact-0-value').fill('refresh@example.invalid')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#bp-legal_name')).to_have_value('Bozza refresh isolata')
        expect(self.page.locator('#bp-contact-0-value')).to_have_value('refresh@example.invalid')
        self.assertEqual(self.mutations, [])
        self.assertEqual(self.case.root.request(self.case.path())[1]['items'], [])
        self.page.locator('[data-action=cancel-related]').click()
        self.page.get_by_role('button', name='Annulla', exact=True).click()
        self.page.reload(wait_until='networkidle')
        expect(self.page.get_by_role('button', name='Nuovo Business Partner', exact=True)).to_be_visible()
        self.assertEqual(self.mutations, [])

    def test_refresh_with_fixture_user_and_explicit_permissions(self):
        import uuid
        tenant = self.case.tenant_id
        request = self.case.root.request
        username = 'refresh-' + uuid.uuid4().hex[:10]
        password = uuid.uuid4().hex + '-Initial!'
        changed = uuid.uuid4().hex + '-Changed!'
        def create(resource, values):
            status, item = request(f'/api/data/{resource}?tenantId={tenant}', 'POST', values)
            self.assertEqual(status, 201, item)
            return item
        user = create('users', {'username': username, 'first_name': 'Utente', 'last_name': 'Prova', 'email': 'refresh@example.invalid'})
        role = create('roles', {'name': 'Refresh browser'})
        codes = {'business-partners.read', 'business-partners.create', 'business-partners.update'}
        catalog = request(f'/api/data/permissions?tenantId={tenant}&pageSize=100')[1]['items']
        ids = [item['id'] for item in catalog if item['code'] in codes]
        self.assertEqual(len(ids), len(codes))
        for link, owner, targets in [('user-roles', user['id'], [role['id']]), ('role-permissions', role['id'], ids)]:
            self.assertEqual(request(f'/api/links/{link}/{owner}?tenantId={tenant}', 'PUT', {'ids': targets})[0], 204)
        self.assertEqual(request(f'/api/users/{user["id"]}/password?tenantId={tenant}', 'PUT', {'newPassword': password})[0], 204)
        from test_api import Client
        actor = Client()
        self.assertEqual(actor.login({'username': username, 'password': password}, self.case.code)[0], 200)
        self.assertEqual(actor.request('/api/auth/password', 'PUT', {'currentPassword': password, 'newPassword': changed})[0], 204)
        self.page.goto(__import__('run_business_partner_proof').ORIGIN, wait_until='networkidle')
        self.page.locator('#username').fill(username)
        self.page.locator('#password').fill(changed)
        self.page.locator('#tenant-code').fill(self.case.code)
        self.page.get_by_role('button', name='Accedi', exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        self.navigate()
        self.page.get_by_role('button', name='Nuovo Business Partner', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Bozza utente autorizzato')
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#bp-legal_name')).to_have_value('Bozza utente autorizzato')
        self.assertEqual(self.mutations, [])
        self.assertEqual(request(self.case.path())[1]['items'], [])

    def test_refresh_existing_draft_keeps_original_revision(self):
        row = self.case.create('Originale refresh isolato')
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Modifica Originale refresh isolato', exact=True).click()
        self.page.locator('#bp-legal_name').fill('Modifica locale non salvata')
        status, external = self.case.update(row, {'legal_name': 'Modifica concorrente'})
        self.assertEqual(status, 200)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#bp-legal_name')).to_have_value('Modifica locale non salvata')
        self.assertEqual(self.mutations, [])
        with self.page.expect_response(lambda r: r.request.method == 'PUT' and '/save' in r.url) as response:
            self.page.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(response.value.status, 409)
        self.assertEqual(self.case.read(row), external)
        expect(self.page.locator('#bp-legal_name')).to_have_value('Modifica locale non salvata')

if __name__ == '__main__':
    unittest.main()
