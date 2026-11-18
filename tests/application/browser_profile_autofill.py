"""Riproduzione del riempimento password attuale nel profilo, con HTTP e dati reali isolati."""
import json,unittest
from pathlib import Path
from playwright.sync_api import expect
import browser_self_profile as base
from unified_save_support import sql
base.EVIDENCE=Path('/root/.hermes/cache/scratch/enginia360-profile-autofill/browser');base.EVIDENCE.mkdir(exist_ok=True)

class ProfileAutofillBrowserTests(base.SelfProfileBrowserTests):
 def test_current_password_autofill_does_not_block_personal_save_or_rotate_credentials(self):
  self.login();d=self.open();before=sql(f"SELECT md5(password_hash || security_stamp::text) FROM foundation.\"user\" WHERE id='{self.user['id']}';").stdout
  d.locator('#profile-password-current').fill('simulated password-manager fill');expect(d.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
  d.locator('#profile-first_name').fill('Profilo senza cambio password');expect(d.get_by_role('button',name='Salva',exact=True)).to_be_enabled();expect(d.locator('#profile-password-new')).not_to_have_attribute('required','')
  for field in ('new','confirm'):
   d.locator('#profile-password-'+field).fill('short');expect(d.get_by_role('button',name='Salva',exact=True)).to_be_disabled();d.locator('#profile-password-'+field).fill('');expect(d.get_by_role('button',name='Salva',exact=True)).to_be_enabled()
  with self.page.expect_response(lambda r:r.url.endswith('/api/profile') and r.request.method=='PUT') as response:d.get_by_role('button',name='Salva',exact=True).click()
  self.assertEqual(response.value.status,200);self.assertEqual(response.value.request.post_data_json,{'values':{'first_name':'Profilo senza cambio password'}});expect(d).not_to_be_visible()
  after=sql(f"SELECT md5(password_hash || security_stamp::text) FROM foundation.\"user\" WHERE id='{self.user['id']}';").stdout;self.assertTrue(before==after,'Hash e security stamp invariati')
  status,p=self.actor.request('/api/profile');self.assertEqual(status,200);self.assertEqual(p['first_name'],'Profilo senza cambio password');self.assertEqual(len(self.writes),1)
  self.page.reload(wait_until='networkidle');d=self.open();expect(d.locator('#profile-first_name')).to_have_value('Profilo senza cambio password');d.get_by_role('button',name='Annulla',exact=True).click()

if __name__=='__main__':unittest.main(verbosity=2)
