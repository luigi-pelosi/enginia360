#!/usr/bin/env python3
"""Opt-in isolated PostgreSQL organization contract, no deployed target."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('authority',ROOT/'scripts/test-mvp02a-authority.py')
assert spec and spec.loader
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated SQL required')
class OrganizationTests(base.AuthorityTests):
 def prepare_org(self):
  self.prepare();self.actor=self.payload();self.command(self.actor)
 def actor_settings(self):
  p=self.actor
  return f"SELECT set_config('app.identity_subject','{p['internalIdentityId']}',true),set_config('app.identity_issuer','{p['issuer']}',true),set_config('app.external_subject','{p['subject']}',true);"
 def app_result(self,statement):
  output=self.sql('BEGIN;'+self.actor_settings()+statement+';COMMIT;',app=True)
  return json.loads(output.splitlines()[-1])
 def read_org(self,target=None):
  literal='NULL' if target is None else "'"+target+"'::uuid"
  return self.app_result('SELECT organization_access.read_organization('+literal+')')
 def test_directory_includes_empty_tenant_without_business_rights(self):
  self.prepare_org()
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.read_organization(uuid)') IS NOT NULL"),'t','finite organization read missing')
  self.sql('INSERT INTO organization_access.tenants VALUES(\'bbbbbbbb-0000-0000-0000-000000000001\',\'Empty\');')
  result=self.read_org()
  self.assertEqual(result,dict(state='ok',tenants=[dict(id='bbbbbbbb-0000-0000-0000-000000000001',name='Empty',revision=1)]))
  tree=self.read_org('bbbbbbbb-0000-0000-0000-000000000001')
  self.assertEqual(tree['companies'],[]);self.assertEqual(tree['sites'],[]);self.assertEqual(tree['warehouses'],[])
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'),'0')
  # Function-local verified tenant context must not leak into ordinary app queries.
  self.assertEqual(self.app_result("SELECT to_json(count(*)) FROM organization_access.tenants"),0)
 def org_payload(self, **changes):
  return dict(dict(commandId=str(uuid.uuid4()),operation='create',kind='tenant',tenantId=None,resourceId=None,parentId=None,name='  Synthetic organization  ',expectedRevision=0),**changes)
 def org_command(self,p,target=None):
  literal='NULL' if target is None else "'"+target+"'::uuid"
  return self.app_result("SELECT organization_access.command_organization("+literal+",'"+json.dumps(p).replace("'","''")+"'::jsonb)")
 def test_create_tenant_persists_server_id_and_exact_command_result(self):
  self.prepare_org()
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.command_organization(uuid,jsonb)') IS NOT NULL"),'t','finite create command missing')
  p=self.org_payload();first=self.org_command(p)
  self.assertEqual(first['state'],'applied')
  snap=first['snapshot'];self.assertNotEqual(snap['resourceId'],p['commandId'])
  self.assertEqual(snap,dict(resourceId=snap['resourceId'],tenantId=snap['resourceId'],parentId=None,kind='tenant',name='Synthetic organization',revision=1))
  self.assertEqual(self.org_command(p),dict(state='replayed',snapshot=snap))
  self.assertEqual(self.org_command(dict(p,name='Changed'))['state'],'conflict')
  self.assertEqual(self.read_org()['tenants'],[dict(id=snap['resourceId'],name=snap['name'],revision=1)])
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_commands'),'1')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'),'0')
 def create_tenant(self):
  return self.org_command(self.org_payload())['snapshot']['resourceId']
 def test_create_company_and_incomplete_hierarchy(self):
  self.prepare_org();tenant=self.create_tenant()
  p=self.org_payload(kind='company',tenantId=tenant,parentId=tenant,name='Company')
  result=self.org_command(p,tenant)
  self.assertEqual(result['state'],'applied','company create must be persisted')
  tree=self.read_org(tenant)
  self.assertEqual(tree['companies'],[dict(id=result['snapshot']['resourceId'],parentId=tenant,name='Company',revision=1)])
  self.assertEqual(tree['sites'],[]);self.assertEqual(tree['warehouses'],[])
 def create_company(self,tenant):
  return self.org_command(self.org_payload(kind='company',tenantId=tenant,parentId=tenant,name='Company'),tenant)['snapshot']['resourceId']
 def test_create_site_under_verified_company(self):
  self.prepare_org();tenant=self.create_tenant();company=self.create_company(tenant)
  p=self.org_payload(kind='site',tenantId=tenant,parentId=company,name='Site')
  result=self.org_command(p,tenant)
  self.assertEqual(result['state'],'applied','site create must persist')
  self.assertEqual(self.read_org(tenant)['sites'],[dict(id=result['snapshot']['resourceId'],parentId=company,name='Site',revision=1)])
  self.assertEqual(self.read_org(tenant)['warehouses'],[])
 def create_site(self,tenant,company):
  return self.org_command(self.org_payload(kind='site',tenantId=tenant,parentId=company,name='Site'),tenant)['snapshot']['resourceId']
 def test_create_warehouse_under_verified_site(self):
  self.prepare_org();tenant=self.create_tenant();company=self.create_company(tenant);site=self.create_site(tenant,company)
  result=self.org_command(self.org_payload(kind='warehouse',tenantId=tenant,parentId=site,name='Warehouse'),tenant)
  self.assertEqual(result['state'],'applied','warehouse create must persist')
  self.assertEqual(self.read_org(tenant)['warehouses'],[dict(id=result['snapshot']['resourceId'],parentId=site,name='Warehouse',revision=1)])
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'),'0')
 def test_rename_optimistic_revision_immutable_parent_and_historical_replay(self):
  self.prepare_org();tenant=self.create_tenant();company=self.create_company(tenant);site=self.create_site(tenant,company)
  create=self.org_payload(kind='warehouse',tenantId=tenant,parentId=site,name='Warehouse')
  first=self.org_command(create,tenant)['snapshot'];warehouse=first['resourceId']
  for kind,id,parent in [('tenant',tenant,None),('company',company,tenant),('site',site,company),('warehouse',warehouse,site)]:
   with self.subTest(kind=kind):
    p=self.org_payload(operation='rename',kind=kind,tenantId=tenant,resourceId=id,parentId=parent,name='Renamed '+kind,expectedRevision=1)
    result=self.org_command(p,tenant)
    self.assertEqual(result['state'],'applied','optimistic rename missing for '+kind)
    self.assertEqual(result['snapshot'],dict(resourceId=id,tenantId=tenant,parentId=parent,kind=kind,name='Renamed '+kind,revision=2))
    self.assertEqual(self.org_command(p,tenant),dict(state='replayed',snapshot=result['snapshot']))
    self.assertEqual(self.org_command(dict(p,commandId=str(uuid.uuid4())),tenant)['state'],'conflict')
    self.assertEqual(self.org_command(dict(p,commandId=str(uuid.uuid4()),expectedRevision=2,parentId=str(uuid.uuid4())),tenant)['state'],'not_found')
  self.assertEqual(self.org_command(create,tenant),dict(state='replayed',snapshot=first))
  self.assertEqual(self.read_org(tenant)['warehouses'][0]['name'],'Renamed warehouse')
 def test_name_boundaries_preserve_literal_v_and_unicode(self):
  self.prepare_org()
  for name in ['v','av','é'*100,'x'*100,'\t Synthetic \r\n']:
   with self.subTest(name=name):
    result=self.org_command(self.org_payload(name=name))
    self.assertEqual(result['state'],'applied','valid boundary name must not be altered/refused')
    self.assertEqual(result['snapshot']['name'],name.strip(' \t\r\n\f\v'))
  for name in ['', ' \t\r\n', 'x'*101, 'é'*101, 'a\tb', 'x\x01y']:
   self.assertEqual(self.org_command(self.org_payload(name=name))['state'],'invalid')
 def test_invalid_command_closed_inputs_and_wrong_target_parent_write_nothing(self):
  self.prepare_org();tenant=self.create_tenant();foreign=self.create_tenant();company=self.create_company(tenant);foreign_company=self.create_company(foreign)
  count=self.sql('SELECT count(*) FROM organization_access.organization_commands')
  p=self.org_payload()
  bad=[None,[],dict(p,extra=True),dict(p,operation=None),dict(p,kind=None),dict(p,kind='Tenant'),dict(p,operation='delete'),dict(p,name=None),dict(p,name=3),dict(p,expectedRevision=True),dict(p,expectedRevision=-1),dict(p,expectedRevision=2147483647),dict(p,commandId=''),dict(p,commandId='00000000-0000-0000-0000-000000000000'),dict(p,commandId=p['commandId'].upper()),dict(p,resourceId=str(uuid.uuid4())),dict(p,parentId=str(uuid.uuid4()))]
  for value in bad:
   with self.subTest(value=value):self.assertEqual(self.org_command(value)['state'],'invalid')
  wrong=[(self.org_payload(kind='company',tenantId=foreign,parentId=foreign),tenant),
    (self.org_payload(kind='company',tenantId=tenant,parentId=foreign),tenant),
    (self.org_payload(kind='site',tenantId=tenant,parentId=foreign_company),tenant),
    (self.org_payload(kind='warehouse',tenantId=tenant,parentId=company),tenant),
    (self.org_payload(kind='site',tenantId=tenant,parentId=str(uuid.uuid4())),tenant)]
  for value,target in wrong:
   self.assertEqual(self.org_command(value,target),dict(state='not_found'))
  self.assertEqual(self.read_org(str(uuid.uuid4())),dict(state='not_found'))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_commands'),count)
 def test_current_binding_revoke_and_exact_actor_tuple_deny_even_replay(self):
  self.prepare_org();p=self.org_payload();first=self.org_command(p)
  saved=self.actor
  for key,value in [('internalIdentityId',str(uuid.uuid4())),('issuer','https://foreign.test'),('subject','opaque-subject')]:
   self.actor=dict(saved,**{key:value})
   self.assertEqual(self.read_org(),dict(state='forbidden'))
   self.assertEqual(self.org_command(p),dict(state='forbidden'))
  self.actor=saved
  self.command(dict(saved,operation='revoke',expectedRevision=1,commandId=str(uuid.uuid4())))
  self.assertEqual(self.org_command(p),dict(state='forbidden'))
  self.command(dict(saved,expectedRevision=2,commandId=str(uuid.uuid4())))
  self.assertEqual(self.org_command(p),dict(state='replayed',snapshot=first['snapshot']))
  self.sql('DELETE FROM organization_access.external_identity_bindings')
  self.assertEqual(self.read_org(),dict(state='forbidden'))
  self.assertEqual(self.org_command(p),dict(state='forbidden'))
 def test_app_dml_audit_immutable_forced_rls_and_no_privileged_role(self):
  self.prepare_org();self.create_tenant();app=os.environ['R00_APP_USER']
  for relation in ('tenants','legal_entities','sites','warehouses','organization_commands'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','organization_access.{relation}','INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
   self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='organization_access.{relation}'::regclass"),'t')
  for role in [app,self.owner]:
   self.assertEqual(self.sql(f"SELECT rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb FROM pg_roles WHERE rolname='{role}'"),'f')
  self.assertEqual(self.sql(f"SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='{app}')"),'0')
  self.assertEqual(self.sql(f"SELECT has_function_privilege('{app}','organization_access.apply_organization_command(uuid,jsonb)','EXECUTE')"),'f')
  self.assertEqual(self.sql(f"SELECT has_function_privilege('{app}','organization_access.lock_organization_actor()','EXECUTE')"),'f')
  for statement in ('UPDATE organization_access.organization_commands SET "Request"=\'{}\'','DELETE FROM organization_access.organization_commands','TRUNCATE organization_access.organization_commands'):
   self.assertNotEqual(self.owner_sql(statement,ok=False).returncode,0)
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'),'0')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.membership_scopes'),'0')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.capability_activations'),'0')
  self.assertEqual(self.sql("SELECT count(*) FROM pg_policies WHERE schemaname<>'organization_access' AND policyname LIKE 'platform%'") ,'0')
 def test_audit_insert_and_deferred_commit_failure_roll_back_mutation(self):
  self.prepare_org()
  self.sql("CREATE FUNCTION organization_access.fixture_org_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic audit refusal'; END $$;")
  for timing in ['BEFORE','DEFERRED']:
   if timing=='BEFORE':
    self.sql('CREATE TRIGGER fixture_org_fail BEFORE INSERT ON organization_access.organization_commands FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_org_fail()')
   else:
    self.sql('CREATE CONSTRAINT TRIGGER fixture_org_fail AFTER INSERT ON organization_access.organization_commands DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_org_fail()')
   p=self.org_payload();statement="BEGIN;"+self.actor_settings()+"SELECT organization_access.command_organization(NULL,'"+json.dumps(p)+"');COMMIT;"
   env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
   result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input=statement,text=True,env=env,capture_output=True,timeout=20)
   self.assertNotEqual(result.returncode,0);self.assertIn('synthetic audit refusal',result.stderr)
   self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenants'),'0')
   self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_commands'),'0')
   self.sql('DROP TRIGGER fixture_org_fail ON organization_access.organization_commands')
 def test_function_restores_prior_target_in_same_transaction_and_max_revision_conflicts(self):
  self.prepare_org();tenant=self.create_tenant();prior=str(uuid.uuid4())
  result=self.sql('BEGIN;'+self.actor_settings()+f"SELECT set_config('app.tenant_id','{prior}',true);SELECT organization_access.read_organization('{tenant}');SELECT current_setting('app.tenant_id');SELECT count(*) FROM organization_access.tenants;COMMIT;",app=True)
  self.assertEqual(result.splitlines()[-2:],[prior,'0'])
  self.sql(f'UPDATE organization_access.tenants SET "Revision"=2147483647 WHERE "Id"=\'{tenant}\'')
  p=self.org_payload(operation='rename',kind='tenant',tenantId=tenant,resourceId=tenant,expectedRevision=2147483646)
  self.assertEqual(self.org_command(p,tenant),dict(state='conflict'))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_commands'),'1')
 def org_statement(self,p,target=None):
  literal='NULL' if target is None else "'"+target+"'::uuid"
  return self.actor_settings()+"SELECT organization_access.command_organization("+literal+",'"+json.dumps(p).replace("'","''")+"');"
 def barrier_race(self,holder_statement,workers,holder_role='owner'):
  import selectors,time
  def environment(role):
   env=dict(os.environ,PGDATABASE=self.database)
   if role=='owner':env.update(PGUSER=self.owner,PGPASSWORD=os.environ['R00_OWNER_PASSWORD'])
   if role=='app':env.update(PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
   return env
  holder=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment(holder_role))
  children=[]
  try:
   holder.stdin.write('BEGIN;'+holder_statement+'SELECT pg_backend_pid();\\echo LOCKED\n');holder.stdin.flush()
   lines=[]
   while True:
    # psql flushes each result; marker proves the real SQL lock is already held.
    line=holder.stdout.readline().strip()
    if line=='LOCKED':break
    self.assertIsNone(holder.poll(),'barrier holder failed before marker')
    if line:lines.append(line)
   pid=int(lines[-1])
   for statement,role in workers:
    children.append(subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1','-c','BEGIN;'+statement+'COMMIT;'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment(role)))
   deadline=time.monotonic()+10
   while int(self.sql(f'SELECT count(*) FROM pg_stat_activity WHERE {pid}=ANY(pg_blocking_pids(pid))'))<len(workers):
    self.assertLess(time.monotonic(),deadline,'all physical waiters must block on the held real lock');time.sleep(.05)
   holder.stdin.write('COMMIT;\\q\n');holder.stdin.flush();_,error=holder.communicate(timeout=10);self.assertEqual(holder.returncode,0,error)
   results=[]
   for process in children:
    output,error=process.communicate(timeout=10);self.assertEqual(process.returncode,0,error)
    results.append(json.loads(output.strip().splitlines()[-1]))
   return results,[json.loads(line) for line in lines if line.startswith('{')]
  finally:
   for process in [holder,*children]:
    if process.poll() is None:process.kill();process.communicate(timeout=5)
 def test_physical_barriers_concurrent_create_exact_replay_and_optimistic_updates(self):
  self.prepare_org();p=self.org_payload()
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.org_statement(p),'app')]*2)
  self.assertEqual(sorted(r['state'] for r in results),['applied','replayed'])
  self.assertEqual(results[0]['snapshot'],results[1]['snapshot']);tenant=results[0]['snapshot']['resourceId']
  p=self.org_payload(operation='rename',tenantId=tenant,resourceId=tenant,expectedRevision=1,name='First')
  other=dict(p,commandId=str(uuid.uuid4()),name='Second')
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.org_statement(p,tenant),'app'),(self.org_statement(other,tenant),'app')])
  self.assertEqual(sorted(r['state'] for r in results),['applied','conflict'])
  self.assertEqual(self.read_org(tenant)['tenant']['revision'],2)
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_commands'),'2')
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.org_statement(self.org_payload()),'app'),(self.org_statement(self.org_payload()),'app')])
  self.assertEqual([r['state'] for r in results],['applied','applied']);self.assertNotEqual(results[0]['snapshot']['resourceId'],results[1]['snapshot']['resourceId'])
 def test_physical_revoke_before_mutation_and_mutation_before_revoke(self):
  self.prepare_org();p=self.org_payload()
  revoke=dict(self.actor,operation='revoke',commandId=str(uuid.uuid4()),expectedRevision=1)
  statement="SELECT organization_access.command_platform_authority('"+json.dumps(revoke)+"');"
  results,_=self.barrier_race(statement,[(self.org_statement(p),'app')])
  self.assertEqual(results,[dict(state='forbidden')]);self.assertEqual(self.sql('SELECT count(*) FROM organization_access.tenants'),'0')
  self.command(dict(self.actor,commandId=str(uuid.uuid4()),expectedRevision=2))
  revoke=dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=3)
  statement="SELECT organization_access.command_platform_authority('"+json.dumps(revoke)+"');"
  results,holder=self.barrier_race(self.org_statement(p),[(statement,'owner')],holder_role='app')
  self.assertEqual(holder[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.org_command(p),dict(state='forbidden'))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_commands'),'1')
 def test_physical_binding_deletion_before_mutation_denies_without_write(self):
  self.prepare_org();p=self.org_payload()
  results,_=self.barrier_race('DELETE FROM organization_access.external_identity_bindings;',[(self.org_statement(p),'app')],holder_role='infra')
  self.assertEqual(results,[dict(state='forbidden')])
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_commands'),'0')
 def test_rename_audit_failure_rolls_back_name_and_revision(self):
  self.prepare_org();tenant=self.create_tenant()
  self.sql("CREATE FUNCTION organization_access.fixture_org_rename_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic rename audit refusal'; END $$; CREATE CONSTRAINT TRIGGER fixture_org_rename_fail AFTER INSERT ON organization_access.organization_commands DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_org_rename_fail();")
  p=self.org_payload(operation='rename',tenantId=tenant,resourceId=tenant,expectedRevision=1,name='Must roll back')
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.org_statement(p,tenant)+'COMMIT;',text=True,env=env,capture_output=True,timeout=20)
  self.assertNotEqual(result.returncode,0);self.assertIn('synthetic rename audit refusal',result.stderr)
  self.assertEqual(self.read_org(tenant)['tenant'],dict(id=tenant,name='Synthetic organization',revision=1))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_commands'),'1')
 def test_app_actual_dml_is_denied_even_with_forged_target(self):
  self.prepare_org();tenant=self.create_tenant()
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  for table in ('tenants','legal_entities','sites','warehouses'):
   for operation in ('UPDATE organization_access.'+table+' SET "Name"=\'Attack\'', 'DELETE FROM organization_access.'+table):
    result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.actor_settings()+f"SELECT set_config('app.tenant_id','{tenant}',true);"+operation+';COMMIT;',text=True,env=env,capture_output=True,timeout=20)
    self.assertNotEqual(result.returncode,0);self.assertIn('permission denied',result.stderr)
  self.assertEqual(self.read_org(tenant)['tenant']['name'],'Synthetic organization')
 def prepare_delegate(self):
  self.prepare_org();self.owner_actor=self.actor;self.tenant=self.create_tenant()
  self.delegate=dict(internalIdentityId='dddddddd-0000-0000-0000-000000000001',issuer='https://delegate.test',subject='Delegate')
  self.member='dddddddd-0000-0000-0000-000000000002'
  self.sql(f'''INSERT INTO organization_access.external_identity_bindings VALUES('{self.delegate['internalIdentityId']}','{self.delegate['issuer']}','{self.delegate['subject']}'); INSERT INTO organization_access.memberships VALUES('{self.member}','{self.tenant}','{self.delegate['internalIdentityId']}');''')
 def delegation_read(self,target):
  return self.app_result(f"SELECT organization_access.read_organization_delegations('{target}')")
 def test_owner_minimal_existing_trusted_membership_selector(self):
  self.prepare_delegate()
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.read_organization_delegations(uuid)') IS NOT NULL"),'t','minimal owner-authorized membership selector missing')
  self.assertEqual(self.delegation_read(self.tenant),dict(state='ok',memberships=[dict(membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=self.sql(f'''SELECT encode(sha256(convert_to(jsonb_build_array("Issuer","Subject")::text,'UTF8')),'hex') FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{self.delegate['internalIdentityId']}' '''),active=False,revision=0)]))
  self.actor=self.delegate
  self.assertEqual(self.delegation_read(self.tenant),dict(state='forbidden'))
  self.actor=self.owner_actor
  self.assertEqual(self.delegation_read(str(uuid.uuid4())),dict(state='not_found'))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'),'1')
 def delegation_payload(self,**changes):
  row=self.delegation_read(self.tenant)['memberships'][0]
  return dict(dict(commandId=str(uuid.uuid4()),operation='grant',membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=row['bindingHash'],expectedRevision=row['revision']),**changes)
 def delegation_command(self,p,target=None):
  return self.app_result("SELECT organization_access.command_organization_delegation('"+(target or self.tenant)+"','"+json.dumps(p).replace("'","''")+"')")
 def test_owner_grant_revoke_exact_replay_revision_and_minimized_atomic_audit(self):
  self.prepare_delegate()
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.command_organization_delegation(uuid,jsonb)') IS NOT NULL"),'t','finite delegation command missing')
  p=self.delegation_payload();result=self.delegation_command(p)
  self.assertEqual(result['state'],'applied')
  expected=dict(tenantId=self.tenant,membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=p['bindingHash'],active=True,revision=1)
  self.assertEqual(result['snapshot'],expected)
  self.assertEqual(self.delegation_command(p),dict(state='replayed',snapshot=expected))
  self.assertEqual(self.delegation_command(dict(p,operation='revoke'))['state'],'conflict')
  self.assertEqual(self.delegation_command(dict(p,commandId=str(uuid.uuid4())))['state'],'conflict')
  self.assertEqual(self.delegation_read(self.tenant)['memberships'][0]['active'],True)
  revoke=dict(p,commandId=str(uuid.uuid4()),operation='revoke',expectedRevision=1)
  self.assertEqual(self.delegation_command(revoke)['snapshot'],dict(expected,active=False,revision=2))
  self.assertEqual(self.delegation_command(p),dict(state='replayed',snapshot=expected))
  self.assertFalse(self.delegation_read(self.tenant)['memberships'][0]['active'])
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_delegation_commands'),'2')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.memberships'),'1')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.membership_scopes'),'0')
  self.assertEqual(self.sql('''SELECT count(*) FROM organization_access.organization_delegation_commands WHERE "Request" ?| ARRAY['issuer','subject','email','token','name']'''),'0')
 def test_delegate_structure_only_own_tenant_and_current_grant_every_replay(self):
  self.prepare_delegate();grant=self.delegation_payload();self.delegation_command(grant)
  foreign=self.create_tenant();self.actor=self.delegate
  self.assertEqual(self.read_org(self.tenant)['state'],'ok','active delegate cannot read own structure')
  self.assertEqual(self.read_org(),dict(state='forbidden'))
  self.assertEqual(self.read_org(foreign),dict(state='forbidden'))
  self.assertEqual(self.org_command(self.org_payload()),dict(state='forbidden'))
  rename=self.org_payload(operation='rename',kind='tenant',tenantId=self.tenant,resourceId=self.tenant,expectedRevision=1)
  self.assertEqual(self.org_command(rename,self.tenant),dict(state='forbidden'))
  p=self.org_payload(kind='company',tenantId=self.tenant,parentId=self.tenant,name='Delegated company')
  created=self.org_command(p,self.tenant);self.assertEqual(created['state'],'applied')
  self.assertEqual(self.org_command(p,self.tenant),dict(state='replayed',snapshot=created['snapshot']))
  company=created['snapshot']['resourceId'];site=self.create_site(self.tenant,company)
  warehouse=self.org_command(self.org_payload(kind='warehouse',tenantId=self.tenant,parentId=site),self.tenant)
  self.assertEqual(warehouse['state'],'applied')
  self.assertEqual(self.org_command(dict(p,commandId=str(uuid.uuid4()),tenantId=foreign,parentId=foreign),foreign),dict(state='forbidden'))
  self.assertEqual(self.delegation_command(grant),dict(state='forbidden'))
  self.actor=self.owner_actor
  self.delegation_command(dict(grant,commandId=str(uuid.uuid4()),operation='revoke',expectedRevision=1))
  self.actor=self.delegate
  self.assertEqual(self.read_org(self.tenant),dict(state='forbidden'))
  self.assertEqual(self.org_command(p,self.tenant),dict(state='forbidden'))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.membership_scopes'),'0')
 def test_delegation_uuid_cannot_be_reused_for_structure_command(self):
  self.prepare_delegate();p=self.delegation_payload();self.delegation_command(p)
  structure=self.org_payload(commandId=p['commandId'],kind='company',tenantId=self.tenant,parentId=self.tenant)
  self.assertEqual(self.org_command(structure,self.tenant),dict(state='conflict'),'delegation UUID collision must refuse structure mutation')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.legal_entities'),'0')
 def delegation_statement(self,p):
  return self.actor_settings()+"SELECT organization_access.command_organization_delegation('"+self.tenant+"','"+json.dumps(p)+"');"
 def test_delegation_physical_concurrent_replay_conflict_and_both_revoke_orderings(self):
  self.prepare_delegate();p=self.delegation_payload()
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.delegation_statement(p),'app')]*2)
  self.assertEqual(sorted(r['state'] for r in results),['applied','replayed'])
  self.assertEqual(results[0]['snapshot'],results[1]['snapshot'])
  revoke=dict(p,commandId=str(uuid.uuid4()),operation='revoke',expectedRevision=1)
  other=dict(revoke,commandId=str(uuid.uuid4()),operation='grant')
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.delegation_statement(revoke),'app'),(self.delegation_statement(other),'app')])
  self.assertEqual(sorted(r['state'] for r in results),['applied','conflict'])
  self.delegation_command(dict(p,commandId=str(uuid.uuid4()),expectedRevision=2))
  revoke=dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=3)
  holder=self.delegation_statement(revoke)
  command=self.org_payload(kind='company',tenantId=self.tenant,parentId=self.tenant)
  self.actor=self.delegate;worker=self.org_statement(command,self.tenant)
  results,_=self.barrier_race(holder,[(worker,'app')],holder_role='app')
  self.assertEqual(results,[dict(state='forbidden')])
  self.actor=self.owner_actor
  self.delegation_command(dict(p,commandId=str(uuid.uuid4()),expectedRevision=4))
  revoke=dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=5);worker=self.delegation_statement(revoke)
  self.actor=self.delegate
  results,held=self.barrier_race(self.org_statement(command,self.tenant),[(worker,'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.org_command(command,self.tenant),dict(state='forbidden'))
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_delegation_commands'),'6')
 def test_delegation_current_target_binding_membership_owner_and_actor_loss(self):
  self.prepare_delegate();p=self.delegation_payload();self.delegation_command(p)
  self.actor=self.delegate;command=self.org_payload(kind='company',tenantId=self.tenant,parentId=self.tenant)
  snapshot=self.org_command(command,self.tenant)['snapshot']
  saved=self.actor
  for key,value in [('issuer','https://other.test'),('subject','other'),('internalIdentityId',str(uuid.uuid4()))]:
   self.actor=dict(saved,**{key:value});self.assertEqual(self.read_org(self.tenant),dict(state='forbidden'));self.assertEqual(self.org_command(command,self.tenant),dict(state='forbidden'))
  self.actor=self.owner_actor
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Rebound' WHERE "InternalIdentityId"='{self.delegate['internalIdentityId']}';''')
  self.assertEqual(self.delegation_command(p),dict(state='forbidden'),'historical target binding cannot replay')
  self.actor=dict(saved,subject='Rebound');self.assertEqual(self.read_org(self.tenant),dict(state='forbidden'),'old grant does not survive rebinding')
  self.actor=self.owner_actor
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Delegate' WHERE "InternalIdentityId"='{self.delegate['internalIdentityId']}';''')
  self.sql(f'''DELETE FROM organization_access.memberships WHERE "Id"='{self.member}';''')
  self.assertEqual(self.delegation_command(p),dict(state='forbidden'))
  self.actor=self.delegate;self.assertEqual(self.org_command(command,self.tenant),dict(state='forbidden'))
  self.actor=self.owner_actor;self.sql(f'''DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{self.actor['internalIdentityId']}';''')
  self.assertEqual(self.delegation_read(self.tenant),dict(state='forbidden'))
 def test_delegation_closed_input_boundaries_privileges_immutable_and_rollback(self):
  self.prepare_delegate();p=self.delegation_payload()
  for bad in [None,[],dict(p,extra=True),dict(p,expectedRevision=True),dict(p,expectedRevision=-1),dict(p,expectedRevision=2147483647),dict(p,bindingHash='bad'),dict(p,operation='invite'),dict(p,membershipId=str(uuid.uuid4())),dict(p,internalIdentityId=self.owner_actor['internalIdentityId'])]:
   self.assertIn(self.delegation_command(bad)['state'],['invalid','forbidden'])
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_delegation_commands'),'0')
  app=os.environ['R00_APP_USER']
  for table in ('organization_delegations','organization_delegation_commands'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','organization_access.{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
   self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='organization_access.{table}'::regclass"),'t')
  self.sql("CREATE FUNCTION organization_access.fixture_delegation_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic delegation audit refusal'; END $$;")
  for timing in ('BEFORE','DEFERRED'):
   sql='CREATE TRIGGER fixture_delegation_fail BEFORE INSERT' if timing=='BEFORE' else 'CREATE CONSTRAINT TRIGGER fixture_delegation_fail AFTER INSERT'
   sql+=' ON organization_access.organization_delegation_commands '+('DEFERRABLE INITIALLY DEFERRED ' if timing=='DEFERRED' else '')+'FOR EACH ROW EXECUTE FUNCTION organization_access.fixture_delegation_fail();'
   self.sql(sql)
   env=dict(os.environ,PGDATABASE=self.database,PGUSER=app,PGPASSWORD=os.environ['R00_APP_PASSWORD'])
   result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.delegation_statement(p)+'COMMIT;',text=True,capture_output=True,env=env,timeout=20)
   self.assertNotEqual(result.returncode,0);self.assertIn('synthetic delegation audit refusal',result.stderr)
   self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_delegations'),'0');self.assertEqual(self.sql('SELECT count(*) FROM organization_access.organization_delegation_commands'),'0')
   self.sql('DROP TRIGGER fixture_delegation_fail ON organization_access.organization_delegation_commands;')
  self.delegation_command(p)
  for mutation in ('UPDATE organization_access.organization_delegation_commands SET "Request"=\'{}\'','DELETE FROM organization_access.organization_delegation_commands','TRUNCATE organization_access.organization_delegation_commands'):
   self.assertNotEqual(self.owner_sql(mutation,ok=False).returncode,0)
  self.sql('UPDATE organization_access.organization_delegations SET "Revision"=2147483647')
  self.assertEqual(self.delegation_command(dict(p,commandId=str(uuid.uuid4()),expectedRevision=2147483646))['state'],'conflict')
 def test_delegated_workspace_discovers_only_current_granted_tenant(self):
  self.prepare_delegate();p=self.delegation_payload();self.delegation_command(p)
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.read_organization_workspace()') IS NOT NULL"),'t','scoped administrative workspace discovery missing')
  self.actor=self.delegate
  self.assertEqual(self.app_result('SELECT organization_access.read_organization_workspace()'),dict(state='ok',mode='delegate',tenants=[self.read_org(self.tenant)['tenant']]))
  self.actor=self.owner_actor
  self.delegation_command(dict(p,commandId=str(uuid.uuid4()),operation='revoke',expectedRevision=1))
  self.actor=self.delegate
  self.assertEqual(self.app_result('SELECT organization_access.read_organization_workspace()'),dict(state='forbidden'))
class FixtureTests(unittest.TestCase):
 def test_nonroot_fixture_extension_and_repeated_owner_input_remain_readonly(self):
  import tempfile
  spec=importlib.util.spec_from_file_location('runner',ROOT/'scripts/run-mvp02b-tests.py')
  assert spec and spec.loader
  runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as directory:
   state=Path(directory);sql,identities=runner.fixtures(state,'synthetic-only')
   self.assertTrue(sql);self.assertEqual(json.loads((state/'browser.json').read_text())['authorityIdentity'],identities[4])
   for name in ('realm.json','browser.json'):
    self.assertEqual((state/name).stat().st_mode&0o777,0o444)
   for operation in ('grant','revoke','grant'):
    runner.write_readonly_json(state/'authority.json',dict(operation=operation))
    self.assertEqual((state/'authority.json').stat().st_mode&0o777,0o444)
    self.assertEqual(json.loads((state/'authority.json').read_text()),dict(operation=operation))
if __name__=='__main__':unittest.main()
