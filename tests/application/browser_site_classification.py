"""Classificazione sede: form e fetch reali sulle candidate isolate."""
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit
import browser_unified_save as harness
from unified_save_support import sql
from playwright.sync_api import expect

EVIDENCE = Path('/root/.hermes/cache/scratch/enginia360-site-classification/browser')
EVIDENCE.mkdir(parents=True, exist_ok=True)
harness.EVIDENCE = EVIDENCE
Base = harness.UnifiedSaveBrowserTests


class SiteClassificationBrowserTests(unittest.TestCase):
    setUpClass = classmethod(Base.setUpClass.__func__)
    tearDownClass = classmethod(Base.tearDownClass.__func__)
    tearDown = Base.tearDown
    login = Base.login

    def setUp(self):
        harness.UnifiedSaveBrowserTests.setUp(self)
        self.company = self.case.create('companies', {'name': 'Area Service'})

    def navigate(self, name='Sedi'):
        self.page.locator('nav').get_by_role('button', name=name, exact=True).click()

    def new(self):
        self.navigate()
        self.page.get_by_role('button', name='Nuovo', exact=True).first.click()
        return self.page.get_by_role('dialog')

    def open(self, row):
        self.navigate()
        self.page.locator('tbody tr').filter(has_text=row['name']).get_by_role('button', name=re.compile('^(Modifica|Dettagli) ')).click()
        return self.page.get_by_role('dialog')

    def stored(self, row):
        return json.loads(sql(f"SELECT row_to_json(t) FROM foundation.site t WHERE id='{row['id']}'").stdout)

    def legal(self, dialog, label):
        dialog.get_by_role('combobox', name='Tipologia giuridica', exact=True).click()
        self.page.get_by_role('option', name=label, exact=True).click()

    def test_native_create_legal_select_multiple_functions_and_one_atomic_save(self):
        self.login()
        dialog = self.new()
        expect(dialog.get_by_role('combobox', name='Tipologia giuridica', exact=True)).to_be_visible()
        dialog.locator('#field-company_id').click()
        self.page.get_by_role('option', name=self.company['name'], exact=True).click()
        dialog.locator('#field-name').fill('Officina Napoli')
        self.legal(dialog, 'Unità locale')
        for name in ('Operativa', 'Commerciale', 'Magazzino', 'Assistenza tecnica'):
            dialog.get_by_role('checkbox', name=name, exact=True).check()
        expect(dialog.get_by_role('button', name='Salva', exact=True)).to_have_count(1)
        expect(dialog.locator('#field-code')).not_to_have_attribute('required', '')
        self.assertEqual(self.mutations, [])
        self.page.screenshot(path=str(EVIDENCE / 'site-classification-draft.png'), full_page=True)
        with self.page.expect_response(lambda r:urlsplit(r.url).path == '/api/data/sites/save' and r.request.method == 'POST') as saved:
            dialog.get_by_role('button', name='Salva', exact=True).click()
        self.assertEqual(saved.value.status, 201)
        row = saved.value.json()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(row['site_type'], 'LOCAL_UNIT')
        self.assertEqual(row['functions'], ['OPERATIONAL', 'COMMERCIAL', 'WAREHOUSE', 'TECHNICAL_SERVICE'])
        self.assertEqual(self.stored(row)['functions'], row['functions'])
        dialog = self.open(row)
        expect(dialog.get_by_role('combobox', name='Tipologia giuridica', exact=True)).to_contain_text('Unità locale')
        for name in ('Operativa', 'Commerciale', 'Magazzino', 'Assistenza tecnica'):
            expect(dialog.get_by_role('checkbox', name=name, exact=True)).to_be_checked()
        expect(dialog.get_by_role('button', name='Salva', exact=True)).to_be_disabled()

    def test_cancel_discards_legal_and_function_changes_without_writes(self):
        row = self.case.create('sites', {'company_id': self.company['id'], 'name': 'Sede invariata'})
        self.login()
        dialog = self.open(row)
        self.legal(dialog, 'Sede legale')
        dialog.get_by_role('checkbox', name='Direzionale', exact=True).check()
        dialog.get_by_role('button', name='Annulla', exact=True).click()
        self.assertEqual(self.mutations, [])
        self.assertIsNone(self.stored(row)['site_type'])
        self.assertEqual(self.stored(row)['functions'], [])

    def test_deselect_all_functions_and_clear_optional_legal_classification(self):
        row = self.case.create('sites', {'company_id': self.company['id'], 'name': 'Sede da azzerare', 'site_type': 'SECONDARY', 'functions': ['WAREHOUSE']})
        self.login()
        dialog = self.open(row)
        dialog.get_by_role('checkbox', name='Magazzino', exact=True).uncheck()
        dialog.get_by_role('combobox', name='Tipologia giuridica', exact=True).click()
        # L'opzione priva di codice è la scelta facoltativa vuota, distinta dai tre tipi.
        options = self.page.get_by_role('option')
        options.filter(has_not_text=re.compile('^(Sede legale|Unità locale|Sede secondaria)$')).first.click()
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 1)
        self.assertEqual(self.mutations[0]['body']['values']['functions'], [])
        self.assertIsNone(self.stored(row)['site_type'])
        self.assertEqual(self.stored(row)['functions'], [])

    def test_readonly_actor_sees_localized_fields_without_mutation_controls(self):
        row = self.case.create('sites', {'company_id': self.company['id'], 'name': 'Sede sola lettura', 'site_type': 'LEGAL', 'functions': ['MANAGEMENT']})
        _, _, _, credentials = self.case.actor(['sites.read', 'companies.read'])
        self.login(credentials, self.case.tenant['code'])
        dialog = self.open(row)
        expect(dialog.get_by_role('combobox', name='Tipologia giuridica', exact=True)).to_be_disabled()
        expect(dialog.get_by_role('checkbox', name='Direzionale', exact=True)).to_be_checked()
        expect(dialog.get_by_role('checkbox', name='Direzionale', exact=True)).to_be_disabled()
        expect(dialog.get_by_role('button', name='Salva', exact=True)).to_have_count(0)
        self.assertEqual(self.mutations, [])

    def test_mobile_english_localized_options_without_raw_codes_or_overflow(self):
        row = self.case.create('sites', {'company_id': self.company['id'], 'name': 'English site', 'site_type': 'LOCAL_UNIT', 'functions': ['TECHNICAL_SERVICE', 'RETAIL']})
        self.login()
        self.context.add_cookies([{'name': 'locale', 'value': 'en', 'url': harness.ORIGIN}])
        self.page.reload(wait_until='networkidle')
        self.page.locator('#tenant-select').click()
        self.page.get_by_role('option', name='Verifica salvataggio', exact=True).click()
        self.navigate('Sites')
        self.page.locator('tbody tr').filter(has_text=row['name']).get_by_role('button', name='Edit '+row['name'], exact=True).click()
        dialog = self.page.get_by_role('dialog')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        expect(dialog.get_by_role('combobox', name='Legal classification', exact=True)).to_contain_text('Local unit')
        expect(dialog.get_by_role('checkbox', name='Technical service', exact=True)).to_be_checked()
        expect(dialog.get_by_role('checkbox', name='Retail', exact=True)).to_be_checked()
        self.assertNotIn('TECHNICAL_SERVICE', dialog.inner_text())
        self.assertNotIn('LOCAL_UNIT', dialog.inner_text())
        self.assertTrue(dialog.evaluate('(el)=>el.scrollWidth<=el.clientWidth'))
        self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
        self.page.screenshot(path=str(EVIDENCE / 'site-classification-mobile-en.png'), full_page=True)

    def test_commit_failure_keeps_draft_and_retry_uses_identical_one_save_payload(self):
        row = self.case.create('sites', {'company_id': self.company['id'], 'name': 'Sede retry', 'site_type': 'LEGAL', 'functions': ['MANAGEMENT']})
        self.login()
        dialog = self.open(row)
        self.legal(dialog, 'Unità locale')
        dialog.get_by_role('checkbox', name='Assistenza tecnica', exact=True).check()
        sql("CREATE FUNCTION foundation.site_browser_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.resource='sites' AND NEW.record_id='{row['id']}'::uuid THEN RAISE EXCEPTION 'Fixture browser commit failure'; END IF; RETURN NEW; END $$; "
            "CREATE CONSTRAINT TRIGGER site_browser_reject AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.site_browser_reject();")
        try:
            with self.page.expect_response(lambda r:r.request.method == 'PUT' and urlsplit(r.url).path.endswith('/save')) as failed:
                dialog.get_by_role('button', name='Salva', exact=True).click()
            self.assertEqual(failed.value.status, 500)
            expect(dialog.locator('[data-slot=alert]')).to_be_visible()
            expect(dialog.get_by_role('combobox', name='Tipologia giuridica', exact=True)).to_contain_text('Unità locale')
            expect(dialog.get_by_role('checkbox', name='Assistenza tecnica', exact=True)).to_be_checked()
            self.assertEqual(self.stored(row)['site_type'], 'LEGAL')
            self.assertEqual(self.stored(row)['functions'], ['MANAGEMENT'])
        finally:
            sql('DROP TRIGGER site_browser_reject ON foundation.audit_event;DROP FUNCTION foundation.site_browser_reject();')
        dialog.get_by_role('button', name='Salva', exact=True).click()
        expect(self.page.get_by_role('dialog')).to_have_count(0)
        self.assertEqual(len(self.mutations), 2)
        self.assertEqual(self.mutations[0]['body'], self.mutations[1]['body'])
        self.assertEqual(self.stored(row)['site_type'], 'LOCAL_UNIT')
        self.assertEqual(self.stored(row)['functions'], ['TECHNICAL_SERVICE', 'MANAGEMENT'])


# Evita che unittest raccolga anche la classe storica importata come harness.
del Base

if __name__ == '__main__':
    unittest.main(verbosity=2)
