#!/usr/bin/env python3
"""MVP06 final-phase real isolated PostgreSQL acceptance; UNEXECUTED sources."""
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
class DocumentTypeTests(unittest.TestCase):
 locals().update({k:v for k,v in vars(base.RoleTests).items() if callable(v) and not k.startswith('test')})
 def read(self,record=None,company=None,revision=None,search=None,after=None,before=None,chooser=False):
  lit=lambda v:"'"+str(v).replace("'","''")+"'" if v is not None else 'NULL'
  return self.app_result('SELECT document_types.read('+','.join([lit(None if chooser else company or self.company)+'::uuid',lit(search)+'::text',lit(after)+'::uuid',lit(record)+'::uuid',lit(revision)+'::integer',lit(before)+'::integer'])+')')
 def cp(self,p):
  return self.app_result("SELECT document_types.command('"+json.dumps(p).replace("'","''")+"')")
 def cp_statement(self,p):
  return self.actor_settings()+"SELECT document_types.command('"+json.dumps(p).replace("'","''")+"');"
 def new(self,**changes):
  return dict(dict(commandId=str(uuid.uuid4()),operation='create',legalEntityId=self.company,documentTypeId=None,expectedRevision=0,label='Synthetic type',effect='None'),**changes)
 def prepare_types(self):
  self.prepare_user_admin()
  self.assertEqual(self.read(chooser=True),dict(state='forbidden'),'admin is not a business grant')
  self.permissions=[]
  for action in ('document-types.read','document-types.create','document-types.edit'):
   p=self.role_payload('permission',label=action,action=action,legalEntityId=self.company,siteId=None,warehouseId=None)
   result=self.role_command(p);self.assertEqual(result['state'],'applied');self.permissions.append((p,result['snapshot']))
  role=self.role_payload('role',label='Company type operator',permissionIds=[s['resourceId'] for _,s in self.permissions]);self.cp_role_request=role;self.cp_role=self.role_command(role)['snapshot']
  member=next(m for m in self.role_read()['memberships'] if m['membershipId']==self.member)
  assignment=self.role_payload('assignment',roleId=self.cp_role['resourceId'],membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=member['bindingHash'],active=True)
  self.cp_assignment_request=assignment;self.cp_assignment=self.role_command(assignment)['snapshot']
 def grant_company(self,company):
  ids=[s['resourceId'] for _,s in self.permissions]
  for action in ('document-types.read','document-types.create','document-types.edit'):
   result=self.role_command(self.role_payload('permission',label=action,action=action,legalEntityId=company,siteId=None,warehouseId=None));self.assertEqual(result['state'],'applied');ids.append(result['snapshot']['resourceId'])
  return self.role_command(dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=ids))
 def test_four_closed_effects_new_immutable_versions_and_historical_exact_replay(self):
  self.prepare_types();self.assertEqual(self.read()['items'],[])
  for effect in ('Load','Unload','Transfer','None'):
   request=self.new(effect=effect,label='Synthetic '+effect);result=self.cp(request);self.assertEqual(result['state'],'applied');snap=result['snapshot'];id=snap['id']
   self.assertEqual(snap['legalEntityId'],self.company);self.assertEqual(snap['effect'],effect);self.assertEqual(snap['revision'],1)
   edit=self.new(operation='edit',documentTypeId=id,expectedRevision=1,label='Changed '+effect,effect='None' if effect!='None' else 'Transfer')
   self.assertEqual(self.cp(edit)['snapshot']['revision'],2)
   read=self.read(id,revision=1);self.assertEqual(read['detail']['revision'],2);self.assertEqual(read['selectedVersion'],snap);self.assertEqual(len(read['history']),2)
   self.assertEqual(self.cp(request),dict(state='replayed',snapshot=snap))
   self.assertEqual(self.cp(dict(request,label='Other')),dict(state='conflict'))
   self.assertEqual(self.cp(dict(edit,commandId=str(uuid.uuid4()))),dict(state='conflict'))
   self.assertEqual(self.cp(self.new(label=edit['label']))['state'],'applied','duplicate labels are not merge instructions')
  for table in ('inventory.stock','catalog.supplier_purchase_price_history','workshop.orders','billing.invoices'):
   self.assertEqual(self.sql('SELECT count(*) FROM '+table),'0','configuration produces no document/stock/fiscal fact')
 def test_company_chooser_exact_rights_same_tenant_isolation_and_command_collision(self):
  self.prepare_types();actor=self.actor;self.actor=self.owner_actor;other=self.create_company(self.tenant);self.actor=actor
  original=self.new();snap=self.cp(original)['snapshot']
  self.assertEqual([c['id'] for c in self.read(chooser=True)['companies']],[self.company])
  self.assertEqual(self.read(company=other),dict(state='forbidden'))
  self.assertEqual(self.cp(self.new(legalEntityId=other)),dict(state='forbidden'))
  self.assertEqual(self.grant_company(other)['state'],'applied')
  self.assertEqual({c['id'] for c in self.read(chooser=True)['companies']},{self.company,other})
  self.assertEqual(self.read(company=other)['items'],[])
  self.assertEqual(self.read(snap['id'],company=other,revision=1),dict(state='not_found'))
  self.assertEqual(self.cp(dict(original,legalEntityId=other)),dict(state='conflict'))
  self.assertEqual(self.cp(self.new(operation='edit',legalEntityId=other,documentTypeId=snap['id'],expectedRevision=1)),dict(state='not_found'))
  other_snap=self.cp(self.new(legalEntityId=other,label='Independent company',effect='Load'))['snapshot']
  self.assertNotEqual(other_snap['id'],snap['id']);self.assertEqual(self.read(snap['id'])['detail'],snap)
 def test_exact_company_nulls_no_global_or_warehouse_fallback(self):
  self.prepare_types()
  for action,company,site,warehouse in [('document-types.read',None,None,None),('document-types.create',self.company,self.site,None),('document-types.edit',self.company,None,self.warehouse),('document-types.*',self.company,None,None),('organization-context.read',self.company,None,None),('catalog.shared.read',self.company,None,None)]:
   result=self.role_command(self.role_payload('permission',label='Invalid scope',action=action,legalEntityId=company,siteId=site,warehouseId=warehouse));self.assertIn(result['state'],('invalid','forbidden'))
  self.assertEqual(self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT coalesce(jsonb_agg(\"Permission\"),'[]') FROM organization_access.effective_membership_scopes WHERE \"MembershipId\"='{self.member}'"),[])
  self.sql(f'''UPDATE organization_access.tenant_role_objects SET "Data"="Data"-'siteId' WHERE "TenantId"='{self.tenant}' AND "Kind"='permission' AND "Data"->>'action'='document-types.read' ''')
  self.assertEqual(self.read(),dict(state='forbidden'))
 def test_bounded_exact_input_and_no_freeform_engine(self):
  self.prepare_types();p=self.new()
  for invalid in (None,[],{},True,'create'):self.assertEqual(self.cp(invalid),dict(state='invalid'))
  for change in [dict(commandId=''),dict(commandId='AAAAAAAA-0000-0000-0000-000000000001'),dict(commandId='00000000-0000-0000-0000-000000000000'),dict(legalEntityId=None),dict(legalEntityId=self.tenant),dict(extra=True),dict(tenantId=self.tenant),dict(expectedRevision=True),dict(expectedRevision='0'),dict(expectedRevision=2147483648),dict(label=' '),dict(label='x'*101),dict(label='bad\nlabel'),dict(effect='StockLoad'),dict(effect='load'),dict(effect=0),dict(effect=None),dict(formula='quantity*2'),dict(operation='delete'),dict(documentTypeId=str(uuid.uuid4()))]:
   self.assertIn(self.cp(dict(p,**change))['state'],('invalid','forbidden'),change)
  for key in p:
   reduced=dict(p);del reduced[key];self.assertEqual(self.cp(reduced),dict(state='invalid'),key)
  self.assertEqual(self.cp(self.new(label='😀'*100))['state'],'applied')
  self.assertEqual(self.read(revision=1),dict(state='invalid'));self.assertEqual(self.read(chooser=True,search='x'),dict(state='invalid'))
 def test_atomic_audit_insert_and_deferred_commit_rollback_create_edit_all_effects(self):
  self.prepare_types();items=[self.cp(self.new(effect=e))['snapshot'] for e in ('Load','Unload','Transfer','None')]
  for table in ('definitions','versions','command_audit'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','document_types.{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
   self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='document_types.{table}'::regclass"),'t')
  for table in ('versions','command_audit'):
   for statement in (f'UPDATE document_types.{table} SET "TenantId"="TenantId"',f'DELETE FROM document_types.{table}',f'TRUNCATE document_types.{table}'):
    self.assertNotEqual(self.owner_sql(statement,ok=False).returncode,0)
  self.sql("CREATE FUNCTION document_types.fixture_fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic audit refusal'; END $$")
  import subprocess
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  payloads=[self.new(effect=i['effect']) for i in items]+[self.new(operation='edit',documentTypeId=i['id'],expectedRevision=1,effect=i['effect']) for i in items]
  baseline=self.read()
  for timing in ('BEFORE','DEFERRED'):
   self.sql(('CREATE TRIGGER fixture_fail_audit BEFORE INSERT' if timing=='BEFORE' else 'CREATE CONSTRAINT TRIGGER fixture_fail_audit AFTER INSERT')+' ON document_types.command_audit '+('DEFERRABLE INITIALLY DEFERRED ' if timing=='DEFERRED' else '')+'FOR EACH ROW EXECUTE FUNCTION document_types.fixture_fail_audit()')
   for p in payloads:
    result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.cp_statement(p)+'COMMIT;',env=env,capture_output=True,text=True,timeout=20)
    self.assertNotEqual(result.returncode,0);self.assertIn('synthetic audit refusal',result.stderr);self.assertEqual(self.read(),baseline)
   self.sql('DROP TRIGGER fixture_fail_audit ON document_types.command_audit')
  rows=json.loads(self.sql('SELECT jsonb_agg(to_jsonb(a)) FROM document_types.command_audit a'));self.assertEqual(len(rows),4)
  for row in rows:
   self.assertEqual(row['Before'],{});self.assertTrue(row['BindingHash']);self.assertNotIn('issuer',row['Request']);self.assertNotIn('subject',row['Request'])
  for payload in payloads:self.assertEqual(self.cp(payload)['state'],'applied')
  persisted=json.loads(self.sql('SELECT jsonb_agg(to_jsonb(a)) FROM document_types.command_audit a'))
  self.assertEqual(len(persisted),12)
  self.assertEqual({r['After']['effect'] for r in persisted if r['Request']['operation']=='edit'},{'Load','Unload','Transfer','None'})
  for item in items:
   self.assertEqual(self.read(item['id'],revision=1)['selectedVersion'],item)
   self.assertEqual(self.read(item['id'])['detail']['revision'],2)
 def test_current_concurrent_commands_and_revision_conflict(self):
  self.prepare_types();p=self.new()
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.cp_statement(p),'app')]*4)
  self.assertEqual(sorted(r['state'] for r in results),['applied','replayed','replayed','replayed']);id=results[0]['snapshot']['id']
  a=self.new(operation='edit',documentTypeId=id,expectedRevision=1,label='Concurrent A');b=dict(a,commandId=str(uuid.uuid4()),label='Concurrent B')
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.cp_statement(a),'app'),(self.cp_statement(b),'app')]);self.assertEqual(sorted(r['state'] for r in results),['applied','conflict'])
  self.assertEqual(self.read(id,revision=1)['selectedVersion']['revision'],1);self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'2')
 def test_pagination_search_literal_and_history_bounded(self):
  self.prepare_types()
  for i in range(23):self.cp(self.new(label='Synthetic page '+str(i)))
  first=self.read(search='SYNTHETIC PAGE');self.assertEqual(len(first['items']),21)
  self.assertEqual(len(self.read(search='Synthetic page',after=first['items'][19]['id'])['items']),3);self.assertEqual(self.read(search='%')['items'],[])
  item=first['items'][0]
  for revision in range(1,24):self.assertEqual(self.cp(self.new(operation='edit',documentTypeId=item['id'],expectedRevision=revision))['state'],'applied')
  first=self.read(item['id']);self.assertEqual(len(first['history']),21)
  second=self.read(item['id'],before=first['history'][19]['revision']);self.assertEqual(len(second['history']),4)
  self.assertEqual(self.read(item['id'],revision=1)['selectedVersion'],item)
 def test_max_revision_refused_without_rewriting_versions(self):
  self.prepare_types();item=self.cp(self.new())['snapshot'];id=item['id']
  self.sql(f'''BEGIN;UPDATE document_types.definitions SET "Revision"=2147483647 WHERE "Id"='{id}';INSERT INTO document_types.versions("TenantId","LegalEntityId","DocumentTypeId","Revision","Label","Effect") VALUES('{self.tenant}','{self.company}','{id}',2147483647,'Exhausted','None');COMMIT;''')
  self.assertEqual(self.cp(self.new(operation='edit',documentTypeId=id,expectedRevision=2147483647)),dict(state='conflict'))
  self.assertEqual(self.read(id,revision=1)['selectedVersion'],item);self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'1')

 def test_role_permission_assignment_edits_and_disable_apply_before_replay(self):
  self.prepare_types();p=self.new();self.cp(p)
  edit=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  self.assertEqual(self.role_command(edit)['state'],'applied');self.assertEqual(self.cp(p),dict(state='forbidden'))
  self.role_command(dict(edit,commandId=str(uuid.uuid4()),expectedRevision=2,permissionIds=[s['resourceId'] for _,s in self.permissions]))
  request,snap=self.permissions[1]
  self.role_command(dict(request,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=1,action='document-types.edit'))
  self.assertEqual(self.cp(p),dict(state='forbidden'),'permission edit removes create on same identity')
  self.role_command(dict(request,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=2))
  self.assertEqual(self.cp(p)['state'],'replayed')
  self.sql(f'''INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1)''')
  self.assertEqual(self.read(),dict(state='forbidden'));self.assertEqual(self.cp(p),dict(state='forbidden'))

 def test_foreign_current_binding_and_raw_company_legacy_origins_are_independent(self):
  self.prepare_types();id=self.cp(self.new())['snapshot']['id']
  self.actor=self.owner_actor;self.assertEqual(self.read(),dict(state='forbidden'),'SUPER ADMIN is not a business membership')
  self.actor=self.delegate;self.actor=dict(self.actor,subject='changed opaque subject')
  self.assertEqual(self.read(id),dict(state='forbidden'))

 def test_current_role_revocation_serializes_before_pending_command_and_replay(self):
  self.prepare_types();p=self.new();self.cp(p)
  revoke=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  results,_=self.barrier_race(self.role_statement(revoke),[(self.cp_statement(p),'app')],holder_role='app')
  self.assertEqual(results,[dict(state='forbidden')])
  self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'1')

 def test_old_repeatable_read_snapshot_cannot_resurrect_a_revoked_business_role(self):
  self.prepare_types();p=self.new()
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
   self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'0')
  finally:
   if child.poll() is None:child.kill();child.communicate(timeout=5)

 def test_regression_effect_before_role_revoke_serializes_and_binding_replacement_refuses(self):
  self.prepare_types();p=self.new()
  revoke=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  results,held=self.barrier_race(self.cp_statement(p),[(self.role_statement(revoke),'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.cp(p),dict(state='forbidden'));self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'1')
  self.role_command(dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=2,permissionIds=[s['resourceId'] for _,s in self.permissions]))
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Replaced binding' WHERE "InternalIdentityId"='{self.actor['internalIdentityId']}' ''')
  self.assertEqual(self.cp(p),dict(state='forbidden'))
  self.actor=dict(self.actor,subject='Replaced binding');self.assertEqual(self.cp(p),dict(state='forbidden'),'replacement binding does not inherit historical assignment')

 def test_assignment_revoke_and_read_dependency_before_historical_replay(self):
  self.prepare_types();p=self.new();self.cp(p)
  revoke=dict(self.cp_assignment_request,commandId=str(uuid.uuid4()),resourceId=self.cp_assignment['resourceId'],expectedRevision=1,active=False)
  self.assertEqual(self.role_command(revoke)['state'],'applied');self.assertEqual(self.cp(p),dict(state='forbidden'))
  self.assertEqual(self.role_command(dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=2,active=True))['state'],'applied')
  without_read=[snapshot['resourceId'] for request,snapshot in self.permissions if request['action']!='document-types.read']
  self.role_command(dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=without_read))
  self.assertEqual(self.cp(p),dict(state='forbidden'))

 def test_permission_assignment_and_binding_races_use_same_current_777036_boundary(self):
  self.prepare_types();accepted=self.new();self.cp(accepted)
  request,snapshot=self.permissions[1]
  changes=[(dict(request,commandId=str(uuid.uuid4()),resourceId=snapshot['resourceId'],expectedRevision=1,action='document-types.edit'),dict(request,commandId=str(uuid.uuid4()),resourceId=snapshot['resourceId'],expectedRevision=2)),
   (dict(self.cp_assignment_request,commandId=str(uuid.uuid4()),resourceId=self.cp_assignment['resourceId'],expectedRevision=1,active=False),dict(self.cp_assignment_request,commandId=str(uuid.uuid4()),resourceId=self.cp_assignment['resourceId'],expectedRevision=2))]
  for revoke,restore in changes:
   results,_=self.barrier_race(self.role_statement(revoke),[(self.cp_statement(accepted),'app')],holder_role='app')
   self.assertEqual(results,[dict(state='forbidden')]);self.assertEqual(self.role_command(restore)['state'],'applied')
  binding=self.actor['internalIdentityId']
  results,_=self.barrier_race(f"UPDATE organization_access.external_identity_bindings SET \"Subject\"='Replaced' WHERE \"InternalIdentityId\"='{binding}';",[(self.cp_statement(accepted),'app')],holder_role='infra')
  self.assertEqual(results,[dict(state='forbidden')]);self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'1')

 def test_effect_before_permission_assignment_binding_and_disable_serializes_current_revocation(self):
  self.prepare_types()
  permission,snapshot=self.permissions[1]
  changes=[
   (self.role_statement(dict(permission,commandId=str(uuid.uuid4()),resourceId=snapshot['resourceId'],expectedRevision=1,action='document-types.edit')),'app',lambda:self.role_command(dict(permission,commandId=str(uuid.uuid4()),resourceId=snapshot['resourceId'],expectedRevision=2))),
   (self.role_statement(dict(self.cp_assignment_request,commandId=str(uuid.uuid4()),resourceId=self.cp_assignment['resourceId'],expectedRevision=1,active=False)),'app',lambda:self.role_command(dict(self.cp_assignment_request,commandId=str(uuid.uuid4()),resourceId=self.cp_assignment['resourceId'],expectedRevision=2)))
  ]
  for statement,role,restore in changes:
   accepted=self.new()
   results,held=self.barrier_race(self.cp_statement(accepted),[(statement,role)],holder_role='app')
   self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
   self.assertEqual(self.cp(accepted),dict(state='forbidden'));self.assertEqual(restore()['state'],'applied')
  identity=self.actor['internalIdentityId'];subject=self.actor['subject'].replace("'","''")
  accepted=self.new()
  statement=f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Synthetic replaced reverse ordering' WHERE "InternalIdentityId"='{identity}';SELECT jsonb_build_object('state','replaced');'''
  results,held=self.barrier_race(self.cp_statement(accepted),[(statement,'infra')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results,[dict(state='replaced')]);self.assertEqual(self.cp(accepted),dict(state='forbidden'))
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='{subject}' WHERE "InternalIdentityId"='{identity}' ''')
  accepted=self.new()
  statement=f'''INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1);SELECT jsonb_build_object('state','disabled');'''
  results,held=self.barrier_race(self.cp_statement(accepted),[(statement,'infra')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results,[dict(state='disabled')]);self.assertEqual(self.cp(accepted),dict(state='forbidden'))
  self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'4')

 def test_disable_first_physical_boundary_denies_new_effect_and_historical_replay(self):
  self.prepare_types();accepted=self.new();self.cp(accepted)
  fresh=self.new(label='Must not persist after disable')
  statement=f'''SELECT pg_advisory_xact_lock(777036);INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1);SELECT jsonb_build_object('state','disabled');'''
  results,held=self.barrier_race(statement,[(self.cp_statement(fresh),'app'),(self.cp_statement(accepted),'app')],holder_role='infra')
  self.assertEqual(held[-1],dict(state='disabled'));self.assertEqual(results,[dict(state='forbidden'),dict(state='forbidden')])
  self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'1')
  self.assertEqual(self.sql('SELECT count(*) FROM document_types.versions'),'1')

 def test_edit_replay_returns_its_original_version_after_a_later_behavior_edit(self):
  self.prepare_types();first=self.cp(self.new(effect='Load'))['snapshot']
  edit=self.new(operation='edit',documentTypeId=first['id'],expectedRevision=1,label='Second version',effect='Unload')
  second=self.cp(edit)['snapshot']
  third=self.cp(self.new(operation='edit',documentTypeId=first['id'],expectedRevision=2,label='Third version',effect='Transfer'))['snapshot']
  self.assertEqual(self.cp(edit),dict(state='replayed',snapshot=second))
  read=self.read(first['id'],revision=1);self.assertEqual(read['detail'],third);self.assertEqual(read['selectedVersion'],first)
  self.assertEqual(self.read(first['id'],revision=2)['selectedVersion'],second)
  self.assertEqual(self.sql('SELECT count(*) FROM document_types.command_audit'),'3')

 def test_foreign_tenant_authorized_writer_cannot_read_mutate_or_replay_original(self):
  self.prepare_types();original=self.new();snap=self.cp(original)['snapshot'];actor=self.actor
  foreign,company,identity,member,role,assignment=[str(uuid.uuid4()) for _ in range(6)]
  self.sql(f'''INSERT INTO organization_access.tenants("Id","Name") VALUES('{foreign}','Synthetic foreign');
   INSERT INTO organization_access.legal_entities("Id","TenantId","Name") VALUES('{company}','{foreign}','Foreign company');
   INSERT INTO organization_access.external_identity_bindings VALUES('{identity}','https://foreign.test','opaque');
   INSERT INTO organization_access.memberships VALUES('{member}','{foreign}','{identity}');
   INSERT INTO organization_access.tenant_role_objects SELECT gen_random_uuid(),'{foreign}','permission',jsonb_build_object('action',a,'legalEntityId','{company}','siteId',NULL,'warehouseId',NULL),1 FROM unnest(ARRAY['document-types.read','document-types.create','document-types.edit']) a;
   INSERT INTO organization_access.tenant_role_objects VALUES('{role}','{foreign}','role',jsonb_build_object('permissionIds',(SELECT jsonb_agg("Id"::text) FROM organization_access.tenant_role_objects WHERE "TenantId"='{foreign}' AND "Kind"='permission')),1);
   INSERT INTO organization_access.tenant_role_objects VALUES('{assignment}','{foreign}','assignment',jsonb_build_object('membershipId','{member}','internalIdentityId','{identity}','active',true,'roleId','{role}','bindingHash',encode(sha256(convert_to(jsonb_build_array('https://foreign.test','opaque')::text,'UTF8')),'hex')),1);''')
  self.actor=dict(internalIdentityId=identity,issuer='https://foreign.test',subject='opaque')
  self.assertEqual(self.read(company=company)['items'],[])
  self.assertEqual(self.read(snap['id'],company=company,revision=1),dict(state='not_found'))
  self.assertEqual(self.read(snap['id'],company=self.company,revision=1),dict(state='forbidden'))
  self.assertEqual(self.cp(dict(original,legalEntityId=company)),dict(state='conflict'))
  self.assertEqual(self.cp(self.new(operation='edit',legalEntityId=company,documentTypeId=snap['id'],expectedRevision=1)),dict(state='not_found'))
  self.actor=actor;self.assertEqual(self.read(snap['id'])['detail'],snap)

if __name__=='__main__':unittest.main()
