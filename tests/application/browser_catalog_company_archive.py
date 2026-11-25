"""Chromium: archiviazione atomica, filtro abilitazioni e recupero senza replay."""
from urllib.parse import urlsplit
from browser_catalog_companies import CatalogCompaniesBrowser,control
from catalog_items_helpers import fixture

BROWSER_CASES=('test_archive_confirmation_disables_companies_and_default_hides_them','test_english_enabled_default_explicit_filters_refresh_and_menu_reset','test_lost_archive_response_keeps_single_atomic_commit')
class CatalogCompanyArchiveBrowser(CatalogCompaniesBrowser):
    def start_archive(self,item):
        from playwright.sync_api import expect
        self.login();self.navigate();self.open(item);self.field('status').click();self.page.get_by_role('option',name='Archiviato',exact=True).click()
        control(self.dialog(),'item-save').click();confirmation=self.page.get_by_test_id('catalog-item-archive-confirm');expect(confirmation).to_be_visible();return confirmation
    def filter(self,value):
        self.page.locator('#company-catalog-enabled').click();self.page.get_by_role('option',name=self.messages['catalogCompanies'][value],exact=True).click()
    def rows(self):return self.page.locator('#company-catalog-table tr[data-company-id]')
    def test_archive_confirmation_disables_companies_and_default_hides_them(self):
        from playwright.sync_api import expect
        item=self.case.item();a=self.api_case.config(self.a,item);b=self.api_case.config(self.b,item)
        confirmation=self.start_archive(item);self.assertEqual(self.mutations,[])
        control(confirmation,'item-archive-cancel').click();expect(confirmation).to_have_count(0)
        self.assertTrue(self.api_case.read_config(self.a,item)['is_enabled']);self.assertTrue(self.api_case.read_config(self.b,item)['is_enabled'])
        control(self.dialog(),'item-save').click();expect(confirmation).to_be_visible()
        with self.page.expect_response(lambda response:response.request.method=='PUT' and urlsplit(response.url).path=='/api/catalog/items/'+item['id']) as saved:control(confirmation,'item-archive-confirm').click()
        self.assertEqual(saved.value.status,200,saved.value.text());archived=saved.value.json();self.assertEqual(archived['status'],'ARCHIVED');self.case.full(archived)
        expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
        for company,old in ((self.a,a),(self.b,b)):
            row=self.api_case.read_config(company,item);self.assertFalse(row['is_enabled']);self.assertEqual(row['version'],old['version']+1)
            for key in ('is_sellable','is_purchasable','track_stock','default_sales_uom_id','default_purchase_uom_id'):self.assertEqual(row[key],old[key])
        self.assertEqual(len(self.mutations),1);self.assertEqual(self.company_writes,[])
        self.navigate_company_catalog();expect(self.page.locator('#company-catalog-enabled')).to_contain_text(self.messages['catalogCompanies']['ENABLED']);expect(self.rows()).to_have_count(0)
        self.filter('DISABLED');expect(self.rows()).to_have_count(2)
        for row in self.rows().all():expect(row).to_contain_text(self.messages['catalogCompanies']['ARCHIVED']);expect(row).to_contain_text(self.messages['catalogCompanies']['DISABLED'])
        self.page.reload(wait_until='networkidle');expect(self.rows()).to_have_count(2)
    def test_english_enabled_default_explicit_filters_refresh_and_menu_reset(self):
        from playwright.sync_api import expect
        enabled=self.case.item();disabled=self.case.item();self.api_case.config(self.a,enabled);self.api_case.config(self.b,disabled,{'is_enabled':False})
        self.login('en');self.navigate_company_catalog();expect(self.rows()).to_have_count(1);expect(self.page.locator('#company-catalog-enabled')).to_contain_text('Enabled')
        self.filter('ALL');expect(self.rows()).to_have_count(2);self.page.reload(wait_until='networkidle');expect(self.rows()).to_have_count(2)
        self.filter('DISABLED');expect(self.rows()).to_have_count(1);expect(self.rows().first).to_have_attribute('data-item-id',disabled['id'])
        self.page.reload(wait_until='networkidle');expect(self.page.locator('#company-catalog-enabled')).to_contain_text('Disabled');expect(self.rows()).to_have_count(1)
        self.navigate_company_catalog();expect(self.page.locator('#company-catalog-enabled')).to_contain_text('Enabled');expect(self.rows()).to_have_count(1);expect(self.rows().first).to_have_attribute('data-item-id',enabled['id'])
        self.assertEqual(self.mutations,[]);self.assertEqual(self.company_writes,[])
    def test_lost_archive_response_keeps_single_atomic_commit(self):
        from playwright.sync_api import expect
        item=self.case.item();a=self.api_case.config(self.a,item);b=self.api_case.config(self.b,item);confirmation=self.start_archive(item);committed=[]
        target='/api/catalog/items/'+item['id']
        def drop(route):
            request=route.request;url=urlsplit(request.url)
            if request.method=='PUT' and url.path==target and not committed:
                response=route.fetch(url=f'http://127.0.0.1:{self.state["apiPort"]}'+url.path+('?' +url.query if url.query else ''),headers={**request.all_headers(),'host':url.netloc},max_retries=0,max_redirects=0)
                self.assertEqual(response.status,200);committed.append(response.json());route.abort('failed')
            else:route.fallback()
        self.page.route('**/api/catalog/items/*',drop)
        with self.page.expect_event('requestfailed',predicate=lambda request:request.method=='PUT' and urlsplit(request.url).path==target):control(confirmation,'item-archive-confirm').click()
        expect(self.page.locator('#item-review')).to_be_enabled();self.assertEqual(len(committed),1)
        self.page.reload(wait_until='networkidle');expect(self.page.locator('#item-review')).to_be_visible();self.page.locator('#item-review').click();expect(self.page.locator('#item-acknowledge')).to_be_visible();self.page.locator('#item-acknowledge').click();expect(self.page.locator('#item-review')).to_have_count(0)
        self.assertEqual(len(self.mutations),1);self.assertEqual(self.company_writes,[])
        for company,old in ((self.a,a),(self.b,b)):
            actual=self.api_case.read_config(company,item);self.assertFalse(actual['is_enabled']);self.assertEqual(actual['version'],old['version']+1)
        self.case.full(committed[0])
