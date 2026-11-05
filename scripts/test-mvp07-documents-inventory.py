#!/usr/bin/env python3
"""MVP07 real isolated SQL acceptance SOURCES. Execute only after whole #146 source-complete."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('roles',ROOT/'scripts/test-mvp03b1-roles.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
def uid():return str(uuid.uuid4())
def lit(value):return 'NULL' if value is None else "'"+str(value).replace("'","''")+"'"
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated SQL required')
class DocumentInventoryTests(unittest.TestCase):
 locals().update({k:v for k,v in vars(base.RoleTests).items() if callable(v) and not k.startswith('test')})
 def doc(self,p):return self.app_result('SELECT documents.command('+lit(json.dumps(p))+'::jsonb)')
 def statement(self,p):return self.actor_settings()+'SELECT documents.command('+lit(json.dumps(p))+'::jsonb);'
 def read(self,id=None,warehouse=None,company=None,site=None,search=None,after=None,chooser=False,selection=None,selection_after=None,ledger_after=None):
  values=[None if chooser else company or self.company,None if chooser else site or self.site,warehouse,id,search,after,selection,selection_after,ledger_after]
  types=['uuid','uuid','uuid','uuid','text','uuid','text','uuid','uuid']
  return self.app_result('SELECT documents.read('+','.join(lit(v)+'::'+t for v,t in zip(values,types))+')')
 def counts(self):return json.loads(self.sql("SELECT jsonb_build_object("+','.join(lit(t)+",(SELECT coalesce(jsonb_agg(to_jsonb(x) ORDER BY to_jsonb(x)::text),'[]') FROM documents."+t+' x)' for t in ('headers','lines','versions','policy_versions','balances','ledger','command_audit','snapshot_fence'))+')'))
 def prepare_documents(self):
  self.prepare_user_admin();self.assertEqual(self.read(chooser=True),dict(state='forbidden'))
  actor=self.actor;self.actor=self.owner_actor
  self.destination=self.org_command(self.org_payload(kind='warehouse',tenantId=self.tenant,parentId=self.site,name='Synthetic destination'),self.tenant)['snapshot']['resourceId']
  self.actor=actor;self.permissions=[]
  actions=[(a,self.company,self.site,None) for a in ('documents.read','documents.save','documents.confirm')]
  actions += [(a,self.company,self.site,w) for w in (self.warehouse,self.destination) for a in ('inventory.document-effects.apply','inventory.quantities.read')]
  actions += [(a,self.company,None,None) for a in ('inventory.policy.read','inventory.policy.manage','document-types.read','document-types.create','document-types.edit')]
  for a,c,s,w in actions:
   p=self.role_payload('permission',label=a,action=a,legalEntityId=c,siteId=s,warehouseId=w);r=self.role_command(p);self.assertEqual(r['state'],'applied');self.permissions.append((p,r['snapshot']))
  self.role_request=self.role_payload('role',label='Synthetic document operator',permissionIds=[p['resourceId'] for _,p in self.permissions]);self.role_snapshot=self.role_command(self.role_request)['snapshot']
  member=next(m for m in self.role_read()['memberships'] if m['membershipId']==self.member)
  self.assignment_request=self.role_payload('assignment',roleId=self.role_snapshot['resourceId'],membershipId=self.member,internalIdentityId=self.delegate['internalIdentityId'],bindingHash=member['bindingHash'],active=True)
  self.assignment_snapshot=self.role_command(self.assignment_request)['snapshot']
  self.types={}
  for effect in ('Load','Unload','Transfer','None'):
   p=dict(commandId=uid(),operation='create',legalEntityId=self.company,documentTypeId=None,expectedRevision=0,label='Synthetic '+effect,effect=effect)
   self.types[effect]=self.app_result('SELECT document_types.command('+lit(json.dumps(p))+'::jsonb)')['snapshot']
  self.part=uid();self.service=uid()
  # Synthetic fixture identities only. New stock is NEVER seeded directly.
  self.sql(f'''INSERT INTO catalog.items VALUES('{self.part}','{self.tenant}','{self.company}','Part','Synthetic article',1),('{self.service}','{self.tenant}','{self.company}','Service','Synthetic service',1)''')
 def line(self,quantity='1',item=None,warehouse=None,destination=None,**changes):
  return dict(dict(id=uid(),itemId=item or self.part,catalogRevision=1,quantity=quantity,warehouseId=warehouse,destinationWarehouseId=destination),**changes)
 def draft(self,effect='Load',lines=None,**changes):
  return dict(dict(commandId=uid(),operation='create',legalEntityId=self.company,siteId=self.site,documentId=None,expectedRevision=0,documentTypeId=self.types[effect]['id'],expectedTypeRevision=1,title='Synthetic '+effect,lines=lines if lines is not None else [self.line(warehouse=self.warehouse if effect!='None' else None,destination=self.destination if effect=='Transfer' else None)]),**changes)
 def confirm(self,snapshot,**changes):
  current=self.read(snapshot['id'])
  type=next(t for t in current['types'] if t['id']==snapshot['documentTypeId'])
  return dict(dict(commandId=uid(),operation='confirm',legalEntityId=self.company,siteId=self.site,documentId=snapshot['id'],expectedRevision=snapshot['revision'],expectedTypeRevision=type['revision'],expectedPolicyRevision=current['policy']['revision']),**changes)
 def load(self,quantity='10',warehouse=None):
  first=self.doc(self.draft(lines=[self.line(quantity,warehouse=warehouse or self.warehouse)]));self.assertEqual(first['state'],'applied');r=self.doc(self.confirm(first['snapshot']));self.assertEqual(r['state'],'applied');return r['snapshot']
 def balance(self,warehouse=None):
  values=self.read(warehouse=warehouse or self.warehouse)['balances'];return next((x['quantity'] for x in values if x['itemId']==self.part),'0.000000')
 def policy(self,allow,revision=None):
  return dict(commandId=uid(),operation='policy',legalEntityId=self.company,expectedRevision=self.read()['policy']['revision'] if revision is None else revision,allowNegative=allow)
 def test_initial_load_multiple_same_item_service_and_save_no_effect(self):
  self.prepare_documents();self.assertEqual(self.balance(),'0.000000')
  p=self.draft(lines=[self.line('2.000001',warehouse=self.warehouse),self.line('0.999999',warehouse=self.warehouse),self.line('8',item=self.service)])
  d=self.doc(p)['snapshot'];self.assertEqual(len(d['lines']),3);self.assertEqual(self.balance(),'0.000000');self.assertEqual(self.read(d['id'])['ledger'],[])
  p.update(commandId=uid(),operation='save',documentId=d['id'],expectedRevision=1,title='Reopened saved draft')
  d=self.doc(p)['snapshot'];self.assertEqual(d['revision'],2);self.assertEqual(self.balance(),'0.000000')
  r=self.doc(self.confirm(d));self.assertEqual(r['state'],'applied');self.assertEqual(self.balance(),'3.000000');self.assertEqual(len(self.read(d['id'])['ledger']),2)
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.stock'),'0');self.assertEqual(self.sql('SELECT count(*) FROM workshop.orders'),'0')
 def test_all_four_effects_atomic_transfer_and_none_service(self):
  self.prepare_documents();self.load('10')
  for effect,quantity,expected in [('Unload','2','8.000000'),('Transfer','3','5.000000'),('None','4','5.000000')]:
   p=self.draft(effect,lines=[self.line(quantity,warehouse=self.warehouse if effect!='None' else None,destination=self.destination if effect=='Transfer' else None),self.line('7',item=self.service)])
   d=self.doc(p)['snapshot'];r=self.doc(self.confirm(d));self.assertEqual(r['state'],'applied');self.assertEqual(self.balance(),expected)
   legs=self.read(d['id'])['ledger'];self.assertEqual(len(legs),{'Unload':1,'Transfer':2,'None':0}[effect])
   if effect=='Transfer':self.assertEqual(self.balance(self.destination),'3.000000');self.assertEqual(sum(__import__('decimal').Decimal(l['quantity']) for l in legs),0)
 def test_default_insufficient_blocks_whole_document_and_no_zero_rows_leak(self):
  self.prepare_documents();self.load('2');d=self.doc(self.draft('Unload',lines=[self.line('1',warehouse=self.warehouse),self.line('2',warehouse=self.warehouse)]))['snapshot'];before=self.counts()
  self.assertEqual(self.doc(self.confirm(d)),dict(state='insufficient_stock'));self.assertEqual(self.counts(),before);self.assertEqual(self.balance(),'2.000000');self.assertEqual(self.read(d['id'])['detail']['state'],'Draft')
  transfer=self.doc(self.draft('Transfer',lines=[self.line('3',warehouse=self.warehouse,destination=self.destination)]))['snapshot'];before=self.counts();self.assertEqual(self.doc(self.confirm(transfer)),dict(state='insufficient_stock'));self.assertEqual(self.counts(),before)
 def test_explicit_company_policy_allow_negative_replay_reblock_no_correction(self):
  self.prepare_documents();self.load('2');p=self.policy(True);setting=self.doc(p);self.assertEqual(setting['state'],'applied');self.assertEqual(self.doc(p),dict(state='replayed',snapshot=setting['snapshot']))
  d=self.doc(self.draft('Unload',lines=[self.line('3',warehouse=self.warehouse)]))['snapshot'];confirmed=self.doc(self.confirm(d))['snapshot'];self.assertEqual(self.balance(),'-1.000000');self.assertTrue(confirmed['appliedConfiguration']['policy']['allowNegative'])
  self.assertEqual(self.doc(self.policy(False))['state'],'applied');self.assertEqual(self.balance(),'-1.000000');self.assertEqual(self.doc(p),dict(state='replayed',snapshot=setting['snapshot']));self.assertFalse(self.read()['policy']['allowNegative'])
  self.load('0.5');self.assertEqual(self.balance(),'-0.500000');self.assertEqual(self.read(d['id'])['detail'],confirmed)
 def test_policy_is_company_owned_and_not_implicitly_granted_by_save_or_admin(self):
  self.prepare_documents();permission=next(p for p,s in self.permissions if p['action']=='inventory.policy.manage');snap=next(s for p,s in self.permissions if p['action']=='inventory.policy.manage')
  revoke=dict(permission,commandId=uid(),resourceId=snap['resourceId'],expectedRevision=1,action='inventory.policy.read');self.role_command(revoke)
  self.assertEqual(self.doc(self.policy(True)),dict(state='forbidden'));self.assertEqual(self.doc(self.draft())['state'],'applied')
 def test_current_type_policy_conflicts_without_draft_lifetime_freeze(self):
  self.prepare_documents();self.load();d=self.doc(self.draft('Unload'))['snapshot'];old=self.confirm(d);self.doc(self.policy(True));before=self.counts();self.assertEqual(self.doc(old),dict(state='config_changed'));self.assertEqual(self.counts(),before)
  t=self.types['Unload'];edit=dict(commandId=uid(),operation='edit',legalEntityId=self.company,documentTypeId=t['id'],expectedRevision=1,label='New Load',effect='Load');self.app_result('SELECT document_types.command('+lit(json.dumps(edit))+'::jsonb)')
  self.assertEqual(self.doc(self.confirm(d,expectedTypeRevision=1)),dict(state='config_changed'))
  r=self.doc(self.confirm(d));self.assertEqual(r['state'],'applied');self.assertEqual(r['snapshot']['appliedConfiguration']['documentType']['effect'],'Load');self.assertEqual(self.balance(),'11.000000')
 def test_confirmed_catalog_snapshot_stays_after_canonical_edit(self):
  self.prepare_documents();d=self.doc(self.draft())['snapshot'];self.sql(f'''UPDATE catalog.items SET "Label"='Later master label',"Version"=2 WHERE "Id"='{self.part}' ''');confirmed=self.doc(self.confirm(d))['snapshot']
  self.assertEqual(confirmed['lines'][0]['label'],'Synthetic article');self.assertEqual(confirmed['lines'][0]['catalogRevision'],1)
  self.assertEqual(self.read(d['id'])['ledger'][0]['label'],'Synthetic article')
 def test_accepted_replay_normalizes_quantity_and_new_uuid_cannot_reconfirm(self):
  self.prepare_documents();p=self.draft(lines=[self.line('1.00',warehouse=self.warehouse)]);d=self.doc(p)['snapshot'];p['lines'][0]['quantity']='1';self.assertEqual(self.doc(p),dict(state='replayed',snapshot=d))
  confirm=self.confirm(d);r=self.doc(confirm);self.assertEqual(self.doc(confirm),dict(state='replayed',snapshot=r['snapshot']));self.assertEqual(self.doc(dict(confirm,commandId=uid())),dict(state='already_confirmed'));self.assertEqual(self.balance(),'1.000000');self.assertEqual(self.doc(p),dict(state='replayed',snapshot=d));self.assertEqual(self.read(d['id'])['detail']['state'],'Confirmed')
  self.assertEqual(self.doc(dict(p,title='Collision')),dict(state='conflict'))
 def test_same_tenant_foreign_company_warehouse_site_and_tenant_refusals(self):
  self.prepare_documents();actor=self.actor;self.actor=self.owner_actor;other=self.create_company(self.tenant);other_site=self.create_site(self.tenant,other);other_warehouse=self.org_command(self.org_payload(kind='warehouse',tenantId=self.tenant,parentId=other_site,name='Foreign company warehouse'),self.tenant)['snapshot']['resourceId'];self.actor=actor
  d=self.doc(self.draft())['snapshot'];self.assertEqual(self.read(d['id'],company=other,site=other_site),dict(state='forbidden'))
  self.assertEqual(self.doc(self.draft(lines=[self.line(warehouse=other_warehouse)])),dict(state='forbidden'))
  self.assertEqual(self.doc(self.draft(legalEntityId=other,siteId=other_site)),dict(state='forbidden'))
  self.assertEqual(self.doc(self.draft(tenantId=self.tenant)),dict(state='invalid'))
  original=self.actor;self.actor=dict(internalIdentityId=uid(),issuer='https://foreign.test',subject='Foreign');self.assertEqual(self.doc(self.draft()),dict(state='forbidden'));self.actor=original
 def test_exact_scope_no_null_wildcard_supported_actions_only(self):
  self.prepare_documents()
  for action,c,s,w in [('documents.read',self.company,None,None),('documents.confirm',self.company,self.site,self.warehouse),('inventory.policy.manage',None,None,None),('inventory.policy.read',self.company,self.site,None),('inventory.document-effects.apply',self.company,self.site,None),('inventory.quantities.read',self.company,None,self.warehouse),('documents.*',self.company,self.site,None)]:
   r=self.role_command(self.role_payload('permission',label='Invalid',action=action,legalEntityId=c,siteId=s,warehouseId=w));self.assertIn(r['state'],('invalid','forbidden'))
 def test_quantity_precision_positive_and_storage_overflow_all_or_nothing(self):
  self.prepare_documents()
  for q in ('0','-1','1.0000001','1e2','1,5','01','NaN','Infinity','1000000000000000000','9'*1000):self.assertEqual(self.doc(self.draft(lines=[self.line(q,warehouse=self.warehouse)])),dict(state='invalid'),q)
  self.load('999999999999999999.999999');d=self.doc(self.draft(lines=[self.line('0.000001',warehouse=self.warehouse)]))['snapshot'];before=self.counts();self.assertEqual(self.doc(self.confirm(d)),dict(state='quantity_overflow'));self.assertEqual(self.counts(),before)
  aggregate=self.doc(self.draft(lines=[self.line('999999999999999999.999999',warehouse=self.destination),self.line('999999999999999999.999999',warehouse=self.destination)]))['snapshot'];before=self.counts();self.assertEqual(self.doc(self.confirm(aggregate)),dict(state='quantity_overflow'));self.assertEqual(self.counts(),before)
 def test_concurrent_discharge_multiline_aggregation_exact_retries(self):
  self.prepare_documents();self.load('3')
  docs=[self.doc(self.draft('Unload',lines=[self.line('1',warehouse=self.warehouse),self.line('1',warehouse=self.warehouse)]))['snapshot'] for _ in range(2)]
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.statement(self.confirm(d)),'app') for d in docs]);self.assertEqual(sorted(r['state'] for r in results),['applied','insufficient_stock']);self.assertEqual(self.balance(),'1.000000')
  p=self.draft();results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.statement(p),'app')]*4);self.assertEqual(sorted(r['state'] for r in results),['applied','replayed','replayed','replayed'])
 def test_opposing_transfers_deterministic_key_order_no_deadlock(self):
  self.prepare_documents();self.load('5');self.load('5',self.destination)
  docs=[self.doc(self.draft('Transfer',lines=[self.line('2',warehouse=a,destination=b)]))['snapshot'] for a,b in [(self.warehouse,self.destination),(self.destination,self.warehouse)]]
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.statement(self.confirm(d)),'app') for d in docs]);self.assertEqual([r['state'] for r in results],['applied','applied']);self.assertEqual(self.balance(),'5.000000');self.assertEqual(self.balance(self.destination),'5.000000')
 def test_policy_change_and_confirmation_have_one_physical_order(self):
  self.prepare_documents();d=self.doc(self.draft('Unload'))['snapshot'];confirm=self.confirm(d);p=self.policy(True)
  # Holder writes setting before blocked confirmation; expected version0 is stale.
  holder=self.statement(p);results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);'+holder,[(self.statement(confirm),'app')]);self.assertEqual(results[0]['state'],'config_changed');self.assertEqual(self.balance(),'0.000000')
 def test_current_assignment_role_permission_binding_and_enabled_before_replay(self):
  self.prepare_documents();p=self.draft();self.doc(p)
  for target in ('role','assignment','permission','binding','enabled'):
   if target=='role':sql=f'''UPDATE organization_access.tenant_role_objects SET "Data"="Data"||'{{"permissionIds":[]}}'::jsonb WHERE "Id"='{self.role_snapshot['resourceId']}' '''
   elif target=='assignment':sql=f'''UPDATE organization_access.tenant_role_objects SET "Data"="Data"||'{{"active":false}}'::jsonb WHERE "Id"='{self.assignment_snapshot['resourceId']}' '''
   elif target=='permission':sql=f'''UPDATE organization_access.tenant_role_objects SET "Data"="Data"-'siteId' WHERE "Id"='{next(s['resourceId'] for p,s in self.permissions if p['action']=='documents.read')}' '''
   elif target=='binding':sql=f'''UPDATE organization_access.external_identity_bindings SET "Subject"='Revoked' WHERE "InternalIdentityId"='{self.delegate['internalIdentityId']}' '''
   else:sql=f'''INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1)'''
   saved=self.sql("SELECT jsonb_build_object('roles',(SELECT jsonb_agg(to_jsonb(x)) FROM organization_access.tenant_role_objects x),'bindings',(SELECT jsonb_agg(to_jsonb(x)) FROM organization_access.external_identity_bindings x))")
   self.sql('BEGIN;'+sql+';COMMIT;');self.assertEqual(self.doc(p),dict(state='forbidden'),target)
   rows=json.loads(saved)
   for row in rows['roles']:self.sql('UPDATE organization_access.tenant_role_objects SET "Data"='+lit(json.dumps(row['Data']))+'::jsonb WHERE "Id"='+lit(row['Id']))
   for row in rows['bindings']:self.sql('UPDATE organization_access.external_identity_bindings SET "Subject"='+lit(row['Subject'])+' WHERE "InternalIdentityId"='+lit(row['InternalIdentityId']))
   if target=='enabled':self.sql('DELETE FROM organization_access.membership_access_state')
   self.assertEqual(self.doc(p)['state'],'replayed')
 def test_insert_and_deferred_failure_roll_back_each_owned_confirmation_fact(self):
  self.prepare_documents();self.load('5');d=self.doc(self.draft('Transfer'))['snapshot'];p=self.confirm(d);before=self.counts()
  self.sql("CREATE FUNCTION documents.fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic owned fact failure'; END $$")
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  for table,event in [('headers','UPDATE'),('balances','UPDATE'),('ledger','INSERT'),('versions','INSERT'),('command_audit','INSERT'),('snapshot_fence','UPDATE')]:
   for deferred in (False,True):
    create=('CREATE CONSTRAINT TRIGGER fixture_fail AFTER ' if deferred else 'CREATE TRIGGER fixture_fail BEFORE ')+event+' ON documents.'+table+(' DEFERRABLE INITIALLY DEFERRED' if deferred else '')+' FOR EACH ROW EXECUTE FUNCTION documents.fixture_fail()'
    self.sql(create)
    try:
     r=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.statement(p)+'COMMIT;',env=env,capture_output=True,text=True,timeout=20);self.assertNotEqual(r.returncode,0);self.assertIn('synthetic owned fact failure',r.stderr);self.assertEqual(self.counts(),before)
    finally:self.sql('DROP TRIGGER fixture_fail ON documents.'+table)
  self.assertEqual(self.doc(p)['state'],'applied')
 def test_draft_and_policy_audit_failure_and_confirmed_immutability_acl(self):
  self.prepare_documents();before=self.counts();self.sql("CREATE FUNCTION documents.fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic audit failure'; END $$;CREATE TRIGGER fixture_fail BEFORE INSERT ON documents.command_audit FOR EACH ROW EXECUTE FUNCTION documents.fixture_fail()")
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  try:
   for p in (self.draft(),self.policy(True)):
    r=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.statement(p)+'COMMIT;',env=env,capture_output=True,text=True,timeout=20);self.assertNotEqual(r.returncode,0);self.assertEqual(self.counts(),before)
  finally:self.sql('DROP TRIGGER fixture_fail ON documents.command_audit')
  d=self.load()
  for table in ('headers','lines','versions','policy_versions','balances','ledger','command_audit','snapshot_fence'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','documents.{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
  for table in ('headers','lines','versions','ledger','command_audit'):
   self.assertNotEqual(self.owner_sql('BEGIN;SELECT set_config(\'app.tenant_id\','+lit(self.tenant)+',true),set_config(\'app.legal_entity_id\','+lit(self.company)+',true);UPDATE documents.'+table+' SET "TenantId"="TenantId";COMMIT;',ok=False).returncode,0)
 def test_search_and_selector_paging_keep_canonical_ids(self):
  self.prepare_documents()
  for i in range(23):self.doc(self.draft(title='Page '+str(i)))
  first=self.read(search='PAGE');self.assertEqual(len(first['items']),21);second=self.read(search='Page',after=first['items'][19]['id']);self.assertEqual(len(second['items']),3);self.assertEqual(self.read(search='%')['items'],[])
  choices=self.read(selection='catalog')['catalog'];self.assertEqual({x['id'] for x in choices},{self.part,self.service});self.assertEqual({x['kind'] for x in choices},{'Article','Service'})
  part_ids=[uid() for _ in range(26)];type_ids=[uid() for _ in range(26)]
  parts=','.join('('+','.join(map(lit,[id,self.tenant,self.company,'Part','Page item '+str(i)]))+',1)' for i,id in enumerate(part_ids))
  definitions=','.join('('+','.join(map(lit,[id,self.tenant,self.company]))+',1)' for id in type_ids)
  versions=','.join('('+','.join(map(lit,[self.tenant,self.company,id]))+",1,"+lit('Page type '+str(i))+",'None')" for i,id in enumerate(type_ids))
  self.sql('BEGIN;INSERT INTO catalog.items VALUES '+parts+';INSERT INTO document_types.definitions VALUES '+definitions+';INSERT INTO document_types.versions("TenantId","LegalEntityId","DocumentTypeId","Revision","Label","Effect") VALUES '+versions+';COMMIT;')
  for selection,needle,ids,key in [('catalog','Page item',part_ids,'catalog'),('types','Page type',type_ids,'types')]:
   first=self.read(selection=selection,search=needle)[key];self.assertEqual(len(first),21)
   second=self.read(selection=selection,search=needle,selection_after=first[19]['id'])[key]
   self.assertEqual({r['id'] for r in first[:20]+second},set(ids));self.assertEqual(len(first[:20]+second),len(ids));self.assertEqual(self.read(selection=selection,search='%')[key],[])
  draft=self.doc(self.draft(lines=[self.line(item=id,warehouse=self.warehouse) for id in part_ids]))['snapshot'];self.assertEqual(self.read(warehouse=self.warehouse)['balances'],[])
  confirmed=self.doc(self.confirm(draft))['snapshot'];self.assertEqual(len(confirmed['lines']),len(part_ids))
  first=self.read(warehouse=self.warehouse);second=self.read(warehouse=self.warehouse,after=first['balances'][19]['itemId']);self.assertEqual({r['itemId'] for r in first['balances'][:20]+second['balances']},set(part_ids))
  movements=self.read(warehouse=self.warehouse,ledger_after=first['ledger'][19]['id'])['ledger'];self.assertEqual({r['lineId'] for r in first['ledger'][:20]+movements},{l['id'] for l in confirmed['lines']});self.assertTrue(all(r['documentId']==confirmed['id'] for r in first['ledger'][:20]+movements))
  # Warehouse quantity cursors never truncate the separate document list.
  self.assertEqual([d['id'] for d in first['items']],[d['id'] for d in second['items']])
  for i in range(23):self.assertEqual(self.doc(self.policy(i%2==0))['state'],'applied')
  history=self.read()['policyHistory'];self.assertEqual(len(history),20);self.assertEqual([v['revision'] for v in history],list(range(23,23-len(history),-1)))

 def test_physical_confirmation_and_revocation_both_orders_each_current_origin(self):
  self.prepare_documents();self.load('20')
  role_id=self.role_snapshot['resourceId'];assignment_id=self.assignment_snapshot['resourceId']
  permission_id=next(s['resourceId'] for p,s in self.permissions if p['action']=='inventory.document-effects.apply' and p['warehouseId']==self.warehouse)
  identity=self.actor['internalIdentityId'];subject=self.actor['subject']
  cases=[
   (f"UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"||'{{\"permissionIds\":[]}}'::jsonb WHERE \"Id\"='{role_id}';",lambda:f"UPDATE organization_access.tenant_role_objects SET \"Data\"="+lit(json.dumps(self.role_snapshot))+f"::jsonb WHERE \"Id\"='{role_id}';"),
   (f"UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"||'{{\"active\":false}}'::jsonb WHERE \"Id\"='{assignment_id}';",lambda:f"UPDATE organization_access.tenant_role_objects SET \"Data\"="+lit(json.dumps(self.assignment_snapshot))+f"::jsonb WHERE \"Id\"='{assignment_id}';"),
   (f"UPDATE organization_access.tenant_role_objects SET \"Data\"=\"Data\"-'warehouseId' WHERE \"Id\"='{permission_id}';",lambda:f"UPDATE organization_access.tenant_role_objects SET \"Data\"="+lit(json.dumps(next(s for p,s in self.permissions if s['resourceId']==permission_id)))+f"::jsonb WHERE \"Id\"='{permission_id}';"),
   (f"UPDATE organization_access.external_identity_bindings SET \"Subject\"='Revoked binding' WHERE \"InternalIdentityId\"='{identity}';",lambda:'UPDATE organization_access.external_identity_bindings SET "Subject"='+lit(subject)+f' WHERE "InternalIdentityId"=\'{identity}\';'),
   (f"INSERT INTO organization_access.membership_access_state VALUES('{self.member}','{self.tenant}',false,1) ON CONFLICT(\"MembershipId\") DO UPDATE SET \"Enabled\"=false,\"Revision\"=organization_access.membership_access_state.\"Revision\"+1;",lambda:f"UPDATE organization_access.membership_access_state SET \"Enabled\"=true,\"Revision\"=\"Revision\"+1 WHERE \"MembershipId\"='{self.member}';")]
  for revoke,restore in cases:
   draft=self.doc(self.draft('Unload'))['snapshot'];p=self.confirm(draft);before=self.balance()
   revocation="SELECT pg_advisory_xact_lock(777036);"+revoke+"SELECT jsonb_build_object('state','revoked');"
   results,held=self.barrier_race(revocation,[(self.statement(p),'app')],holder_role='infra');self.assertEqual(held[-1],dict(state='revoked'));self.assertEqual(results,[dict(state='forbidden')])
   self.sql(restore());self.assertEqual(self.balance(),before)
   results,held=self.barrier_race(self.statement(p),[(revocation,'infra')],holder_role='app');self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results,[dict(state='revoked')]);self.assertEqual(self.doc(p),dict(state='forbidden'))
   self.sql(restore());self.assertEqual(self.doc(p)['state'],'replayed')
  self.assertEqual(self.balance(),'15.000000')
 def test_old_rr_snapshot_refuses_revoked_grant_and_absent_policy_after_change(self):
  self.prepare_documents();d=self.doc(self.draft())['snapshot'];p=self.confirm(d)
  import selectors
  for policy_change in (True,False):
   env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
   child=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,text=True)
   try:
    child.stdin.write("BEGIN ISOLATION LEVEL REPEATABLE READ;SELECT 'SNAPSHOT_READY',count(*) FROM pg_catalog.pg_class;\n");child.stdin.flush()
    poll=selectors.DefaultSelector();poll.register(child.stdout,selectors.EVENT_READ)
    try:self.assertTrue(poll.select(10));self.assertTrue(child.stdout.readline().startswith('SNAPSHOT_READY|'))
    finally:poll.close()
    if policy_change:self.assertEqual(self.doc(self.policy(True))['state'],'applied')
    else:self.role_command(dict(self.role_request,commandId=uid(),resourceId=self.role_snapshot['resourceId'],expectedRevision=1,permissionIds=[]))
    child.stdin.write(self.statement(p)+'COMMIT;\n');child.stdin.flush();child.stdin.close();child.stdin=None
    output,error=child.communicate(timeout=20);self.assertNotEqual(child.returncode,0);self.assertIn('could not serialize',error)
   finally:
    if child.poll() is None:child.kill();child.communicate(timeout=5)
  self.assertEqual(self.sql('SELECT count(*) FROM documents.ledger'),'0')
 def test_two_authorized_companies_have_independent_policy_defaults_and_versions(self):
  self.prepare_documents();self.assertEqual(self.doc(self.policy(True))['state'],'applied')
  actor=self.actor;self.actor=self.owner_actor;other=self.create_company(self.tenant);self.actor=actor
  ids=[s['resourceId'] for _,s in self.permissions]
  for action in ('inventory.policy.read','inventory.policy.manage'):
   r=self.role_command(self.role_payload('permission',label=action,action=action,legalEntityId=other,siteId=None,warehouseId=None));self.assertEqual(r['state'],'applied');ids.append(r['snapshot']['resourceId'])
  self.role_command(dict(self.role_request,commandId=uid(),resourceId=self.role_snapshot['resourceId'],expectedRevision=1,permissionIds=ids))
  def company_read(company):return self.app_result('SELECT documents.read('+lit(company)+'::uuid,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)')
  self.assertEqual(company_read(other)['policy'],dict(revision=0,allowNegative=False,occurredAt=None));self.assertTrue(company_read(self.company)['policy']['allowNegative'])
  p=dict(commandId=uid(),operation='policy',legalEntityId=other,expectedRevision=0,allowNegative=False);self.assertEqual(self.doc(p)['state'],'applied');self.assertEqual(company_read(other)['policy']['revision'],1);self.assertTrue(company_read(self.company)['policy']['allowNegative'])
  self.assertEqual(self.doc(dict(p,legalEntityId=self.company)),dict(state='conflict'))
 def test_draft_lines_and_policy_insert_deferred_failures_rollback_the_entire_command(self):
  self.prepare_documents();self.sql("CREATE FUNCTION documents.fixture_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic deferred fact failure'; END $$")
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  d=self.doc(self.draft())['snapshot'];save=self.draft(operation='save',documentId=d['id'],expectedRevision=1,title='Must rollback')
  cases=[('lines',self.draft(),'INSERT'),('headers',self.draft(),'INSERT'),('versions',self.draft(),'INSERT'),('command_audit',self.draft(),'INSERT'),('lines',save,'INSERT'),('headers',save,'UPDATE'),('versions',save,'INSERT'),('command_audit',save,'INSERT'),('snapshot_fence',save,'UPDATE'),('policy_versions',self.policy(True),'INSERT'),('command_audit',self.policy(True),'INSERT'),('snapshot_fence',self.policy(True),'UPDATE')]
  for table,p,event in cases:
   for deferred in (False,True):
    before=self.counts();self.sql(('CREATE CONSTRAINT TRIGGER fixture_fail AFTER ' if deferred else 'CREATE TRIGGER fixture_fail BEFORE ')+event+' ON documents.'+table+(' DEFERRABLE INITIALLY DEFERRED' if deferred else '')+' FOR EACH ROW EXECUTE FUNCTION documents.fixture_fail()')
    try:
     r=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.statement(p)+'COMMIT;',env=env,capture_output=True,text=True,timeout=20);self.assertNotEqual(r.returncode,0);self.assertIn('synthetic deferred fact failure',r.stderr);self.assertEqual(self.counts(),before)
    finally:self.sql('DROP TRIGGER fixture_fail ON documents.'+table)
 def test_closed_line_shapes_unicode_and_confirmed_service_without_stock_permission(self):
  self.prepare_documents()
  for value in (None,True,1,'bad',[],{}):self.assertEqual(self.doc(self.draft(lines=[value])),dict(state='invalid'))
  for quantity in ('1','1.0','1.000000'):
   r=self.doc(self.draft(title='😀'*100,lines=[self.line(quantity,item=self.service)]));self.assertEqual(r['state'],'applied');self.assertEqual(self.doc(self.confirm(r['snapshot']))['state'],'applied')
  self.assertEqual(self.sql('SELECT count(*) FROM documents.balances'),'0');self.assertEqual(self.sql('SELECT count(*) FROM documents.ledger'),'0')
  d=self.doc(self.draft(lines=[self.line(item=self.service)]))['snapshot'];ids=[s['resourceId'] for p,s in self.permissions if p['action']!='inventory.document-effects.apply']
  self.role_command(dict(self.role_request,commandId=uid(),resourceId=self.role_snapshot['resourceId'],expectedRevision=1,permissionIds=ids));self.assertEqual(self.doc(self.confirm(d))['state'],'applied')
 def test_allow_negative_transfer_and_policy_change_after_effect_keep_applied_version(self):
  self.prepare_documents();self.load('2');self.assertEqual(self.doc(self.policy(True))['state'],'applied')
  draft=self.doc(self.draft('Transfer',lines=[self.line('3',warehouse=self.warehouse,destination=self.destination)]))['snapshot'];confirm=self.confirm(draft);block=self.policy(False)
  results,held=self.barrier_race(self.statement(confirm),[(self.statement(block),'app')],holder_role='app')
  self.assertEqual(held[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied')
  self.assertEqual(self.balance(),'-1.000000');self.assertEqual(self.balance(self.destination),'3.000000')
  current=self.read(draft['id']);self.assertFalse(current['policy']['allowNegative']);self.assertEqual(current['policy']['revision'],2)
  applied=current['detail']['appliedConfiguration'];self.assertEqual(applied['policy']['revision'],1);self.assertTrue(applied['policy']['allowNegative']);self.assertEqual(len(current['ledger']),2)
  self.assertEqual(self.doc(confirm)['state'],'replayed')
 def test_authorized_foreign_tenant_writer_cannot_read_master_stock_or_replay_original(self):
  self.prepare_documents();original=self.draft();snapshot=self.doc(original)['snapshot'];actor=self.actor
  tenant,company,site,warehouse,identity,member,role,assignment,item,type_id=[uid() for _ in range(10)]
  self.sql(f"""INSERT INTO organization_access.tenants VALUES('{tenant}','Synthetic foreign tenant');
   INSERT INTO organization_access.legal_entities VALUES('{company}','{tenant}','Foreign company');
   INSERT INTO organization_access.sites VALUES('{site}','{company}','{tenant}','Foreign site');
   INSERT INTO organization_access.warehouses VALUES('{warehouse}','{site}','{company}','{tenant}','Foreign warehouse');
   INSERT INTO organization_access.external_identity_bindings VALUES('{identity}','https://foreign.test','opaque');
   INSERT INTO organization_access.memberships VALUES('{member}','{tenant}','{identity}');
   INSERT INTO catalog.items VALUES('{item}','{tenant}','{company}','Part','Foreign canonical article',1);
   BEGIN;INSERT INTO document_types.definitions VALUES('{type_id}','{tenant}','{company}',1);
   INSERT INTO document_types.versions(\"TenantId\",\"LegalEntityId\",\"DocumentTypeId\",\"Revision\",\"Label\",\"Effect\") VALUES('{tenant}','{company}','{type_id}',1,'Foreign Load','Load');COMMIT;
   INSERT INTO organization_access.tenant_role_objects SELECT gen_random_uuid(),'{tenant}','permission',jsonb_build_object('action',a,'legalEntityId','{company}','siteId','{site}','warehouseId',NULL),1 FROM unnest(ARRAY['documents.read','documents.save','documents.confirm']) a;
   INSERT INTO organization_access.tenant_role_objects SELECT gen_random_uuid(),'{tenant}','permission',jsonb_build_object('action',a,'legalEntityId','{company}','siteId','{site}','warehouseId','{warehouse}'),1 FROM unnest(ARRAY['inventory.document-effects.apply','inventory.quantities.read']) a;
   INSERT INTO organization_access.tenant_role_objects VALUES('{role}','{tenant}','role',jsonb_build_object('permissionIds',(SELECT jsonb_agg(\"Id\"::text) FROM organization_access.tenant_role_objects WHERE \"TenantId\"='{tenant}' AND \"Kind\"='permission')),1);
   INSERT INTO organization_access.tenant_role_objects VALUES('{assignment}','{tenant}','assignment',jsonb_build_object('membershipId','{member}','internalIdentityId','{identity}','active',true,'roleId','{role}','bindingHash',encode(sha256(convert_to(jsonb_build_array('https://foreign.test','opaque')::text,'UTF8')),'hex')),1);""")
  self.actor=dict(internalIdentityId=identity,issuer='https://foreign.test',subject='opaque')
  self.assertEqual(self.read(snapshot['id']),dict(state='forbidden'));self.assertEqual(self.read(snapshot['id'],company=company,site=site),dict(state='not_found'))
  foreign=dict(original,legalEntityId=company,siteId=site,documentTypeId=type_id,lines=[self.line(item=item,warehouse=warehouse)])
  self.assertEqual(self.doc(foreign),dict(state='conflict'))
  foreign['commandId']=uid();foreign_snapshot=self.doc(foreign)['snapshot']
  self.assertEqual(self.doc(dict(commandId=uid(),operation='confirm',legalEntityId=company,siteId=site,documentId=foreign_snapshot['id'],expectedRevision=1,expectedTypeRevision=1,expectedPolicyRevision=0))['state'],'applied')
  self.assertEqual(self.read(company=company,site=site,warehouse=warehouse)['balances'][0]['quantity'],'1.000000')
  foreign.update(commandId=uid(),lines=[self.line(item=self.part,warehouse=warehouse)])
  self.assertEqual(self.doc(foreign),dict(state='catalog_changed'))
  self.actor=actor;self.assertEqual(self.balance(),'0.000000');self.assertEqual(self.read(snapshot['id'])['detail'],snapshot)
 def test_authorized_same_tenant_companies_share_catalog_not_stock_type_or_warehouse_scope(self):
  self.prepare_documents();original=self.draft();original_snapshot=self.doc(original)['snapshot'];actor=self.actor;self.actor=self.owner_actor
  company=self.create_company(self.tenant);site=self.create_site(self.tenant,company);warehouse=self.org_command(self.org_payload(kind='warehouse',tenantId=self.tenant,parentId=site,name='Second company warehouse'),self.tenant)['snapshot']['resourceId'];self.actor=actor
  ids=[s['resourceId'] for _,s in self.permissions]
  actions=[(a,site,None) for a in ('documents.read','documents.save','documents.confirm')]+[(a,site,warehouse) for a in ('inventory.document-effects.apply','inventory.quantities.read')]+[(a,None,None) for a in ('document-types.read','document-types.create')]
  for action,s,w in actions:
   r=self.role_command(self.role_payload('permission',label=action,action=action,legalEntityId=company,siteId=s,warehouseId=w));self.assertEqual(r['state'],'applied');ids.append(r['snapshot']['resourceId'])
  self.role_command(dict(self.role_request,commandId=uid(),resourceId=self.role_snapshot['resourceId'],expectedRevision=1,permissionIds=ids))
  type_request=dict(commandId=uid(),operation='create',legalEntityId=company,documentTypeId=None,expectedRevision=0,label='Independent Load',effect='Load')
  type_snapshot=self.app_result('SELECT document_types.command('+lit(json.dumps(type_request))+'::jsonb)')['snapshot']
  self.assertEqual(self.read(original_snapshot['id'],company=company,site=site),dict(state='not_found'))
  wrong_type=self.draft(legalEntityId=company,siteId=site,lines=[self.line(warehouse=warehouse)])
  self.assertEqual(self.doc(wrong_type),dict(state='not_found'))
  payload=dict(wrong_type,commandId=original['commandId'],documentTypeId=type_snapshot['id']);self.assertEqual(self.doc(payload),dict(state='conflict'))
  payload['commandId']=uid();payload['lines']=[self.line('7',warehouse=warehouse)];snapshot=self.doc(payload)['snapshot']
  confirm=dict(commandId=uid(),operation='confirm',legalEntityId=company,siteId=site,documentId=snapshot['id'],expectedRevision=1,expectedTypeRevision=1,expectedPolicyRevision=0)
  self.assertEqual(self.doc(confirm)['state'],'applied');self.assertEqual(self.balance(),'0.000000');self.assertEqual(self.read(company=company,site=site,warehouse=warehouse)['balances'][0]['quantity'],'7.000000')
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.items'),'2','no duplicate canonical identity for second-company stock')
  forbidden=dict(payload,commandId=uid(),lines=[self.line(warehouse=self.warehouse)])
  self.assertEqual(self.doc(forbidden),dict(state='forbidden'));self.assertEqual(self.doc(self.policy(True)|dict(legalEntityId=company)),dict(state='forbidden'))
 def test_every_transfer_leg_current_grant_and_quantity_only_provenance_boundary(self):
  self.prepare_documents();opening=self.load('4');draft=self.doc(self.draft('Transfer'))['snapshot'];confirm=self.confirm(draft)
  all_ids=[s['resourceId'] for _,s in self.permissions];revision=1
  for warehouse in (self.warehouse,self.destination):
   excluded=next(s['resourceId'] for p,s in self.permissions if p['action']=='inventory.document-effects.apply' and p['warehouseId']==warehouse)
   update=dict(self.role_request,commandId=uid(),resourceId=self.role_snapshot['resourceId'],expectedRevision=revision,permissionIds=[id for id in all_ids if id!=excluded])
   self.assertEqual(self.role_command(update)['state'],'applied');revision+=1;before=self.counts()
   self.assertEqual(self.doc(confirm),dict(state='forbidden'));self.assertEqual(self.counts(),before)
   self.assertEqual(self.doc(self.draft('Transfer'))['state'],'forbidden')
  self.assertEqual(self.role_command(dict(self.role_request,commandId=uid(),resourceId=self.role_snapshot['resourceId'],expectedRevision=revision,permissionIds=all_ids))['state'],'applied');revision+=1
  self.assertEqual(self.doc(confirm)['state'],'applied')
  excluded=next(s['resourceId'] for p,s in self.permissions if p['action']=='documents.read')
  self.assertEqual(self.role_command(dict(self.role_request,commandId=uid(),resourceId=self.role_snapshot['resourceId'],expectedRevision=revision,permissionIds=[id for id in all_ids if id!=excluded]))['state'],'applied')
  stock=self.read(warehouse=self.warehouse);self.assertEqual(stock['state'],'ready');self.assertEqual(stock['balances'][0]['quantity'],'3.000000')
  self.assertEqual(stock['items'],[]);self.assertIsNone(stock['detail']);self.assertEqual(stock['catalog'],[]);self.assertEqual(stock['types'],[])
  self.assertTrue(stock['ledger']);self.assertTrue(all(row['canReadDocument'] is False for row in stock['ledger']))
  self.assertEqual(self.read(opening['id']),dict(state='forbidden'));self.assertEqual(self.read(draft['id'],warehouse=self.warehouse),dict(state='forbidden'))
 def test_owner_cannot_add_or_move_draft_lines_into_a_confirmed_document(self):
  self.prepare_documents();confirmed=self.load('2');draft=self.doc(self.draft())['snapshot']
  context="BEGIN;SELECT set_config('app.tenant_id',"+lit(self.tenant)+",true),set_config('app.legal_entity_id',"+lit(self.company)+",true);"
  for statement in [
   'UPDATE documents.lines SET "DocumentId"='+lit(confirmed['id'])+',"Position"=199 WHERE "DocumentId"='+lit(draft['id']),
   'INSERT INTO documents.lines SELECT "TenantId","LegalEntityId",'+lit(confirmed['id'])+'::uuid,"Id",199,"CatalogItemId","CatalogVersion","Kind","Label","Quantity","WarehouseId","DestinationWarehouseId" FROM documents.lines WHERE "DocumentId"='+lit(draft['id'])]:
   result=self.owner_sql(context+statement+';COMMIT;',ok=False);self.assertNotEqual(result.returncode,0);self.assertIn('confirmed line immutable',result.stderr)
  self.assertEqual(self.read(confirmed['id'])['detail'],confirmed);self.assertEqual(self.balance(),'2.000000')
if __name__=='__main__':unittest.main()
