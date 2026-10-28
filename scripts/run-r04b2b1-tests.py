#!/usr/bin/env python3
"""D91 isolated TLS/OIDC/Chromium/API/PostgreSQL acceptance; no external traffic or retained resources."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);assert spec and spec.loader
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
purchase=load('purchase','scripts/run-r04b2a-tests.py')
binding=purchase.binding
binding.SPEC='r04b2b1-acceptance.cjs'
binding.r00.CONFIG=ROOT/'compose.r04b2b1-test.yaml'
base=binding.fixtures
controller={}
def fixtures(state,secret):
 sql=base(state,secret);browser=json.loads((state/'browser.json').read_text());ctx=browser['contexts'][0]
 t,c=ctx['tenantId'],ctx['legalEntityId'];actor,identity,proof=[str(uuid.uuid4()) for _ in range(3)]
 supplier=json.loads((state/'purchase-fixture.json').read_text())['supplier']
 browser['purchasePrices']={'supplierId':supplier,'catalogItemId':browser['workshop'][0]['partId']}
 (state/'browser.json').chmod(0o600);(state/'browser.json').write_text(json.dumps(browser));(state/'browser.json').chmod(0o444)
 grants=[]
 for action in ('catalog.purchase-prices.read','catalog.purchase-prices.manage'):
  grants.append(dict(commandId=str(uuid.uuid4()),tenantId=t,legalEntityId=c,actorMembershipId=actor,targetMembershipId=browser['adminMembershipId'],verificationReference=proof,expectedRevision=0,action=action,operation='grant'))
 (state/'price-grants.json').write_text(json.dumps(grants))
 return sql+f"""
 INSERT INTO organization_access.external_identity_bindings VALUES ('{identity}','https://synthetic.test','price-owner-{identity}');
 INSERT INTO organization_access.memberships VALUES ('{actor}','{t}','{identity}');
 INSERT INTO organization_access.capability_activations VALUES ('{c}','catalog',true);
 """
def control(action,state,query,fixture,holders):
 if not action.startswith('price-'):return False
 run=binding.run;ctx=fixture['contexts'][0];t,c=ctx['tenantId'],ctx['legalEntityId'];member=fixture['adminMembershipId']
 def sql(statement):return run(query+['-c',statement]).strip()
 if action=='price-owner-grants':
  command=query[:query.index('exec')]
  for value in json.loads((state/'price-grants.json').read_text()):
   path=state/'public/price-grant.json';path.write_text(json.dumps(value));path.chmod(0o444)
   for _ in range(2):
    output=run(command+['run','--rm','--no-deps','-T','--entrypoint','python3','migrator','scripts/owner-purchase-price-grant.py','/run/tls/price-grant.json'])
    assert 'exact immutable audit read back' in output
   path.chmod(0o600)
  assert sql('SELECT count(*) FROM organization_access.purchase_price_grant_history')=='2'
 elif action=='price-counts':
  (state/'control/price-counts.json').write_text(sql("""SELECT json_build_object('prices',(SELECT count(*) FROM catalog.supplier_purchase_price_history),'grants',(SELECT count(*) FROM organization_access.purchase_price_grant_history),'intents',(SELECT count(*) FROM inventory.purchase_intents),'held',(SELECT count(*) FROM inventory.purchase_intent_outbox WHERE "State"='Held'),'salesOutbox',(SELECT count(*) FROM workshop.administrative_outbox))"""))
 elif action=='price-intent-hash':
  (state/'control/price-intent-hash.json').write_text(sql('''SELECT json_build_object('intents',(SELECT json_agg(md5(row_to_json(i)::text) ORDER BY "Id") FROM inventory.purchase_intents i),'outbox',(SELECT json_agg(row_to_json(o) ORDER BY "IntentId") FROM inventory.purchase_intent_outbox o))'''))
 elif action=='price-capture-layout':
  import os,shutil
  target=Path(os.environ['TMPDIR'])/'r04b2b1-logs'/('evidence-pool'+binding.POOL);target.mkdir(parents=True,exist_ok=True)
  for image in (state/'control').glob('price-layout-*.png'):shutil.copyfile(image,target/image.name)
 elif action.startswith('price-row:'):
  command=str(uuid.UUID(action.split(':')[1]))
  (state/'control/price-row.json').write_text(sql(f'''SELECT row_to_json(h)::jsonb||jsonb_build_object('UnitPurchasePrice',"UnitPurchasePrice"::text) FROM catalog.supplier_purchase_price_history h WHERE "CommandId"='{command}';'''))
 elif action=='price-hold-master':
  holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);holders.append(holder)
  holder.stdin.write(f"BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('master-authority:{t}',0)); SELECT pg_backend_pid();\n\\echo LOCKED\n");holder.stdin.flush()
  output=binding.marker(holder,b'LOCKED').splitlines();controller.update(holder=holder,pid=int([x for x in output if x.isdigit()][-1]))
 elif action.startswith('price-wait:'):
  required=int(action.split(':')[1]);assert required in (1,2);pid=controller['pid'];stop=time.monotonic()+10
  while True:
   count=int(sql(f"WITH RECURSIVE chain(pid,blocker) AS (SELECT pid,unnest(pg_blocking_pids(pid)) FROM pg_stat_activity WHERE datname=current_database() UNION SELECT chain.pid,unnest(pg_blocking_pids(chain.blocker)) FROM chain) SELECT count(DISTINCT pid) FROM chain WHERE blocker={pid}"))
   if count>=required:break
   if time.monotonic()>stop:raise TimeoutError('price physical connection barrier not reached')
   time.sleep(.03)
  print(f'PRICE_PHYSICAL_BARRIER controller={pid} waiters={count}',flush=True)
 elif action=='price-release':
  holder=controller['holder'];holder.stdin.write('COMMIT;\n\\q\n');holder.stdin.flush();holder.stdin.close();holder.wait(timeout=5)
 elif action.startswith('price-fault:'):
  mode=action.split(':')[1];assert mode in ('on','deferred','off')
  if mode=='off':sql('DROP TRIGGER IF EXISTS price_fixture_fault ON catalog.supplier_purchase_price_history; DROP FUNCTION IF EXISTS catalog.price_fixture_fault();')
  else:sql(f"""CREATE FUNCTION catalog.price_fixture_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'isolated price rollback fixture'; END $$;
   CREATE {'CONSTRAINT ' if mode=='deferred' else ''}TRIGGER price_fixture_fault AFTER INSERT ON catalog.supplier_purchase_price_history {'DEFERRABLE INITIALLY DEFERRED ' if mode=='deferred' else ''}FOR EACH ROW EXECUTE FUNCTION catalog.price_fixture_fault();""")
 elif action.startswith('price-permission:'):
  _,name,mode=action.split(':');assert name in ('read','manage') and mode in ('deny','allow');permission='catalog.purchase-prices.'+name
  if mode=='deny':
   data=sql(f'''SELECT row_to_json(p) FROM organization_access.company_permissions p WHERE "MembershipId"='{member}' AND "LegalEntityId"='{c}' AND "Permission"='{permission}' AND "SiteId" IS NULL AND "WarehouseId" IS NULL;''');assert data
   (state/('price-'+name+'.json')).write_text(data)
   sql(f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{member}' AND "LegalEntityId"='{c}' AND "Permission"='{permission}';''')
  else:
   data=(state/('price-'+name+'.json')).read_text().replace("'","''")
   sql(f"INSERT INTO organization_access.company_permissions SELECT * FROM jsonb_populate_record(NULL::organization_access.company_permissions,'{data}'::jsonb)")
 elif action.startswith('price-capability:'):
  enabled=action.split(':')[1];assert enabled in ('true','false');sql(f'''UPDATE organization_access.capability_activations SET "Enabled"={enabled} WHERE "LegalEntityId"='{c}' AND "Capability"='catalog';''')
 else:raise ValueError('unknown price fixture control')
 return True
binding.fixtures=fixtures
binding.EXTRA_CONTROL=control
if __name__=='__main__':binding.main()
