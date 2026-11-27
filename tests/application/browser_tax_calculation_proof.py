"""Sei percorsi Chromium F5, API reali e selettori letti dai componenti effettivi.

Nessun risultato simulato nel trasporto: il proxy degli helper inoltra alle porte
isolate. Discovery e setup-smoke non autenticando non costituiscono acceptance.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from typing import Any
import unittest
from urllib.parse import urlsplit

from tax_helpers import configure_fixture
from test_tax_calculation_http import TaxCalculationHttp, SIMULATION_GRANTS
from browser_tax_determination_proof import TaxDeterminationBrowser
from browser_company_tax_proof import CompanyTaxBrowser
from browser_taxclassification_proof import TaxClassificationBrowser
from browser_tax_proof import TaxBrowser


# Contratti ID presi da tax-calculation-panel.tsx e tax-simulator.tsx.
STATIC_UI_IDS = (
    'tax-calculation-panel', 'tax-calc-tab', 'tax-calc-add-scenario',
    'tax-calc-run', 'tax-calc-direction', 'tax-calc-result', 'tax-calc-stale',
    'tax-calc-pin', 'tax-calc-comparison', 'tax-calc-document-add',
)
DYNAMIC_UI_PREFIXES = (
    'tax-calc-line-', 'tax-calc-quantity-', 'tax-calc-price-',
    'tax-calc-price-mode-', 'tax-calc-deductible-', 'tax-calc-document-mode-',
    'tax-calc-document-value-',
)


class TaxCalculationBrowser(unittest.TestCase):
    page: Any  # Inizializzata dal setup browser condiviso.
    http_case_class = TaxCalculationHttp
    http_case_name = unittest.defaultTestLoader.getTestCaseNames(TaxCalculationHttp)[0]
    setUp = CompanyTaxBrowser.setUp
    tearDown = TaxClassificationBrowser.tearDown
    login = TaxBrowser.login
    button = TaxBrowser.button
    navigation = TaxDeterminationBrowser.navigation
    choose = TaxDeterminationBrowser.choose
    country_label = TaxDeterminationBrowser.country_label
    tab = TaxDeterminationBrowser.tab
    fill_context = TaxDeterminationBrowser.fill_context
    fill_facts = TaxDeterminationBrowser.fill_facts
    run_simulation = TaxDeterminationBrowser.run_simulation

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        TaxCalculationHttp.setUpClass()
        cls.fixture = configure_fixture('enginia360-company-tax-proof')
        cls.fixture.EVIDENCE = Path(os.environ['ENGINIA360_COMPANY_TAX_EVIDENCE'])
        cls.state = json.loads(Path(os.environ['ENGINIA360_TAX_STATE']).read_text())
        if cls.state['scope'] != cls.fixture.SCOPE or not cls.fixture.verify_target(cls.fixture.WEB):
            raise RuntimeError('Frontend F5 isolato non consegnato')
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path=os.environ.get('ENGINIA360_CHROMIUM',
                '/root/.hermes/tools/chromium-1208/chrome-linux64/chrome'),
            headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def ready(self):
        from playwright.sync_api import expect
        expect(self.page.locator('#tax-simulator-section')).to_have_attribute('aria-busy', 'false')

    def item(self, kind):
        from playwright.sync_api import expect
        self.tab('taxSimulator', 'context')
        self.page.locator('#tax-sim-choose-item').click()
        subject = self.case.items[kind]
        self.page.locator('#tax-sim-source-search').fill(subject['name'])
        self.page.locator('#tax-sim-source-' + subject['id']).click()
        expect(self.page.locator('#tax-sim-selected-item')).to_contain_text(subject['name'])
        self.ready()
        self.tab('taxSimulator', 'facts')
        category = 'ORDINARY_MOVABLE_GOODS' if kind == 'GOOD' else 'GENERAL_SERVICES'
        self.choose('#tax-sim-operation-category', self.messages['taxSimulator'][category])
        if kind == 'SERVICE':
            self.choose('#tax-sim-service_location_country_id', self.country_label())

    def append_scenario(self, price, kind='GOOD', mode='TAX_EXCLUSIVE'):
        from playwright.sync_api import expect
        output = self.run_simulation()
        self.assertEqual(output['outcome'], 'SUCCESS', output)
        before = self.page.locator('#tax-calculation-panel article[id^="tax-calc-line-"]').count()
        self.page.locator('#tax-calc-add-scenario').click()
        panel = self.page.locator('#tax-calculation-panel')
        expect(panel).to_be_visible()
        rows = panel.locator('article[id^="tax-calc-line-"]')
        expect(rows).to_have_count(before + 1)
        row = rows.last
        line_id = row.get_attribute('id').removeprefix('tax-calc-line-')
        self.assertTrue(line_id)
        self.page.locator('#tax-calc-price-' + line_id).fill(price)
        self.page.locator('#tax-calc-price-mode-' + line_id).select_option(mode)
        expect(row).to_contain_text(self.case.items[kind]['id'])
        return line_id, output

    def run_calculation(self, expected=200):
        from playwright.sync_api import expect
        with self.page.expect_response(lambda response: response.request.method == 'POST'
                and urlsplit(response.url).path == '/api/tax/calculations/simulate') as calculation:
            self.page.locator('#tax-calc-run').click()
        response = calculation.value
        self.assertEqual(response.status, expected, response.text())
        self.ready()
        output = response.json()
        if expected == 200:
            self.assertEqual(set(output), {'isSimulation', 'result'})
            self.assertTrue(output['isSimulation'])
            self.case.reconciles(output['result'])
            expect(self.page.locator('#tax-calc-result')).to_be_visible()
            expect(self.page.locator('#tax-calc-result')).to_contain_text(output['result']['totals']['amountPayable'])
        return output

    def begin(self, locale='it', operation='SALE'):
        self.login(locale)
        self.navigation('determination')
        self.fill_context()
        if operation != 'SALE':
            self.choose('#tax-sim-operation', self.messages['taxSimulator'][operation])
            self.ready()
        self.fill_facts()

    def document_discount(self, value):
        self.page.locator('#tax-calc-document-add').click()
        mode = self.page.locator('select[id^="tax-calc-document-mode-"]').last
        mode.select_option('FIXED_AMOUNT')
        control = self.page.locator('input[id^="tax-calc-document-value-"]').last
        control.fill(value)

    def assert_readonly_layout(self):
        original = self.page.viewport_size
        try:
            for width in (1440, 768, 390):
                self.page.set_viewport_size({'width': width, 'height': 1000})
                for identifier in ('tax-calc-result', 'tax-calc-comparison'):
                    result = self.page.locator('#' + identifier)
                    if not result.count():
                        continue
                    result.locator('details').evaluate_all('(nodes) => nodes.forEach(node => {node.open = true})')
                    measurements = result.evaluate('''root => {
                        const visible = node => node.getBoundingClientRect().height > 0;
                        const composite = [...root.querySelectorAll('dd')].filter(node => visible(node) && node.querySelector(':scope > dl, :scope > ol'));
                        const identifiers = [...root.querySelectorAll('dd')].filter(node => visible(node) && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(node.textContent.trim()));
                        return {
                            composite: composite.map(node => ({width: node.getBoundingClientRect().width, parent: node.closest('dl').getBoundingClientRect().width})),
                            identifiers: identifiers.map(node => ({width: node.getBoundingClientRect().width, height: node.getBoundingClientRect().height})),
                            overflow: root.scrollWidth - root.clientWidth
                        };
                    }''')
                    self.assertTrue(measurements['composite'], 'Mancano oggetti annidati reali')
                    self.assertTrue(measurements['identifiers'], 'Mancano UUID reali nello snapshot acquisito')
                    for cell in measurements['composite']:
                        self.assertGreaterEqual(cell['width'], cell['parent'] * .9,
                            f'Oggetto annidato ristretto nella colonna valori: {identifier}, viewport={width}, {cell}')
                    for cell in measurements['identifiers']:
                        self.assertGreaterEqual(cell['width'], 80, f'UUID ridotto a una colonna verticale: {cell}')
                        self.assertLessEqual(cell['height'], 100, f'UUID spezzato carattere per carattere: {cell}')
                    self.assertLessEqual(measurements['overflow'], 2, f'Dettaglio oltre il contenitore a {width}px')
        finally:
            self.page.set_viewport_size(original)

    def multirate_journey(self, locale, inclusive=False):
        from playwright.sync_api import expect
        # Una bozza esplicitamente selezionata è fonte F4, non un rate inviato a F5.
        rule = self.case.new_rule([{'field': 'item.nature', 'operator': 'EQUALS', 'value': 'GOOD'}],
                                 priority=200, tax_code_id=self.case.codes['GOOD']['id'])
        self.begin(locale)
        self.tab('taxSimulator', 'draftPreview')
        self.page.locator('#tax-sim-preview-select').click()
        self.page.locator('input[data-version-id="' + rule['versions'][0]['id'] + '"]').check()
        self.page.get_by_role('dialog').locator('button[data-slot="dialog-close"]').click()
        first, _ = self.append_scenario('122' if inclusive else '100', mode='TAX_INCLUSIVE' if inclusive else 'TAX_EXCLUSIVE')
        self.item('SERVICE')
        second, _ = self.append_scenario('55' if inclusive else '50', kind='SERVICE',
                                         mode='TAX_INCLUSIVE' if inclusive else 'TAX_EXCLUSIVE')
        output = self.run_calculation()
        self.case.assert_totals(output['result'], '150.00', '27.00', '177.00')
        self.assertEqual(len(output['result']['summaries']), 2)
        self.assertEqual({x['lineId'] for x in output['result']['lines']}, {first, second})
        request = [x for x in self.mutations if x['path'] == '/api/tax/calculations/simulate'][-1]['body']
        self.assertEqual([x['fiscal_context']['item_id'] for x in request['lines']],
                         [self.case.items['GOOD']['id'], self.case.items['SERVICE']['id']])
        self.assertEqual(request['lines'][0]['fiscal_context']['draft_version_ids'], [rule['versions'][0]['id']])
        self.assertNotIn('policy', request)
        for line in request['lines']:
            self.assertNotIn('determination', line)
            self.assertNotIn('tax_rate', line)
        self.page.locator('#tax-calc-result details').filter(
            has=self.page.get_by_text(self.messages['taxCalculation']['summaries'], exact=True)).locator('summary').click()
        expect(self.page.locator('#tax-calc-result')).to_contain_text('22.000000')
        expect(self.page.locator('#tax-calc-result')).to_contain_text('10.000000')
        self.document_discount('17.70' if inclusive else '15')
        discounted = self.run_calculation()['result']
        self.case.assert_totals(discounted, '135.00', '24.30', '159.30')
        if inclusive:
            allocation = discounted['calculationTrace']['adjustments'][0]
            from fractions import Fraction
            self.assertEqual(Fraction(allocation['priceBaseAmountExact']), Fraction('17.70'))
        self.assertFalse(any(x['path'] == '/api/tax/calculations' for x in self.mutations),
                         'Il pannello con bozze invia soltanto simulazioni')
        self.assert_readonly_layout()

    def test_01_italian_selected_scenario_two_lines_multirate_document_discount_exclusive(self):
        self.multirate_journey('it')

    def test_02_english_selected_scenario_two_lines_multirate_document_discount_inclusive(self):
        self.multirate_journey('en', inclusive=True)

    def test_03_stable_submitted_pin_stale_refresh_and_parent_context_no_post(self):
        from playwright.sync_api import expect
        self.begin('it')
        line_id, _ = self.append_scenario('100')
        self.run_calculation()
        original = self.page.locator('#tax-calc-result').inner_text()
        self.page.locator('#tax-calc-pin').click()
        expect(self.page.locator('#tax-calc-comparison')).to_contain_text('122.00')
        posts = deepcopy(self.mutations)
        self.page.locator('#tax-calc-price-' + line_id).fill('200')
        expect(self.page.locator('#tax-calc-stale')).to_be_visible()
        self.assertEqual(self.page.locator('#tax-calc-result').inner_text(), original)
        # Modificare l'editor F4 non modifica lo scenario già aggiunto alla riga.
        self.item('SERVICE')
        self.page.locator('#tax-calc-tab').click()
        expect(self.page.locator('#tax-calc-line-' + line_id)).to_contain_text(self.case.items['GOOD']['id'])
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#tax-calc-stale')).to_be_visible()
        expect(self.page.locator('#tax-calc-price-' + line_id)).to_have_value('200')
        self.assertEqual(self.page.locator('#tax-calc-result').inner_text(), original)
        expect(self.page.locator('#tax-calc-comparison')).to_contain_text('122.00')
        self.assertEqual(self.mutations, posts, 'Edit, pin e reload non eseguono POST')
        self.run_calculation()
        expect(self.page.locator('#tax-calc-result')).to_contain_text('244.00')
        expect(self.page.locator('#tax-calc-comparison')).to_contain_text('122.00')
        self.assert_readonly_layout()

    def test_04_purchase_normal_reversal_nullable_and_declared_deductibility(self):
        from playwright.sync_api import expect
        self.begin('en', operation='PURCHASE')
        line_id, _ = self.append_scenario('1000')
        normal = self.run_calculation()['result']
        self.assertIsNone(normal['lines'][0]['deductibility'])
        self.case.assert_totals(normal, '1000.00', '220.00', '1220.00')
        control = self.page.locator('#tax-calc-deductible-' + line_id)
        expect(control).to_have_value('')
        control.fill('40')
        declared = self.run_calculation()['result']
        self.assertEqual(declared['lines'][0]['deductibility']['deductibleAmount'], '88.00')
        self.page.locator('#tax-calc-direction').select_option('REVERSAL')
        reversal = self.run_calculation()['result']
        self.case.assert_totals(reversal, '-1000.00', '-220.00', '-1220.00')
        self.assertEqual(reversal['lines'][0]['deductibility']['deductibleAmount'], '-88.00')
        self.assertEqual(reversal['lines'][0]['deductibility']['nonDeductibleAmount'], '-132.00')
        control.fill('')
        nullable = self.run_calculation()['result']
        self.assertIsNone(nullable['lines'][0]['deductibility'])
        request = [x for x in self.mutations if x['path'] == '/api/tax/calculations/simulate'][-1]['body']
        self.assertIsNone(request['lines'][0]['deductible_percentage'])

    def test_05_real_server_422_index_and_fiscal_trace_preserve_result(self):
        from playwright.sync_api import expect
        self.begin('it')
        self.append_scenario('100')
        self.run_calculation()
        previous_result = self.page.locator('#tax-calc-result').inner_text()
        # La fonte cambia davvero dopo l'acquisizione F4: nessun route.fulfill fittizio.
        rule = self.case.rules['GOOD', 'SALE']
        withdrawn = self.case.transition(rule, 'withdraw')
        self.assertEqual(withdrawn['versions'][0]['status'], 'WITHDRAWN')
        error = self.run_calculation(expected=422)
        self.assertEqual((error['code'], error['field'], error['outcome']),
                         ('tax_calculation_determination_failed', 'lines[0].fiscal_context', 'NO_MATCHING_RULE'))
        alert = self.page.locator('#tax-calculation-panel > div[role="alert"]')
        expect(alert).to_contain_text('lines[0].fiscal_context')
        alert.locator('summary').click()
        expect(alert.locator('details')).to_have_attribute('open', '')
        self.assertTrue(error['trace'])
        self.assertEqual(self.page.locator('#tax-calc-result').inner_text(), previous_result)

    def test_06_fresh_revocation_blocks_f5_post_and_f4_source_authority(self):
        from playwright.sync_api import expect
        actor, role, credentials = self.case.actor(SIMULATION_GRANTS)
        self.case.assign_companies(role, [self.case.company])
        # IT evita l'attesa amministrativa "Settings" dell'helper login EN.
        self.login('it', credentials=credentials)
        self.navigation('determination')
        self.fill_context()
        self.fill_facts()
        self.append_scenario('100')
        self.run_calculation()
        status, _ = self.case.root.request(self.case.scope('/api/links/role-permissions/' + role['id']),
                                           'PUT', {'ids': []})
        self.assertEqual(status, 204)
        status, readback = self.case.root.request(self.case.scope('/api/links/role-permissions/' + role['id']))
        self.assertEqual(status, 200, readback)
        self.assertEqual(readback['ids'], [])
        before = deepcopy(self.mutations)
        self.page.locator('#tax-calc-run').click()
        expect(self.page.locator('#tax-calculation-panel > div[role="alert"]')).to_be_visible()
        self.assertEqual(self.mutations, before, 'Fresh /session blocca il POST F5 con ruolo revocato')
        self.case.calculate(client=actor, expected=403)
        self.case.simulate(client=actor, expected=403)


def load_tests(loader, tests, pattern):
    # Importare gli helper browser/HTTP storici non duplica i casi scoperti.
    return loader.loadTestsFromTestCase(TaxCalculationBrowser)


if __name__ == '__main__':
    unittest.main()
