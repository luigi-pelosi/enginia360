#!/usr/bin/env python3
"""Existing-member access tracer; opt-in isolated PostgreSQL only."""
import importlib.util
import os
import json
import subprocess
from pathlib import Path
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('roles', ROOT / 'scripts/test-mvp03b1-roles.py')
assert spec and spec.loader
roles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roles)


@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS') == '1', 'isolated SQL required')
class MembershipAccessTests(unittest.TestCase):
    # Reuse the established private-database/owner bootstrap without inheriting
    # and accidentally rerunning the whole historical test composition.
    tenant: str
    member: str
    target_member: str
    company: str
    site: str
    warehouse: str
    target: dict[str, str]
    actor: dict[str, str]

    setUp = roles.RoleTests.setUp
    tearDown = roles.RoleTests.tearDown
    sql = roles.RoleTests.sql
    start_migration = roles.RoleTests.start_migration
    migrate = roles.RoleTests.migrate
    prepare = roles.RoleTests.prepare
    payload = roles.RoleTests.payload
    owner_sql = roles.RoleTests.owner_sql
    command = roles.RoleTests.command
    prepare_org = roles.RoleTests.prepare_org
    actor_settings = roles.RoleTests.actor_settings
    app_result = roles.RoleTests.app_result
    org_payload = roles.RoleTests.org_payload
    org_command = roles.RoleTests.org_command
    create_tenant = roles.RoleTests.create_tenant
    create_company = roles.RoleTests.create_company
    create_site = roles.RoleTests.create_site
    prepare_delegate = roles.RoleTests.prepare_delegate
    barrier_race = roles.RoleTests.barrier_race
    role_read = roles.RoleTests.role_read
    role_payload = roles.RoleTests.role_payload
    role_command = roles.RoleTests.role_command
    prepare_user_admin = roles.RoleTests.prepare_user_admin
    permission_payload = roles.RoleTests.permission_payload
    prepare_role = roles.RoleTests.prepare_role
    effective = roles.RoleTests.effective
    role_statement = roles.RoleTests.role_statement

    def test_existing_member_selector_distinguishes_access_from_user_delegation(self):
        self.prepare_delegate()
        result = self.role_read(self.tenant)
        self.assertEqual(result['state'], 'ok')
        self.assertEqual(len(result['memberships']), 1)
        member = result['memberships'][0]
        self.assertEqual(member['membershipId'], self.member)
        # Existing authority labels remain unchanged and are not access state.
        self.assertFalse(member['active'])
        self.assertEqual(member['revision'], 0)
        self.assertIn('accessEnabled', member,
                      'existing-member selector has no separate tenant-access state')
        self.assertIs(member['accessEnabled'], True)
        self.assertEqual(member['accessRevision'], 0)

    def access_payload(self, **changes):
        row = next(m for m in self.role_read(self.tenant)['memberships'] if m['membershipId'] == self.target_member)
        return dict(dict(commandId=str(uuid.uuid4()), membershipId=self.target_member,
                         internalIdentityId=self.target['internalIdentityId'], bindingHash=row['bindingHash'],
                         expectedRevision=row['accessRevision'], enabled=False), **changes)

    def access_statement(self, payload):
        return self.actor_settings() + "SELECT organization_access.command_membership_access('" + self.tenant + "','" + json.dumps(payload).replace("'", "''") + "');"

    def access_command(self, payload):
        return self.app_result("SELECT organization_access.command_membership_access('" + self.tenant + "','" + json.dumps(payload).replace("'", "''") + "')")

    def access_row(self):
        return next(m for m in self.role_read(self.tenant)['memberships'] if m['membershipId'] == self.target_member)

    def exercise_available_command(self, payload):
        # Missing baseline ingress performs no mutation; assert physical state.
        # No fabricated command response or fixture mutation substitutes for it.
        self.sql("BEGIN;" + self.actor_settings() + "DO $probe$ BEGIN PERFORM organization_access.command_membership_access('" + self.tenant + "','" + json.dumps(payload) + "'); EXCEPTION WHEN undefined_function THEN NULL; END $probe$;COMMIT;", app=True)

    def test_disable_changes_existing_access_without_deleting_grants(self):
        self.prepare_role()
        self.exercise_available_command(self.access_payload())
        self.assertIs(self.access_row()['accessEnabled'], False, 'disable must change current existing-member access')
        self.assertEqual(self.access_row()['accessRevision'], 1)
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'), '2')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenant_role_objects'), '3')

    def test_enable_changes_disabled_access_with_independent_revision(self):
        self.prepare_role()
        self.sql(f"INSERT INTO organization_access.membership_access_state VALUES('{self.target_member}','{self.tenant}',false,1)")
        self.exercise_available_command(self.access_payload(enabled=True))
        self.assertIs(self.access_row()['accessEnabled'], True, 'enable must change current disabled-member access')
        self.assertEqual(self.access_row()['accessRevision'], 2)

    def test_access_replay_conflict_stale_revision_and_current_revoked_actor(self):
        self.prepare_role(); p = self.access_payload()
        first = self.access_command(p)
        self.assertEqual(first['state'], 'applied')
        self.assertEqual(self.access_command(p), dict(state='replayed', snapshot=first['snapshot']))
        self.assertEqual(self.access_command(dict(p, enabled=True))['state'], 'conflict')
        self.assertEqual(self.access_command(dict(p, commandId=str(uuid.uuid4())))['state'], 'conflict')
        self.assertEqual(self.access_command(self.access_payload(enabled=True))['state'], 'applied')
        self.assertEqual(self.access_command(p)['snapshot']['enabled'], False)
        self.assertTrue(self.access_row()['accessEnabled'])
        self.actor = self.owner_actor
        revoke = dict(self.grant, commandId=str(uuid.uuid4()), resourceId=self.grant_snapshot['resourceId'], expectedRevision=1, active=False)
        self.role_command(revoke); self.actor = self.delegate
        self.assertEqual(self.access_command(p), dict(state='forbidden'))

    def test_access_audit_is_minimized_immutable_and_atomic_at_insert_and_commit(self):
        self.prepare_role(); p = self.access_payload()
        self.assertEqual(self.access_command(p)['state'], 'applied')
        row = json.loads(self.sql('SELECT to_jsonb(a) FROM organization_access.membership_access_audit a'))
        self.assertEqual(row['Before'], dict(enabled=True, revision=0))
        self.assertEqual(row['After']['enabled'], False)
        self.assertEqual(row['Request'], p)
        self.assertEqual(row['Authority'], dict(kind='user-administration',resourceId=self.grant_snapshot['resourceId'],revision=1))
        self.assertEqual(row['ActorId'], self.delegate['internalIdentityId'])
        self.assertEqual(row['TenantId'], self.tenant)
        self.assertTrue(row['BindingHash']); self.assertTrue(row['OccurredAt'])
        for mutation in ("UPDATE organization_access.membership_access_audit SET \"Request\"='{}'", 'DELETE FROM organization_access.membership_access_audit', 'TRUNCATE organization_access.membership_access_audit'):
            self.assertNotEqual(self.owner_sql(mutation, ok=False).returncode, 0)
        self.sql("CREATE FUNCTION organization_access.fixture_access_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic access audit refusal'; END $$")
        for timing in ('BEFORE', 'DEFERRED'):
            prefix = 'CREATE TRIGGER fixture_access_fail BEFORE INSERT' if timing == 'BEFORE' else 'CREATE CONSTRAINT TRIGGER fixture_access_fail AFTER INSERT'
            self.sql(prefix + ' ON organization_access.membership_access_audit ' + ('DEFERRABLE INITIALLY DEFERRED ' if timing == 'DEFERRED' else '') + 'FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_access_fail()')
            for enabled in (True, False):
                attempt = self.access_payload(enabled=enabled)
                baseline = self.sql('SELECT jsonb_agg(to_jsonb(s)) FROM organization_access.membership_access_state s')
                env = dict(os.environ, PGDATABASE=self.database, PGUSER=os.environ['R00_APP_USER'], PGPASSWORD=os.environ['R00_APP_PASSWORD'])
                result = subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'], input='BEGIN;'+self.access_statement(attempt)+'COMMIT;', env=env, capture_output=True, text=True, timeout=20)
                self.assertNotEqual(result.returncode,0); self.assertIn('synthetic access audit refusal',result.stderr)
                self.assertEqual(self.sql('SELECT jsonb_agg(to_jsonb(s)) FROM organization_access.membership_access_state s'),baseline)
                self.assertEqual(self.sql('SELECT count(*) FROM organization_access.membership_access_audit'),'1')
            self.sql('DROP TRIGGER fixture_access_fail ON organization_access.membership_access_audit')

    def test_disabled_delegate_cannot_read_mutate_or_replay_administration(self):
        self.prepare_role(); p = self.access_payload()
        applied = self.access_command(p)
        self.actor = self.owner_actor
        own = next(m for m in self.role_read(self.tenant)['memberships'] if m['membershipId'] == self.member)
        disable_actor = dict(p, commandId=str(uuid.uuid4()), membershipId=self.member, internalIdentityId=own['internalIdentityId'], bindingHash=own['bindingHash'])
        self.assertEqual(self.access_command(disable_actor)['state'], 'applied')
        self.actor = self.delegate
        self.assertEqual(self.role_read(), dict(state='forbidden'))
        self.assertEqual(self.role_command(self.role_creation), dict(state='forbidden'))
        self.assertEqual(self.access_command(p), dict(state='forbidden'))
        self.actor = self.owner_actor
        self.assertEqual(self.role_read(self.tenant)['state'], 'ok')
        self.assertEqual(applied['state'], 'applied')

    def test_disabled_role_scope_origin_has_no_permissive_union_escape(self):
        self.prepare_role(); self.role_command(self.assignment)
        self.actor = self.target; self.assertEqual(self.effective(), ['organization-context.read'])
        self.actor = self.delegate; self.access_command(self.access_payload())
        self.actor = self.target
        self.assertEqual(self.effective(), [], 'disabled configurable role still authorizes via UNION function')

    def test_privileged_target_enable_restriction_not_blanket_disable_ban(self):
        self.prepare_role(); p = self.access_payload()
        self.sql(f"INSERT INTO organization_access.organization_delegations VALUES('{self.target_member}','{self.tenant}','{self.target['internalIdentityId']}',decode('{p['bindingHash']}','hex'),true,1)")
        self.actor = self.target
        self.assertEqual(self.app_result('SELECT organization_access.read_organization_workspace()')['mode'], 'delegate')
        self.actor = self.delegate
        self.assertEqual(self.access_command(p)['state'], 'applied')
        self.actor = self.target
        self.assertEqual(self.app_result('SELECT organization_access.read_organization_workspace()'), dict(state='forbidden'))
        self.actor = self.delegate
        enable = self.access_payload(enabled=True)
        self.assertEqual(self.access_command(enable), dict(state='forbidden'))
        self.actor = self.owner_actor
        self.assertEqual(self.access_command(enable)['state'], 'applied')
        self.actor = self.delegate
        self.access_command(self.access_payload())
        self.sql(f"UPDATE organization_access.organization_delegations SET \"Active\"=false WHERE \"MembershipId\"='{self.target_member}'")
        self.assertEqual(self.access_command(self.access_payload(enabled=True))['state'], 'applied')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_delegations WHERE "Active"'), '0')

    def test_physical_double_uuid_revision_binding_and_access_read_orders(self):
        self.prepare_role(); p = self.access_payload()
        results, _ = self.barrier_race('SELECT pg_advisory_xact_lock(777036);', [(self.access_statement(p),'app')]*2)
        self.assertEqual(sorted(r['state'] for r in results), ['applied','replayed'])
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.membership_access_audit WHERE "Outcome"=\'applied\''), '1')
        enable = self.access_payload(enabled=True)
        results, _ = self.barrier_race('SELECT pg_advisory_xact_lock(777036);', [(self.access_statement(enable),'app'),(self.access_statement(dict(enable,commandId=str(uuid.uuid4()))),'app')])
        self.assertEqual(sorted(r['state'] for r in results), ['applied','conflict'])
        disable = self.access_payload()
        self.actor = self.target
        read = self.actor_settings()+f"SELECT jsonb_build_object('allowed',organization_access.current_membership_access('{self.tenant}'));"
        self.actor = self.delegate
        results, _ = self.barrier_race(self.access_statement(disable), [(read,'app')], holder_role='app')
        self.assertEqual(results, [dict(allowed=False)])
        self.access_command(self.access_payload(enabled=True))
        disable = self.access_payload()
        results, held = self.barrier_race(read, [(self.access_statement(disable),'app')], holder_role='app')
        self.assertEqual(held[-1], dict(allowed=True)); self.assertEqual(results[0]['state'], 'applied')
        attempt = self.access_payload(enabled=True)
        replacement = f"UPDATE organization_access.external_identity_bindings SET \"Subject\"='Replaced' WHERE \"InternalIdentityId\"='{self.target['internalIdentityId']}';"
        results, _ = self.barrier_race(replacement, [(self.access_statement(attempt),'app')])
        self.assertEqual(results, [dict(state='forbidden')])

    def test_closed_access_validation_exact_target_and_private_dml(self):
        self.prepare_role(); p = self.access_payload()
        for change in (dict(extra=True),dict(expectedRevision=True),dict(expectedRevision=2147483647),dict(enabled='false'),dict(bindingHash='x'),dict(commandId='00000000-0000-0000-0000-000000000000')):
            self.assertEqual(self.access_command(dict(p,**change))['state'], 'invalid')
        for change in (dict(membershipId=str(uuid.uuid4())),dict(internalIdentityId=str(uuid.uuid4())),dict(bindingHash='0'*64)):
            self.assertEqual(self.access_command(dict(p,**change)), dict(state='forbidden'))
        for table in ('membership_access_state','membership_access_audit'):
            self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','organization_access.{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.membership_access_audit WHERE "Outcome"<>\'applied\' AND ("TenantId" IS NOT NULL OR "ResourceId" IS NOT NULL OR "Request"<>\'{}\')'),'0')

    def test_user_delegation_privilege_and_self_disable_require_owner_restore(self):
        self.prepare_role(); p = self.access_payload()
        self.actor = self.owner_actor
        target_grant = dict(self.grant, commandId=str(uuid.uuid4()), membershipId=self.target_member, internalIdentityId=self.target['internalIdentityId'], bindingHash=p['bindingHash'])
        self.assertEqual(self.role_command(target_grant)['state'], 'applied')
        self.actor = self.delegate
        self.assertEqual(self.access_command(p)['state'], 'applied')
        self.assertEqual(self.access_command(self.access_payload(enabled=True)), dict(state='forbidden'))
        self.actor = self.owner_actor
        self.assertEqual(self.access_command(self.access_payload(enabled=True))['state'], 'applied')
        self.actor = self.delegate
        own = next(m for m in self.role_read()['memberships'] if m['membershipId'] == self.member)
        self_disable = dict(p, commandId=str(uuid.uuid4()), membershipId=self.member, internalIdentityId=own['internalIdentityId'], bindingHash=own['bindingHash'])
        self.assertEqual(self.access_command(self_disable)['state'], 'applied')
        self.assertEqual(self.access_command(dict(self_disable, commandId=str(uuid.uuid4()), expectedRevision=1, enabled=True)), dict(state='forbidden'))
        self.actor = self.owner_actor
        self.assertEqual(self.access_command(dict(self_disable, commandId=str(uuid.uuid4()), expectedRevision=1, enabled=True))['state'], 'applied')
        self.actor = self.delegate
        self.assertEqual(self.role_read()['state'], 'ok')

    def test_d77_admin_target_and_operative_recipient_are_distinct(self):
        self.prepare_role(); p = self.access_payload(); mandate = str(uuid.uuid4())
        self.sql(f"BEGIN;SELECT set_config('app.owner_actor','{self.owner_actor['internalIdentityId']}',true);INSERT INTO organization_access.delegation_mandates VALUES('{mandate}','{self.tenant}','{self.target_member}','{self.company}','{self.site}','{self.warehouse}','organization-context.read',now()-interval '1 hour',now()+interval '1 hour',NULL);COMMIT;")
        self.assertEqual(self.access_command(p)['state'], 'applied')
        self.assertEqual(self.access_command(self.access_payload(enabled=True)), dict(state='forbidden'))
        self.sql(f"BEGIN;SELECT set_config('app.owner_actor','{self.owner_actor['internalIdentityId']}',true);UPDATE organization_access.delegation_mandates SET \"RevokedAt\"=now() WHERE \"Id\"='{mandate}';COMMIT;")
        self.assertEqual(self.access_command(self.access_payload(enabled=True))['state'], 'applied')
        # A separate mandate belongs to the other admin; its operative recipient
        # is not an administrator and may be enabled by the user delegate.
        other = str(uuid.uuid4())
        self.sql(f"BEGIN;SELECT set_config('app.owner_actor','{self.owner_actor['internalIdentityId']}',true);INSERT INTO organization_access.delegation_mandates VALUES('{other}','{self.tenant}','{self.member}','{self.company}','{self.site}','{self.warehouse}','organization-context.read',now()-interval '1 hour',now()+interval '1 hour',NULL);INSERT INTO organization_access.delegated_scopes VALUES('{uuid.uuid4()}','{self.target_member}','{self.tenant}','{self.company}','{self.site}','{self.warehouse}','organization-context.read','{other}');COMMIT;")
        self.actor = self.target; self.assertEqual(self.effective(), ['organization-context.read'])
        self.actor = self.delegate; self.access_command(self.access_payload())
        self.actor = self.target; self.assertEqual(self.effective(), [])
        self.actor = self.delegate
        self.assertEqual(self.access_command(self.access_payload(enabled=True))['state'], 'applied')
        self.actor = self.target; self.assertEqual(self.effective(), ['organization-context.read'])
        self.assertEqual(self.access_command(p), dict(state='forbidden'))

    def test_d77_disabled_mandate_admin_is_denied_before_operative_replay(self):
        self.prepare_role()
        mandate = str(uuid.uuid4())
        self.sql(f"BEGIN;SELECT set_config('app.owner_actor','{self.owner_actor['internalIdentityId']}',true);INSERT INTO organization_access.delegation_mandates VALUES('{mandate}','{self.tenant}','{self.member}','{self.company}','{self.site}','{self.warehouse}','organization-context.read',now()-interval '1 hour',now()+interval '1 hour',NULL);COMMIT;")
        command = str(uuid.uuid4())

        # Match the existing D77 API transaction: exact verified actor AND
        # its server-resolved tenant (the original FORCE RLS requires both).
        def d77_result(statement):
            output = self.sql('BEGIN;' + self.actor_settings() +
                f"SELECT set_config('app.tenant_id','{self.tenant}',true);" + statement + ';COMMIT;', app=True)
            return json.loads(output.splitlines()[-1])

        def operative(command_id=command, operation='grant'):
            return d77_result(f"SELECT to_json(organization_access.command_operative_grant('{command_id}','{mandate}','{self.target_member}','{self.tenant}','{self.company}','{self.site}','{self.warehouse}','organization-context.read','{operation}'))")

        self.assertEqual(len(d77_result('SELECT organization_access.grant_administration()')), 1)
        self.assertEqual(operative(), 'applied')
        self.assertEqual(operative(), 'replayed')
        before = self.sql('SELECT count(*) FROM organization_access.grant_commands')
        self.actor = self.owner_actor
        own = next(m for m in self.role_read(self.tenant)['memberships'] if m['membershipId'] == self.member)
        disable = dict(self.access_payload(), membershipId=self.member,
                       internalIdentityId=own['internalIdentityId'], bindingHash=own['bindingHash'],
                       expectedRevision=own['accessRevision'])
        self.assertEqual(self.access_command(disable)['state'], 'applied')
        self.actor = self.delegate
        self.assertEqual(d77_result('SELECT organization_access.grant_administration()'), [])
        self.assertEqual(operative(), 'forbidden', 'disabled mandate administrator must be refused before historical replay')
        self.assertEqual(operative(str(uuid.uuid4()), 'revoke'), 'forbidden')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.grant_commands'), before)
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.delegated_scopes'), '1')
        self.actor = self.owner_actor
        self.assertEqual(self.access_command(dict(disable, commandId=str(uuid.uuid4()), expectedRevision=1, enabled=True))['state'], 'applied')
        self.actor = self.delegate
        self.assertEqual(len(d77_result('SELECT organization_access.grant_administration()')), 1)
        self.assertEqual(operative(), 'replayed')
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.grant_commands'), before)
        self.assertEqual(self.sql('SELECT count(*) FROM organization_access.delegated_scopes'), '1')

    def test_owner_ordinary_membership_disabled_does_not_grant_business_bypass(self):
        self.prepare_role(); p = self.access_payload(); self.actor = self.owner_actor
        # Owner identity has no membership and cannot use the ordinary helper.
        self.assertFalse(self.app_result(f"SELECT to_json(organization_access.current_membership_access('{self.tenant}'))"))
        self.assertEqual(self.access_command(p)['state'], 'applied')
        own_member = str(uuid.uuid4())
        self.sql(f"INSERT INTO organization_access.memberships VALUES('{own_member}','{self.tenant}','{self.owner_actor['internalIdentityId']}')")
        own = next(m for m in self.role_read(self.tenant)['memberships'] if m['membershipId'] == own_member)
        disable = dict(p, commandId=str(uuid.uuid4()), membershipId=own_member, internalIdentityId=own['internalIdentityId'], bindingHash=own['bindingHash'])
        self.assertEqual(self.access_command(disable)['state'], 'applied')
        self.assertFalse(self.app_result(f"SELECT to_json(organization_access.current_membership_access('{self.tenant}'))"))
        self.assertEqual(self.role_read(self.tenant)['mode'], 'owner')
        self.assertEqual(self.access_command(dict(disable, commandId=str(uuid.uuid4()), expectedRevision=1, enabled=True))['state'], 'applied')

    def test_state_command_is_a_distinct_authenticated_sql_contract(self):
        self.prepare_delegate()
        self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.command_membership_access(uuid,jsonb)') IS NOT NULL"),
                         't', 'audited existing-membership access command is absent')

    def test_replaced_binding_cannot_reuse_root_scopes_through_direct_sql(self):
        self.prepare_role()
        self.sql(f'''INSERT INTO organization_access.membership_scopes
            VALUES('{uuid.uuid4()}','{self.target_member}','{self.tenant}',
                '{self.company}','{self.site}','{self.warehouse}',
                'organization-context.read')''')
        self.actor = self.target
        root_read = (f"SELECT set_config('app.tenant_id','{self.tenant}',true);"
                     "SELECT to_json(count(*)) FROM organization_access.membership_scopes "
                     f"WHERE \"MembershipId\"='{self.target_member}'")
        self.assertEqual(self.app_result(root_read), 1,
                         'valid enabled existing binding must retain its root scope')
        self.sql(f'''UPDATE organization_access.external_identity_bindings
            SET "Subject"='Replacement' WHERE "InternalIdentityId"='{self.target['internalIdentityId']}' ''')
        self.assertEqual(self.app_result(root_read), 0,
                         'old verified binding still exposes root scopes at independent SQL ingress')

    def test_replaced_binding_cannot_reuse_company_grant_through_direct_sql(self):
        self.prepare_role()
        self.sql(f'''INSERT INTO organization_access.company_permissions
            VALUES('{uuid.uuid4()}','{self.target_member}','{self.tenant}',
                '{self.company}','counterparties.read',NULL,NULL)''')
        self.actor = self.target
        company_read = (f"SELECT set_config('app.tenant_id','{self.tenant}',true);"
                        "SELECT to_json(count(*)) FROM organization_access.company_permissions "
                        f"WHERE \"MembershipId\"='{self.target_member}'")
        self.assertEqual(self.app_result(company_read), 1,
                         'valid enabled existing binding must retain its company grant')
        self.sql(f'''UPDATE organization_access.external_identity_bindings
            SET "Subject"='Replacement' WHERE "InternalIdentityId"='{self.target['internalIdentityId']}' ''')
        self.assertEqual(self.app_result(company_read), 0,
                         'old verified binding still exposes company grants at independent SQL ingress')


    def test_business_direct_sql_uses_exact_current_binding_without_permissive_escape(self):
        self.prepare_role()
        item, vehicle = str(uuid.uuid4()), str(uuid.uuid4())
        self.sql(f"INSERT INTO catalog.items VALUES('{item}','{self.tenant}','{self.company}','Part','Synthetic member part',1); INSERT INTO vehicles.vehicles VALUES('{vehicle}','{self.tenant}','{self.company}','{uuid.uuid4()}','Synthetic member vehicle'); INSERT INTO inventory.stock VALUES('{self.tenant}','{self.company}','{self.site}','{self.warehouse}','{item}',5)")
        self.sql(f"INSERT INTO organization_access.company_stock_profiles (\"CommandId\",\"TenantId\",\"LegalEntityId\",\"Domain\",\"Version\",\"Direction\",\"SourceId\",\"ProfileId\",\"ActorMembershipId\",\"VerificationReference\") VALUES ('{uuid.uuid4()}','{self.tenant}','{self.company}','stock',1,'Enginia360ToExternal','{uuid.uuid4()}','{uuid.uuid4()}','{self.target_member}','{uuid.uuid4()}')")
        profile_read = f"SELECT set_config('app.tenant_id','{self.tenant}',true); SELECT to_json(organization_access.company_stock_profile('{self.tenant}','{self.company}'))"
        disable = self.access_payload()
        self.actor = self.target
        self.assertEqual(self.app_result(profile_read), 'local')
        for table in ('catalog.items', 'vehicles.vehicles', 'inventory.stock'):
            self.assertEqual(self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true); SELECT jsonb_build_object('count',count(*)) FROM {table}"), dict(count=1))
        self.actor = self.delegate
        self.assertEqual(self.access_command(disable)['state'], 'applied')
        self.actor = self.target
        self.assertEqual(self.app_result(profile_read), 'missing')
        for table in ('catalog.items', 'vehicles.vehicles', 'inventory.stock'):
            self.assertEqual(self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true); SELECT jsonb_build_object('count',count(*)) FROM {table}"), dict(count=0))
        for call in (
            f"catalog.supplier_purchase_price_state('{self.company}','{uuid.uuid4()}','{item}')",
            f"catalog.purchase_intent_quote('{uuid.uuid4()}','{uuid.uuid4()}','{self.warehouse}','{uuid.uuid4()}')",
            f"inventory.receipt_state('{uuid.uuid4()}')",
            f"inventory.receipt_sources('{uuid.uuid4()}','{uuid.uuid4()}','{self.warehouse}')",
            f"inventory.purchase_intent_state('{uuid.uuid4()}','{uuid.uuid4()}','{self.warehouse}')",
        ):
            self.assertEqual(self.app_result('SELECT '+call), dict(state='forbidden'))
        self.actor = self.delegate
        self.assertEqual(self.access_command(self.access_payload(enabled=True))['state'], 'applied')
        self.actor = self.target
        self.assertEqual(self.app_result(profile_read), 'local')
        for table in ('catalog.items', 'vehicles.vehicles', 'inventory.stock'):
            self.assertEqual(self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true); SELECT jsonb_build_object('count',count(*)) FROM {table}"), dict(count=1))
        self.sql(f"UPDATE organization_access.external_identity_bindings SET \"Subject\"='Replaced' WHERE \"InternalIdentityId\"='{self.target['internalIdentityId']}'")
        for table in ('catalog.items', 'vehicles.vehicles', 'inventory.stock'):
            self.assertEqual(self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true); SELECT jsonb_build_object('count',count(*)) FROM {table}"), dict(count=0))

if __name__ == '__main__':
    unittest.main()
