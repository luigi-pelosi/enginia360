"""Real Chromium journeys: mandatory profiles, recovery, grants and fiscal-root CF.

Requests use the existing real-container forwarding harness. The only injected
network fault drops a real, already-committed registration POST response; no API is fabricated.
"""
import unittest
import re
from urllib.parse import urlsplit


from browser_company_tax_proof import CompanyTaxBrowser as Harness
from test_company_tax_required_http import CompanyTaxRequiredHttp


class CompanyTaxRequiredBrowser(unittest.TestCase):
    http_case_class = CompanyTaxRequiredHttp
    http_case_name = 'test_required_initial_chain_rejections_are_atomic_no_rows'

    @classmethod
    def setUpClass(cls):
        CompanyTaxRequiredHttp.setUpClass()
        Harness.setUpClass.__func__(cls)
    tearDownClass = classmethod(Harness.tearDownClass.__func__)
    tearDown = Harness.tearDown
    login = Harness.login
    company_navigation = Harness.company_navigation
    open_company = Harness.open_company
    tab = Harness.tab
    select_country = Harness.select_country
    editor = Harness.editor
    def fill_registration(self, profile=True):
        from playwright.sync_api import expect
        # Every new registration has the same mandatory regime controls.
        expect(self.page.locator('#company-tax-include-profile')).to_have_count(0)
        self.page.locator('#company-tax-tax_identifier').fill(self.case.identifier())
        self.page.locator('#company-tax-registration-valid_from').fill(self.case.start)
        self.page.locator('#company-tax-profile-valid_from').fill(self.case.start)

    general_save = Harness.general_save
    window_geometry = Harness.window_geometry

    def setUp(self):
        Harness.setUp(self)

    def required_editor(self):
        from playwright.sync_api import expect
        dialog = self.page.locator('#company-tax-editor')
        expect(dialog).to_be_visible()
        for optional in ('include-registration', 'include-profile'):
            expect(dialog.locator('#company-tax-' + optional)).to_have_count(0)
        for field in ('tax_identifier', 'registration-valid_from', 'tax_regime_id', 'profile-valid_from'):
            expect(dialog.locator('#company-tax-' + field)).to_be_visible()
        expect(dialog.locator('#company-tax-tax_identifier')).to_have_attribute('required', '')
        expect(dialog.locator('#company-tax-tax_code')).to_be_visible()
        return dialog


    def fiscal_table_layout(self, locale):
        from playwright.sync_api import expect
        root = self.case.create(tax_code='Readonly CF')
        self.login(locale)
        self.open_company()
        self.tab()
        card = self.page.locator('[data-company-tax-id="' + root['id'] + '"]')
        expect(card).to_contain_text('Readonly CF')
        expect(card.locator('[id^="company-tax-update-"]')).to_have_count(0)
        expect(self.page.locator('#company-tax-tax_code')).to_have_count(0)
        dialog = self.page.locator('[data-slot="dialog-content"]').filter(has=self.page.locator('#company-tax-section'))
        self.assertGreater(dialog.bounding_box()['width'], 1000)
        table = self.page.locator('#company-tax-configurations')
        for index, field in enumerate(('tax_type_id', 'establishment_country_id', 'tax_code')):
            expect(table.locator('thead th').nth(index)).to_have_text(self.messages['companyTax'][field])
        expect(card.locator('td')).to_have_count(5)
        expect(card.locator('td').nth(2)).to_have_text('Readonly CF')
        details = self.page.locator('#company-tax-registrations-' + root['id'])
        expect(details).to_have_count(0)
        self.page.screenshot(path=str(self.fixture.EVIDENCE / ('configuration-list-' + locale + '.png')))
        self.page.locator('#company-tax-details-' + root['id']).click()
        expect(details).to_be_visible()
        expect(details.locator('thead th')).to_have_count(8)
        expect(details.locator('[id^="company-tax-activate-"]')).to_have_count(0)
        expect(details.locator('[id^="company-tax-register-"]')).to_have_count(0)
        self.page.reload(wait_until='networkidle')
        expect(details).to_be_visible()
        expect(self.page.locator('#company-tax-details-' + root['id'])).to_have_attribute('aria-expanded', 'true')
        dimensions = table.evaluate('e => ({content: e.parentElement.scrollWidth, available: e.parentElement.clientWidth})')
        self.assertLessEqual(dimensions['content'], dimensions['available'] + 1)
        self.page.screenshot(path=str(self.fixture.EVIDENCE / ('fiscal-table-' + locale + '.png')))
        self.tab(False)
        expect(dialog).to_have_css('width', '672px')
        self.assertLess(dialog.bounding_box()['width'], 800)
        self.tab()
        self.page.set_viewport_size({'width': 480, 'height': 900})
        expect(dialog).to_have_css('width', '448px')
        bounds = dialog.bounding_box()
        self.assertGreaterEqual(bounds['x'], 0)
        self.assertLessEqual(bounds['x'] + bounds['width'], 480)
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        self.assertEqual(self.mutations, [])

    def test_italian_wide_fiscal_table_and_readonly_cf(self):
        self.fiscal_table_layout('it')

    def test_english_wide_fiscal_table_and_readonly_cf(self):
        self.fiscal_table_layout('en')

    def row_actions(self, locale):
        from playwright.sync_api import expect
        root = self.case.create(tax_code='Row actions CF')
        self.login(locale)
        self.open_company()
        self.tab()
        table = self.page.locator('#company-tax-configurations')
        expect(self.page.locator('#company-tax-create')).to_have_count(0)
        expect(table.locator('tbody td[data-kind="actions"] #company-tax-activate-' + root['id'])).to_be_visible()
        expect(table.locator('tbody td[data-kind="actions"] #company-tax-register-' + root['id'])).to_be_visible()
        self.editor('activate', root)
        with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith('/' + root['id'] + '/activate')) as saved:
            self.page.locator('#company-tax-save').click()
        self.assertEqual(saved.value.status, 200)
        root = saved.value.json()
        self.assertEqual((root['status'], root['version']), ('ACTIVE', 2))
        self.assertEqual(self.case.read(root), root)
        expect(table.locator('#company-tax-activate-' + root['id'])).to_have_count(0)
        expect(table.locator('#company-tax-suspend-' + root['id'])).to_be_visible()
        expect(self.page.locator('#company-tax-editor')).to_have_count(0)
        self.editor('register', root)
        self.select_country('country_id', 'DE')
        self.fill_registration()
        self.page.locator('#company-tax-tax_identifier').fill(self.case.identifier('DE'))
        with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith('/' + root['id'] + '/registrations')) as saved:
            self.page.locator('#company-tax-save').click()
        self.assertEqual(saved.value.status, 201)
        updated = saved.value.json()
        self.assertEqual((updated['version'], len(updated['registrations'])), (3, 2))
        self.assertEqual(self.case.read(updated), updated)
        expect(table.get_by_role('group', name=self.messages['companyTax']['configurationActions'], exact=True)).to_have_count(1)
        expect(table.get_by_role('group', name=self.messages['companyTax']['registrationActions'], exact=True)).to_have_count(2)
        registrations = self.page.locator('#company-tax-registrations-' + root['id'])
        expect(registrations.locator('tbody tr')).to_have_count(2)
        expect(self.page.locator('[data-company-tax-id]')).to_have_count(1)
        self.page.reload(wait_until='networkidle')
        expect(registrations).to_be_visible()
        expect(registrations.locator('tbody tr')).to_have_count(2)
        self.page.screenshot(path=str(self.fixture.EVIDENCE / ('row-actions-' + locale + '.png')))

    def test_italian_configuration_commands_in_action_cell(self):
        self.row_actions('it')

    def test_english_configuration_commands_in_action_cell(self):
        self.row_actions('en')

    def registration_layout(self, locale):
        from playwright.sync_api import expect
        root = self.case.create(tax_code='Unchanged root CF')
        self.login(locale)
        self.open_company()
        self.tab()
        dialog = self.editor('register', root)
        expect(dialog.locator('h4')).to_have_text([self.messages['companyTax']['registration'], self.messages['companyTax']['initialProfile']])
        expect(dialog.locator('#company-tax-country_id')).to_contain_text(re.compile(r'^IT\s'))
        expect(dialog.locator('#company-tax-include-profile')).to_have_count(0)
        expect(dialog.locator('#company-tax-tax_regime_id')).to_be_visible()
        expect(dialog.locator('#company-tax-profile-valid_from')).to_have_attribute('required', '')
        self.select_country('country_id', 'DE')
        self.fill_registration()
        identifier = self.case.identifier('DE')
        dialog.locator('#company-tax-tax_identifier').fill(identifier)
        dialog.locator('#company-tax-notes').fill('Registration layout notes')
        # A pre-contract unchecked draft must forget its stale regime choice.
        self.page.evaluate("""() => {for(const key of Object.keys(sessionStorage)){if(!key.startsWith('company-tax:v1:'))continue;const state=JSON.parse(sessionStorage.getItem(key));if(state.editor?.action==='register'){state.editor.includeProfile=false;sessionStorage.setItem(key,JSON.stringify(state));}}}""")
        self.page.reload(wait_until='networkidle')
        expect(dialog.locator('#company-tax-include-profile')).to_have_count(0)
        expect(dialog.locator('#company-tax-tax_regime_id')).not_to_contain_text('ORDINARY')
        expect(dialog.locator('#company-tax-tax_identifier')).to_have_value(identifier)
        expect(dialog.locator('#company-tax-notes')).to_have_value('Registration layout notes')
        before = self.case.snapshot()
        dialog.locator('#company-tax-save').click()
        expect(dialog).to_be_visible()
        self.assertEqual(self.mutations, [], 'Recovered incomplete registration must not POST')
        self.assertEqual(self.case.snapshot(), before)
        self.page.locator('#company-tax-tax_regime_id').click()
        self.page.get_by_role('option', name=re.compile(r'^ORDINARY\s')).click()
        self.page.reload(wait_until='networkidle')
        expect(dialog.locator('#company-tax-tax_regime_id')).to_contain_text('ORDINARY')
        self.assertEqual(self.mutations, [], 'Refresh must not replay a registration')
        for left, right in [('country_id', 'registration_type'), ('tax_identifier', 'registration-valid_from'), ('tax_regime_id', 'profile-valid_from')]:
            first = dialog.locator('#company-tax-' + left).bounding_box()
            second = dialog.locator('#company-tax-' + right).bounding_box()
            self.assertGreater(second['x'], first['x'])
            self.assertLess(abs(first['y'] - second['y']), 2)
        last = dialog.locator('#company-tax-profile-valid_to').bounding_box()
        notes = dialog.locator('#company-tax-notes').bounding_box()
        self.assertLess(last['y'] + last['height'], notes['y'])
        self.assertLess(notes['y'] + notes['height'], dialog.locator('#company-tax-save').bounding_box()['y'])
        expect(dialog.locator('#company-tax-tax_code')).to_have_count(0)
        self.page.screenshot(path=str(self.fixture.EVIDENCE / ('registration-layout-' + locale + '.png')))
        with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path.endswith('/' + root['id'] + '/registrations')) as saved:
            dialog.locator('#company-tax-save').click()
        self.assertEqual(saved.value.status, 201)
        updated = saved.value.json()
        self.assertEqual(updated['version'], root['version'] + 1)
        self.assertEqual(updated['tax_code'], root['tax_code'])
        added = next(row for row in updated['registrations'] if row['tax_identifier'] == identifier)
        self.assertEqual((len(added['profiles']), added['notes']), (1, 'Registration layout notes'))
        self.assertEqual(self.case.read(updated), updated)

    def test_register_permission_visibility_and_fresh_assign_regime_revocation(self):
        import json
        from playwright.sync_api import expect
        root = self.case.create()
        grants = ['companies.read', 'companies.update', 'company-tax-configurations.read', 'company-tax-configurations.register']
        _, role, credentials = self.case.actor(grants)
        self.case.assign_companies(role, [self.case.company])
        self.login('it', credentials)
        # Il ruolo limitato accede alle aziende, non al menu Impostazioni.
        self.page.get_by_role('combobox', name='Lingua', exact=True).click()
        self.page.get_by_role('option', name='English', exact=True).click()
        expect(self.page.locator('nav')).to_contain_text('Companies')
        self.messages = json.loads((self.fixture.ROOT / 'frontend/messages/en.json').read_text())
        self.open_company()
        self.tab()
        expect(self.page.locator('#company-tax-register-' + root['id'])).to_have_count(0)
        # Grant the second action on the SAME role, then revoke it after opening.
        permissions = []
        for page in (1, 2):
            status, body = self.case.root.request(self.case.scope('/api/data/permissions?pageSize=100&page=' + str(page)))
            self.assertEqual(status, 200, body)
            permissions.extend(body['items'])
        original = [p['id'] for p in permissions if p['code'] in grants]
        complete = original + [p['id'] for p in permissions if p['code'] == 'company-tax-configurations.assign_regime']
        self.assertEqual((len(original), len(complete)), (4, 5))
        path = self.case.scope('/api/links/role-permissions/' + role['id'])
        self.assertEqual(self.case.root.request(path, 'PUT', {'ids': complete})[0], 204)
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#company-tax-register-' + root['id'])).to_be_visible()
        self.editor('register', root)
        self.select_country('country_id', 'DE')
        self.fill_registration()
        self.page.locator('#company-tax-tax_identifier').fill(self.case.identifier('DE'))
        self.assertEqual(self.case.root.request(path, 'PUT', {'ids': original})[0], 204)
        before = self.case.snapshot()
        self.page.locator('#company-tax-save').click()
        expect(self.page.locator('#company-tax-editor [role="alert"]')).to_be_visible()
        self.assertEqual(self.mutations, [], 'Fresh authority must prevent the registration POST')
        self.assertEqual(self.case.snapshot(), before)
        self.assertEqual(self.case.read(root), root)

    def test_registration_committed_response_drop_preserves_marker_without_replay(self):
        from playwright.sync_api import expect
        root = self.case.create()
        self.login('en')
        self.open_company()
        self.tab()
        self.editor('register', root)
        self.select_country('country_id', 'DE')
        self.fill_registration()
        self.page.locator('#company-tax-tax_identifier').fill(self.case.identifier('DE'))
        self.drop_path = '/api/tax/company-configurations/' + root['id'] + '/registrations'
        self.page.locator('#company-tax-save').click()
        expect(self.page.locator('#company-tax-review')).to_be_visible()
        pending = self.page.evaluate("Object.values(sessionStorage).map(v=>{try{return JSON.parse(v)}catch{return null}}).find(s=>s?.pending?.path?.endsWith('/registrations'))?.pending")
        self.assertIsNotNone(pending)
        committed = self.case.read(root)
        self.assertEqual((committed['version'], len(committed['registrations'])), (root['version'] + 1, 2))
        self.assertTrue(all(row['profiles'] for row in committed['registrations']))
        self.page.reload(wait_until='networkidle')
        expect(self.page.locator('#company-tax-review')).to_be_visible()
        recovered = self.page.evaluate("Object.values(sessionStorage).map(v=>{try{return JSON.parse(v)}catch{return null}}).find(s=>s?.pending?.path?.endsWith('/registrations'))?.pending")
        self.assertEqual(recovered, pending, 'Frozen submitted marker must not be normalized')
        self.page.locator('#company-tax-review').click()
        self.page.locator('#company-tax-acknowledge').click()
        expect(self.page.locator('#company-tax-review')).to_have_count(0)
        self.assertEqual(self.case.read(root), committed)
        self.assertEqual(len(self.mutations), 1, 'No automatic replay after uncertain registration')
        self.assertEqual(self.mutations[0]['body']['expectedVersion'], root['version'])
        self.assertEqual(len(self.mutations[0]['body']['profiles']), 1)

    def test_italian_new_registration_consistent_layout_and_regime(self):
        self.registration_layout('it')

    def test_english_new_registration_consistent_layout_and_regime(self):
        self.registration_layout('en')

    def concise_layout(self, locale):
        from playwright.sync_api import expect
        self.login(locale)
        self.open_company()
        self.tab()
        self.editor()
        dialog = self.required_editor()
        titles = {'it': ['Registrazione iniziale', 'Regime iniziale'],
                  'en': ['Initial registration', 'Initial regime']}
        for field in ('establishment_country_id', 'country_id'):
            expect(dialog.locator('#company-tax-' + field)).to_contain_text(re.compile(r'^IT\s'))
        expect(dialog.locator('h4')).to_have_text(titles[locale])
        cf = dialog.locator('#company-tax-tax_code').bounding_box()
        until = dialog.locator('#company-tax-registration-valid_to').bounding_box()
        notes = dialog.locator('#company-tax-notes').bounding_box()
        self.assertGreater(cf['x'], until['x'])
        self.assertLess(abs(cf['y'] - until['y']), 2)
        self.assertLess(cf['y'] + cf['height'], notes['y'])
        regime_end = dialog.locator('#company-tax-profile-valid_to').bounding_box()
        self.assertLess(regime_end['y'] + regime_end['height'], notes['y'])
        self.assertLess(notes['y'] + notes['height'], dialog.locator('#company-tax-save').bounding_box()['y'])
        self.page.screenshot(path=str(self.fixture.EVIDENCE / ('layout-' + locale + '.png')))
        self.select_country('establishment_country_id', 'FR')
        self.select_country('country_id', 'DE')
        self.page.reload(wait_until='networkidle')
        expect(dialog.locator('#company-tax-establishment_country_id')).to_contain_text(re.compile(r'^FR\s'))
        expect(dialog.locator('#company-tax-country_id')).to_contain_text(re.compile(r'^DE\s'))
        self.assertEqual(self.mutations, [])

    def test_italian_concise_titles_and_cf_next_to_registration_end(self):
        self.concise_layout('it')

    def test_english_concise_titles_and_cf_next_to_registration_end(self):
        self.concise_layout('en')

    def journey(self, locale):
        from playwright.sync_api import expect
        self.login(locale)
        self.company_navigation()
        self.page.locator('.page-heading').get_by_role('button', name=self.messages['app']['new'], exact=True).click()
        name = 'Required staged ' + self.case.code
        self.page.locator('#field-name').fill(name)
        for field in ('tax_code', 'vat_number'):
            expect(self.page.locator('#field-' + field)).to_have_count(0)
        self.tab()
        dialog = self.editor()
        self.window_geometry(dialog)
        self.required_editor()
        self.select_country()
        self.page.locator('#company-tax-tax_code').fill('  Staged CF é漢  ')
        # Recover an old incomplete draft whose former opt-in flags were false.
        self.page.evaluate("""() => {for(const key of Object.keys(sessionStorage)){if(!key.startsWith('company-tax:v1:'))continue;const state=JSON.parse(sessionStorage.getItem(key));if(state.editor?.action==='create'){state.editor.includeRegistration=false;state.editor.includeProfile=false;sessionStorage.setItem(key,JSON.stringify(state));}}}""")
        self.page.reload(wait_until='networkidle')
        self.required_editor()
        expect(self.page.locator('#company-tax-tax_code')).to_have_value('  Staged CF é漢  ')
        # An old checkbox=false draft may not stage an empty chain after recovery.
        self.page.locator('#company-tax-save').click()
        expect(self.page.get_by_test_id('company-tax-staged')).to_have_count(0)
        self.assertEqual(self.mutations, [])
        self.fill_registration(True)
        # La bozza legacy non aveva scelto un regime: completarlo esplicitamente.
        self.page.locator('#company-tax-tax_regime_id').click()
        self.page.get_by_role('option', name=re.compile(r'^ORDINARY\s')).click()
        identifier = self.page.locator('#company-tax-tax_identifier').input_value()
        self.page.locator('#company-tax-save').click()
        expect(self.page.get_by_test_id('company-tax-staged')).to_have_count(1)
        self.assertEqual(self.mutations, [], 'Staging is local until the first Company POST')
        self.page.reload(wait_until='networkidle')
        expect(self.page.get_by_test_id('company-tax-staged')).to_have_count(1)
        expect(self.page.get_by_test_id('company-tax-staged')).to_contain_text(identifier)
        expect(self.page.get_by_test_id('company-tax-staged')).to_contain_text('Staged CF é漢')
        self.page.locator('#company-tax-stage-edit-0').click()
        self.required_editor()
        expect(self.page.locator('#company-tax-tax_code')).to_have_value('Staged CF é漢')
        expect(self.page.locator('#company-tax-tax_identifier')).to_have_value(identifier)
        expect(self.page.locator('#company-tax-profile-valid_from')).to_have_value(self.case.start)
        self.page.locator('#company-tax-save').click()
        expect(self.page.locator('#company-tax-editor')).to_have_count(0)
        self.assertEqual(self.mutations, [])
        self.tab(False)
        expect(self.page.locator('#field-name')).to_have_value(name)
        expect(self.page.locator('#field-tax_code')).to_have_count(0)
        created = self.general_save('POST', 201)
        self.assertNotIn('tax_code', created)
        self.assertEqual(len(self.mutations), 1)
        body = self.mutations[0]['body']
        self.assertNotIn('tax_code', body['values'])
        staged = body['taxConfigurations']
        self.assertEqual((len(staged), len(staged[0]['registrations']), len(staged[0]['registrations'][0]['profiles'])), (1, 1, 1))
        self.assertEqual(staged[0]['values']['tax_code'], 'Staged CF é漢')
        roots = self.case.req(self.case.list_route(created))['items']
        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertEqual((root['tax_code'], root['status'], root['version']), ('Staged CF é漢', 'DRAFT', 1))
        self.assertEqual(root['registrations'][0]['tax_identifier'], identifier)
        self.open_company(created)
        expect(self.page.locator('#field-tax_code')).to_have_count(0)
        self.tab()
        card = self.page.locator('[data-company-tax-id="' + root['id'] + '"]')
        expect(card).to_contain_text('Staged CF é漢')
        expect(card.locator('[id^="company-tax-update-"]')).to_have_count(0)
        expect(self.page.locator('#company-tax-tax_code')).to_have_count(0)
        self.page.reload(wait_until='networkidle')
        expect(card).to_contain_text('Staged CF é漢')
        self.assertEqual(self.case.read(root), root)
        self.assertFalse(any(request['method'] == 'PUT' for request in self.mutations))
        self.tab(False)
        expect(self.page.locator('#field-tax_code')).to_have_count(0)
        self.assertNotIn('tax_code', self.case.company_read(created))

    def test_italian_required_chain_cf_staging_refresh_edit_and_no_replay(self):
        self.journey('it')

    def test_english_required_chain_cf_staging_refresh_edit_and_no_replay(self):
        self.journey('en')
