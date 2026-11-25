"""Catalogo unificato: tab, permessi minimi, recupero e URL precedenti."""
from urllib.parse import urlsplit,parse_qs
from browser_catalog_companies import CatalogCompaniesBrowser,control
from catalog_items_helpers import ORIGIN

BROWSER_CASES=('test_italian_tabs_keep_independent_filters_and_refresh_then_menu_resets','test_company_only_reader_enters_unified_screen_without_identity_requests','test_legacy_company_url_selects_company_tab_on_canonical_route','test_uncertain_company_write_survives_unified_menu_reset_without_replay')
class CatalogUnifiedBrowser(CatalogCompaniesBrowser):
    def company_tab(self):
        from playwright.sync_api import expect
        self.page.locator('[data-action="catalog-company-view"]').click();expect(self.page.get_by_test_id('company-catalog-items')).to_be_visible()
    def test_italian_tabs_keep_independent_filters_and_refresh_then_menu_resets(self):
        from playwright.sync_api import expect
        first=self.case.item(name='First identity');second=self.case.item(name='Second identity');self.api_case.config(self.a,second)
        self.login();self.navigate();expect(self.page.locator('[data-action="catalog-identity-view"]')).to_have_attribute('aria-pressed','true')
        expect(self.page.locator('[data-action="catalog-identity-view"]')).to_have_text('Identità');expect(self.page.locator('[data-action="catalog-company-view"]')).to_have_text('Per azienda')
        self.page.locator('#catalog-item-search').fill(first['code']);expect(self.page.locator('#catalog-item-table tr[data-record-id]')).to_have_count(1)
        self.company_tab();expect(self.page.locator('#catalog-item-table')).to_have_count(0);self.page.locator('#company-catalog-search').fill(second['code'])
        expect(self.page.locator('#company-catalog-table tr[data-company-id]')).to_have_count(1)
        self.all_api_gets.clear();self.page.reload(wait_until='networkidle');expect(self.page.locator('[data-action="catalog-company-view"]')).to_have_attribute('aria-pressed','true');expect(self.page.locator('#company-catalog-search')).to_have_value(second['code'])
        self.assertNotIn('/api/catalog/items',self.all_api_gets);self.assertNotIn('/api/catalog/item-options',self.all_api_gets)
        self.page.locator('[data-action="catalog-identity-view"]').click();expect(self.page.locator('#catalog-item-search')).to_have_value(first['code'])
        control(self.page,'catalog-item-new').click();self.field('name').fill('Recovered identity draft');self.page.reload(wait_until='networkidle');expect(self.field('name')).to_have_value('Recovered identity draft');control(self.dialog(),'item-cancel').click()
        self.company_tab();expect(self.page.locator('#company-catalog-search')).to_have_value(second['code'])
        self.navigate();expect(self.page.locator('[data-action="catalog-identity-view"]')).to_have_attribute('aria-pressed','true');expect(self.page.locator('#catalog-item-search')).to_have_value('')
        self.company_tab();expect(self.page.locator('#company-catalog-search')).to_have_value('');expect(self.page.locator('#company-catalog-enabled')).to_contain_text(self.messages['catalogCompanies']['ENABLED'])
        self.assertEqual(self.mutations,[]);self.assertEqual(self.company_writes,[])
    def test_company_only_reader_enters_unified_screen_without_identity_requests(self):
        from playwright.sync_api import expect
        item=self.case.item();self.api_case.config(self.a,item);self.api_case.config(self.b,item)
        actor,role,credentials=self.api_case.scoped_actor(['catalog-item-companies.read'],[self.a]);self.login('en',credentials);self.all_api_gets.clear()
        self.page.locator('nav').get_by_role('button',name=self.messages['resources']['catalog'],exact=True).click()
        expect(self.page.get_by_role('button',name=self.messages['resources']['catalog-item-companies'],exact=True)).to_have_count(0)
        self.page.get_by_role('button',name=self.messages['resources']['catalog-items'],exact=True).click();expect(self.page.locator('[data-action="catalog-company-view"]')).to_have_attribute('aria-pressed','true')
        expect(self.page.locator('[data-action="catalog-company-view"]')).to_have_text('By company');expect(self.page.locator('#company-catalog-table tr[data-company-id]')).to_have_count(1)
        expect(self.page.locator('#company-catalog-table tr[data-company-id="'+self.b['id']+'"]')).to_have_count(0)
        self.assertNotIn('/api/catalog/items',self.all_api_gets);self.assertNotIn('/api/catalog/item-options',self.all_api_gets);self.assertNotIn('/api/data/companies',self.all_api_gets)
        self.page.reload(wait_until='networkidle');expect(self.page.get_by_test_id('company-catalog-items')).to_be_visible();self.assertEqual(self.company_writes,[])
        self.assertEqual(parse_qs(urlsplit(self.page.url).query).get('view'),['catalog-items'])
    def test_legacy_company_url_selects_company_tab_on_canonical_route(self):
        from playwright.sync_api import expect
        item=self.case.item();self.api_case.config(self.a,item);self.login();self.page.goto(ORIGIN+'/?view=catalog-item-companies',wait_until='networkidle')
        expect(self.page.get_by_test_id('company-catalog-items')).to_be_visible();expect(self.page.locator('[data-action="catalog-company-view"]')).to_have_attribute('aria-pressed','true')
        self.assertEqual(parse_qs(urlsplit(self.page.url).query).get('view'),['catalog-items'])
        self.page.reload(wait_until='networkidle');expect(self.page.locator('[data-action="catalog-company-view"]')).to_have_attribute('aria-pressed','true');self.assertEqual(self.mutations,[])
    def test_uncertain_company_write_survives_unified_menu_reset_without_replay(self):
        from playwright.sync_api import expect
        item=self.case.item();self.api_case.config(self.a,item);self.login();self.navigate();self.company_tab()
        self.page.locator('#catalog-company-edit-'+self.a['id']+'-'+item['id']).click();expect(self.company_dialog()).to_be_visible();self.toggle('catalog-company-is-enabled',False)
        target='/api/companies/'+self.a['id']+'/catalog/items/'+item['id'];committed=[]
        def drop(route):
            request=route.request;url=urlsplit(request.url)
            if request.method=='PATCH' and url.path==target and not committed:
                response=route.fetch(url=f'http://127.0.0.1:{self.state["apiPort"]}'+url.path+('?' +url.query if url.query else ''),headers={**request.all_headers(),'host':url.netloc},max_retries=0,max_redirects=0)
                self.assertEqual(response.status,200);committed.append(response.json());route.abort('failed')
            else:route.fallback()
        self.page.route('**/api/companies/**/catalog/items/*',drop)
        with self.page.expect_event('requestfailed',predicate=lambda request:request.method=='PATCH' and urlsplit(request.url).path==target):self.page.locator('#catalog-company-save').click()
        expect(self.page.locator('#catalog-company-review')).to_be_enabled();self.page.reload(wait_until='networkidle');expect(self.page.locator('#catalog-company-review')).to_be_visible()
        self.navigate();self.company_tab();expect(self.page.locator('#catalog-company-review')).to_be_visible();self.assertEqual(len(self.company_writes),1)
        self.page.locator('#catalog-company-review').click();expect(self.page.locator('#catalog-company-acknowledge')).to_be_visible();self.page.locator('#catalog-company-acknowledge').click();expect(self.page.locator('#catalog-company-review')).to_have_count(0)
        self.assertEqual(len(self.company_writes),1);self.assertEqual(len(committed),1);self.assertFalse(self.api_case.read_config(self.a,item)['is_enabled']);self.assertEqual(self.mutations,[])
