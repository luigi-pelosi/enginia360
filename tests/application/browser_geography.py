"""Cataloghi globali e indirizzo locale: browser autentico sulla candidata isolata."""
from pathlib import Path
import json,re,unittest
from urllib.parse import urlsplit,urlencode
from playwright.sync_api import expect
import browser_self_profile as base
from unified_save_support import sql
EVIDENCE=Path('/root/.hermes/cache/scratch/enginia360-geography/browser');EVIDENCE.mkdir(exist_ok=True)
M=base.MESSAGES
class GeographyBrowserTests(unittest.TestCase):
 setUpClass=classmethod(base.SelfProfileBrowserTests.setUpClass.__func__)
 tearDownClass=classmethod(base.SelfProfileBrowserTests.tearDownClass.__func__)
 def setUp(self):
  base.SelfProfileBrowserTests.setUp(self);self.business=[];self.page.on('request',lambda r:self.business.append((r.method,urlsplit(r.url).path)) if '/api/data/' in r.url and r.method not in ('GET','HEAD') else None)
 def tearDown(self):
  try:self.page.screenshot(path=str(EVIDENCE/(self._testMethodName+'.png')))
  finally:base.SelfProfileBrowserTests.tearDown(self)
 login=base.SelfProfileBrowserTests.login
 def nav(self,key,lang='it'):
  if key in ('countries','cities'):
   self.page.locator('nav').get_by_role('button',name=M[lang]['resources']['settings'],exact=True).click()
   self.page.locator('.workspace').get_by_role('button',name=M[lang]['resources'][key],exact=True).click()
  else:self.page.locator('nav').get_by_role('button',name=M[lang]['resources'][key],exact=True).click()
  expect(self.page.get_by_role('heading',name=M[lang]['resources'][key],exact=True)).to_be_visible()
 def editor(self,lang='it'):
  self.page.locator('.page-heading').get_by_role('button',name=M[lang]['app']['new'],exact=True).click();return self.page.get_by_role('dialog')
 def site_actor(self,codes=None):
  self.actor,self.user,_,self.credentials=self.case.actor(codes or ['sites.read','sites.create','sites.update','companies.read'])
 def test_settings_tiles_round_trip_without_tenant_and_without_settings_data_grants(self):
  requests=[];self.page.on('request',lambda r:requests.append(urlsplit(r.url).path))
  self.login();self.page.locator('nav').get_by_role('button',name='Impostazioni',exact=True).click()
  for name in ('Nazioni','Città'):
   expect(self.page.locator('nav').get_by_role('button',name=name,exact=True)).to_have_count(0)
   self.page.locator('.workspace').get_by_role('button',name=name,exact=True).click();expect(self.page.get_by_role('heading',name=name,exact=True)).to_be_visible()
   self.page.get_by_role('button',name='Torna alle impostazioni',exact=True).click();expect(self.page.locator('.workspace').get_by_role('button',name=name,exact=True)).to_be_visible()
  expect(self.page.locator('.workspace').get_by_role('button',name='Integrazioni',exact=True)).to_have_count(0)
  self.assertFalse(any(path=='/api/data/settings' for path in requests))

 def test_global_city_catalog_crud_without_tenant_and_cancel(self):
  self.login(global_user=True);self.nav('cities');data=self.page.evaluate("fetch('/api/data/cities?pageSize=25').then(r=>r.json())");self.assertEqual(data['total'],8458);self.assertEqual(len(data['items']),25)
  self.page.locator('.search-box input').fill('Alghero');expect(self.page.locator('tbody')).to_contain_text('07041');expect(self.page.locator('tbody')).to_contain_text('SS');expect(self.page.locator('tbody')).to_contain_text('Sardegna')
  d=self.editor();d.locator('#field-name').fill('Località QA Browser');d.locator('#field-postal_code').fill('01010');d.locator('#field-province').fill('VT');d.locator('#field-region').fill('Lazio');d.locator('#field-country_id').click();self.page.get_by_role('option',name='Italia',exact=True).click();d.locator('#field-notes').fill('Manutenzione manuale')
  with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/data/cities/save' and r.request.method=='POST') as response:d.get_by_role('button',name='Salva',exact=True).click()
  self.assertEqual(response.value.status,201);city=response.value.json();expect(d).not_to_be_visible()
  try:
   self.page.locator('.search-box input').fill('Località QA Browser');row=self.page.locator('tbody tr').filter(has_text='Località QA Browser');expect(row).to_be_visible();row.get_by_role('button',name=re.compile(r'^Modifica(?:\s|$)')).click();d=self.page.get_by_role('dialog');d.locator('#field-name').fill('Non salvare');d.get_by_role('button',name='Annulla',exact=True).click();expect(d).not_to_be_visible();self.assertEqual(self.root.request('/api/data/cities?'+urlencode({'search':'Località QA Browser'}))[1]['items'][0]['name'],'Località QA Browser')
   row.get_by_role('button',name=re.compile(r'^Modifica(?:\s|$)')).click();d=self.page.get_by_role('dialog');d.locator('#field-notes').fill('Nota aggiornata')
   with self.page.expect_response(lambda r:r.request.method=='PUT' and r.url.endswith('/save')) as response:d.get_by_role('button',name='Salva',exact=True).click()
   self.assertEqual(response.value.status,200);expect(d).not_to_be_visible();self.assertEqual(self.root.request('/api/data/cities?'+urlencode({'search':'Località QA Browser'}))[1]['items'][0]['notes'],'Nota aggiornata')
  finally:self.root.request('/api/data/cities/'+city['id'],'DELETE')
 def test_ordinary_reader_catalog_is_read_only(self):
  self.login();self.nav('countries');expect(self.page.locator('tbody')).to_contain_text('Italia');expect(self.page.locator('.page-heading').get_by_role('button',name='Nuovo',exact=True)).to_have_count(0)
  self.nav('cities');self.page.locator('.search-box input').fill('Alghero');expect(self.page.locator('tbody')).to_contain_text('07041');expect(self.page.locator('tbody').get_by_role('button',name=re.compile(r'^Modifica(?:\s|$)'))).to_have_count(0);expect(self.page.locator('tbody').get_by_role('button',name=re.compile(r'^Elimina(?:\s|$)'))).to_have_count(0);self.assertEqual(self.business,[])
 def test_local_catalog_completes_city_cap_province_region_and_keeps_manual_street(self):
  self.site_actor();company=self.case.create('companies',{'name':'Azienda geografia '+self.case.tenant['id'][:8]});self.login();self.nav('sites');d=self.editor();d.locator('#field-company_id').click();self.page.get_by_role('option',name=company['name'],exact=True).click();d.locator('#field-name').fill('Sede con catalogo locale');d.locator('#field-address').fill('Via manuale 17')
  country=d.locator('#field-country_code');expect(country).to_be_enabled();country.click();expect(self.page.get_by_role('option')).to_have_count(249);self.page.get_by_role('option',name='Italia',exact=True).click();d.locator('#field-city').fill('Alghero');expect(self.page.get_by_role('option',name=re.compile('Alghero.*07041.*SS'))).to_be_visible();expect(d.get_by_text('Powered by',exact=False)).to_have_count(0);d.locator('#field-city').press('ArrowDown');d.locator('#field-city').press('Enter')
  for key,value in [('city','Alghero'),('postal_code','07041'),('province','SS'),('region','Sardegna'),('address','Via manuale 17')]:expect(d.locator('#field-'+key)).to_have_value(value)
  self.assertEqual(self.business,[])
  d.locator('#field-city').fill('Capua');self.page.get_by_role('option',name=re.compile(r'^Capua.*81043.*CE')).click()
  for key,value in [('city','Capua'),('postal_code','81043'),('province','CE'),('region','Campania'),('address','Via manuale 17')]:expect(d.locator('#field-'+key)).to_have_value(value)
  with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/data/sites/save' and r.request.method=='POST') as response:d.get_by_role('button',name='Salva',exact=True).click()
  self.assertEqual(response.value.status,201);saved=response.value.json();self.assertEqual((saved['postal_code'],saved['province'],saved['region'],saved['address'],saved['country_code']),('81043','CE','Campania','Via manuale 17','IT'));self.assertEqual(self.business,[('POST','/api/data/sites/save')]);expect(d).not_to_be_visible()
 def test_no_external_integration_in_settings_or_address_editor(self):
  self.site_actor();self.login();self.page.locator('nav').get_by_role('button',name='Impostazioni',exact=True).click();expect(self.page.get_by_role('button',name='Integrazioni',exact=True)).to_have_count(0)
  self.nav('sites');d=self.editor();country=d.locator('#field-country_code');expect(country).to_be_enabled();country.click();expect(self.page.get_by_role('option')).to_have_count(249);self.page.get_by_role('option',name='Italia',exact=True).click();expect(country).to_contain_text('Italia');expect(d.locator('a[href*="geoapify"],a[href*="openstreetmap"]')).to_have_count(0);d.get_by_role('button',name='Annulla',exact=True).click();self.assertEqual(self.business,[])
 def test_english_mobile_global_catalog(self):
  self.page.set_viewport_size({'width':390,'height':844});sql(f"UPDATE foundation.\"user\" SET preferred_language='en' WHERE id='{self.root_id}';");self.login(global_user=True);expect(self.page.locator('html')).to_have_attribute('lang','en');self.page.locator('[data-slot=sidebar-trigger]').click();self.nav('countries','en');expect(self.page.locator('tbody')).to_contain_text('IT');self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
if __name__=='__main__':unittest.main(verbosity=2)
