"""Browser autenticato: sedi e autocomplete dal catalogo locale isolato."""
from pathlib import Path
import unittest
from urllib.parse import urlsplit
import browser_unified_save as harness
from unified_save_support import sql
from playwright.sync_api import expect

EVIDENCE=Path('/root/.hermes/cache/scratch/enginia360-site-addresses/browser')
EVIDENCE.mkdir(parents=True,exist_ok=True)
harness.EVIDENCE=EVIDENCE


class SiteAddressesBrowserTests(unittest.TestCase):
    setUpClass=classmethod(harness.UnifiedSaveBrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(harness.UnifiedSaveBrowserTests.tearDownClass.__func__)
    tearDown=harness.UnifiedSaveBrowserTests.tearDown
    def login(self,credentials=None,tenant_code=''):
        credentials=credentials or self.credentials
        self.page.goto(harness.ORIGIN,wait_until='networkidle')
        self.page.locator('#username').fill(credentials['username']);self.page.locator('#password').fill(credentials['password'])
        if tenant_code:self.page.locator('#tenant-code').fill(tenant_code)
        self.page.get_by_role('button',name='Accedi',exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        if not tenant_code:
            self.page.locator('#tenant-select').click();self.page.get_by_role('option',name=self.case.tenant['name'],exact=True).click()

    def setUp(self):
        harness.UnifiedSaveBrowserTests.setUp(self)
        self.case.tenant['name']='Indirizzi '+self.case.tenant['id'][:8]
        self.assertEqual(self.root.request('/api/data/tenants/'+self.case.tenant['id'],'PUT',{'name':self.case.tenant['name']})[0],200)
        self.company=self.case.create('companies',{'name':'Area Service'})

    def new_site(self):
        self.page.locator('nav').get_by_role('button',name='Sedi',exact=True).click()
        self.page.get_by_role('button',name='Nuovo',exact=True).first.click()
        dialog=self.page.get_by_role('dialog')
        dialog.locator('#field-company_id').click()
        self.page.get_by_role('option',name=self.company['name'],exact=True).click()
        dialog.locator('#field-name').fill('Officina Capua')
        return dialog

    def complete_manual_address(self,dialog,country=True):
        for field,value in [('address','Via QA 1'),('city','Capua'),('province','CE'),('postal_code','81043')]:
            if not dialog.locator('#field-'+field).input_value():dialog.locator('#field-'+field).fill(value)
        if country and 'Italia' not in dialog.locator('#field-country_code').inner_text():
            dialog.locator('#field-country_code').click();self.page.get_by_role('option',name='Italia',exact=True).click()

    def test_code_order_alternative_fiscal_requirement_and_catalog_country_dropdown(self):
        self.login();dialog=self.new_site()
        self.assertTrue(dialog.locator('#field-name').evaluate('(el)=>el.closest(".field").nextElementSibling.contains(document.getElementById("field-code"))'))
        expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
        dialog.locator('#field-tax_code').fill('CF-TEST')
        expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
        self.complete_manual_address(dialog,country=False)
        dialog.locator('#field-country_code').click()
        expect(self.page.get_by_role('option')).to_have_count(1)
        self.page.get_by_role('option',name='Italia',exact=True).click()
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/data/sites/save' and r.request.method=='POST') as saved:
            dialog.get_by_role('button',name='Salva',exact=True).click()
        self.assertEqual(saved.value.status,201);row=saved.value.json()
        self.assertEqual(row['country_code'],'IT');self.assertIsNone(row['vat_number']);self.assertEqual(row['tax_code'],'CF-TEST');self.assertIsNone(row['code'])
        self.assertEqual(len(self.mutations),1)

    def test_local_city_autocomplete_fills_geography_and_saves_one_draft(self):
        self.login();dialog=self.new_site()
        dialog.locator('#field-vat_number').fill('VAT-TEST')
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/addresses/autocomplete' and 'field=city' in r.url) as found:
            dialog.locator('#field-city').fill('Capua')
        self.assertEqual(found.value.status,200)
        self.assertEqual(found.value.json()['attribution'],'')
        items=found.value.json()['items'];choice=next(item for item in items if item['city']=='Capua' and item['countryCode']=='IT')
        dialog.get_by_role('option',name=choice['label'],exact=True).click()
        expect(dialog.locator('#field-city')).to_have_value('Capua')
        expect(dialog.locator('#field-province')).to_have_value('CE')
        expect(dialog.locator('#field-country_code')).to_contain_text('Italia')
        expect(dialog.locator('#field-postal_code')).to_have_value('81043')
        expect(dialog.locator('#field-region')).to_have_value('Campania')
        expect(dialog.locator('#field-address')).to_have_value('')
        self.assertEqual(self.mutations,[])
        expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
        self.complete_manual_address(dialog)
        self.page.screenshot(path=str(EVIDENCE/'site-city-autofill.png'),full_page=True)
        with self.page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path=='/api/data/sites/save') as saved:
            dialog.get_by_role('button',name='Salva',exact=True).click()
        self.assertEqual(saved.value.status,201);row=saved.value.json();self.assertEqual(row['country_code'],'IT');self.assertEqual(row['province'],'CE');self.assertEqual(row['postal_code'],'81043');self.assertEqual(row['region'],'Campania')
        expect(self.page.get_by_role('dialog')).to_have_count(0);self.assertEqual(len(self.mutations),1)

    def test_autocomplete_selection_cancel_never_writes_and_failure_allows_manual_entry(self):
        self.login();dialog=self.new_site()
        dialog.locator('#field-tax_code').fill('CF-TEST')
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/addresses/autocomplete') as found:dialog.locator('#field-city').fill('Capua')
        choice=next(item for item in found.value.json()['items'] if item['countryCode']=='IT')
        dialog.get_by_role('option',name=choice['label'],exact=True).click()
        dialog.get_by_role('button',name='Annulla',exact=True).click();self.assertEqual(self.mutations,[])
        self.assertEqual(sql(f"SELECT count(*) FROM foundation.site WHERE tenant_id='{self.case.tenant['id']}'").stdout.strip(),'0')
        # Guasto HTTP simulato del solo endpoint locale, senza configurazioni esterne.
        self.page.route('**/api/addresses/autocomplete?*',lambda route:route.fulfill(status=503,content_type='application/json',body='{"code":"unavailable"}'))
        dialog=self.new_site();dialog.locator('#field-tax_code').fill('CF-TEST')
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/addresses/autocomplete') as failed:dialog.locator('#field-city').fill('Capua')
        self.assertEqual(failed.value.status,503)
        self.complete_manual_address(dialog)
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/addresses/autocomplete'):
            dialog.locator('#field-city').focus()
        expect(dialog.locator('#field-city-error')).to_be_visible()
        before=dialog.get_by_role('button',name='Salva',exact=True).bounding_box()
        dialog.locator('#field-tax_code').focus()
        expect(dialog.locator('#field-city-error')).not_to_be_visible()
        after=dialog.get_by_role('button',name='Salva',exact=True).bounding_box()
        self.assertLess(abs(before['y']-after['y']),1,'Il feedback della ricerca non deve spostare Salva durante il click')
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/addresses/autocomplete'):
            dialog.locator('#field-city').focus()
        expect(dialog.locator('#field-city-error')).to_be_visible()
        expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_enabled()
        dialog.get_by_role('button',name='Salva',exact=True).click();expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations),1)

    def test_mobile_english_ui_catalog_country_and_manual_fields(self):
        self.login();self.context.add_cookies([{'name':'locale','value':'en','url':harness.ORIGIN}]);self.page.reload(wait_until='networkidle')
        self.page.locator('#tenant-select').click();self.page.get_by_role('option',name=self.case.tenant['name'],exact=True).click()
        self.page.locator('nav').get_by_role('button',name='Sites',exact=True).click();self.page.get_by_role('button',name='New',exact=True).click()
        dialog=self.page.get_by_role('dialog');self.page.set_viewport_size({'width':390,'height':844})
        dialog.locator('#field-country_code').click();self.page.get_by_role('option',name='Italia',exact=True).click()
        expect(dialog.locator('#field-country_code')).to_contain_text('Italia')
        self.assertTrue(dialog.evaluate('(el)=>el.scrollWidth<=el.clientWidth'));self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.screenshot(path=str(EVIDENCE/'site-country-mobile-en.png'),full_page=True)


if __name__=='__main__':unittest.main(verbosity=2)
