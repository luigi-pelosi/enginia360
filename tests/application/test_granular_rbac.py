"""Prove HTTP del RBAC granulare, esclusivamente sul cluster isolato dedicato."""
import concurrent.futures
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import unittest
import uuid

from test_api import Client
from test_database_security import sql

ISOLATED = (os.environ.get('ENGINIA360_DB_CONTAINER') == 'enginia360-rbac-db'
            and os.environ.get('ENGINIA360_DB_DATABASE') == 'enginia360_rbac_api'
            and os.environ.get('ENGINIA360_TEST_CREDENTIALS'))


@unittest.skipUnless(ISOLATED, 'Richiede API, credenziali e database RBAC isolati')
class GranularRbacTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.credentials = json.loads(Path(os.environ['ENGINIA360_TEST_CREDENTIALS']).read_text())
        cls.root = Client()
        status, session = cls.root.login(cls.credentials)
        if status != 200 or session['mustChangePassword']:
            raise AssertionError('Predisporre il solo account QA isolato con password definitiva')
        cls.root_id = session['id']

    def setUp(self):
        self.tenants = []
        self.tenant = self.new_tenant()
        # Il fixture prepara un catalogo valido anche contro il backend precedente,
        # così le prove dei gate granulari non falliscono durante la preparazione.
        sql(f"INSERT INTO foundation.permission(tenant_id,code,name,is_system) "
            f"SELECT '{self.tenant['id']}',code,name,true FROM foundation.permission WHERE tenant_id="
            f"(SELECT id FROM foundation.tenant WHERE code='ARIT') AND is_system "
            "ON CONFLICT (tenant_id,code) DO NOTHING;")
        response = self.root.request(self.path('permissions', '?pageSize=100'))
        self.assertEqual(response[0], 200)
        self.catalog = {row['code']: row for row in response[1]['items']}
        self.assertEqual(len(self.catalog), 41)

    def tearDown(self):
        # Solo record nei tenant creati dal fixture, mai nel database reale.
        for tenant in self.tenants:
            value = tenant['id']
            for table in ('role_permission','user_role','user_group_member','user_group_role',
                          'permission','role','user_group','user','company'):
                sql(f'DELETE FROM foundation."{table}" WHERE tenant_id=\'{value}\';')
            sql(f"DELETE FROM foundation.tenant WHERE id='{value}';")

    def new_tenant(self):
        status, tenant = self.root.request('/api/data/tenants', 'POST', {
            'code': 'rbac-' + uuid.uuid4().hex, 'name': 'Verifica RBAC',
        })
        self.assertEqual(status, 201)
        self.tenants.append(tenant)
        return tenant

    def path(self, resource, suffix=''):
        separator = '&' if '?' in suffix else '?'
        return f"/api/data/{resource}{suffix}{separator}tenantId={self.tenant['id']}"

    def links(self, relation, owner):
        return f"/api/links/{relation}/{owner}?tenantId={self.tenant['id']}"

    def create(self, resource, body):
        status, row = self.root.request(self.path(resource), 'POST', body)
        self.assertEqual(status, 201, (resource, status))
        return row

    def replace(self, relation, owner, ids, client=None):
        return (client or self.root).request(self.links(relation, owner), 'PUT', {'ids': ids})

    def role(self, codes=()):
        role = self.create('roles', {'code': 'role-' + uuid.uuid4().hex, 'name': 'Ruolo verifica'})
        self.set_grants(role['id'], codes)
        return role

    def set_grants(self, role, codes):
        self.assertEqual(self.replace('role-permissions', role, [self.catalog[code]['id'] for code in codes])[0], 204)

    def user(self):
        username = 'operator-' + uuid.uuid4().hex[:10]
        return self.create('users', {'username': username, 'first_name': 'Operatore',
                                    'last_name': 'Verifica', 'email': username + '@example.invalid'})

    def login_user(self, user):
        password = secrets.token_urlsafe(24)
        self.assertEqual(self.root.request(f"/api/users/{user['id']}/password?tenantId={self.tenant['id']}",
                                          'PUT', {'newPassword': password})[0], 204)
        client = Client()
        self.assertEqual(client.login({'username': user['username'], 'password': password}, self.tenant['code'])[0], 200)
        changed = secrets.token_urlsafe(24)
        self.assertEqual(client.request('/api/auth/password', 'PUT', {
            'currentPassword': password, 'newPassword': changed,
        })[0], 204)
        client.token = None
        return client

    def actor(self, codes):
        user = self.user()
        role = self.role(codes)
        self.assertEqual(self.replace('user-roles', user['id'], [role['id']])[0], 204)
        return self.login_user(user), user, role

    def company(self):
        return self.create('companies', {'code': uuid.uuid4().hex, 'name': 'Società verifica'})

    def test_new_tenant_receives_catalog_automatically_and_nothing_else(self):
        tenant = self.new_tenant()
        status, data = self.root.request(f"/api/data/permissions?tenantId={tenant['id']}&pageSize=100")
        self.assertEqual(status, 200)
        self.assertEqual(len(data['items']), 41, 'Il nuovo tenant deve ricevere il catalogo applicativo')
        self.assertTrue(all(not row['code'].startswith('tenants.') and not row['code'].endswith('.write') for row in data['items']))
        self.assertEqual(sql(f"SELECT count(*) FROM foundation.user_role WHERE tenant_id='{tenant['id']}';").stdout.strip(), '0')
        self.assertEqual(sql(f"SELECT count(*) FROM foundation.role WHERE tenant_id='{tenant['id']}';").stdout.strip(), '0')

    def test_create_update_delete_are_independent_permissions(self):
        client, _, _ = self.actor(['companies.read', 'companies.create'])
        status, created = client.request(self.path('companies'), 'POST', {'code': 'own', 'name': 'Creazione consentita'})
        self.assertEqual(status, 201, 'companies.create deve autorizzare la creazione senza .write')
        self.assertEqual(client.request(self.path('companies/' + created['id']), 'PUT', {'name': 'Non consentita'})[0], 403)
        self.assertEqual(client.request(self.path('companies/' + created['id']), 'DELETE')[0], 403)
        self.assertEqual(client.request(self.path('companies'))[0], 200)

    def test_update_does_not_require_create_or_delete(self):
        company = self.company()
        client, _, _ = self.actor(['companies.update'])
        self.assertEqual(client.request(self.path('companies/' + company['id']), 'PUT', {'name': 'Aggiornata'})[0], 200)
        self.assertEqual(client.request(self.path('companies'), 'POST', {'code': 'denied', 'name': 'Negata'})[0], 403)
        self.assertEqual(client.request(self.path('companies/' + company['id']), 'DELETE')[0], 403)

    def test_password_reset_is_independent_of_profile_updates(self):
        target = self.user()
        editor, _, _ = self.actor(['users.update'])
        self.assertEqual(editor.request(self.path('users/' + target['id']), 'PUT', {'first_name': 'Aggiornato'})[0], 200)
        path = f"/api/users/{target['id']}/password?tenantId={self.tenant['id']}"
        self.assertEqual(editor.request(path, 'PUT', {'newPassword': secrets.token_urlsafe(24)})[0], 403)
        resetter, _, _ = self.actor(['users.reset_password'])
        self.assertEqual(resetter.request(path, 'PUT', {'newPassword': secrets.token_urlsafe(24)})[0], 204)
        self.assertEqual(resetter.request(self.path('users/' + target['id']), 'PUT', {'first_name': 'Negato'})[0], 403)

    def test_role_assignment_is_independent_of_user_profile_updates(self):
        target, chosen = self.user(), self.role(['companies.read'])
        editor, _, _ = self.actor(['users.read', 'users.update', 'roles.read'])
        self.assertEqual(editor.request(self.path('users/' + target['id']), 'PUT', {'first_name': 'Aggiornato'})[0], 200)
        self.assertEqual(self.replace('user-roles', target['id'], [chosen['id']], editor)[0], 403)
        assigner, _, _ = self.actor(['users.read', 'roles.read', 'roles.assign'])
        self.assertEqual(self.replace('user-roles', target['id'], [chosen['id']], assigner)[0], 204)
        self.assertEqual(assigner.request(self.links('user-roles', target['id']))[1]['ids'], [chosen['id']])
        self.assertEqual(assigner.request(self.path('users/' + target['id']), 'PUT', {'first_name': 'Negato'})[0], 403)

    def test_role_permission_assignment_is_independent_of_role_updates(self):
        target = self.role()
        editor, _, _ = self.actor(['roles.read', 'roles.update', 'permissions.read'])
        self.assertEqual(editor.request(self.path('roles/' + target['id']), 'PUT', {'name': 'Aggiornato'})[0], 200)
        self.assertEqual(self.replace('role-permissions', target['id'], [self.catalog['companies.create']['id']], editor)[0], 403)
        assigner, _, _ = self.actor(['roles.read', 'permissions.read', 'roles.assign_permissions'])
        self.assertEqual(self.replace('role-permissions', target['id'], [self.catalog['companies.create']['id']], assigner)[0], 204)
        self.assertEqual(assigner.request(self.path('roles/' + target['id']), 'PUT', {'name': 'Negato'})[0], 403)

    def test_group_membership_assignment_is_independent_of_group_updates(self):
        group = self.create('groups', {'code': 'operators', 'name': 'Operatori'})
        user = self.user()
        editor, _, _ = self.actor(['groups.update'])
        self.assertEqual(editor.request(self.path('groups/' + group['id']), 'PUT', {'name': 'Aggiornato'})[0], 200)
        self.assertEqual(self.replace('group-users', group['id'], [user['id']], editor)[0], 403)
        assigner, _, _ = self.actor(['groups.read', 'users.read', 'groups.assign_users'])
        self.assertEqual(self.replace('group-users', group['id'], [user['id']], assigner)[0], 204)
        self.assertEqual(assigner.request(self.path('groups/' + group['id']), 'PUT', {'name': 'Negato'})[0], 403)

    def test_catalog_is_read_only_including_super_admin(self):
        before = sql('SELECT count(*) FROM foundation.permission; SELECT count(*) FROM foundation.audit_event;').stdout
        permission = self.catalog['companies.read']
        for method, path, payload in (
            ('POST', self.path('permissions'), {'code': 'arbitrary.write', 'name': 'Inventato'}),
            ('PUT', self.path('permissions/' + permission['id']), {'is_enabled': False}),
            ('DELETE', self.path('permissions/' + permission['id']), None),
        ):
            with self.subTest(method=method):
                self.assertEqual(self.root.request(path, method, payload)[0], 403)
        self.assertEqual(sql('SELECT count(*) FROM foundation.permission; SELECT count(*) FROM foundation.audit_event;').stdout, before)
        resources = self.root.request('/api/resources')[1]
        self.assertTrue(next(r for r in resources if r['key'] == 'permissions')['readOnly'])

    def test_direct_and_group_roles_union_and_revocation_use_fresh_state(self):
        client, user, direct = self.actor(['companies.read'])
        inherited = self.role(['companies.read', 'companies.create'])
        group = self.create('groups', {'code': 'operators', 'name': 'Operatori'})
        self.assertEqual(self.replace('group-users', group['id'], [user['id']])[0], 204)
        self.assertEqual(self.replace('group-roles', group['id'], [inherited['id']])[0], 204)
        self.assertEqual(client.request('/api/session')[1]['permissions'], ['companies.create', 'companies.read'])
        self.set_grants(direct['id'], [])
        self.assertEqual(client.request(self.path('companies'))[0], 200, 'La seconda provenienza mantiene il grant')
        self.assertEqual(self.replace('group-users', group['id'], [])[0], 204)
        self.assertEqual(client.request(self.path('companies'))[0], 403)
        self.assertEqual(client.request('/api/session')[1]['permissions'], [])

    def test_disabled_role_group_permission_and_tenant_remove_access(self):
        client, user, role = self.actor(['companies.read'])
        self.assertEqual(client.request(self.path('companies'))[0], 200)
        self.assertEqual(self.root.request(self.path('roles/' + role['id']), 'PUT', {'is_enabled': False})[0], 200)
        self.assertEqual(client.request(self.path('companies'))[0], 403)
        self.root.request(self.path('roles/' + role['id']), 'PUT', {'is_enabled': True})
        group = self.create('groups', {'code': 'operators', 'name': 'Operatori'})
        self.replace('user-roles', user['id'], [])
        self.replace('group-users', group['id'], [user['id']])
        self.replace('group-roles', group['id'], [role['id']])
        self.assertEqual(client.request(self.path('companies'))[0], 200)
        self.root.request(self.path('groups/' + group['id']), 'PUT', {'is_enabled': False})
        self.assertEqual(client.request(self.path('companies'))[0], 403)
        self.root.request(self.path('groups/' + group['id']), 'PUT', {'is_enabled': True})
        permission = self.catalog['companies.read']['id']
        sql(f"UPDATE foundation.permission SET is_enabled=false WHERE id='{permission}';")
        self.assertEqual(client.request(self.path('companies'))[0], 403)
        sql(f"UPDATE foundation.permission SET is_enabled=true WHERE id='{permission}';")
        self.assertEqual(client.request(self.path('companies'))[0], 200)
        self.root.request('/api/data/tenants/' + self.tenant['id'], 'PUT', {'is_enabled': False})
        self.assertEqual(client.request('/api/session')[0], 401)

    def test_cross_tenant_objects_and_platform_authority_are_refused(self):
        client, user, _ = self.actor(['companies.read', 'companies.update', 'roles.assign', 'roles.assign_permissions', 'groups.assign_users'])
        foreign = self.new_tenant()
        self.assertEqual(client.request(f"/api/data/companies?tenantId={foreign['id']}")[0], 403)
        self.assertEqual(client.request('/api/data/tenants')[0], 403)
        self.assertEqual(client.request('/api/data/tenants', 'POST', {'code': 'not-allowed', 'name': 'Negato'})[0], 403)
        status, role = self.root.request(f"/api/data/roles?tenantId={foreign['id']}", 'POST', {'code': 'foreign', 'name': 'Esterno'})
        self.assertEqual(status, 201)
        self.assertEqual(self.replace('user-roles', user['id'], [role['id']], client)[0], 400)
        self.assertEqual(self.replace('user-roles', self.root_id, [], client)[0], 404)
        self.assertEqual(self.replace('user-roles', user['id'], [role['id']], self.root)[0], 400)
        self.assertEqual(client.request(self.path('users/' + user['id']), 'PUT', {'is_super_admin': True})[0], 403)

    def test_unknown_legacy_permission_never_becomes_effective(self):
        client, _, role = self.actor([])
        permission = str(uuid.uuid4())
        sql(f"INSERT INTO foundation.permission(id,tenant_id,code,name) VALUES ('{permission}','{self.tenant['id']}','companies.write','Storico'); "
            f"INSERT INTO foundation.role_permission(tenant_id,role_id,permission_id) VALUES ('{self.tenant['id']}','{role['id']}','{permission}');")
        self.assertEqual(client.request('/api/session')[1]['permissions'], [])
        self.assertEqual(client.request(self.path('companies'), 'POST', {'code': 'denied', 'name': 'Negato'})[0], 403)
        self.assertEqual(self.root.request(self.links('role-permissions', role['id']))[1]['ids'], [])
        self.assertNotIn(permission, [row['id'] for row in self.root.request(self.path('permissions', '?pageSize=100'))[1]['items']])
        self.assertEqual(self.replace('role-permissions', role['id'], [permission])[0], 400)

    def test_assignment_audit_has_actor_tenant_and_before_after_ids(self):
        role = self.role(['companies.read'])
        read, create = self.catalog['companies.read']['id'], self.catalog['companies.create']['id']
        self.assertEqual(self.replace('role-permissions', role['id'], [create])[0], 204)
        event = json.loads(sql(f"SELECT row_to_json(t) FROM (SELECT actor_id,tenant_id,details FROM foundation.audit_event "
                              f"WHERE resource='role-permissions' AND record_id='{role['id']}' ORDER BY created_at DESC LIMIT 1) t;").stdout)
        self.assertEqual(event['actor_id'], self.root_id)
        self.assertEqual(event['tenant_id'], self.tenant['id'])
        self.assertIsInstance(event['details'], dict, 'Le assegnazioni devono registrare dettagli audit prima/dopo')
        self.assertEqual(event['details']['beforeIds'], [read])
        self.assertEqual(event['details']['afterIds'], [create])
        for forbidden in ('password_hash', 'security_stamp', 'password'):
            self.assertNotIn(forbidden, json.dumps(event))

    def test_audit_failure_rolls_back_permission_assignment(self):
        role = self.role()
        sql("CREATE FUNCTION foundation.rbac_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.resource='role-permissions' AND NEW.record_id='{role['id']}'::uuid THEN "
            "RAISE EXCEPTION 'Fixture audit rollback'; END IF; RETURN NEW; END $$; "
            "CREATE TRIGGER rbac_reject_audit BEFORE INSERT ON foundation.audit_event FOR EACH ROW "
            "EXECUTE FUNCTION foundation.rbac_reject_audit();")
        try:
            self.assertEqual(self.replace('role-permissions', role['id'], [self.catalog['companies.create']['id']])[0], 500)
            self.assertEqual(self.root.request(self.links('role-permissions', role['id']))[1]['ids'], [])
        finally:
            sql('DROP TRIGGER rbac_reject_audit ON foundation.audit_event; DROP FUNCTION foundation.rbac_reject_audit();')

    def test_request_waits_for_grant_revocation_commit_and_uses_fresh_permissions(self):
        client, _, role = self.actor(['companies.read'])
        self.assertEqual(client.request(self.path('companies'))[0], 200)
        marker = 'rbac-barrier-' + uuid.uuid4().hex
        barrier = subprocess.Popen(['docker','exec','-i','enginia360-rbac-db','psql','-U','postgres',
                                    '-d','enginia360_rbac_api','-X','-qAt','-v','ON_ERROR_STOP=1'],
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, text=True)
        try:
            barrier.stdin.write(f"SET application_name='{marker}'; BEGIN; SELECT pg_advisory_xact_lock(3607902026); "
                                f"DELETE FROM foundation.role_permission WHERE role_id='{role['id']}';\n")
            barrier.stdin.flush()
            for _ in range(100):
                if sql(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{marker}' AND state='idle in transaction';").stdout.strip() == '1':
                    break
                time.sleep(.03)
            else:
                self.fail('Barriera di revoca non acquisita')
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(client.request, self.path('companies'))
                try:
                    for _ in range(100):
                        if sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted;").stdout.strip() != '0':
                            break
                        time.sleep(.03)
                    else:
                        self.fail('La richiesta non attende il lock autorizzativo')
                    self.assertFalse(pending.done())
                finally:
                    barrier.stdin.write('COMMIT;\n')
                    barrier.stdin.close()
                self.assertEqual(pending.result(timeout=15)[0], 403)
            self.assertEqual(client.request('/api/session')[1]['permissions'], [])
        finally:
            if barrier.poll() is None:
                if not barrier.stdin.closed:
                    barrier.stdin.close()
                barrier.wait(timeout=10)
            errors = barrier.stderr.read()
            barrier.stderr.close()
            self.assertEqual(barrier.returncode, 0, errors)

    def test_catalog_seed_and_tenant_creation_roll_back_together(self):
        code = 'rbac-seed-' + uuid.uuid4().hex
        before = sql('SELECT count(*) FROM foundation.permission; SELECT count(*) FROM foundation.tenant;').stdout
        sql("CREATE FUNCTION foundation.rbac_reject_seed() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            "IF NEW.code='roles.assign_permissions' THEN RAISE EXCEPTION 'Fixture seed rollback'; END IF; RETURN NEW; END $$; "
            "CREATE TRIGGER rbac_reject_seed BEFORE INSERT ON foundation.permission FOR EACH ROW EXECUTE FUNCTION foundation.rbac_reject_seed();")
        try:
            self.assertEqual(self.root.request('/api/data/tenants', 'POST', {'code': code, 'name': 'Rollback catalogo'})[0], 500)
            self.assertEqual(sql(f"SELECT count(*) FROM foundation.tenant WHERE code='{code}';").stdout.strip(), '0')
            self.assertEqual(sql('SELECT count(*) FROM foundation.permission; SELECT count(*) FROM foundation.tenant;').stdout, before)
        finally:
            sql('DROP TRIGGER rbac_reject_seed ON foundation.permission; DROP FUNCTION foundation.rbac_reject_seed();')

    def test_empty_tenant_deletion_cleans_only_its_catalog_and_nonempty_refusal_is_atomic(self):
        tenant = self.new_tenant()
        self.assertEqual(self.root.request('/api/data/tenants/' + tenant['id'], 'DELETE')[0], 204)
        self.assertEqual(sql(f"SELECT count(*) FROM foundation.permission WHERE tenant_id='{tenant['id']}';").stdout.strip(), '0')
        self.company()
        before = sql(f"SELECT count(*) FROM foundation.permission WHERE tenant_id='{self.tenant['id']}';").stdout
        self.assertEqual(self.root.request('/api/data/tenants/' + self.tenant['id'], 'DELETE')[0], 409)
        self.assertEqual(sql(f"SELECT count(*) FROM foundation.permission WHERE tenant_id='{self.tenant['id']}';").stdout, before)


if __name__ == '__main__':
    unittest.main()
