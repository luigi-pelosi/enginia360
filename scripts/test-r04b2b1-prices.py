#!/usr/bin/env python3
"""D91 synthetic owning-module PostgreSQL acceptance; never ERP traffic."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('supplier',ROOT/'scripts/test-r04b1-supplier.py')
assert spec and spec.loader
supplier=importlib.util.module_from_spec(spec);spec.loader.exec_module(supplier)
class OwnerInputTests(unittest.TestCase):
 def tool(self):
  path=ROOT/'scripts/owner-purchase-price-grant.py'
  self.assertTrue(path.exists(),'owner CLI surface absent')
  spec=importlib.util.spec_from_file_location('price_grant_tool',path);assert spec and spec.loader
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
 def good(self):
  value={k:str(uuid.uuid4()) for k in ('commandId','tenantId','legalEntityId','actorMembershipId','targetMembershipId','verificationReference')}
  value.update(expectedRevision=0,action='catalog.purchase-prices.manage',operation='grant');return value
 def test_owner_cli_surface_accepts_closed_explicit_command(self):
  value=self.good();self.assertEqual(self.tool().validate(value),value)
 def test_owner_cli_rejects_noncanonical_extra_or_unsupported_grants_and_self_grant(self):
  value=self.good();tool=self.tool()
  for bad in ({},dict(value,extra='x'),dict(value,action='counterparties.common.edit'),dict(value,operation='delegate'),dict(value,expectedRevision=True),dict(value,expectedRevision=2147483648),dict(value,tenantId=value['tenantId'].upper()),dict(value,commandId=str(uuid.UUID(int=0))),dict(value,targetMembershipId=value['actorMembershipId'])):
   with self.subTest(bad=bad):
    with self.assertRaises(ValueError):tool.validate(bad)
 def test_owner_cli_refuses_unverified_tls_before_database_access(self):
  tool=self.tool();self.assertTrue(callable(getattr(tool,'apply',None)),'owner CLI apply surface absent')
  from unittest.mock import patch
  with patch.dict(os.environ,{'PGSSLMODE':'disable'},clear=False),patch('subprocess.run') as run:
   with self.assertRaises(ValueError):tool.apply(self.good())
   run.assert_not_called()

@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated PostgreSQL required')
class PriceSqlTests(unittest.TestCase):
 setUp=supplier.SupplierSqlTests.setUp
 tearDown=supplier.SupplierSqlTests.tearDown
 sql=supplier.SupplierSqlTests.sql
 start_migration=supplier.SupplierSqlTests.start_migration
 migrate=supplier.SupplierSqlTests.migrate
 world=supplier.SupplierSqlTests.world
 authority=supplier.SupplierSqlTests.authority
 app_prefix=supplier.SupplierSqlTests.app_prefix
 role=supplier.SupplierSqlTests.role
 def price_world(self):
  self.assertEqual(self.migrate()[0],0)
  ids=self.world();ids['item']=str(uuid.uuid4());t=ids['tenant'];c=ids['companies'][0];m=ids['member']
  self.sql(f'''INSERT INTO catalog.items VALUES ('{ids['item']}','{t}','{c}','Part','Synthetic part',1);
   INSERT INTO organization_access.capability_activations VALUES ('{c}','catalog',true);
   INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{m}','{t}','{c}','catalog.purchase-prices.read',NULL,NULL),('{uuid.uuid4()}','{m}','{t}','{c}','catalog.purchase-prices.manage',NULL,NULL);''')
  self.sql(self.app_prefix(ids)+self.role(ids,1,0)+'COMMIT;',app=True)
  return ids
 def read(self,ids,company=None,subject=None,item=None,record=None):
  c=company or ids['companies'][0]
  return json.loads(self.sql(self.app_prefix(ids,c,subject)+f"SELECT catalog.supplier_purchase_price_state('{c}','{record or ids['record']}','{item or ids['item']}')::text; COMMIT;",app=True).splitlines()[-1])
 def test_missing_lookup_surface_returns_no_fabricated_list_entry(self):
  ids=self.price_world()
  self.assertEqual(self.sql("SELECT to_regprocedure('catalog.supplier_purchase_price_state(uuid,uuid,uuid)') IS NOT NULL"),'t','supplier purchase-price lookup absent (surface RED only)')
  got=self.read(ids)
  self.assertEqual((got['state'],got['entry'],got['revision'],got['provisionalUnitPurchasePrice'],got['requiresManualPrice']),('ready',None,0,'0.000000',True))
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'0')
 def test_read_needs_exact_company_action_and_trusted_binding_not_admin_or_manage(self):
  ids=self.price_world();c=ids['companies'][0];m=ids['member'];t=ids['tenant']
  self.sql(f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{m}' AND "Permission"='catalog.purchase-prices.read';''')
  self.assertEqual(self.read(ids),{'state':'forbidden'},'valid trusted same-tenant manage/common-edit identity is not list-read')
  self.sql(f'''INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{m}','{t}','{c}','catalog.purchase-prices.read',NULL,NULL);''')
  self.assertEqual(self.read(ids,company=ids['companies'][1]),{'state':'forbidden'})
  self.assertEqual(self.read(ids,subject=str(uuid.uuid4())),{'state':'forbidden'})
  self.sql(f'''DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{ids['actor']}';''')
  self.assertEqual(self.read(ids),{'state':'forbidden'})
 def test_lookup_relates_current_supplier_and_tenant_catalog_without_erp_mapping(self):
  ids=self.price_world()
  self.assertEqual(self.read(ids,record=ids['other_record']),{'state':'not_supplier'})
  self.assertEqual(self.read(ids,item=str(uuid.uuid4())),{'state':'not_found'})
  self.assertEqual(self.read(ids,record=str(uuid.uuid4())),{'state':'not_found'})
  self.authority(ids,1,'ExternalToEnginia360')
  self.assertEqual(self.read(ids)['canManage'],False)
  self.assertEqual(self.read(ids)['writeState'],'master_external')
 def command_sql(self,ids,command=None,price='0',expected=0,company=None,**changes):
  a=dict(company=company or ids['companies'][0],supplier=ids['record'],item=ids['item'],command=command or str(uuid.uuid4()),expected=expected,supplierRevision=1,catalogVersion=1,authorityVersion=1,price=price);a.update(changes)
  return f"SELECT catalog.set_supplier_purchase_price('{a['company']}','{a['supplier']}','{a['item']}','{a['command']}',{a['expected']},{a['supplierRevision']},{a['catalogVersion']},{a['authorityVersion']},'{a['price']}')::text;"
 def write(self,ids,subject=None,**changes):
  return json.loads(self.sql(self.app_prefix(ids,changes.get('company',ids['companies'][0]),subject)+self.command_sql(ids,**changes)+'COMMIT;',app=True).splitlines()[-1])
 def test_explicit_zero_creates_audited_list_revision_not_missing(self):
  ids=self.price_world();command=str(uuid.uuid4())
  self.assertEqual(self.sql("SELECT to_regprocedure('catalog.set_supplier_purchase_price(uuid,uuid,uuid,uuid,integer,integer,integer,integer,text)') IS NOT NULL"),'t','write surface absent; later semantics need separate RED')
  got=self.write(ids,command=command)
  self.assertEqual(got,{'state':'applied','commandId':command,'revision':1})
  entry=json.loads(self.sql('SELECT row_to_json(h) FROM catalog.supplier_purchase_price_history h'))
  self.assertEqual((entry['UnitPurchasePrice'],entry['Revision'],entry['ActorMembershipId'],entry['SupplierRevision'],entry['CatalogVersion'],entry['AuthorityVersion']),(0,1,ids['member'],1,1,1))
 def test_read_present_zero_and_q6_with_history_not_provisional_absence(self):
  ids=self.price_world();self.write(ids)
  first=self.read(ids)
  self.assertEqual(first['revision'],1)
  self.assertEqual(first['entry']['unitPurchasePrice'],'0.000000')
  self.assertFalse(first['requiresManualPrice']);self.assertIsNone(first['provisionalUnitPurchasePrice'])
  self.write(ids,expected=1,price='123.456789')
  second=self.read(ids)
  self.assertEqual((second['revision'],second['entry']['unitPurchasePrice']),(2,'123.456789'))
  self.assertEqual([(h['revision'],h['unitPurchasePrice']) for h in second['history']],[(2,'123.456789'),(1,'0.000000')])
 def test_manage_is_exact_company_action_and_disabled_capability_retains_history(self):
  ids=self.price_world();self.write(ids);c=ids['companies'][0];m=ids['member'];t=ids['tenant']
  self.sql(f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{m}' AND "Permission"='catalog.purchase-prices.manage';''')
  self.assertEqual(self.write(ids,expected=1)['state'],'forbidden','list read/common edit/admin is not exact price management')
  self.assertFalse(self.read(ids)['canManage'])
  for site,warehouse in [(str(uuid.uuid4()),None),(None,str(uuid.uuid4()))]:
   self.sql(f'''INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{m}','{t}','{c}','catalog.purchase-prices.manage',{("'"+site+"'") if site else 'NULL'},{("'"+warehouse+"'") if warehouse else 'NULL'});''')
   self.assertEqual(self.write(ids,expected=1)['state'],'forbidden')
  self.sql(f'''INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{m}','{t}','{c}','catalog.purchase-prices.manage',NULL,NULL);
   UPDATE organization_access.capability_activations SET "Enabled"=false WHERE "LegalEntityId"='{c}' AND "Capability"='catalog';''')
  self.assertEqual(self.write(ids,expected=1)['state'],'forbidden')
  self.assertEqual(self.read(ids)['entry']['unitPurchasePrice'],'0.000000');self.assertFalse(self.read(ids)['canManage'])
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'1')
 def test_write_requires_current_supplier_item_and_master_versions(self):
  for axis in ('supplier','item','supplierRevision','catalogVersion','authorityVersion'):
   with self.subTest(axis=axis):
    ids=self.price_world();change={'supplier':ids['other_record'],'item':str(uuid.uuid4()),'supplierRevision':0,'catalogVersion':2,'authorityVersion':2}
    self.assertEqual(self.write(ids,**{axis:change[axis]})['state'],'conflict')
  ids=self.price_world();self.authority(ids,1,'ExternalToEnginia360')
  self.assertEqual(self.write(ids,authorityVersion=2)['state'],'master_external')
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'0')
 def test_optimistic_revision_rejects_stale_and_skipped_versions(self):
  ids=self.price_world()
  self.assertEqual(self.write(ids,expected=9)['state'],'conflict')
  self.assertEqual(self.write(ids)['state'],'applied')
  self.assertEqual(self.write(ids,expected=0)['state'],'conflict')
  self.assertEqual(self.write(ids,expected=1,price='1.000001')['revision'],2)
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'2')
 def test_exact_uuid_payload_replay_after_new_price_returns_original_revision(self):
  ids=self.price_world();command=str(uuid.uuid4());self.write(ids,command=command,price='1.000001')
  self.write(ids,expected=1,price='2')
  self.assertEqual(self.write(ids,command=command,price='1.000001'),{'state':'replayed','commandId':command,'revision':1})
  self.assertEqual(self.write(ids,command=command,price='1.000002')['state'],'conflict')
  self.assertEqual(self.write(ids,command=command,price='1.000001',expected=1)['state'],'conflict')
  other=self.price_world()
  self.assertEqual(self.write(other,command=command,price='1.000001'),{'state':'conflict'})
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'2')
 def test_q6_transport_rejects_precision_exponent_negative_overflow_without_rows(self):
  for price in ('1.0000001','-1','1000000','1e2','NaN',' 1',''):
   with self.subTest(price=price):
    ids=self.price_world();self.assertEqual(self.write(ids,price=price),{'state':'invalid'})
  ids=self.price_world();self.assertEqual(self.write(ids,command=str(uuid.UUID(int=0))),{'state':'invalid'})
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'0')
  self.assertEqual(self.write(ids,price='999999.999999')['state'],'applied')
  self.assertEqual(self.read(ids)['entry']['unitPurchasePrice'],'999999.999999')
 def test_maximum_revision_is_controlled_conflict_without_overflow(self):
  ids=self.price_world()
  self.sql(f'''INSERT INTO catalog.supplier_purchase_price_history("CommandId","TenantId","LegalEntityId","SupplierId","CatalogItemId","Revision","UnitPurchasePrice","ActorMembershipId","SupplierRevision","CatalogVersion","AuthorityVersion","Payload") VALUES ('{uuid.uuid4()}','{ids['tenant']}','{ids['companies'][0]}','{ids['record']}','{ids['item']}',2147483647,1,'{ids['member']}',1,1,1,'{{}}');''')
  self.assertEqual(self.write(ids,expected=2147483647),{'state':'conflict'})
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'1')
 def test_company_prices_separate_shared_identity_and_foreign_sources_fail_closed(self):
  ids=self.price_world();self.write(ids,price='7.123456');t=ids['tenant'];m=ids['member'];c=ids['companies'][1]
  self.sql(f'''INSERT INTO organization_access.capability_activations VALUES ('{c}','catalog',true); INSERT INTO organization_access.company_permissions VALUES ('{uuid.uuid4()}','{m}','{t}','{c}','catalog.purchase-prices.read',NULL,NULL),('{uuid.uuid4()}','{m}','{t}','{c}','catalog.purchase-prices.manage',NULL,NULL);''')
  self.assertIsNone(self.read(ids,company=c)['entry'])
  self.assertEqual(self.write(ids,company=c,price='8')['state'],'applied')
  self.assertEqual(self.read(ids)['entry']['unitPurchasePrice'],'7.123456')
  self.assertEqual(self.read(ids,company=c)['entry']['unitPurchasePrice'],'8.000000')
  foreign=self.price_world()
  self.assertEqual(self.read(foreign,item=ids['item']),{'state':'not_found'})
  self.assertEqual(self.write(foreign,supplier=ids['record'])['state'],'conflict')
  for stmt in ['UPDATE catalog.supplier_purchase_price_history SET "Revision"="Revision"','DELETE FROM catalog.supplier_purchase_price_history','TRUNCATE catalog.supplier_purchase_price_history']:
   result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input=stmt+';',env=dict(os.environ,PGDATABASE=self.database),text=True,capture_output=True,timeout=10)
   self.assertNotEqual(result.returncode,0);self.assertIn('append-only',result.stderr)
  self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','catalog.supplier_purchase_price_history','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
 def process(self,ids,sql,app=True):
  env=dict(os.environ,PGDATABASE=self.database,PGAPPNAME='r04b2b1-proof')
  if app:env.update(PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  p=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
  self.addCleanup(lambda:(p.kill(),p.communicate()) if p.poll() is None else None)
  p.stdin.write(sql+'\n');p.stdin.flush();return p
 def finish(self,p):
  p.stdin.close();p.stdin=None
  out,err=p.communicate(timeout=15);self.assertEqual(p.returncode,0,err);return (out.strip().splitlines() or [''])[-1]
 def waiters(self,pid,count=1):
  deadline=time.monotonic()+5
  while time.monotonic()<deadline:
   rows=self.sql(f"WITH RECURSIVE chain(pid,blocker) AS (SELECT pid,unnest(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE datname=current_database() UNION SELECT chain.pid,unnest(pg_blocking_pids(chain.blocker)) FROM chain) SELECT count(DISTINCT pid) FROM chain WHERE blocker={pid}")
   if int(rows)>=count:
    print('PHYSICAL_BARRIER',pid,self.sql('SELECT pid||\':\'||pg_blocking_pids(pid)::text FROM pg_stat_activity WHERE cardinality(pg_blocking_pids(pid))>0'),flush=True);return
   time.sleep(.03)
  self.fail('separate physical connection failed to reach lock barrier')
 def release(self,p,commit=False):
  p.stdin.write(('COMMIT' if commit else 'ROLLBACK')+';\n');p.stdin.flush();return self.finish(p)
 def test_concurrent_exact_replay_and_new_revision_collision_have_one_audit_each(self):
  ids=self.price_world();t=ids['tenant'];c=ids['companies'][0]
  for expected,identical in [(0,True),(1,False)]:
   holder=self.process(ids,f"BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('master-authority:{t}',0)); SELECT pg_backend_pid();",app=False)
   holder.stdout.readline();pid=int(holder.stdout.readline());command=str(uuid.uuid4())
   a=self.process(ids,self.app_prefix(ids,c)+self.command_sql(ids,expected=expected,command=command)+'COMMIT;')
   b=self.process(ids,self.app_prefix(ids,c)+self.command_sql(ids,expected=expected,command=command if identical else str(uuid.uuid4()))+'COMMIT;')
   self.waiters(pid,2);self.release(holder)
   self.assertEqual(sorted(json.loads(self.finish(p))['state'] for p in (a,b)),['applied','replayed' if identical else 'conflict'])
  self.assertEqual(self.sql('SELECT count(*) FROM catalog.supplier_purchase_price_history'),'2')
 def test_coherent_read_waits_for_price_revision_commit(self):
  ids=self.price_world();c=ids['companies'][0]
  writer=self.process(ids,self.app_prefix(ids,c)+self.command_sql(ids,price='5.123456')+'SELECT pg_backend_pid();')
  writer.stdout.readline();json.loads(writer.stdout.readline());pid=int(writer.stdout.readline())
  read=self.process(ids,self.app_prefix(ids,c)+f"SELECT catalog.supplier_purchase_price_state('{c}','{ids['record']}','{ids['item']}')::text; COMMIT;")
  self.waiters(pid);self.release(writer,commit=True)
  result=json.loads(self.finish(read));self.assertEqual((result['revision'],result['entry']['revision'],result['entry']['unitPurchasePrice']),(1,1,'5.123456'))
 def owner_grant(self,ids,command=None,action='catalog.purchase-prices.manage',operation='grant',expected=0,actor=None,target=None):
  return self.sql(f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{ids['tenant']}',true),set_config('app.legal_entity_id','{ids['companies'][0]}',true); SELECT organization_access.set_purchase_price_grant('{command or uuid.uuid4()}','{ids['tenant']}','{ids['companies'][0]}','{actor or ids['grantActor']}','{target or ids['member']}','{ids['proof']}',{expected},'{action}','{operation}'); COMMIT;").splitlines()[-1]
 def grant_world(self):
  ids=self.price_world();ids['grantActor']=str(uuid.uuid4());identity=str(uuid.uuid4());t=ids['tenant']
  self.sql(f'''INSERT INTO organization_access.external_identity_bindings VALUES ('{identity}','https://synthetic.test','grant-{identity}'); INSERT INTO organization_access.memberships VALUES ('{ids['grantActor']}','{t}','{identity}'); DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{ids['member']}' AND "Permission"='catalog.purchase-prices.manage';''')
  return ids
 def test_owner_grant_surface_targets_existing_trusted_member_with_immutable_evidence(self):
  ids=self.grant_world();command=str(uuid.uuid4())
  self.assertEqual(self.sql("SELECT to_regprocedure('organization_access.set_purchase_price_grant(uuid,uuid,uuid,uuid,uuid,uuid,integer,text,text)') IS NOT NULL"),'t','owner grant surface absent')
  self.assertEqual(self.owner_grant(ids,command=command),'applied')
  self.assertEqual(self.write(ids)['state'],'applied')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.purchase_price_grant_history'),'1')
 def test_owner_grant_does_not_provision_or_self_grant_or_delegate_arbitrary_actions(self):
  for axis in ('unsupported','self','untrusted'):
   with self.subTest(axis=axis):
    ids=self.grant_world();changes={}
    if axis=='unsupported':changes['action']='counterparties.common.edit'
    if axis=='self':changes['actor']=ids['member']
    if axis=='untrusted':self.sql(f'''DELETE FROM organization_access.external_identity_bindings WHERE "InternalIdentityId"='{ids['actor']}';''')
    self.assertEqual(self.owner_grant(ids,**changes),'forbidden')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.purchase_price_grant_history'),'0')
  self.assertEqual(self.sql(f"SELECT has_function_privilege('{os.environ['R00_APP_USER']}','organization_access.set_purchase_price_grant(uuid,uuid,uuid,uuid,uuid,uuid,integer,text,text)','EXECUTE')"),'f')
 def test_owner_grants_are_optimistic_idempotent_and_revocable_not_new_mandates(self):
  ids=self.grant_world();command=str(uuid.uuid4())
  self.assertEqual(self.owner_grant(ids,expected=9),'conflict')
  self.assertEqual(self.owner_grant(ids,command=command),'applied')
  self.assertEqual(self.owner_grant(ids,command=command),'replayed')
  self.assertEqual(self.owner_grant(ids,command=command,operation='revoke'),'conflict')
  self.assertEqual(self.owner_grant(ids,expected=1,operation='revoke'),'applied')
  self.assertFalse(self.read(ids)['canManage']);self.assertEqual(self.write(ids)['state'],'forbidden')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.purchase_price_grant_history'),'2')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.delegation_mandates'),'0')
 def test_owner_grant_exact_replay_and_revoke_effect(self):
  ids=self.grant_world();command=str(uuid.uuid4());self.owner_grant(ids,command=command)
  self.assertEqual(self.owner_grant(ids,command=command),'replayed')
 def test_owner_grant_revoke_removes_only_exact_company_action(self):
  ids=self.grant_world();self.owner_grant(ids)
  self.assertEqual(self.owner_grant(ids,operation='revoke',expected=1),'applied')
  self.assertEqual(self.write(ids)['state'],'forbidden')
  self.assertEqual(self.read(ids)['state'],'ready')
 def test_owner_grant_refuses_empty_command_and_verification_without_permission_effect(self):
  ids=self.grant_world()
  self.assertEqual(self.owner_grant(ids,command=str(uuid.UUID(int=0))),'invalid')
  ids['proof']=str(uuid.UUID(int=0))
  self.assertEqual(self.owner_grant(ids),'invalid')
  self.assertEqual(self.sql('SELECT count(*) FROM organization_access.purchase_price_grant_history'),'0')
 def test_tenant_context_is_resolved_only_from_the_authenticated_identity(self):
  ids=self.price_world();c=ids['companies'][0]
  result=self.sql(f"BEGIN; SELECT set_config('app.identity_subject','{ids['actor']}',true); SELECT catalog.supplier_purchase_price_state('{c}','{ids['record']}','{ids['item']}')->>'state'; COMMIT;",app=True).splitlines()[-1]
  self.assertEqual(result,'ready')
  wrong=self.sql(f"BEGIN; SELECT set_config('app.tenant_id','{uuid.uuid4()}',true),set_config('app.identity_subject','{ids['actor']}',true); SELECT catalog.supplier_purchase_price_state('{c}','{ids['record']}','{ids['item']}')->>'state'; COMMIT;",app=True).splitlines()[-1]
  self.assertEqual(wrong,'forbidden')
 def test_write_resolves_tenant_after_identity_authorization_on_clean_connection(self):
  ids=self.price_world()
  got=self.sql(f"BEGIN; SELECT set_config('app.tenant_id','',true),set_config('app.identity_subject','{ids['actor']}',true);"+self.command_sql(ids)+'COMMIT;',app=True).splitlines()[-1]
  self.assertEqual(json.loads(got)['state'],'applied')
 def test_supplier_catalog_authority_and_exact_grant_removal_both_physical_orderings(self):
  for axis in ('supplier','catalog','authority','grant'):
   for write_first in (False,True):
    with self.subTest(axis=axis,write_first=write_first):
     ids=self.price_world();c=ids['companies'][0];t=ids['tenant'];m=ids['member'];command=str(uuid.uuid4())
     if axis=='supplier':change=self.app_prefix(ids,c)+self.role(ids,1,1,supplier=False)
     if axis=='catalog':change=f'''BEGIN; UPDATE catalog.items SET "Version"=2 WHERE "Id"='{ids['item']}';'''
     if axis=='grant':change=f'''BEGIN; DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{m}' AND "LegalEntityId"='{c}' AND "Permission"='catalog.purchase-prices.manage';'''
     if axis=='authority':change=f"BEGIN; SET LOCAL ROLE {self.owner}; SELECT set_config('app.tenant_id','{t}',true); SELECT organization_access.establish_master_authority('{uuid.uuid4()}','{t}','{m}','{ids['proof']}',1,'ExternalToEnginia360','{ids['source']}','{ids['profile']}',ARRAY['{c}'::uuid]);"
     write=self.app_prefix(ids,c)+self.command_sql(ids,command=command)
     # A row-lock controller and app use separate PostgreSQL backends; the first holds its transaction open.
     first=self.process(ids,(write if write_first else change)+'SELECT pg_backend_pid();',app=write_first or axis=='supplier')
     # Read until the last server PID, preceded by a fixed end marker so setup SELECTs cannot be confused with a PID.
     first.stdin.write('\\echo READY\n');first.stdin.flush()
     lines=[]
     while True:
      raw=first.stdout.readline()
      if not raw:self.fail('controller failed before READY: '+first.stderr.read())
      line=raw.strip()
      if line=='READY':break
      lines.append(line)
     pid=int(lines[-1]);self.assertGreater(pid,0)
     second=self.process(ids,(change if write_first else write)+'COMMIT;',app=(axis=='supplier') if write_first else True)
     self.waiters(pid);self.release(first,commit=True);result=self.finish(second)
     if not write_first:self.assertEqual(json.loads(result)['state'],'forbidden' if axis=='grant' else 'master_external' if axis=='authority' else 'conflict')
     self.assertEqual(self.sql(f'''SELECT count(*) FROM catalog.supplier_purchase_price_history WHERE "SupplierId"='{ids['record']}';'''),'1' if write_first else '0')
     if write_first and axis=='grant':self.assertEqual(self.write(ids,command=command)['state'],'forbidden')
if __name__=='__main__':unittest.main()
