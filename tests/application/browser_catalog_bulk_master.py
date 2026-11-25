"""Parità dei dati articolo tra master e selettore massivo, senza azioni."""
from browser_catalog_bulk_tables import CatalogBulkTablesBrowser
from catalog_items_helpers import fixture
BROWSER_CASES=('test_italian_master_columns_and_values','test_english_master_columns_and_mobile_overflow')
class CatalogBulkMasterBrowser(CatalogBulkTablesBrowser):
    def parity(self,locale):
        from playwright.sync_api import expect
        brand=self.case.create('brands',{'name':'Brand proof','is_active':True});items=[self.case.item(name='With brand',brand_id=brand['id']),self.case.item(name='Without brand')]
        self.login(locale);self.navigate();master=self.page.locator('#catalog-item-table');expect(master.locator('tr[data-record-id]')).to_have_count(2)
        headers=[s.strip() for s in master.locator('thead th').all_text_contents()][:-1]
        values={item['id']:[cell.strip() for cell in master.locator('tr[data-record-id="'+item['id']+'"]').locator('td').all_text_contents()][:-1] for item in items}
        self.navigate_company_catalog();self.page.locator('#catalog-company-bulk').click();table=self.page.locator('#catalog-bulk-items-table');expect(table.locator('tbody tr')).to_have_count(2)
        self.assertEqual([s.strip() for s in table.locator('thead th').all_text_contents()][1:],headers);expect(table.locator('[data-kind="actions"]')).to_have_count(0)
        self.assertTrue(table.locator('thead th').last.evaluate('e=>e.getBoundingClientRect().right<=e.closest("[data-slot=table-container]").getBoundingClientRect().right+1'),'Le intestazioni devono entrare nel selettore desktop')
        for item in items:
            row=self.page.locator('#catalog-bulk-item-'+item['id']).locator('xpath=ancestor::tr');self.assertEqual([s.strip() for s in row.locator('td').all_text_contents()][1:],values[item['id']]);self.assertEqual(row.locator('td').last.evaluate('e=>getComputedStyle(e).textAlign'),'center')
        self.page.locator('#catalog-bulk-item-all').click();self.page.reload(wait_until='networkidle');expect(self.page.locator('#catalog-bulk-item-all')).to_have_attribute('aria-checked','true')
        self.assertEqual(self.company_writes,[]);return table
    def test_italian_master_columns_and_values(self):
        self.parity('it');self.page.screenshot(path=str(fixture.EVIDENCE/'bulk-master-italian.png'),full_page=True)
    def test_english_master_columns_and_mobile_overflow(self):
        from playwright.sync_api import expect
        table=self.parity('en');self.page.set_viewport_size({'width':390,'height':844});dialog=self.bulk_dialog();dialog.evaluate('async e=>{await Promise.all(e.getAnimations({subtree:true}).filter(a=>a.effect?.getTiming().iterations!==Infinity).map(a=>a.finished.catch(()=>{})));}')
        table.locator('thead th').last.scroll_into_view_if_needed();expect(table.locator('thead th').last).to_be_visible();b=dialog.bounding_box();self.assertGreaterEqual(b['x'],0);self.assertLessEqual(b['x']+b['width'],390)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=document.documentElement.clientWidth'))
        self.page.screenshot(path=str(fixture.EVIDENCE/'bulk-master-mobile.png'),full_page=True)
