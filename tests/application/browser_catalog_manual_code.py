"""Prova browser reale dei codici manuali e della numerazione automatica invariata."""
from urllib.parse import urlsplit
from browser_catalog_item_states import CatalogItemStateBrowser,control

BROWSER_CASES=('test_manual_ascii_code_italian_create_and_edit','test_manual_ascii_code_english_create_and_edit','test_automatic_code_unaffected')
class CatalogManualCodeBrowser(CatalogItemStateBrowser):
    def prove_manual(self,locale):
        from playwright.sync_api import expect
        self.case.manual();self.login(locale);self.navigate();self.new_form('Manual ASCII '+locale)
        code=self.field('code');expect(code).to_have_attribute('maxlength','40');expect(code).to_have_attribute('pattern','[A-Za-z0-9]{1,40}')
        for invalid in ('AB CD','AB-CD','AB_CD','AB/CD','caffè','ＡBC',' ABC','ABC '):
            code.fill(invalid);control(self.dialog(),'item-save').click()
            expect(code).to_have_attribute('aria-invalid','true');expect(self.page.get_by_test_id('catalog-item-activation-confirm')).to_have_count(0)
            expect(self.dialog()).to_contain_text(self.messages['catalogItems']['catalog_item_manual_code_invalid']);self.assertEqual(self.mutations,[])
        self.page.reload(wait_until='networkidle');expect(self.field('code')).to_have_value('ABC ')
        control(self.dialog(),'item-save').click();expect(self.field('code')).to_have_attribute('aria-invalid','true');self.assertEqual(self.mutations,[])
        self.field('code').fill('A'*41);expect(self.field('code')).to_have_value('A'*40)
        self.field('code').fill('aB09'*10);self.choose_status('Sospeso' if locale=='it' else 'Suspended')
        with self.page.expect_response(lambda response:response.request.method=='POST' and urlsplit(response.url).path=='/api/catalog/items') as saved:control(self.dialog(),'item-save').click()
        self.assertEqual(saved.value.status,201,saved.value.text());row=saved.value.json();self.assertEqual(row['code'],'aB09'*10);self.case.full(row)
        expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
        control(self.page,'catalog-item-filter-status').click();self.page.get_by_role('option',name='Sospeso' if locale=='it' else 'Suspended',exact=True).click()
        self.open(row);before=len(self.mutations);self.field('code').fill('NEW-CODE');control(self.dialog(),'item-save').click();expect(self.field('code')).to_have_attribute('aria-invalid','true');self.assertEqual(len(self.mutations),before)
        self.field('code').fill('NewCode09')
        with self.page.expect_response(lambda response:response.request.method=='PUT' and urlsplit(response.url).path=='/api/catalog/items/'+row['id']) as saved:control(self.dialog(),'item-save').click()
        self.assertEqual(saved.value.status,200,saved.value.text());changed=saved.value.json();self.assertEqual(changed['code'],'NewCode09');self.case.full(changed)
    def test_manual_ascii_code_italian_create_and_edit(self):self.prove_manual('it')
    def test_manual_ascii_code_english_create_and_edit(self):self.prove_manual('en')
    def test_automatic_code_unaffected(self):
        from playwright.sync_api import expect
        self.login('it');self.navigate();self.new_form('Automatic numbering unaffected');expect(self.field('code')).to_have_count(0)
        control(self.dialog(),'item-save').click();expect(self.page.get_by_test_id('catalog-item-activation-confirm')).to_be_visible();row=self.confirm_active_save('POST')
        self.assertEqual(row['code'],'ART-000001');self.open(row);expect(self.field('code')).to_be_disabled();expect(self.field('code')).not_to_have_attribute('maxlength','40')
        self.field('name').fill('Automatic unchanged code retained')
        with self.page.expect_response(lambda response:response.request.method=='PUT' and urlsplit(response.url).path=='/api/catalog/items/'+row['id']) as saved:control(self.dialog(),'item-save').click()
        self.assertEqual(saved.value.status,200,saved.value.text());self.assertEqual(saved.value.json()['code'],row['code']);self.case.full(saved.value.json())
