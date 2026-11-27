"""Real HTTP journeys for mandatory registration profiles and fiscal-root CF.

Only the exact labelled disposable fixture is writable. No synthetic API bodies;
SQL is limited to authoritative readback and a tenant-bounded deferred audit fault.
"""
from copy import deepcopy
import unittest
import uuid

from test_company_tax_http import CompanyTaxHttp as Harness, PREFIX
from test_company_identity_http import CompanyIdentityHttp


class CompanyTaxRequiredHttp(unittest.TestCase):
    setUpClass = classmethod(Harness.setUpClass.__func__)
    setUp = Harness.setUp
    actor = Harness.actor
    path = Harness.path
    scope = Harness.scope
    req = Harness.req
    sql = Harness.sql
    company_create = Harness.company_create
    company_read = Harness.company_read
    list_route = Harness.list_route
    route = Harness.route
    identifier = Harness.identifier
    profile = Harness.profile
    registration = Harness.registration
    foreign_registration = Harness.foreign_registration
    payload = Harness.payload
    create = Harness.create
    read = Harness.read
    command = Harness.command
    assign_companies = Harness.assign_companies
    catalog_flag = Harness.catalog_flag
    save = CompanyIdentityHttp.save

    def snapshot(self):
        tables = ('foundation.company', 'taxmanagement.company_tax_configurations',
                  'taxmanagement.company_tax_registrations', 'taxmanagement.company_tax_regime_profiles',
                  'foundation.audit_event')
        # Full rows, not only counts: a failed command must not mutate prior roots.
        return {table: self.sql("SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY r.id),'[]'::jsonb) FROM " + table + " r WHERE tenant_id='" + self.tenant_id + "';") for table in tables}

    def edit_cf(self, root, value, expected=200, client=None, **envelope):
        return self.req(self.route(root), 'PUT', {'values': {'tax_code': value}, 'expectedVersion': root['version'], **envelope}, expected, client=client)

    def invalid_initials(self):
        good = self.payload(tax_code='  root CF  ')
        missing = deepcopy(good)
        del missing['registrations']
        no_profiles = deepcopy(good)
        del no_profiles['registrations'][0]['profiles']
        empty_profiles = deepcopy(good)
        empty_profiles['registrations'][0]['profiles'] = []
        null_profiles = deepcopy(good)
        null_profiles['registrations'][0]['profiles'] = None
        wrong = deepcopy(good)
        wrong['registrations'][0]['profiles'][0]['tax_regime_id'] = next(r['id'] for r in self.refs['regimes'] if r['country_id'] != self.country_id and r['is_supported'])
        outside = deepcopy(good)
        outside['registrations'][0]['profiles'][0]['valid_from'] = '2026-11-25'
        second_incomplete = deepcopy(good)
        second_incomplete['registrations'].append(self.foreign_registration(profiles=False))
        return [missing, {**good, 'registrations': []}, {**good, 'registrations': None},
                no_profiles, empty_profiles, null_profiles, wrong, outside, second_incomplete]

    def test_required_initial_chain_rejections_are_atomic_no_rows(self):
        before = self.snapshot()
        for payload in self.invalid_initials():
            with self.subTest(payload=payload):
                self.req(self.list_route(), 'POST', payload, 400)
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.req(self.list_route())['items'], [])
        self.catalog_flag('is_supported', False)
        try:
            self.create(expected=409)
            self.assertEqual(self.snapshot(), before)
        finally:
            self.catalog_flag('is_supported', True)
        root = self.create(tax_code='  CF é漢😀  ')
        self.assertEqual((root['tax_code'], root['status'], root['version']), ('CF é漢😀', 'DRAFT', 1))
        self.assertEqual((len(root['registrations']), len(root['registrations'][0]['profiles'])), (1, 1))
        self.assertEqual(self.read(root), root)
        root = self.command(root, 'registrations', self.foreign_registration(), 201)
        extra = next(r for r in root['registrations'] if r['country_id'] == self.countries['DE']['id'])
        self.assertEqual(len(extra['profiles']), 1)
        self.assertEqual(root['version'], 2)

    def test_every_new_registration_requires_profiles_atomically(self):
        root = self.create()
        registration = self.foreign_registration()
        for shape in ('omitted', 'empty', 'null', 'object'):
            body = deepcopy(registration)
            if shape == 'omitted':
                del body['profiles']
            else:
                body['profiles'] = {'empty': [], 'null': None, 'object': {}}[shape]
            before = self.snapshot()
            with self.subTest(profiles=shape):
                error = self.command(root, 'registrations', body, 400)
                self.assertIn('profiles', str(error))
                if shape in ('omitted', 'empty'):
                    self.assertIn('company_tax_initial_regime_required', str(error))
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.read(root), root)
        audits = int(self.sql("SELECT count(*) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "';"))
        updated = self.command(root, 'registrations', registration, 201)
        self.assertEqual(updated['version'], root['version'] + 1)
        added = next(row for row in updated['registrations'] if row['tax_identifier'] == registration['values']['tax_identifier'])
        self.assertEqual(len(added['profiles']), 1)
        self.assertEqual(self.read(updated), updated)
        self.assertEqual(int(self.sql("SELECT count(*) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "';")), audits + 1)
        before = self.snapshot()
        self.command(root, 'registrations', self.foreign_registration(), 409)
        self.assertEqual(self.snapshot(), before)
        # Keep the existing multiple-temporal-profile payload contract valid.
        other = self.create(company=self.company_create())
        temporal = self.foreign_registration()
        temporal['profiles'][0]['valid_to'] = self.start
        temporal['profiles'].append({**temporal['profiles'][0], 'valid_from': self.future, 'valid_to': None})
        other = self.command(other, 'registrations', temporal, 201)
        added = next(row for row in other['registrations'] if row['tax_identifier'] == temporal['values']['tax_identifier'])
        self.assertEqual(len(added['profiles']), 2)
        self.assertEqual(self.read(other), other)

    def test_register_assign_regime_must_share_scoped_role_and_live_authority(self):
        root = self.create()
        other = self.company_create()
        actor, register_role, _ = self.actor(['companies.read', PREFIX + 'read', PREFIX + 'register'])
        self.assign_companies(register_role, [self.company])
        _, assign_role, _ = self.actor([PREFIX + 'assign_regime'])
        user = actor.request('/api/session')[1]['id']
        self.assertEqual(self.root.request(self.scope('/api/links/user-roles/' + user), 'PUT', {'ids': [register_role['id'], assign_role['id']]})[0], 204)
        # Actions split across scoped roles must not combine, even on the same Company.
        for companies in ([other], [self.company]):
            self.assign_companies(assign_role, companies)
            before = self.snapshot()
            self.command(root, 'registrations', self.foreign_registration(), 403, client=actor)
            self.assertEqual(self.snapshot(), before)
            self.assertNotIn('register', self.req('companies/' + self.company['id'] + '/permissions', client=actor)['permissions'])
        complete, role, _ = self.actor(['companies.read', PREFIX + 'read', PREFIX + 'register', PREFIX + 'assign_regime'])
        self.assign_companies(role, [other])
        before = self.snapshot()
        self.command(root, 'registrations', self.foreign_registration(), 403, client=complete)
        self.assertEqual(self.snapshot(), before)
        self.assign_companies(role, [self.company])
        self.assertIn('register', self.req('companies/' + self.company['id'] + '/permissions', client=complete)['permissions'])
        updated = self.command(root, 'registrations', self.foreign_registration(), 201, client=complete)
        self.assertEqual(updated['version'], root['version'] + 1)
        self.assign_companies(role, [])
        before = self.snapshot()
        self.command(updated, 'registrations', self.foreign_registration(), 403, client=complete)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.read(updated), updated)

    def test_nested_company_initial_post_complete_and_rollback(self):
        before = self.snapshot()
        for payload in self.invalid_initials():
            with self.subTest(payload=payload):
                self.company_create(taxConfigurations=[payload], expected=400)
                self.assertEqual(self.snapshot(), before)
        # A valid first root must also roll back if a later root in the array fails.
        self.company_create(taxConfigurations=[self.payload(), self.invalid_initials()[0]], expected=400)
        self.assertEqual(self.snapshot(), before)
        company = self.company_create(taxConfigurations=[self.payload(tax_code='  Staged CF  ')])
        self.assertNotIn('tax_code', company)
        roots = self.req(self.list_route(company))['items']
        self.assertEqual(len(roots), 1)
        root = roots[0]
        self.assertEqual((root['company_id'], root['tax_code'], root['status'], root['version']), (company['id'], 'Staged CF', 'DRAFT', 1))
        self.assertEqual((len(root['registrations']), len(root['registrations'][0]['profiles'])), (1, 1))
        self.assertEqual(self.read(root), root)
        for configs in ([], [self.payload()]):
            before = self.snapshot()
            status, body = self.root.request(self.scope('/api/data/companies/' + company['id'] + '/save'), 'PUT', {'values': {'name': 'Must not persist'}, 'taxConfigurations': configs})
            self.assertEqual(status, 400, body)
            self.assertEqual(self.snapshot(), before)
        for extra in ({}, {'taxConfigurations': []}):
            plain = self.company_create(**extra)
            self.assertEqual(self.req(self.list_route(plain))['items'], [])

    def test_general_company_rejects_cf_and_site_contract_is_unchanged(self):
        # Preserve the adjacent physical-address and legacy-field negative cases.
        CompanyIdentityHttp.test_metadata_company_cf_only_and_site_no_fiscal_fields(self)
        CompanyIdentityHttp.test_company_general_cf_rejected_on_both_routes_without_changes(self)
        CompanyIdentityHttp.test_site_no_fiscal_gate_address_invariants_and_legacy_payload_rejection(self)

    def test_root_cf_trim_clear_size_strict_envelope_and_stale_version(self):
        root = self.create(tax_code='  CF é漢😀  ')
        self.assertEqual(root['tax_code'], 'CF é漢😀')
        general = self.company_read()
        for value, normalized in [('  Edited CF  ', 'Edited CF'), (' \t\n ', None), ('\u00a0\u2003', None),
                                  (None, None), ('é' * 500, 'é' * 500), ('😀' * 250, '😀' * 250)]:
            old = root
            root = self.edit_cf(root, value)
            self.assertEqual((root['tax_code'], root['version']), (normalized, old['version'] + 1))
            self.assertEqual(root['registrations'], old['registrations'])
            self.assertEqual(self.read(root), root)
            self.edit_cf(old, 'Stale must not persist', expected=409)
            self.assertEqual(self.read(root), root)
        for invalid in ('x' * 501, 'é' * 501, '😀' * 251, ' ' * 501, 'bad\x00value', 123, [], {}):
            before = self.snapshot()
            self.edit_cf(root, invalid, expected=400)
            self.assertEqual(self.snapshot(), before)
        bad_envelopes = [{'expectedVersion': root['version'], 'values': {}},
                         {'expectedVersion': root['version'], 'values': {'tax_code': None, 'status': 'ACTIVE'}},
                         {'expectedVersion': root['version'], 'values': {'tax_code': None}, 'surprise': True},
                         {'values': {'tax_code': None}}]
        bad_envelopes += [{'expectedVersion': v, 'values': {'tax_code': None}} for v in (0, -1, 1.5, '1', None, 9007199254740992)]
        for body in bad_envelopes:
            before = self.snapshot()
            self.req(self.route(root), 'PUT', body, 400)
            self.assertEqual(self.snapshot(), before)
        # Create follows the same policy, including omitted/blank/null and max size.
        for value, normalized in [(None, None), ('  ', None), ('é' * 500, 'é' * 500), ('CF é漢😀', 'CF é漢😀')]:
            other = self.create(company=self.company_create(), tax_code=value)
            self.assertEqual(other['tax_code'], normalized)
        omitted = self.create(company=self.company_create())
        self.assertIsNone(omitted['tax_code'])
        for invalid in ('x' * 501, ' ' * 501, 123, [], {}, 'bad\x00value'):
            company = self.company_create()
            before = self.snapshot()
            self.create(company=company, tax_code=invalid, expected=400)
            self.assertEqual(self.snapshot(), before)
        # CF has no uniqueness/checksum/case-fold relation with VAT identifiers.
        duplicate = self.create(company=self.company_create(), tax_code=root['tax_code'])
        self.assertEqual(duplicate['tax_code'], root['tax_code'])
        self.assertEqual(self.company_read(), general)
        self.assertNotIn('tax_code', general)

    def test_update_own_permission_same_role_scope_and_complete_create_permissions(self):
        root = self.create()
        other = self.company_create()
        actor, read_role, _ = self.actor(['companies.read', 'companies.update', PREFIX + 'read', PREFIX + 'create'])
        self.assign_companies(read_role, [self.company])
        self.edit_cf(root, 'Denied generic update/create', expected=403, client=actor)
        _, write_role, _ = self.actor([PREFIX + 'update'])
        self.assign_companies(write_role, [other])
        status, session = actor.request('/api/session')
        self.assertEqual(status, 200, session)
        self.assertEqual(self.root.request(self.scope('/api/links/user-roles/' + session['id']), 'PUT', {'ids': [read_role['id'], write_role['id']]})[0], 204)
        self.edit_cf(root, 'Denied crossed union', expected=403, client=actor)
        self.assertNotIn('update', self.req('companies/' + self.company['id'] + '/permissions', client=actor)['permissions'])
        self.assign_companies(write_role, [self.company])
        # No companies.update on this writer role; only the fiscal permission matters.
        root = self.edit_cf(root, 'Fiscal-only permission', client=actor)
        self.assertIn('update', self.req('companies/' + self.company['id'] + '/permissions', client=actor)['permissions'])
        self.assign_companies(write_role, [])
        self.edit_cf(root, 'Revoked must not persist', expected=403, client=actor)
        no_general, role, _ = self.actor([PREFIX + 'read', PREFIX + 'update'])
        self.assign_companies(role, [self.company])
        self.edit_cf(root, 'No companies.read', expected=403, client=no_general)
        independent, role, _ = self.actor(['companies.read', PREFIX + 'read', PREFIX + 'update'])
        self.assign_companies(role, [self.company])
        root = self.edit_cf(root, 'No companies.update needed', client=independent)
        for missing in ('create', 'register', 'assign_regime'):
            creator, role, _ = self.actor(['companies.read', PREFIX + 'read'] + [PREFIX + a for a in ('create', 'register', 'assign_regime') if a != missing])
            self.assign_companies(role, [other])
            before = self.snapshot()
            self.create(company=other, client=creator, expected=403)
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.read(root)['tax_code'], 'No companies.update needed')
        Harness.test_catalog_readonly_policy_and_permission_catalog(self)

    def test_deferred_audit_failure_rolls_back_create_company_and_cf_update(self):
        root = self.create(tax_code='Before audit fault')
        target = self.company_create()
        before = self.snapshot()
        fault = 'required_proof_' + uuid.uuid4().hex[:12]
        self.sql("CREATE FUNCTION taxmanagement." + fault + "() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.tenant_id='" + self.tenant_id + "'::uuid THEN RAISE EXCEPTION 'synthetic required-chain audit rejection'; END IF; RETURN NEW; END $$; CREATE CONSTRAINT TRIGGER " + fault + " AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION taxmanagement." + fault + "();")
        try:
            self.edit_cf(root, 'Must roll back', expected=500)
            self.assertEqual(self.snapshot(), before)
            self.command(root, 'registrations', self.foreign_registration(), 500)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.read(root), root)
            self.company_create(taxConfigurations=[self.payload(tax_code='Nested rollback')], expected=500)
            self.assertEqual(self.snapshot(), before)
            # Existing company root creation is also atomic at the deferred failure.
            self.create(company=target, tax_code='Direct rollback', expected=500)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.read(root), root)
        finally:
            self.sql('DROP TRIGGER ' + fault + ' ON foundation.audit_event; DROP FUNCTION taxmanagement.' + fault + '();')
        count = int(self.sql("SELECT count(*) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "';"))
        root = self.edit_cf(root, 'After audit recovery')
        self.assertEqual(root['version'], 2)
        self.assertEqual(self.read(root), root)
        self.assertEqual(int(self.sql("SELECT count(*) FROM foundation.audit_event WHERE tenant_id='" + self.tenant_id + "';")), count + 1)
