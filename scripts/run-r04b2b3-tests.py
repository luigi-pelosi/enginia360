#!/usr/bin/env python3
"""R04.b.2b.3 isolated TLS/OIDC/Chromium/API/PostgreSQL purchase-order dispatch acceptance; Giobby-protocol fake only, no live traffic."""
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import uuid
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('freeze_runner',ROOT/'scripts/run-r04b2b2-tests.py');assert spec and spec.loader
freeze=importlib.util.module_from_spec(spec);spec.loader.exec_module(freeze)
binding=freeze.binding
import os
SPECS=('r04b2b3-acceptance.cjs','r04b2b3-readout.cjs')  # dispatch behaviour vs PR2 Italian readout; separate command bounds
binding.SPEC=os.environ.get('R04B2B3_SPEC','r04b2b3-acceptance.cjs')
if binding.SPEC not in SPECS:raise ValueError('unknown purchase-order acceptance specification')
binding.r00.CONFIG=ROOT/'compose.r04b2b3-test.yaml'
base=binding.fixtures
controller={}
def fixtures(state,secret):
 sql=base(state,secret)
 browser=json.loads((state/'browser.json').read_text());part=browser['workshop'][0]['partId']
 host=json.loads((state/'giobby.json').read_text())
 # Explicit host purchase-order setup; absent in every earlier chain, so those chains never dispatch.
 host['ExternalAdministration']['Giobby']['PurchaseOrder']={'DocumentType':2,'OrderType':1,'BusinessUnit':'U1','Numerator':1,'PosType':1,'Payments':'none','Currency':'EUR','Vat':'22','Storage':'MB','Materials':{part:'owned-product-1'}}
 (state/'purchase-original.json').write_text(json.dumps(host['ExternalAdministration']['Giobby']['PurchaseOrder']))
 (state/'giobby.json').write_text(json.dumps(host))
 return sql
binding.fixtures=fixtures
def control(action,state,query,fixture,holders):
 if not action.startswith('po-'):return freeze.control(action,state,query,fixture,holders)
 command=query[:query.index('exec')]
 def sql(text):return binding.run(query+['-c',text]).strip()
 def simulator(path,body=None):
  args=command+['exec','-T','admin-simulator','python3','-I','-c',binding.SIMULATOR_CONTROL,path]+([body] if body is not None else [])
  return json.loads(binding.run(args,timeout=30))
 if action.startswith('po-config:'):
  mode=action.split(':')[1];assert mode in ('original','changed','missing')
  host=json.loads((state/'giobby.json').read_text());giobby=host['ExternalAdministration']['Giobby']
  giobby['PurchaseOrder']=json.loads((state/'purchase-original.json').read_text())
  if mode=='changed':giobby['PurchaseOrder']['Storage']='XX'
  elif mode=='missing':del giobby['PurchaseOrder']
  (state/'giobby.json').write_text(json.dumps(host))
  binding.run(command+['restart','api'],timeout=60)
 elif action.startswith('po-lease:'):
  _,intent,mode=action.split(':');intent=str(uuid.UUID(intent));assert mode in ('future','expired')
  delta="1 minute" if mode=='future' else "-1 minute"
  sql(f'''UPDATE integrations.purchase_dispatches SET "LeaseUntil"=clock_timestamp()+interval '{delta}',"NextAttemptAt"=clock_timestamp() WHERE "IntentId"='{intent}';''')
 elif action.startswith('po-mode:'):
  mode=action.split(':')[1];assert mode in ('complete','500','lost-response','lost-response-empty','empty','mismatch','redirect')
  simulator('/control/mode',json.dumps({'mode':mode}))
 elif action.startswith('po-state:'):
  intent=str(uuid.UUID(action.split(':')[1]))
  (state/'control/po-state.json').write_text(sql(f'''SELECT json_build_object('dispatch',(SELECT row_to_json(d) FROM integrations.purchase_dispatches d WHERE "IntentId"='{intent}'),'outcome',(SELECT row_to_json(o) FROM inventory.purchase_intent_outcomes o WHERE "IntentId"='{intent}'),'salesOutbox',(SELECT count(*) FROM workshop.administrative_outbox),'dispatches',(SELECT count(*) FROM integrations.purchase_dispatches),'outcomes',(SELECT count(*) FROM inventory.purchase_intent_outcomes))'''))
 elif action=='po-hold':
  if binding.POOL=='1':
   # A held physical worker connection would saturate a one-slot pool; gate discovery instead and restore the exact original definition.
   (state/'po-discovery.sql').write_text(binding.run(query+['-c',"SELECT pg_get_functiondef('inventory.pending_purchase_dispatch(integer,integer)'::regprocedure)"]))
   sql('''CREATE OR REPLACE FUNCTION inventory.pending_purchase_dispatch(max_items integer, scan_offset integer) RETURNS TABLE ("TenantId" uuid,"LegalEntityId" uuid,"IntentId" uuid) LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$ SELECT NULL::uuid,NULL::uuid,NULL::uuid WHERE false $$;''')
  else:
   holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);holders.append(holder)
   holder.stdin.write('BEGIN; LOCK TABLE integrations.purchase_dispatches IN SHARE ROW EXCLUSIVE MODE; SELECT pg_backend_pid();\n\\echo LOCKED\n');holder.stdin.flush()
   output=binding.marker(holder,b'LOCKED').splitlines();controller.update(holder=holder,pid=int([x for x in output if x.isdigit()][-1]))
   # A second real API process owns an independent pool/worker; both must enter the physical claim barrier.
   project=command[command.index('-p')+1]
   racer=binding.run(command+['run','-d','--no-deps','--name',project+'-purchase-racer','api'],timeout=60).strip()
   controller['racer']=racer
 elif action=='po-wait':
  if binding.POOL=='1':time.sleep(1.5)
  else:
   pid=controller['pid'];stop=time.monotonic()+15
   while True:
    count=int(sql(f"SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND {pid}=ANY(pg_blocking_pids(pid))"))
    if count>=2:break
    if time.monotonic()>stop:raise TimeoutError('purchase dispatcher physical claim barrier not reached')
    time.sleep(.03)
   print(f'PO_PHYSICAL_BARRIER controller={pid} waiters={count}',flush=True)
 elif action=='po-release':
  if binding.POOL=='1':binding.run(query,input=(state/'po-discovery.sql').read_text())
  else:
   holder=controller['holder'];holder.stdin.write('COMMIT;\n\\q\n');holder.stdin.flush();holder.stdin.close();holder.wait(timeout=5)
 elif action=='po-racer-stop':
  if binding.POOL!='1':
   racer=controller.pop('racer');info=json.loads(binding.run(['docker','inspect',racer]))[0]
   assert info['Config']['Labels']['com.docker.compose.project']==command[command.index('-p')+1]
   binding.run(['docker','rm','-f',racer],timeout=30)
 elif action.startswith('po-grant:'):
  mode=action.split(':')[1];assert mode in ('remove','restore')
  member=fixture['adminMembershipId'];where=f'''\"MembershipId\"='{member}' AND \"Permission\"='inventory.purchase-intents.create\''''
  if mode=='remove':
   saved=sql(f'''SELECT row_to_json(p) FROM organization_access.company_permissions p WHERE {where};''');assert saved.count('\n')==0 and saved.startswith('{'),'exactly one grant row expected'
   (state/'po-grant.json').write_text(saved);sql(f'''DELETE FROM organization_access.company_permissions WHERE {where};''')
  else:
   saved=(state/'po-grant.json').read_text().replace("'","''")
   sql(f'''INSERT INTO organization_access.company_permissions SELECT * FROM json_populate_record(NULL::organization_access.company_permissions,'{saved}');''')
 elif action=='po-logs-safe':
  logs=binding.run(command+['logs','--no-color','api'])
  for secret in ('synthetic-runtime-token','GBV-4711','Synthetic Supplier','owned-product-1','12.345678','https://admin-simulator','E360-PO-'):
   assert secret not in logs,'secret/identifier/payload leaked to API logs: '+secret
 else:raise ValueError('unknown purchase dispatch fixture control')
 return True
binding.EXTRA_CONTROL=control
if __name__=='__main__':binding.main()
