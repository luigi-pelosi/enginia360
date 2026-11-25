"""Chromium reale Fase 3: form indipendenti, scope, bulk e risposte perse."""
from urllib.parse import urlsplit
from browser_catalog_items_proof import CatalogItemsBrowser,control
from test_catalog_companies_http import CatalogCompaniesHttp
from catalog_items_helpers import ORIGIN

BROWSER_CASES=('test_item_company_form_preserves_main_draft_and_independent_configuration',
 'test_company_only_reader_navigation_filter_and_no_master_requests',
 'test_multi_item_multi_company_bulk_and_existing_disabled_preserved',
 'test_nonphysical_stock_disabled_and_company_units',
 'test_lost_committed_response_refresh_menu_review_never_replays')

class CatalogCompaniesBrowser(CatalogItemsBrowser):
    def setUp(self):
        super().setUp()
        self.api_case=CatalogCompaniesHttp('test_opt_in_defaults_copied_once_and_independent_companies')
        self.api_case.__dict__.update(self.case.__dict__)
        self.a=self.case.data_create('companies',{'name':'Browser Company A','is_enabled':True})
        self.b=self.case.data_create('companies',{'name':'Browser Company B','is_enabled':True})
        self.api_case.a=self.a;self.api_case.b=self.b
        self.company_writes=[];self.all_api_gets=[]
        def observed(request):
            path=urlsplit(request.url).path
            if request.method=='GET' and path.startswith('/api/'):self.all_api_gets.append(path)
            if path.startswith('/api/companies/') and '/catalog/items/' in path and request.method in ('PUT','PATCH') or path=='/api/catalog/item-companies/bulk-enable' and request.method=='POST':
                self.company_writes.append({'path':path,'method':request.method})
        self.page.on('request',observed)
    def companies_tab(self,item,locale='it'):
        self.login(locale);self.navigate();self.open(item);control(self.dialog(),'item-tab-companies').click()
        from playwright.sync_api import expect
        expect(self.page.get_by_test_id('catalog-item-companies')).to_be_visible()
    def company_dialog(self):return self.page.get_by_test_id('catalog-company-editor')
    def save_company(self,company,item,method='PUT'):
        path='/api/companies/'+company['id']+'/catalog/items/'+item['id']
        with self.page.expect_response(lambda response:response.request.method==method and urlsplit(response.url).path==path) as saved:
            self.page.locator('#catalog-company-save').click()
        self.assertIn(saved.value.status,(200,201),saved.value.text())
        return saved.value.json()
    def navigate_company_catalog(self):
        from playwright.sync_api import expect
        self.page.locator('nav').get_by_role('button',name=self.messages['resources']['catalog'],exact=True).click()
        self.page.get_by_role('button',name=self.messages['resources']['catalog-items'],exact=True).click()
        self.page.locator('[data-action="catalog-company-view"]').click()
        expect(self.page.get_by_test_id('company-catalog-items')).to_be_visible()
    def choose(self,field,row):
        # Le selezioni del padre restano quelle dell'harness originale.
        return super().choose(field,row)
    def choose_company(self,company):
        self.page.locator('#catalog-company-company').click();self.page.get_by_role('option',name=company['name'],exact=True).click()
    def toggle(self,ident,checked):
        from playwright.sync_api import expect
        node=self.page.locator('#'+ident)
        expect(node).to_be_enabled()
        if node.get_attribute('aria-checked')!=str(checked).lower():node.click()
        expect(node).to_have_attribute('aria-checked',str(checked).lower())
    def test_item_company_form_preserves_main_draft_and_independent_configuration(self):
        from playwright.sync_api import expect
        item=self.case.item();self.login();self.navigate();self.open(item)
        self.field('name').fill('Unsaved organization draft')
        control(self.dialog(),'item-tab-companies').click();self.page.locator('#catalog-company-associate').click()
        expect(self.company_dialog()).to_be_visible();self.choose_company(self.a)
        self.toggle('catalog-company-is-purchasable',False);a=self.save_company(self.a,item)
        expect(self.company_dialog()).to_have_count(0);self.assertFalse(a['is_purchasable'])
        self.assertEqual(self.case.req('items',item['id']),item)
        self.page.locator('#catalog-company-associate').click();self.choose_company(self.b)
        b=self.save_company(self.b,item);self.assertTrue(b['is_purchasable'])
        expect(self.company_dialog()).to_have_count(0)
        control(self.dialog(),'item-tab-general').click();expect(self.field('name')).to_have_value('Unsaved organization draft')
        self.page.reload(wait_until='networkidle');expect(self.field('name')).to_have_value('Unsaved organization draft')
        self.assertEqual(self.api_case.read_config(self.a,item),a);self.assertEqual(self.api_case.read_config(self.b,item),b)
        self.assertEqual(len(self.company_writes),2);self.assertEqual(self.case.req('items',item['id']),item)
    def test_company_only_reader_navigation_filter_and_no_master_requests(self):
        from playwright.sync_api import expect
        item=self.case.item();self.api_case.config(self.a,item);self.api_case.config(self.b,item)
        actor,role,credentials=self.api_case.scoped_actor(['catalog-item-companies.read'],[self.a])
        self.login('en',credentials);self.all_api_gets.clear();self.navigate_company_catalog()
        table=self.page.locator('#company-catalog-table');expect(table.locator('tr[data-company-id]')).to_have_count(1)
        expect(table.locator('tr[data-company-id="'+self.a['id']+'"]')).to_be_visible()
        expect(table.locator('tr[data-company-id="'+self.b['id']+'"]')).to_have_count(0)
        expect(self.page.locator('#catalog-company-bulk')).to_have_count(0)
        self.page.locator('#company-catalog-search').fill(item['code']);self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#company-catalog-search')).to_have_value(item['code'])
        expect(table.locator('tr[data-company-id]')).to_have_count(1)
        self.assertFalse(any(path in ('/api/catalog/items','/api/data/companies') for path in self.all_api_gets),self.all_api_gets)
        self.assertEqual(self.company_writes,[])
    def test_multi_item_multi_company_bulk_and_existing_disabled_preserved(self):
        from playwright.sync_api import expect
        x=self.case.item(name='Bulk browser one');y=self.case.item(name='Bulk browser two')
        disabled=self.api_case.config(self.a,x,{'is_enabled':False})
        self.login('en');self.navigate_company_catalog();self.page.locator('#catalog-company-bulk').click()
        dialog=self.page.get_by_test_id('catalog-company-bulk-editor');expect(dialog).to_be_visible()
        self.toggle('catalog-bulk-company-'+self.b['id'],True)
        for item in (x,y):self.toggle('catalog-bulk-item-'+item['id'],True)
        with self.page.expect_response(lambda response:response.request.method=='POST' and urlsplit(response.url).path=='/api/catalog/item-companies/bulk-enable') as saved:self.page.locator('#catalog-bulk-save').click()
        self.assertEqual(saved.value.status,200,saved.value.text());self.assertEqual(saved.value.json()['created'],3);self.assertEqual(saved.value.json()['unchanged'],1)
        expect(dialog).to_have_count(0);expect(self.page.locator('#company-catalog-table tr[data-company-id]')).to_have_count(3)
        self.assertEqual(self.api_case.read_config(self.a,x),disabled);self.assertEqual(len(self.company_writes),1)
        self.page.locator('#company-catalog-enabled').click();self.page.get_by_role('option',name=self.messages['catalogCompanies']['ALL'],exact=True).click()
        expect(self.page.locator('#company-catalog-table tr[data-company-id]')).to_have_count(4)
        self.page.locator('#company-catalog-enabled').click();self.page.get_by_role('option',name=self.messages['catalogCompanies']['DISABLED'],exact=True).click()
        expect(self.page.locator('#company-catalog-table tr[data-company-id]')).to_have_count(1)
        self.page.reload(wait_until='networkidle');expect(self.page.locator('#company-catalog-table tr[data-company-id]')).to_have_count(1)
    def test_nonphysical_stock_disabled_and_company_units(self):
        from playwright.sync_api import expect
        ty=self.case.create('types',{'name':'Digital browser','kind':'INTANGIBLE','default_sellable':True,'default_purchasable':True,'default_track_stock':False})
        item=self.case.item(item_type_id=ty['id']);pack=self.case.pack();item=self.case.child(item,'units',self.case.ratio(pack))
        self.companies_tab(item);self.page.locator('#catalog-company-associate').click();self.choose_company(self.a)
        expect(self.page.locator('#catalog-company-track-stock')).to_be_disabled()
        self.page.locator('#catalog-company-default_purchase_uom_id').click();self.page.get_by_role('option',name=pack['name']+' · '+pack['code'],exact=True).click()
        row=self.save_company(self.a,item);self.assertFalse(row['track_stock']);self.assertEqual(row['effective_purchase_uom_id'],pack['id']);self.assertEqual(self.case.req('items',item['id']),item)
    def test_lost_committed_response_refresh_menu_review_never_replays(self):
        from playwright.sync_api import expect
        item=self.case.item();self.companies_tab(item);self.page.locator('#catalog-company-associate').click();self.choose_company(self.a)
        committed=[];target='/api/companies/'+self.a['id']+'/catalog/items/'+item['id']
        def drop(route):
            request=route.request;url=urlsplit(request.url)
            if request.method=='PUT' and url.path==target and not committed:
                response=route.fetch(url=f'http://127.0.0.1:{self.state["apiPort"]}'+url.path+('?' +url.query if url.query else ''),headers={**request.all_headers(),'host':url.netloc},max_retries=0,max_redirects=0)
                committed.append(response.status);route.abort('failed')
            else:route.fallback()
        self.page.route('**/api/companies/**/catalog/items/*',drop)
        with self.page.expect_event('requestfailed',predicate=lambda request:request.method=='PUT' and urlsplit(request.url).path==target):
            self.page.locator('#catalog-company-save').click()
        expect(self.page.locator('#catalog-company-review')).to_be_enabled();self.assertEqual(committed,[201]);self.assertEqual(len(self.company_writes),1)
        self.page.reload(wait_until='networkidle');expect(self.page.locator('#catalog-company-review')).to_be_visible();self.assertEqual(len(self.company_writes),1)
        control(self.dialog(),'item-cancel').click();expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
        self.navigate();self.open(item);control(self.dialog(),'item-tab-companies').click()
        expect(self.page.locator('#catalog-company-review')).to_be_visible();self.assertEqual(len(self.company_writes),1)
        self.page.locator('#catalog-company-review').click();expect(self.page.locator('#catalog-company-acknowledge')).to_be_visible()
        self.page.locator('#catalog-company-acknowledge').click();expect(self.page.locator('#catalog-company-review')).to_have_count(0)
        self.assertEqual(len(self.company_writes),1);self.assertTrue(self.api_case.read_config(self.a,item)['is_enabled']);self.assertEqual(self.case.req('items',item['id']),item)
