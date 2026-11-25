"""Chromium reale eliminazione tipologie: controlli, avviso e conferma IT/EN."""
import re
from urllib.parse import urlsplit
from browser_catalog_item_states import CatalogItemStateBrowser,control

BROWSER_CASES=('test_linked_type_warning_has_no_delete_request','test_unused_type_confirmation_cancel_then_delete','test_relation_added_after_preflight_is_blocked','test_refresh_rechecks_existing_relation')

class CatalogTypeDeletionBrowser(CatalogItemStateBrowser):
    def type(self,name):return self.case.create('types',{'name':name,'kind':'GOOD','is_active':True,'default_sellable':True,'default_purchasable':True,'default_track_stock':False})
    def types_page(self,locale='it'):
        from playwright.sync_api import expect
        self.login(locale)
        self.page.locator('nav').get_by_role('button',name=self.messages['resources']['settings'],exact=True).click()
        self.page.locator('#main').get_by_role('button',name=self.app('masterData'),exact=True).click()
        self.page.locator('#main').get_by_role('button',name=self.messages['resources']['settings-catalog'],exact=True).click()
        self.page.get_by_role('button',name=self.messages['resources']['catalog-types'],exact=True).click()
        expect(control(self.page,'catalog-table')).to_be_visible()
    def click_delete(self,row):
        from playwright.sync_api import expect
        control(self.page,'catalog-search').fill(row['name'])
        tr=control(self.page,'catalog-table').locator('tr[data-record-id="'+row['id']+'"]');expect(tr).to_have_count(1)
        tr.get_by_role('button',name=re.compile('^'+re.escape(self.app('delete'))+r'\s')).click()

    def test_linked_type_warning_has_no_delete_request(self):
        from playwright.sync_api import expect
        row=self.type('Linked type browser');item=self.case.item(item_type_id=row['id'])
        row={**row,'canChangeKind':False}
        self.types_page();before=len(self.mutations);self.click_delete(row)
        blocked=self.page.get_by_test_id('catalog-type-delete-blocked');expect(blocked).to_be_visible()
        expect(blocked).to_contain_text(self.messages['catalog']['item_type_in_use'])
        expect(self.page.locator('#catalog-delete-confirm')).to_have_count(0)
        self.assertEqual(len(self.mutations),before)
        control(blocked,'catalog-type-delete-close').click();expect(blocked).to_have_count(0)
        self.assertEqual(self.case.req('types',row['id']),row);self.case.full(item)

    def test_unused_type_confirmation_cancel_then_delete(self):
        from playwright.sync_api import expect
        row=self.type('Unused type browser');self.types_page('en');before=len(self.mutations);self.click_delete(row)
        confirm=self.page.locator('#catalog-delete-confirm');expect(confirm).to_be_visible()
        self.assertEqual(len(self.mutations),before)
        control(self.page,'catalog-delete-cancel').click();expect(confirm).to_have_count(0)
        self.assertEqual(self.case.req('types',row['id']),row)
        self.click_delete(row);expect(confirm).to_be_visible()
        with self.page.expect_response(lambda response:response.request.method=='DELETE' and urlsplit(response.url).path=='/api/catalog/types/'+row['id']) as saved:confirm.click()
        self.assertEqual(saved.value.status,204)
        expect(confirm).to_have_count(0);expect(control(self.page,'catalog-table').locator('tr[data-record-id="'+row['id']+'"]')).to_have_count(0)
        self.assertEqual(len(self.mutations),before+1);self.case.req('types',row['id'],expected=404)

    def test_relation_added_after_preflight_is_blocked(self):
        from playwright.sync_api import expect
        row=self.type('Race linked browser');self.types_page();before=len(self.mutations);self.click_delete(row)
        confirm=self.page.locator('#catalog-delete-confirm');expect(confirm).to_be_visible()
        item=self.case.item(item_type_id=row['id'])
        with self.page.expect_response(lambda response:response.request.method=='DELETE' and urlsplit(response.url).path=='/api/catalog/types/'+row['id']) as saved:confirm.click()
        self.assertEqual(saved.value.status,409)
        blocked=self.page.get_by_test_id('catalog-type-delete-blocked');expect(blocked).to_be_visible()
        expect(self.page.locator('#catalog-delete-confirm')).to_have_count(0)
        self.assertEqual(len(self.mutations),before+1);self.assertEqual(self.case.req('types',row['id']),{**row,'canChangeKind':False});self.case.full(item)

    def test_refresh_rechecks_existing_relation(self):
        from playwright.sync_api import expect
        row=self.type('Refresh linked browser');self.types_page();self.click_delete(row)
        expect(self.page.locator('#catalog-delete-confirm')).to_be_visible()
        item=self.case.item(item_type_id=row['id']);before=len(self.mutations)
        self.page.reload(wait_until='domcontentloaded')
        expect(self.page.get_by_test_id('catalog-type-delete-blocked')).to_be_visible()
        expect(self.page.locator('#catalog-delete-confirm')).to_have_count(0)
        self.assertEqual(len(self.mutations),before);self.assertEqual(self.case.req('types',row['id']),{**row,'canChangeKind':False});self.case.full(item)
