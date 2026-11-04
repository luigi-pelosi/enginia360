#!/usr/bin/env python3
"""MVP05 final-only real PostgreSQL acceptance; no deployed target or business seed."""
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
class CatalogTests(unittest.TestCase):
 # Reuse setup/teardown and trusted identity/role command helpers, not old tests.
 locals().update({k:v for k,v in vars(base.RoleTests).items() if callable(v) and not k.startswith('test')})
 def read(self,record=None,kind=None,search=None,after=None):
  lit=lambda v: "'"+str(v).replace("'","''")+"'" if v is not None else 'NULL'
  return self.app_result('SELECT catalog.management_read('+','.join([lit(search)+'::text',lit(after)+'::uuid',lit(record)+'::uuid',lit(kind)+'::text'])+')')
 def cp(self,p):
  return self.app_result("SELECT catalog.management_command('"+json.dumps(p).replace("'","''")+"')")
 def cp_statement(self,p):
  return self.actor_settings()+"SELECT catalog.management_command('"+json.dumps(p).replace("'","''")+"');"
 def new(self,**changes):
  return dict(dict(commandId=str(uuid.uuid4()),operation='create',itemId=None,expectedRevision=0,authorityVersion=1,kind='Article',label='Synthetic catalog'),**changes)
 def prepare_catalog(self,authority=True):
  self.prepare_user_admin()
  self.assertEqual(self.read(),dict(state='forbidden'),'administrative delegation is not an operative grant')
  self.permissions=[]
  for action in ('catalog.shared.read','catalog.shared.create','catalog.shared.edit'):
   p=self.role_payload('permission',label=action,action=action,legalEntityId=None,siteId=None,warehouseId=None)
   self.permissions.append((p,self.role_command(p)['snapshot']))
  role=self.role_payload('role',label='Configured business operator',permissionIds=[s['resourceId'] for _,s in self.permissions]);self.cp_role_request=role;self.cp_role=self.role_command(role)['snapshot']
  member=next(m for m in self.role_read()['memberships'] if m['membershipId']==self.member)
  assignment=self.role_payload('assignment',roleId=self.cp_role['resourceId'],membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=member['bindingHash'],active=True)
  self.cp_assignment_request=assignment;self.cp_assignment=self.role_command(assignment)['snapshot']
  if authority:
   command,verification,source,profile=[str(uuid.uuid4()) for _ in range(4)]
   statement=f"BEGIN;SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT catalog.establish_authority('{command}','{self.tenant}','{self.member}','{verification}',0,'Enginia360ToExternal','{source}','{profile}',ARRAY['{self.company}']::uuid[]);COMMIT;"
   result=self.owner_sql(statement);self.assertEqual(result.returncode,0,result.stderr);self.assertIn('applied',result.stdout)
 def test_role_permission_assignment_edits_and_disable_apply_before_replay(self):
  self.prepare_catalog();p=self.new();self.cp(p)
  edit=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  self.assertEqual(self.role_command(edit)['state'],'applied');self.assertEqual(self.cp(p),dict(state='forbidden'))
  self.role_command(dict(edit,commandId=str(uuid.uuid4()),expectedRevision=2,permissionIds=[s['resourceId'] for _,s in self.permissions]))
  request,snap=self.permissions[1]
  self.role_command(dict(request,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=1,action='catalog.shared.edit'))
  self.assertEqual(self.cp(p),dict(state='forbidden'),'permission edit removes create on same identity')
  self.role_command(dict(request,commandId=str(uuid.uuid4()),resourceId=snap['resourceId'],expectedRevision=2))
  self.assertEqual(self.cp(p)['state'],'replayed')
  self.sql(f'''INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1)''')
  self.assertEqual(self.read(),dict(state='forbidden'));self.assertEqual(self.cp(p),dict(state='forbidden'))
 def test_foreign_current_binding_and_raw_company_legacy_origins_are_independent(self):
  self.prepare_catalog();id=self.cp(self.new())['snapshot']['id']
  self.actor=self.owner_actor;self.assertEqual(self.read(),dict(state='forbidden'),'SUPER ADMIN is not a business membership')
  self.actor=self.delegate;self.actor=dict(self.actor,subject='changed opaque subject')
  self.assertEqual(self.read(id),dict(state='forbidden'))
 def test_current_role_revocation_serializes_before_pending_command_and_replay(self):
  self.prepare_catalog();p=self.new();self.cp(p)
  revoke=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  results,_=self.barrier_race(self.role_statement(revoke),[(self.cp_statement(p),'app')],holder_role='app')
  self.assertEqual(results,[dict(state='forbidden')])
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.management_audit'),'1')
 def test_old_repeatable_read_snapshot_cannot_resurrect_a_revoked_business_role(self):
  self.prepare_catalog();p=self.new()
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
   self.assertEqual(self.sql('SELECT count(*) FROM catalog.management_audit'),'0')
  finally:
   if child.poll() is None:child.kill();child.communicate(timeout=5)
 def test_regression_effect_before_role_revoke_serializes_and_binding_replacement_refuses(self):
  self.prepare_catalog();p=self.new()
  revoke=dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=[])
  results,held=self.barrier_race(self.cp_statement(p),[(self.role_statement(revoke),'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.cp(p),dict(state='forbidden'));self.assertEqual(self.sql('SELECT count(*) FROM catalog.management_audit'),'1')
  self.role_command(dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=2,permissionIds=[s['resourceId'] for _,s in self.permissions]))
  self.sql(f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Replaced binding' WHERE "InternalIdentityId"='{self.actor['internalIdentityId']}' ''')
  self.assertEqual(self.cp(p),dict(state='forbidden'))
  self.actor=dict(self.actor,subject='Replaced binding');self.assertEqual(self.cp(p),dict(state='forbidden'),'replacement binding does not inherit historical assignment')
 def test_article_and_service_canonical_create_detail_search_edit_historical_replay_duplicates(self):
  self.prepare_catalog();self.assertEqual(self.read()['items'],[])
  for kind,stored in [('Article','Part'),('Service','Service')]:
   request=self.new(kind=kind,label='Synthetic '+kind);first=self.cp(request);self.assertEqual(first['state'],'applied');snapshot=first['snapshot'];id=snapshot['id']
   self.assertEqual(snapshot,dict(id=id,kind=kind,label=request['label'],revision=1))
   self.assertEqual(self.read(id)['detail'],snapshot);self.assertEqual(self.read(kind=kind,search=kind.lower())['items'],[snapshot])
   edit=self.new(operation='edit',itemId=id,expectedRevision=1,kind=kind,label='Edited '+kind)
   self.assertEqual(self.cp(edit)['snapshot']['revision'],2);self.assertEqual(self.read(id)['detail']['label'],edit['label'])
   self.assertEqual(self.cp(request),dict(state='replayed',snapshot=snapshot))
   self.assertEqual(self.cp(dict(request,label='changed'))['state'],'conflict')
   self.assertEqual(self.cp(dict(edit,commandId=str(uuid.uuid4())))['state'],'conflict')
   self.assertEqual(self.cp(self.new(operation='edit',itemId=id,expectedRevision=2,kind='Service' if kind=='Article' else 'Article'))['state'],'conflict')
   self.assertEqual(self.sql(f"SELECT \"Kind\" FROM catalog.items WHERE \"Id\"='{id}'"),stored)
   self.assertEqual(self.cp(self.new(kind=kind,label=edit['label']))['state'],'applied','duplicates do not imply merge')
  self.assertEqual(len(self.read()['items']),4)
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.stock'),'0','catalog never manufactures stock')
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'0','no implicit prices')
 def test_finite_scope_and_missing_null_keys_never_become_warehouse_wildcards(self):
  self.prepare_catalog()
  for action,company,site,warehouse in [('catalog.shared.read',self.company,None,None),('catalog.shared.create',None,self.site,None),('catalog.shared.edit',None,None,self.warehouse),('catalog.shared.*',None,None,None),('organization-context.read',None,None,None),('counterparties.extensions.read',None,None,None)]:
   p=self.role_payload('permission',label='Invalid scope',action=action,legalEntityId=company,siteId=site,warehouseId=warehouse)
   self.assertIn(self.role_command(p)['state'],('invalid','forbidden'))
  self.assertEqual(self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT coalesce(jsonb_agg(\"Permission\"),'[]') FROM organization_access.effective_membership_scopes WHERE \"MembershipId\"='{self.member}'"),[])
  self.sql("UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"-'siteId' WHERE \"TenantId\"='"+self.tenant+"' AND \"Kind\"='permission' AND \"Data\"->>'action'='catalog.shared.read'")
  self.assertEqual(self.read(),dict(state='forbidden'))
 def test_exact_fields_types_canonical_ids_and_unicode_bounds(self):
  self.prepare_catalog();p=self.new()
  for invalid in (None,[],{},True,'create'):
   self.assertEqual(self.cp(invalid)['state'],'invalid')
  for change in [dict(commandId=''),dict(commandId='AAAAAAAA-0000-0000-0000-000000000001'),dict(commandId='00000000-0000-0000-0000-000000000000'),dict(extra=True),dict(expectedRevision=True),dict(expectedRevision='0'),dict(authorityVersion=None),dict(label=' '),dict(label='x'*101),dict(label='bad\nlabel'),dict(kind='Part'),dict(kind=0),dict(kind=None),dict(operation='delete'),dict(itemId=str(uuid.uuid4()))]:
   self.assertEqual(self.cp(dict(p,**change))['state'],'invalid',change)
  self.assertEqual(self.cp(self.new(label='😀'*100))['state'],'applied')
  for key in p:
   reduced=dict(p);del reduced[key];self.assertEqual(self.cp(reduced)['state'],'invalid',key)
 def test_missing_external_and_stale_authority_without_silent_fallback(self):
  self.prepare_catalog(authority=False);self.assertEqual(self.read()['authority']['state'],'missing');self.assertEqual(self.cp(self.new())['state'],'missing')
  for version,direction in [(0,'ExternalToEnginia360'),(1,'Enginia360ToExternal')]:
   command,verification,source,profile=[str(uuid.uuid4()) for _ in range(4)]
   result=self.owner_sql(f"BEGIN;SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT catalog.establish_authority('{command}','{self.tenant}','{self.member}','{verification}',{version},'{direction}','{source}','{profile}',ARRAY['{self.company}']::uuid[]);COMMIT;")
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(self.cp(self.new())['state'],'external' if version==0 else 'stale_authority')
  self.assertEqual(self.cp(self.new(authorityVersion=2))['state'],'applied')
 def test_atomic_immutable_minimized_audit_before_insert_and_deferred_commit_rollback_both_kinds(self):
  self.prepare_catalog();items={kind:self.cp(self.new(kind=kind))['snapshot'] for kind in ['Article','Service']}
  for table in ('management_audit','authority_history'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','catalog.{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
   self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='catalog.{table}'::regclass"),'t')
   for mutation in (f'UPDATE catalog.{table} SET "TenantId"="TenantId"',f'DELETE FROM catalog.{table}',f'TRUNCATE catalog.{table}'):
    self.assertNotEqual(self.owner_sql(mutation,ok=False).returncode,0)
  self.sql("CREATE FUNCTION catalog.fixture_fail_audit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic catalog audit refusal'; END $$")
  import subprocess
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  payloads=[self.new(kind=kind) for kind in items]+[self.new(operation='edit',itemId=item['id'],expectedRevision=1,kind=kind,label='Must rollback') for kind,item in items.items()]
  baseline=self.read()
  for timing in ('BEFORE','DEFERRED'):
   self.sql(('CREATE TRIGGER fixture_fail_audit BEFORE INSERT' if timing=='BEFORE' else 'CREATE CONSTRAINT TRIGGER fixture_fail_audit AFTER INSERT')+' ON catalog.management_audit '+('DEFERRABLE INITIALLY DEFERRED ' if timing=='DEFERRED' else '')+'FOR EACH ROW EXECUTE FUNCTION catalog.fixture_fail_audit()')
   for payload in payloads:
    result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.cp_statement(payload)+'COMMIT;',env=env,capture_output=True,text=True,timeout=20)
    self.assertNotEqual(result.returncode,0);self.assertIn('synthetic catalog audit refusal',result.stderr);self.assertEqual(self.read(),baseline)
   self.sql('DROP TRIGGER fixture_fail_audit ON catalog.management_audit')
  rows=json.loads(self.sql('SELECT jsonb_agg(to_jsonb(a)) FROM catalog.management_audit a'))
  self.assertEqual(len(rows),2)
  for row in rows:
   self.assertEqual(row['Before'],{});self.assertEqual(row['After']['revision'],1);self.assertTrue(row['BindingHash']);self.assertNotIn('issuer',row['Request']);self.assertNotIn('subject',row['Request'])
 def test_concurrent_create_replay_revision_and_disable_current_boundary(self):
  self.prepare_catalog();p=self.new()
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.cp_statement(p),'app')]*4)
  self.assertEqual(sorted(r['state'] for r in results),['applied','replayed','replayed','replayed']);id=results[0]['snapshot']['id']
  a=self.new(operation='edit',itemId=id,expectedRevision=1,label='Concurrent A');b=dict(a,commandId=str(uuid.uuid4()),label='Concurrent B')
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.cp_statement(a),'app'),(self.cp_statement(b),'app')])
  self.assertEqual(sorted(r['state'] for r in results),['applied','conflict'])
  holder=f"SELECT pg_advisory_xact_lock(777036);SELECT set_config('app.tenant_id','{self.tenant}',true);INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1);"
  results,_=self.barrier_race(holder,[(self.cp_statement(p),'app')]);self.assertEqual(results,[dict(state='forbidden')])
 def test_search_pagination_literal_and_foreign_tenant_detail_no_disclosure(self):
  self.prepare_catalog();first_actor=self.actor
  for i in range(23):self.assertEqual(self.cp(self.new(label='Synthetic page '+str(i)))['state'],'applied')
  first=self.read(search='SYNTHETIC PAGE');self.assertEqual(len(first['items']),21)
  second=self.read(search='Synthetic page',after=first['items'][19]['id']);self.assertEqual(len(second['items']),3)
  self.assertEqual(self.read(search='%')['items'],[],'search is literal, not wildcard')
  foreign=str(uuid.uuid4());identity=str(uuid.uuid4());member=str(uuid.uuid4());permission=str(uuid.uuid4());role=str(uuid.uuid4());assignment=str(uuid.uuid4())
  self.sql(f"INSERT INTO organization_access.tenants(\"Id\",\"Name\") VALUES('{foreign}','Synthetic foreign');INSERT INTO organization_access.external_identity_bindings VALUES('{identity}','https://foreign.test','opaque');INSERT INTO organization_access.memberships VALUES('{member}','{foreign}','{identity}');")
  self.sql(f"INSERT INTO organization_access.tenant_role_objects VALUES('{permission}','{foreign}','permission',jsonb_build_object('action','catalog.shared.read','legalEntityId',NULL,'siteId',NULL,'warehouseId',NULL),1);INSERT INTO organization_access.tenant_role_objects VALUES('{role}','{foreign}','role',jsonb_build_object('permissionIds',jsonb_build_array('{permission}')),1);INSERT INTO organization_access.tenant_role_objects VALUES('{assignment}','{foreign}','assignment',jsonb_build_object('membershipId','{member}','internalIdentityId','{identity}','active',true,'roleId','{role}','bindingHash',encode(sha256(convert_to(jsonb_build_array('https://foreign.test','opaque')::text,'UTF8')),'hex')),1);")
  self.actor=dict(internalIdentityId=identity,issuer='https://foreign.test',subject='opaque')
  self.assertEqual(self.read()['items'],[]);self.assertEqual(self.read(first['items'][0]['id']),dict(state='not_found'))
  edit_permission=str(uuid.uuid4());foreign_company=str(uuid.uuid4())
  self.sql(f"INSERT INTO organization_access.legal_entities(\"Id\",\"TenantId\",\"Name\") VALUES('{foreign_company}','{foreign}','Synthetic foreign company');INSERT INTO organization_access.tenant_role_objects VALUES('{edit_permission}','{foreign}','permission',jsonb_build_object('action','catalog.shared.edit','legalEntityId',NULL,'siteId',NULL,'warehouseId',NULL),1);UPDATE organization_access.tenant_role_objects SET \"Data\"=jsonb_build_object('permissionIds',jsonb_build_array('{permission}','{edit_permission}')),\"Revision\"=2 WHERE \"Id\"='{role}';")
  setup=self.owner_sql(f"BEGIN;SELECT set_config('app.tenant_id','{foreign}',true);SELECT catalog.establish_authority('{uuid.uuid4()}','{foreign}','{member}','{uuid.uuid4()}',0,'Enginia360ToExternal','{uuid.uuid4()}','{uuid.uuid4()}',ARRAY['{foreign_company}']::uuid[]);COMMIT;")
  self.assertEqual(setup.returncode,0,setup.stderr);self.assertIn('applied',setup.stdout)
  attack=self.new(operation='edit',itemId=first['items'][0]['id'],expectedRevision=1,label='Cross-tenant forbidden write')
  self.assertEqual(self.cp(attack),dict(state='not_found'),'even a fully authorized foreign writer cannot mutate the target identity')
  self.actor=first_actor;self.assertEqual(len(self.read()['items']),21);self.assertNotEqual(self.read(first['items'][0]['id'])['detail']['label'],attack['label'])
 def test_assignment_revoke_and_read_dependency_before_historical_replay(self):
  self.prepare_catalog();p=self.new();self.cp(p)
  revoke=dict(self.cp_assignment_request,commandId=str(uuid.uuid4()),resourceId=self.cp_assignment['resourceId'],expectedRevision=1,active=False)
  self.assertEqual(self.role_command(revoke)['state'],'applied');self.assertEqual(self.cp(p),dict(state='forbidden'))
  self.assertEqual(self.role_command(dict(revoke,commandId=str(uuid.uuid4()),expectedRevision=2,active=True))['state'],'applied')
  without_read=[snapshot['resourceId'] for request,snapshot in self.permissions if request['action']!='catalog.shared.read']
  self.role_command(dict(self.cp_role_request,commandId=str(uuid.uuid4()),resourceId=self.cp_role['resourceId'],expectedRevision=1,permissionIds=without_read))
  self.assertEqual(self.cp(p),dict(state='forbidden'))
 def test_canonical_edit_never_reprices_company_extensions_or_inherits_pricing_grants(self):
  self.prepare_catalog();item=self.cp(self.new())['snapshot']['id'];supplier=str(uuid.uuid4());actor=self.actor
  self.actor=self.owner_actor;second=self.create_company(self.tenant);self.actor=actor
  self.sql(f"INSERT INTO counterparties.counterparties(\"Id\",\"TenantId\",\"LegalName\",\"FiscalIdentifier\",\"RegisteredOffice\",\"IsSupplier\") VALUES('{supplier}','{self.tenant}','Synthetic supplier','','',true)")
  def price(company):
   return self.app_result(f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT catalog.supplier_purchase_price_state('{company}','{supplier}','{item}')")
  self.assertEqual(price(self.company),dict(state='forbidden'),'shared identity permission never grants company prices')
  for company,amount in [(self.company,'12.345678'),(second,'7.890123')]:
   self.sql(f"INSERT INTO organization_access.company_permissions(\"Id\",\"MembershipId\",\"TenantId\",\"LegalEntityId\",\"Permission\") SELECT gen_random_uuid(),'{self.member}','{self.tenant}','{company}',a FROM unnest(ARRAY['catalog.purchase-prices.read','counterparties.read']) a;INSERT INTO catalog.supplier_purchase_price_history(\"CommandId\",\"TenantId\",\"LegalEntityId\",\"SupplierId\",\"CatalogItemId\",\"Revision\",\"UnitPurchasePrice\",\"ActorMembershipId\",\"SupplierRevision\",\"CatalogVersion\",\"AuthorityVersion\",\"Payload\") VALUES(gen_random_uuid(),'{self.tenant}','{company}','{supplier}','{item}',1,{amount},'{self.member}',0,1,1,'{{}}');")
  before=self.sql('SELECT jsonb_agg(to_jsonb(p) ORDER BY "LegalEntityId") FROM catalog.supplier_purchase_price_history p')
  edit=self.new(operation='edit',itemId=item,expectedRevision=1,label='Updated shared label')
  self.assertEqual(self.cp(edit)['state'],'applied')
  after=self.sql('SELECT jsonb_agg(to_jsonb(p) ORDER BY "LegalEntityId") FROM catalog.supplier_purchase_price_history p')
  self.assertEqual(after,before)
  print('MVP05_PRICE_PRESERVATION '+json.dumps(dict(beforeSqlJson=before,afterSqlJson=after,currentIdentity=self.read(item)['detail'])),flush=True)
  for company,amount in [(self.company,'12.345678'),(second,'7.890123')]:
   result=price(company);self.assertEqual(result['state'],'ready');self.assertEqual(result['item']['id'],item);self.assertEqual(result['item']['version'],2)
   self.assertEqual(result['entry']['catalogVersion'],1);self.assertEqual(result['entry']['unitPurchasePrice'],amount);self.assertFalse(result['canManage'])
 def test_permission_assignment_and_binding_races_use_same_current_777036_boundary(self):
  self.prepare_catalog();accepted=self.new();self.cp(accepted)
  request,snapshot=self.permissions[1]
  changes=[(dict(request,commandId=str(uuid.uuid4()),resourceId=snapshot['resourceId'],expectedRevision=1,action='catalog.shared.edit'),dict(request,commandId=str(uuid.uuid4()),resourceId=snapshot['resourceId'],expectedRevision=2)),
   (dict(self.cp_assignment_request,commandId=str(uuid.uuid4()),resourceId=self.cp_assignment['resourceId'],expectedRevision=1,active=False),dict(self.cp_assignment_request,commandId=str(uuid.uuid4()),resourceId=self.cp_assignment['resourceId'],expectedRevision=2))]
  for revoke,restore in changes:
   results,_=self.barrier_race(self.role_statement(revoke),[(self.cp_statement(accepted),'app')],holder_role='app')
   self.assertEqual(results,[dict(state='forbidden')]);self.assertEqual(self.role_command(restore)['state'],'applied')
  binding=self.actor['internalIdentityId']
  results,_=self.barrier_race(f"UPDATE organization_access.external_identity_bindings SET \"Subject\"='Replaced' WHERE \"InternalIdentityId\"='{binding}';",[(self.cp_statement(accepted),'app')],holder_role='infra')
  self.assertEqual(results,[dict(state='forbidden')]);self.assertEqual(self.sql('SELECT count(*) FROM catalog.management_audit'),'1')
 def test_authority_race_and_changed_source_profile_never_replay_old_writer(self):
  self.prepare_catalog();accepted=self.new();self.cp(accepted)
  def authority(version,direction):
   command,verification,source,profile=[str(uuid.uuid4()) for _ in range(4)]
   return f"SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT jsonb_build_object('state',catalog.establish_authority('{command}','{self.tenant}','{self.member}','{verification}',{version},'{direction}','{source}','{profile}',ARRAY['{self.company}']::uuid[]));"
  # Same direction but new technical source/profile is a new version, not permission to reuse stale bytes.
  results,_=self.barrier_race(authority(1,'Enginia360ToExternal'),[(self.cp_statement(accepted),'app')])
  self.assertEqual(results,[dict(state='stale_authority')]);self.assertEqual(self.read()['authority']['version'],2)
  command=self.new(authorityVersion=2)
  results,held=self.barrier_race(self.cp_statement(command),[(authority(2,'ExternalToEnginia360'),'owner')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results,[dict(state='applied')]);self.assertEqual(self.cp(command),dict(state='external'))
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.management_audit'),'2')
 def test_owner_catalog_setup_replay_requires_current_enabled_trusted_membership(self):
  self.prepare_catalog(authority=False)
  command,verification,source,profile=[str(uuid.uuid4()) for _ in range(4)]
  statement=f"BEGIN;SELECT set_config('app.tenant_id','{self.tenant}',true);SELECT catalog.establish_authority('{command}','{self.tenant}','{self.member}','{verification}',0,'Enginia360ToExternal','{source}','{profile}',ARRAY['{self.company}']::uuid[]);COMMIT;"
  for outcome in ('applied','replayed'):
   result=self.owner_sql(statement);self.assertEqual(result.returncode,0,result.stderr);self.assertIn(outcome,result.stdout)
  self.sql(f"INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1)")
  refused=self.owner_sql(statement);self.assertEqual(refused.returncode,0);self.assertIn('forbidden',refused.stdout)
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.authority_history'),'1')
  self.assertEqual(self.sql(f"SELECT has_function_privilege('{os.environ['R00_APP_USER']}','catalog.establish_authority(uuid,uuid,uuid,uuid,integer,text,uuid,uuid,uuid[])','EXECUTE')"),'f')
 def test_real_owner_cli_both_domains_applied_replayed_denied_despite_exact_old_history(self):
  # Real psql/TLS/owner process, never a fabricated response or provider identity.
  self.prepare_catalog(authority=False)
  import subprocess,sys,tempfile
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=self.owner,PGPASSWORD=os.environ['R00_OWNER_PASSWORD'])
  self.assertEqual(env.get('PGSSLMODE'),'verify-full')
  binding=json.loads(self.sql(f"SELECT to_jsonb(b) FROM organization_access.external_identity_bindings b WHERE b.\"InternalIdentityId\"='{self.actor['internalIdentityId']}'"))
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'explicit.json'
   for domain,table in [('counterparties','organization_access.master_authority_history'),('catalog','catalog.authority_history')]:
    value=dict(commandId=str(uuid.uuid4()),domain=domain,tenantId=self.tenant,actorMembershipId=self.member,verificationReference=str(uuid.uuid4()),expectedVersion=0,direction='Enginia360ToExternal',sourceId=str(uuid.uuid4()),profileId=str(uuid.uuid4()),companyIds=[self.company])
    path.write_text(json.dumps(value))
    def cli(overrides=None):
     return subprocess.run([sys.executable,'-I',str(ROOT/'scripts/owner-master-authority.py'),str(path)],env=dict(env,**(overrides or {})),capture_output=True,text=True,timeout=35)
    for _ in range(2):
     result=cli();self.assertEqual(result.returncode,0,result.stderr);self.assertIn('exact history read back',result.stdout)
    self.assertEqual(self.sql(f'SELECT count(*) FROM {table}'),'1')
    insecure=cli(dict(PGSSLMODE='require'));self.assertNotEqual(insecure.returncode,0);self.assertNotIn('exact history read back',insecure.stdout)
    # Preserve an exact immutable history row but remove the current trusted binding.
    # The old helper incorrectly treated this count=1 as successful owner setup.
    self.sql(f"DELETE FROM organization_access.external_identity_bindings WHERE \"InternalIdentityId\"='{binding['InternalIdentityId']}'")
    refused=cli();self.assertNotEqual(refused.returncode,0);self.assertNotIn('exact history read back',refused.stdout)
    self.assertEqual(self.sql(f'SELECT count(*) FROM {table}'),'1')
    literal=lambda x:"'"+x.replace("'","''")+"'"
    self.sql('INSERT INTO organization_access.external_identity_bindings VALUES('+','.join(literal(binding[k]) for k in ('InternalIdentityId','Issuer','Subject'))+')')
    result=cli();self.assertEqual(result.returncode,0,result.stderr);self.assertIn('exact history read back',result.stdout)
 def test_effect_before_permission_assignment_binding_and_disable_serializes_current_revocation(self):
  self.prepare_catalog()
  permission,snapshot=self.permissions[1]
  changes=[
   (self.role_statement(dict(permission,commandId=str(uuid.uuid4()),resourceId=snapshot['resourceId'],expectedRevision=1,action='catalog.shared.edit')),'app',lambda:self.role_command(dict(permission,commandId=str(uuid.uuid4()),resourceId=snapshot['resourceId'],expectedRevision=2))),
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
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.management_audit'),'4')
 def test_persisted_legacy_commercial_snapshots_of_both_kinds_survive_canonical_edit(self):
  self.prepare_catalog()
  document,order,group,payer,vehicle=[str(uuid.uuid4()) for _ in range(5)]
  self.sql(f'''INSERT INTO workshop.document_types("Id","TenantId","LegalEntityId","Version","Name") VALUES('{document}','{self.tenant}','{self.company}',1,'Synthetic historical profile');
   INSERT INTO workshop.orders("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","ConfigurationVersion","PayerId","VehicleId","VehicleHolderId","CreatedByMembershipId") VALUES('{order}','{self.tenant}','{self.company}','{self.site}','{document}',1,'{payer}','{vehicle}','{payer}','{self.member}');
   INSERT INTO workshop.working_groups VALUES('{group}','{self.tenant}','{order}','Synthetic retained group','Active',1,0);''')
  for kind,stored in [('Article','Part'),('Service','Service')]:
   item=self.cp(self.new(kind=kind,label='Frozen '+kind))['snapshot']
   line=str(uuid.uuid4())
   self.sql(f'''INSERT INTO workshop.commercial_lines("Id","TenantId","OrderId","CatalogItemId","CatalogVersion","CatalogLabel","Kind","Quantity","UnitPrice","DiscountPercent","NetAmount","TaxRate","PayerId","WorkingGroupId","ConfigurationVersion","ExpectedRevision") VALUES('{line}','{self.tenant}','{order}','{item['id']}',1,'{item['label']}','{stored}',2,12.345678,0,24.691356,22,'{payer}','{group}',1,0);''')
   before=self.sql(f'''SELECT to_jsonb(l) FROM workshop.commercial_lines l WHERE "Id"='{line}' ''')
   self.assertEqual(self.cp(self.new(kind=kind,operation='edit',itemId=item['id'],expectedRevision=1,label='Current '+kind))['state'],'applied')
   self.assertEqual(self.read(item['id'])['detail']['revision'],2)
   after=self.sql(f'''SELECT to_jsonb(l) FROM workshop.commercial_lines l WHERE "Id"='{line}' ''')
   self.assertEqual(after,before)
   print('MVP05_FROZEN_LINE_PRESERVATION '+json.dumps(dict(beforeSqlJson=before,afterSqlJson=after,currentIdentity=self.read(item['id'])['detail'])),flush=True)
   saved=json.loads(before);self.assertEqual(saved['CatalogItemId'],item['id']);self.assertEqual(saved['CatalogVersion'],1);self.assertEqual(saved['CatalogLabel'],item['label']);self.assertEqual(saved['Kind'],stored)
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.stock'),'0')
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'0')
 def test_maximum_shared_revision_returns_controlled_conflict_without_overflow_or_effect(self):
  self.prepare_catalog();item=self.cp(self.new())['snapshot']['id']
  self.sql(f"UPDATE catalog.items SET \"Version\"=2147483647 WHERE \"Id\"='{item}'")
  payload=self.new(operation='edit',itemId=item,expectedRevision=2147483647,label='Must not overflow')
  self.assertEqual(self.cp(payload),dict(state='conflict'));self.assertEqual(self.read(item)['detail']['revision'],2147483647)
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.management_audit'),'1')
if __name__=='__main__':unittest.main()
