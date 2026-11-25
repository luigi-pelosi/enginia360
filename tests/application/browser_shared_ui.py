"""Barra filtri adattiva e allineamento semantico su fixture browser isolate."""
from browser_catalog_company_capabilities import CatalogCompanyCapabilitiesBrowser
from catalog_items_helpers import fixture

BROWSER_CASES=('test_desktop_single_filter_row_and_company_alignment','test_overflow_accordion_preserves_filters_refresh_and_mobile','test_numeric_payment_cells_and_headers_follow_shared_alignment','test_business_partner_overflow_and_filters_survive_refresh')
class SharedUiBrowser(CatalogCompanyCapabilitiesBrowser):
    def test_desktop_single_filter_row_and_company_alignment(self):
        from playwright.sync_api import expect
        self.prepare_rows();self.login();self.navigate_company_catalog()
        panel=self.page.locator('#company-catalog-filters')
        ids=['company-catalog-search','company-catalog-company','company-catalog-enabled','company-catalog-canSell','company-catalog-canPurchase','company-catalog-canTrackStock']
        for ident in ids:expect(self.page.locator('#'+ident)).to_be_visible()
        boxes=[self.page.locator('#'+ident).bounding_box() for ident in ids]
        self.assertLessEqual(max(b['y'] for b in boxes)-min(b['y'] for b in boxes),2,'I sei controlli devono entrare sulla stessa riga desktop')
        self.assertEqual([b['x'] for b in boxes],sorted(b['x'] for b in boxes),'La ricerca deve restare il primo filtro a sinistra')
        expect(panel).to_be_visible()
        expect(self.page.locator('#company-catalog-filters-toggle')).to_have_count(0)
        metrics=self.page.locator('#company-catalog-table').evaluate('''table=>({headers:[...table.querySelectorAll('thead th')].map(e=>getComputedStyle(e).textAlign),rows:[...table.querySelectorAll('tbody tr[data-company-id]')].map(row=>[...row.children].map(e=>getComputedStyle(e).textAlign)),icons:[...table.querySelectorAll('[data-capability]')].map(cell=>{const c=cell.getBoundingClientRect(),s=cell.querySelector('svg').getBoundingClientRect();return Math.abs(c.x+c.width/2-s.x-s.width/2);}),actions:[...table.querySelectorAll('td[data-kind="actions"]')].map(cell=>{const c=cell.getBoundingClientRect(),buttons=[...cell.querySelectorAll('button')].map(b=>b.getBoundingClientRect());return buttons.length?Math.abs((Math.min(...buttons.map(b=>b.left))+Math.max(...buttons.map(b=>b.right)))/2-c.x-c.width/2):0;})})''')
        expected=['left','left','center','center','center','center','center','center'];self.assertEqual(metrics['headers'],expected)
        for row in metrics['rows']:self.assertEqual(row,expected)
        self.assertTrue(all(delta<=2 for delta in metrics['icons']),metrics['icons']);self.assertTrue(all(delta<=2 for delta in metrics['actions']),metrics['actions'])
        self.page.screenshot(path=str(fixture.EVIDENCE/'shared-ui-desktop-company.png'),full_page=True);self.assertEqual(self.mutations,[])
    def test_overflow_accordion_preserves_filters_refresh_and_mobile(self):
        from playwright.sync_api import expect
        self.prepare_rows();self.login('en');self.navigate_company_catalog();self.page.set_viewport_size({'width':1024,'height':900})
        toggle=self.page.locator('#company-catalog-filters-toggle');expect(toggle).to_be_visible();expect(toggle).to_have_attribute('aria-expanded','false')
        expect(self.page.locator('#company-catalog-canTrackStock')).to_be_hidden();self.assertEqual(toggle.get_attribute('aria-controls'),'company-catalog-filters-more')
        toggle.click();expect(toggle).to_have_attribute('aria-expanded','true');expect(self.page.locator('#company-catalog-canTrackStock')).to_be_visible()
        self.select_capability('canTrackStock','NO');expect(self.rows()).to_have_count(2);toggle.click();expect(self.page.locator('#company-catalog-canTrackStock')).to_be_hidden();expect(self.rows()).to_have_count(2)
        self.page.reload(wait_until='networkidle');expect(toggle).to_have_attribute('aria-expanded','false');expect(self.rows()).to_have_count(2)
        toggle.focus();self.page.keyboard.press('Enter');expect(toggle).to_have_attribute('aria-expanded','true');expect(self.page.locator('#company-catalog-canTrackStock')).to_contain_text(self.messages['catalog']['no'])
        self.page.reload(wait_until='networkidle');expect(toggle).to_have_attribute('aria-expanded','true');expect(self.rows()).to_have_count(2)
        self.page.set_viewport_size({'width':1440,'height':1050});expect(toggle).to_have_count(0);expect(self.page.locator('#company-catalog-canTrackStock')).to_be_visible()
        self.page.set_viewport_size({'width':390,'height':844});expect(toggle).to_be_visible();expect(self.page.locator('#company-catalog-search')).to_be_visible()
        if toggle.get_attribute('aria-expanded')=='true':toggle.click()
        expect(self.page.locator('#company-catalog-company')).to_be_hidden();toggle.click();expect(self.page.locator('#company-catalog-company')).to_be_visible()
        for ident in ('company-catalog-search','company-catalog-filters-toggle'):
            b=self.page.locator('#'+ident).bounding_box();self.assertGreaterEqual(b['x'],0);self.assertLessEqual(b['x']+b['width'],390)
        self.page.screenshot(path=str(fixture.EVIDENCE/'shared-ui-mobile-overflow.png'),full_page=True);self.assertEqual(self.mutations,[])
    def test_numeric_payment_cells_and_headers_follow_shared_alignment(self):
        from playwright.sync_api import expect
        self.login();self.page.locator('nav').get_by_role('button',name=self.messages['resources']['payments'],exact=True).click()
        workspace=self.page.locator('[data-payments-workspace]');expect(workspace).to_be_visible();workspace.locator('#payment-company').click();self.page.get_by_role('option',name=self.a['name'],exact=True).click()
        workspace.get_by_role('button',name='Condizioni di pagamento',exact=True).click();workspace.get_by_role('button',name='Nuovo',exact=True).click()
        dialog=self.page.get_by_role('dialog');dialog.get_by_role('tab',name='Rate',exact=True).click();table=dialog.locator('[data-installments-table] table');expect(table).to_be_visible()
        numeric=table.locator('td[data-kind="number"]');self.assertGreater(numeric.count(),0)
        for cell in numeric.all():self.assertEqual(cell.evaluate('e=>getComputedStyle(e).textAlign'),'right')
        for head in table.locator('th[data-kind="number"]').all():self.assertEqual(head.evaluate('e=>getComputedStyle(e).textAlign'),'center')
        for control in numeric.locator('input').all():self.assertEqual(control.evaluate('e=>getComputedStyle(e).textAlign'),'right')
        self.page.screenshot(path=str(fixture.EVIDENCE/'shared-ui-numeric-payment.png'),full_page=True)
        dialog.get_by_role('button',name='Annulla',exact=True).click();self.assertEqual(self.mutations,[])
    def test_business_partner_overflow_and_filters_survive_refresh(self):
        from playwright.sync_api import expect
        self.login('en');self.page.locator('nav').get_by_role('button',name=self.messages['resources']['business-partners'],exact=True).click()
        self.page.locator('[data-action="partner-company-view"]').click();expect(self.page.locator('#company-partner-filters')).to_be_visible()
        self.page.set_viewport_size({'width':1024,'height':900});toggle=self.page.locator('#company-partner-filters-toggle');expect(toggle).to_be_visible();expect(self.page.locator('#company-partner-usable')).to_be_hidden();toggle.click()
        self.page.locator('#company-partner-role').click();self.page.get_by_role('option',name=self.messages['partnerCompanies']['SUPPLIER'],exact=True).click();self.page.locator('#company-partner-search').fill('Retained search')
        expect(self.page.locator('#company-partner-role')).to_contain_text(self.messages['partnerCompanies']['SUPPLIER'])
        self.page.reload(wait_until='networkidle');expect(toggle).to_have_attribute('aria-expanded','true');expect(self.page.locator('#company-partner-search')).to_have_value('Retained search');expect(self.page.locator('#company-partner-role')).to_contain_text(self.messages['partnerCompanies']['SUPPLIER'])
        toggle.click();expect(self.page.locator('#company-partner-usable')).to_be_hidden();self.page.reload(wait_until='networkidle');expect(toggle).to_have_attribute('aria-expanded','false');expect(self.page.locator('#company-partner-search')).to_have_value('Retained search');self.assertEqual(self.mutations,[])
