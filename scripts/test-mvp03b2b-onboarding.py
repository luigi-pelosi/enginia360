#!/usr/bin/env python3
"""Final-only real PostgreSQL onboarding proof; never accepts a deployed target."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('roles',ROOT/'scripts/test-mvp03b1-roles.py')
assert spec and spec.loader
roles=importlib.util.module_from_spec(spec);spec.loader.exec_module(roles)
# Reuse fixture helpers, not its test methods or historical acceptance campaign.
Helpers=type('Helpers',(),{name:value for name,value in vars(roles.RoleTests).items() if callable(value) and not name.startswith(('test_','__'))})
def quote(value): return "'"+str(value).replace("'","''")+"'"
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated SQL required')
class OnboardingTests(Helpers,unittest.TestCase):
 def payload_onboarding(self,operation='invite',resource=None,revision=0,**changes):
  return dict(dict(commandId=str(uuid.uuid4()),operation=operation,resourceId=resource,expectedRevision=revision),**changes)
 def statement_onboarding(self,p,target=None):
  return self.actor_settings()+"SELECT organization_access.command_onboarding("+quote(target or self.tenant)+","+quote(json.dumps(p))+"::jsonb);"
 def onboarding(self,p,target=None):
  return self.app_result("SELECT organization_access.command_onboarding("+quote(target or self.tenant)+","+quote(json.dumps(p))+"::jsonb)")
 def directory(self,target=None):
  return self.app_result("SELECT organization_access.read_onboarding("+(quote(target) if target else 'NULL::uuid')+")")
 def begin(self,invitation,subject=None,issuer=None):
  return self.app_result("SELECT set_config('app.identity_issuer',"+quote(issuer or self.new_issuer)+",true),set_config('app.external_subject',"+quote(subject or self.new_subject)+",true);SELECT organization_access.begin_onboarding("+quote(invitation)+")")
 def pending(self,request,tenant=None,subject=None):
  return self.app_result("SELECT set_config('app.identity_issuer',"+quote(self.new_issuer)+",true),set_config('app.external_subject',"+quote(subject or self.new_subject)+",true);SELECT organization_access.pending_onboarding_status("+quote(request)+","+quote(tenant or self.tenant)+")")
 def new_request(self):
  self.prepare_user_admin();self.new_subject='Opaque '+str(uuid.uuid4());self.new_issuer='https://new.test'
  self.invite=self.payload_onboarding();self.invitation=self.onboarding(self.invite)['snapshot']['invitationId']
  self.request=self.begin(self.invitation)['requestId'];self.approval=self.payload_onboarding('approve',self.request,1)
 def count_bindings(self): return self.sql('SELECT count(*) FROM organization_access.external_identity_bindings')
 def test_complete_delegate_first_binding_disabled_membership_then_distinct_enable_and_role(self):
  self.new_request();before=self.count_bindings()
  grant_tables=('membership_scopes','common_edit_permissions','company_permissions','delegation_mandates','delegated_scopes','tenant_role_objects','organization_delegations')
  grants_before={table:self.sql("SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') FROM organization_access."+table+' t') for table in grant_tables}
  first=self.onboarding(self.approval)
  self.assertEqual(grants_before,{table:self.sql("SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') FROM organization_access."+table+' t') for table in grant_tables},'first binding must not insert or edit any independent grant/delegation origin')
  self.assertEqual(first['state'],'applied');snap=first['snapshot'];self.assertFalse(snap['enabled'])
  self.assertEqual(self.count_bindings(),str(int(before)+1));self.assertTrue(self.pending(self.request)['approved'])
  row=next(m for m in self.role_read()['memberships'] if m['membershipId']==snap['membershipId'])
  self.assertFalse(row['accessEnabled']);self.assertFalse(row['active']);self.assertFalse(row['organizationDelegationActive'])
  self.assertEqual(row['accessRevision'],1)
  self.assertEqual(self.onboarding(self.approval),dict(state='replayed',snapshot=snap))
  enable=dict(commandId=str(uuid.uuid4()),membershipId=row['membershipId'],internalIdentityId=row['internalIdentityId'],bindingHash=row['bindingHash'],expectedRevision=1,enabled=True)
  self.assertEqual(self.app_result("SELECT organization_access.command_membership_access("+quote(self.tenant)+","+quote(json.dumps(enable))+"::jsonb)")['state'],'applied')
  p=self.role_command(self.permission_payload())['snapshot'];r=self.role_command(self.role_payload('role',label='Explicit',permissionIds=[p['resourceId']]))['snapshot']
  assignment=self.role_payload('assignment',membershipId=row['membershipId'],internalIdentityId=row['internalIdentityId'],bindingHash=row['bindingHash'],roleId=r['resourceId'],active=True)
  self.assertEqual(self.role_command(assignment)['state'],'applied')
  self.target=dict(internalIdentityId=row['internalIdentityId'],issuer=self.new_issuer,subject=self.new_subject);self.target_member=row['membershipId'];self.actor=self.target
  self.assertEqual(self.effective(),['organization-context.read'])
  self.actor=self.delegate
  disable=dict(enable,commandId=str(uuid.uuid4()),expectedRevision=2,enabled=False)
  self.app_result("SELECT organization_access.command_membership_access("+quote(self.tenant)+","+quote(json.dumps(disable))+"::jsonb)")
  self.assertEqual(self.onboarding(self.approval)['state'],'replayed')
  self.assertFalse(next(m for m in self.role_read()['memberships'] if m['membershipId']==row['membershipId'])['accessEnabled'])
  self.actor=self.target;self.assertEqual(self.effective(),[])
 def test_exact_pending_subject_tenant_and_single_request_no_public_customer_oracle(self):
  self.new_request();self.assertEqual(self.begin(self.invitation)['requestId'],self.request)
  self.assertEqual(self.begin(self.invitation,subject='Different'),dict(state='forbidden'))
  self.assertEqual(self.pending(self.request,subject='Different'),dict(state='forbidden'))
  self.assertEqual(self.pending(self.request,tenant=str(uuid.uuid4())),dict(state='forbidden'))
  self.assertEqual(self.onboarding(self.approval,str(uuid.uuid4())),dict(state='forbidden'))
  self.assertEqual(self.directory(str(uuid.uuid4())),dict(state='forbidden'))
  self.assertNotIn('tenants',self.directory());self.assertEqual(len(self.directory()['requests']),1)
  self.actor=self.owner_actor;self.assertEqual(self.directory()['mode'],'owner')
  self.actor=self.delegate;self.sql(f'''UPDATE organization_access.tenant_role_objects SET "Data"="Data"||'{{"active":false}}',"Revision"=2 WHERE "Kind"='delegation' ''')
  self.assertEqual(self.directory(),dict(state='forbidden'));self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'))
 def test_current_actor_disable_revoke_organization_only_and_owner_explicit_target(self):
  self.new_request();self.sql(f'''INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1)''')
  self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'))
  self.sql(f'''UPDATE organization_access.membership_access_state SET "Enabled"=true,"Revision"=2 WHERE "MembershipId"='{self.member}' ''')
  self.actor=self.owner_actor;revoke=dict(self.grant,commandId=str(uuid.uuid4()),resourceId=self.grant_snapshot['resourceId'],expectedRevision=1,active=False);self.role_command(revoke)
  self.sql(f'''INSERT INTO organization_access.organization_delegations VALUES('{self.member}','{self.tenant}','{self.delegate['internalIdentityId']}',decode('{self.grant['bindingHash']}','hex'),true,1)''')
  self.actor=self.delegate;self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'))
  self.actor=self.owner_actor;self.assertEqual(self.onboarding(self.approval)['state'],'applied')
 def test_replay_conflict_rebind_and_expiry_never_mutate_later_state(self):
  self.new_request();first=self.onboarding(self.approval)
  self.assertEqual(self.onboarding(dict(self.approval,operation='revoke'))['state'],'forbidden')
  self.assertEqual(self.onboarding(dict(self.approval,expectedRevision=2))['state'],'conflict')
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Replacement' WHERE "InternalIdentityId"='{first['snapshot']['internalIdentityId']}' ''')
  self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'))
 def test_invitation_revoke_expiry_and_pending_proof_expiry(self):
  self.new_request();self.sql(f'''UPDATE organization_access.onboarding_requests SET "ExpiresAt"=clock_timestamp()-interval '1 second' WHERE "Id"='{self.request}' ''')
  self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'));self.assertEqual(self.pending(self.request),dict(state='forbidden'))
  self.sql(f'''UPDATE organization_access.onboarding_requests SET "ExpiresAt"=clock_timestamp()+interval '1 minute' WHERE "Id"='{self.request}' ''')
  self.assertEqual(self.onboarding(self.payload_onboarding('revoke',self.invitation,1))['state'],'applied')
  self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'));self.assertEqual(self.begin(self.invitation),dict(state='forbidden'))
  another=self.onboarding(self.payload_onboarding())['snapshot']['invitationId']
  self.sql(f'''UPDATE organization_access.onboarding_invitations SET "ExpiresAt"=clock_timestamp()-interval '1 second' WHERE "Id"='{another}' ''')
  self.assertEqual(self.begin(another),dict(state='forbidden'))
 def test_existing_binding_hidden_by_rls_conflicts_without_takeover_or_second_membership(self):
  self.new_request();identity=str(uuid.uuid4());foreign=str(uuid.uuid4())
  self.sql(f'''INSERT INTO organization_access.tenants("Id","Name") VALUES('{foreign}','Foreign');INSERT INTO organization_access.external_identity_bindings VALUES('{identity}','{self.new_issuer}','{self.new_subject}');INSERT INTO organization_access.memberships VALUES(gen_random_uuid(),'{foreign}','{identity}')''')
  before=self.count_bindings();self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'));self.assertEqual(self.count_bindings(),before)
  self.assertEqual(self.sql(f'''SELECT count(*) FROM organization_access.memberships WHERE "IdentitySubject"='{identity}' '''),'1')
  self.assertEqual(self.begin(self.invitation),dict(state='forbidden'))
 def test_atomic_audit_insert_and_deferred_commit_roll_back_every_new_row(self):
  self.new_request();before=self.count_bindings()
  self.sql("CREATE FUNCTION organization_access.fixture_onboarding_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.\"Outcome\"='applied' THEN RAISE EXCEPTION 'synthetic onboarding audit refusal'; END IF;RETURN NEW; END $$")
  for deferred in (False,True):
   self.sql(('CREATE CONSTRAINT TRIGGER' if deferred else 'CREATE TRIGGER')+' fixture_onboarding_fail '+('AFTER' if deferred else 'BEFORE')+' INSERT ON organization_access.onboarding_audit '+('DEFERRABLE INITIALLY DEFERRED ' if deferred else '')+'FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_onboarding_fail()')
   env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
   result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.statement_onboarding(self.approval)+'COMMIT;',env=env,capture_output=True,text=True,timeout=20)
   self.assertNotEqual(result.returncode,0);self.assertIn('synthetic onboarding audit refusal',result.stderr)
   self.assertEqual(self.count_bindings(),before);self.assertFalse(self.pending(self.request)['approved']);self.assertEqual(self.sql('SELECT count(*) FROM organization_access.membership_access_state'),'0')
   self.sql('DROP TRIGGER fixture_onboarding_fail ON organization_access.onboarding_audit')
  self.assertEqual(self.onboarding(self.approval)['state'],'applied')
 def test_physical_duplicate_and_different_key_approvals_and_revoke_both_orders(self):
  self.new_request();p=self.approval
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.statement_onboarding(p),'app')]*2)
  self.assertEqual(sorted(r['state'] for r in results),['applied','replayed'])
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.onboarding_audit WHERE "Request"->>\'operation\'=\'approve\' AND "Outcome"=\'applied\''),'1')
  self.new_subject='Opaque '+str(uuid.uuid4())
  invite=self.onboarding(self.payload_onboarding())['snapshot']['invitationId'];req=self.begin(invite)['requestId'];p=self.payload_onboarding('approve',req,1)
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.statement_onboarding(p),'app'),(self.statement_onboarding(dict(p,commandId=str(uuid.uuid4()))),'app')])
  self.assertEqual(sorted(r['state'] for r in results),['applied','conflict'])
 def test_physical_delegate_revocation_disable_and_approval_commit_orders(self):
  self.new_request();self.actor=self.owner_actor
  revoke=dict(self.grant,commandId=str(uuid.uuid4()),resourceId=self.grant_snapshot['resourceId'],expectedRevision=1,active=False)
  revocation=self.role_statement(revoke);self.actor=self.delegate
  results,_=self.barrier_race(revocation,[(self.statement_onboarding(self.approval),'app')],holder_role='app')
  self.assertEqual(results,[dict(state='forbidden')]);self.assertFalse(self.pending(self.request)['approved'])
  self.actor=self.owner_actor;self.role_command(dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=2,active=True));self.actor=self.delegate
  self.actor=self.owner_actor;revoke2=dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=3);revocation=self.role_statement(revoke2);self.actor=self.delegate
  results,held=self.barrier_race(self.statement_onboarding(self.approval),[(revocation,'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'))
 def test_physical_enabled_actor_disable_both_commit_orders(self):
  self.new_request();self.actor=self.owner_actor
  member=next(m for m in self.role_read(self.tenant)['memberships'] if m['membershipId']==self.member)
  disable=dict(commandId=str(uuid.uuid4()),membershipId=self.member,internalIdentityId=member['internalIdentityId'],bindingHash=member['bindingHash'],expectedRevision=0,enabled=False)
  effect=self.actor_settings()+"SELECT organization_access.command_membership_access("+quote(self.tenant)+","+quote(json.dumps(disable))+"::jsonb);"
  self.actor=self.delegate
  results,_=self.barrier_race(effect,[(self.statement_onboarding(self.approval),'app')],holder_role='app')
  self.assertEqual(results,[dict(state='forbidden')]);self.assertFalse(self.pending(self.request)['approved'])
  self.actor=self.owner_actor;enable=dict(disable,commandId=str(uuid.uuid4()),expectedRevision=1,enabled=True)
  self.app_result("SELECT organization_access.command_membership_access("+quote(self.tenant)+","+quote(json.dumps(enable))+"::jsonb)")
  disable=dict(disable,commandId=str(uuid.uuid4()),expectedRevision=2)
  effect=self.actor_settings()+"SELECT organization_access.command_membership_access("+quote(self.tenant)+","+quote(json.dumps(disable))+"::jsonb);"
  self.actor=self.delegate
  results,held=self.barrier_race(self.statement_onboarding(self.approval),[(effect,'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'))
 def test_physical_invitation_revocation_and_approval_both_commit_orders(self):
  self.new_request();revoke=self.payload_onboarding('revoke',self.invitation,1)
  results,_=self.barrier_race(self.statement_onboarding(revoke),[(self.statement_onboarding(self.approval),'app')],holder_role='app')
  self.assertEqual(results,[dict(state='forbidden')])
  invite=self.onboarding(self.payload_onboarding())['snapshot']['invitationId'];request=self.begin(invite)['requestId']
  approval=self.payload_onboarding('approve',request,1);revoke=self.payload_onboarding('revoke',invite,1)
  results,held=self.barrier_race(self.statement_onboarding(approval),[(self.statement_onboarding(revoke),'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.onboarding(approval)['state'],'replayed')
 def test_mid_insert_hidden_internal_identity_or_membership_collision_rolls_back_binding(self):
  self.new_request();before=self.count_bindings()
  # Fixture-only trigger simulates a generated UUID/internal membership collision;
  # application never supplies or chooses an existing internal identity.
  self.sql("CREATE FUNCTION organization_access.fixture_onboarding_collision() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN NEW.\"IdentitySubject\":='"+self.delegate['internalIdentityId']+"';RETURN NEW;END $$;CREATE TRIGGER fixture_onboarding_collision BEFORE INSERT ON organization_access.memberships FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_onboarding_collision()")
  self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'));self.assertEqual(self.count_bindings(),before)
  self.assertFalse(self.pending(self.request)['approved']);self.assertEqual(self.sql('SELECT count(*) FROM organization_access.membership_access_state'),'0')
  self.sql('DROP TRIGGER fixture_onboarding_collision ON organization_access.memberships;DROP FUNCTION organization_access.fixture_onboarding_collision()')
  self.sql("CREATE FUNCTION organization_access.fixture_onboarding_identity_collision() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN NEW.\"InternalIdentityId\":='"+self.delegate['internalIdentityId']+"';RETURN NEW;END $$;CREATE TRIGGER fixture_onboarding_identity_collision BEFORE INSERT ON organization_access.external_identity_bindings FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_onboarding_identity_collision()")
  self.assertEqual(self.onboarding(self.approval),dict(state='forbidden'));self.assertEqual(self.count_bindings(),before)
  self.assertFalse(self.pending(self.request)['approved'])
  self.sql('DROP TRIGGER fixture_onboarding_identity_collision ON organization_access.external_identity_bindings;DROP FUNCTION organization_access.fixture_onboarding_identity_collision()')
  self.assertEqual(self.onboarding(self.approval)['state'],'applied')
 def test_two_invitations_same_verified_subject_cannot_expand_ordinary_membership_cardinality(self):
  self.new_request();invite=self.onboarding(self.payload_onboarding())['snapshot']['invitationId']
  other=self.begin(invite)['requestId'];p=self.payload_onboarding('approve',other,1)
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.statement_onboarding(self.approval),'app'),(self.statement_onboarding(p),'app')])
  self.assertEqual(sorted(r['state'] for r in results),['applied','forbidden'])
  self.assertEqual(self.sql("SELECT count(*) FROM organization_access.external_identity_bindings WHERE \"Issuer\"="+quote(self.new_issuer)+" AND \"Subject\"="+quote(self.new_subject)),'1')
 def assert_old_snapshot_refuses_current_row_change(self,change,owner=False):
  self.new_request()
  if owner:self.actor=self.owner_actor
  before=self.count_bindings()
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  process=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1','-v','VERBOSITY=verbose'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
  try:
   # Establish an old real MVCC snapshot BEFORE taking the owning advisory lock.
   process.stdin.write('BEGIN ISOLATION LEVEL REPEATABLE READ;'+self.actor_settings()+'SELECT txid_current_snapshot();\\echo SNAPSHOT\n');process.stdin.flush()
   while True:
    line=process.stdout.readline().strip()
    if line=='SNAPSHOT':break
    self.assertIsNone(process.poll(),'old-snapshot fixture failed before marker')
   # This commits on a separate physical infrastructure connection. No app DML.
   self.sql(change(self))
   process.stdin.write(self.statement_onboarding(self.approval)+'COMMIT;\\q\n');process.stdin.flush()
   output,error=process.communicate(timeout=20)
   self.assertNotEqual(process.returncode,0,(output,error))
   self.assertIn('40001',error,'current exact authority/binding row lock must reject the stale snapshot')
   self.assertEqual(self.count_bindings(),before)
   self.assertFalse(self.pending(self.request)['approved'])
  finally:
   if process.poll() is None:process.kill();process.communicate(timeout=5)
 def test_old_snapshot_cannot_approve_after_delegate_revision_revocation(self):
  self.assert_old_snapshot_refuses_current_row_change(lambda s:"UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"||'{\"active\":false}',\"Revision\"=\"Revision\"+1 WHERE \"Id\"="+quote(s.grant_snapshot['resourceId']))
 def test_old_snapshot_cannot_approve_after_enabled_actor_disable(self):
  self.assert_old_snapshot_refuses_current_row_change(lambda s:f'''INSERT INTO organization_access.membership_access_state VALUES('{s.member}','{s.tenant}',false,1)''')
 def test_old_snapshot_cannot_approve_after_exact_actor_binding_change(self):
  self.assert_old_snapshot_refuses_current_row_change(lambda s:"UPDATE organization_access.external_identity_bindings SET \"Subject\"='Changed current binding' WHERE \"InternalIdentityId\"="+quote(s.delegate['internalIdentityId']))
 def test_old_snapshot_cannot_approve_after_global_authority_revocation(self):
  self.assert_old_snapshot_refuses_current_row_change(lambda s:'UPDATE organization_access.platform_authority SET "Active"=false,"Revision"="Revision"+1',owner=True)
 def test_minimized_immutable_audit_closed_input_private_tables_and_helpers(self):
  self.new_request();self.onboarding(self.approval)
  for table in ('onboarding_invitations','onboarding_requests','onboarding_audit'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','organization_access.{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
   self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='organization_access.{table}'::regclass"),'t')
  for command in ('UPDATE organization_access.onboarding_audit SET "Request"=\'{}\'','DELETE FROM organization_access.onboarding_audit','TRUNCATE organization_access.onboarding_audit'):
   self.assertNotEqual(self.owner_sql(command,ok=False).returncode,0)
  for change in (dict(extra=True),dict(expectedRevision=True),dict(expectedRevision=2147483647),dict(operation='grant'),dict(resourceId='bad')):
   self.assertEqual(self.onboarding(dict(self.approval,**change))['state'],'invalid')
  self.onboarding(self.payload_onboarding('approve',str(uuid.uuid4()),1))
  rows=json.loads(self.sql('SELECT jsonb_agg(to_jsonb(a)) FROM organization_access.onboarding_audit a'))
  for row in rows:
   self.assertNotIn(self.new_subject,json.dumps(row));self.assertNotIn(self.new_issuer,json.dumps(row))
   self.assertTrue(row['BindingHash']);self.assertTrue(row['OccurredAt'])
   if row['Outcome']=='forbidden':self.assertIsNone(row['TenantId']);self.assertEqual(row['Request'],{})
  for helper in ('onboarding_authority(uuid)','apply_onboarding(uuid,jsonb,jsonb)'):
   self.assertEqual(self.sql(f"SELECT has_function_privilege('{os.environ['R00_APP_USER']}','organization_access.{helper}','EXECUTE')"),'f')
if __name__=='__main__': unittest.main()
