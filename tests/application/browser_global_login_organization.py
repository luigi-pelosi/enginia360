"""Browser reale: preselezione globale distinta dall'identità e cambio organizzazione."""
import json
from pathlib import Path
import secrets
import unittest
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
from unified_save_support import root_client,PORTS,ORIGIN,Case,sql,Client,PRIVATE

EVIDENCE=Path('/root/.hermes/cache/scratch/enginia360-login-preselection/browser')
EVIDENCE.mkdir(parents=True,exist_ok=True)


class GlobalLoginBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright=sync_playwright().start()
        cls.browser=cls.playwright.chromium.launch(executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.playwright.stop()
    def setUp(self):
        sql('DELETE FROM foundation.login_limit;')
        self.root,self.credentials=root_client();self.case=Case(self.root);self.other=Case(self.root)
        for case,label in ((self.case,'A'),(self.other,'B')):
            case.tenant['name']='Login '+label+' '+case.tenant['id'][:8]
            self.assertEqual(self.root.request('/api/data/tenants/'+case.tenant['id'],'PUT',{'name':case.tenant['name']})[0],200)
            company=case.create('companies',{'name':'Azienda '+label})
            case.create('sites',{'company_id':company['id'],'name':'Sede '+label})
        self.context=self.browser.new_context(viewport={'width':1440,'height':1000})
        def forward(route):
            u=urlsplit(route.request.url);kind='backend' if u.path.startswith('/api/') else 'frontend'
            response=route.fetch(url=f'http://127.0.0.1:{PORTS[kind]}'+u.path+('?' +u.query if u.query else ''),headers={**route.request.all_headers(),'host':u.netloc});route.fulfill(response=response)
        self.context.route(ORIGIN+'/**',forward);self.page=self.context.new_page();self.errors=[];self.page.on('pageerror',lambda e:self.errors.append(str(e)))
    def tearDown(self):
        try:
            self.page.screenshot(path=str(EVIDENCE/(self._testMethodName+'.png')));self.assertEqual(self.errors,[])
        finally:
            self.context.unroute_all(behavior='wait');self.context.close();self.other.close();self.case.close()
    def login(self,code=None):
        self.page.goto(ORIGIN,wait_until='networkidle');self.page.locator('#username').fill(self.credentials['username']);self.page.locator('#password').fill(self.credentials['password'])
        self.page.locator('#tenant-code').fill(code or '')
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/auth/login') as response:self.page.get_by_role('button',name='Accedi',exact=True).click()
        self.assertEqual(response.value.status,200);return response.value.json()
    def test_selected_organization_is_visible_survives_reload_and_can_be_changed(self):
        session=self.login(self.case.tenant['code']);self.assertTrue(session['isSuperAdmin']);self.assertIsNone(session['tenantId']);self.assertEqual(session['selectedTenantId'],self.case.tenant['id'])
        expect(self.page.locator('#tenant-select')).to_contain_text(self.case.tenant['name'])
        self.page.reload(wait_until='networkidle');expect(self.page.locator('#tenant-select')).to_contain_text(self.case.tenant['name'])
        self.page.locator('nav').get_by_role('button',name='Sedi',exact=True).click();expect(self.page.locator('tbody')).to_contain_text('Sede A');expect(self.page.locator('tbody')).not_to_contain_text('Sede B')
        self.page.locator('#tenant-select').click();self.page.get_by_role('option',name=self.other.tenant['name'],exact=True).click();expect(self.page.locator('tbody')).to_contain_text('Sede B');expect(self.page.locator('tbody')).not_to_contain_text('Sede A')
        expect(self.page.locator('nav').get_by_role('button',name='Organizzazioni',exact=True)).to_be_visible()
    def test_preselection_survives_the_preferred_language_login_reload(self):
        actor=self.root.request('/api/session')[1]['id'];sql(f"UPDATE foundation.\"user\" SET preferred_language='en' WHERE id='{actor}';")
        try:
            self.login(self.case.tenant['code']);expect(self.page.locator('html')).to_have_attribute('lang','en');expect(self.page.locator('#tenant-select')).to_contain_text(self.case.tenant['name'])
            self.page.locator('nav').get_by_role('button',name='Sites',exact=True).click();expect(self.page.locator('tbody')).to_contain_text('Sede A')
        finally:sql(f"UPDATE foundation.\"user\" SET preferred_language='it' WHERE id='{actor}';")
    def test_omitted_code_does_not_reuse_a_previous_login_selection(self):
        self.login(self.case.tenant['code']);expect(self.page.locator('#tenant-select')).to_contain_text(self.case.tenant['name'])
        self.page.locator('.topbar-actions').get_by_role('button',name='Profilo personale',exact=True).click();self.page.get_by_role('menuitem',name='Esci',exact=True).click();expect(self.page.get_by_role('heading',name='Accedi',exact=True)).to_be_visible()
        self.page.locator('#password').fill(self.credentials['password']);self.page.locator('#tenant-code').fill('')
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/auth/login') as response:self.page.get_by_role('button',name='Accedi',exact=True).click()
        self.assertEqual(response.value.status,200);self.assertIsNone(response.value.json().get('selectedTenantId'));expect(self.page.locator('#tenant-select')).to_contain_text('Seleziona organizzazione')
    def test_z_forced_password_change_preserves_selected_context(self):
        actor=self.root.request('/api/session')[1]['id'];sql(f"UPDATE foundation.\"user\" SET must_change_password=true WHERE id='{actor}';")
        client=Client();status,session=client.login(self.credentials,self.case.tenant['code']);self.assertEqual(status,200);self.assertTrue(session['mustChangePassword'])
        password=secrets.token_urlsafe(30);self.assertEqual(client.request('/api/auth/password','PUT',{'currentPassword':self.credentials['password'],'newPassword':password})[0],204)
        status,session=client.request('/api/session');self.assertEqual(status,200);self.assertEqual(session['selectedTenantId'],self.case.tenant['id']);self.assertIsNone(session['tenantId']);self.assertFalse(session['mustChangePassword'])
        self.credentials['password']=password;(PRIVATE/'bootstrap.json').write_text(json.dumps(self.credentials))
        self.login(self.case.tenant['code']);expect(self.page.locator('#tenant-select')).to_contain_text(self.case.tenant['name'])

if __name__=='__main__':unittest.main(verbosity=2)
