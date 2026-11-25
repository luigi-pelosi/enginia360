"""Geometria e comandi reali della barra tab/azioni del Catalogo."""
from urllib.parse import urlsplit
from browser_catalog_unified import CatalogUnifiedBrowser
from browser_catalog_items_proof import control

BROWSER_CASES=('test_desktop_italian_actions_share_tab_row','test_desktop_english_actions_share_tab_row','test_mobile_actions_remain_visible_without_overlap')
class CatalogToolbarBrowser(CatalogUnifiedBrowser):
    def refresh_button(self):return self.page.locator('#main').get_by_role('button',name=self.messages['app']['refresh'],exact=True)
    def assert_desktop_row(self,action):
        from playwright.sync_api import expect
        tab=self.page.locator('[data-action="catalog-identity-view"]');expect(action).to_be_visible()
        a=action.bounding_box();t=tab.bounding_box();shell=self.page.locator('[data-catalog-overview="catalog-items"]').bounding_box()
        self.assertLessEqual(abs((a['y']+a['height']/2)-(t['y']+t['height']/2)),2,'Azioni e tab devono condividere la riga desktop')
        self.assertLessEqual(abs(a['x']+a['width']-shell['x']-shell['width']),2,'Ultima azione allineata a destra')
        refresh=self.refresh_button();expect(refresh).to_have_count(1);r=refresh.bounding_box();self.assertLessEqual(abs((r['y']+r['height']/2)-(t['y']+t['height']/2)),2)
    def prove_desktop(self,locale):
        from playwright.sync_api import expect
        self.login(locale);self.navigate();self.assert_desktop_row(self.page.locator('#catalog-item-new'))
        with self.page.expect_response(lambda response:response.request.method=='GET' and urlsplit(response.url).path=='/api/catalog/items') as loaded:self.refresh_button().click()
        self.assertEqual(loaded.value.status,200)
        self.page.locator('#catalog-item-new').click();expect(self.page.get_by_test_id('catalog-item-editor')).to_be_visible();control(self.dialog(),'item-cancel').click();expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
        self.company_tab();self.assert_desktop_row(self.page.locator('#catalog-company-bulk'))
        with self.page.expect_response(lambda response:response.request.method=='GET' and urlsplit(response.url).path=='/api/catalog/item-companies') as loaded:self.refresh_button().click()
        self.assertEqual(loaded.value.status,200)
        self.page.locator('#catalog-company-bulk').click();expect(self.page.get_by_test_id('catalog-company-bulk-editor')).to_be_visible();self.page.locator('#catalog-bulk-cancel').click();expect(self.page.get_by_test_id('catalog-company-bulk-editor')).to_have_count(0)
        self.assertEqual(self.mutations,[]);self.assertEqual(self.company_writes,[])
    def test_desktop_italian_actions_share_tab_row(self):self.prove_desktop('it')
    def test_desktop_english_actions_share_tab_row(self):self.prove_desktop('en')
    def test_mobile_actions_remain_visible_without_overlap(self):
        from playwright.sync_api import expect
        self.login();self.navigate();self.page.set_viewport_size({'width':390,'height':844})
        for company in (False,True):
            if company:self.company_tab()
            action=self.page.locator('#catalog-company-bulk' if company else '#catalog-item-new');expect(action).to_be_visible();expect(self.refresh_button()).to_have_count(1)
            a=action.bounding_box();tab=self.page.locator('[data-action="catalog-company-view"]').bounding_box();r=self.refresh_button().bounding_box()
            self.assertGreaterEqual(a['x'],0);self.assertLessEqual(a['x']+a['width'],390);self.assertLessEqual(r['x']+r['width'],390)
            overlapping=not(a['x']>=tab['x']+tab['width'] or tab['x']>=a['x']+a['width'] or a['y']>=tab['y']+tab['height'] or tab['y']>=a['y']+a['height'])
            self.assertFalse(overlapping,'Tab e azioni non devono sovrapporsi su mobile')
        self.assertEqual(self.mutations,[])
