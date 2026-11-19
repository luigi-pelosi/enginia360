"""Fase 2: HTTP autentico isolato, ruoli commerciali e autorità aziendale legata al ruolo."""
import concurrent.futures
import unittest
import uuid

import browser_business_partners as proof
from test_api import Client


class BusinessPartnerCompanyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        proof.BusinessPartnerTests.setUpClass()

    def setUp(self):
        self.case = proof.BusinessPartnerTests('test_01_metadata_and_default_automatic_numbering')
        self.case.setUp()
        self.root = self.case.root
        self.tenant = self.case.tenant_id
        self.a = self.create('companies', {'name': 'Service ' + self.case.code})
        self.b = self.create('companies', {'name': 'Trading ' + self.case.code})
        self.bp = self.case.create('Alfa Ricambi ' + self.case.code)

    def scope(self, path, tenant=None):
        return path + ('&' if '?' in path else '?') + 'tenantId=' + (tenant or self.tenant)

    def create(self, resource, body):
        status, row = self.root.request(self.scope('/api/data/' + resource), 'POST', body)
        self.assertEqual(status, 201, row)
        return row

    def endpoint(self, company=None, partner=None):
        return '/api/companies/' + (company or self.a)['id'] + '/business-partners' + ('/' + partner['id'] if partner else '')

    def associate(self, company=None, roles=None):
        status, row = self.root.request(self.scope(self.endpoint(company)), 'POST', {
            'businessPartnerId': self.bp['id'], 'roles': roles if roles is not None else ['CUSTOMER', 'SUPPLIER']})
        self.assertEqual(status, 201, row)
        return row

    def assign_companies(self, role, companies):
        status, body = self.root.request(self.scope('/api/roles/' + role['id'] + '/companies'), 'PUT', {'companyIds': [row['id'] for row in companies]})
        self.assertIn(status, (200, 204), body)

    def role(self, codes, companies):
        role = self.create('roles', {'name': 'Ruolo ' + uuid.uuid4().hex[:8]})
        catalog = self.root.request(self.scope('/api/data/permissions?pageSize=100'))[1]['items']
        ids = [row['id'] for row in catalog if row['code'] in codes]
        self.assertEqual(len(ids), len(codes), 'Catalogo permessi della fase 2 incompleto')
        self.assertEqual(self.root.request(self.scope('/api/links/role-permissions/' + role['id']), 'PUT', {'ids': ids})[0], 204)
        self.assign_companies(role, companies)
        return role

    def role_change(self, relation, role, status, company=None, client=None):
        return (client or self.root).request(self.scope(self.endpoint(company, self.bp) + '/roles/' + role), 'PUT', {'status': status, 'expectedVersion': relation['version']})

    def test_13_all_companies_default_includes_blocked_roles_and_relations(self):
        service = self.associate()
        trading = self.associate(self.b, ['SUPPLIER'])
        self.assertEqual(self.root.request(self.scope(self.endpoint(self.b,self.bp)), 'PATCH', {'status':'BLOCKED','expectedVersion':trading['version']})[0], 200)
        self.assertEqual(self.role_change(service, 'CUSTOMER', 'BLOCKED')[0], 200)
        path = '/api/business-partner-companies?search=' + self.case.code
        status, result = self.root.request(self.scope(path))
        self.assertEqual(status, 200, result)
        self.assertEqual(result['total'], 2)
        self.assertEqual({row['company_id'] for row in result['items']}, {self.a['id'], self.b['id']})
        self.assertEqual({row['company_name'] for row in result['items']}, {self.a['name'], self.b['name']})
        a = next(row for row in result['items'] if row['company_id'] == self.a['id'])
        self.assertEqual({role['role_code'] for role in a['roles']}, {'CUSTOMER', 'SUPPLIER'})
        self.assertEqual(next(role['status'] for role in a['roles'] if role['role_code']=='CUSTOMER'), 'BLOCKED')
        self.assertEqual(next(row['status'] for row in result['items'] if row['company_id']==self.b['id']), 'BLOCKED')
        filtered = self.root.request(self.scope(path+'&role=CUSTOMER&usableOnly=true'))
        self.assertEqual(filtered[0], 200, filtered)
        self.assertEqual(filtered[1]['total'], 0)
        status, first = self.root.request(self.scope(path+'&pageSize=1&page=1'))
        status2, second = self.root.request(self.scope(path+'&pageSize=1&page=2'))
        self.assertEqual((status, status2), (200, 200))
        self.assertEqual(first['total'], 2)
        self.assertNotEqual(first['items'][0]['id'], second['items'][0]['id'])
        for invalid in ('&role=UNKNOWN','&role=CUSTOMER&role=SUPPLIER','&usableOnly=1','&pageSize=101','&page=0'):
            self.assertEqual(self.root.request(self.scope(path+invalid))[0], 400, invalid)

    def test_14_all_companies_reads_only_exact_scopes_and_revocations(self):
        self.associate(); self.associate(self.b)
        actor, reader = self.case.actor(['business-partners.read','business-partner-companies.read'])
        self.assign_companies(reader, [self.a])
        writer = self.role(['business-partner-companies.update'], [self.b])
        user = actor.request('/api/session')[1]['id']
        self.assertEqual(self.root.request(self.scope('/api/links/user-roles/'+user), 'PUT', {'ids':[reader['id'],writer['id']]})[0], 204)
        path = self.scope('/api/business-partner-companies?search='+self.case.code)
        status, result = actor.request(path)
        self.assertEqual(status, 200, result)
        self.assertEqual(result['total'], 1)
        self.assertEqual({row['company_id'] for row in result['items']}, {self.a['id']})
        self.assertEqual(actor.request(self.scope(self.endpoint(self.b)))[0], 403)
        self.assign_companies(reader, [])
        status, result = actor.request(path)
        self.assertEqual(status, 200, result)
        self.assertEqual(result['total'], 0)
        self.assertEqual(result['items'], [])
        self.assertEqual(self.root.request('/api/business-partner-companies')[0], 400)
        for codes in (['business-partners.read'], ['business-partner-companies.read']):
            denied, role = self.case.actor(codes)
            self.assign_companies(role, [self.a])
            self.assertEqual(denied.request(path)[0], 403)
        other_status, other_tenant = self.root.request('/api/data/tenants', 'POST', {'name':'Other '+self.case.code,'code':'other-'+uuid.uuid4().hex[:8]})
        self.assertEqual(other_status, 201, other_tenant)
        self.assertEqual(actor.request('/api/business-partner-companies?tenantId='+other_tenant['id'])[0], 403)

    def test_01_same_identity_multiple_roles_and_companies(self):
        service = self.associate()
        trading = self.associate(self.b, ['SUPPLIER'])
        self.assertEqual({role['role_code'] for role in service['roles']}, {'CUSTOMER', 'SUPPLIER'})
        self.assertEqual({role['role_code'] for role in trading['roles']}, {'SUPPLIER'})
        status, result = self.root.request(self.scope('/api/data/business-partners/' + self.bp['id'] + '/companies'))
        self.assertEqual(status, 200, result)
        self.assertEqual({row['company_id'] for row in result['items']}, {self.a['id'], self.b['id']})
        status, _ = self.root.request(self.scope(self.endpoint()), 'POST', {'businessPartnerId': self.bp['id'], 'roles': ['CUSTOMER']})
        self.assertEqual(status, 409)
        self.assertEqual(self.case.read(self.bp)['version'], self.bp['version'])

    def test_02_role_and_relation_blocks_are_independent_and_keep_ids(self):
        a = self.associate()
        b = self.associate(self.b, ['SUPPLIER'])
        ids = {role['role_code']: role['id'] for role in a['roles']}
        status, changed = self.role_change(a, 'CUSTOMER', 'BLOCKED')
        self.assertEqual(status, 200, changed)
        self.assertEqual(set(changed['usable_roles']), {'SUPPLIER'})
        self.assertEqual({role['role_code']: role['id'] for role in changed['roles']}, ids)
        status, active = self.role_change(changed, 'CUSTOMER', 'ACTIVE')
        self.assertEqual(status, 200, active)
        self.assertEqual({role['role_code']: role['id'] for role in active['roles']}, ids)
        status, blocked = self.root.request(self.scope(self.endpoint(partner=self.bp)), 'PATCH', {'status': 'BLOCKED', 'expectedVersion': active['version']})
        self.assertEqual(status, 200, blocked)
        self.assertEqual(blocked['usable_roles'], [])
        status, other = self.root.request(self.scope(self.endpoint(self.b, self.bp)))
        self.assertEqual(status, 200, other)
        self.assertEqual(other['version'], b['version'])
        self.assertEqual(other['usable_roles'], ['SUPPLIER'])
        self.assertEqual({role['role_code']: role['id'] for role in blocked['roles']}, ids)

    def test_03_global_partner_company_and_tenant_state_gate_eligibility(self):
        relation = self.associate()
        for state in ('DRAFT', 'BLOCKED', 'ARCHIVED', 'ACTIVE'):
            current = self.case.read(self.bp)
            self.assertEqual(self.case.update(current, {'status': state})[0], 200)
            status, result = self.root.request(self.scope(self.endpoint(partner=self.bp)))
            self.assertEqual(status, 200)
            self.assertEqual(set(result['usable_roles']), {'CUSTOMER', 'SUPPLIER'} if state == 'ACTIVE' else set())
        self.assertEqual(self.root.request(self.scope('/api/data/companies/' + self.a['id']), 'PUT', {'is_enabled': False})[0], 200)
        status, historical = self.root.request(self.scope(self.endpoint(partner=self.bp)))
        self.assertEqual(status, 200)
        self.assertEqual(historical['usable_roles'], [])
        self.assertEqual(historical['id'], relation['id'])

    def test_04_exact_permission_cannot_cross_product_company_scopes(self):
        a = self.associate()
        self.associate(self.b)
        actor, edit_role = self.case.actor(['business-partners.read', 'business-partner-companies.read', 'business-partner-companies.update', 'business-partner-companies.use_supplier'])
        self.assign_companies(edit_role, [self.a])
        read_role = self.role(['business-partners.read', 'business-partner-companies.read'], [self.b])
        user_id = actor.request('/api/session')[1]['id']
        self.assertEqual(self.root.request(self.scope('/api/links/user-roles/' + user_id), 'PUT', {'ids': [edit_role['id'], read_role['id']]})[0], 204)
        status, service = actor.request(self.scope(self.endpoint(partner=self.bp)))
        self.assertEqual(status, 200, service)
        self.assertEqual(service['usable_roles'], ['SUPPLIER'])
        status, trading = actor.request(self.scope(self.endpoint(self.b, self.bp)))
        self.assertEqual(status, 200, trading)
        self.assertEqual(trading['usable_roles'], [])
        self.assertEqual(self.role_change(trading, 'CUSTOMER', 'BLOCKED', self.b, actor)[0], 403)
        self.assertEqual(self.role_change(a, 'CUSTOMER', 'BLOCKED', client=actor)[0], 200)
        options = actor.request(self.scope('/api/business-partner-companies/options'))
        self.assertEqual(options[0], 200)
        by_id = {row['id']: set(row['permissions']) for row in options[1]['items']}
        self.assertIn('update', by_id[self.a['id']])
        self.assertNotIn('update', by_id[self.b['id']])
        self.assign_companies(edit_role, [])
        self.assertEqual(actor.request(self.scope(self.endpoint(partner=self.bp)))[0], 403)
        self.assertEqual(actor.request(self.scope(self.endpoint(self.b, self.bp)))[0], 200)

    def test_05_no_assignment_deny_group_role_grants_and_revocation(self):
        self.associate()
        actor, own_role = self.case.actor(['business-partners.read', 'business-partner-companies.read', 'business-partner-companies.update'])
        self.assertEqual(actor.request(self.scope(self.endpoint(partner=self.bp)))[0], 403)
        granted = self.role(['business-partner-companies.read', 'business-partner-companies.use_customer'], [self.a])
        group = self.create('groups', {'name': 'Gruppo aziende'})
        user = actor.request('/api/session')[1]['id']
        for kind, owner, targets in [('group-users', group['id'], [user]), ('group-roles', group['id'], [granted['id']])]:
            self.assertEqual(self.root.request(self.scope('/api/links/' + kind + '/' + owner), 'PUT', {'ids': targets})[0], 204)
        status, relation = actor.request(self.scope(self.endpoint(partner=self.bp)))
        self.assertEqual(status, 200, relation)
        self.assertEqual(relation['usable_roles'], ['CUSTOMER'])
        self.assertEqual(self.role_change(relation, 'CUSTOMER', 'BLOCKED', client=actor)[0], 403)
        self.assertEqual(self.root.request(self.scope('/api/data/roles/' + granted['id']), 'PUT', {'is_enabled': False})[0], 200)
        self.assertEqual(actor.request(self.scope(self.endpoint(partner=self.bp)))[0], 403)
        self.assertEqual(self.root.request(self.scope('/api/data/roles/' + granted['id']), 'PUT', {'is_enabled': True})[0], 200)
        self.assertEqual(actor.request(self.scope(self.endpoint(partner=self.bp)))[0], 200)
        self.assertEqual(self.root.request(self.scope('/api/links/group-roles/' + group['id']), 'PUT', {'ids': []})[0], 204)
        self.assertEqual(actor.request(self.scope(self.endpoint(partner=self.bp)))[0], 403)

    def test_06_foreign_tenant_references_are_rejected_atomically(self):
        foreign = self.root.request('/api/data/tenants', 'POST', {'name': 'Altro tenant', 'code': 'foreign-' + uuid.uuid4().hex[:8]})[1]
        other = self.root.request(self.scope('/api/data/business-partners/save', foreign['id']), 'POST', {'values': {'kind': 'ORGANIZATION', 'legal_name': 'BP altro tenant'}})[1]
        status, _ = self.root.request(self.scope(self.endpoint()), 'POST', {'businessPartnerId': other['id'], 'roles': ['CUSTOMER']})
        self.assertIn(status, (400, 403, 404))
        self.assertEqual(self.root.request(self.scope(self.endpoint()))[1]['total'], 0)
        role = self.create('roles', {'name': 'Ruolo confini'})
        company = self.root.request(self.scope('/api/data/companies', foreign['id']), 'POST', {'name': 'Azienda altro tenant'})[1]
        status, _ = self.root.request(self.scope('/api/roles/' + role['id'] + '/companies'), 'PUT', {'companyIds': [self.a['id'], company['id']]})
        self.assertIn(status, (400, 403, 404))
        self.assertEqual(self.root.request(self.scope('/api/roles/' + role['id'] + '/companies'))[1]['companyIds'], [])
        actor, scoped_role = self.case.actor(['business-partners.read', 'business-partner-companies.read'])
        self.assign_companies(scoped_role, [self.a])
        self.assertEqual(actor.request(self.scope(self.endpoint(), foreign['id']))[0], 403)

    def test_07_concurrent_role_commands_use_one_revision(self):
        relation = self.associate()
        def update(code):
            client = Client()
            self.assertEqual(client.login(self.case.credentials)[0], 200)
            return self.role_change(relation, code, 'BLOCKED', client=client)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, ('CUSTOMER', 'SUPPLIER')))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        status, current = self.root.request(self.scope(self.endpoint(partner=self.bp)))
        self.assertEqual(status, 200)
        self.assertEqual(current['version'], relation['version'] + 1)
        self.assertEqual(sum(role['status'] == 'BLOCKED' for role in current['roles']), 1)

    def test_08_filters_and_invalid_shapes_preserve_history(self):
        relation = self.associate()
        for role, status in [('CUSTOMER', 'BLOCKED'), ('SUPPLIER', 'ACTIVE')]:
            response, relation = self.role_change(relation, role, status)
            self.assertEqual(response, 200)
        for role, expected in [('CUSTOMER', 0), ('SUPPLIER', 1)]:
            status, result = self.root.request(self.scope(self.endpoint() + '?role=' + role + '&usableOnly=true&search=Alfa&page=1&pageSize=1'))
            self.assertEqual(status, 200, result)
            self.assertEqual(result['total'], expected)
        before = self.root.request(self.scope(self.endpoint(partner=self.bp)))[1]
        for code in ('PROSPECT', 'UNKNOWN'):
            self.assertEqual(self.role_change(before, code, 'ACTIVE')[0], 400)
        for body in ({'status': 'WRONG', 'expectedVersion': before['version']}, {'status': 'ACTIVE'}, {'status': 'ACTIVE', 'expectedVersion': 0}, {'status': 'ACTIVE', 'expectedVersion': before['version'], 'companyId': self.b['id']}):
            self.assertEqual(self.root.request(self.scope(self.endpoint(partner=self.bp)), 'PATCH', body)[0], 400)
        self.assertEqual(self.root.request(self.scope(self.endpoint(partner=self.bp)))[1], before)
        self.assertIn(self.root.request(self.scope(self.endpoint(partner=self.bp)), 'DELETE')[0], (404, 405, 409))

    def test_09_csrf_and_assignment_authority_are_independent(self):
        relation = self.associate()
        change = {'status': 'BLOCKED', 'expectedVersion': relation['version']}
        relation_path = self.scope(self.endpoint(partner=self.bp))
        self.assertIn(self.root.request(relation_path, 'PATCH', change, csrf=False)[0], (400, 403))
        self.assertEqual(self.root.request(relation_path, 'PATCH', change, origin='https://foreign.invalid')[0], 403)
        self.assertEqual(self.root.request(relation_path)[1], relation)
        role = self.create('roles', {'name': 'Ruolo sicuro'})
        path = self.scope('/api/roles/' + role['id'] + '/companies')
        body = {'companyIds': [self.a['id']]}
        self.assertIn(self.root.request(path, 'PUT', body, csrf=False)[0], (400, 403))
        self.assertEqual(self.root.request(path, 'PUT', body, origin='https://foreign.invalid')[0], 403)
        actor, _ = self.case.actor(['roles.read', 'roles.update', 'companies.read'])
        self.assertEqual(actor.request(path, 'PUT', body)[0], 403)
        self.assertEqual(self.root.request(path)[1]['companyIds'], [])
        self.assertEqual(Client().request(path)[0], 401)

    def test_10_deferred_audit_failure_rolls_back_relation_and_scope(self):
        from run_business_partner_proof import sql
        relation = self.associate()
        role = self.role(['business-partner-companies.read'], [self.a])
        function = 'bp_phase2_reject_' + uuid.uuid4().hex[:8]
        sql(f"CREATE FUNCTION foundation.{function}() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'phase2 audit failure'; END$$; "
            f"CREATE CONSTRAINT TRIGGER {function} AFTER INSERT ON foundation.audit_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.{function}();")
        try:
            status, _ = self.role_change(relation, 'CUSTOMER', 'BLOCKED')
            self.assertEqual(status, 500)
            self.assertEqual(self.root.request(self.scope(self.endpoint(partner=self.bp)))[1], relation)
            path = self.scope('/api/roles/' + role['id'] + '/companies')
            status, _ = self.root.request(path, 'PUT', {'companyIds': [self.b['id']]})
            self.assertEqual(status, 500)
            self.assertEqual(self.root.request(path)[1]['companyIds'], [self.a['id']])
        finally:
            sql(f'DROP TRIGGER {function} ON foundation.audit_event; DROP FUNCTION foundation.{function}();')

    def test_11_concurrent_association_creates_only_one_history(self):
        def associate(_):
            client = Client()
            self.assertEqual(client.login(self.case.credentials)[0], 200)
            return client.request(self.scope(self.endpoint()), 'POST', {'businessPartnerId': self.bp['id'], 'roles': ['CUSTOMER', 'SUPPLIER']})
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(associate, range(2)))
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        status, listing = self.root.request(self.scope(self.endpoint()))
        self.assertEqual(status, 200)
        self.assertEqual(listing['total'], 1)
        self.assertEqual(len(listing['items'][0]['roles']), 2)

    def test_12_eligibility_endpoint_requires_exact_use_and_resolves_ids(self):
        relation = self.associate()
        actor, role = self.case.actor(['business-partners.read', 'business-partner-companies.read', 'business-partner-companies.use_supplier'])
        self.assign_companies(role, [self.a])
        path = self.scope(self.endpoint(partner=self.bp) + '/eligibility/SUPPLIER')
        self.assertEqual(actor.request(path), (200, {'usable': True}))
        self.assertEqual(actor.request(path.replace('/SUPPLIER', '/CUSTOMER'))[0], 403)
        self.assertEqual(actor.request(path.replace(self.a['id'], self.b['id']))[0], 403)
        missing = str(uuid.uuid4())
        self.assertEqual(actor.request(path.replace(self.bp['id'], missing)), (200, {'usable': False}))
        self.assertEqual(self.role_change(relation, 'SUPPLIER', 'BLOCKED')[0], 200)
        self.assertEqual(actor.request(path), (200, {'usable': False}))
        self.assertEqual(self.root.request('/api/data/tenants/'+self.tenant, 'PUT', {'is_enabled': False})[0], 200)
        try:
            self.assertEqual(self.root.request(path), (200, {'usable': False}))
            self.assertEqual(actor.request(path)[0], 401)
        finally:
            self.assertEqual(self.root.request('/api/data/tenants/'+self.tenant, 'PUT', {'is_enabled': True})[0], 200)


if __name__ == '__main__':
    unittest.main(verbosity=2)
