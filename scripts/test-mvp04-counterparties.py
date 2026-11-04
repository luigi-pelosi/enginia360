#!/usr/bin/env python3
"""MVP04 final-only real PostgreSQL acceptance; no deployed target or business seed."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('roles',ROOT/'scripts/test-mvp03b1-roles.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated SQL required')
class CounterpartyTests(unittest.TestCase):
 # Reuse setup/teardown and trusted identity/role command helpers, not old tests.
 locals().update({k:v for k,v in vars(base.RoleTests).items() if callable(v) and not k.startswith('test')})
 def read(self,record=None,company=None,search=None,after=None):
  lit=lambda v: "'"+str(v).replace("'","''")+"'" if v is not None else 'NULL'
  return self.app_result('SELECT counterparties.management_read('+','.join([lit(search)+'::text',lit(after)+'::uuid',lit(record)+'::uuid',lit(company)+'::uuid'])+')')
 def cp(self,p):
  return self.app_result("SELECT counterparties.management_command('"+json.dumps(p).replace("'","''")+"')")
 def cp_statement(self,p):
  return self.actor_settings()+"SELECT counterparties.management_command('"+json.dumps(p).replace("'","''")+"');"
 def new(self,**changes):
  return dict(dict(commandId=str(uuid.uuid4()),operation='create',counterpartyId=None,expectedRevision=0,authorityVersion=1,legalName='Synthetic counterparty',fiscalIdentifier='',registeredOffice=''),**changes)
 def prepare_cp(self,authority=True):
  self.prepare_user_admin()
  self.assertEqual(self.read(),dict(state='forbidden'),'administrative delegation is not an operative grant')
  self.permissions=[]
  for action in ('counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write','counterparties.extensions.read','counterparties.extensions.write'):
   p=self.role_payload('permission',label=action,action=action,legalEntityId=self.company if '.extensions.' in action else None,siteId=None,warehouseId=None)
   self.permissions.append((p,self.role_command(p)['snapshot']))
  role=self.role_payload('role',label='Configured business operator',permissionIds=[s['resourceId'] for _,s in self.permissions]);self.cp_role_request=role;self.cp_role=self.role_command(role)['snapshot']
  member=next(m for m in self.role_read()['memberships'] if m['membershipId']==self.member)
  assignment=self.role_payload('assignment',roleId=self.cp_role['resourceId'],membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=member['bindingHash'],active=True)
  self.cp_assignment_request=assignment;self.cp_assignment=self.role_command(assignment)['snapshot']
  if authority:
   command,verification,source,profile=[str(uuid.uuid4()) for _ in range(4)]
   statement=f"BEGIN;SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT organization_access.establish_master_authority('{command}','{self.tenant}','{self.member}','{verification}',0,'Enginia360ToExternal','{source}','{profile}',ARRAY['{self.company}']::uuid[]);COMMIT;"
   result=self.owner_sql(statement);self.assertEqual(result.returncode,0,result.stderr);self.assertIn('applied',result.stdout)
 def test_empty_create_search_select_detail_edit_supplier_replay_and_duplicates(self):
  self.prepare_cp();self.assertEqual(self.read()['items'],[])
  p=self.new();first=self.cp(p);self.assertEqual(first['state'],'applied');snap=first['snapshot'];id=snap['id']
  self.assertEqual(snap['revision'],1);self.assertFalse(snap['isSupplier'])
  self.assertEqual(self.read(id)['detail'],snap);self.assertEqual(self.read(search='counterparty')['items'],[snap])
  role=dict(commandId=str(uuid.uuid4()),operation='supplier-role',counterpartyId=id,expectedRevision=1,authorityVersion=1,isSupplier=True)
  self.assertEqual(self.cp(role)['snapshot']['revision'],2)
  edit=self.new(operation='edit',counterpartyId=id,expectedRevision=2,legalName='Edited shared identity')
  self.assertEqual(self.cp(edit)['snapshot']['revision'],3)
  self.assertEqual(self.cp(p),dict(state='replayed',snapshot=snap),'replay must not return current state')
  self.assertEqual(self.cp(role)['state'],'replayed');self.assertEqual(self.cp(dict(p,legalName='changed'))['state'],'conflict')
  self.assertEqual(self.cp(self.new())['state'],'applied','duplicates do not imply merge or fiscal uniqueness')
  self.assertEqual(len(self.read()['items']),2)
 def test_catalog_scope_types_and_no_null_warehouse_wildcard(self):
  self.prepare_cp();self.assertEqual(self.effective_for_self(),[])
  for action,company,site,warehouse in [('organization-context.read',None,None,None),('counterparties.shared.read',self.company,None,None),('counterparties.extensions.read',None,None,None),('counterparties.extensions.write',self.company,self.site,None),('counterparties.shared.*',None,None,None)]:
   p=self.role_payload('permission',label='Invalid scope',action=action,legalEntityId=company,siteId=site,warehouseId=warehouse)
   self.assertIn(self.role_command(p)['state'],('invalid','forbidden'))
  self.assertEqual(self.read()['state'],'ready')
  self.sql("UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"-'siteId' WHERE \"TenantId\"='"+self.tenant+"' AND \"Kind\"='permission' AND \"Data\"->>'action'='counterparties.shared.read'")
  self.assertEqual(self.read(),dict(state='forbidden'),'missing scope keys are not explicit tenant-null scope')
 def effective_for_self(self):
  return self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT coalesce(jsonb_agg(\"Permission\"),'[]') FROM organization_access.effective_membership_scopes WHERE \"MembershipId\"='{self.member}'")
 def test_exact_types_keys_canonical_uuids_numeric_and_unicode_bounds(self):
  self.prepare_cp();p=self.new()
  for change in [dict(commandId=''),dict(commandId='AAAAAAAA-0000-0000-0000-000000000001'),dict(commandId='00000000-0000-0000-0000-000000000000'),dict(extra=True),dict(expectedRevision=True),dict(expectedRevision='0'),dict(authorityVersion=None),dict(legalName=' '),dict(legalName='x'*201),dict(fiscalIdentifier='x'*101),dict(registeredOffice='x'*501),dict(isSupplier=True),dict(operation='delete')]:
   self.assertEqual(self.cp(dict(p,**change))['state'],'invalid',change)
  self.assertEqual(self.cp(self.new(legalName='😀'*200))['state'],'applied')
 def test_authority_missing_external_and_stale_never_choose_local_writer(self):
  self.prepare_cp(authority=False);self.assertEqual(self.read()['authority']['state'],'missing');self.assertEqual(self.cp(self.new())['state'],'missing')
  command,verification,source,profile=[str(uuid.uuid4()) for _ in range(4)]
  result=self.owner_sql(f"BEGIN;SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT organization_access.establish_master_authority('{command}','{self.tenant}','{self.member}','{verification}',0,'ExternalToEnginia360','{source}','{profile}',ARRAY['{self.company}']::uuid[]);COMMIT;")
  self.assertEqual(result.returncode,0);self.assertEqual(self.cp(self.new())['state'],'external')
  self.assertEqual(self.read()['authority']['state'],'external')
 def test_separate_company_destination_revision_read_write_and_foreign_refusal(self):
  self.prepare_cp();id=self.cp(self.new())['snapshot']['id'];foreign=str(uuid.uuid4())
  p=dict(commandId=str(uuid.uuid4()),operation='destination-create',counterpartyId=id,expectedRevision=0,legalEntityId=self.company,destinationId=None,address='Synthetic private address')
  first=self.cp(p);self.assertEqual(first['state'],'applied');snap=first['snapshot']
  self.assertEqual(self.read(id,self.company)['destinations'][0]['address'],p['address']);self.assertEqual(self.read(id)['detail']['revision'],1)
  edit=dict(p,commandId=str(uuid.uuid4()),operation='destination-edit',destinationId=snap['id'],expectedRevision=1,address='Updated private address')
  self.assertEqual(self.cp(edit)['snapshot']['revision'],2);self.assertEqual(self.cp(p),dict(state='replayed',snapshot=snap))
  self.assertEqual(self.cp(dict(edit,commandId=str(uuid.uuid4())))['state'],'conflict')
  self.assertEqual(self.read(id,foreign),dict(state='forbidden'));self.assertEqual(self.cp(dict(p,commandId=str(uuid.uuid4()),legalEntityId=foreign))['state'],'forbidden')
  self.assertEqual(self.read(str(uuid.uuid4()))['state'],'not_found')
 def test_role_permission_assignment_edits_and_disable_apply_before_replay(self):
  self.prepare_cp();p=self.new();self.cp(p)
  edit=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  self.assertEqual(self.role_command(edit)['state'],'applied');self.assertEqual(self.cp(p),dict(state='forbidden'))
  self.role_command(dict(edit,commandId=str(uuid.uuid4()),expectedRevision=2,permissionIds=[s['resourceId'] for _,s in self.permissions]))
  request,snap=self.permissions[1]
  self.role_command(dict(request,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=1,action='counterparties.shared.edit'))
  self.assertEqual(self.cp(p),dict(state='forbidden'),'permission edit removes create on same identity')
  self.role_command(dict(request,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=2))
  self.assertEqual(self.cp(p)['state'],'replayed')
  self.sql(f'''INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1)''')
  self.assertEqual(self.read(),dict(state='forbidden'));self.assertEqual(self.cp(p),dict(state='forbidden'))
 def test_immutable_audit_and_insert_failure_rolls_back_create_and_extension(self):
  self.prepare_cp();id=self.cp(self.new())['snapshot']['id']
  for table in ('management_audit','destination_revisions'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','counterparties.{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
  for mutation in ('UPDATE counterparties.management_audit SET "Request"=\'{}\'','DELETE FROM counterparties.management_audit','TRUNCATE counterparties.management_audit'):
   self.assertNotEqual(self.owner_sql(mutation,ok=False).returncode,0)
  destination=dict(commandId=str(uuid.uuid4()),operation='destination-create',counterpartyId=id,expectedRevision=0,legalEntityId=self.company,destinationId=None,address='Existing private')
  destination_snapshot=self.cp(destination)['snapshot']
  self.sql("CREATE FUNCTION counterparties.fixture_fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic audit refusal'; END $$")
  import subprocess
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  payloads=[self.new(),self.new(operation='edit',counterpartyId=id,expectedRevision=1,legalName='Must rollback'),
   dict(commandId=str(uuid.uuid4()),operation='supplier-role',counterpartyId=id,expectedRevision=1,authorityVersion=1,isSupplier=True),
   dict(destination,commandId=str(uuid.uuid4())),
   dict(destination,commandId=str(uuid.uuid4()),operation='destination-edit',destinationId=destination_snapshot['id'],expectedRevision=1,address='Must rollback')]
  baseline=self.read(id,self.company)
  for timing in ('BEFORE','DEFERRED'):
   self.sql(('CREATE TRIGGER fixture_fail_audit BEFORE INSERT' if timing=='BEFORE' else 'CREATE CONSTRAINT TRIGGER fixture_fail_audit AFTER INSERT')+' ON counterparties.management_audit '+('DEFERRABLE INITIALLY DEFERRED ' if timing=='DEFERRED' else '')+'FOR EACH ROW EXECUTE FUNCTION counterparties.fixture_fail_audit()')
   for payload in payloads:
    result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.cp_statement(payload)+'COMMIT;',env=env,capture_output=True,text=True,timeout=20)
    self.assertNotEqual(result.returncode,0);self.assertIn('synthetic audit refusal',result.stderr);self.assertEqual(self.read(id,self.company),baseline)
   self.sql('DROP TRIGGER fixture_fail_audit ON counterparties.management_audit')
  self.assertEqual(self.sql('SELECT count(*) FROM counterparties.management_audit'),'2')
 def test_concurrent_create_replay_common_role_revision_and_disable_lock_order(self):
  self.prepare_cp();p=self.new()
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.cp_statement(p),'app')]*4)
  self.assertEqual(sorted(r['state'] for r in results),['applied','replayed','replayed','replayed']);id=results[0]['snapshot']['id']
  edit=self.new(operation='edit',counterpartyId=id,expectedRevision=1)
  role=dict(commandId=str(uuid.uuid4()),operation='supplier-role',counterpartyId=id,expectedRevision=1,authorityVersion=1,isSupplier=True)
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.cp_statement(edit),'app'),(self.cp_statement(role),'app')])
  self.assertEqual(sorted(r['state'] for r in results),['applied','conflict'])
  holder=f'''SELECT pg_advisory_xact_lock(777036);SELECT set_config('app.tenant_id','{self.tenant}',true);INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1);'''
  results,_=self.barrier_race(holder,[(self.cp_statement(p),'app')])
  self.assertEqual(results,[dict(state='forbidden')])
 def test_foreign_current_binding_and_raw_company_legacy_origins_are_independent(self):
  self.prepare_cp();id=self.cp(self.new())['snapshot']['id']
  self.actor=self.owner_actor;self.assertEqual(self.read(),dict(state='forbidden'),'SUPER ADMIN is not a business membership')
  self.actor=self.delegate;self.actor=dict(self.actor,subject='changed opaque subject')
  self.assertEqual(self.read(id),dict(state='forbidden'))
 def test_shared_company_concurrency_preserves_both_independent_revisions(self):
  self.prepare_cp();id=self.cp(self.new())['snapshot']['id']
  edit=self.new(operation='edit',counterpartyId=id,expectedRevision=1,legalName='Concurrent shared')
  destination=dict(commandId=str(uuid.uuid4()),operation='destination-create',counterpartyId=id,expectedRevision=0,legalEntityId=self.company,destinationId=None,address='Concurrent private')
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.cp_statement(edit),'app'),(self.cp_statement(destination),'app')])
  self.assertEqual([r['state'] for r in results],['applied','applied']);self.assertEqual(self.read(id,self.company)['detail']['revision'],2)
  self.assertEqual(self.read(id,self.company)['destinations'][0]['revision'],1)
 def test_current_role_revocation_serializes_before_pending_command_and_replay(self):
  self.prepare_cp();p=self.new();self.cp(p)
  revoke=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  results,_=self.barrier_race(self.role_statement(revoke),[(self.cp_statement(p),'app')],holder_role='app')
  self.assertEqual(results,[dict(state='forbidden')])
  self.assertEqual(self.sql('SELECT count(*) FROM counterparties.management_audit'),'1')
 def test_other_authorized_company_and_tenant_do_not_inherit_extension_or_identity_access(self):
  self.prepare_cp();first_actor=self.actor;id=self.cp(self.new())['snapshot']['id'];first_tenant=self.tenant
  self.actor=self.owner_actor;second_company=self.create_company(self.tenant)
  self.actor=first_actor
  self.assertEqual(self.read(id,second_company),dict(state='forbidden'),'company-null shared grant is never a company wildcard')
  second_identity=str(uuid.uuid4());second_member=str(uuid.uuid4());second_tenant=str(uuid.uuid4())
  self.sql(f'''INSERT INTO organization_access.tenants("Id","Name") VALUES('{second_tenant}','Synthetic other tenant');INSERT INTO organization_access.external_identity_bindings VALUES('{second_identity}','https://second.test','other-opaque');INSERT INTO organization_access.memberships VALUES('{second_member}','{second_tenant}','{second_identity}');''')
  # Same supported read action, separate configured role and exact second binding.
  permission,role,assignment=[str(uuid.uuid4()) for _ in range(3)]
  self.sql(f'''INSERT INTO organization_access.tenant_role_objects VALUES('{permission}','{second_tenant}','permission',jsonb_build_object('action','counterparties.shared.read','legalEntityId',NULL,'siteId',NULL,'warehouseId',NULL),1);INSERT INTO organization_access.tenant_role_objects VALUES('{role}','{second_tenant}','role',jsonb_build_object('permissionIds',jsonb_build_array('{permission}')),1);INSERT INTO organization_access.tenant_role_objects VALUES('{assignment}','{second_tenant}','assignment',jsonb_build_object('membershipId','{second_member}','internalIdentityId','{second_identity}','active',true,'roleId','{role}','bindingHash',encode(sha256(convert_to(jsonb_build_array('https://second.test','other-opaque')::text,'UTF8')),'hex')),1);''')
  self.actor=dict(internalIdentityId=second_identity,issuer='https://second.test',subject='other-opaque')
  self.assertEqual(self.read()['tenantId'],second_tenant);self.assertEqual(self.read()['items'],[]);self.assertEqual(self.read(id),dict(state='not_found'))
  self.actor=first_actor;self.assertEqual(self.read()['tenantId'],first_tenant);self.assertEqual(self.read(id)['detail']['id'],id)
 def test_old_repeatable_read_snapshot_cannot_resurrect_a_revoked_business_role(self):
  self.prepare_cp();p=self.new()
  import subprocess,selectors,time
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  child=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,text=True)
  try:
   child.stdin.write("BEGIN ISOLATION LEVEL REPEATABLE READ;SELECT 'SNAPSHOT_READY',count(*) FROM pg_catalog.pg_class;\n");child.stdin.flush()
   poll=selectors.DefaultSelector();poll.register(child.stdout,selectors.EVENT_READ)
   self.assertTrue(poll.select(10),'old snapshot readiness missing');line=child.stdout.readline();self.assertTrue(line.startswith('SNAPSHOT_READY|'),line);poll.close()
   revoke=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
   self.assertEqual(self.role_command(revoke)['state'],'applied')
   child.stdin.write(self.cp_statement(p)+'COMMIT;\n');child.stdin.flush();child.stdin.close();child.stdin=None
   output,error=child.communicate(timeout=20)
   self.assertNotEqual(child.returncode,0);self.assertIn('could not serialize',error)
   self.assertEqual(self.sql('SELECT count(*) FROM counterparties.management_audit'),'0')
  finally:
   if child.poll() is None:child.kill();child.communicate(timeout=5)
 def test_regression_supplier_remove_stale_authority_and_legacy_common_history(self):
  self.prepare_cp();p=self.new(fiscalIdentifier='Synthetic fiscal',registeredOffice='Synthetic office');id=self.cp(p)['snapshot']['id']
  self.assertEqual(self.cp(self.new(authorityVersion=0))['state'],'stale_authority')
  role=dict(commandId=str(uuid.uuid4()),operation='supplier-role',counterpartyId=id,expectedRevision=1,authorityVersion=1,isSupplier=True)
  self.assertTrue(self.cp(role)['snapshot']['isSupplier'])
  removed=dict(role,commandId=str(uuid.uuid4()),expectedRevision=2,isSupplier=False)
  self.assertFalse(self.cp(removed)['snapshot']['isSupplier']);self.assertEqual(self.read(id)['detail']['revision'],3)
  legacy=lambda command,revision: self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT set_config('app.legal_entity_id','{self.company}',true);SELECT counterparties.edit_common('{self.company}','{id}','{command}',1,{revision},'Legacy common edit','Synthetic fiscal','Synthetic office')")
  self.assertEqual(legacy(str(uuid.uuid4()),3),dict(state='forbidden'),'new grants never confer legacy common edit')
  self.sql(f'''INSERT INTO organization_access.company_permissions("Id","MembershipId","TenantId","LegalEntityId","Permission") VALUES(gen_random_uuid(),'{self.member}','{self.tenant}','{self.company}','counterparties.read');INSERT INTO organization_access.common_edit_permissions("MembershipId","TenantId") VALUES('{self.member}','{self.tenant}');''')
  old=str(uuid.uuid4());self.assertEqual(legacy(old,3)['state'],'applied');self.assertEqual(self.read(id)['detail']['revision'],4)
  self.assertEqual(self.read(id)['detail']['legalName'],'Legacy common edit')
  edit=self.new(operation='edit',counterpartyId=id,expectedRevision=4,legalName='New after legacy')
  self.assertEqual(self.cp(edit)['snapshot']['revision'],5)
  self.assertEqual(self.cp(dict(edit,commandId=old))['state'],'conflict')
  self.assertEqual(legacy(edit['commandId'],5)['state'],'conflict')
  self.assertEqual(self.cp(p)['snapshot']['revision'],1)
  self.assertEqual(json.loads(self.sql(f'''SELECT jsonb_agg("Revision" ORDER BY "Revision") FROM counterparties.common_edit_history WHERE "CounterpartyId"='{id}' ''')),[1,2,3,4,5])
 def test_regression_explicit_read_dependencies_and_cross_company_private_extensions(self):
  self.prepare_cp();id=self.cp(self.new())['snapshot']['id'];first=self.actor
  self.actor=self.owner_actor;second=self.create_company(self.tenant);self.actor=first
  for action in ('counterparties.extensions.read','counterparties.extensions.write'):
   p=self.role_payload('permission',label='Second '+action,action=action,legalEntityId=second,siteId=None,warehouseId=None)
   self.permissions.append((p,self.role_command(p)['snapshot']))
  role=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[s['resourceId'] for _,s in self.permissions]);self.assertEqual(self.role_command(role)['state'],'applied')
  def destination(company):return dict(commandId=str(uuid.uuid4()),operation='destination-create',counterpartyId=id,expectedRevision=0,legalEntityId=company,destinationId=None,address='Private '+company)
  a,b=destination(self.company),destination(second);self.assertEqual(self.cp(a)['state'],'applied');self.assertEqual(self.cp(b)['state'],'applied')
  for company,payload in [(self.company,a),(second,b)]:
   state=self.read(id,company);self.assertEqual(state['detail']['id'],id);self.assertEqual([d['address'] for d in state['destinations']],[payload['address']])
  for excluded in ('counterparties.shared.read','counterparties.extensions.read'):
   selected=[s['resourceId'] for p,s in self.permissions if not (p['action']==excluded and (excluded.endswith('shared.read') or p['legalEntityId']==self.company))]
   role=dict(role,commandId=str(uuid.uuid4()),expectedRevision=role['expectedRevision']+1,permissionIds=selected);self.assertEqual(self.role_command(role)['state'],'applied')
   self.assertEqual(self.cp(destination(self.company)),dict(state='forbidden'))
   self.assertEqual(self.read(id,self.company),dict(state='forbidden'))
  self.assertEqual(self.sql('SELECT count(*) FROM counterparties.management_audit'),'3')
 def test_regression_effect_before_role_revoke_serializes_and_binding_replacement_refuses(self):
  self.prepare_cp();p=self.new()
  revoke=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  results,held=self.barrier_race(self.cp_statement(p),[(self.role_statement(revoke),'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.cp(p),dict(state='forbidden'));self.assertEqual(self.sql('SELECT count(*) FROM counterparties.management_audit'),'1')
  self.role_command(dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=2,permissionIds=[s['resourceId'] for _,s in self.permissions]))
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Replaced binding' WHERE "InternalIdentityId"='{self.actor['internalIdentityId']}' ''')
  self.assertEqual(self.cp(p),dict(state='forbidden'))
  self.actor=dict(self.actor,subject='Replaced binding');self.assertEqual(self.cp(p),dict(state='forbidden'),'replacement binding does not inherit historical assignment')
if __name__=='__main__':unittest.main()
