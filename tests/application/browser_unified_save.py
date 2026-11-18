"""Unico Salva e bulk multilivello: browser nativo e API/DB reali nella copia isolata."""
import json
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import urlsplit

from unified_save_support import Case, ORIGIN, PORTS, root_client, sql
from playwright.sync_api import sync_playwright, expect

EVIDENCE = Path('/root/.hermes/cache/scratch/enginia360-unified-save/browser')
EVIDENCE.mkdir(parents=True, exist_ok=True)


class UnifiedSaveBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.credentials = root_client()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(
            executable_path='/root/.hermes/tools/chromium-1208/chrome-linux64/chrome',
            headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.case = Case(self.root)
        self.context = self.browser.new_context(locale='it-IT', viewport={'width': 1440, 'height': 1000})
        def forward(route):
            url = urlsplit(route.request.url)
            if url.netloc != urlsplit(ORIGIN).netloc:
                raise RuntimeError('Host inatteso nel test isolato')
            component = 'backend' if url.path.startswith('/api/') else 'frontend'
            response = route.fetch(url=f'http://127.0.0.1:{PORTS[component]}' + url.path + ('?' + url.query if url.query else ''),
                                   headers={**route.request.all_headers(), 'host': url.netloc})
            route.fulfill(response=response)
        self.forward = forward
        self.context.route(ORIGIN + '/**', forward)
        self.page = self.context.new_page()
        self.errors = []
        self.mutations = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        def track(request):
            path = urlsplit(request.url).path
            if request.method in ('POST','PUT','DELETE') and path.startswith(('/api/data/','/api/links/')):
                self.mutations.append({'path': path, 'method': request.method, 'body': request.post_data_json})
        self.page.on('request', track)

    def tearDown(self):
        try:
            self.page.screenshot(path=str(EVIDENCE / (self._testMethodName + '.png')), full_page=True)
            self.assertEqual(self.errors, [])
        finally:
            self.context.unroute_all(behavior='wait')
            self.context.close()
            self.case.close()

    def login(self, credentials=None, tenant_code=''):
        credentials = credentials or self.credentials
        self.page.goto(ORIGIN, wait_until='networkidle')
        self.page.locator('#username').fill(credentials['username'])
        self.page.locator('#password').fill(credentials['password'])
        if tenant_code:
            self.page.locator('#tenant-code').fill(tenant_code)
        self.page.get_by_role('button', name='Accedi', exact=True).click()
        expect(self.page.locator('[data-slot=sidebar-wrapper]')).to_be_visible()
        if not tenant_code:
            self.page.locator('#tenant-select').click()
            self.page.get_by_role('option', name='Verifica salvataggio', exact=True).click()

    def open_role(self, role, readonly=False):
        self.page.locator('nav').get_by_role('button', name='Ruoli', exact=True).click()
        row = self.page.locator('tbody tr').filter(has_text=role['code'])
        row.get_by_role('button', name=re.compile('^(Modifica|Dettagli) ')).click()
        return self.page.get_by_role('dialog')

    def permission_section(self, dialog):
        section = dialog.locator('section').filter(has=self.page.get_by_role('heading', name='Permessi del ruolo', exact=True))
        expect(section.locator('[data-permission-domain]')).to_have_count(3)
        return section

    def checkbox(self, scope, selector):
        node = scope.locator(selector)
        expect(node).to_have_count(1)
        return node if node.get_attribute('role') == 'checkbox' else node.get_by_role('checkbox')

    def selected_ids(self, role):
        status, data = self.root.request(self.case.link('role-permissions', role['id']))
        self.assertEqual(status, 200)
        return set(data['ids'])

    def test_one_save_commits_role_profile_and_permission_draft_with_one_request(self):
        role = self.case.role(name='Ruolo unico')
        self.login()
        dialog = self.open_role(role)
        section = self.permission_section(dialog)
        expect(dialog.get_by_role('button', name=re.compile('^Salva'))).to_have_count(1)
        dialog.locator('#field-name').fill('Ruolo aggiornato insieme')
        section.get_by_role('textbox').fill('companies.read')
        leaf = section.locator('[data-permission-code="companies.read"]').get_by_role('checkbox')
        expect(leaf).to_be_enabled()
        leaf.check()
        self.assertEqual(self.mutations, [], 'La bozza non deve emettere richieste di scrittura')
        with self.page.expect_response(lambda response: urlsplit(response.url).path.endswith('/save') and response.request.method == 'PUT') as saved:
            dialog.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 200)
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(self.mutations[0]['path'], '/api/data/roles/' + role['id'] + '/save')
        self.assertEqual(self.mutations[0]['body']['values'], {'name': 'Ruolo aggiornato insieme'})
        self.assertEqual(self.selected_ids(role), {self.case.catalog['companies.read']})
        expect(self.page.locator('tbody')).to_contain_text('Ruolo aggiornato insieme')

    def test_bulk_global_domain_and_resource_have_tristate_and_full_branch_scope(self):
        role = self.case.role(name='Ruolo bulk')
        self.login()
        dialog = self.open_role(role)
        section = self.permission_section(dialog)
        all_box = self.checkbox(section, '[data-permission-selection="all"]')
        expect(all_box).to_be_enabled()
        expect(all_box).not_to_be_checked()
        warehouse = section.locator('[data-permission-domain="warehouse"]')
        domain_box = self.checkbox(section, '[data-permission-domain-checkbox="warehouse"]')
        domain_box.check()
        self.assertIsNone(warehouse.get_attribute('open'), 'Il checkbox non deve aprire o chiudere il ramo')
        expect(domain_box).to_be_checked()
        expect(all_box).to_have_attribute('aria-checked', 'mixed')
        expect(all_box.locator('svg.lucide-minus')).to_be_visible()
        warehouse.locator(':scope > summary').get_by_text('Magazzino', exact=True).click()
        resource_box = self.checkbox(section, '[data-permission-resource-checkbox="warehouses"]')
        expect(resource_box).to_be_checked()
        resource_box.uncheck()
        expect(domain_box).to_have_attribute('aria-checked', 'mixed')
        expect(warehouse.locator(':scope > summary')).to_contain_text('8/12')
        all_box.check()
        expect(all_box).to_be_checked()
        section.get_by_role('textbox').fill('companies.read')
        expect(section.locator('[data-permission-code]')).to_have_count(1)
        expect(all_box).to_be_checked()
        org_box = self.checkbox(section, '[data-permission-domain-checkbox="organization"]')
        org_box.uncheck()
        expect(all_box).to_have_attribute('aria-checked', 'mixed')
        expect(section.locator('[data-permission-domain="organization"] > summary')).to_contain_text('0/8')
        self.assertEqual(self.mutations, [])
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        expected = {value for code,value in self.case.catalog.items() if code.split('.')[0] not in ('companies','sites')}
        self.assertEqual(self.selected_ids(role), expected)
        self.assertEqual(len(self.mutations), 1)
        self.assertNotIn('values', self.mutations[0]['body'])

    def test_cancel_discards_profile_and_hidden_permission_drafts(self):
        role = self.case.role(['companies.read'], name='Ruolo da conservare')
        self.login()
        dialog = self.open_role(role)
        section = self.permission_section(dialog)
        dialog.locator('#field-name').fill('Non salvato')
        self.checkbox(section, '[data-permission-selection="all"]').check()
        dialog.get_by_role('button', name='Annulla', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(self.mutations, [])
        self.assertEqual(self.selected_ids(role), {self.case.catalog['companies.read']})
        dialog = self.open_role(role)
        expect(dialog.locator('#field-name')).to_have_value('Ruolo da conservare')
        section = self.permission_section(dialog)
        expect(self.checkbox(section, '[data-permission-selection="all"]')).to_have_attribute('aria-checked','mixed')

    def test_group_profile_members_and_roles_share_one_save(self):
        first, second = self.case.user('Primo'), self.case.user('Secondo')
        old_role, new_role = self.case.role(name='Vecchio ruolo'), self.case.role(name='Nuovo ruolo')
        group = self.case.create('groups', {'code': 'browser-group', 'name': 'Gruppo unico'})
        self.root.request(self.case.link('group-users', group['id']), 'PUT', {'ids': [first['id']]})
        self.root.request(self.case.link('group-roles', group['id']), 'PUT', {'ids': [old_role['id']]})
        self.login()
        self.page.locator('nav').get_by_role('button', name='Gruppi', exact=True).click()
        self.page.get_by_role('button', name='Modifica Gruppo unico', exact=True).click()
        dialog = self.page.get_by_role('dialog')
        expect(dialog.get_by_role('button', name=re.compile('^Salva'))).to_have_count(1)
        dialog.locator('#field-name').fill('Gruppo aggiornato')
        for heading, old, new in [('Utenti del gruppo','Primo Verifica','Secondo Verifica'),('Ruoli del gruppo','Vecchio ruolo','Nuovo ruolo')]:
            section = dialog.locator('section').filter(has=self.page.get_by_role('heading', name=heading, exact=True))
            expect(section.get_by_role('checkbox', name=old, exact=True)).to_be_checked()
            section.get_by_role('checkbox', name=old, exact=True).uncheck()
            section.get_by_role('checkbox', name=new, exact=True).check()
        self.assertEqual(self.mutations, [])
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(set(self.mutations[0]['body']['links']), {'group-users','group-roles'})
        self.assertEqual(set(self.root.request(self.case.link('group-users', group['id']))[1]['ids']), {second['id']})
        self.assertEqual(set(self.root.request(self.case.link('group-roles', group['id']))[1]['ids']), {new_role['id']})

    def test_new_group_can_stage_associations_before_atomic_creation(self):
        user, role = self.case.user('Primo'), self.case.role(name='Ruolo iniziale')
        self.login()
        self.page.locator('nav').get_by_role('button', name='Gruppi', exact=True).click()
        self.page.get_by_role('button', name='Nuovo', exact=True).first.click()
        dialog = self.page.get_by_role('dialog')
        dialog.locator('#field-code').fill('new-combined')
        dialog.locator('#field-name').fill('Nuovo con associazioni')
        for heading,name in [('Utenti del gruppo','Primo Verifica'),('Ruoli del gruppo','Ruolo iniziale')]:
            section = dialog.locator('section').filter(has=self.page.get_by_role('heading', name=heading, exact=True))
            expect(section.get_by_role('checkbox', name=name, exact=True)).to_be_enabled()
            section.get_by_role('checkbox', name=name, exact=True).check()
        self.assertEqual(self.mutations, [])
        with self.page.expect_response(lambda response: urlsplit(response.url).path == '/api/data/groups/save' and response.request.method == 'POST') as saved:
            dialog.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 201)
        group = saved.value.json()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(set(self.root.request(self.case.link('group-users', group['id']))[1]['ids']), {user['id']})
        self.assertEqual(set(self.root.request(self.case.link('group-roles', group['id']))[1]['ids']), {role['id']})

    def test_assignment_only_actor_gets_one_save_without_profile_mutation(self):
        role = self.case.role(name='Ruolo solo associazioni')
        _, _, _, credentials = self.case.actor(['roles.read','permissions.read','roles.assign_permissions'])
        self.login(credentials, self.case.tenant['code'])
        dialog = self.open_role(role, readonly=True)
        expect(dialog.locator('#field-name')).to_be_disabled()
        section = self.permission_section(dialog)
        expect(dialog.get_by_role('button', name='Salva', exact=True)).to_have_count(1)
        self.checkbox(section, '[data-permission-selection="all"]').check()
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 1)
        self.assertNotIn('values', self.mutations[0]['body'])
        self.assertEqual(self.selected_ids(role), set(self.case.catalog.values()))

    def test_failed_save_retains_draft_and_retry_commits_once(self):
        role = self.case.role(name='Ruolo recuperabile')
        self.login()
        dialog = self.open_role(role)
        section = self.permission_section(dialog)
        dialog.locator('#field-name').fill('Ruolo recuperato')
        self.checkbox(section, '[data-permission-selection="all"]').check()
        sql("CREATE FUNCTION foundation.browser_unified_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.resource='role-permissions' AND NEW.record_id='{role['id']}'::uuid THEN RAISE EXCEPTION 'Fixture browser rejection'; END IF; RETURN NEW; END $$; "
            "CREATE TRIGGER browser_unified_reject BEFORE INSERT ON foundation.audit_event FOR EACH ROW EXECUTE FUNCTION foundation.browser_unified_reject();")
        try:
            with self.page.expect_response(lambda response: urlsplit(response.url).path.endswith('/save') and response.request.method == 'PUT') as rejected:
                dialog.get_by_role('button', name='Salva', exact=True).click()
            self.assertEqual(rejected.value.status, 500)
            expect(dialog).to_be_visible()
            expect(dialog.locator('[role=alert]')).to_be_visible()
            expect(dialog.locator('#field-name')).to_have_value('Ruolo recuperato')
            expect(self.checkbox(section, '[data-permission-selection="all"]')).to_be_checked()
            self.assertEqual(self.selected_ids(role), set())
            name = sql(f"SELECT name FROM foundation.role WHERE id='{role['id']}'").stdout.strip()
            self.assertEqual(name, 'Ruolo recuperabile')
        finally:
            sql('DROP TRIGGER browser_unified_reject ON foundation.audit_event; DROP FUNCTION foundation.browser_unified_reject();')
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 2)
        self.assertEqual(self.selected_ids(role), set(self.case.catalog.values()))

    def test_user_profile_and_role_assignment_share_one_save(self):
        user = self.case.user('Utente')
        role = self.case.role(name='Ruolo utente')
        self.login()
        self.page.locator('nav').get_by_role('button', name='Utenti', exact=True).click()
        row = self.page.locator('tbody tr').filter(has_text=user['username'])
        row.get_by_role('button', name='Modifica Utente Verifica', exact=True).click()
        dialog = self.page.get_by_role('dialog')
        section = dialog.locator('section').filter(has=self.page.get_by_role('heading', name='Ruoli utente', exact=True))
        expect(section.get_by_role('checkbox', name='Ruolo utente', exact=True)).to_be_enabled()
        expect(dialog.get_by_role('button', name=re.compile('^Salva'))).to_have_count(1)
        dialog.locator('#field-first_name').fill('Utente aggiornato')
        section.get_by_role('checkbox', name='Ruolo utente', exact=True).check()
        self.assertEqual(self.mutations, [])
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(self.mutations[0]['body']['values'], {'first_name': 'Utente aggiornato'})
        self.assertEqual(set(self.root.request(self.case.link('user-roles', user['id']))[1]['ids']), {role['id']})
        expect(self.page.locator('tbody')).to_contain_text('Utente aggiornato')

    def test_postcommit_session_revocation_returns_to_login_without_retry_or_false_save_error(self):
        _, user, _, credentials = self.case.actor(['users.read','users.update','roles.read'])
        self.login(credentials, self.case.tenant['code'])
        self.page.locator('nav').get_by_role('button', name='Utenti', exact=True).click()
        row = self.page.locator('tbody tr').filter(has_text=user['username'])
        row.get_by_role('button', name='Modifica Operatore Verifica', exact=True).click()
        dialog = self.page.get_by_role('dialog')
        new_username = user['username'] + '-saved'
        dialog.locator('#field-username').fill(new_username)
        with self.page.expect_response(lambda response: urlsplit(response.url).path.endswith('/save') and response.request.method == 'PUT') as saved:
            dialog.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 200)
        expect(self.page.locator('#username')).to_be_visible()
        expect(self.page.get_by_role('heading', name='Accedi', exact=True)).to_be_visible()
        self.assertEqual(self.page.locator('[data-slot=alert]').count(), 0)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(sql(f"SELECT username FROM foundation.\"user\" WHERE id='{user['id']}'").stdout.strip(), new_username)

    def test_readonly_picker_and_english_bulk_controls_preserve_authorities(self):
        role = self.case.role(['companies.read'], name='Ruolo consultabile')
        _, _, _, credentials = self.case.actor(['roles.read','permissions.read'])
        self.login(credentials, self.case.tenant['code'])
        dialog = self.open_role(role, readonly=True)
        section = self.permission_section(dialog)
        expect(self.checkbox(section, '[data-permission-selection="all"]')).to_be_disabled()
        self.assertEqual(dialog.get_by_role('button', name='Salva', exact=True).count(), 0)
        dialog.get_by_role('button', name='Annulla', exact=True).click()
        self.page.get_by_role('combobox', name='Lingua', exact=True).click()
        self.page.get_by_role('option', name='English', exact=True).click()
        expect(self.page.locator('html')).to_have_attribute('lang','en')
        self.page.locator('nav').get_by_role('button', name='Roles', exact=True).click()
        row = self.page.locator('tbody tr').filter(has_text=role['code'])
        row.get_by_role('button', name=re.compile('^Details ')).click()
        section = self.page.get_by_role('dialog').locator('section')
        expect(section.get_by_role('checkbox', name='Select all', exact=True)).to_be_disabled()
        self.page.set_viewport_size({'width':390,'height':844})
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))


if __name__ == '__main__':
    unittest.main(defaultTest='UnifiedSaveBrowserTests', argv=[sys.argv[0], *sys.argv[1:]], verbosity=2)
