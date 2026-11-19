"""Percorsi browser isolati della fase 2 BP; nessun account o dato live."""
import unittest
from urllib.parse import urlsplit
from playwright.sync_api import expect
import browser_business_partners as base
import test_business_partner_companies as http


class BusinessPartnerCompanyBrowserTests(unittest.TestCase):
    setUpClass = classmethod(base.BusinessPartnerBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(base.BusinessPartnerBrowserTests.tearDownClass.__func__)
    setUp = base.BusinessPartnerBrowserTests.setUp
    tearDown = base.BusinessPartnerBrowserTests.tearDown
    login = base.BusinessPartnerBrowserTests.login
    navigate = base.BusinessPartnerBrowserTests.navigate

    def fixture(self):
        case = http.BusinessPartnerCompanyTests('test_01_same_identity_multiple_roles_and_companies')
        case.case = self.case
        case.root = self.case.root
        case.tenant = self.case.tenant_id
        case.a = case.create('companies', {'name': 'Service browser'})
        case.b = case.create('companies', {'name': 'Trading browser'})
        case.bp = self.case.create('Alfa browser')
        return case

    def test_01_associate_roles_and_independent_blocks_persist_without_main_save(self):
        case = self.fixture()
        self.login(); self.navigate()
        self.page.get_by_role('button', name='Modifica Alfa browser', exact=True).click()
        expect(self.page.locator('[data-bp-company-relations]')).to_be_visible()
        self.page.locator('#bp-legal_name').fill('Nome ancora locale')
        self.page.locator('[data-action=associate-company]').click()
        editor = self.page.locator('[data-bp-company-editor]')
        expect(editor).to_be_visible()
        editor.locator('#bp-company-id').click()
        self.page.get_by_role('option', name='Service browser', exact=True).click()
        editor.locator('#bp-company-CUSTOMER').check()
        editor.locator('#bp-company-SUPPLIER').check()
        with self.page.expect_response(lambda response: response.request.method=='POST' and '/companies/' in urlsplit(response.url).path and urlsplit(response.url).path.endswith('/business-partners')) as saved:
            editor.locator('[data-action=confirm-company-association]').click()
        self.assertEqual(saved.value.status, 201)
        expect(editor).to_have_count(0)
        relation = saved.value.json()
        self.assertEqual({role['role_code'] for role in relation['roles']}, {'CUSTOMER', 'SUPPLIER'})
        row = self.page.locator(f'[data-bp-company-relations] [data-company-id="{case.a["id"]}"]')
        expect(row).to_be_visible()
        row.locator(f'[data-action="manage-company-{case.a["id"]}"]').click()
        management = self.page.locator('[data-bp-company-editor=manage]')
        management.locator('[data-action=toggle-CUSTOMER]').click()
        with self.page.expect_response(lambda response: response.request.method=='PUT' and '/roles/CUSTOMER' in response.url) as blocked:
            self.page.locator('[data-action=confirm-company-operation]').click()
        self.assertEqual(blocked.value.status, 200)
        self.assertEqual(blocked.value.json()['usable_roles'], ['SUPPLIER'])
        expect(self.page.locator('[data-bp-company-confirmation]')).to_have_count(0)
        management.locator('[data-action=close-company-management]').click()
        row.locator('[data-action=toggle-relation]').click()
        with self.page.expect_response(lambda response: response.request.method=='PATCH' and '/business-partners/' in response.url) as blocked_relation:
            self.page.locator('[data-action=confirm-company-operation]').click()
        self.assertEqual(blocked_relation.value.status, 200)
        self.assertEqual(blocked_relation.value.json()['usable_roles'], [])
        expect(self.page.locator('[data-bp-company-confirmation]')).to_have_count(0)
        expect(self.page.locator('#bp-legal_name')).to_have_value('Nome ancora locale')
        self.assertEqual(self.case.read(case.bp)['legal_name'], 'Alfa browser')
        self.page.get_by_role('button', name='Annulla', exact=True).click()
        self.page.reload(wait_until='networkidle'); self.navigate()
        self.page.get_by_role('button', name='Modifica Alfa browser', exact=True).click()
        expect(row).to_be_visible()
        result = self.case.root.request(case.scope(case.endpoint(partner=case.bp)))[1]
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(next(role for role in result['roles'] if role['role_code']=='CUSTOMER')['status'], 'BLOCKED')
        self.assertEqual(self.case.read(case.bp)['version'], case.bp['version'])

    def test_02_role_company_assignment_is_explicit_and_persisted(self):
        case = self.fixture()
        role = case.role(['business-partners.read', 'business-partner-companies.read'], [])
        self.login()
        self.page.locator('nav').get_by_role('button', name='Ruoli', exact=True).click()
        self.page.get_by_role('button', name='Modifica '+role['name'], exact=True).click()
        dialog = self.page.get_by_role('dialog')
        panel = dialog.locator('[data-role-company-access]')
        expect(panel).to_be_visible()
        checkbox = panel.locator(f'[data-company-id="{case.a["id"]}"]')
        checkbox.check()
        path = case.scope('/api/roles/'+role['id']+'/companies')
        self.assertEqual(case.root.request(path)[1]['companyIds'], [])
        with self.page.expect_response(lambda response: response.request.method=='PUT' and '/roles/'+role['id']+'/companies' in response.url) as saved:
            panel.locator('[data-action=save-role-companies]').click()
        self.assertIn(saved.value.status, (200, 204))
        self.assertEqual(case.root.request(path)[1]['companyIds'], [case.a['id']])
        dialog.locator('[data-slot=dialog-footer]').get_by_role('button', name='Annulla', exact=True).click()
        self.page.get_by_role('button', name='Modifica '+role['name'], exact=True).click()
        expect(self.page.locator(f'[data-role-company-access] [data-company-id="{case.a["id"]}"]')).to_be_checked()

    def test_04_company_view_filters_structural_and_usable_roles_in_both_languages(self):
        case = self.fixture()
        relation = case.associate()
        other = case.associate(case.b, ['SUPPLIER'])
        self.assertEqual(case.root.request(case.scope(case.endpoint(case.b,case.bp)), 'PATCH', {'status':'BLOCKED','expectedVersion':other['version']})[0], 200)
        self.assertEqual(case.role_change(relation, 'CUSTOMER', 'BLOCKED')[0], 200)
        self.login()
        for locale, supplier, customer in (('it', 'Fornitore', 'Cliente'), ('en', 'Supplier', 'Customer')):
            self.page.evaluate('sessionStorage.clear()')
            self.page.set_viewport_size({'width':1440,'height':1000})
            self.context.add_cookies([{'name':'locale','value':locale,'url':base.runner.ORIGIN}])
            self.page.reload(wait_until='networkidle')
            self.page.locator('nav').get_by_role('button',name='Business Partner',exact=True).click()
            self.page.locator('[data-action=partner-company-view]').click()
            company = self.page.locator('#company-partner-company')
            expect(company).to_have_text('Tutte le aziende' if locale=='it' else 'All companies')
            expect(self.page.locator('#company-partner-role')).to_have_text('Tutti i ruoli' if locale=='it' else 'All roles')
            expect(self.page.locator('#company-partner-usable')).not_to_be_checked()
            all_rows = self.page.locator(f'[data-company-partners] [data-business-partner-id="{case.bp["id"]}"]')
            expect(all_rows).to_have_count(2)
            expect(all_rows.filter(has_text='Trading browser')).to_contain_text('Bloccato' if locale=='it' else 'Blocked')
            expect(all_rows.filter(has_text='Service browser')).to_contain_text(customer)
            company.click(); self.page.get_by_role('option',name='Service browser',exact=True).click()
            partner = self.page.locator(f'[data-company-partners] [data-business-partner-id="{case.bp["id"]}"]')
            expect(partner).to_be_visible()
            expect(partner.locator('[data-usable-roles]')).to_have_text(supplier)
            self.page.locator('#company-partner-usable').check()
            self.page.locator('#company-partner-role').click()
            self.page.get_by_role('option',name=customer,exact=True).click()
            expect(partner).to_have_count(0)
            self.page.locator('#company-partner-usable').uncheck()
            expect(partner).to_be_visible()
            expect(partner).to_contain_text('Alfa browser')
            self.page.locator('#company-partner-search').fill('non presente')
            expect(partner).to_have_count(0)
            self.page.locator('#company-partner-search').fill('Alfa')
            expect(partner).to_be_visible()
            self.page.set_viewport_size({'width':390,'height':1000})
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),390)
            self.page.screenshot(path=str(base.runner.EVIDENCE/f'bp-phase2-company-view-{locale}.png'),full_page=True)
            self.page.set_viewport_size({'width':1440,'height':1000})

    def test_03_scoped_reader_has_no_trading_mutation_controls(self):
        case = self.fixture()
        case.associate(); case.associate(case.b)
        actor, role = self.case.actor(['business-partners.read','business-partner-companies.read','business-partner-companies.update'])
        case.assign_companies(role,[case.a])
        other = case.role(['business-partners.read','business-partner-companies.read'],[case.b])
        user = actor.request('/api/session')[1]['id']
        self.assertEqual(case.root.request(case.scope('/api/links/user-roles/'+user),'PUT',{'ids':[role['id'],other['id']]})[0],204)
        cookies = next(handler.cookiejar for handler in actor.opener.handlers if hasattr(handler,'cookiejar'))
        self.context.add_cookies([{'name':cookie.name,'value':cookie.value,'url':base.runner.ORIGIN} for cookie in cookies])
        self.page.goto(base.runner.ORIGIN,wait_until='networkidle')
        self.page.locator('nav').get_by_role('button',name='Business Partner',exact=True).click()
        self.page.get_by_role('button',name='Dettagli Alfa browser',exact=True).click()
        section = self.page.locator('[data-bp-company-relations]')
        service = section.locator(f'[data-company-id="{case.a["id"]}"]')
        trading = section.locator(f'[data-company-id="{case.b["id"]}"]')
        expect(service.locator('[data-action=toggle-relation]')).to_be_visible()
        expect(trading.locator('[data-action=toggle-relation]')).to_have_count(0)
        expect(trading.locator('[data-action=toggle-CUSTOMER]')).to_have_count(0)
        self.page.set_viewport_size({'width':390,'height':1000})
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),390)
        self.page.screenshot(path=str(base.runner.EVIDENCE/'bp-phase2-scoped-mobile.png'),full_page=True)


if __name__=='__main__':
    unittest.main(verbosity=2)
