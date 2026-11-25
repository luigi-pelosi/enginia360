"""Chromium reale: nature, filtri e quattro numerazioni; nessun trasporto simulato."""
from browser_catalog_item_states import CatalogItemStateBrowser,control

BROWSER_CASES=('test_intangible_italian_create_and_recover','test_charge_english_create_and_filter','test_four_independent_numbering_rows_and_kind_filter')
LABELS={'it':{'INTANGIBLE':'Bene immateriale','CHARGE':'Onere accessorio'},'en':{'INTANGIBLE':'Intangible asset','CHARGE':'Ancillary charge'}}

class CatalogNaturesBrowser(CatalogItemStateBrowser):
    def prove_kind(self,kind,locale,prefix):
        from playwright.sync_api import expect
        kind_type=self.case.create('types',{'name':'Synthetic '+kind,'kind':kind,'is_active':True,'default_sellable':True,'default_purchasable':True,'default_track_stock':False})
        self.login(locale);self.navigate()
        control(self.page,'catalog-item-new').click()
        self.field('name').fill('Browser '+kind)
        self.choose('type_id',kind_type);self.choose('category_id',self.case.category);self.choose('base_uom_id',self.case.base)
        expect(control(self.dialog(),'item-tab-physical')).to_have_count(0)
        self.page.reload(wait_until='networkidle')
        expect(self.field('name')).to_have_value('Browser '+kind)
        expect(self.field('type_id')).to_contain_text(kind_type['name'])
        expect(control(self.dialog(),'item-tab-physical')).to_have_count(0)
        before=len(self.mutations)
        control(self.dialog(),'item-save').click()
        confirmation=self.page.get_by_test_id('catalog-item-activation-confirm')
        expect(confirmation).to_be_visible();self.assertEqual(len(self.mutations),before)
        row=self.confirm_active_save('POST')
        self.assertEqual(row['kind'],kind);self.assertEqual(row['code'],prefix+'000001');self.assertIsNone(row['physicalData'])
        self.assertEqual(len(self.mutations),before+1);self.case.full(row)
        control(self.page,'catalog-item-filter-kind').click()
        self.page.get_by_role('option',name=LABELS[locale][kind],exact=True).click()
        record=control(self.page,'catalog-item-table').locator('tr[data-record-id="'+row['id']+'"]')
        expect(record).to_have_count(1)
        self.page.reload(wait_until='networkidle')
        expect(control(self.page,'catalog-item-filter-kind')).to_contain_text(LABELS[locale][kind])
        expect(record).to_have_count(1)
        self.open(row);expect(control(self.dialog(),'item-tab-physical')).to_have_count(0)
        self.assertEqual(self.case.req('numbering',kind=kind)['nextNumber'],2)
        self.assertEqual(self.case.req('numbering',kind='GOOD')['nextNumber'],1)
        self.assertEqual(self.case.req('numbering',kind='SERVICE')['nextNumber'],1)

    def test_intangible_italian_create_and_recover(self):self.prove_kind('INTANGIBLE','it','IMM-')
    def test_charge_english_create_and_filter(self):self.prove_kind('CHARGE','en','ONR-')

    def test_four_independent_numbering_rows_and_kind_filter(self):
        from playwright.sync_api import expect
        self.login('it')
        nav=self.page.locator('nav')
        self.page.get_by_role('button',name=self.messages['resources']['settings'],exact=True).click()
        self.page.get_by_role('button',name=self.app('masterData'),exact=True).click()
        self.page.locator('#main').get_by_role('button',name=self.messages['resources']['settings-catalog'],exact=True).click()
        self.page.get_by_role('button',name=self.messages['resources']['catalog-numbering'],exact=True).click()
        table=control(self.page,'catalog-table')
        expect(table.locator('tr[data-record-id]')).to_have_count(4)
        for kind,prefix in (('GOOD','ART-'),('INTANGIBLE','IMM-'),('SERVICE','SRV-'),('CHARGE','ONR-')):
            expect(table.locator('tr[data-record-id="'+kind+'"]')).to_contain_text(prefix)
        self.page.get_by_role('combobox',name=self.messages['catalog']['kind'],exact=True).click()
        self.page.get_by_role('option',name='Bene immateriale',exact=True).click()
        expect(table.locator('tr[data-record-id]')).to_have_count(1)
        expect(table.locator('tr[data-record-id="INTANGIBLE"]')).to_be_visible()
        self.assertEqual(self.mutations,[])
