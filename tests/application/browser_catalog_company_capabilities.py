"""Filtri e indicatori atomici delle abilitazioni effettive nel browser reale."""
from urllib.parse import urlsplit,parse_qs
from browser_catalog_companies import CatalogCompaniesBrowser

BROWSER_CASES=('test_italian_atomic_columns_icons_and_server_filters','test_english_filters_refresh_and_menu_reset','test_mobile_search_is_first_filter')
class CatalogCompanyCapabilitiesBrowser(CatalogCompaniesBrowser):
    def prepare_rows(self):
        good=self.case.item(name='Enabled material');self.api_case.config(self.a,good,{'is_sellable':True,'is_purchasable':True,'track_stock':True})
        digital_type=self.case.create('types',{'name':'Digital type','kind':'INTANGIBLE','default_track_stock':False})
        digital=self.case.item(name='Digital purchase',item_type_id=digital_type['id']);self.api_case.config(self.a,digital,{'is_sellable':False,'is_purchasable':True})
        paused=self.case.item(name='Paused material');self.api_case.config(self.a,paused,{'is_sellable':True,'is_purchasable':True,'track_stock':True});paused=self.case.status(paused,'SUSPENDED')
        return good,digital,paused
    def rows(self):return self.page.locator('#company-catalog-table tr[data-company-id]')
    def row(self,item):return self.page.locator('#company-catalog-table tr[data-item-id="'+item['id']+'"]')
    def select_capability(self,key,value):
        with self.page.expect_response(lambda response:response.request.method=='GET' and urlsplit(response.url).path=='/api/catalog/item-companies' and parse_qs(urlsplit(response.url).query).get(key)==[value]) as loaded:
            self.page.locator('#company-catalog-'+key).click();label=self.messages['catalogCompanies']['ALL'] if value=='ALL' else self.messages['catalog']['yes' if value=='YES' else 'no'];self.page.get_by_role('option',name=label,exact=True).click()
        self.assertEqual(loaded.value.status,200);return loaded.value.json()
    def check_icon(self,item,key,value):
        from playwright.sync_api import expect
        cell=self.row(item).locator('[data-capability="'+key+'"]');expect(cell).to_have_count(1)
        label=self.messages['catalog']['yes' if value else 'no'];expect(cell.get_by_role('img',name=label,exact=True)).to_have_count(1)
        self.assertIn('text-green-600' if value else 'text-red-600',cell.inner_html());expect(cell.locator('svg')).to_have_count(1)
    def test_italian_atomic_columns_icons_and_server_filters(self):
        from playwright.sync_api import expect
        good,digital,paused=self.prepare_rows();self.login();self.navigate_company_catalog();expect(self.rows()).to_have_count(3)
        headers=self.page.locator('#company-catalog-table thead');expect(headers.get_by_text(self.messages['catalogCompanies']['configuration'],exact=True)).to_have_count(0);expect(headers.get_by_text(self.messages['catalogCompanies']['effective'],exact=True)).to_have_count(0)
        for key in ('canSell','canPurchase','canTrackStock'):expect(headers.get_by_text(self.messages['catalogCompanies'][key],exact=True)).to_have_count(1)
        expect(self.page.locator('#company-catalog-kind')).to_have_count(0)
        first=self.page.locator('label[for="company-catalog-search"]').evaluate('element => element.parentElement.parentElement.firstElementChild.contains(element)');self.assertTrue(first,'La ricerca deve essere il primo filtro')
        for key in ('canSell','canPurchase','canTrackStock'):self.check_icon(good,key,True);self.check_icon(paused,key,False)
        self.check_icon(digital,'canSell',False);self.check_icon(digital,'canPurchase',True);self.check_icon(digital,'canTrackStock',False)
        data=self.select_capability('canSell','YES');self.assertEqual(data['total'],1);expect(self.row(good)).to_be_visible();expect(self.rows()).to_have_count(1)
        self.select_capability('canSell','ALL');data=self.select_capability('canPurchase','NO');self.assertEqual(data['total'],1);expect(self.row(paused)).to_be_visible()
        self.select_capability('canPurchase','ALL');data=self.select_capability('canTrackStock','NO');self.assertEqual(data['total'],2);expect(self.rows()).to_have_count(2)
        data=self.select_capability('canSell','YES');self.assertEqual(data['total'],0);expect(self.rows()).to_have_count(0)
        self.select_capability('canSell','ALL');self.select_capability('canTrackStock','ALL');expect(self.rows()).to_have_count(3)
        self.assertEqual(self.mutations,[]);self.assertEqual(self.company_writes,[])
    def test_english_filters_refresh_and_menu_reset(self):
        from playwright.sync_api import expect
        good,digital,paused=self.prepare_rows();self.login('en');self.navigate_company_catalog();self.select_capability('canTrackStock','NO');expect(self.rows()).to_have_count(2)
        self.page.reload(wait_until='networkidle');expect(self.page.locator('#company-catalog-canTrackStock')).to_contain_text(self.messages['catalog']['no']);expect(self.rows()).to_have_count(2)
        self.check_icon(digital,'canPurchase',True);self.check_icon(paused,'canSell',False)
        self.navigate_company_catalog();expect(self.page.locator('#company-catalog-canTrackStock')).to_contain_text(self.messages['catalogCompanies']['ALL']);expect(self.rows()).to_have_count(3)
        expect(self.page.locator('#company-catalog-enabled')).to_contain_text(self.messages['catalogCompanies']['ENABLED']);self.assertEqual(self.mutations,[])
    def test_mobile_search_is_first_filter(self):
        from playwright.sync_api import expect
        self.login();self.navigate_company_catalog();self.page.set_viewport_size({'width':390,'height':844})
        search=self.page.locator('#company-catalog-search');company=self.page.locator('#company-catalog-company');expect(search).to_be_visible()
        toggle=self.page.locator('#company-catalog-filters-toggle');expect(toggle).to_be_visible();expect(company).to_be_hidden();toggle.click();expect(company).to_be_visible()
        a=search.bounding_box();b=company.bounding_box();self.assertLess(a['y'],b['y']);self.assertGreaterEqual(a['x'],0);self.assertLessEqual(a['x']+a['width'],390)
        for key in ('canSell','canPurchase','canTrackStock'):expect(self.page.locator('#company-catalog-'+key)).to_have_count(1)
        expect(self.page.locator('#company-catalog-kind')).to_have_count(0);self.assertEqual(self.mutations,[])
