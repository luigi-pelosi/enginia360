"""Chromium con API reale: modifica natura tipologie e protezione dei riferimenti."""
import re
from urllib.parse import urlsplit
from browser_catalog_type_deletion import CatalogTypeDeletionBrowser,control
BROWSER_CASES=('test_unused_type_changes_nature_and_survives_refresh','test_used_type_nature_is_locked_name_remains_editable','test_new_reference_refuses_unsaved_nature_change')

class CatalogTypeNatureBrowser(CatalogTypeDeletionBrowser):
    def open_type(self,row):
        from playwright.sync_api import expect
        control(self.page,'catalog-search').fill(row['name'])
        tr=control(self.page,'catalog-table').locator('tr[data-record-id="'+row['id']+'"]');expect(tr).to_have_count(1)
        tr.get_by_role('button',name=re.compile('^'+re.escape(self.app('edit'))+r'\s')).click()
        expect(control(self.page,'catalog-kind')).to_be_visible()
    def choose_kind(self,kind):
        control(self.page,'catalog-kind').click();self.page.get_by_role('option',name=self.messages['catalog'][kind],exact=True).click()
    def save_type(self,row,expected=200):
        with self.page.expect_response(lambda response:response.request.method=='PUT' and urlsplit(response.url).path=='/api/catalog/types/'+row['id']) as saved:control(self.page,'catalog-save').click()
        self.assertEqual(saved.value.status,expected);return saved.value.json()

    def test_unused_type_changes_nature_and_survives_refresh(self):
        from playwright.sync_api import expect
        row=self.type('Unused nature browser');self.types_page();self.open_type(row)
        expect(control(self.page,'catalog-kind')).to_be_enabled();self.choose_kind('CHARGE')
        self.page.reload(wait_until='networkidle')
        expect(control(self.page,'catalog-kind')).to_be_enabled();expect(control(self.page,'catalog-kind')).to_contain_text(self.messages['catalog']['CHARGE'])
        before=len(self.mutations);changed=self.save_type(row)
        self.assertEqual(changed['kind'],'CHARGE');self.assertTrue(changed['canChangeKind']);self.assertEqual(len(self.mutations),before+1)
        self.assertEqual(self.case.req('types',row['id']),changed)

    def test_used_type_nature_is_locked_name_remains_editable(self):
        from playwright.sync_api import expect
        row=self.type('Used nature browser');item=self.case.item(item_type_id=row['id'])
        self.types_page('en');self.open_type(row);expect(control(self.page,'catalog-kind')).to_be_disabled()
        control(self.page,'catalog-name').fill('Renamed used browser');before=len(self.mutations);changed=self.save_type(row)
        self.assertEqual(changed['kind'],'GOOD');self.assertFalse(changed['canChangeKind']);self.assertEqual(changed['name'],'Renamed used browser');self.assertEqual(len(self.mutations),before+1);self.case.full(item)

    def test_new_reference_refuses_unsaved_nature_change(self):
        from playwright.sync_api import expect
        row=self.type('Concurrent nature browser');self.types_page();self.open_type(row);self.choose_kind('INTANGIBLE')
        item=self.case.item(item_type_id=row['id']);before=len(self.mutations);error=self.save_type(row,409)
        self.assertEqual(error['code'],'immutable_item_kind');expect(self.page.get_by_role('alert')).to_contain_text(self.messages['catalog']['immutable_item_kind'])
        self.assertEqual(self.case.req('types',row['id'])['kind'],'GOOD');self.assertEqual(len(self.mutations),before+1);self.case.full(item)
        self.page.reload(wait_until='networkidle');expect(control(self.page,'catalog-kind')).to_be_disabled();self.assertEqual(len(self.mutations),before+1)
