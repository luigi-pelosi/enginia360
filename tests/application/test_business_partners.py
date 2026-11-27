"""Accettazione HTTP del Core BP: soltanto fixture isolate esplicite."""
import concurrent.futures
import copy
import json
import os
from pathlib import Path
import unittest
import uuid

from test_api import Client


@unittest.skipUnless(os.environ.get('ENGINIA360_BP_PROOF') == '1', 'Richiede il runner BP isolato')
class BusinessPartnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.credentials = json.loads(Path(os.environ['ENGINIA360_TEST_CREDENTIALS']).read_text())
        cls.root = Client()
        status, session = cls.root.login(cls.credentials)
        if status != 200:
            raise AssertionError(('login isolato', status))
        if session['mustChangePassword']:
            changed = uuid.uuid4().hex + '-Changed!'
            status, _ = cls.root.request('/api/auth/password', 'PUT', {
                'currentPassword': cls.credentials['password'], 'newPassword': changed})
            if status != 204:
                raise AssertionError(('password isolata', status))
            cls.credentials['password'] = changed
            cls.root.token = None
            Path(os.environ['ENGINIA360_TEST_CREDENTIALS']).write_text(json.dumps(cls.credentials))

    def setUp(self):
        self.code = 'bp-' + uuid.uuid4().hex[:12]
        status, self.tenant = self.root.request('/api/data/tenants', 'POST', {'code': self.code, 'name': 'Prova BP'})
        self.assertEqual(status, 201)
        self.tenant_id = self.tenant['id']

    def path(self, suffix='', tenant=None):
        return f'/api/data/business-partners{suffix}?tenantId={tenant or self.tenant_id}'

    def numbering(self):
        return f'/api/business-partner-numbering?tenantId={self.tenant_id}'

    def create(self, name='Alfa Ricambi', **extra):
        body = {'values': {'kind': 'ORGANIZATION', 'legal_name': name, 'status': 'ACTIVE'}, **extra}
        status, row = self.root.request(self.path('/save'), 'POST', body)
        self.assertEqual(status, 201, row)
        return row

    def update(self, row, values=None, **extra):
        return self.root.request(self.path('/'+row['id']+'/save'), 'PUT', {
            'values': values or {'status': row['status']}, 'expectedVersion': row['version'], **extra})

    def read(self, row):
        status, result = self.root.request(self.path('/'+row['id']))
        self.assertEqual(status, 200)
        return result

    def test_13_validation_identifies_the_rejected_field_without_partial_writes(self):
        row = self.create('Verifica messaggi fiscali')
        before = self.read(row)
        status, response = self.update(row, {'legal_name': 'Modifica non persistita'}, taxIdentifiers=[
            {'country_code': 'DE', 'identifier_type': 'FOREIGN_TAX_ID', 'value': 'DE-12345'},
            {'country_code': 'IT', 'identifier_type': 'VAT', 'value': 'IT12345678901'}])
        self.assertEqual(status, 400)
        self.assertEqual(response, {'code': 'invalid_italian_vat', 'field': 'taxIdentifiers[1].value'})
        self.assertEqual(self.read(row), before)
        for value, code, field in (
            ({'taxIdentifiers': [{'country_code': 'IT', 'identifier_type': 'FISCAL_CODE', 'value': 'ABC'}]}, 'invalid_italian_fiscal_code', 'taxIdentifiers[0].value'),
            ({'contactChannels': [{'channel_type': 'PHONE', 'value': 'not-a-phone'}]}, 'invalid_contact_phone', 'contactChannels[0].value'),
            ({'addresses': [{'street': 'Via Roma', 'city': 'Roma', 'country_code': 'IT'}]}, 'business_partner_address_required', 'addresses[0].postal_code'),
        ):
            with self.subTest(code=code):
                status, response = self.update(row, **value)
                self.assertEqual(status, 400)
                self.assertEqual(response, {'code': code, 'field': field})
                self.assertEqual(self.read(row), before)

    def test_14_tax_diagnostics_do_not_confuse_format_length_and_normalization(self):
        row = self.create('Verifica cause distinte')
        before = self.read(row)
        for value, extra, code, field in (
            ('X' * 101, {}, 'field_too_long', 'value'),
            (123, {}, 'invalid_field_value', 'value'),
            ('AB\tCD', {}, 'invalid_field_value', 'value'),
            ('AB123', {'normalized_value': 'DIFFERENT'}, 'tax_identifier_normalization_mismatch', 'normalized_value'),
        ):
            with self.subTest(code=code, field=field):
                status, response = self.update(row, taxIdentifiers=[{'country_code': 'FR', 'identifier_type': 'FOREIGN_TAX_ID', 'value': value, **extra}])
                self.assertEqual(status, 400)
                self.assertEqual(response, {'code': code, 'field': 'taxIdentifiers[0].' + field})
                self.assertEqual(self.read(row), before)

    def test_15_geography_uses_the_selected_crud_permissions_and_catalog(self):
        from urllib.parse import urlencode
        country = self.root.request('/api/data/countries', 'POST', {'name': 'Italia prova', 'iso_code': 'IT'})
        if country[0] == 409:
            country_id = next(item['id'] for item in self.root.request('/api/data/countries?pageSize=100&search=Italia')[1]['items'] if item['iso_code'] == 'IT')
        else:
            self.assertEqual(country[0], 201, country[1]); country_id = country[1]['id']
        status, city = self.root.request('/api/data/cities', 'POST', {'country_id': country_id, 'name': 'Località BP prova', 'province': 'RM', 'postal_code': '00123'})
        self.assertIn(status, (201, 409), city)
        lookup = '/api/addresses/autocomplete?' + urlencode({'tenantId': self.tenant_id, 'resource': 'business-partners', 'field': 'city', 'text': 'Località BP prova', 'countryCode': 'IT'})
        countries = '/api/addresses/countries?' + urlencode({'tenantId': self.tenant_id, 'resource': 'business-partners'})
        creator, _ = self.actor(['business-partners.create'])
        updater, role = self.actor(['business-partners.update'])
        reader, _ = self.actor(['business-partners.read'])
        site_writer, _ = self.actor(['sites.create'])
        for path in (lookup, countries):
            with self.subTest(path=path):
                self.assertEqual(Client().request(path)[0], 401)
                for actor in (creator, updater): self.assertEqual(actor.request(path)[0], 200)
                for actor in (reader, site_writer): self.assertEqual(actor.request(path)[0], 403)
                self.assertEqual(creator.request(path.replace('business-partners', 'sites'))[0], 403)
                self.assertEqual(site_writer.request(path.replace('business-partners', 'sites'))[0], 200)
                self.assertEqual(self.root.request(path.replace('business-partners', 'unknown'))[0], 400)
                self.assertEqual(creator.request(path.replace(self.tenant_id, '00000000-0000-0000-0000-000000000001'))[0], 403)
        status, response = creator.request(lookup)
        self.assertEqual(status, 200, response)
        items = response['items']
        item = next(item for item in items if item['city'] == 'Località BP prova')
        self.assertEqual((item['postalCode'], item['province'], item['countryCode'], item['address']), ('00123', 'RM', 'IT', ''))
        self.assertEqual(self.root.request(f'/api/links/role-permissions/{role["id"]}?tenantId={self.tenant_id}', 'PUT', {'ids': []})[0], 204)
        self.assertEqual(updater.request(lookup)[0], 403)

    def test_16_related_only_commands_preserve_identity_and_omitted_collections(self):
        row = self.create('Identità da conservare',
            addresses=[{'street': 'Via Roma', 'city': 'Roma', 'postal_code': '00100', 'country_code': 'IT'}],
            contactChannels=[{'channel_type': 'EMAIL', 'value': 'keep@example.invalid', 'is_primary': True}])
        before = self.read(row)
        status, changed = self.root.request(self.path('/'+row['id']+'/save'), 'PUT', {
            'values': {}, 'expectedVersion': before['version'],
            'taxIdentifiers': [{'country_code': 'DE', 'identifier_type': 'FOREIGN_TAX_ID', 'value': 'DE-12345'}]})
        self.assertEqual(status, 200, changed)
        self.assertEqual(changed['legal_name'], before['legal_name'])
        self.assertEqual(changed['addresses'], before['addresses'])
        self.assertEqual(changed['contact_channels'], before['contact_channels'])
        self.assertEqual(changed['version'], before['version'] + 1)
        status, removed = self.root.request(self.path('/'+row['id']+'/save'), 'PUT', {
            'values': {}, 'expectedVersion': changed['version'], 'contactChannels': []})
        self.assertEqual(status, 200, removed)
        self.assertEqual(removed['contact_channels'], [])
        self.assertEqual(removed['tax_identifiers'], changed['tax_identifiers'])
        self.assertEqual(removed['addresses'], before['addresses'])
        self.assertEqual(self.read(row), removed)
        for grants in (['business-partners.read'], ['business-partners.create']):
            actor, _ = self.actor(grants)
            self.assertEqual(actor.request(self.path('/'+row['id']+'/save'), 'PUT', {
                'values': {}, 'expectedVersion': removed['version'], 'taxIdentifiers': []})[0], 403)
        self.assertEqual(self.read(row), removed)

    def test_01_metadata_and_default_automatic_numbering(self):
        status, resources = self.root.request('/api/resources')
        self.assertEqual(status, 200)
        self.assertIn('business-partners', [r['key'] for r in resources])
        status, config = self.root.request(self.numbering())
        self.assertEqual(status, 200)
        self.assertEqual({k: config[k] for k in ('mode', 'prefix', 'padding', 'nextNumber')},
                         {'mode': 'AUTO', 'prefix': 'BP-', 'padding': 6, 'nextNumber': 1})
        first = self.create()
        second = self.create('Beta Ricambi')
        self.assertEqual((first['code'], second['code']), ('BP-000001', 'BP-000002'))
        self.assertEqual(self.read(first)['legal_name'], 'Alfa Ricambi')
        status, _ = self.update(first, {'code': 'REWRITE'})
        self.assertIn(status, (400, 409))
        self.assertEqual(self.read(first)['code'], first['code'])

    def test_02_nested_aggregate_save_omission_and_empty_collections(self):
        row = self.create(taxIdentifiers=[{'country_code': 'DE', 'identifier_type': 'FOREIGN_TAX_ID', 'value': 'DE-12345'}],
                          contactChannels=[{'channel_type': 'EMAIL', 'value': 'orders@example.invalid', 'purpose': 'Ordini', 'is_primary': True}],
                          addresses=[{'label': 'Principale', 'street': 'Via Roma', 'street_number': '1', 'city': 'Roma',
                                      'province': 'RM', 'postal_code': '00100', 'country_code': 'IT',
                                      'usages': [{'usage': 'BILLING', 'is_default': True}, {'usage': 'SHIPPING', 'is_default': True}]}])
        self.assertEqual(len(row['addresses']), 1)
        self.assertEqual(len(row['addresses'][0]['usages']), 2)
        status, changed = self.update(row, {'legal_name': 'Alfa aggiornata'})
        self.assertEqual(status, 200, changed)
        self.assertEqual(changed['contact_channels'][0]['value'], 'orders@example.invalid')
        status, cleared = self.update(changed, contactChannels=[], addresses=[])
        self.assertEqual(status, 200, cleared)
        self.assertEqual(cleared['contact_channels'], [])
        self.assertEqual(cleared['addresses'], [])
        self.assertEqual(len(cleared['tax_identifiers']), 1)

    def test_03_fiscal_duplicate_blocks_and_rolls_back_counter(self):
        tax = [{'country_code': 'DE', 'identifier_type': 'FOREIGN_TAX_ID', 'value': 'DE 12345'}]
        self.create(taxIdentifiers=tax)
        before = self.root.request(self.numbering())[1]
        status, result = self.root.request(self.path('/save'), 'POST', {
            'values': {'kind': 'ORGANIZATION', 'legal_name': 'Duplicato'},
            'taxIdentifiers': [{'country_code': 'DE', 'identifier_type': 'FOREIGN_TAX_ID', 'value': 'de12345'}]})
        self.assertEqual(status, 409, result)
        self.assertEqual(self.root.request(self.numbering())[1]['nextNumber'], before['nextNumber'])
        self.assertEqual(self.root.request(self.path())[1]['total'], 1)
        self.assertEqual(self.create('Successivo')['code'], 'BP-000002')

    def test_04_version_and_tenant_isolation(self):
        row = self.create()
        status, updated = self.update(row, {'legal_name': 'Versione nuova'})
        self.assertEqual(status, 200, updated)
        self.assertGreater(updated['version'], row['version'])
        self.assertEqual(self.update(row, {'legal_name': 'Obsoleta'})[0], 409)
        self.assertEqual(self.read(row)['legal_name'], 'Versione nuova')
        status, other = self.root.request('/api/data/tenants', 'POST', {'code': self.code+'-other', 'name': 'Altro tenant'})
        self.assertEqual(status, 201)
        self.assertEqual(self.root.request(self.path('/'+row['id'], other['id']))[0], 404)
        self.assertEqual(self.root.request(self.path(tenant=other['id']))[1]['total'], 0)
        self.assertEqual(self.root.request(self.path('/'+row['id']+'/save', other['id']), 'PUT', {
            'expectedVersion': updated['version'], 'values': {'legal_name': 'Intruso'}})[0], 404)

    def test_05_manual_configuration_and_format_frozen_after_use(self):
        status, config = self.root.request(self.numbering())
        self.assertEqual(status, 200)
        config.update(mode='MANUAL', prefix='PART-', padding=4, nextNumber=50)
        status, config = self.root.request(self.numbering(), 'PUT', config)
        self.assertEqual(status, 200, config)
        self.assertEqual(self.root.request(self.path('/save'), 'POST', {
            'values': {'kind': 'ORGANIZATION', 'legal_name': 'Senza codice'}})[0], 400)
        row = self.root.request(self.path('/save'), 'POST', {
            'values': {'kind': 'ORGANIZATION', 'legal_name': 'Manuale', 'code': 'EXT-ALFA'}})
        self.assertEqual(row[0], 201, row[1])
        self.assertEqual(row[1]['code'], 'EXT-ALFA')
        self.assertEqual(self.root.request(self.path('/save'), 'POST', {
            'values': {'kind': 'PERSON', 'first_name': 'Mario', 'last_name': 'Rossi', 'code': 'EXT-ALFA'}})[0], 409)
        config = self.root.request(self.numbering())[1]
        config['prefix'] = 'CHANGED-'
        self.assertEqual(self.root.request(self.numbering(), 'PUT', config)[0], 409)

    def test_06_search_name_code_tax_contact_and_literal_wildcards(self):
        row = self.create('Ricambi % cento',
                          taxIdentifiers=[{'country_code': 'FR', 'identifier_type': 'FOREIGN_TAX_ID', 'value': 'FR999888'}],
                          contactChannels=[{'channel_type': 'EMAIL', 'value': 'unique@example.invalid', 'is_primary': True}])
        for term in ('Ricambi', row['code'], 'FR999888', 'unique@example.invalid', '%'):
            status, results = self.root.request(self.path()+f'&search={__import__("urllib.parse", fromlist=["quote"]).quote(term)}')
            self.assertEqual(status, 200)
            self.assertEqual([item['id'] for item in results['items']], [row['id']], term)
        self.assertEqual(self.root.request(self.path()+'&search=_nonexistent_')[1]['total'], 0)

    def test_07_duplicate_address_defaults_and_bad_channels_are_atomic(self):
        row = self.create()
        address = {'street': 'Via Uno', 'city': 'Roma', 'postal_code': '00100', 'country_code': 'IT',
                   'usages': [{'usage': 'BILLING', 'is_default': True}]}
        before = self.read(row)
        status, _ = self.update(row, {'legal_name': 'Non deve cambiare'}, addresses=[address, copy.deepcopy(address)])
        self.assertIn(status, (400, 409))
        self.assertEqual(self.read(row), before)
        status, _ = self.update(row, contactChannels=[{'channel_type': 'EMAIL', 'value': 'not-an-email', 'is_primary': True}])
        self.assertEqual(status, 400)
        self.assertEqual(self.read(row), before)

    def test_08_concurrent_allocations_are_unique(self):
        def create_one(index):
            client = Client()
            self.assertEqual(client.login(self.credentials)[0], 200)
            return client.request(self.path('/save'), 'POST', {
                'values': {'kind': 'ORGANIZATION', 'legal_name': f'Concorrente {index}'}})
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(create_one, range(4)))
        self.assertTrue(all(status == 201 for status, _ in results), results)
        codes = [row['code'] for _, row in results]
        self.assertEqual(len(set(codes)), 4)
        self.assertEqual(set(codes), {f'BP-{number:06}' for number in range(1, 5)})
        self.assertEqual(self.root.request(self.numbering())[1]['nextNumber'], 5)

    def actor(self, permissions):
        def create(resource, values):
            status, row = self.root.request(f'/api/data/{resource}?tenantId={self.tenant_id}', 'POST', values)
            self.assertEqual(status, 201, row)
            return row
        username = 'actor-'+uuid.uuid4().hex[:8]
        user = create('users', {'username': username, 'first_name': 'Mario', 'last_name': 'Prova', 'email': 'actor@example.invalid'})
        role = create('roles', {'name': 'Ruolo prova'})
        catalog = []
        for page in range(1, 1001):
            status, result = self.root.request(f'/api/data/permissions?tenantId={self.tenant_id}&pageSize=100&page={page}')
            self.assertEqual(status, 200, result)
            catalog.extend(result['items'])
            if len(catalog) >= result['total']:break
        self.assertEqual(len(catalog), result['total'])
        ids = [r['id'] for r in catalog if r['code'] in permissions]
        self.assertEqual(len(ids), len(permissions))
        for link, owner, targets in [('user-roles', user['id'], [role['id']]), ('role-permissions', role['id'], ids)]:
            self.assertEqual(self.root.request(f'/api/links/{link}/{owner}?tenantId={self.tenant_id}', 'PUT', {'ids': targets})[0], 204)
        initial = uuid.uuid4().hex+'-Initial!'
        self.assertEqual(self.root.request(f'/api/users/{user["id"]}/password?tenantId={self.tenant_id}', 'PUT', {'newPassword': initial})[0], 204)
        client = Client()
        self.assertEqual(client.login({'username': username, 'password': initial}, self.code)[0], 200)
        self.assertEqual(client.request('/api/auth/password', 'PUT', {'currentPassword': initial, 'newPassword': uuid.uuid4().hex+'-Updated!'})[0], 204)
        client.token = None
        return client, role

    def test_09_permissions_are_independent_and_revocation_is_immediate(self):
        reader, role = self.actor(['business-partners.read'])
        self.assertEqual(reader.request(self.path())[0], 200)
        self.assertEqual(reader.request(self.numbering())[0], 403)
        self.assertEqual(reader.request(self.path('/save'), 'POST', {'values': {'kind': 'ORGANIZATION', 'legal_name': 'Negato'}})[0], 403)
        self.assertEqual(self.root.request(f'/api/links/role-permissions/{role["id"]}?tenantId={self.tenant_id}', 'PUT', {'ids': []})[0], 204)
        self.assertEqual(reader.request(self.path())[0], 403)
        creator, _ = self.actor(['business-partners.create'])
        self.assertEqual(creator.request(self.path())[0], 403)
        self.assertEqual(creator.request(self.numbering())[0], 403)
        self.assertEqual(creator.request(self.path('/save'), 'POST', {'values': {'kind': 'ORGANIZATION', 'legal_name': 'Solo creazione'}})[0], 201)

    def test_11_audit_commit_failure_rolls_back_entire_aggregate(self):
        from run_business_partner_proof import sql
        row = self.create()
        before = self.read(row)
        config = self.root.request(self.numbering())[1]
        sql("CREATE FUNCTION foundation.bp_proof_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.resource='business-partners' AND NEW.tenant_id='{self.tenant_id}'::uuid THEN "
            "RAISE EXCEPTION 'Rifiuto audit fixture'; END IF; RETURN NEW; END $$; "
            "CREATE CONSTRAINT TRIGGER bp_proof_reject_audit AFTER INSERT ON foundation.audit_event "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.bp_proof_reject_audit();")
        try:
            status, result = self.update(row, {'legal_name': 'Non committata'},
                                         contactChannels=[{'channel_type': 'EMAIL', 'value': 'rollback@example.invalid'}])
            self.assertEqual(status, 500, result)
            self.assertEqual(self.read(row), before)
            status, result = self.root.request(self.path('/save'), 'POST', {
                'values': {'kind': 'ORGANIZATION', 'legal_name': 'Nuova non committata'}})
            self.assertEqual(status, 500, result)
            self.assertEqual(self.root.request(self.numbering())[1], config)
            self.assertEqual(self.root.request(self.path())[1]['total'], 1)
        finally:
            sql('DROP TRIGGER bp_proof_reject_audit ON foundation.audit_event; DROP FUNCTION foundation.bp_proof_reject_audit();')

    def test_12_invalid_transport_and_shape_leave_state_unchanged(self):
        row = self.create()
        before = self.read(row)
        for values in ({'legal_name': '\ud800'}, {'legal_name': 'NUL\0'}, {'kind': 'UNKNOWN'}, {'unexpected': True}):
            status, result = self.update(row, values)
            self.assertEqual(status, 400, result)
            self.assertEqual(self.read(row), before)
        for field in ('taxIdentifiers', 'addresses', 'contactChannels'):
            status, result = self.update(row, **{field: None})
            self.assertEqual(status, 400, result)
            self.assertEqual(self.read(row), before)

    def test_10_csrf_and_generic_mutation_bypasses_are_refused(self):
        body = {'values': {'kind': 'ORGANIZATION', 'legal_name': 'Prova'}}
        self.assertIn(self.root.request(self.path('/save'), 'POST', body, csrf=False)[0], (400, 403))
        self.assertEqual(self.root.request(self.path('/save'), 'POST', body, origin='https://foreign.invalid')[0], 403)
        row = self.create()
        status, _ = self.root.request(self.path('/'+row['id']), 'PUT', {'legal_name': 'Bypass'})
        self.assertIn(status, (400, 403, 405, 409))
        self.assertEqual(self.read(row)['legal_name'], row['legal_name'])
        self.assertIn(self.root.request(self.path('/'+row['id']), 'DELETE')[0], (403, 405, 409))


if __name__ == '__main__':
    unittest.main()
