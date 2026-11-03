#!/usr/bin/env python3
"""Real PostgreSQL role administration acceptance; no supplied deployed target."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('organization',ROOT/'scripts/test-mvp02b-organization.py')
assert spec and spec.loader
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated SQL required')
class RoleTests(unittest.TestCase):
 setUp=base.OrganizationTests.setUp
 tearDown=base.OrganizationTests.tearDown
 sql=base.OrganizationTests.sql
 start_migration=base.OrganizationTests.start_migration
 migrate=base.OrganizationTests.migrate
 prepare=base.OrganizationTests.prepare
 payload=base.OrganizationTests.payload
 owner_sql=base.OrganizationTests.owner_sql
 command=base.OrganizationTests.command
 prepare_org=base.OrganizationTests.prepare_org
 actor_settings=base.OrganizationTests.actor_settings
 app_result=base.OrganizationTests.app_result
 org_payload=base.OrganizationTests.org_payload
 org_command=base.OrganizationTests.org_command
 create_tenant=base.OrganizationTests.create_tenant
 create_company=base.OrganizationTests.create_company
 create_site=base.OrganizationTests.create_site
 prepare_delegate=base.OrganizationTests.prepare_delegate
 barrier_race=base.OrganizationTests.barrier_race
 def role_read(self,target=None):
  literal="'"+target+"'::uuid" if target else 'NULL::uuid'
  return self.app_result('SELECT organization_access.read_tenant_roles('+literal+')')
 def test_owner_selector_separates_user_authority_from_organization(self):
  self.prepare_delegate()
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.read_tenant_roles(uuid)') IS NOT NULL"),'t','user administration selector missing')
  result=self.role_read(self.tenant)
  self.assertEqual(result['state'],'ok');self.assertEqual(result['mode'],'owner')
  self.assertEqual(len(result['memberships']),1)
  self.assertEqual(result['memberships'][0]['membershipId'],self.member)
  self.assertFalse(result['memberships'][0]['active']);self.assertEqual(result['memberships'][0]['revision'],0)
  self.assertEqual(result['actions'],['organization-context.read','organization-context.write'])
  self.assertEqual(result['permissions'],[]);self.assertEqual(result['roles'],[]);self.assertEqual(result['assignments'],[])
  self.actor=self.delegate
  self.assertEqual(self.role_read(self.tenant),dict(state='forbidden'))
 def role_payload(self,kind='delegation',**changes):
  row=self.role_read(self.tenant)['memberships'][0]
  values=dict(commandId=str(uuid.uuid4()),kind=kind,resourceId=None,expectedRevision=0)
  if kind=='delegation':values.update(membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=row['bindingHash'],active=True)
  return dict(values,**changes)
 def role_command(self,p,target=None):
  return self.app_result("SELECT organization_access.command_tenant_role('"+(target or self.tenant)+"','"+json.dumps(p).replace("'","''")+"')")
 def test_distinct_user_delegation_current_read_and_replay_revocation(self):
  self.prepare_delegate()
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.command_tenant_role(uuid,jsonb)') IS NOT NULL"),'t','distinct user-administration command missing')
  p=self.role_payload();first=self.role_command(p)
  self.assertEqual(first['state'],'applied');snap=first['snapshot']
  self.assertEqual(snap['revision'],1);self.assertTrue(snap['active'])
  self.assertEqual(self.role_command(p),dict(state='replayed',snapshot=snap))
  self.assertEqual(self.role_command(dict(p,active=False))['state'],'conflict')
  self.actor=self.delegate
  self.assertEqual(self.role_read()['state'],'ok');self.assertEqual(self.role_read()['mode'],'delegate')
  self.assertEqual(self.role_command(p),dict(state='forbidden'))
  self.assertEqual(self.app_result("SELECT organization_access.read_organization_workspace()"),dict(state='forbidden'))
  self.actor=self.owner_actor
  revoke=dict(p,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=1,active=False)
  self.assertEqual(self.role_command(revoke)['snapshot']['revision'],2)
  self.actor=self.delegate;self.assertEqual(self.role_read(),dict(state='forbidden'))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenant_role_audit WHERE "Outcome"=\'applied\''),'2')
 def prepare_user_admin(self):
  self.prepare_delegate();self.grant=self.role_payload();self.grant_snapshot=self.role_command(self.grant)['snapshot']
  self.company=self.create_company(self.tenant);self.site=self.create_site(self.tenant,self.company)
  warehouse=self.org_command(self.org_payload(kind='warehouse',tenantId=self.tenant,parentId=self.site,name='Synthetic warehouse'),self.tenant)
  self.warehouse=warehouse['snapshot']['resourceId'];self.actor=self.delegate
 def permission_payload(self,**changes):
  return self.role_payload('permission',label='Configured permission',action='organization-context.read',legalEntityId=self.company,siteId=self.site,warehouseId=self.warehouse,**changes)
 def test_delegate_create_edit_permission_exact_supported_scope_and_historical_replay(self):
  self.prepare_user_admin();p=self.permission_payload();first=self.role_command(p)
  self.assertEqual(first['state'],'applied','delegate cannot create executable permission definition')
  snap=first['snapshot'];self.assertEqual(snap['action'],'organization-context.read')
  edit=dict(p,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=1,label='SUPER ADMIN',action='organization-context.write')
  self.assertEqual(self.role_command(edit)['snapshot']['revision'],2)
  self.assertEqual(self.role_command(p),dict(state='replayed',snapshot=snap))
  self.assertEqual(self.role_read()['permissions'][0]['action'],'organization-context.write')
  for change in [dict(action='*'),dict(action='organization-context.*'),dict(action='tenant.create'),dict(action='counterparties.read'),dict(legalEntityId=None),dict(siteId=str(uuid.uuid4())),dict(warehouseId=str(uuid.uuid4())),dict(label='x'*101)]:
   self.assertIn(self.role_command(dict(p,commandId=str(uuid.uuid4()),**change))['state'],('invalid','forbidden'))
  self.assertEqual(self.role_command(dict(edit,commandId=str(uuid.uuid4())))['state'],'conflict')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenant_role_audit WHERE "Outcome"=\'applied\''),'3')
 def test_delegate_composes_edits_role_without_creating_administrator(self):
  self.prepare_user_admin();permission=self.role_command(self.permission_payload())['snapshot']
  p=self.role_payload('role',label='SUPER ADMIN',permissionIds=[permission['resourceId']]);first=self.role_command(p)
  self.assertEqual(first['state'],'applied','configurable role composition missing')
  snap=first['snapshot'];edit=dict(p,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=1,permissionIds=[])
  self.assertEqual(self.role_command(edit)['snapshot']['revision'],2)
  self.assertEqual(self.role_command(p),dict(state='replayed',snapshot=snap))
  self.assertEqual(self.role_read()['roles'][0]['permissionIds'],[])
  for ids in [[permission['resourceId']]*2,[str(uuid.uuid4())],['*'],[None],True]:
   self.assertIn(self.role_command(dict(p,commandId=str(uuid.uuid4()),permissionIds=ids))['state'],('invalid','forbidden'))
  self.assertEqual(self.app_result('SELECT organization_access.read_organization_workspace()'),dict(state='forbidden'))
 def prepare_role(self):
  self.prepare_user_admin();self.permission_command=self.permission_payload();self.permission=self.role_command(self.permission_command)['snapshot']
  self.role_creation=self.role_payload('role',label='Configured role',permissionIds=[self.permission['resourceId']]);self.role=self.role_command(self.role_creation)['snapshot']
  self.target=dict(internalIdentityId=str(uuid.uuid4()),issuer='https://target.test',subject='Target');self.target_member=str(uuid.uuid4())
  self.sql(f'''INSERT INTO organization_access.external_identity_bindings VALUES('{self.target['internalIdentityId']}','{self.target['issuer']}','{self.target['subject']}');INSERT INTO organization_access.memberships VALUES('{self.target_member}','{self.tenant}','{self.target['internalIdentityId']}')''')
  row=next(m for m in self.role_read()['memberships'] if m['membershipId']==self.target_member)
  self.assignment=self.role_payload('assignment',roleId=self.role['resourceId'],membershipId=self.target_member,internalIdentityId=self.target['internalIdentityId'],bindingHash=row['bindingHash'],active=True)
 def test_existing_member_assignment_revoke_and_target_binding_exact_replay(self):
  self.prepare_role();first=self.role_command(self.assignment)
  self.assertEqual(first['state'],'applied','existing trusted member role assignment missing')
  snap=first['snapshot'];self.assertEqual(self.role_command(self.assignment),dict(state='replayed',snapshot=snap))
  revoke=dict(self.assignment,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=1,active=False)
  self.assertEqual(self.role_command(revoke)['snapshot']['revision'],2)
  self.assertEqual(self.role_command(dict(self.assignment,commandId=str(uuid.uuid4())))['state'],'conflict')
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Rebound' WHERE "InternalIdentityId"='{self.target['internalIdentityId']}' ''')
  self.assertEqual(self.role_command(self.assignment),dict(state='forbidden'))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'),'2')
 def effective(self):
  return self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT coalesce(jsonb_agg(\"Permission\" ORDER BY \"Permission\"),'[]') FROM organization_access.effective_membership_scopes WHERE \"MembershipId\"='{self.target_member}'")
 def test_actual_effective_scopes_reflect_permission_role_and_assignment_changes(self):
  self.prepare_role();self.assertEqual(self.effective(),[])
  assigned=self.role_command(self.assignment)['snapshot'];self.actor=self.target
  self.assertEqual(self.effective(),['organization-context.read'],'assigned role is not consumed by current authorization view')
  self.actor=self.delegate
  edit=dict(self.permission_command,commandId=str(uuid.uuid4()),resourceId=self.permission['resourceId'],expectedRevision=1,action='organization-context.write')
  self.role_command(edit);self.actor=self.target;self.assertEqual(self.effective(),['organization-context.write'])
  self.actor=self.delegate
  empty=dict(self.role_creation,commandId=str(uuid.uuid4()),resourceId=self.role['resourceId'],expectedRevision=1,permissionIds=[])
  self.role_command(empty);self.actor=self.target;self.assertEqual(self.effective(),[])
  self.actor=self.delegate
  self.role_command(dict(empty,commandId=str(uuid.uuid4()),expectedRevision=2,permissionIds=[self.permission['resourceId']]))
  self.actor=self.target;self.assertEqual(self.effective(),['organization-context.write'])
  self.actor=self.delegate
  self.role_command(dict(self.assignment,commandId=str(uuid.uuid4()),resourceId=assigned['resourceId'],expectedRevision=1,active=False))
  self.actor=self.target;self.assertEqual(self.effective(),[])
 def test_nonexistent_owner_target_is_controlled_and_writes_no_object(self):
  self.prepare_user_admin();self.actor=self.owner_actor
  p=self.role_payload('role',label='Bounded role',permissionIds=[])
  self.assertEqual(self.role_command(p,str(uuid.uuid4())),dict(state='forbidden'),'nonexistent target must be controlled, never a foreign-key outage')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenant_role_objects WHERE "Kind"=\'role\''),'0')
 def role_statement(self,p,target=None):
  return self.actor_settings()+"SELECT organization_access.command_tenant_role('"+(target or self.tenant)+"','"+json.dumps(p).replace("'","''")+"');"
 def test_regression_atomic_minimized_immutable_audit_and_direct_dml_denial(self):
  self.prepare_role();assignment=self.role_command(self.assignment)['snapshot']
  rows=json.loads(self.sql('SELECT jsonb_agg(to_jsonb(a) ORDER BY "OccurredAt") FROM organization_access.tenant_role_audit a WHERE "Outcome"=\'applied\''))
  self.assertEqual(len(rows),4)
  for row in rows:
   self.assertEqual(row['TenantId'],self.tenant);self.assertEqual(row['ResourceId'],row['After']['resourceId'])
   self.assertEqual(row['Request']['commandId'],row['CommandId']);self.assertEqual(row['Before'],{})
   self.assertEqual(row['After']['revision'],1);self.assertTrue(row['OccurredAt']);self.assertTrue(row['BindingHash'])
   self.assertNotIn('issuer',row['Request']);self.assertNotIn('subject',row['Request']);self.assertNotIn('email',row['Request'])
  self.assertEqual(rows[0]['Authority']['kind'],'owner')
  for row in rows[1:]:
   self.assertEqual(row['ActorId'],self.delegate['internalIdentityId']);self.assertEqual(row['Authority'],dict(kind='user-administration',resourceId=self.grant_snapshot['resourceId'],revision=1))
  revoke=dict(self.assignment,commandId=str(uuid.uuid4()),resourceId=assignment['resourceId'],expectedRevision=1,active=False)
  self.role_command(revoke)
  self.assertEqual(json.loads(self.sql('SELECT "Before" FROM organization_access.tenant_role_audit WHERE "CommandId"=\''+revoke['commandId']+'\'')),assignment)
  for table in ('tenant_role_objects','tenant_role_audit'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','organization_access.{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
   self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='organization_access.{table}'::regclass"),'t')
  for mutation in ('UPDATE organization_access.tenant_role_audit SET "Request"=\'{}\'','DELETE FROM organization_access.tenant_role_audit','TRUNCATE organization_access.tenant_role_audit'):
   self.assertNotEqual(self.owner_sql(mutation,ok=False).returncode,0)
  self.assertEqual(self.sql(f"SELECT has_function_privilege('{os.environ['R00_APP_USER']}','organization_access.apply_tenant_role(uuid,jsonb,jsonb)','EXECUTE')"),'f')
 def test_regression_every_mutation_audit_insert_and_deferred_commit_rollback(self):
  import subprocess
  self.prepare_role();assigned=self.role_command(self.assignment)['snapshot']
  self.sql("CREATE FUNCTION organization_access.fixture_role_audit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic role audit refusal'; END $$")
  commands=[(self.delegate,self.permission_payload()),(self.delegate,self.role_payload('role',label='Another',permissionIds=[])),
   (self.delegate,dict(self.permission_command,commandId=str(uuid.uuid4()),resourceId=self.permission['resourceId'],expectedRevision=1,label='Edited')),
   (self.delegate,dict(self.role_creation,commandId=str(uuid.uuid4()),resourceId=self.role['resourceId'],expectedRevision=1,permissionIds=[])),
   (self.delegate,dict(self.assignment,commandId=str(uuid.uuid4()),resourceId=assigned['resourceId'],expectedRevision=1,active=False)),
   (self.owner_actor,dict(self.grant,commandId=str(uuid.uuid4()),resourceId=self.grant_snapshot['resourceId'],expectedRevision=1,active=False))]
  rows=self.role_read()['memberships'];self_row=next(m for m in rows if m['membershipId']==self.member);target_row=next(m for m in rows if m['membershipId']==self.target_member)
  commands.extend([
   (self.delegate,self.role_payload('assignment',roleId=self.role['resourceId'],membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=self_row['bindingHash'],active=True)),
   (self.owner_actor,dict(self.grant,commandId=str(uuid.uuid4()),membershipId=self.target_member,internalIdentityId=self.target['internalIdentityId'],bindingHash=target_row['bindingHash']))
  ])
  for timing in ('BEFORE','DEFERRED'):
   statement='CREATE TRIGGER fixture_role_audit_fail BEFORE INSERT' if timing=='BEFORE' else 'CREATE CONSTRAINT TRIGGER fixture_role_audit_fail AFTER INSERT'
   self.sql(statement+' ON organization_access.tenant_role_audit '+('DEFERRABLE INITIALLY DEFERRED ' if timing=='DEFERRED' else '')+'FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_role_audit_fail()')
   baseline=self.sql('SELECT jsonb_agg(to_jsonb(o) ORDER BY "Id") FROM organization_access.tenant_role_objects o')
   for actor,payload in commands:
    self.actor=actor
    env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
    result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.role_statement(payload)+'COMMIT;',env=env,capture_output=True,text=True,timeout=20)
    self.assertNotEqual(result.returncode,0);self.assertIn('synthetic role audit refusal',result.stderr)
    self.assertEqual(self.sql('SELECT jsonb_agg(to_jsonb(o) ORDER BY "Id") FROM organization_access.tenant_role_objects o'),baseline)
    self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenant_role_audit'),'4')
   self.sql('DROP TRIGGER fixture_role_audit_fail ON organization_access.tenant_role_audit')
 def test_regression_physical_assignment_edit_replay_and_revoke_both_orderings(self):
  self.prepare_role()
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.role_statement(self.assignment),'app')]*2)
  self.assertEqual(sorted(r['state'] for r in results),['applied','replayed']);assigned=results[0]['snapshot']
  update=dict(self.role_creation,commandId=str(uuid.uuid4()),resourceId=self.role['resourceId'],expectedRevision=1,permissionIds=[])
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.role_statement(update),'app'),(self.role_statement(dict(update,commandId=str(uuid.uuid4()),label='Concurrent')),'app')])
  self.assertEqual(sorted(r['state'] for r in results),['applied','conflict'])
  self.actor=self.owner_actor
  revoke=dict(self.grant,commandId=str(uuid.uuid4()),resourceId=self.grant_snapshot['resourceId'],expectedRevision=1,active=False)
  holder=self.role_statement(revoke);self.actor=self.delegate
  results,_=self.barrier_race(holder,[(self.role_statement(self.assignment),'app'),(self.role_statement(self.permission_payload()),'app'),(self.role_statement(dict(update,commandId=str(uuid.uuid4()),expectedRevision=2)),'app')],holder_role='app')
  self.assertEqual(results,[dict(state='forbidden')]*3)
  self.actor=self.owner_actor
  self.role_command(dict(self.grant,commandId=str(uuid.uuid4()),resourceId=self.grant_snapshot['resourceId'],expectedRevision=2))
  worker=self.role_statement(dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=3));self.actor=self.delegate
  mutation=dict(update,commandId=str(uuid.uuid4()),expectedRevision=2)
  results,held=self.barrier_race(self.role_statement(mutation),[(worker,'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.role_command(mutation),dict(state='forbidden'))
 def test_regression_current_actor_target_binding_and_membership_loss(self):
  self.prepare_role();self.role_command(self.assignment)
  original=self.actor
  for key,value in [('issuer','https://foreign.test'),('subject','Other'),('internalIdentityId',str(uuid.uuid4()))]:
   self.actor=dict(original,**{key:value});self.assertEqual(self.role_read(),dict(state='forbidden'));self.assertEqual(self.role_command(self.assignment),dict(state='forbidden'))
  self.actor=original
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Rebound' WHERE "InternalIdentityId"='{original['internalIdentityId']}' ''')
  self.actor=dict(original,subject='Rebound');self.assertEqual(self.role_read(),dict(state='forbidden'))
  self.actor=self.target
  self.assertEqual(self.effective(),['organization-context.read'],'revoking administrator identity does not silently delete independent operative assignments')
  self.sql(f'''DELETE FROM organization_access.memberships WHERE "Id"='{self.target_member}' ''')
  self.assertEqual(self.effective(),[])
 def test_regression_closed_validation_cross_tenant_and_no_denial_payload_leak(self):
  self.prepare_role();self.actor=self.owner_actor;foreign=self.create_tenant();self.actor=self.delegate
  for p in [None,[],{},dict(self.assignment,extra=True),dict(self.assignment,expectedRevision=True),dict(self.assignment,expectedRevision=2147483647),dict(self.assignment,commandId='00000000-0000-0000-0000-000000000000'),dict(self.assignment,roleId='*'),dict(self.assignment,active='true'),dict(self.assignment,bindingHash='bad')]:
   self.assertIn(self.role_command(p)['state'],('invalid','forbidden'))
  self.assertEqual(self.role_command(self.assignment,foreign),dict(state='forbidden'))
  self.assertEqual(self.role_read(foreign),dict(state='forbidden'))
  self.assertEqual(self.role_command(dict(self.assignment,roleId=str(uuid.uuid4())))['state'],'forbidden')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenant_role_audit WHERE "Outcome"<>\'applied\' AND ("TenantId" IS NOT NULL OR "ResourceId" IS NOT NULL OR "Request"<>\'{}\' OR "Before"<>\'{}\' OR "After"<>\'{}\')'),'0')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenant_role_audit WHERE "Outcome"=\'applied\''),'3')
 def test_regression_physical_current_scope_reads_serialize_with_role_permission_and_assignment_revoke(self):
  self.prepare_role();assigned=self.role_command(self.assignment)['snapshot']
  self.actor=self.target
  read=self.actor_settings()+f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT jsonb_build_object('permissions',coalesce((SELECT jsonb_agg(\"Permission\") FROM organization_access.effective_membership_scopes WHERE \"MembershipId\"='{self.target_member}'),'[]'));"
  self.actor=self.delegate
  permission_edit=dict(self.permission_command,commandId=str(uuid.uuid4()),resourceId=self.permission['resourceId'],expectedRevision=1,action='organization-context.write')
  results,_=self.barrier_race(self.role_statement(permission_edit),[(read,'app')],holder_role='app')
  self.assertEqual(results,[dict(permissions=['organization-context.write'])])
  empty=dict(self.role_creation,commandId=str(uuid.uuid4()),resourceId=self.role['resourceId'],expectedRevision=1,permissionIds=[])
  results,_=self.barrier_race(self.role_statement(empty),[(read,'app')],holder_role='app');self.assertEqual(results,[dict(permissions=[])])
  self.role_command(dict(empty,commandId=str(uuid.uuid4()),expectedRevision=2,permissionIds=[self.permission['resourceId']]))
  revoke=dict(self.assignment,commandId=str(uuid.uuid4()),resourceId=assigned['resourceId'],expectedRevision=1,active=False)
  results,held=self.barrier_race(read,[(self.role_statement(revoke),'app')],holder_role='app')
  self.assertEqual(held[-1],dict(permissions=['organization-context.write']));self.assertEqual(results[0]['state'],'applied')
  self.actor=self.target;self.assertEqual(self.effective(),[])
  self.actor=self.delegate
  self.role_command(dict(self.assignment,commandId=str(uuid.uuid4()),resourceId=assigned['resourceId'],expectedRevision=2))
  results,_=self.barrier_race(self.role_statement(dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=3)),[(read,'app')],holder_role='app')
  self.assertEqual(results,[dict(permissions=[])])
 def test_regression_valid_owner_self_membership_and_revision_exhaustion_refused(self):
  self.prepare_role();self.actor=self.owner_actor;owner_member=str(uuid.uuid4())
  self.sql(f'''INSERT INTO organization_access.memberships VALUES('{owner_member}','{self.tenant}','{self.owner_actor['internalIdentityId']}')''')
  own=next(m for m in self.role_read(self.tenant)['memberships'] if m['membershipId']==owner_member)
  own_payload=dict(self.grant,commandId=str(uuid.uuid4()),membershipId=owner_member,internalIdentityId=own['internalIdentityId'],bindingHash=own['bindingHash'])
  self.assertEqual(self.role_command(own_payload),dict(state='forbidden'))
  self.actor=self.delegate
  self.sql(f'''UPDATE organization_access.tenant_role_objects SET "Revision"=2147483647 WHERE "Id"='{self.role['resourceId']}' ''')
  self.assertEqual(self.role_command(dict(self.role_creation,commandId=str(uuid.uuid4()),resourceId=self.role['resourceId'],expectedRevision=2147483646))['state'],'conflict')
 def test_effective_scope_rows_have_distinct_entity_ids_for_multiple_role_permissions(self):
  self.prepare_role()
  write=self.role_command(dict(self.permission_command,commandId=str(uuid.uuid4()),action='organization-context.write'))['snapshot']
  self.role_command(dict(self.role_creation,commandId=str(uuid.uuid4()),resourceId=self.role['resourceId'],expectedRevision=1,permissionIds=[self.permission['resourceId'],write['resourceId']]))
  self.role_command(self.assignment);self.actor=self.target
  result=self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT jsonb_build_object('rows',count(*),'ids',count(DISTINCT \"Id\")) FROM organization_access.effective_membership_scopes WHERE \"MembershipId\"='{self.target_member}'")
  self.assertEqual(result,dict(rows=2,ids=2),'effective MembershipScope primary identity must distinguish read/write rows')
if __name__=='__main__':unittest.main()
