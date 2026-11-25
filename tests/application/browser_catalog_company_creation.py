"""Chromium: aziende locali prima del primo salvataggio dell'articolo (§11.14)."""
from urllib.parse import urlsplit
from browser_catalog_companies import CatalogCompaniesBrowser,control

BROWSER_CASES=('test_local_companies_refresh_then_one_atomic_root_post','test_local_remove_and_parent_cancel_never_write','test_lost_atomic_root_response_refresh_never_replays')
class CatalogCompanyCreationBrowser(CatalogCompaniesBrowser):
    def new_form(self,name,locale='it',item_type=None):
        self.login(locale);self.navigate();control(self.page,'catalog-item-new').click()
        self.field('name').fill(name);self.choose('type_id',item_type or self.case.good);self.choose('category_id',self.case.category);self.choose('base_uom_id',self.case.base)
        control(self.dialog(),'item-tab-companies').click()
    def add_local(self,company,purchasable=None):
        from playwright.sync_api import expect
        self.page.locator('#catalog-company-draft-add').click();dialog=self.page.get_by_test_id('catalog-company-draft-editor');expect(dialog).to_be_visible()
        self.page.locator('#catalog-company-draft-company').click();self.page.get_by_role('option',name=company['name'],exact=True).click()
        if purchasable is not None:self.toggle('catalog-company-draft-is-purchasable',purchasable)
        self.page.locator('#catalog-company-draft-save').click();expect(dialog).to_have_count(0)
        expect(self.page.locator('#catalog-company-drafts-table tr[data-company-id="'+company['id']+'"]')).to_have_count(1)
    def root_create(self):
        from playwright.sync_api import expect
        control(self.dialog(),'item-save').click();confirmation=self.page.get_by_test_id('catalog-item-activation-confirm');expect(confirmation).to_be_visible()
        with self.page.expect_response(lambda response:response.request.method=='POST' and urlsplit(response.url).path=='/api/catalog/items') as saved:control(confirmation,'item-activation-confirm').click()
        self.assertEqual(saved.value.status,201,saved.value.text());expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
        return saved.value.json()
    def test_local_companies_refresh_then_one_atomic_root_post(self):
        from playwright.sync_api import expect
        ty=self.case.create('types',{'name':'Local company defaults','kind':'GOOD','default_sellable':False,'default_purchasable':True,'default_track_stock':True})
        self.new_form('Atomic browser companies','it',ty)
        self.page.locator('#catalog-company-draft-add').click()
        expect(self.page.locator('#catalog-company-draft-is-sellable')).to_have_attribute('aria-checked','false')
        expect(self.page.locator('#catalog-company-draft-track-stock')).to_have_attribute('aria-checked','true')
        self.page.locator('#catalog-company-draft-cancel').click()
        self.add_local(self.a,False);self.add_local(self.b,True)
        self.assertEqual(self.mutations,[]);self.assertEqual(self.company_writes,[]);self.assertEqual(self.api_case.list_configs()['total'],0)
        self.page.reload(wait_until='networkidle');expect(self.page.locator('#catalog-company-drafts-table tr[data-company-id]')).to_have_count(2)
        row=self.root_create();self.assertEqual(len(self.mutations),1);self.assertEqual(len(self.mutations[0]['body']['companies']),2);self.assertEqual(self.company_writes,[])
        a=self.api_case.read_config(self.a,row);b=self.api_case.read_config(self.b,row)
        self.assertFalse(a['is_sellable']);self.assertFalse(a['is_purchasable']);self.assertTrue(b['is_purchasable']);self.assertTrue(a['track_stock']);self.case.full(row)
    def test_local_remove_and_parent_cancel_never_write(self):
        from playwright.sync_api import expect
        self.new_form('Cancelled local companies','en');expect(self.page.locator('#catalog-company-drafts-table tr[data-company-id]')).to_have_count(0)
        self.add_local(self.a)
        self.page.locator('#catalog-company-draft-remove-'+self.a['id']).click();expect(self.page.locator('#catalog-company-drafts-table tr[data-company-id]')).to_have_count(0)
        self.add_local(self.b);control(self.dialog(),'item-cancel').click();expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
        self.assertEqual(self.mutations,[]);self.assertEqual(self.company_writes,[]);self.assertEqual(self.case.req('items')['total'],0);self.assertEqual(self.api_case.list_configs()['total'],0)
    def test_lost_atomic_root_response_refresh_never_replays(self):
        from playwright.sync_api import expect
        self.new_form('Lost atomic company root');self.add_local(self.a);committed=[]
        def drop(route):
            request=route.request;url=urlsplit(request.url)
            if request.method=='POST' and url.path=='/api/catalog/items' and not committed:
                response=route.fetch(url=f'http://127.0.0.1:{self.state["apiPort"]}'+url.path+('?' +url.query if url.query else ''),headers={**request.all_headers(),'host':url.netloc},max_retries=0,max_redirects=0)
                self.assertEqual(response.status,201);committed.append(response.json());route.abort('failed')
            else:route.fallback()
        self.page.route('**/api/catalog/items*',drop)
        control(self.dialog(),'item-save').click();confirmation=self.page.get_by_test_id('catalog-item-activation-confirm');expect(confirmation).to_be_visible()
        with self.page.expect_event('requestfailed',predicate=lambda request:request.method=='POST' and urlsplit(request.url).path=='/api/catalog/items'):control(confirmation,'item-activation-confirm').click()
        expect(self.page.locator('#item-review')).to_be_enabled();self.assertEqual(len(committed),1);self.assertEqual(len(self.mutations),1)
        self.page.reload(wait_until='networkidle');expect(self.page.locator('#item-review')).to_be_visible();self.assertEqual(len(self.mutations),1)
        self.page.locator('#item-review').click();expect(self.page.locator('#item-acknowledge')).to_be_visible();self.page.locator('#item-acknowledge').click()
        expect(self.page.locator('#item-review')).to_have_count(0);self.assertEqual(len(self.mutations),1);self.assertEqual(self.company_writes,[])
        row=committed[0];self.case.full(row);self.assertTrue(self.api_case.read_config(self.a,row)['is_enabled']);self.assertEqual(self.api_case.list_configs()['total'],1)
