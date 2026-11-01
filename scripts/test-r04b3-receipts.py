#!/usr/bin/env python3
"""D86/D93/D94 receiving contracts, synthetic ephemeral PostgreSQL only."""
import importlib.util,json,os,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dispatch',ROOT/'scripts/test-r04b2b3-dispatch.py');assert spec and spec.loader
dispatch=importlib.util.module_from_spec(spec);spec.loader.exec_module(dispatch)
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated PostgreSQL required')
class ReceiptSqlTests(unittest.TestCase):
 for _name,_value in vars(dispatch.DispatchSqlTests).items():
  if not _name.startswith('test_') and callable(_value) and not _name.startswith('__'):locals()[_name]=_value
 del _name,_value
 def test_receiving_surface_is_distinct_from_purchase(self):
  self.freeze_world()
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.set_receipt_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,integer,text)') IS NOT NULL"),'t','dedicated owner-only receiving grant is absent')
 def receipt_world(self):
  ids=self.freeze_world();ids['ownerMember']=str(uuid.uuid4());identity=str(uuid.uuid4())
  self.sql(f'''INSERT INTO organization_access.capability_activations VALUES ('{ids['companies'][0]}','external-administration',true); INSERT INTO organization_access.external_identity_bindings VALUES ('{identity}','https://synthetic.test','owner-{identity}'); INSERT INTO organization_access.memberships VALUES ('{ids['ownerMember']}','{ids['tenant']}','{identity}');''')
  return ids
 def grant(self,ids,command=None,expected=0,operation='grant',app=False,**changes):
  a=dict(tenant=ids['tenant'],company=ids['companies'][0],site=ids['site'],warehouse=ids['warehouse'],actor=ids['ownerMember'],target=ids['member'],verification=ids['proof']);a.update(changes)
  q=lambda v:"NULL" if v is None else "'"+str(v)+"'"
  context=self.app_prefix(ids,ids['companies'][0]) if app else f"SET ROLE {self.owner}; BEGIN; SELECT set_config('app.tenant_id','{ids['tenant']}',true),set_config('app.legal_entity_id','{ids['companies'][0]}',true);"
  return self.sql(context+f"SELECT organization_access.set_receipt_grant('{command or uuid.uuid4()}',{','.join(q(a[k]) for k in ('tenant','company','site','warehouse','actor','target','verification'))},{expected},'{operation}'); COMMIT;",app=app).splitlines()[-1]
 def test_owner_offline_grant_records_exact_scope_and_immutable_audit(self):
  ids=self.receipt_world();command=str(uuid.uuid4())
  self.assertEqual(self.grant(ids,command),'applied','verified owner path must grant the dedicated receiving action')
  self.assertEqual(self.grant(ids,command),'replayed')
  self.assertEqual(self.sql(f'''SELECT "Permission"||'|'||"SiteId"||'|'||"WarehouseId" FROM organization_access.company_permissions WHERE "Permission"='inventory.receipts.create';'''),f"inventory.receipts.create|{ids['site']}|{ids['warehouse']}")
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.receipt_grant_history'),'1')
  self.assertEqual(self.grant(ids,expected=1,operation='revoke'),'applied')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.company_permissions WHERE "Permission"=\'inventory.receipts.create\''),'0')
 def test_receiving_sources_require_dedicated_grant_not_purchase_permission(self):
  ids=self.receipt_world();source=self.confirmed(ids)
  # Resolve through to_regprocedure first: missing surface is reported explicitly, not a SQL setup error.
  exists=self.sql("SELECT to_regprocedure('inventory.receipt_sources(uuid,uuid,uuid)') IS NOT NULL")
  self.assertEqual(exists,'t','dedicated receiving source read is absent (surface RED only)')
  def read():return json.loads(self.sql(self.app_prefix(ids,ids['companies'][0])+f"SELECT inventory.receipt_sources('{ids['order']}','{ids['line']}','{ids['warehouse']}')::text; COMMIT;",app=True).splitlines()[-1])
  self.assertEqual(read(),{'state':'forbidden'})
 def test_receiving_sources_return_only_confirmed_frozen_lines_without_purchase_grant(self):
  ids=self.receipt_world();source=self.confirmed(ids);self.grant(ids)
  self.sql('''DELETE FROM organization_access.company_permissions WHERE "Permission"='inventory.purchase-intents.create';''')
  def read(order=None,line=None,warehouse=None):return json.loads(self.sql(self.app_prefix(ids,ids['companies'][0])+f"SELECT inventory.receipt_sources('{order or ids['order']}','{line or ids['line']}','{warehouse or ids['warehouse']}')::text; COMMIT;",app=True).splitlines()[-1])
  got=read();self.assertEqual(got['state'],'ready','dedicated receiving grant must discover confirmed source without purchasing rights')
  self.assertEqual(got['sources'],[dict(id=source,orderedQuantity='3.000000',unitPurchasePrice='12.345678',externalOrderReference='GiobbyPurchaseOrder-301',supplierName='Supplier candidate',description='Part')])
  self.assertEqual(read(warehouse=str(uuid.uuid4())),{'state':'forbidden'})
  self.assertEqual(read(order=str(uuid.uuid4())),{'state':'not_found'})
  self.sql('''DELETE FROM organization_access.company_permissions WHERE "Permission"='inventory.receipts.create';''');self.assertEqual(read(),{'state':'forbidden'})
 def test_receipt_intent_surface(self):
  self.freeze_world()
  self.assertEqual(self.sql("SELECT to_regprocedure('inventory.create_receipt_intent(uuid,uuid,text,jsonb)') IS NOT NULL"),'t','receipt command surface absent')
 def test_owner_grant_cannot_self_grant_or_extend_d77_or_untrusted_scope(self):
  ids=self.receipt_world()
  for changes in ({'actor':ids['member']},{'target':str(uuid.uuid4())},{'site':str(uuid.uuid4())},{'warehouse':str(uuid.uuid4())},{'tenant':str(uuid.uuid4())},{'company':ids['companies'][1]}):
   with self.subTest(changes=changes):self.assertEqual(self.grant(ids,**changes),'forbidden')
  for changes in ({'verification':None},{'verification':str(uuid.UUID(int=0))}):self.assertEqual(self.grant(ids,**changes),'invalid')
  with self.assertRaises(AssertionError):self.grant(ids,app=True)
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.receipt_grant_history'),'0')
 def receive_sql(self,ids,source,command=None,quantity='2',destination=None):
  d=destination or dict(self.good_destination(ids),kind='GiobbyReceiptV1',fingerprint='b'*64)
  return f"SELECT inventory.create_receipt_intent('{command or uuid.uuid4()}','{source}','{quantity}','{json.dumps(d)}'::jsonb)::text;"
 def receive(self,ids,source,**changes):
  return json.loads(self.sql(self.app_prefix(ids,ids['companies'][0])+self.receive_sql(ids,source,**changes)+'COMMIT;',app=True).splitlines()[-1])
 def confirmed(self,ids,quantity='3'):
  source=self.priced(ids,quantity=quantity);self.assertEqual(self.record(ids,source),'recorded');return source
 def test_receipt_freezes_confirmed_source_and_original_purchase_price_atomically(self):
  ids=self.receipt_world();self.assertEqual(self.grant(ids),'applied');source=self.confirmed(ids)
  command=str(uuid.uuid4());got=self.receive(ids,source,command=command,quantity='0.123456')
  self.assertEqual(got['state'],'applied','dedicated receiving grant must create the receipt intent')
  row=json.loads(self.sql(f'''SELECT to_jsonb(r) FROM inventory.receipt_intents r WHERE "Id"='{command}';'''))
  self.assertEqual(row['Quantity'],0.123456);self.assertEqual(row['SourceIntentId'],source)
  self.assertEqual(row['Snapshot']['quantity'],'0.123456');self.assertEqual(row['Snapshot']['unitPrice'],'12.345678')
  self.assertEqual(row['Snapshot']['externalOrderReference'],'GiobbyPurchaseOrder-301')
  self.assertEqual(row['Snapshot']['supplier']['vendorId'],'4711');self.assertEqual(row['WarehouseId'],ids['warehouse'])
  self.assertEqual(row['Destination']['fingerprint'],'b'*64)
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.receipt_outbox'),'1')
  self.assertEqual(self.sql('SELECT sum("Quantity") FROM inventory.purchase_intents'),'3.000000','D90 is never replenished')
 def test_cumulative_receiving_cap_counts_reserved_commands_across_new_uuids(self):
  ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids)
  self.assertEqual(self.receive(ids,source,quantity='2')['state'],'applied')
  self.assertEqual(self.receive(ids,source,quantity='2')['state'],'exceeds_remaining','a new UUID cannot reset the confirmed-line cap')
  self.assertEqual(self.receive(ids,source,quantity='1')['state'],'applied')
  self.assertEqual(self.sql('SELECT sum("Quantity") FROM inventory.receipt_intents'),'3.000000')
 def test_exact_replay_returns_original_snapshot_after_source_list_and_destination_edits(self):
  ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids);command=str(uuid.uuid4())
  first=self.receive(ids,source,command=command,quantity='2')
  self.listed(ids,price='99',revision=1)
  changed=dict(self.good_destination(ids),kind='GiobbyReceiptV1',fingerprint='c'*64)
  second=self.receive(ids,source,command=command,quantity='2',destination=changed)
  self.assertEqual(second,dict(first,state='replayed'),'exact replay must retain the first frozen price/destination and consume no more budget')
  self.assertEqual(self.receive(ids,source,command=command,quantity='1')['state'],'conflict')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.receipt_intents'),'1');self.assertEqual(self.sql('SELECT count(*) FROM inventory.receipt_outbox'),'1')
 def test_physical_source_budget_lock_serializes_distinct_uuids(self):
  ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids)
  self.assertEqual(self.receive(ids,source,quantity='2')['state'],'applied')
  holder,pid,_=self.hold(ids,f"BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('receipt-source:{ids['tenant']}:{source}',0));",app=False)
  contenders=[self.process(ids,self.app_prefix(ids,ids['companies'][0])+self.receive_sql(ids,source,quantity='1')+'COMMIT;') for _ in range(2)]
  try:self.waiters(pid,2)
  finally:self.release(holder)
  self.assertEqual(sorted(json.loads(self.finish(p))['state'] for p in contenders),['applied','exceeds_remaining'])
  self.assertEqual(self.sql('SELECT sum("Quantity") FROM inventory.receipt_intents'),'3.000000')
 def test_foreign_command_uuid_is_controlled_conflict_without_foreign_snapshot(self):
  a=self.receipt_world();b=self.receipt_world();self.grant(a);self.grant(b);sa=self.confirmed(a);sb=self.confirmed(b);command=str(uuid.uuid4())
  self.assertEqual(self.receive(a,sa,command=command)['state'],'applied')
  self.assertEqual(self.receive(b,sb,command=command),{'state':'conflict'})
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.receipt_intents'),'1')
 def test_regression_purchase_permission_and_partial_receiving_scopes_never_authorize_receiving(self):
  ids=self.receipt_world();source=self.confirmed(ids);t,c,s,w,m=(ids['tenant'],ids['companies'][0],ids['site'],ids['warehouse'],ids['member'])
  self.assertEqual(self.receive(ids,source)['state'],'forbidden','purchase-only membership lacks receiving')
  for site,warehouse in ((None,None),(s,None),(None,w),(s,str(uuid.uuid4()))):
   self.sql(f'''DELETE FROM organization_access.company_permissions WHERE "Permission"='inventory.receipts.create'; INSERT INTO organization_access.company_permissions VALUES('{uuid.uuid4()}','{m}','{t}','{c}','inventory.receipts.create',{('NULL' if site is None else chr(39)+site+chr(39))},{('NULL' if warehouse is None else chr(39)+warehouse+chr(39))});''')
   self.assertEqual(self.receive(ids,source)['state'],'forbidden')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.receipt_intents'),'0')
 def test_regression_numeric_and_unconfirmed_source_and_missing_destination_are_refused(self):
  ids=self.receipt_world();self.grant(ids);source=self.priced(ids,quantity='3')
  self.assertEqual(self.receive(ids,source)['state'],'source_unconfirmed');self.record(ids,source)
  for q in ('0','-1','1.0000001','1000000','1e1',' 1','NaN',''):
   with self.subTest(q=q):self.assertEqual(self.receive(ids,source,quantity=q)['state'],'invalid')
  self.assertEqual(self.receive(ids,source,command=str(uuid.UUID(int=0)))['state'],'invalid')
  for d in ({'kind':'SimulatorV1'},dict(self.good_destination(ids),kind='GiobbyReceiptV1',siteId=str(uuid.uuid4())),dict(self.good_destination(ids),kind='GiobbyReceiptV1',stockSourceId=str(uuid.uuid4()))):
   self.assertEqual(self.receive(ids,source,destination=d)['state'],'destination_unavailable')
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.receipt_intents'),'0')
 def test_regression_receipt_facts_and_grant_audit_are_force_rls_and_immutable(self):
  ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids);self.receive(ids,source)
  for table in ('inventory.receipt_intents','inventory.receipt_outbox','organization_access.receipt_grant_history'):
   self.assertEqual(self.sql(f"SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='{table}'::regclass"),'t')
   for privilege in ('SELECT','INSERT','UPDATE','DELETE','TRUNCATE'):self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','{table}','{privilege}')"),'f')
   for statement in (f'UPDATE {table} SET "TenantId"="TenantId"',f'DELETE FROM {table}'):
    with self.assertRaises(AssertionError):self.sql(statement)
  self.assertEqual(self.sql("SELECT has_function_privilege('runtime_app','organization_access.set_receipt_grant(uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid,integer,text)','EXECUTE')"),'f')
 def test_regression_atomic_receipt_and_outbox_rollback_at_insert_and_deferred_commit(self):
  import subprocess
  ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids)
  for table in ('receipt_intents','receipt_outbox'):
   for deferred in (False,True):
    with self.subTest(table=table,deferred=deferred):
     self.sql(f'''CREATE FUNCTION inventory.receipt_fixture_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'isolated receipt rollback fixture'; END $$; CREATE {'CONSTRAINT ' if deferred else ''}TRIGGER receipt_fixture_fault AFTER INSERT ON inventory.{table} {'DEFERRABLE INITIALLY DEFERRED ' if deferred else ''}FOR EACH ROW EXECUTE FUNCTION inventory.receipt_fixture_fault();''')
     try:
      result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input=self.app_prefix(ids,ids['companies'][0])+self.receive_sql(ids,source)+'COMMIT;',env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD']),text=True,capture_output=True,timeout=15)
      self.assertNotEqual(result.returncode,0);self.assertIn('isolated receipt rollback fixture',result.stderr)
     finally:self.sql(f'DROP TRIGGER receipt_fixture_fault ON inventory.{table}; DROP FUNCTION inventory.receipt_fixture_fault();')
     self.assertEqual(self.sql('SELECT (SELECT count(*) FROM inventory.receipt_intents)+(SELECT count(*) FROM inventory.receipt_outbox)'),'0')
 def test_regression_receiving_grant_revocation_both_physical_orderings(self):
  for revoke_first in (True,False):
   ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids);command=str(uuid.uuid4())
   revoke=f'''BEGIN; DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{ids['member']}' AND "Permission"='inventory.receipts.create';'''
   receive=self.app_prefix(ids,ids['companies'][0])+self.receive_sql(ids,source,command=command)
   holder,pid,_=self.hold(ids,revoke if revoke_first else receive,app=not revoke_first)
   contender=self.process(ids,(receive if revoke_first else revoke)+'COMMIT;',app=revoke_first)
   try:self.waiters(pid,1)
   finally:self.release(holder)
   result=self.finish(contender)
   if revoke_first:self.assertEqual(json.loads(result)['state'],'forbidden')
   self.assertEqual(self.sql('SELECT count(*) FROM inventory.receipt_intents'),'0' if revoke_first else '1')
   self.assertEqual(self.receive(ids,source,command=command)['state'],'forbidden')
 def test_receipt_confirmed_outcome_keeps_capacity_and_exact_replay(self):
  ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids);command=str(uuid.uuid4())
  first=self.receive(ids,source,command=command,quantity='2')
  self.assertEqual(self.sql("SELECT to_regprocedure('inventory.record_receipt_outcome(uuid,uuid,uuid,text)') IS NOT NULL"),'t','receipt outcome contract absent')
  context=self.ctx(ids)
  def record(ref='GiobbyReceipt-902'):
   return self.sql(context+f"SELECT inventory.record_receipt_outcome('{ids['tenant']}','{ids['companies'][0]}','{command}','{ref}'); COMMIT;",app=True).splitlines()[-1]
  self.assertEqual(record(),'recorded');self.assertEqual(record(),'replayed');self.assertEqual(record('GiobbyReceipt-903'),'conflict')
  self.assertEqual(self.receive(ids,source,quantity='2')['state'],'exceeds_remaining')
  self.assertEqual(self.receive(ids,source,quantity='1')['state'],'applied')
  self.assertEqual(self.receive(ids,source,command=command,quantity='2'),dict(first,state='replayed'))
  self.assertEqual(self.sql('SELECT sum("Quantity") FROM inventory.purchase_intents'),'3.000000')
 def test_receipt_state_reads_atomic_accepted_and_uncertain_non_authoritative_overlay(self):
  ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids);command=str(uuid.uuid4());self.receive(ids,source,command=command,quantity='2')
  self.assertEqual(self.sql("SELECT to_regprocedure('inventory.receipt_state(uuid)') IS NOT NULL"),'t','receipt readout absent')
  def read():return json.loads(self.sql(self.app_prefix(ids,ids['companies'][0])+f"SELECT inventory.receipt_state('{source}')::text; COMMIT;",app=True).splitlines()[-1])
  got=read();self.assertEqual(got['state'],'ready','authorized source needs a coherent receipt projection');self.assertEqual((got['acceptedQuantity'],got['uncertainQuantity'],got['remainingQuantity']),('0.000000','2.000000','1.000000'))
  self.assertTrue(got['nonAuthoritative']);self.assertIsNone(got['erpPerOrderResidual']);self.assertEqual(got['precisionDiscrepancy'],'receipt_q6_stock_report_q5_observed')
  self.sql(self.ctx(ids)+f"SELECT inventory.record_receipt_outcome('{ids['tenant']}','{ids['companies'][0]}','{command}','GiobbyReceipt-902'); COMMIT;",app=True)
  got=read();self.assertEqual((got['acceptedQuantity'],got['uncertainQuantity'],got['remainingQuantity']),('2.000000','0.000000','1.000000'))
  self.sql(f'''DELETE FROM organization_access.company_permissions WHERE "Permission"='inventory.receipts.create';''')
  self.assertEqual(read(),{'state':'forbidden'})
 def test_receipt_outbox_exposes_only_frozen_facts_and_unconfirmed_envelopes(self):
  ids=self.receipt_world();self.grant(ids);source=self.confirmed(ids);command=str(uuid.uuid4());self.receive(ids,source,command=command)
  self.assertEqual(self.sql("SELECT to_regprocedure('inventory.pending_receipt_dispatch(integer,integer)') IS NOT NULL AND to_regprocedure('inventory.read_receipt_dispatch(uuid,uuid,uuid)') IS NOT NULL"),'t','receipt worker public contracts absent')
  raw=self.sql(self.ctx(ids)+f"SELECT coalesce(inventory.read_receipt_dispatch('{ids['tenant']}','{ids['companies'][0]}','{command}')::text,'null'); COMMIT;",app=True).splitlines()[-1]
  self.assertNotEqual(raw,'null','frozen receipt payload must be available to the worker');got=json.loads(raw)
  self.assertEqual((got['receiptId'],got['quantity'],got['unitPrice'],got['fingerprint']),(command,'2.000000','12.345678','b'*64))
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.pending_receipt_dispatch(20,0)',app=True),'1')
  self.sql(self.ctx(ids)+f"SELECT inventory.record_receipt_outcome('{ids['tenant']}','{ids['companies'][0]}','{command}','GiobbyReceipt-902'); COMMIT;",app=True)
  self.assertEqual(self.sql('SELECT count(*) FROM inventory.pending_receipt_dispatch(20,0)',app=True),'0')
class ReceiptOwnerInputTests(unittest.TestCase):
 def test_closed_explicit_owner_scope_validation_refuses_self_grant_and_malformed_commands(self):
  spec=importlib.util.spec_from_file_location('receipt_owner',ROOT/'scripts/owner-receipt-grant.py');owner=importlib.util.module_from_spec(spec);spec.loader.exec_module(owner)
  value={k:str(uuid.uuid4()) for k in ('commandId','tenantId','legalEntityId','siteId','warehouseId','actorMembershipId','targetMembershipId','verificationReference')}
  value.update(expectedRevision=0,operation='grant');self.assertEqual(owner.validate(value),value)
  for bad in (dict(value,actorMembershipId=value['targetMembershipId']),dict(value,action='inventory.purchase-intents.create'),dict(value,verificationReference=str(uuid.UUID(int=0))),dict(value,expectedRevision=True),dict(value,operation='delegate'),dict(value,warehouseId='malformed')):
   with self.subTest(bad=bad),self.assertRaises(ValueError):owner.validate(bad)
if __name__=='__main__':unittest.main()
