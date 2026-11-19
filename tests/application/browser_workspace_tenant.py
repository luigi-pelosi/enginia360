"""Ripristino organizzazione del superadmin su browser e API reali isolati."""
import unittest
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import expect
import browser_business_partners as base

class WorkspaceTenantBrowserTests(unittest.TestCase):
    setUpClass = classmethod(base.BusinessPartnerBrowserTests.setUpClass.__func__)
    tearDownClass = classmethod(base.BusinessPartnerBrowserTests.tearDownClass.__func__)
    setUp = base.BusinessPartnerBrowserTests.setUp
    tearDown = base.BusinessPartnerBrowserTests.tearDown
    login = base.BusinessPartnerBrowserTests.login

    def test_explicit_login_organization_takes_precedence_over_expired_session_preference(self):
        status,other=self.case.root.request('/api/data/tenants','POST',{'name':'Preferenza scaduta '+self.case.code,'code':'stale-'+self.case.code})
        self.assertEqual(status,201,other)
        self.page.goto(base.runner.ORIGIN,wait_until='networkidle')
        user_id=self.case.root.request('/api/session')[1]['id']
        self.page.evaluate("([id,tenant])=>sessionStorage.setItem('workspace-tenant:'+id,tenant)",[user_id,other['id']])
        self.login()
        expect(self.page.locator('#tenant-select')).to_have_text(self.case.tenant['name'])

    def test_selected_organization_and_draft_survive_refresh_without_wrong_tenant_reads(self):
        status, other = self.case.root.request('/api/data/tenants','POST',{'name':'Seconda organizzazione '+self.case.code,'code':'second-'+self.case.code})
        self.assertEqual(status,201,other)
        self.login()
        self.page.locator('#tenant-select').click()
        self.page.get_by_role('option',name=other['name'],exact=True).click()
        expect(self.page.locator('#tenant-select')).to_have_text(other['name'])
        self.page.locator('nav').get_by_role('button',name='Business Partner',exact=True).click()
        self.page.get_by_role('button',name='Nuovo Business Partner',exact=True).click()
        self.page.locator('#bp-legal_name').fill('Bozza organizzazione selezionata')
        self.page.wait_for_timeout(400)
        requests=[]
        self.page.on('request',lambda request:requests.append(request.url))
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tenant-select')).to_have_text(other['name'])
        expect(self.page.locator('#bp-legal_name')).to_have_value('Bozza organizzazione selezionata')
        scoped=[parse_qs(urlsplit(url).query)['tenantId'][0] for url in requests if 'tenantId' in parse_qs(urlsplit(url).query)]
        self.assertTrue(scoped,'La pagina deve caricare il contesto selezionato')
        self.assertEqual(set(scoped),{other['id']},'Il refresh non deve leggere prima l’organizzazione del login')
        self.page.get_by_role('button',name='Annulla',exact=True).click()
        self.page.locator('#tenant-select').click()
        self.page.get_by_role('option',name='Seleziona organizzazione',exact=True).click()
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tenant-select')).to_have_text('Seleziona organizzazione')
        # Un valore non più disponibile non deve essere inviato alle API.
        self.page.evaluate("id=>sessionStorage.setItem('workspace-tenant:'+id,'00000000-0000-0000-0000-000000000001')",self.case.root.request('/api/session')[1]['id'])
        requests.clear()
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tenant-select')).to_have_text('Seleziona organizzazione')
        self.assertFalse([url for url in requests if 'tenantId' in parse_qs(urlsplit(url).query)])
        self.page.locator('#tenant-select').click()
        self.page.get_by_role('option',name=other['name'],exact=True).click()
        user_id=self.case.root.request('/api/session')[1]['id']
        expect(self.page.locator('#tenant-select')).to_have_text(other['name'])
        self.assertEqual(self.page.evaluate("id=>sessionStorage.getItem('workspace-tenant:'+id)",user_id),other['id'])
        self.page.locator('button[aria-haspopup=menu]').click()
        self.page.locator('#user-logout-menu-item').click()
        expect(self.page.locator('#username')).to_be_visible()
        self.assertIsNone(self.page.evaluate("id=>sessionStorage.getItem('workspace-tenant:'+id)",user_id))
        # Il logout revoca anche la sessione HTTP della stessa identità di prova.
        for handler in self.case.root.opener.handlers:
            if hasattr(handler,'cookiejar'):handler.cookiejar.clear()
        self.case.root.token=None
        self.assertEqual(self.case.root.login(self.case.credentials)[0],200)

if __name__=='__main__':unittest.main(verbosity=2)
