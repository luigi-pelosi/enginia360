"""Profilo personale: Chromium autentico su copia isolata, senza credenziali del proprietario."""
import json,secrets,unittest
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
from unified_save_support import root_client,PORTS,ORIGIN,Case,sql,Client
EVIDENCE=Path('/root/.hermes/cache/scratch/enginia360-self-profile/browser');EVIDENCE.mkdir(exist_ok=True)
MESSAGES={lang:json.loads(Path('/root/enginia360/frontend/messages/'+lang+'.json').read_text()) for lang in ('it','en')}
class SelfProfileBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch(executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',headless=True,args=['--no-sandbox'])
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.pw.stop()
 def setUp(self):
  sql('DELETE FROM foundation.login_limit;');self.root,self.root_credentials=root_client();self.case=Case(self.root);self.actor,self.user,_,self.credentials=self.case.actor([]);self.root_id=self.root.request('/api/session')[1]['id'];sql(f"UPDATE foundation.\"user\" SET preferred_language='it' WHERE id='{self.root_id}';")
  self.ctx=self.browser.new_context(viewport={'width':1440,'height':1000});self.writes=[];self.reads=[];self.errors=[]
  def forward(route):
   u=urlsplit(route.request.url);kind='backend' if u.path.startswith('/api/') else 'frontend'
   if u.path=='/api/profile':
    (self.reads if route.request.method=='GET' else self.writes).append(route.request.url)
   response=route.fetch(url=f'http://127.0.0.1:{PORTS[kind]}'+u.path+('?' +u.query if u.query else ''),headers={**route.request.all_headers(),'host':u.netloc});route.fulfill(response=response)
  self.ctx.route(ORIGIN+'/**',forward);self.page=self.ctx.new_page();self.page.on('pageerror',lambda e:self.errors.append(str(e)))
 def tearDown(self):
  try:self.assertEqual(self.errors,[])
  finally:
   self.ctx.unroute_all(behavior='wait');self.ctx.close();sql(f"UPDATE foundation.\"user\" SET preferred_language='it' WHERE id='{self.root_id}';");self.case.close()
 def login(self,global_user=False,code=None):
  self.page.goto(ORIGIN,wait_until='networkidle');c=self.root_credentials if global_user else self.credentials
  self.page.locator('#username').fill(c['username']);self.page.locator('#password').fill(c['password']);self.page.locator('#tenant-code').fill((code or '') if global_user else self.case.tenant['code'])
  self.page.get_by_role('button',name='Accedi',exact=True).click();expect(self.page.locator('.topbar-actions')).to_be_visible()
 def open(self,lang='it'):
  t=MESSAGES[lang]['app'];trigger=self.page.locator('.topbar-actions').get_by_role('button',name=t['personalProfile'],exact=True);expect(trigger).to_be_visible();trigger.click();self.page.get_by_role('menuitem',name=t['personalProfile'],exact=True).click();dialog=self.page.get_by_role('dialog',name=t['personalProfile'],exact=True);expect(dialog.locator('#profile-first_name')).to_be_visible();return dialog
 def save(self,dialog,lang='it',status=200):
  with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/profile' and r.request.method=='PUT') as response:dialog.get_by_role('button',name=MESSAGES[lang]['app']['save'],exact=True).click()
  self.assertEqual(response.value.status,status);return response.value.json()
 def test_no_grants_profile_cancel_escape_and_personal_save(self):
  self.login();self.assertEqual(self.page.locator('[data-slot=sidebar-footer]').count(),0);self.assertEqual(self.page.locator('.topbar-actions').get_by_role('button',name='Cambia password',exact=True).count(),0)
  d=self.open();expect(d.get_by_role('button',name='Salva',exact=True)).to_be_disabled();expect(d.locator('#profile-username')).to_have_attribute('readonly','');original=d.locator('#profile-first_name').input_value();d.locator('#profile-first_name').fill('Non salvare');d.get_by_role('button',name='Annulla',exact=True).click();expect(d).not_to_be_visible();self.assertEqual(self.writes,[])
  d=self.open();expect(d.locator('#profile-first_name')).to_have_value(original);d.locator('#profile-first_name').fill('Neanche questo');self.page.keyboard.press('Escape');expect(d).not_to_be_visible();self.assertEqual(self.writes,[])
  d=self.open();d.locator('#profile-first_name').fill('Profilo Browser');d.locator('#profile-email').fill('browser-profile@example.invalid');d.locator('#profile-date_of_birth').fill('1990-01-02');d.locator('#profile-phone_number').fill('+39 123');self.save(d);expect(d).not_to_be_visible();self.assertEqual(len(self.writes),1);self.assertTrue(all('tenantId' not in u for u in self.reads+self.writes));expect(self.page.locator('.topbar-actions')).to_contain_text('Profilo Browser')
  self.page.reload(wait_until='networkidle');d=self.open();expect(d.locator('#profile-email')).to_have_value('browser-profile@example.invalid');expect(d.locator('#profile-date_of_birth')).to_have_value('1990-01-02');self.page.screenshot(path=str(EVIDENCE/'personal-profile.png'));d.get_by_role('button',name='Annulla',exact=True).click()
 def test_combined_password_error_retry_session_refresh_and_follow_up_write(self):
  self.login();d=self.open();before=self.actor.request('/api/profile')[1];d.locator('#profile-first_name').fill('Profilo con password');password=secrets.token_urlsafe(28)
  for field,value in [('current','incorrect'),('new',password),('confirm',password)]:d.locator('#profile-password-'+field).fill(value)
  self.save(d,status=400);expect(d.get_by_text(MESSAGES['it']['errors']['current_password_invalid'],exact=True)).to_be_visible();expect(d.locator('#profile-first_name')).to_have_value('Profilo con password');self.assertEqual(self.actor.request('/api/profile')[1]['first_name'],before['first_name']);d.locator('#profile-password-current').fill(self.credentials['password']);self.save(d);expect(d).not_to_be_visible();expect(self.page.locator('.topbar-actions')).to_contain_text('Profilo con password');self.assertEqual(self.actor.request('/api/session')[0],401)
  client=Client();self.assertEqual(client.login({**self.credentials,'password':password},self.case.tenant['code'])[0],200)
  d=self.open();d.locator('#profile-phone_number').fill('+39 456');self.save(d);expect(d).not_to_be_visible();self.assertEqual(client.request('/api/profile')[1]['phone_number'],'+39 456');self.assertEqual(len(self.writes),3)
 def test_global_without_selected_organization_edits_own_profile(self):
  self.login(global_user=True);d=self.open();expect(d.locator('#profile-username')).to_have_value(self.root_credentials['username']);d.locator('#profile-first_name').fill('Globale Browser');p=self.save(d);self.assertEqual(p['id'],self.root_id);expect(d).not_to_be_visible();s=self.page.evaluate("fetch('/api/session').then(r=>r.json())");self.assertTrue(s['isSuperAdmin']);self.assertIsNone(s['tenantId']);self.assertIsNone(s['selectedTenantId']);self.assertTrue(all('tenantId' not in u for u in self.reads+self.writes))
 def test_global_selected_organization_survives_profile_language_reload(self):
  self.login(global_user=True,code=self.case.tenant['code']);d=self.open();d.locator('#profile-preferred_language').click();self.page.get_by_role('option',name=MESSAGES['it']['languages']['en'],exact=True).click();self.save(d);expect(self.page.locator('html')).to_have_attribute('lang','en');expect(self.page.locator('#tenant-select')).to_contain_text(self.case.tenant['name']);s=self.page.evaluate("fetch('/api/session').then(r=>r.json())");self.assertTrue(s['isSuperAdmin']);self.assertIsNone(s['tenantId']);self.assertEqual(s['selectedTenantId'],self.case.tenant['id']);d=self.open('en');expect(d.get_by_role('button',name='Save',exact=True)).to_be_disabled();expect(d.get_by_role('heading',name=MESSAGES['en']['app']['personalDetails'],exact=True)).to_be_visible();self.page.screenshot(path=str(EVIDENCE/'global-profile-en.png'));d.get_by_role('button',name='Cancel',exact=True).click()
 def test_mobile_keyboard_menu_profile_layout_and_logout(self):
  self.page.set_viewport_size({'width':390,'height':844});self.login();trigger=self.page.locator('.topbar-actions').get_by_role('button',name='Profilo personale',exact=True);box=trigger.bounding_box();self.assertGreater(box['x'],195);trigger.focus();self.page.keyboard.press('Enter');item=self.page.get_by_role('menuitem',name='Profilo personale',exact=True);expect(item).to_be_visible();self.page.keyboard.press('Escape');d=self.open();self.assertLessEqual(d.bounding_box()['width'],390);self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'));self.page.screenshot(path=str(EVIDENCE/'mobile-profile.png'));d.get_by_role('button',name='Annulla',exact=True).click();trigger.click();self.page.get_by_role('menuitem',name='Esci',exact=True).click();expect(self.page.get_by_role('heading',name='Accedi',exact=True)).to_be_visible()
if __name__=='__main__':unittest.main(verbosity=2)
