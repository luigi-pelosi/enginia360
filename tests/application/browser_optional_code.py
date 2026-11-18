"""Ordine e obbligatorietà nei form reali, guidati dai metadati del backend."""
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from test_optional_code import BUSINESS, references
import browser_unified_save as harness
from playwright.sync_api import expect

EVIDENCE=Path('/root/.hermes/cache/scratch/enginia360-optional-code/browser')
EVIDENCE.mkdir(parents=True,exist_ok=True)
harness.EVIDENCE=EVIDENCE
IT=json.loads(Path('frontend/messages/it.json').read_text())
EN=json.loads(Path('frontend/messages/en.json').read_text())
Base=harness.UnifiedSaveBrowserTests


class OptionalCodeBrowserTests(unittest.TestCase):
    setUpClass=classmethod(Base.setUpClass.__func__)
    tearDownClass=classmethod(Base.tearDownClass.__func__)
    setUp=Base.setUp
    tearDown=Base.tearDown
    login=Base.login

    def new_form(self,key,messages=IT):
        self.page.locator('nav').get_by_role('button',name=messages['resources'][key],exact=True).click()
        self.page.get_by_role('button',name=messages['app']['new'],exact=True).first.click()
        dialog=self.page.get_by_role('dialog')
        expect(dialog.locator('#field-code')).to_be_visible()
        return dialog

    def assert_secondary_code(self,dialog,required=False):
        self.assertEqual(dialog.locator('#field-code').get_attribute('required') is not None,required,
                         'Il codice anagrafico deve essere facoltativo')
        order=dialog.evaluate('(dialog)=>[...dialog.querySelectorAll("[id^=field-]")].map(node=>node.id)')
        self.assertLess(order.index('field-name'),order.index('field-code'),'Nome deve precedere Codice')
        if not required:self.assertNotIn('*',dialog.locator('label[for=field-code]').inner_text())

    def fill_references(self,dialog,key,rows):
        fields={'sites':[('company_id','companies')],
                'warehouses':[('site_id','sites'),('warehouse_type_id','warehouse-types')],
                'warehouse-locations':[('warehouse_id','warehouses')]}.get(key,[])
        for field,target in fields:
            expect(dialog.locator('#field-'+field)).to_be_enabled()
            dialog.locator('#field-'+field).click()
            self.page.get_by_role('option',name=rows[target]['name'],exact=True).click()

    def create_without_code(self,key,rows,messages=IT):
        dialog=self.new_form(key,messages)
        self.assert_secondary_code(dialog)
        self.fill_references(dialog,key,rows)
        dialog.locator('#field-name').fill('Nuovo senza codice '+key)
        with self.page.expect_response(lambda response:urlsplit(response.url).path=='/api/data/'+key+'/save' and response.request.method=='POST') as saved:
            dialog.get_by_role('button',name=messages['app']['save'],exact=True).click()
        self.assertEqual(saved.value.status,201)
        row=saved.value.json();self.assertIsNone(row['code'])
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        return row

    def test_warehouse_code_optional_and_name_before_code(self):
        rows=references(self.case)
        self.login()
        self.create_without_code('warehouses',rows)
        self.assertEqual(len(self.mutations),1)

    def test_all_business_forms_save_without_code(self):
        rows=references(self.case)
        self.login()
        for key in BUSINESS:
            with self.subTest(resource=key):self.create_without_code(key,rows)
        self.assertEqual(len(self.mutations),len(BUSINESS))
        self.assertTrue(all(m['body']['values'].get('code') is None for m in self.mutations))

    def test_organization_code_required_after_name(self):
        self.login()
        dialog=self.new_form('tenants')
        self.assert_secondary_code(dialog,required=True)
        dialog.locator('#field-name').fill('Organizzazione senza codice')
        self.assertFalse(dialog.locator('form').evaluate('(form)=>form.checkValidity()'))
        dialog.get_by_role('button',name='Annulla',exact=True).click()
        self.assertEqual(self.mutations,[])

    def test_mobile_english_warehouse_form(self):
        rows=references(self.case)
        self.login()
        self.page.get_by_role('combobox',name='Lingua',exact=True).click()
        self.page.get_by_role('option',name='English',exact=True).click()
        expect(self.page.locator('html')).to_have_attribute('lang','en')
        self.page.locator('#tenant-select').click()
        self.page.get_by_role('option',name=self.case.tenant['name'],exact=True).click()
        dialog=self.new_form('warehouses',EN)
        self.page.set_viewport_size({'width':390,'height':844})
        self.assert_secondary_code(dialog)
        expect(dialog.locator('label[for=field-code]')).to_have_text('Code')
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.fill_references(dialog,'warehouses',rows)
        dialog.locator('#field-name').fill('Warehouse without code')
        dialog.get_by_role('button',name=EN['app']['save'],exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations),1)


if __name__=='__main__':unittest.main(defaultTest='OptionalCodeBrowserTests',verbosity=2)
