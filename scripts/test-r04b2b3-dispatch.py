#!/usr/bin/env python3
"""R04.b.2b.3 isolated PostgreSQL acceptance of the purchase dispatch SQL contract. Synthetic only; no ERP traffic."""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('freeze',ROOT/'scripts/test-r04b2b2-freeze.py');assert spec and spec.loader
freeze=importlib.util.module_from_spec(spec);spec.loader.exec_module(freeze)
MIGRATION=ROOT/'database/runtime/migrations/0031_purchase_dispatch.sql'
class MigrationTextTests(unittest.TestCase):
 def test_migration_is_appended_only_and_creates_no_stock_or_purchase_writer(self):
  self.assertTrue(MIGRATION.exists(),'migration 0031 is absent')
  text=MIGRATION.read_text()
  statements=[line.strip() for line in text.splitlines() if not line.startswith('--')]
  for forbidden in ('DROP ','TRUNCATE ','DELETE ','ALTER TABLE inventory.purchase_intents','ALTER TABLE inventory.purchase_intent_outbox','inventory.stock','GRANT INSERT ON inventory','GRANT UPDATE ON inventory','GRANT DELETE'):
   self.assertFalse([x for x in statements if x.startswith(forbidden)],forbidden)
  self.assertNotIn('inventory.stock',text)
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated PostgreSQL required')
class DispatchSqlTests(unittest.TestCase):
 # Borrow only fixtures/helpers, never the earlier suites' tests.
 for _name,_value in vars(freeze.FreezeSqlTests).items():
  if not _name.startswith('test_') and callable(_value) and not _name.startswith('__'):locals()[_name]=_value
 purchase=freeze.purchase.PurchaseSqlTests.purchase
 purchase_sql=freeze.purchase.PurchaseSqlTests.purchase_sql
 del _name,_value
 def priced(self,ids,price='12.345678',quantity='2'):
  command=str(uuid.uuid4());got=self.accept(ids,command=command,quantity=quantity,manual=price)
  self.assertEqual(got['state'],'applied');return command
 def pending(self):
  out=self.sql('SELECT "TenantId"||\'|\'||"LegalEntityId"||\'|\'||"IntentId" FROM inventory.pending_purchase_dispatch(20,0) ORDER BY 1;',app=True)
  return [line for line in out.splitlines() if '|' in line]
 def ctx(self,ids,tenant=None,company=None):
  return f"BEGIN; SELECT set_config('app.tenant_id','{tenant or ids['tenant']}',true),set_config('app.legal_entity_id','{company or ids['companies'][0]}',true);"
 def read(self,ids,intent,**changes):
  return self.sql(self.ctx(ids,changes.get('tenant'),changes.get('company'))+f"SELECT coalesce(inventory.read_purchase_dispatch('{changes.get('arg_tenant') or ids['tenant']}','{changes.get('arg_company') or ids['companies'][0]}','{intent}')::text,'null'); COMMIT;",app=True).splitlines()[-1]
 def record(self,ids,intent,reference='GiobbyPurchaseOrder-301',**changes):
  return self.sql(self.ctx(ids,changes.get('tenant'),changes.get('company'))+f"SELECT inventory.record_purchase_outcome('{changes.get('arg_tenant') or ids['tenant']}','{changes.get('arg_company') or ids['companies'][0]}','{intent}','{reference}'); COMMIT;",app=True).splitlines()[-1]
 def test_dispatch_surface_and_privileges(self):
  self.freeze_world()
  self.assertEqual(self.sql("SELECT to_regprocedure('inventory.pending_purchase_dispatch(integer,integer)') IS NOT NULL AND to_regprocedure('inventory.read_purchase_dispatch(uuid,uuid,uuid)') IS NOT NULL AND to_regprocedure('inventory.record_purchase_outcome(uuid,uuid,uuid,text)') IS NOT NULL"),'t')
  self.assertEqual(self.sql("SELECT pg_get_userbyid(proowner)||'|'||prosecdef||'|'||array_to_string(proconfig,',') FROM pg_proc WHERE oid='inventory.pending_purchase_dispatch(integer,integer)'::regprocedure"),'enginia360_outbox_reader|true|search_path=pg_catalog, pg_temp')
  self.assertEqual(self.sql("SELECT has_schema_privilege('enginia360_outbox_reader','inventory','CREATE')"),'f')
  self.assertEqual(self.sql("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='inventory.purchase_intent_outcomes'::regclass"),'t')
  self.assertEqual(self.sql("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='integrations.purchase_dispatches'::regclass"),'t')
  app=os.environ['R00_APP_USER'] if 'R00_APP_USER' in os.environ else 'runtime_app'
  self.assertEqual(self.sql(f"SELECT has_table_privilege('{app}','inventory.purchase_intent_outcomes','INSERT') OR has_table_privilege('{app}','inventory.purchase_intent_outcomes','SELECT') OR has_table_privilege('{app}','inventory.purchase_intent_outcomes','UPDATE')"),'f')
 def test_only_priced_unresolved_intents_are_pending_and_unpriced_are_never_dispatchable(self):
  ids=self.freeze_world();priced=self.priced(ids,quantity='1')
  legacy=str(uuid.uuid4())
  self.assertEqual(self.purchase(ids,command=legacy,quantity='1')['state'],'applied')
  rows=self.pending()
  self.assertEqual(rows,[f"{ids['tenant']}|{ids['companies'][0]}|{priced}"],'only the priced intent may be dispatched')
  self.assertNotIn(legacy,'\n'.join(rows))
 def test_read_returns_exactly_the_frozen_facts(self):
  ids=self.freeze_world();intent=self.priced(ids,'12.345678','2')
  got=json.loads(self.read(ids,intent))
  self.assertEqual({k:got[k] for k in ('tenantId','legalEntityId','intentId','catalogItemId','quantity','unitPrice','vendorId','vendorName','fingerprint')},
   dict(tenantId=ids['tenant'],legalEntityId=ids['companies'][0],intentId=intent,catalogItemId=ids['catalog'],quantity='2.000000',unitPrice='12.345678',vendorId='4711',vendorName='Synthetic Supplier S.r.l.',fingerprint='a'*64))
  self.assertEqual(got['siteId'],ids['site']);self.assertTrue(got['description'])
  self.assertNotIn('memberId',json.dumps(got))
 def test_read_of_an_unpriced_intent_is_null(self):
  ids=self.freeze_world();legacy=str(uuid.uuid4());self.assertEqual(self.purchase(ids,command=legacy,quantity='1')['state'],'applied')
  self.assertEqual(self.read(ids,legacy),'null')
 def test_read_and_record_refuse_foreign_or_unset_tenant_context(self):
  ids=self.freeze_world();intent=self.priced(ids);other=str(uuid.uuid4())
  self.assertEqual(self.read(ids,intent,tenant=other,arg_tenant=ids['tenant']),'null','argument differing from verified context')
  self.assertEqual(self.read(ids,intent,tenant=other,arg_tenant=other),'null','other tenant sees nothing')
  self.assertEqual(self.read(ids,intent,company=str(uuid.uuid4()),arg_company=str(uuid.uuid4())),'null','other company sees nothing')
  self.assertEqual(self.record(ids,intent,tenant=other,arg_tenant=ids['tenant']),'forbidden')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outcomes'),'0')
 def test_record_is_idempotent_exact_and_removes_the_intent_from_pending(self):
  ids=self.freeze_world();first=self.priced(ids,quantity='1');second=self.priced(ids,quantity='1')
  self.assertEqual(self.record(ids,first),'recorded')
  self.assertEqual(self.record(ids,first),'replayed')
  self.assertEqual(self.record(ids,first,'GiobbyPurchaseOrder-302'),'conflict','a different reference cannot replace the outcome')
  self.assertEqual(self.record(ids,second),'conflict','one external order confirms at most one intent')
  self.assertEqual(self.pending(),[f"{ids['tenant']}|{ids['companies'][0]}|{second}"])
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outcomes'),'1')
 def test_record_rejects_unpriced_unknown_and_malformed(self):
  ids=self.freeze_world();legacy=str(uuid.uuid4());self.assertEqual(self.purchase(ids,command=legacy,quantity='1')['state'],'applied')
  self.assertEqual(self.record(ids,legacy),'not_priced')
  self.assertEqual(self.record(ids,str(uuid.uuid4())),'not_found')
  intent=self.priced(ids)
  for bad in ('', ' x','a b','-x','x'*65,'x;DROP'):
   self.assertEqual(self.record(ids,intent,bad),'invalid',bad)
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outcomes'),'0')
 def test_outcomes_are_insert_only_even_for_the_owner(self):
  ids=self.freeze_world();intent=self.priced(ids);self.assertEqual(self.record(ids,intent),'recorded')
  for statement in ("UPDATE inventory.purchase_intent_outcomes SET \"ExternalReference\"='x'",'DELETE FROM inventory.purchase_intent_outcomes','TRUNCATE inventory.purchase_intent_outcomes'):
   with self.assertRaises(Exception,msg=statement):self.sql(self.ctx(ids)+statement+'; COMMIT;')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outcomes'),'1')
 def test_concurrent_identical_outcomes_record_once(self):
  ids=self.freeze_world();intent=self.priced(ids)
  with concurrent.futures.ThreadPoolExecutor(4) as pool:results=sorted(pool.map(lambda _:self.record(ids,intent),range(4)))
  self.assertEqual(results,['recorded','replayed','replayed','replayed']);self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outcomes'),'1')
 def dispatch_row(self,ids,intent,tenant=None):
  t=tenant or ids['tenant']
  return f"INSERT INTO integrations.purchase_dispatches(\"IntentId\",\"TenantId\",\"LegalEntityId\",\"State\",\"Attempts\",\"NextAttemptAt\",\"UpdatedAt\") VALUES('{intent}','{t}','{ids['companies'][0]}','Queued',0,now(),now());"
 def test_dispatch_state_is_tenant_isolated_technical_and_not_an_outcome(self):
  ids=self.freeze_world();intent=self.priced(ids);other=str(uuid.uuid4())
  self.sql(f"BEGIN; SELECT set_config('app.tenant_id','{ids['tenant']}',true);"+self.dispatch_row(ids,intent)+'COMMIT;',app=True)
  self.assertEqual(self.sql(f"BEGIN; SELECT set_config('app.tenant_id','{other}',true); SELECT count(*) FROM integrations.purchase_dispatches; COMMIT;",app=True).splitlines()[-1],'0')
  with self.assertRaises(Exception):self.sql(f"BEGIN; SELECT set_config('app.tenant_id','{other}',true);"+self.dispatch_row(ids,str(uuid.uuid4()))+'COMMIT;',app=True)
  with self.assertRaises(Exception):self.sql(f"BEGIN; SELECT set_config('app.tenant_id','{ids['tenant']}',true); UPDATE integrations.purchase_dispatches SET \"TenantId\"='{other}'; COMMIT;",app=True)
  with self.assertRaises(Exception):self.sql(f"BEGIN; SELECT set_config('app.tenant_id','{ids['tenant']}',true); UPDATE integrations.purchase_dispatches SET \"State\"='Exploded'; COMMIT;",app=True)
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.purchase_intent_outcomes'),'0','a dispatch row confirms nothing')
if __name__=='__main__':unittest.main()
