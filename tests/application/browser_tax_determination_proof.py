"""Percorsi Chromium finiti Fase4, tutte le API reali, niente API mock.

Solo il fault dichiarato perde una risposta reale già committata. Questi test
non diventano PASS tramite discovery o semplice lancio headless.
"""
import json
import os
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

from tax_helpers import configure_fixture
from test_tax_determination_http import TaxDeterminationHttp, SOURCE_READS
from browser_company_tax_proof import CompanyTaxBrowser
from browser_taxclassification_proof import TaxClassificationBrowser
from browser_tax_proof import TaxBrowser


class TaxDeterminationBrowser(unittest.TestCase):
    http_case_class = TaxDeterminationHttp
    http_case_name = unittest.defaultTestLoader.getTestCaseNames(TaxDeterminationHttp)[0]
    setUp = CompanyTaxBrowser.setUp
    tearDown = TaxClassificationBrowser.tearDown
    login = TaxBrowser.login
    button = TaxBrowser.button
    window_geometry = TaxClassificationBrowser.window_geometry

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        TaxDeterminationHttp.setUpClass()
        cls.fixture = configure_fixture('enginia360-company-tax-proof')
        cls.fixture.EVIDENCE = Path(os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'])
        cls.state = json.loads(Path(os.environ['ENGINIA360_TAX_STATE']).read_text())
        if cls.state['scope'] != cls.fixture.SCOPE or not cls.fixture.verify_target(cls.fixture.WEB):
            raise RuntimeError('Phase4 exact frontend scope unavailable')
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(executable_path=os.environ.get('ENGINIA360_CHROMIUM', '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome'), headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.playwright.stop()

    def navigation(self, section):
        from playwright.sync_api import expect
        self.page.locator('nav').get_by_role('button', name=self.messages['resources']['settings'], exact=True).click()
        self.button('masterData').click()
        self.page.get_by_role('button', name=self.messages['resources']['tax-management'], exact=True).click()
        self.page.get_by_test_id('tax-tab-'+section).click()
        target='#tax-rules-section' if section=='rules' else '#tax-simulator-section'
        expect(self.page.locator(target)).to_be_visible()
        expect(self.page.locator(target)).to_have_attribute('aria-busy','false')

    def choose(self, selector, label):
        from playwright.sync_api import expect
        control=self.page.locator(selector)
        expect(control).to_be_enabled(); control.click()
        self.page.get_by_role('option',name=label,exact=True).click()

    def country_label(self):
        row=self.case.countries['IT']
        return 'IT '+row['name']

    def tab(self, group, key):
        self.page.get_by_role('tab',name=self.messages[group][key],exact=True).click()

    def open_rule(self, rule):
        from playwright.sync_api import expect
        self.page.locator('#tax-rule-search').fill(rule['code'])
        self.page.locator('#tax-rule-open-'+rule['id']).click()
        expect(self.page.locator('#tax-rule-name')).to_have_value(rule['name'])

    def rules_journey(self, locale):
        from playwright.sync_api import expect
        rule=self.case.new_rule()
        self.login(locale); self.navigation('rules'); self.open_rule(rule)
        dialog=self.page.get_by_role('dialog').filter(has=self.page.locator('#tax-rule-name'))
        self.window_geometry(dialog)
        self.page.locator('#tax-rule-name').fill('Local metadata must remain independent')
        self.tab('taxRules','versions')
        self.page.locator('#tax-rule-add-version').click()
        self.choose('#tax-rule-tax-code','VAT_STANDARD Synthetic configured VAT')
        self.page.locator('#tax-rule-valid_from').fill(self.case.day)
        self.page.locator('#tax-rule-legal-reference').fill('Synthetic UI version')
        self.tab('taxRules','conditions')
        self.page.locator('#tax-rule-condition-add').click()
        self.choose('#tax-rule-condition-0-field',self.messages['taxRules']['field_item_nature'])
        self.choose('#tax-rule-condition-0-operator',self.messages['taxRules']['EQUALS'])
        self.choose('#tax-rule-condition-0-value',self.messages['taxRules']['GOOD'])
        conditions = dialog.get_by_role('tabpanel')
        expect(conditions.locator('textarea')).to_have_count(0)
        expect(conditions.get_by_role('combobox')).to_have_count(3)
        self.tab('taxRules','versions')
        with self.page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path.endswith('/versions')) as saved:
            self.page.locator('#tax-rule-version-save').click()
        self.assertEqual(saved.value.status,201,saved.value.text())
        actual=self.case.req(self.case.rule_route(rule))
        self.assertEqual((actual['name'],len(actual['versions'])),(rule['name'],2))
        self.assertEqual(actual['versions'][-1]['conditions'][0]['value'],'GOOD')
        self.tab('taxRules','general')
        expect(self.page.locator('#tax-rule-name')).to_have_value('Local metadata must remain independent')
        expect(self.page.locator('#tax-rule-save')).to_be_disabled()
        writes=len(self.mutations)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tax-rule-name')).to_have_value('Local metadata must remain independent')
        self.assertEqual(len(self.mutations),writes,'Refresh never submits local metadata')

    def test_01_italian_rules_typed_conditions_independent_versions_dialog(self):
        self.rules_journey('it')

    def test_02_english_rules_typed_conditions_independent_versions_dialog(self):
        self.rules_journey('en')

    def fill_context(self):
        from playwright.sync_api import expect
        self.choose('#tax-sim-company',self.case.company['name'])
        expect(self.page.locator('#tax-simulator-section')).to_have_attribute('aria-busy','false')
        self.choose('#tax-sim-type','VAT '+self.case.vat['name'])
        expect(self.page.locator('#tax-simulator-section')).to_have_attribute('aria-busy','false')
        self.page.locator('#tax-sim-date').fill(self.case.day)
        for kind,subject in [('item',self.case.items['GOOD']),('partner',self.case.partners['TAXABLE_PERSON'])]:
            self.page.locator('#tax-sim-choose-'+kind).click()
            self.page.locator('#tax-sim-source-search').fill(subject.get('name') or subject['legal_name'])
            self.page.locator('#tax-sim-source-'+subject['id']).click()
            expect(self.page.locator('#tax-simulator-section')).to_have_attribute('aria-busy','false')

    def fill_facts(self):
        self.tab('taxSimulator','facts')
        labels=self.messages['taxSimulator']
        for selector,label in [('#tax-sim-taxable-person',labels['true']),('#tax-sim-partner_establishment_country_id',self.country_label()),
            ('#tax-sim-operation-category',labels['ORDINARY_MOVABLE_GOODS']),('#tax-sim-ordinary-territory',labels['true']),
            ('#tax-sim-special-treatment',labels['NONE']),('#tax-sim-goods_location_country_id',self.country_label()),
            ('#tax-sim-dispatch_country_id',self.country_label()),('#tax-sim-destination_country_id',self.country_label()),
            ('#tax-sim-customs-status',labels['NATIONAL_OR_UNION'])]: self.choose(selector,label)
        self.page.locator('#tax-sim-source-reference').fill('Synthetic UI declared facts')

    def run_simulation(self):
        from playwright.sync_api import expect
        with self.page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path=='/api/tax/determinations/simulate') as result:
            self.page.locator('#tax-sim-run').click()
        self.assertEqual(result.value.status,200,result.value.text())
        expect(self.page.locator('#tax-sim-result')).to_be_visible()
        return result.value.json()

    def simulator_journey(self,locale):
        from playwright.sync_api import expect
        # A single explicit Draft yields a preview, never an operational result.
        rule=self.case.new_rule()
        self.login(locale); self.navigation('determination'); self.fill_context()
        missing=self.run_simulation()
        self.assertEqual(missing['outcome'],'INCOMPLETE_CONTEXT')
        expect(self.page.locator('#tax-sim-result')).to_contain_text(self.messages['taxSimulator']['INCOMPLETE_CONTEXT'])
        expect(self.page.locator('#tax-sim-result details[open]')).not_to_have_count(0)
        self.fill_facts()
        self.assertEqual(self.run_simulation()['outcome'],'NO_MATCHING_RULE')
        self.page.locator('#tax-sim-pin').click()
        self.tab('taxSimulator','draftPreview')
        self.page.locator('#tax-sim-preview-select').click()
        label=self.page.get_by_role('dialog').locator('label').filter(has_text=rule['versions'][0]['id'])
        label.get_by_role('checkbox').check()
        self.page.get_by_role('dialog').locator('button[data-slot="dialog-close"]').click()
        result=self.run_simulation(); self.case.assert_success(result)
        self.assertEqual(result['result']['taxRuleVersionId'],rule['versions'][0]['id'])
        before=len(self.mutations)
        self.tab('taxSimulator','facts')
        self.page.locator('#tax-sim-source-reference').fill('Changed local fact; result remains submitted snapshot')
        expect(self.page.locator('#tax-sim-stale')).to_be_visible()
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tax-sim-stale')).to_be_visible()
        self.assertEqual(len(self.mutations),before,'No auto simulation on refresh')
        self.tab('taxSimulator','result')
        self.page.locator('#tax-sim-compare').click()
        expect(self.page.locator('#tax-sim-comparison-left')).to_contain_text(self.messages['taxSimulator']['NO_MATCHING_RULE'])
        expect(self.page.locator('#tax-sim-comparison-right')).to_contain_text('17.375000')
        self.page.get_by_role('dialog').locator('button[data-slot="dialog-close"]').click()
        self.assertEqual(self.case.simulate()['outcome'],'NO_MATCHING_RULE')

    def test_03_italian_simulator_missing_trace_selected_preview_stale_compare_refresh(self):
        self.simulator_journey('it')

    def test_04_english_simulator_missing_trace_selected_preview_stale_compare_refresh(self):
        self.simulator_journey('en')

    def test_05_dropped_committed_rule_response_refresh_never_replays(self):
        from playwright.sync_api import expect
        rule=self.case.new_rule()
        self.login(); self.navigation('rules'); self.open_rule(rule)
        self.page.locator('#tax-rule-name').fill('Committed but response dropped')
        self.drop_method='PUT'; self.drop_path='/api/tax/rules/'+rule['id']
        expected_path=self.drop_path
        with self.page.expect_event('requestfailed',predicate=lambda r:r.method=='PUT' and urlsplit(r.url).path==expected_path):
            self.page.locator('#tax-rule-save').click()
        self.assertIsNone(self.drop_path,'The real accepted response was lost only after commit')
        expect(self.page.locator('#tax-rule-review')).to_be_visible()
        actual=self.case.req(self.case.rule_route(rule))
        self.assertEqual((actual['name'],actual['version']),('Committed but response dropped',rule['version']+1))
        before=list(self.mutations)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tax-rule-review')).to_be_visible()
        self.page.locator('#tax-rule-review').click()
        expect(self.page.locator('#tax-rule-acknowledge')).to_be_visible()
        self.assertEqual(self.mutations,before,'Review/refresh must not replay PUT')
        self.assertEqual(self.case.req(self.case.rule_route(rule)),actual)

    def test_06_fresh_revoked_simulation_authority_no_post(self):
        from playwright.sync_api import expect
        actor,role,credentials=self.case.actor(SOURCE_READS+['tax-determination.read','tax-determination.simulate'])
        self.case.assign_companies(role,[self.case.company])
        self.login(credentials=credentials); self.navigation('determination'); self.fill_context(); self.fill_facts()
        status,_=self.case.root.request(self.case.scope('/api/links/role-permissions/'+role['id']),'PUT',{'ids':[]})
        self.assertEqual(status,204)
        before=len(self.mutations)
        self.page.locator('#tax-sim-run').click()
        expect(self.page.locator('#tax-simulator-section').get_by_role('alert')).to_be_visible()
        self.assertEqual(len(self.mutations),before,'Fresh /session check must block stale simulation command')


def load_tests(loader, tests, pattern):
    # Imported predecessor TestCases are helpers, never implicit acceptance.
    return loader.loadTestsFromTestCase(TaxDeterminationBrowser)


if __name__=='__main__':
    unittest.main()
