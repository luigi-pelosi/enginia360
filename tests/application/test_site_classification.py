"""Classificazione sedi: richieste autentiche al backend della copia isolata."""
import json
import unittest
from unified_save_support import Case, root_client, sql

TYPES = ['LEGAL', 'LOCAL_UNIT', 'SECONDARY']
FUNCTIONS = ['OPERATIONAL', 'ADMINISTRATIVE', 'COMMERCIAL', 'PRODUCTION', 'LOGISTICS', 'WAREHOUSE', 'TECHNICAL_SERVICE', 'MANAGEMENT', 'RETAIL']


class SiteClassificationApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.credentials = root_client()

    def setUp(self):
        self.case = Case(self.root)
        self.company = self.case.create('companies', {'name': 'Azienda sedi'})

    def tearDown(self):
        self.case.close()

    def create(self, **values):
        data = {'company_id': self.company['id'], 'name': 'Sede classificata', **values}
        status, row = self.root.request(self.case.path('sites', save=True), 'POST', {'values': data})
        self.assertEqual(status, 201, row)
        return row

    def stored(self, record_id):
        result = sql(f"SELECT row_to_json(t) FROM foundation.site t WHERE id='{record_id}'")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_metadata_and_create_accept_legal_classification_and_multiple_functions(self):
        status, resources = self.root.request('/api/resources')
        self.assertEqual(status, 200)
        fields = {f['name']: f for r in resources if r['key'] == 'sites' for f in r['fields']}
        self.assertEqual(fields['site_type']['type'], 'select')
        self.assertEqual(fields['site_type']['options'], TYPES)
        self.assertFalse(fields['site_type']['required'])
        self.assertEqual(fields['functions']['type'], 'multiselect')
        self.assertEqual(fields['functions']['options'], FUNCTIONS)
        row = self.create(site_type='LOCAL_UNIT', functions=['TECHNICAL_SERVICE', 'OPERATIONAL', 'WAREHOUSE'])
        self.assertEqual(row['functions'], ['OPERATIONAL', 'WAREHOUSE', 'TECHNICAL_SERVICE'])
        self.assertEqual(row['site_type'], 'LOCAL_UNIT')
        self.assertIsNone(row['code'])
        self.assertEqual(self.stored(row['id'])['functions'], row['functions'])

    def test_omission_preserves_and_explicit_clear_resets_without_legal_default(self):
        row = self.create()
        self.assertIsNone(row['site_type'])
        self.assertEqual(row['functions'], [])
        status, row = self.root.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'site_type': 'SECONDARY', 'functions': FUNCTIONS}})
        self.assertEqual(status, 200)
        status, updated = self.root.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'name': 'Nome aggiornato'}})
        self.assertEqual(status, 200)
        self.assertEqual(updated['site_type'], 'SECONDARY')
        self.assertEqual(updated['functions'], FUNCTIONS)
        status, cleared = self.root.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'site_type': None, 'functions': []}})
        self.assertEqual(status, 200)
        self.assertIsNone(cleared['site_type'])
        self.assertEqual(cleared['functions'], [])
        status, blank = self.root.request(self.case.path('sites', row['id']), 'PUT', {'site_type': '   '})
        self.assertEqual(status, 200)
        self.assertIsNone(blank['site_type'])

    def test_invalid_classification_arrays_and_duplicates_are_atomic_client_refusals(self):
        row = self.create(site_type='LEGAL', functions=['MANAGEMENT'])
        before = self.stored(row['id'])
        audits = sql(f"SELECT count(*) FROM foundation.audit_event WHERE record_id='{row['id']}'").stdout
        invalid = [{'site_type': value} for value in ('WAREHOUSE', 'legal', ' LEGAL ', 1, [])]
        invalid += [{'functions': value} for value in (None, 'WAREHOUSE', {}, [None], [1], ['UNKNOWN'], ['warehouse'], ['WAREHOUSE', 'WAREHOUSE'], FUNCTIONS + ['WAREHOUSE'], [['WAREHOUSE']], ['\ud800'])]
        for values in invalid:
            with self.subTest(values=values):
                status, _ = self.root.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'name': 'Non applicare', **values}})
                self.assertEqual(status, 400)
                self.assertEqual(self.stored(row['id']), before)
        self.assertEqual(sql(f"SELECT count(*) FROM foundation.audit_event WHERE record_id='{row['id']}'").stdout, audits)

    def test_fiscal_data_warehouse_and_purchase_coverage_remain_unchanged(self):
        row = self.create(site_type='LOCAL_UNIT', functions=['WAREHOUSE'], vat_number='VAT esistente', tax_code='CF esistente')
        kind = self.case.create('warehouse-types', {'name': 'Fisico'})
        warehouse = self.case.create('warehouses', {'name': 'Ricambi', 'site_id': row['id'], 'warehouse_type_id': kind['id']})
        status, purchase = self.root.request(self.case.path('purchasing-organizations', save=True), 'POST', {
            'values': {'name': 'Acquisti'}, 'coverage': [{'companyId': self.company['id'], 'siteScope': 'selected_sites', 'siteIds': [row['id']]}]})
        self.assertEqual(status, 201)
        status, updated = self.root.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'site_type': 'SECONDARY', 'functions': ['TECHNICAL_SERVICE', 'COMMERCIAL']}})
        self.assertEqual(status, 200)
        self.assertEqual((updated['vat_number'], updated['tax_code']), ('VAT esistente', 'CF esistente'))
        self.assertEqual(sql(f"SELECT site_id FROM foundation.warehouse WHERE id='{warehouse['id']}'").stdout.strip(), row['id'])
        status, coverage = self.root.request('/api/data/purchasing-organizations/' + purchase['id'] + '/coverage?tenantId=' + self.case.tenant['id'])
        self.assertEqual(status, 200)
        self.assertEqual(coverage['coverage'][0]['siteIds'], [row['id']])

    def test_existing_site_permissions_and_cross_tenant_boundaries_apply(self):
        row = self.create(functions=['WAREHOUSE'])
        reader, _, _, _ = self.case.actor(['sites.read', 'companies.read'])
        self.assertEqual(reader.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'functions': ['COMMERCIAL']}})[0], 403)
        writer, _, _, _ = self.case.actor(['sites.read', 'sites.update', 'companies.read'])
        self.assertEqual(writer.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'functions': ['COMMERCIAL']}})[0], 200)
        foreign = Case(self.root)
        try:
            company = foreign.create('companies', {'name': 'Altra azienda'})
            other = foreign.create('sites', {'name': 'Altra sede', 'company_id': company['id']})
            self.assertEqual(writer.request(self.case.path('sites', other['id'], save=True), 'PUT', {'values': {'functions': ['WAREHOUSE']}})[0], 404)
            self.assertEqual(writer.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'company_id': company['id'], 'functions': ['WAREHOUSE']}})[0], 400)
        finally:
            foreign.close()

    def test_deferred_audit_failure_rolls_back_both_fields_and_success_records_snapshots(self):
        row = self.create(site_type='LEGAL', functions=['MANAGEMENT'])
        before = self.stored(row['id'])
        sql("CREATE FUNCTION foundation.site_proof_reject() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.resource='sites' AND NEW.record_id='{row['id']}'::uuid THEN RAISE EXCEPTION 'Fixture site commit failure'; END IF; RETURN NEW; END $$; "
            "CREATE CONSTRAINT TRIGGER site_proof_reject AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.site_proof_reject();")
        try:
            status, _ = self.root.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'site_type': 'LOCAL_UNIT', 'functions': ['OPERATIONAL', 'TECHNICAL_SERVICE']}})
            self.assertEqual(status, 500)
            self.assertEqual(self.stored(row['id']), before)
        finally:
            sql('DROP TRIGGER site_proof_reject ON foundation.audit_event;DROP FUNCTION foundation.site_proof_reject();')
        status, after = self.root.request(self.case.path('sites', row['id'], save=True), 'PUT', {'values': {'site_type': 'LOCAL_UNIT', 'functions': ['OPERATIONAL', 'TECHNICAL_SERVICE']}})
        self.assertEqual(status, 200)
        details = json.loads(sql(f"SELECT details FROM foundation.audit_event WHERE record_id='{row['id']}' AND action='update' ORDER BY created_at DESC LIMIT 1").stdout)
        self.assertEqual(details['before']['functions'], before['functions'])
        self.assertEqual(details['after']['functions'], after['functions'])
        self.assertEqual(details['before']['site_type'], 'LEGAL')
        self.assertEqual(details['after']['site_type'], 'LOCAL_UNIT')


if __name__ == '__main__':
    unittest.main(verbosity=2)
