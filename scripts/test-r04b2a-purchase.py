#!/usr/bin/env python3
"""Synthetic owning-contract PostgreSQL proofs, opt-in ephemeral only."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('supplier',ROOT/'scripts/test-r04b1-supplier.py')
assert spec and spec.loader
supplier=importlib.util.module_from_spec(spec);spec.loader.exec_module(supplier)
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated PostgreSQL required')
class PurchaseSqlTests(supplier.SupplierSqlTests):
 def test_chooser_projects_only_current_company_mapped_suppliers(self):
  self.assertEqual(self.migrate()[0],0)
  ids=self.world()
  self.assertEqual(self.sql(self.app_prefix(ids)+self.role(ids,1,0)+'COMMIT;',app=True).splitlines()[-1],'applied')
  self.assertEqual(self.sql(self.vendor(ids)).splitlines()[-1],'applied')
  exists=self.sql("SELECT to_regprocedure('counterparties.purchase_suppliers(uuid)') IS NOT NULL")
  self.assertEqual(exists,'t','purchase supplier chooser contract absent')
  c=ids['companies'][0]
  value=json.loads(self.sql(self.app_prefix(ids,c)+f"SELECT counterparties.purchase_suppliers('{c}')::text; COMMIT;",app=True).splitlines()[-1])
  self.assertEqual(value['suppliers'],[{'id':ids['record'],'name':'Supplier candidate','revision':1,'mappingRevision':1}])
 def chooser(self,ids,company=None,subject=None):
  c=company or ids['companies'][0]
  return json.loads(self.sql(self.app_prefix(ids,c,subject)+f"SELECT counterparties.purchase_suppliers('{c}')::text; COMMIT;",app=True).splitlines()[-1])
 def test_chooser_needs_exact_company_read_and_local_master_authority(self):
  self.assertEqual(self.migrate()[0],0)
  ids=self.world(local=False);c=ids['companies'][0]
  states=[self.chooser(ids)['state']]
  self.authority(ids,0,'Enginia360ToExternal')
  states.append(self.chooser(ids,subject=str(__import__('uuid').uuid4()))['state'])
  self.sql(f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{ids['member']}' AND "LegalEntityId"='{c}';''')
  states.append(self.chooser(ids)['state'])
  self.authority(ids,1,'ExternalToEnginia360')
  states.append(self.chooser(ids,company=ids['companies'][1])['state'])
  self.assertEqual(states,['master_missing','forbidden','forbidden','master_external'])
 def purchase_world(self):
  ids=self.world();ids.update({k:str(uuid.uuid4()) for k in ('site','warehouse','order','line','group','document','catalog','stockSource','stockProfile')})
  c=ids['companies'][0];t=ids['tenant'];s=ids['site'];w=ids['warehouse'];o=ids['order'];g=ids['group'];m=ids['member'];r=ids['record']
  self.sql(f'''INSERT INTO organization_access.sites VALUES ('{s}','{c}','{t}','Site');
   INSERT INTO organization_access.warehouses VALUES ('{w}','{s}','{c}','{t}','Warehouse');
   INSERT INTO organization_access.capability_activations VALUES ('{c}','inventory',true),('{c}','workshop',true);
   INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{m}','{t}','{c}','workshop.orders.read',NULL,NULL),('{uuid.uuid4()}','{m}','{t}','{c}','inventory.purchase-intents.create','{s}','{w}');
   INSERT INTO workshop.document_types VALUES ('{ids['document']}','{t}','{c}',7,'Synthetic',true);
   INSERT INTO workshop.orders("Id","TenantId","LegalEntityId","SiteId","DocumentTypeId","ConfigurationVersion","PayerId","VehicleId","VehicleHolderId","CreatedByMembershipId") VALUES ('{o}','{t}','{c}','{s}','{ids['document']}',7,'{r}','{r}','{r}','{m}');
   INSERT INTO workshop.working_groups VALUES ('{g}','{t}','{o}','Group','Active',1,0);
   INSERT INTO workshop.commercial_lines("Id","TenantId","OrderId","CatalogItemId","CatalogVersion","CatalogLabel","Kind","Quantity","UnitPrice","DiscountPercent","NetAmount","TaxRate","PayerId","WorkingGroupId","ConfigurationVersion","ExpectedRevision") VALUES ('{ids['line']}','{t}','{o}','{ids['catalog']}',8,'Part','Part',3,1,0,3,22,'{r}','{g}',9,0);''')
  self.assertEqual(self.sql(self.app_prefix(ids)+self.role(ids,1,0)+'COMMIT;',app=True).splitlines()[-1],'applied')
  self.assertEqual(self.sql(self.vendor(ids)).splitlines()[-1],'applied')
  self.sql(f"SET ROLE {self.owner}; BEGIN; SELECT set_config('app.tenant_id','{t}',true); SELECT organization_access.establish_stock_profile('{uuid.uuid4()}','{t}','{c}','{m}','{ids['proof']}','ExternalToEnginia360','{ids['stockSource']}','{ids['stockProfile']}'); COMMIT;")
  return ids
 def good_destination(self,ids):
  return dict(kind='GiobbyPurchaseV1',version=1,fingerprint='a'*64,tenantId=ids['tenant'],legalEntityId=ids['companies'][0],siteId=ids['site'],stockSourceId=ids['stockSource'],stockProfileId=ids['stockProfile'])
 def purchase_sql(self,ids,command=None,quantity='2',**changes):
  a=dict(command=str(command or uuid.uuid4()),order=ids['order'],line=ids['line'],warehouse=ids['warehouse'],supplier=ids['record'],revision=1,roleRevision=1,mappingRevision=1,quantity=quantity)
  a.update(changes)
  destination=json.dumps(a.get('destination',self.good_destination(ids)))
  return f"SELECT inventory.create_purchase_intent('{a['command']}','{a['order']}','{a['line']}','{a['warehouse']}','{a['supplier']}',{a['revision']},{a['roleRevision']},{a['mappingRevision']},'{a['quantity']}','{destination}'::jsonb)::text;"
 def purchase(self,ids,**changes):
  return json.loads(self.sql(self.app_prefix(ids,ids['companies'][0])+self.purchase_sql(ids,**changes)+'COMMIT;',app=True).splitlines()[-1])
 def test_manual_intent_freezes_source_vendor_destination_and_held_outbox(self):
  self.assertEqual(self.migrate()[0],0)
  ids=self.purchase_world()
  self.assertEqual(self.sql("SELECT to_regprocedure('inventory.create_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,jsonb)') IS NOT NULL"),'t','manual intent command absent')
  command=str(uuid.uuid4());got=self.purchase(ids,command=command)
  self.assertEqual((got['state'],got['id'],got['status']),('applied',command,'Held'))
  row=json.loads(self.sql(f'''SELECT jsonb_build_object('source',"Source",'supplier',"Supplier",'destination',"Destination",'quantity',"Quantity"::text) FROM inventory.purchase_intents WHERE "Id"='{command}';'''))
  self.assertEqual(row['quantity'],'2.000000');self.assertEqual(row['source']['lineId'],ids['line']);self.assertEqual(row['source']['revision'],1)
  self.assertEqual(row['supplier']['vendorId'],'4711');self.assertEqual(row['supplier']['vendorName'],'Synthetic Supplier S.r.l.')
  self.assertEqual(row['destination']['fingerprint'],'a'*64)
  self.assertEqual(self.sql(f'''SELECT "State" FROM inventory.purchase_intent_outbox WHERE "IntentId"='{command}';'''),'Held')
 def test_exact_action_is_not_read_common_site_warehouse_or_other_scope(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world()
  t,c,s,w,m=[ids[k] if k!='companies' else ids[k][0] for k in ('tenant','companies','site','warehouse','member')]
  base=f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{m}' AND "Permission"='inventory.purchase-intents.create';'''
  for label,site,warehouse in [('absent',None,None),('company',None,None),('site',s,None),('warehouse',None,w),('wrong-site',str(uuid.uuid4()),w),('wrong-warehouse',s,str(uuid.uuid4()))]:
   with self.subTest(scope=label):
    statement=base
    if label!='absent':
     sv="NULL" if site is None else "'"+site+"'";wv="NULL" if warehouse is None else "'"+warehouse+"'"
     statement+=f"INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{m}','{t}','{c}','inventory.purchase-intents.create',{sv},{wv});"
    self.sql(statement)
    self.assertEqual(self.purchase(ids,quantity='0.000001')['state'],'forbidden')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_dependent_inventory_capability_is_required(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world()
  self.sql(f'''UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "LegalEntityId"='{ids['companies'][0]}' AND "Capability"='inventory';''')
  self.assertEqual(self.purchase(ids)['state'],'forbidden')
 def test_cumulative_line_cap_across_new_uuids(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world()
  self.assertEqual(self.purchase(ids)['state'],'applied')
  self.assertEqual(self.purchase(ids)['state'],'exceeds_remaining','new UUID must not reset pending2 of source3')
  self.assertEqual(self.purchase(ids,quantity='1')['state'],'applied')
  self.assertEqual(self.sql('SELECT sum("Quantity") FROM inventory.purchase_intents'),'3.000000')
 def process(self,ids,sql,app=True):
  env=dict(os.environ,PGDATABASE=self.database,PGAPPNAME='r04b2a-proof')
  if app:env.update(PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  p=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
  self.addCleanup(lambda: (p.kill(),p.communicate()) if p.poll() is None else None)
  p.stdin.write(sql+'\n');p.stdin.flush();return p
 def finish(self,p):
  p.stdin.close();p.stdin=None
  out,err=p.communicate(timeout=15);self.assertEqual(p.returncode,0,err);return (out.strip().splitlines() or [''])[-1]
 def waiters(self,controller,required):
  deadline=time.monotonic()+4
  while time.monotonic()<deadline:
   value=self.sql(f"WITH RECURSIVE chain(pid,blocker) AS (SELECT pid,unnest(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE datname=current_database() UNION SELECT chain.pid,unnest(pg_blocking_pids(chain.blocker)) FROM chain) SELECT count(DISTINCT pid) FROM chain WHERE blocker={controller}")
   if int(value)>=required:
    print('PHYSICAL_BARRIER',controller,self.sql("SELECT pid||':'||pg_blocking_pids(pid)::text FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid))>0"),flush=True);return
   time.sleep(.03)
  self.fail('expected physical connections did not wait on canonical line budget lock')
 def test_concurrent_remaining_one_is_shared_across_supplier_and_warehouse(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world();self.purchase(ids)
  second=str(uuid.uuid4());t,c,s,m=[ids[k] if k!='companies' else ids[k][0] for k in ('tenant','companies','site','member')]
  self.sql(f"INSERT INTO organization_access.warehouses VALUES ('{second}','{s}','{c}','{t}','Second'); INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{m}','{t}','{c}','inventory.purchase-intents.create','{s}','{second}');")
  self.sql(self.app_prefix(ids)+self.role(ids,1,0,record=ids['other_record'])+'COMMIT;',app=True)
  self.sql(self.vendor(ids,record=ids['other_record'],vendor_id='V2'))
  holder=self.process(ids,f"BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('inventory:line:{t}:{ids['line']}',0)); SELECT pg_backend_pid();",app=False)
  holder.stdout.readline();pid=int(holder.stdout.readline())
  a=self.process(ids,self.app_prefix(ids,c)+self.purchase_sql(ids,quantity='1')+'COMMIT;')
  b=self.process(ids,self.app_prefix(ids,c)+self.purchase_sql(ids,quantity='1',supplier=ids['other_record'],warehouse=second)+'COMMIT;')
  self.waiters(pid,2)
  holder.stdin.write('ROLLBACK;\n');holder.stdin.flush();self.finish(holder)
  states=sorted(json.loads(self.finish(p))['state'] for p in (a,b))
  self.assertEqual(states,['applied','exceeds_remaining'])
  self.assertEqual(self.sql('SELECT sum("Quantity") FROM inventory.purchase_intents'),'3.000000')
 def test_identical_uuid_replays_without_quantity_and_changed_payload_conflicts(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world();command=str(uuid.uuid4())
  self.assertEqual(self.purchase(ids,command=command)['state'],'applied')
  self.assertEqual(self.purchase(ids,command=command)['state'],'replayed')
  self.assertEqual(self.purchase(ids,command=command,quantity='1')['state'],'conflict')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outbox'),'1')
 def test_changed_uuid_payload_is_controlled_conflict(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world();command=str(uuid.uuid4());self.purchase(ids,command=command,quantity='1')
  self.assertEqual(self.purchase(ids,command=command,quantity='0.5'),{'state':'conflict'})
 def test_foreign_tenant_command_uuid_conflicts_without_leak(self):
  self.assertEqual(self.migrate()[0],0);a=self.purchase_world();b=self.purchase_world();command=str(uuid.uuid4())
  self.purchase(a,command=command)
  self.assertEqual(self.purchase(b,command=command),{'state':'conflict'})
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'1')
 def test_new_intents_refuse_stale_source_role_mapping_and_closed_removed_sources(self):
  self.assertEqual(self.migrate()[0],0)
  for axis in ('source','role','mapping','not-supplier','master-external','closed','removed'):
   with self.subTest(axis=axis):
    ids=self.purchase_world();args={};c=ids['companies'][0]
    if axis=='source':args['revision']=2147483647
    if axis=='role':args['roleRevision']=2147483647
    if axis=='mapping':args['mappingRevision']=2147483647
    if axis=='not-supplier':self.sql(self.app_prefix(ids)+self.role(ids,1,1,supplier=False)+'COMMIT;',app=True)
    if axis=='master-external':self.authority(ids,1,'ExternalToEnginia360')
    if axis=='closed':self.sql(f'''INSERT INTO workshop.technical_closures VALUES ('{ids['order']}','{uuid.uuid4()}','{ids['tenant']}',0,clock_timestamp(),'{ids['actor']}');''')
    if axis=='removed':self.sql(f'''UPDATE workshop.commercial_lines SET "State"='Removed',"Version"=2 WHERE "Id"='{ids['line']}';''')
    self.assertEqual(self.purchase(ids,**args)['state'],'conflict')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_quantity_transport_refuses_non_q6_without_partial_rows(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world()
  for quantity in ('0','-1','1.0000001','1000000','1e1',' 1','NaN',''):
   with self.subTest(quantity=quantity):self.assertEqual(self.purchase(ids,quantity=quantity)['state'],'invalid')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_missing_or_other_stock_destination_refuses_without_writes(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world()
  for descriptor in ({},dict(kind='SimulatorV1',version=1,fingerprint='a'*64,stockSourceId=ids['stockSource'],stockProfileId=ids['stockProfile']),dict(kind='GiobbyPurchaseV1',version=1,fingerprint='a'*64,stockSourceId=str(uuid.uuid4()),stockProfileId=ids['stockProfile'])):
   with self.subTest(descriptor=descriptor):self.assertEqual(self.purchase(ids,destination=descriptor)['state'],'destination_unavailable')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_destination_scope_must_equal_the_source_tenant_company_and_site(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world()
  for key in ('tenantId','legalEntityId','siteId'):
   with self.subTest(key=key):self.assertEqual(self.purchase(ids,destination=dict(self.good_destination(ids),**{key:str(uuid.uuid4())}))['state'],'destination_unavailable')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_write_needs_workshop_read_capability_and_existing_identity_binding(self):
  self.assertEqual(self.migrate()[0],0)
  for axis in ('read','workshop','binding'):
   with self.subTest(axis=axis):
    ids=self.purchase_world();c=ids['companies'][0];m=ids['member']
    if axis=='read':self.sql(f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{m}' AND "Permission"='workshop.orders.read';''')
    if axis=='workshop':self.sql(f'''UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "LegalEntityId"='{c}' AND "Capability"='workshop';''')
    if axis=='binding':self.sql(f'''DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{ids['actor']}';''')
    self.assertEqual(self.purchase(ids)['state'],'forbidden')
 def test_regression_tables_are_forced_rls_append_only_and_have_no_application_dml(self):
  # New-migration property check on already-written definitions: labelled regression, not RED evidence.
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world();command=str(uuid.uuid4());self.purchase(ids,command=command)
  app=os.environ['R00_APP_USER']
  for table in ('inventory.purchase_intents','inventory.purchase_intent_outbox'):
   self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='{table}'::regclass"),'t',table)
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','{table}','SELECT') OR has_table_privilege('{app}','{table}','INSERT') OR has_table_privilege('{app}','{table}','UPDATE') OR has_table_privilege('{app}','{table}','DELETE') OR has_table_privilege('{app}','{table}','TRUNCATE')"),'f',table)
   for statement in (f'UPDATE {table} SET "TenantId"="TenantId"',f'DELETE FROM {table}','TRUNCATE inventory.purchase_intents, inventory.purchase_intent_outbox'):
    result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input=statement+';',env=dict(os.environ,PGDATABASE=self.database),text=True,capture_output=True,timeout=10)
    self.assertNotEqual(result.returncode,0,statement);self.assertIn('append-only',result.stderr)
  self.assertEqual(self.sql(f"SELECT has_function_privilege('{app}','organization_access.purchase_intent_authorized(uuid,uuid,uuid,uuid,uuid)','EXECUTE') OR has_function_privilege('{app}','counterparties.purchase_supplier(uuid,uuid)','EXECUTE')"),'f','internal helpers are not directly callable')
 def test_state_reads_fresh_source_choices_and_pending_budget(self):
  self.assertEqual(self.migrate()[0],0);ids=self.purchase_world();c=ids['companies'][0]
  self.assertEqual(self.sql("SELECT to_regprocedure('inventory.purchase_intent_state(uuid,uuid,uuid)') IS NOT NULL"),'t','coherent state contract absent')
  def read():return json.loads(self.sql(self.app_prefix(ids,c)+f"SELECT inventory.purchase_intent_state('{ids['order']}','{ids['line']}','{ids['warehouse']}')::text; COMMIT;",app=True).splitlines()[-1])
  before=read();self.assertEqual(before['remaining'],'3.000000');self.assertEqual(before['source']['revision'],1)
  self.assertEqual(len(before['suppliers']),1);self.assertNotIn('vendorId',json.dumps(before))
  self.purchase(ids);after=read();self.assertEqual(after['remaining'],'1.000000');self.assertEqual(after['intents'][0]['status'],'Held')
import uuid
import subprocess
import time
if __name__=='__main__':unittest.main()
