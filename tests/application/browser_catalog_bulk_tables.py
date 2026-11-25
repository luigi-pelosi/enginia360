"""Tabelle del selettore massivo, pagine e selezioni nel browser reale."""
from urllib.parse import urlsplit
from browser_catalog_companies import CatalogCompaniesBrowser
from catalog_items_helpers import fixture
BROWSER_CASES=('test_companies_table_address_page_selection_and_recovery','test_item_table_search_pages_select_all_and_single_bulk_save','test_bulk_dialog_mobile_geometry')
class CatalogBulkTablesBrowser(CatalogCompaniesBrowser):
    def open_bulk(self,locale='it'):
        from playwright.sync_api import expect
        self.login(locale);self.navigate_company_catalog();self.page.locator('#catalog-company-bulk').click();expect(self.bulk_dialog()).to_be_visible()
    def bulk_dialog(self):return self.page.get_by_test_id('catalog-company-bulk-editor')
    def test_companies_table_address_page_selection_and_recovery(self):
        from playwright.sync_api import expect
        branches=[self.case.data_create('companies',{'name':f'Branch {i:02}','is_enabled':True}) for i in range(26)]
        self.case.data_create('sites',{'company_id':branches[0]['id'],'name':'Legale','site_type':'LEGAL','address':'Via Riga 1','city':'Roma','province':'RM','postal_code':'00100','country_code':'IT','tax_code':'SYNTHETIC','is_enabled':True})
        self.open_bulk();dialog=self.bulk_dialog();table=dialog.locator('fieldset').nth(0).locator('table');expect(table.locator('tbody tr')).to_have_count(25)
        self.assertEqual([s.strip() for s in table.locator('thead th').all_text_contents()],['',self.messages['catalogCompanies']['company'],self.messages['catalogCompanies']['legalAddress']])
        row=self.page.locator('#catalog-bulk-company-'+branches[0]['id']).locator('xpath=ancestor::tr');expect(row.locator('td').nth(2)).to_contain_text('Via Riga 1')
        blank=self.page.locator('#catalog-bulk-company-'+branches[1]['id']).locator('xpath=ancestor::tr');expect(blank.locator('td').nth(2)).to_have_text('')
        width=dialog.bounding_box()['width'];self.assertGreaterEqual(width,850)
        header=self.page.locator('#catalog-bulk-company-all');expect(header).to_have_attribute('aria-checked','mixed');header.click();expect(header).to_have_attribute('aria-checked','true')
        self.page.locator('#catalog-bulk-company-next').click();expect(table.locator('tbody tr')).to_have_count(3);expect(header).to_have_attribute('aria-checked','false')
        self.toggle('catalog-bulk-company-'+self.a['id'],True);expect(header).to_have_attribute('aria-checked','mixed');header.click();expect(header).to_have_attribute('aria-checked','true')
        self.page.locator('#catalog-bulk-company-previous').click();expect(table.locator('tbody tr')).to_have_count(25);expect(header).to_have_attribute('aria-checked','true');header.click();expect(header).to_have_attribute('aria-checked','false')
        self.page.locator('#catalog-bulk-company-next').click();expect(header).to_have_attribute('aria-checked','true');self.page.reload(wait_until='networkidle');expect(self.bulk_dialog()).to_be_visible();expect(header).to_have_attribute('aria-checked','true');expect(self.page.locator('#catalog-bulk-company-'+self.a['id'])).to_have_attribute('aria-checked','true')
        self.page.screenshot(path=str(fixture.EVIDENCE/'bulk-tables-companies.png'),full_page=True);self.page.locator('#catalog-bulk-cancel').click();self.assertEqual(self.company_writes,[])
    def test_item_table_search_pages_select_all_and_single_bulk_save(self):
        from playwright.sync_api import expect
        items=[self.case.item(name=f'Bulk item {i:02}') for i in range(26)];self.open_bulk('en');dialog=self.bulk_dialog();table=dialog.locator('fieldset').nth(1).locator('table');expect(table.locator('tbody tr')).to_have_count(25)
        labels=self.messages['catalogItems'];fallback=self.messages['catalog']
        self.assertEqual([s.strip() for s in table.locator('thead th').all_text_contents()],['',*[labels.get(key,fallback.get(key,key)) if key!='base_uom_id' else labels['baseUnitList'] for key in ('code','name','item_type_id','category_id','base_uom_id','brand_id','status')]])
        header=self.page.locator('#catalog-bulk-item-all');header.click();expect(header).to_have_attribute('aria-checked','true');header.click();expect(header).to_have_attribute('aria-checked','false')
        self.toggle('catalog-bulk-item-'+items[0]['id'],True);self.page.locator('#catalog-bulk-next').click();expect(table.locator('tbody tr')).to_have_count(1);self.toggle('catalog-bulk-item-'+items[-1]['id'],True)
        self.page.locator('#catalog-bulk-search').fill(items[0]['name']);expect(table.locator('tbody tr')).to_have_count(1);expect(header).to_have_attribute('aria-checked','true');header.click();expect(header).to_have_attribute('aria-checked','false')
        self.page.reload(wait_until='networkidle');expect(self.bulk_dialog()).to_be_visible();expect(self.page.locator('#catalog-bulk-search')).to_have_value(items[0]['name']);expect(header).to_have_attribute('aria-checked','false')
        with self.page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path=='/api/catalog/item-companies/bulk-enable') as saved:self.page.locator('#catalog-bulk-save').click()
        self.assertEqual(saved.value.status,200,saved.value.text());self.assertEqual(saved.value.request.post_data_json,{'itemIds':[items[-1]['id']],'companyIds':[self.a['id']]});expect(self.bulk_dialog()).to_have_count(0)
        self.api_case.read_config(self.a,items[-1]);self.api_case.read_config(self.a,items[0],expected=404);self.assertEqual(len(self.company_writes),1)
    def test_bulk_dialog_mobile_geometry(self):
        from playwright.sync_api import expect
        self.case.item();self.open_bulk();self.page.set_viewport_size({'width':390,'height':844});dialog=self.bulk_dialog()
        dialog.evaluate('async e=>{await Promise.all(e.getAnimations({subtree:true}).filter(a=>a.effect?.getTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})));}')
        dialog.locator('[data-slot="dialog-footer"]').scroll_into_view_if_needed()
        self.page.wait_for_function('''()=>{const d=document.querySelector('[data-testid="catalog-company-bulk-editor"]').getBoundingClientRect();return ['catalog-bulk-save','catalog-bulk-cancel'].every(id=>{const b=document.getElementById(id).getBoundingClientRect();return b.top>=d.top&&b.bottom<=d.bottom;});}''')
        expect(self.page.locator('#catalog-bulk-save')).to_be_visible();expect(self.page.locator('#catalog-bulk-cancel')).to_be_visible();b=dialog.bounding_box();self.assertGreaterEqual(b['x'],0);self.assertLessEqual(b['x']+b['width'],390)
        self.page.screenshot(path=str(fixture.EVIDENCE/'bulk-tables-mobile.png'),full_page=True);self.page.locator('#catalog-bulk-cancel').click();self.assertEqual(self.company_writes,[])
