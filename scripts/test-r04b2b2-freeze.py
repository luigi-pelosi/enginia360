#!/usr/bin/env python3
"""D91/D92 isolated owning-module price acceptance proofs."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('purchase',ROOT/'scripts/test-r04b2a-purchase.py');assert spec and spec.loader
purchase=importlib.util.module_from_spec(spec);spec.loader.exec_module(purchase)
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated PostgreSQL required')
class FreezeSqlTests(unittest.TestCase):
 setUp=purchase.PurchaseSqlTests.setUp
 tearDown=purchase.PurchaseSqlTests.tearDown
 sql=purchase.PurchaseSqlTests.sql
 start_migration=purchase.PurchaseSqlTests.start_migration
 migrate=purchase.PurchaseSqlTests.migrate
 world=purchase.PurchaseSqlTests.world
 authority=purchase.PurchaseSqlTests.authority
 app_prefix=purchase.PurchaseSqlTests.app_prefix
 role=purchase.PurchaseSqlTests.role
 vendor=purchase.PurchaseSqlTests.vendor
 owner=purchase.PurchaseSqlTests.__dict__.get('owner')
 purchase_world=purchase.PurchaseSqlTests.purchase_world
 good_destination=purchase.PurchaseSqlTests.good_destination
 def freeze_world(self):
  rc,out,err=self.migrate();self.assertEqual(rc,0,err)
  ids=self.purchase_world()
  self.sql(f'''INSERT INTO catalog.items VALUES ('{ids['catalog']}','{ids['tenant']}','{ids['companies'][0]}','Part','Source part',8);''')
  return ids
 def quote(self,ids,subject=None,**changes):
  a=dict(order=ids['order'],line=ids['line'],warehouse=ids['warehouse'],supplier=ids['record']);a.update(changes)
  return json.loads(self.sql(self.app_prefix(ids,ids['companies'][0],subject)+f"SELECT catalog.purchase_intent_quote('{a['order']}','{a['line']}','{a['warehouse']}','{a['supplier']}')::text; COMMIT;",app=True).splitlines()[-1])
 def test_quote_surface(self):
  self.freeze_world()
  self.assertEqual(self.sql("SELECT to_regprocedure('catalog.purchase_intent_quote(uuid,uuid,uuid,uuid)') IS NOT NULL"),'t','minimal source-bound quote surface absent')
 def test_authorized_missing_quote_without_price_list_grants(self):
  ids=self.freeze_world();got=self.quote(ids)
  self.assertEqual(got['state'],'ready')
  self.assertEqual(got['quote'],{'revision':0,'catalogVersion':8,'authorityVersion':1,'sourcePresent':False,'unitPurchasePrice':None})
  self.assertNotIn('history',json.dumps(got));self.assertNotIn('vendorId',json.dumps(got))
  self.assertEqual(self.sql("SELECT count(*) FROM catalog.supplier_purchase_price_history"),'0')
 def listed(self,ids,price='12.345678',revision=1):
  command=str(uuid.uuid4())
  self.sql(f'''INSERT INTO catalog.supplier_purchase_price_history("CommandId","TenantId","LegalEntityId","SupplierId","CatalogItemId","Revision","UnitPurchasePrice","ActorMembershipId","SupplierRevision","CatalogVersion","AuthorityVersion","Payload") VALUES ('{command}','{ids['tenant']}','{ids['companies'][0]}','{ids['record']}','{ids['catalog']}',{revision},'{price}','{ids['member']}',1,8,1,'{{}}');''')
  return command
 def test_listed_quote_is_current_minimal_and_zero_is_present(self):
  ids=self.freeze_world();self.listed(ids,'0')
  got=self.quote(ids)['quote'];self.assertEqual((got['revision'],got['sourcePresent'],got['unitPurchasePrice']),(1,True,'0.000000'))
  self.listed(ids,revision=2)
  got=self.quote(ids)['quote'];self.assertEqual((got['revision'],got['sourcePresent'],got['unitPurchasePrice']),(2,True,'12.345678'))
  self.assertEqual(set(got),{'revision','sourcePresent','unitPurchasePrice','catalogVersion','authorityVersion'})
 def accepted_sql(self,ids,**changes):
  a=dict(command=str(uuid.uuid4()),quantity='1',revision=1,roleRevision=1,mappingRevision=1,quoteRevision=0,catalogVersion=8,authorityVersion=1,manual=None);a.update(changes)
  manual='NULL' if a['manual'] is None else "'"+a['manual']+"'"
  return f"SELECT inventory.accept_purchase_intent('{a['command']}','{ids['order']}','{ids['line']}','{ids['warehouse']}','{ids['record']}',{a['revision']},{a['roleRevision']},{a['mappingRevision']},'{a['quantity']}',{a['quoteRevision']},{a['catalogVersion']},{a['authorityVersion']},{manual},'{json.dumps(self.good_destination(ids))}'::jsonb)::text;"
 def accept(self,ids,subject=None,**changes):
  return json.loads(self.sql(self.app_prefix(ids,ids['companies'][0],subject)+self.accepted_sql(ids,**changes)+'COMMIT;',app=True).splitlines()[-1])
 def test_accept_surface(self):
  self.freeze_world()
  self.assertEqual(self.sql("SELECT to_regprocedure('inventory.accept_purchase_intent(uuid,uuid,uuid,uuid,uuid,integer,integer,integer,text,integer,integer,integer,text,jsonb)') IS NOT NULL"),'t','accepted-price command surface absent')
 def price_row(self,command):
  return json.loads(self.sql(f'''SELECT to_jsonb(p)||jsonb_build_object('AcceptedUnitPurchasePrice',"AcceptedUnitPurchasePrice"::text) FROM inventory.purchase_intent_prices p WHERE "IntentId"='{command}';'''))
 def test_missing_cost_requires_explicit_entry_and_freezes_manual_zero(self):
  ids=self.freeze_world()
  self.assertEqual(self.accept(ids)['state'],'invalid','untouched provisional zero must not be accepted')
  command=str(uuid.uuid4());got=self.accept(ids,command=command,manual='0')
  self.assertEqual(got['state'],'applied','explicitly entered zero is valid')
  row=self.price_row(command)
  self.assertEqual((row['AcceptedUnitPurchasePrice'],row['PriceSource']['sourcePresent'],row['PriceSource']['revision'],row['Method']),( '0.000000',False,0,'manual'))
  self.assertEqual(row['ActorMembershipId'],ids['member']);self.assertTrue(row['AcceptedAt']);self.assertEqual(row['Version'],1)
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outbox'),'1')
 def test_listed_acceptance_freezes_server_price_and_exact_provenance(self):
  ids=self.freeze_world();source=self.listed(ids);command=str(uuid.uuid4())
  self.assertEqual(self.accept(ids,command=command,quoteRevision=1)['state'],'applied')
  row=self.price_row(command)
  self.assertEqual((row['AcceptedUnitPurchasePrice'],row['Method'],row['PriceSource']['provenance']['CommandId']),('12.345678','listed',source))
  self.assertTrue(row['PriceSource']['sourcePresent']);self.assertEqual(row['PriceSource']['revision'],1)
 def test_listed_price_does_not_accept_a_manual_override(self):
  ids=self.freeze_world();self.listed(ids)
  self.assertEqual(self.accept(ids,quoteRevision=1,manual='0')['state'],'invalid')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_quoted_revisions_must_still_match_at_acceptance(self):
  for axis in ('revision','roleRevision','mappingRevision','quoteRevision','catalogVersion','authorityVersion'):
   with self.subTest(axis=axis):
    ids=self.freeze_world()
    self.assertEqual(self.accept(ids,manual='1',**{axis:2147483647})['state'],'conflict')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_list_creation_or_price_edit_between_quote_and_acceptance_conflicts(self):
  ids=self.freeze_world();self.assertFalse(self.quote(ids)['quote']['sourcePresent']);self.listed(ids)
  self.assertEqual(self.accept(ids,manual='0')['state'],'conflict')
  self.listed(ids,'99',revision=2)
  self.assertEqual(self.accept(ids,quoteRevision=1)['state'],'conflict')
 def test_manual_price_transport_rejects_non_q6_without_partial_facts(self):
  ids=self.freeze_world()
  for price in ('1.0000001','1e1',' 1','-1','1000000','NaN',''):
   with self.subTest(price=price):self.assertEqual(self.accept(ids,manual=price)['state'],'invalid')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_quantity_transport_and_empty_uuid_are_controlled(self):
  ids=self.freeze_world()
  for quantity in ('0','1.0000001','1e1',' 1','-1','1000000','NaN',''):
   with self.subTest(quantity=quantity):self.assertEqual(self.accept(ids,manual='1',quantity=quantity)['state'],'invalid')
  self.assertEqual(self.accept(ids,manual='1',command=str(uuid.UUID(int=0)))['state'],'invalid')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_exact_replay_keeps_original_price_after_source_and_list_edits(self):
  ids=self.freeze_world();command=str(uuid.uuid4());self.accept(ids,command=command,manual='0')
  original=self.price_row(command);self.listed(ids)
  self.sql(f'''UPDATE workshop.commercial_lines SET "Version"=2,"Description"='Changed' WHERE "Id"='{ids['line']}';''')
  self.assertEqual(self.accept(ids,command=command,manual='0')['state'],'replayed')
  self.assertEqual(self.price_row(command),original)
  self.assertEqual(self.accept(ids,command=command,manual='1')['state'],'conflict')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outbox'),'1')
 def test_new_uuid_does_not_reset_cumulative_cap_including_old_unpriced_intents(self):
  ids=self.freeze_world()
  legacy=purchase.PurchaseSqlTests.purchase_sql(self,ids,quantity='2')
  self.assertEqual(json.loads(self.sql(self.app_prefix(ids,ids['companies'][0])+legacy+'COMMIT;',app=True).splitlines()[-1])['state'],'applied')
  self.assertEqual(self.accept(ids,manual='1',quantity='2')['state'],'exceeds_remaining')
  self.assertEqual(self.accept(ids,manual='1',quantity='1')['state'],'applied')
  self.assertEqual(self.accept(ids,manual='1',quantity='0.000001')['state'],'exceeds_remaining')
  self.assertEqual(self.sql('SELECT sum("Quantity") FROM inventory.purchase_intents'),'3.000000')
 def test_accept_requires_same_frozen_destination_as_company_stock_authority(self):
  ids=self.freeze_world();destination=self.good_destination(ids);destination['stockSourceId']=str(uuid.uuid4())
  sql=self.accepted_sql(ids,manual='1').replace(json.dumps(self.good_destination(ids)),json.dumps(destination))
  got=json.loads(self.sql(self.app_prefix(ids,ids['companies'][0])+sql+'COMMIT;',app=True).splitlines()[-1])
  self.assertEqual(got['state'],'destination_unavailable')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intents'),'0')
 def test_regression_minimal_grants_suffice_and_management_remains_denied(self):
  ids=self.freeze_world();self.listed(ids)
  self.sql(f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{ids['member']}' AND "Permission" NOT IN ('inventory.purchase-intents.create','workshop.orders.read');''')
  self.assertEqual(self.quote(ids)['quote']['unitPurchasePrice'],'12.345678')
  self.assertEqual(self.accept(ids,quoteRevision=1)['state'],'applied')
  full=self.sql(self.app_prefix(ids,ids['companies'][0])+f"SELECT catalog.supplier_purchase_price_state('{ids['companies'][0]}','{ids['record']}','{ids['catalog']}'); COMMIT;",app=True)
  self.assertEqual(json.loads(full.splitlines()[-1]),{'state':'forbidden'})
 def test_regression_quote_and_accept_require_current_exact_grants_and_binding(self):
  for axis in ('purchase','read','binding','inventory','workshop','company','site','warehouse'):
   with self.subTest(axis=axis):
    ids=self.freeze_world();m=ids['member'];c=ids['companies'][0]
    command=str(uuid.uuid4());self.accept(ids,command=command,manual='1')
    if axis in ('purchase','read'):
     permission='inventory.purchase-intents.create' if axis=='purchase' else 'workshop.orders.read'
     self.sql(f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{m}' AND "Permission"='{permission}';''')
    elif axis=='binding':self.sql(f'''DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{ids['actor']}';''')
    elif axis in ('inventory','workshop'):self.sql(f'''UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "LegalEntityId"='{c}' AND "Capability"='{axis}';''')
    else:
     column={'company':'LegalEntityId','site':'SiteId','warehouse':'WarehouseId'}[axis]
     target=ids['companies'][1] if axis=='company' else str(uuid.uuid4())
     self.sql(f'''UPDATE organization_access.company_permissions SET "{column}"='{target}' WHERE "MembershipId"='{m}' AND "Permission"='inventory.purchase-intents.create';''')
    self.assertEqual(self.quote(ids)['state'],'forbidden')
    self.assertEqual(self.accept(ids,command=command,manual='1')['state'],'forbidden')
 def test_regression_source_access_and_no_arbitrary_item_lookup(self):
  ids=self.freeze_world();foreign=self.freeze_world()
  self.assertEqual(self.quote(ids,line=foreign['line'],order=foreign['order'])['state'],'not_found')
  self.assertEqual(self.quote(ids,supplier=str(uuid.uuid4()))['state'],'conflict')
  self.assertEqual(self.quote(ids,subject=str(uuid.uuid4()))['state'],'forbidden')
  self.assertEqual(self.quote(ids,line=ids['catalog'])['state'],'not_found')
  self.assertEqual(self.sql("SELECT proargnames::text FROM pg_proc WHERE oid='catalog.purchase_intent_quote(uuid,uuid,uuid,uuid)'::regprocedure"),'{ord,line,warehouse,supplier}')
 def test_foreign_tenant_uuid_collision_returns_conflict_without_partial_write(self):
  a=self.freeze_world();b=self.freeze_world();command=str(uuid.uuid4())
  self.assertEqual(self.accept(a,command=command,manual='1')['state'],'applied')
  self.assertEqual(self.accept(b,command=command,manual='1'),{'state':'conflict'})
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_prices'),'1')
 process=purchase.PurchaseSqlTests.process
 finish=purchase.PurchaseSqlTests.finish
 waiters=purchase.PurchaseSqlTests.waiters
 def hold(self,ids,statement,app=True):
  p=self.process(ids,statement+"\nSELECT pg_backend_pid();\n\\echo HELD\n",app=app)
  lines=[]
  while True:
   line=p.stdout.readline().strip()
   if line=='HELD':break
   if not line and p.poll() is not None:self.fail('holder failed before physical barrier: '+p.stderr.read())
   lines.append(line)
  return p,int(lines[-1]),lines
 def release(self,p):
  p.stdin.write('COMMIT;\n');p.stdin.flush();return self.finish(p)
 def price_writer(self,ids,price='99'):
  return f"SELECT catalog.set_supplier_purchase_price('{ids['companies'][0]}','{ids['record']}','{ids['catalog']}','{uuid.uuid4()}',1,1,8,1,'{price}')::text;"
 def allow_prices(self,ids):
  self.sql(f'''INSERT INTO organization_access.capability_activations VALUES ('{ids['companies'][0]}','catalog',true); INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{ids['member']}','{ids['tenant']}','{ids['companies'][0]}','catalog.purchase-prices.read',NULL,NULL),('{uuid.uuid4()}','{ids['member']}','{ids['tenant']}','{ids['companies'][0]}','catalog.purchase-prices.manage',NULL,NULL);''')
 def test_regression_physical_price_writer_before_acceptance_sees_conflict(self):
  ids=self.freeze_world();self.listed(ids);self.allow_prices(ids)
  holder,pid,lines=self.hold(ids,self.app_prefix(ids,ids['companies'][0])+self.price_writer(ids))
  self.assertTrue(any('applied' in x for x in lines))
  contender=self.process(ids,self.app_prefix(ids,ids['companies'][0])+self.accepted_sql(ids,quoteRevision=1)+'COMMIT;')
  self.waiters(pid,1);self.release(holder)
  self.assertEqual(json.loads(self.finish(contender))['state'],'conflict')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_prices'),'0')
 def test_regression_physical_acceptance_before_price_writer_keeps_snapshot(self):
  ids=self.freeze_world();self.listed(ids);self.allow_prices(ids);command=str(uuid.uuid4())
  holder,pid,lines=self.hold(ids,self.app_prefix(ids,ids['companies'][0])+self.accepted_sql(ids,quoteRevision=1,command=command))
  self.assertTrue(any('applied' in x for x in lines))
  contender=self.process(ids,self.app_prefix(ids,ids['companies'][0])+self.price_writer(ids)+'COMMIT;')
  self.waiters(pid,1);self.release(holder)
  self.assertEqual(json.loads(self.finish(contender))['state'],'applied')
  self.assertEqual(self.price_row(command)['AcceptedUnitPurchasePrice'],'12.345678')
 def test_replay_after_source_removed_and_supplier_role_revoked_requires_only_current_access(self):
  ids=self.freeze_world();command=str(uuid.uuid4());self.accept(ids,command=command,manual='1')
  self.sql(self.app_prefix(ids)+self.role(ids,1,1,supplier=False)+'COMMIT;',app=True)
  self.sql(f'''UPDATE workshop.commercial_lines SET "State"='Removed',"Version"=2 WHERE "Id"='{ids['line']}';''')
  self.assertEqual(self.accept(ids,command=command,manual='1')['state'],'replayed')
  self.assertEqual(self.accept(ids,manual='1')['state'],'conflict')
 def test_regression_atomic_rollback_at_each_insert_and_deferred_commit(self):
  import subprocess
  ids=self.freeze_world()
  for table in ('purchase_intents','purchase_intent_prices','purchase_intent_outbox'):
   for deferred in (False,True):
    with self.subTest(table=table,deferred=deferred):
     self.sql(f'''CREATE FUNCTION inventory.freeze_fixture_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'isolated frozen-price rollback fixture'; END $$;
      CREATE {'CONSTRAINT ' if deferred else ''}TRIGGER freeze_fixture_fault AFTER INSERT ON inventory.{table} {'DEFERRABLE INITIALLY DEFERRED ' if deferred else ''}FOR EACH ROW EXECUTE FUNCTION inventory.freeze_fixture_fault();''')
     result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input=self.app_prefix(ids,ids['companies'][0])+self.accepted_sql(ids,manual='1')+'COMMIT;',env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD']),text=True,capture_output=True,timeout=15)
     self.assertNotEqual(result.returncode,0);self.assertIn('isolated frozen-price rollback fixture',result.stderr)
     self.sql(f'DROP TRIGGER freeze_fixture_fault ON inventory.{table}; DROP FUNCTION inventory.freeze_fixture_fault();')
     self.assertEqual(self.sql('SELECT (SELECT count(*) FROM inventory.purchase_intents)+(SELECT count(*) FROM inventory.purchase_intent_prices)+(SELECT count(*) FROM inventory.purchase_intent_outbox)'),'0')
 def test_regression_numeric_max_and_immutable_absence_after_source_creation(self):
  ids=self.freeze_world();command=str(uuid.uuid4())
  self.assertEqual(self.accept(ids,command=command,manual='999999.999999')['state'],'applied')
  original=self.price_row(command);self.listed(ids)
  self.assertEqual(self.accept(ids,command=command,manual='999999.999999')['state'],'replayed')
  self.assertEqual(self.price_row(command),original);self.assertEqual(original['AcceptedUnitPurchasePrice'],'999999.999999');self.assertFalse(original['PriceSource']['sourcePresent'])
  app=os.environ['R00_APP_USER'];table='inventory.purchase_intent_prices'
  self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='{table}'::regclass"),'t')
  for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','{table}','{privilege}')"),'f')
  self.assertEqual(self.sql(f"SELECT has_function_privilege('{app}','catalog.purchasing_price(jsonb)','EXECUTE') OR has_function_privilege('{app}','inventory.purchasing_context(uuid,uuid,uuid,uuid)','EXECUTE')"),'f')
 def test_regression_simultaneous_identical_uuid_commits_one_price_and_outbox(self):
  ids=self.freeze_world();command=str(uuid.uuid4())
  holder,pid,_=self.hold(ids,'BEGIN; SELECT pg_advisory_xact_lock(hashtextextended(\''+command+'\',0));')
  contenders=[self.process(ids,self.app_prefix(ids,ids['companies'][0])+self.accepted_sql(ids,command=command,manual='0')+'COMMIT;') for _ in range(2)]
  self.waiters(pid,2);self.release(holder)
  self.assertEqual(sorted(json.loads(self.finish(p))['state'] for p in contenders),['applied','replayed'])
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_prices'),'1');self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outbox'),'1')
 def test_authoritative_state_reads_accepted_price_without_repricing_old_or_new_intents(self):
  ids=self.freeze_world();command=str(uuid.uuid4());self.accept(ids,command=command,manual='0')
  legacy=purchase.PurchaseSqlTests.purchase_sql(self,ids,quantity='1')
  self.sql(self.app_prefix(ids,ids['companies'][0])+legacy+'COMMIT;',app=True);self.listed(ids)
  got=json.loads(self.sql(self.app_prefix(ids,ids['companies'][0])+f"SELECT inventory.purchase_intent_state('{ids['order']}','{ids['line']}','{ids['warehouse']}'); COMMIT;",app=True).splitlines()[-1])
  current=next(i for i in got['intents'] if i['id']==command)
  self.assertIn('acceptedPrice',current)
  self.assertEqual(current['acceptedPrice']['unitPurchasePrice'],'0.000000');self.assertFalse(current['acceptedPrice']['sourcePresent']);self.assertEqual(current['acceptedPrice']['method'],'manual')
  old=next(i for i in got['intents'] if i['id']!=command);self.assertIsNone(old['acceptedPrice'])
  self.assertNotIn('vendorId',json.dumps(got));self.assertEqual(got['remaining'],'1.000000')
 def change_sql(self,ids,axis):
  t,c,m=ids['tenant'],ids['companies'][0],ids['member']
  if axis=='grant':return f'''BEGIN; DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{m}' AND "Permission"='inventory.purchase-intents.create';'''
  if axis=='role':return self.app_prefix(ids)+self.role(ids,1,1,supplier=False)
  if axis=='mapping':return self.vendor(ids,expected=1,vendor_id='4712').removesuffix(' COMMIT;')
  if axis=='authority':
   companies=','.join("'"+x+"'::uuid" for x in ids['companies'])
   return f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{t}',true); SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{t}','{m}','{ids['proof']}',1,'ExternalToEnginia360','{ids['source']}','{ids['profile']}',ARRAY[{companies}]);"
  if axis=='catalog':return f'''BEGIN; UPDATE catalog.items SET "Version"=9 WHERE "Id"='{ids['catalog']}';'''
  assert axis=='source'
  return f'''BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('{ids['order']}',0)); UPDATE workshop.commercial_lines SET "Version"=2 WHERE "Id"='{ids['line']}';'''
 def test_regression_physical_context_changes_both_serialization_orders(self):
  for axis in ('grant','role','mapping','authority','catalog','source'):
   for change_first in (True,False):
    with self.subTest(axis=axis,change_first=change_first):
     ids=self.freeze_world();command=str(uuid.uuid4());accept=self.app_prefix(ids,ids['companies'][0])+self.accepted_sql(ids,command=command,manual='1');change=self.change_sql(ids,axis)
     if change_first:
      holder,pid,_=self.hold(ids,change,app=axis=='role')
      contender=self.process(ids,accept+'COMMIT;')
      self.waiters(pid,1);self.release(holder)
      expected='forbidden' if axis=='grant' else 'master_external' if axis=='authority' else 'conflict'
      self.assertEqual(json.loads(self.finish(contender))['state'],expected)
      self.assertEqual(self.sql(f'''SELECT count(*) FROM inventory.purchase_intent_prices WHERE "IntentId"='{command}';'''),'0')
     else:
      holder,pid,lines=self.hold(ids,accept);self.assertTrue(any('applied' in x for x in lines))
      contender=self.process(ids,change+'COMMIT;',app=axis=='role')
      self.waiters(pid,1);self.release(holder);self.finish(contender)
      snapshot=self.price_row(command);self.assertEqual(snapshot['AcceptedUnitPurchasePrice'],'1.000000')
      self.assertEqual(self.accept(ids,command=command,manual='1')['state'],'forbidden' if axis=='grant' else 'replayed')
      self.assertEqual(self.price_row(command),snapshot)
 def test_regression_quote_waits_for_price_commit_and_returns_coherent_revision(self):
  ids=self.freeze_world();self.listed(ids);self.allow_prices(ids)
  holder,pid,_=self.hold(ids,self.app_prefix(ids,ids['companies'][0])+self.price_writer(ids))
  contender=self.process(ids,self.app_prefix(ids,ids['companies'][0])+f"SELECT catalog.purchase_intent_quote('{ids['order']}','{ids['line']}','{ids['warehouse']}','{ids['record']}'); COMMIT;")
  self.waiters(pid,1);self.release(holder)
  quote=json.loads(self.finish(contender))['quote'];self.assertEqual((quote['revision'],quote['unitPurchasePrice']),(2,'99.000000'))
 def test_regression_physical_cap_is_shared_by_priced_commands_across_suppliers_and_warehouses(self):
  ids=self.freeze_world();self.assertEqual(self.accept(ids,quantity='2',manual='1')['state'],'applied')
  other=dict(ids,warehouse=str(uuid.uuid4()),record=ids['other_record']);c=ids['companies'][0]
  self.sql(f'''INSERT INTO organization_access.warehouses VALUES ('{other['warehouse']}','{ids['site']}','{c}','{ids['tenant']}','Other'); INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{ids['member']}','{ids['tenant']}','{c}','inventory.purchase-intents.create','{ids['site']}','{other['warehouse']}');''')
  self.sql(self.app_prefix(ids)+self.role(ids,1,0,record=other['record'])+'COMMIT;',app=True)
  self.sql(self.vendor(ids,record=other['record'],vendor_id='V2'))
  holder,pid,_=self.hold(ids,f"BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('inventory:line:{ids['tenant']}:{ids['line']}',0));",app=False)
  contenders=[self.process(ids,self.app_prefix(world,c)+self.accepted_sql(world,manual='1')+'COMMIT;') for world in (ids,other)]
  self.waiters(pid,2);self.release(holder)
  self.assertEqual(sorted(json.loads(self.finish(p))['state'] for p in contenders),['applied','exceeds_remaining'])
  self.assertEqual(self.sql('SELECT sum("Quantity") FROM inventory.purchase_intents'),'3.000000');self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_prices'),'2')
if __name__=='__main__':unittest.main()
