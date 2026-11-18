"""Salvataggio CRUD e associazioni: atomicità e gate HTTP sul solo stack isolato."""
import concurrent.futures
import json
import subprocess
import time
import unittest
import urllib.error
import urllib.request
import uuid

from unified_save_support import Case, Client, ORIGIN, root_client, sql


class UnifiedSaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root, cls.credentials = root_client()
        cls.root_id = cls.root.request('/api/session')[1]['id']

    def setUp(self):
        self.case = Case(self.root)

    def tearDown(self):
        self.case.close()

    def ids(self, relation, owner):
        status, data = self.root.request(self.case.link(relation, owner))
        self.assertEqual(status, 200)
        return set(data['ids'])

    def rows(self, table):
        return json.loads(sql(f"SELECT coalesce(json_agg(t),'[]') FROM (SELECT * FROM foundation.\"{table}\" "
                              f"WHERE tenant_id='{self.case.tenant['id']}') t").stdout)

    def audit_count(self):
        return int(sql(f"SELECT count(*) FROM foundation.audit_event WHERE tenant_id='{self.case.tenant['id']}'").stdout)

    def test_create_group_record_and_both_associations_commit_together(self):
        user, role = self.case.user(), self.case.role(['companies.read'])
        status, group = self.root.request(self.case.path('groups', save=True), 'POST', {
            'values': {'code': 'combined', 'name': 'Gruppo completo'},
            'links': {'group-users': [user['id']], 'group-roles': [role['id']]},
        })
        self.assertEqual(status, 201, 'Una sola POST deve creare anagrafica e associazioni')
        self.assertEqual(group['name'], 'Gruppo completo')
        self.assertEqual(self.ids('group-users', group['id']), {user['id']})
        self.assertEqual(self.ids('group-roles', group['id']), {role['id']})
        self.assertEqual(len([g for g in self.rows('user_group') if g['id'] == group['id']]), 1)

    def test_invalid_second_relation_rolls_back_profile_and_first_relation(self):
        first, second = self.case.user(), self.case.user()
        role = self.case.role(['companies.read'])
        group = self.case.create('groups', {'code': 'initial', 'name': 'Originale'})
        self.root.request(self.case.link('group-users', group['id']), 'PUT', {'ids': [first['id']]})
        self.root.request(self.case.link('group-roles', group['id']), 'PUT', {'ids': [role['id']]})
        before_audit = self.audit_count()
        status, _ = self.root.request(self.case.path('groups', group['id'], save=True), 'PUT', {
            'values': {'name': 'Non persistito'},
            'links': {'group-users': [second['id']], 'group-roles': [str(uuid.uuid4())]},
        })
        self.assertEqual(status, 400)
        self.assertEqual(next(g for g in self.rows('user_group') if g['id'] == group['id'])['name'], 'Originale')
        self.assertEqual(self.ids('group-users', group['id']), {first['id']})
        self.assertEqual(self.ids('group-roles', group['id']), {role['id']})
        self.assertEqual(self.audit_count(), before_audit)

    def test_deferred_commit_failure_rolls_back_every_write_and_buffered_success(self):
        user, role = self.case.user(), self.case.role(['companies.read'])
        group = self.case.create('groups', {'code': 'initial', 'name': 'Originale'})
        before = {t: self.rows(t) for t in ('user_group','user_group_member','user_group_role')}
        audit = self.audit_count()
        sql("CREATE FUNCTION foundation.unified_save_reject_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
            f"IF NEW.resource='groups' AND NEW.record_id='{group['id']}'::uuid AND NEW.action='update' THEN "
            "RAISE EXCEPTION 'Fixture deferred commit failure'; END IF; RETURN NEW; END $$; "
            "CREATE CONSTRAINT TRIGGER unified_save_reject_commit AFTER INSERT ON foundation.audit_event "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION foundation.unified_save_reject_commit();")
        try:
            status, error = self.root.request(self.case.path('groups', group['id'], save=True), 'PUT', {
                'values': {'name': 'Da annullare'},
                'links': {'group-users': [user['id']], 'group-roles': [role['id']]},
            })
            self.assertEqual(status, 500)
            self.assertEqual(error, {'code': 'server_error'})
            self.assertEqual({t: self.rows(t) for t in before}, before)
            self.assertEqual(self.audit_count(), audit)
        finally:
            sql('DROP TRIGGER unified_save_reject_commit ON foundation.audit_event; DROP FUNCTION foundation.unified_save_reject_commit();')

    def test_failed_create_does_not_leave_owner_or_assignment_or_audit(self):
        user = self.case.user()
        audit = self.audit_count()
        status, _ = self.root.request(self.case.path('groups', save=True), 'POST', {
            'values': {'code': 'not-created', 'name': 'Non creato'},
            'links': {'group-users': [user['id']], 'group-roles': [str(uuid.uuid4())]},
        })
        self.assertEqual(status, 400)
        self.assertEqual(self.rows('user_group'), [])
        self.assertEqual(self.rows('user_group_member'), [])
        self.assertEqual(self.audit_count(), audit)

    def test_all_requested_authorities_are_required_before_profile_changes(self):
        target, chosen = self.case.user(), self.case.role(['companies.read'])
        editor, _, _, _ = self.case.actor(['users.update'])
        audit = self.audit_count()
        status, _ = editor.request(self.case.path('users', target['id'], save=True), 'PUT', {
            'values': {'first_name': 'Non persistito'}, 'links': {'user-roles': [chosen['id']]},
        })
        self.assertEqual(status, 403)
        self.assertEqual(next(u for u in self.rows('user') if u['id'] == target['id'])['first_name'], 'Operatore')
        self.assertEqual(self.ids('user-roles', target['id']), set())
        self.assertEqual(self.audit_count(), audit)

    def test_links_only_save_does_not_require_profile_update_or_expose_profile(self):
        target, chosen = self.case.user(), self.case.role(['companies.read'])
        assigner, _, _, _ = self.case.actor(['roles.assign'])
        status, result = assigner.request(self.case.path('users', target['id'], save=True), 'PUT', {
            'links': {'user-roles': [chosen['id']]},
        })
        self.assertEqual(status, 200)
        self.assertEqual(result, {'id': target['id']})
        self.assertEqual(self.ids('user-roles', target['id']), {chosen['id']})
        status, _ = assigner.request(self.case.path('users', target['id'], save=True), 'PUT', {
            'values': {'first_name': 'Non consentito'}, 'links': {'user-roles': []},
        })
        self.assertEqual(status, 403)
        self.assertEqual(self.ids('user-roles', target['id']), {chosen['id']})

    def test_role_profile_and_catalog_permissions_save_together_with_audit(self):
        role = self.case.role(['companies.read'])
        permission = self.case.catalog['companies.create']
        status, row = self.root.request(self.case.path('roles', role['id'], save=True), 'PUT', {
            'values': {'name': 'Ruolo aggiornato'}, 'links': {'role-permissions': [permission]},
        })
        self.assertEqual(status, 200)
        self.assertEqual(row['name'], 'Ruolo aggiornato')
        self.assertEqual(self.ids('role-permissions', role['id']), {permission})
        events = json.loads(sql(f"SELECT json_agg(t) FROM (SELECT resource,action,details FROM foundation.audit_event "
                               f"WHERE record_id='{role['id']}' AND action IN ('update','replace_links') ORDER BY created_at) t").stdout)
        self.assertTrue(any(e['resource'] == 'roles' and e['details']['after']['name'] == 'Ruolo aggiornato' for e in events))
        self.assertTrue(any(e['resource'] == 'role-permissions' and e['details']['afterIds'] == [permission] for e in events))

    def test_unsubmitted_group_relation_is_preserved(self):
        user, role = self.case.user(), self.case.role(['companies.read'])
        group = self.case.create('groups', {'code': 'keep', 'name': 'Conserva'})
        self.root.request(self.case.link('group-roles', group['id']), 'PUT', {'ids': [role['id']]})
        assigner, _, _, _ = self.case.actor(['groups.assign_users'])
        status, result = assigner.request(self.case.path('groups', group['id'], save=True), 'PUT', {
            'links': {'group-users': [user['id']]},
        })
        self.assertEqual(status, 200)
        self.assertEqual(result, {'id': group['id']})
        self.assertEqual(self.ids('group-users', group['id']), {user['id']})
        self.assertEqual(self.ids('group-roles', group['id']), {role['id']})

    def test_cross_tenant_and_wrong_owner_relation_are_rejected_atomically(self):
        other = Case(self.root)
        try:
            foreign = other.user()
            group = self.case.create('groups', {'code': 'keep', 'name': 'Conserva'})
            for links in ({'group-users': [foreign['id']]}, {'role-permissions': [self.case.catalog['companies.read']]}):
                status, _ = self.root.request(self.case.path('groups', group['id'], save=True), 'PUT', {
                    'values': {'name': 'Non persistito'}, 'links': links,
                })
                self.assertEqual(status, 400)
            self.assertEqual(next(g for g in self.rows('user_group') if g['id'] == group['id'])['name'], 'Conserva')
            actor, _, _, _ = self.case.actor(['groups.update'])
            self.assertEqual(actor.request(other.path('groups', str(uuid.uuid4()), save=True), 'PUT', {'values': {'name': 'Negato'}})[0], 403)
        finally:
            other.close()

    def test_global_identity_and_readonly_catalog_are_protected(self):
        role = self.case.role()
        for payload in ({'values': {'is_enabled': False}}, {'links': {'user-roles': [role['id']]}}):
            self.assertEqual(self.root.request(self.case.path('users', self.root_id, save=True), 'PUT', payload)[0], 404)
        permission = self.case.catalog['companies.read']
        self.assertEqual(self.root.request(self.case.path('permissions', permission, save=True), 'PUT', {'values': {'name': 'Non modificabile'}})[0], 403)
        self.assertEqual(self.root.request(self.case.path('permissions', save=True), 'POST', {'values': {'code': 'arbitrary', 'name': 'Non creabile'}})[0], 403)

    def test_csrf_foreign_origin_and_anonymous_save_are_refused(self):
        body = {'values': {'code': 'forbidden', 'name': 'Non creato'}}
        path = self.case.path('groups', save=True)
        self.assertIn(self.root.request(path, 'POST', body, csrf=False)[0], (400,403))
        self.assertEqual(self.root.request(path, 'POST', body, origin='https://foreign.invalid')[0], 403)
        self.assertEqual(Client().request(path, 'POST', body)[0], 401)
        self.assertEqual(self.rows('user_group'), [])

    def test_invalid_payloads_and_duplicate_json_never_mutate_data(self):
        group = self.case.create('groups', {'code': 'keep', 'name': 'Conserva'})
        before, audit = self.rows('user_group'), self.audit_count()
        payloads = [{}, {'values': {}}, {'links': {}}, {'values': None}, {'links': None},
                    {'unknown': {}}, {'values': {'tenant_id': str(uuid.uuid4())}},
                    {'links': {'group-users': ['not-uuid']}}, {'links': {'group-users': [str(uuid.UUID(int=0))]}},
                    {'links': {'group-users': ['a'] * 501}}]
        user = self.case.user()
        payloads.append({'links': {'group-users': [user['id'], user['id']]}})
        for body in payloads:
            with self.subTest(body=body):
                self.assertEqual(self.root.request(self.case.path('groups', group['id'], save=True), 'PUT', body)[0], 400)
        for raw in ('{"values":{"name":"A"},"values":{"name":"B"}}',
                    '{"links":{"group-users":[],"group-users":[]}}',
                    '{"values":{"name":"A","name":"B"}}'):
            token = self.root.request('/api/auth/csrf')[1]['token']
            request = urllib.request.Request(ORIGIN + self.case.path('groups', group['id'], save=True),
                data=raw.encode(), method='PUT', headers={'Origin':ORIGIN,'Host':'vmi3659251.tailfcced0.ts.net:8080',
                'Content-Type':'application/json','X-CSRF-TOKEN':token})
            try:
                response = self.root.opener.open(request, timeout=20)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                self.assertEqual(response.status, 400)
        self.assertEqual(self.rows('user_group'), before)
        # Solo la creazione esplicita dell'utente fixture aggiunge il relativo audit.
        self.assertEqual(self.audit_count(), audit + 1)

    def test_create_normal_resource_and_atomic_tenant_seed_still_work(self):
        status, company = self.root.request(self.case.path('companies', save=True), 'POST', {
            'values': {'code': 'atomic', 'name': 'Società'},
        })
        self.assertEqual(status, 201)
        self.assertEqual(company['name'], 'Società')
        code = 'tenant-save-' + uuid.uuid4().hex
        status, tenant = self.root.request('/api/data/tenants/save', 'POST', {'values': {'code': code, 'name': 'Tenant atomico'}})
        self.assertEqual(status, 201)
        try:
            status, catalog = self.root.request('/api/data/permissions?tenantId=' + tenant['id'] + '&pageSize=100')
            self.assertEqual(status, 200)
            self.assertEqual(len(catalog['items']), 41)
        finally:
            self.assertEqual(self.root.request('/api/data/tenants/' + tenant['id'], 'DELETE')[0], 204)

    def test_self_revocation_commits_once_and_next_session_has_no_permissions(self):
        actor, user, _, _ = self.case.actor(['roles.assign','users.read','roles.read'])
        status, result = actor.request(self.case.path('users', user['id'], save=True), 'PUT', {'links': {'user-roles': []}})
        self.assertEqual(status, 200)
        self.assertEqual(result, {'id': user['id']})
        self.assertEqual(actor.request('/api/session')[1]['permissions'], [])
        self.assertEqual(self.ids('user-roles', user['id']), set())

    def test_pending_save_waits_for_authority_revocation_and_cannot_partially_update(self):
        target = self.case.user()
        group = self.case.create('groups', {'code': 'wait', 'name': 'Originale'})
        actor, _, actor_role, _ = self.case.actor(['groups.update','groups.assign_users'])
        marker = 'save-barrier-' + uuid.uuid4().hex
        barrier = subprocess.Popen(['docker','exec','-i','enginia360-unified-save-db','psql','-U','postgres',
            '-d','enginia360','-X','-qAt','-v','ON_ERROR_STOP=1'], stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        try:
            barrier.stdin.write(f"SET application_name='{marker}'; BEGIN; SELECT pg_advisory_xact_lock(3607902026); "
                f"DELETE FROM foundation.role_permission WHERE role_id='{actor_role['id']}' AND permission_id='{self.case.catalog['groups.assign_users']}';\n")
            barrier.stdin.flush()
            for _ in range(100):
                if sql(f"SELECT count(*) FROM pg_stat_activity WHERE application_name='{marker}' AND state='idle in transaction'").stdout.strip() == '1': break
                time.sleep(.03)
            else: self.fail('Barriera non acquisita')
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(actor.request, self.case.path('groups', group['id'], save=True), 'PUT',
                    {'values': {'name': 'Non autorizzato'}, 'links': {'group-users': [target['id']]}})
                try:
                    for _ in range(100):
                        if sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted").stdout.strip() != '0': break
                        time.sleep(.03)
                    else: self.fail('La richiesta non attende il lock')
                    self.assertFalse(pending.done())
                finally:
                    barrier.stdin.write('COMMIT;\n');barrier.stdin.close()
                self.assertEqual(pending.result(timeout=20)[0], 403)
            self.assertEqual(next(g for g in self.rows('user_group') if g['id'] == group['id'])['name'], 'Originale')
            self.assertEqual(self.ids('group-users', group['id']), set())
        finally:
            if not barrier.stdin.closed: barrier.stdin.close()
            if barrier.poll() is None: barrier.wait(timeout=10)
            errors = barrier.stderr.read();barrier.stderr.close()
            self.assertEqual(barrier.returncode, 0, errors)


if __name__ == '__main__':
    unittest.main(verbosity=2)
