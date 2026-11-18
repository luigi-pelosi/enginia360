"""CRUD organizzazioni e copertura: browser/API reali nel clone isolato."""
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
from test_commercial_organizations import CommercialOrganizationApiTests as ApiCases, canonical
import browser_unified_save as harness
from playwright.sync_api import expect

EVIDENCE=Path('/root/.hermes/cache/scratch/enginia360-commercial-organizations/browser');EVIDENCE.mkdir(parents=True,exist_ok=True)
harness.EVIDENCE=EVIDENCE
IT=json.loads(Path('frontend/messages/it.json').read_text());EN=json.loads(Path('frontend/messages/en.json').read_text())
Base=harness.UnifiedSaveBrowserTests


class CommercialOrganizationBrowserTests(unittest.TestCase):
    setUpClass=classmethod(Base.setUpClass.__func__)
    tearDownClass=classmethod(Base.tearDownClass.__func__)
    tearDown=Base.tearDown
    login=Base.login
    checkbox=Base.checkbox
    full_scope=ApiCases.full_scope
    create_purchasing=ApiCases.create_purchasing
    coverage=ApiCases.coverage

    def setUp(self):
        Base.setUp(self)
        self.a=self.case.create('companies',{'name':'Azienda Alfa'})
        self.b=self.case.create('companies',{'name':'Azienda Beta'})
        self.a1=self.case.create('sites',{'company_id':self.a['id'],'name':'Sede Alfa Uno'})
        self.a2=self.case.create('sites',{'company_id':self.a['id'],'name':'Sede Alfa Due'})
        self.b1=self.case.create('sites',{'company_id':self.b['id'],'name':'Sede Beta Uno'})

    def navigate(self,key,messages=IT):
        button=self.page.locator('nav').get_by_role('button',name=messages['resources'][key],exact=True)
        expect(button).to_have_count(1)
        button.click()

    def new(self,key,messages=IT):
        self.navigate(key,messages)
        self.page.get_by_role('button',name=messages['app']['new'],exact=True).first.click()
        return self.page.get_by_role('dialog')

    def open_purchase(self,org):
        self.navigate('purchasing-organizations')
        self.page.locator('tbody tr').filter(has_text=org['name']).get_by_role('button',name=re.compile('^(Modifica|Dettagli) ')).click()
        return self.page.get_by_role('dialog')

    def panel(self,dialog):
        section=dialog.locator('[data-purchasing-coverage]')
        expect(section).to_be_visible();expect(section).to_have_attribute('aria-busy','false')
        return section

    def add_company(self,section,company,messages=IT):
        section.get_by_role('combobox',name=messages['fields']['company_id'],exact=True).click()
        self.page.get_by_role('option',name=company['name'],exact=True).click()
        section.get_by_role('button',name=messages['app']['add'],exact=True).click()
        block=section.locator('[data-coverage-company="'+company['id']+'"]')
        expect(block).to_have_count(1)
        return block

    def mode(self,block,company,value,messages=IT):
        block.locator('[data-coverage-mode="'+company['id']+'"]').click()
        self.page.get_by_role('option',name=messages['app']['allSites' if value=='all_sites' else 'selectedSites'],exact=True).click()

    def test_sales_navigation_native_create_code_optional(self):
        self.login();dialog=self.new('sales-organizations')
        expect(dialog.locator('#field-code')).not_to_have_attribute('required','')
        dialog.locator('#field-company_id').click();self.page.get_by_role('option',name=self.a['name'],exact=True).click()
        dialog.locator('#field-name').fill('Vendite Service Italia')
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/data/sales-organizations/save' and r.request.method=='POST') as saved:
            dialog.get_by_role('button',name='Salva',exact=True).click()
        self.assertEqual(saved.value.status,201);row=saved.value.json();self.assertIsNone(row['code'])
        self.assertEqual(row['company_id'],self.a['id']);expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations),1)

    def test_purchase_create_multiple_companies_explicit_modes_and_one_save(self):
        self.login();dialog=self.new('purchasing-organizations');section=self.panel(dialog)
        dialog.locator('#field-name').fill('Acquisti centralizzati')
        block_a=self.add_company(section,self.a)
        expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
        self.mode(block_a,self.a,'all_sites')
        block_b=self.add_company(section,self.b);self.mode(block_b,self.b,'selected_sites')
        expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
        self.assertEqual(block_b.locator('[data-coverage-site="'+self.a1['id']+'"]').count(),0)
        self.checkbox(block_b,'[data-coverage-site="'+self.b1['id']+'"]').check()
        expect(dialog.get_by_role('button',name=re.compile('^Salva'))).to_have_count(1)
        self.assertEqual(self.mutations,[])
        self.page.screenshot(path=str(EVIDENCE/'purchase-draft-final.png'),full_page=True)
        with self.page.expect_response(lambda r:urlsplit(r.url).path=='/api/data/purchasing-organizations/save' and r.request.method=='POST') as saved:
            dialog.get_by_role('button',name='Salva',exact=True).click()
        self.assertEqual(saved.value.status,201);org=saved.value.json();expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations),1);self.assertEqual(self.coverage(org),canonical(self.full_scope()))

    def test_switch_mode_clears_hidden_site_ids_and_cancel_discards_all(self):
        org=self.create_purchasing(self.full_scope());self.login();dialog=self.open_purchase(org);section=self.panel(dialog)
        block=section.locator('[data-coverage-company="'+self.b['id']+'"]')
        self.mode(block,self.b,'all_sites')
        self.assertEqual(block.locator('[data-coverage-site]').count(),0)
        self.mode(block,self.b,'selected_sites')
        expect(self.checkbox(block,'[data-coverage-site="'+self.b1['id']+'"]').first).not_to_be_checked()
        expect(dialog.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
        dialog.locator('#field-name').fill('Non salvato')
        dialog.get_by_role('button',name='Annulla',exact=True).click()
        self.assertEqual(self.mutations,[]);self.assertEqual(self.coverage(org),canonical(self.full_scope()))

    def test_scope_only_writer_has_readonly_profile_and_single_save_without_values(self):
        org=self.create_purchasing(self.full_scope())
        _,_,_,credentials=self.case.actor(['purchasing-organizations.read','purchasing-organizations.assign_scope','companies.read','sites.read'])
        self.login(credentials,self.case.tenant['code']);dialog=self.open_purchase(org);section=self.panel(dialog)
        expect(dialog.locator('#field-name')).to_be_disabled()
        block=section.locator('[data-coverage-company="'+self.a['id']+'"]');self.mode(block,self.a,'selected_sites')
        self.checkbox(block,'[data-coverage-site="'+self.a1['id']+'"]').check()
        dialog.get_by_role('button',name='Salva',exact=True).click();expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations),1);self.assertNotIn('values',self.mutations[0]['body'])
        changed=self.full_scope();changed[0]={'companyId':self.a['id'],'siteScope':'selected_sites','siteIds':[self.a1['id']]}
        self.assertEqual(self.coverage(org),canonical(changed))

    def test_profile_writer_cannot_change_scope_and_does_not_resubmit_it(self):
        org=self.create_purchasing(self.full_scope())
        _,_,_,credentials=self.case.actor(['purchasing-organizations.read','purchasing-organizations.update','companies.read','sites.read'])
        self.login(credentials,self.case.tenant['code']);dialog=self.open_purchase(org);section=self.panel(dialog)
        for trigger in section.locator('[data-coverage-mode]').all():expect(trigger).to_be_disabled()
        dialog.locator('#field-name').fill('Anagrafica aggiornata')
        dialog.get_by_role('button',name='Salva',exact=True).click();expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations),1);self.assertNotIn('coverage',self.mutations[0]['body'])
        self.assertEqual(self.coverage(org),canonical(self.full_scope()))

    def test_rejected_commit_retains_scope_draft_and_retry_uses_one_request(self):
        from unified_save_support import sql
        org=self.create_purchasing(self.full_scope());self.login();dialog=self.open_purchase(org);section=self.panel(dialog)
        dialog.locator('#field-name').fill('Acquisti recuperati')
        section.get_by_role('button',name=IT['app']['remove']+' '+self.b['name'],exact=True).click()
        self.assertEqual(section.locator('[data-coverage-company="'+self.b['id']+'"]').count(),0)
        sql("CREATE FUNCTION foundation.commercial_browser_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.resource='purchasing-organization-coverage' AND NEW.record_id='{org['id']}'::uuid THEN RAISE EXCEPTION 'Fixture browser commit failure'; END IF; RETURN NEW; END $$; "
            "CREATE CONSTRAINT TRIGGER commercial_browser_reject AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.commercial_browser_reject();")
        try:
            with self.page.expect_response(lambda response:urlsplit(response.url).path.endswith('/save') and response.request.method=='PUT') as rejected:
                dialog.get_by_role('button',name='Salva',exact=True).click()
            self.assertEqual(rejected.value.status,500)
            expect(dialog.locator('[data-slot=alert]')).to_be_visible()
            expect(dialog.locator('#field-name')).to_have_value('Acquisti recuperati')
            self.assertEqual(section.locator('[data-coverage-company="'+self.b['id']+'"]').count(),0)
            self.assertEqual(self.coverage(org),canonical(self.full_scope()))
            self.assertEqual(sql(f"SELECT name FROM foundation.purchasing_organization WHERE id='{org['id']}'").stdout.strip(),org['name'])
        finally:sql('DROP TRIGGER commercial_browser_reject ON foundation.audit_event;DROP FUNCTION foundation.commercial_browser_reject();')
        dialog.get_by_role('button',name='Salva',exact=True).click();expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations),2)
        self.assertEqual(self.mutations[0]['body'],self.mutations[1]['body'])
        self.assertEqual(self.coverage(org),canonical([self.full_scope()[0]]))

    def test_new_permissions_share_organization_bulk_tree_and_independent_scope_action(self):
        role=self.case.role(name='Ruolo organizzazioni')
        self.login();self.page.locator('nav').get_by_role('button',name='Ruoli',exact=True).click()
        self.page.get_by_role('button',name='Modifica '+role['name'],exact=True).click();dialog=self.page.get_by_role('dialog')
        section=dialog.locator('section').filter(has=self.page.get_by_role('heading',name='Permessi del ruolo',exact=True))
        expect(section.locator('[data-permission-domain]')).to_have_count(3)
        org=section.locator('[data-permission-domain="organization"]')
        self.checkbox(section,'[data-permission-domain-checkbox="organization"]').check()
        expect(org.locator(':scope > summary')).to_contain_text('17/17')
        org.locator(':scope > summary').get_by_text('Organizzazione',exact=True).click()
        purchase=section.locator('[data-permission-resource="purchasing-organizations"]')
        purchase.locator(':scope > summary').get_by_text(IT['resources']['purchasing-organizations'],exact=True).click()
        leaf=purchase.locator('[data-permission-code="purchasing-organizations.assign_scope"]').get_by_role('checkbox')
        expect(leaf).to_be_checked();leaf.uncheck()
        expect(org.locator(':scope > summary')).to_contain_text('16/17')
        self.assertEqual(self.mutations,[])
        dialog.get_by_role('button',name='Salva',exact=True).click();expect(self.page.get_by_role('dialog')).to_have_count(0)
        expected={value for code,value in self.case.catalog.items() if code.split('.')[0] in ('companies','sites','sales-organizations','purchasing-organizations') and code!='purchasing-organizations.assign_scope'}
        self.assertEqual(set(self.root.request(self.case.link('role-permissions',role['id']))[1]['ids']),expected)
        self.assertEqual(len(self.mutations),1)

    def test_readonly_context_and_mobile_english_labels(self):
        org=self.create_purchasing(self.full_scope())
        _,_,_,credentials=self.case.actor(['purchasing-organizations.read','companies.read','sites.read'])
        self.login(credentials,self.case.tenant['code']);dialog=self.open_purchase(org);section=self.panel(dialog)
        self.assertEqual(dialog.get_by_role('button',name='Salva',exact=True).count(),0)
        for trigger in section.locator('[data-coverage-mode]').all():expect(trigger).to_be_disabled()
        dialog.get_by_role('button',name='Annulla',exact=True).click()
        self.page.get_by_role('combobox',name='Lingua',exact=True).click();self.page.get_by_role('option',name='English',exact=True).click()
        expect(self.page.locator('html')).to_have_attribute('lang','en');self.navigate('purchasing-organizations',EN)
        self.page.locator('tbody tr').filter(has_text=org['name']).get_by_role('button',name=re.compile('^Details ')).click()
        section=self.panel(self.page.get_by_role('dialog'));expect(section).to_contain_text(EN['app']['allSites'])
        self.page.set_viewport_size({'width':390,'height':844});self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.assertEqual(self.mutations,[])


if __name__=='__main__':unittest.main(defaultTest='CommercialOrganizationBrowserTests',verbosity=2)
