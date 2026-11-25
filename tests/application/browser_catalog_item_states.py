"""Browser reale: tre stati, creazione e conferma irreversibile al Salva."""
from urllib.parse import urlsplit
from browser_catalog_items_proof import CatalogItemsBrowser, control

BROWSER_CASES = ('test_new_item_defaults_active_and_excludes_archive',
                 'test_already_active_edit_saves_without_confirmation',
                 'test_previously_activated_suspended_item_reactivates_without_confirmation',
                 'test_incomplete_existing_suspended_item_uses_same_required_fields',
                 'test_suspended_new_item_and_bilingual_labels',
                 'test_archive_cancel_preserves_draft_and_confirm_commits_once')


class CatalogItemStateBrowser(CatalogItemsBrowser):
    def confirm_active_save(self, method='PUT'):
        from playwright.sync_api import expect
        with self.page.expect_response(lambda response: response.request.method == method and urlsplit(response.url).path.startswith('/api/catalog/items')) as saved:
            control(self.page.get_by_test_id('catalog-item-activation-confirm'), 'item-activation-confirm').click()
        self.assertEqual(saved.value.status, 201 if method == 'POST' else 200, saved.value.text())
        result = saved.value.json()
        expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
        return result

    def choose_status(self, label):
        self.field('status').click()
        self.page.get_by_role('option', name=label, exact=True).click()

    def new_form(self, name, kind=None):
        control(self.page, 'catalog-item-new').click()
        self.field('name').fill(name)
        self.choose('type_id', kind or self.case.good)
        self.choose('category_id', self.case.category)
        self.choose('base_uom_id', self.case.base)

    def test_new_item_defaults_active_and_excludes_archive(self):
        from playwright.sync_api import expect
        self.case.manual()
        self.login('it')
        self.navigate()
        self.new_form('Nuovo articolo attivo')
        self.field('code').fill('ACTIVECONFIRM')
        expect(self.field('status')).to_contain_text('Attivo')
        self.field('status').click()
        expect(self.page.get_by_role('option', name='Attivo', exact=True)).to_be_visible()
        expect(self.page.get_by_role('option', name='Sospeso', exact=True)).to_be_visible()
        expect(self.page.get_by_role('option', name='Bozza', exact=True)).to_have_count(0)
        expect(self.page.get_by_role('option', name='Archiviato', exact=True)).to_have_count(0)
        self.page.keyboard.press('Escape')
        before = len(self.mutations)
        control(self.dialog(), 'item-save').click()
        confirmation = self.page.get_by_test_id('catalog-item-activation-confirm')
        expect(confirmation).to_contain_text(self.messages['catalogItems']['confirmActivate'])
        self.assertEqual(len(self.mutations), before)
        control(confirmation, 'item-activation-cancel').click()
        expect(confirmation).to_have_count(0)
        expect(self.field('name')).to_have_value('Nuovo articolo attivo')
        expect(self.field('code')).to_have_value('ACTIVECONFIRM')
        expect(self.field('base_uom_id')).to_be_enabled()
        self.assertEqual(len(self.mutations), before)
        control(self.dialog(), 'item-save').click()
        row = self.confirm_active_save('POST')
        self.assertEqual(len(self.mutations), before + 1)
        self.assertEqual(row['status'], 'ACTIVE')
        self.assertIsNotNone(row['activated_at'])
        self.case.full(row)
        self.open(row)
        expect(self.field('code')).to_be_disabled()
        expect(self.field('base_uom_id')).to_be_disabled()

    def test_already_active_edit_saves_without_confirmation(self):
        from playwright.sync_api import expect
        row = self.case.item()
        self.login('it')
        self.navigate()
        self.open(row)
        self.field('name').fill('Attivo modificato senza conferma')
        before = len(self.mutations)
        result = self.save_main().json()
        expect(self.page.get_by_test_id('catalog-item-activation-confirm')).to_have_count(0)
        self.assertEqual(result['name'], 'Attivo modificato senza conferma')
        self.assertEqual(result['status'], 'ACTIVE')
        self.assertEqual(result['activated_at'], row['activated_at'])
        self.assertEqual(result['version'], row['version'] + 1)
        self.assertEqual(len(self.mutations), before + 1)
        self.case.full(result)

    def test_previously_activated_suspended_item_reactivates_without_confirmation(self):
        from playwright.sync_api import expect
        row = self.case.item()
        activated = row['activated_at']
        self.assertIsNotNone(activated)
        row = self.case.status(row, 'SUSPENDED')
        self.login('it')
        self.navigate()
        self.open(row)
        expect(self.field('code')).to_be_disabled()
        expect(self.field('base_uom_id')).to_be_disabled()
        self.choose_status('Attivo')
        before = len(self.mutations)
        result = self.save_main().json()
        expect(self.page.get_by_test_id('catalog-item-activation-confirm')).to_have_count(0)
        self.assertEqual(result['status'], 'ACTIVE')
        self.assertEqual(result['activated_at'], activated)
        self.assertEqual(result['code'], row['code'])
        self.assertEqual(result['base_uom_id'], row['base_uom_id'])
        self.assertEqual(result['version'], row['version'] + 1)
        self.assertEqual(len(self.mutations), before + 1)
        self.case.full(result)

    def test_suspended_new_item_and_bilingual_labels(self):
        from playwright.sync_api import expect
        self.login('en')
        self.navigate()
        self.new_form('New suspended service', self.case.service)
        expect(self.field('status')).to_contain_text('Active')
        self.choose_status('Suspended')
        for field in ('category-id', 'base-uom'):
            expect(self.dialog().locator('label[for="item-' + field + '"]')).to_contain_text('*')
        row = self.save_main('POST', 201).json()
        self.assertEqual(row['status'], 'SUSPENDED')
        self.assertEqual(row['kind'], 'SERVICE')
        self.assertIsNone(row['activated_at'])
        self.case.full(row)
        self.open(row)
        expect(self.field('status')).to_contain_text('Suspended')
        self.choose_status('Active')
        before = len(self.mutations)
        control(self.dialog(), 'item-save').click()
        confirmation = self.page.get_by_test_id('catalog-item-activation-confirm')
        expect(confirmation).to_contain_text(self.messages['catalogItems']['confirmActivate'])
        self.assertEqual(len(self.mutations), before)
        control(confirmation, 'item-activation-cancel').click()
        self.assertEqual(self.case.req('items', row['id']), row)
        control(self.dialog(), 'item-save').click()
        activated = self.confirm_active_save()
        self.assertEqual(activated['status'], 'ACTIVE')
        self.assertIsNotNone(activated['activated_at'])
        self.assertEqual(len(self.mutations), before + 1)
        self.case.full(activated)

    def test_incomplete_existing_suspended_item_uses_same_required_fields(self):
        from playwright.sync_api import expect
        from catalog_items_helpers import fixture_sql
        row = self.case.req('items', method='POST', body={'values': self.case.values(), 'status': 'SUSPENDED'}, expected=201)
        fixture_sql(f"UPDATE masterdata.catalog_item SET category_id=NULL,version=version+1 WHERE id='{row['id']}' AND tenant_id='{self.case.tenant_id}'")
        row = self.case.req('items', row['id'])
        self.login('it')
        self.navigate()
        self.open(row)
        for field in ('category-id', 'base-uom'):
            expect(self.dialog().locator('label[for="item-' + field + '"]')).to_contain_text('*')
        before = len(self.mutations)
        control(self.dialog(), 'item-save').click()
        expect(self.field('category_id')).to_have_attribute('aria-invalid', 'true')
        self.assertEqual(len(self.mutations), before)
        self.assertEqual(self.case.req('items', row['id']), row)
        self.choose('category_id', self.case.category)
        result = self.save_main().json()
        self.assertEqual(result['category_id'], self.case.category['id'])
        self.assertEqual(result['status'], 'SUSPENDED')
        self.assertEqual(result['version'], row['version'] + 1)
        self.case.full(result)

    def test_archive_cancel_preserves_draft_and_confirm_commits_once(self):
        from playwright.sync_api import expect
        row = self.case.item()
        self.assertEqual(row['status'], 'ACTIVE')
        self.login('it')
        self.navigate()
        self.open(row)
        self.field('name').fill('Nome modificato da archiviare')
        self.choose_status('Archiviato')
        before = len(self.mutations)
        control(self.page, 'item-save').click()
        confirmation = self.page.get_by_test_id('catalog-item-archive-confirm')
        expect(confirmation).to_be_visible()
        expect(confirmation).to_contain_text('riattiv')
        self.assertEqual(len(self.mutations), before)
        self.assertEqual(self.case.req('items', row['id']), row)
        control(confirmation, 'item-archive-cancel').click()
        expect(confirmation).to_have_count(0)
        expect(self.field('name')).to_have_value('Nome modificato da archiviare')
        expect(self.field('status')).to_contain_text('Archiviato')
        self.assertEqual(len(self.mutations), before)
        self.assertEqual(self.case.req('items', row['id']), row)
        control(self.page, 'item-save').click()
        expect(confirmation).to_be_visible()
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path == '/api/catalog/items/' + row['id']) as saved:
            control(confirmation, 'item-archive-confirm').click()
        self.assertEqual(saved.value.status, 200, saved.value.text())
        result = saved.value.json()
        self.assertEqual(result['status'], 'ARCHIVED')
        self.assertEqual(result['name'], 'Nome modificato da archiviare')
        self.assertEqual(result['version'], row['version'] + 1)
        self.case.full(result)
        self.assertEqual(len(self.mutations), before + 1)
        self.assertEqual(saved.value.request.post_data_json['expectedVersion'], row['version'])
        expect(self.page.get_by_test_id('catalog-item-editor')).to_have_count(0)
