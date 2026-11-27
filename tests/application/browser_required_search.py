"""Sedi obbligatorie e live search condivisa: browser autenticato nella copia isolata."""
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
import browser_unified_save as harness
from unified_save_support import sql
from playwright.sync_api import expect

EVIDENCE=Path('/root/.hermes/cache/scratch/enginia360-required-search/browser')
EVIDENCE.mkdir(parents=True,exist_ok=True);harness.EVIDENCE=EVIDENCE


class RequiredSearchBrowserTests(unittest.TestCase):
    setUpClass=classmethod(harness.UnifiedSaveBrowserTests.setUpClass.__func__)
    tearDownClass=classmethod(harness.UnifiedSaveBrowserTests.tearDownClass.__func__)
    tearDown=harness.UnifiedSaveBrowserTests.tearDown

    def setUp(self):
        harness.UnifiedSaveBrowserTests.setUp(self)
        self.case.tenant['name']='Ricerca '+self.case.tenant['id'][:8]
        self.assertEqual(self.root.request('/api/data/tenants/'+self.case.tenant['id'],'PUT',{'name':self.case.tenant['name']})[0],200)
        self.company=self.case.create('companies',{'name':'Officina Ricerca'})

    def login(self,credentials=None,tenant_code=''):
        credentials=credentials or self.credentials
        self.page.goto(harness.ORIGIN,wait_until='networkidle')
        self.page.locator('#username').fill(credentials['username']);self.page.locator('#password').fill(credentials['password'])
        if tenant_code:self.page.locator('#tenant-code').fill(tenant_code)
        self.page.get_by_role('button',name='Accedi',exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        if not tenant_code:
            self.page.locator('#tenant-select').click();self.page.get_by_role('option',name=self.case.tenant['name'],exact=True).click()

    def search(self,text):
        field=self.page.locator('[data-slot=select-search]');expect(field).to_be_visible();field.fill(text);return field

    def choose(self,trigger,text,label):
        trigger.click();self.search(text);self.page.get_by_role('option',name=label,exact=True).click()

    def new_site(self):
        self.page.locator('nav').get_by_role('button',name='Sedi',exact=True).click()
        self.page.get_by_role('button',name='Nuovo',exact=True).first.click()
        dialog=self.page.get_by_role('dialog')
        dialog.locator('#field-company_id').click();self.page.get_by_role('option',name=self.company['name'],exact=True).click()
        dialog.locator('#field-name').fill('Sede ricercabile')
        return dialog

    def fill_address(self,dialog):
        for key,text in [('address','Via QA 1'),('city','Città QA'),('province','Provincia QA'),('postal_code','00000')]:dialog.locator('#field-'+key).fill(text)

    def test_no_fiscal_help_all_geographic_fields_required_and_single_manual_save(self):
        self.login();dialog=self.new_site();save=dialog.get_by_role('button',name='Salva',exact=True)
        expect(dialog.locator('#tax-identity-requirement')).to_have_count(0)
        expect(dialog.get_by_text('Compila almeno uno tra Partita IVA e Codice fiscale.',exact=True)).to_have_count(0)
        for field in ('address','city','province','postal_code','country_code'):
            expect(dialog.locator('label[for=field-'+field+']')).to_contain_text('*')
        for field in ('vat_number','tax_code'):
            expect(dialog.locator('#field-'+field)).to_have_count(0)
        expect(save).to_be_disabled()
        self.fill_address(dialog);expect(save).to_be_disabled()
        dialog.locator('#field-country_code').click();expect(self.page.get_by_role('option')).to_have_count(1)
        self.search('ITAL');self.page.get_by_role('option',name='Italia',exact=True).click();expect(save).to_be_enabled()
        for field in ('address','city','province','postal_code'):
            input=dialog.locator('#field-'+field);old=input.input_value()
            self.assertIsNotNone(input.get_attribute('required'));input.fill('   ');expect(save).to_be_disabled();input.fill(old);expect(save).to_be_enabled()
        expect(save).to_be_enabled()
        self.assertEqual(self.mutations,[])
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/data/sites/save' and r.request.method=='POST') as saved:save.click()
        self.assertEqual(saved.value.status,201);row=saved.value.json();self.assertEqual(row['country_code'],'IT');self.assertTrue(all(row[f] for f in ('address','city','province','postal_code')))
        expect(self.page.get_by_role('dialog')).to_have_count(0);self.assertEqual(len(self.mutations),1)

    def test_country_live_filter_keyboard_empty_escape_and_selected_label_persistence(self):
        self.login();dialog=self.new_site();trigger=dialog.locator('#field-country_code')
        trigger.click();search=self.search('zzzz-not-a-country');expect(self.page.get_by_role('option')).to_have_count(0)
        expect(self.page.locator('[data-slot=select-empty]')).to_be_visible()
        search.press('Escape');expect(dialog).to_be_visible();expect(trigger).to_be_focused();expect(trigger).to_contain_text('—')
        trigger.click();expect(self.page.locator('[data-slot=select-search]')).to_have_value('');expect(self.page.get_by_role('option')).to_have_count(1)
        search=self.search('ITAL');expect(self.page.get_by_role('option')).to_have_count(1);search.press('ArrowDown');self.page.keyboard.press('Enter')
        expect(trigger).to_contain_text('Italia');expect(self.page.locator('[data-slot=select-search]')).to_have_count(0)
        trigger.click();self.search('Giappone');expect(self.page.get_by_role('option')).to_have_count(0);expect(self.page.locator('[data-slot=select-empty]')).to_be_visible();expect(trigger).to_contain_text('Italia')
        self.page.keyboard.press('Escape');expect(dialog).to_be_visible();expect(trigger).to_contain_text('Italia');expect(trigger).to_be_focused()
        trigger.click();expect(self.page.get_by_role('option')).to_have_count(1);self.page.keyboard.press('Escape')
        self.assertEqual(self.mutations,[]);dialog.get_by_role('button',name='Annulla',exact=True).click()
        self.assertEqual(sql(f"SELECT count(*) FROM foundation.site WHERE tenant_id='{self.case.tenant['id']}'").stdout.strip(),'0')

    def test_reference_accent_search_and_optional_enum_clear_preserve_local_draft(self):
        other=self.case.create('companies',{'name':'Azienda Città'})
        self.login();dialog=self.new_site();trigger=dialog.locator('#field-company_id')
        trigger.click();search=self.search('CITTA');expect(self.page.get_by_role('option')).to_have_count(1)
        expect(trigger).to_contain_text(self.company['name']);search.press('ArrowDown');self.page.keyboard.press('Enter');expect(trigger).to_contain_text(other['name'])
        legal=dialog.locator('#field-site_type');legal.click();self.search('unita');self.page.get_by_role('option',name='Unità locale',exact=True).click();expect(legal).to_contain_text('Unità locale')
        legal.click();self.page.get_by_role('option',name='—',exact=True).click();expect(legal).to_contain_text('—')
        self.assertEqual(self.mutations,[]);dialog.get_by_role('button',name='Annulla',exact=True).click();self.assertEqual(self.mutations,[])

    def test_tenant_and_language_controls_also_have_localized_live_search(self):
        self.login();tenant=self.page.locator('#tenant-select');tenant.click();self.search(self.case.tenant['id'][:8]);expect(self.page.get_by_role('option')).to_have_count(1)
        self.page.keyboard.press('Escape');expect(tenant).to_contain_text(self.case.tenant['name'])
        language=self.page.get_by_role('combobox',name='Lingua',exact=True);language.click();search=self.search('ENGL');expect(self.page.get_by_role('option')).to_have_count(1)
        search.press('ArrowDown');self.page.keyboard.press('Enter')
        expect(self.page.get_by_role('combobox',name='Language',exact=True)).to_contain_text('English')
        self.page.get_by_role('combobox',name='Language',exact=True).click();search=self.search('ital');self.assertRegex(search.get_attribute('placeholder') or '',r'^Search')
        self.page.keyboard.press('Escape');self.assertEqual(self.mutations,[])

    def test_purchasing_company_and_scope_search_keep_one_atomic_save(self):
        self.login();self.page.locator('nav').get_by_role('button',name='Organizzazioni di acquisto',exact=True).click()
        self.page.get_by_role('button',name='Nuovo',exact=True).first.click();dialog=self.page.get_by_role('dialog');dialog.locator('#field-name').fill('Acquisti ricerca')
        coverage=dialog.locator('[data-purchasing-coverage]');coverage.get_by_role('combobox').click();self.search('Officina');self.page.get_by_role('option',name=self.company['name'],exact=True).click()
        coverage.get_by_role('button',name='Aggiungi',exact=True).click();scope=dialog.locator('[data-coverage-mode]');scope.click();self.search('tutte');self.page.get_by_role('option',name='Tutte le sedi',exact=True).click()
        self.assertEqual(self.mutations,[])
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/data/purchasing-organizations/save' and r.request.method=='POST') as saved:dialog.get_by_role('button',name='Salva',exact=True).click()
        self.assertEqual(saved.value.status,201);self.assertEqual(len(self.mutations),1);expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(sql(f"SELECT site_scope FROM foundation.purchasing_organization_company WHERE purchasing_organization_id='{saved.value.json()['id']}'").stdout.strip(),'all_sites')

    def test_mobile_english_search_catalog_country_and_no_overflow(self):
        self.login();self.context.add_cookies([{'name':'locale','value':'en','url':harness.ORIGIN}]);self.page.reload(wait_until='networkidle')
        self.page.locator('#tenant-select').click();self.search(self.case.tenant['id'][:8]);self.page.get_by_role('option',name=self.case.tenant['name'],exact=True).click()
        self.page.locator('nav').get_by_role('button',name='Sites',exact=True).click();self.page.get_by_role('button',name='New',exact=True).first.click()
        dialog=self.page.get_by_role('dialog');self.page.set_viewport_size({'width':390,'height':844});trigger=dialog.locator('#field-country_code');trigger.click();search=self.search('ITAL')
        self.page.get_by_role('option',name='Italia',exact=True).click();expect(trigger).to_contain_text('Italia')
        self.assertTrue(dialog.evaluate('(el)=>el.scrollWidth<=el.clientWidth'));self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        trigger.click();self.search('zzzz');expect(self.page.locator('[data-slot=select-empty]')).to_have_text(json.loads(Path('/root/enginia360/frontend/messages/en.json').read_text())['app']['empty'])
        self.page.keyboard.press('Escape');expect(dialog).to_be_visible();self.page.screenshot(path=str(EVIDENCE/'mobile-search-en.png'),full_page=True)
        self.assertEqual(self.mutations,[])

    def test_local_city_autocomplete_fills_geography_but_requires_manual_address(self):
        self.login();dialog=self.new_site()
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/addresses/autocomplete' and 'field=city' in r.url) as found:dialog.locator('#field-city').fill('Alghero')
        self.assertEqual(found.value.status,200);self.assertEqual(found.value.json()['attribution'],'');item=next(i for i in found.value.json()['items'] if i['city']=='Alghero' and i['countryCode']=='IT')
        dialog.get_by_role('option',name=item['label'],exact=True).click();expect(dialog.locator('#field-country_code')).to_contain_text('Italia');expect(dialog.locator('#field-province')).to_have_value('SS')
        expect(dialog.locator('#field-postal_code')).to_have_value('07041');expect(dialog.locator('#field-region')).to_have_value('Sardegna')
        self.assertEqual(self.mutations,[])
        expect(dialog.locator('#field-address')).to_have_value('');expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
        dialog.locator('#field-address').fill('Via QA 1')
        dialog.locator('#field-postal_code').fill('');expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_disabled();dialog.locator('#field-postal_code').fill('07041')
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/data/sites/save' and r.request.method=='POST') as saved:dialog.get_by_role('button',name='Salva',exact=True).click()
        self.assertEqual(saved.value.status,201);row=saved.value.json();self.assertEqual((row['country_code'],row['city'],row['province'],row['postal_code'],row['region'],row['address']),('IT','Alghero','SS','07041','Sardegna','Via QA 1'));self.assertEqual(len(self.mutations),1)

    def test_integrated_palette_and_classification_list_labels_in_both_languages(self):
        self.case.create('sites',{'company_id':self.company['id'],'name':'Sede classificata','site_type':'LOCAL_UNIT','functions':['OPERATIONAL','WAREHOUSE']})
        self.login();self.page.locator('nav').get_by_role('button',name='Sedi',exact=True).click()
        row=self.page.locator('tbody tr').filter(has_text='Sede classificata')
        for label in ('Unità locale','Operativa','Magazzino'):expect(row).to_contain_text(label)
        text=row.inner_text();self.assertNotIn('LOCAL_UNIT',text);self.assertNotIn('OPERATIONAL',text)
        self.assertEqual(self.page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--primary").trim()'),'#0b1f43')
        self.context.add_cookies([{'name':'locale','value':'en','url':harness.ORIGIN}]);self.page.reload(wait_until='networkidle')
        self.page.locator('#tenant-select').click();self.search(self.case.tenant['id'][:8]);self.page.get_by_role('option',name=self.case.tenant['name'],exact=True).click()
        self.page.locator('nav').get_by_role('button',name='Sites',exact=True).click();row=self.page.locator('tbody tr').filter(has_text='Sede classificata')
        for label in ('Local unit','Operations','Warehouse'):expect(row).to_contain_text(label)
        self.assertNotIn('LOCAL_UNIT',row.inner_text());self.assertEqual(self.mutations,[])

    def test_readonly_site_selects_are_disabled_and_help_stays_absent(self):
        site=self.case.create('sites',{'company_id':self.company['id'],'name':'Sede readonly'})
        _,_,_,credentials=self.case.actor(['sites.read','companies.read'])
        self.login(credentials,self.case.tenant['code']);self.page.locator('nav').get_by_role('button',name='Sedi',exact=True).click()
        self.page.locator('tbody tr').filter(has_text=site['name']).get_by_role('button',name=re.compile('^(Dettagli|Modifica) ')).click()
        dialog=self.page.get_by_role('dialog');expect(dialog.locator('#field-country_code')).to_be_disabled();expect(dialog.locator('#field-company_id')).to_be_disabled()
        expect(dialog.locator('#tax-identity-requirement')).to_have_count(0);self.assertEqual(self.mutations,[])

if __name__=='__main__':unittest.main(verbosity=2)
