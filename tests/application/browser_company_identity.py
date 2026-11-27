"""IT/EN Chromium acceptance forwarding to real candidate containers."""
import re
import unittest
from urllib.parse import urlsplit
from browser_company_tax_proof import CompanyTaxBrowser as Harness


class CompanyIdentityBrowser(unittest.TestCase):
    setUpClass = classmethod(Harness.setUpClass.__func__)
    tearDownClass = classmethod(Harness.tearDownClass.__func__)
    setUp = Harness.setUp
    tearDown = Harness.tearDown
    login = Harness.login
    company_navigation = Harness.company_navigation
    open_company = Harness.open_company
    general_save = Harness.general_save

    def site_navigation(self):
        from playwright.sync_api import expect
        self.page.locator('nav').get_by_role('button', name=self.messages['resources']['sites'], exact=True).click()
        expect(self.page.get_by_role('heading', name=self.messages['resources']['sites'], exact=True)).to_be_visible()

    def lifecycle(self, locale):
        from playwright.sync_api import expect
        self.login(locale)
        self.open_company()
        expect(self.page.locator('#company-tab-general')).to_have_attribute('aria-selected', 'true')
        expect(self.page.locator('#field-tax_code')).to_have_count(0)
        expect(self.page.locator('#field-vat_number')).to_have_count(0)
        field = self.page.locator('#field-name')
        name = 'General browser ' + self.case.code
        field.fill(name)
        self.page.reload(wait_until='networkidle')
        expect(field).to_have_value(name)
        expect(self.page.locator('#field-tax_code')).to_have_count(0)
        saved = self.general_save()
        self.assertNotIn('tax_code', saved)
        self.case.company = saved
        self.open_company()
        expect(field).to_have_value(name)
        expect(self.page.locator('#field-tax_code')).to_have_count(0)
        self.page.get_by_role('dialog').get_by_role('button', name=self.messages['app']['cancel'], exact=True).click()
        self.site_navigation()
        self.page.locator('.page-heading').get_by_role('button', name=self.messages['app']['new'], exact=True).click()
        dialog = self.page.get_by_role('dialog')
        for key in ('tax_code', 'vat_number'):
            expect(dialog.locator('#field-' + key)).to_have_count(0)
        dialog.locator('#field-company_id').click()
        self.page.get_by_role('option', name=self.case.company['name'], exact=True).click()
        name = 'Identity site ' + self.case.code
        dialog.locator('#field-name').fill(name)
        save = dialog.get_by_role('button', name=self.messages['app']['save'], exact=True)
        expect(save).to_be_disabled()
        for key, value in [('address', 'Via browser 17'), ('city', 'Roma'), ('province', 'RM'), ('postal_code', '00100')]:
            dialog.locator('#field-' + key).fill(value)
        dialog.locator('#field-country_code').click()
        self.page.get_by_role('option', name='Italia', exact=True).click()
        expect(save).to_be_enabled()
        self.page.reload(wait_until='networkidle')
        dialog = self.page.get_by_role('dialog')
        expect(dialog.locator('#field-address')).to_have_value('Via browser 17')
        for key in ('tax_code', 'vat_number'):
            expect(dialog.locator('#field-' + key)).to_have_count(0)
        with self.page.expect_response(lambda response: response.request.method == 'POST' and urlsplit(response.url).path == '/api/data/sites/save') as created:
            dialog.get_by_role('button', name=self.messages['app']['save'], exact=True).click()
        self.assertEqual(created.value.status, 201, created.value.text())
        row = created.value.json()
        self.assertNotIn('tax_code', row)
        self.assertNotIn('vat_number', row)
        expect(dialog).to_have_count(0)
        self.page.locator('.search-box input').fill(name)
        self.page.locator('tbody tr').filter(has_text=name).get_by_role('button', name=re.compile('^' + re.escape(self.messages['app']['edit']) + r'(?:\s|$)')).click()
        dialog = self.page.get_by_role('dialog')
        expect(dialog.locator('#field-address')).to_have_value('Via browser 17')
        dialog.locator('#field-address').fill('Via browser edited 23')
        self.page.reload(wait_until='networkidle')
        dialog = self.page.get_by_role('dialog')
        expect(dialog.locator('#field-address')).to_have_value('Via browser edited 23')
        for key in ('tax_code', 'vat_number'):
            expect(dialog.locator('#field-' + key)).to_have_count(0)
        with self.page.expect_response(lambda response: response.request.method == 'PUT' and urlsplit(response.url).path == '/api/data/sites/' + row['id'] + '/save') as updated:
            dialog.get_by_role('button', name=self.messages['app']['save'], exact=True).click()
        self.assertEqual(updated.value.status, 200, updated.value.text())
        self.assertEqual(updated.value.json()['address'], 'Via browser edited 23')
        self.assertNotIn('tax_code', self.case.company_read())

    def test_italian_company_cf_site_without_fiscal_fields_and_refresh_recovery(self):
        self.lifecycle('it')

    def test_english_company_cf_site_without_fiscal_fields_and_refresh_recovery(self):
        self.lifecycle('en')
