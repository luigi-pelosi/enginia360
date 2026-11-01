#!/usr/bin/env python3
"""D86/D94 isolated receipt API acceptance; owned-capture-shaped TLS fake only, no provider traffic."""
import importlib.util,json,uuid,time,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('purchase_runner',ROOT/'scripts/run-r04b2b3-tests.py');assert spec and spec.loader
purchase=importlib.util.module_from_spec(spec);spec.loader.exec_module(purchase)
binding=purchase.binding
binding.SPEC='r04b3-acceptance.cjs'
binding.r00.CONFIG=ROOT/'compose.r04b3-test.yaml'
base=binding.fixtures
controller={}
def fixtures(state,secret):
 sql=base(state,secret)
 host=json.loads((state/'giobby.json').read_text());po=host['ExternalAdministration']['Giobby']['PurchaseOrder']
 host['ExternalAdministration']['Giobby']['Receipt']={k:v for k,v in po.items() if k not in ('OrderType','Payments','Currency')}
 host['ExternalAdministration']['Giobby']['Receipt']['DocumentType']=0
 (state/'receipt-original.json').write_text(json.dumps(host['ExternalAdministration']['Giobby']['Receipt']))
 (state/'giobby.json').write_text(json.dumps(host))
 return sql
binding.fixtures=fixtures
def control(action,state,query,fixture,holders):
 if not action.startswith('receipt-'):return purchase.control(action,state,query,fixture,holders)
 command=query[:query.index('exec')]
 def sql(text):return binding.run(query+['-c',text]).strip()
 ctx=fixture['contexts'][0];t,c,s,w=(ctx[k] for k in ('tenantId','legalEntityId','siteId','warehouseId'));target=fixture['adminMembershipId']
 if action=='receipt-grant':
  actor=json.loads((state/'price-grants.json').read_text())[0]['actorMembershipId']
  value=dict(commandId=str(uuid.uuid4()),tenantId=t,legalEntityId=c,siteId=s,warehouseId=w,actorMembershipId=actor,targetMembershipId=target,verificationReference=str(uuid.uuid4()),expectedRevision=0,operation='grant')
  path=state/'public/receipt-grant.json';path.write_text(json.dumps(value));path.chmod(0o444)
  for _ in range(2):
   result=binding.run(command+['run','--rm','--no-deps','-T','--entrypoint','python3','migrator','scripts/owner-receipt-grant.py','/run/tls/receipt-grant.json'])
   assert 'exact immutable audit read back' in result
  path.chmod(0o600)
 elif action=='receipt-revoke-hold':
  holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);holders.append(holder)
  holder.stdin.write(f'''BEGIN; DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{target}' AND "Permission"='inventory.receipts.create'; SELECT pg_backend_pid();\n\\echo LOCKED\n''');holder.stdin.flush()
  output=binding.marker(holder,b'LOCKED').splitlines();controller.update(holder=holder,pid=int([v for v in output if v.isdigit()][-1]))
 elif action=='receipt-insert-hold':
  sql('''CREATE FUNCTION inventory.receipt_api_fixture_gate() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock_shared(777033); RETURN NEW; END $$; CREATE TRIGGER receipt_api_fixture_gate BEFORE INSERT ON inventory.receipt_intents FOR EACH ROW EXECUTE FUNCTION inventory.receipt_api_fixture_gate();''')
  holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);holders.append(holder)
  holder.stdin.write('BEGIN; SELECT pg_advisory_xact_lock(777033); SELECT pg_backend_pid();\n\\echo LOCKED\n');holder.stdin.flush()
  output=binding.marker(holder,b'LOCKED').splitlines();controller.update(holder=holder,pid=int([v for v in output if v.isdigit()][-1]))
 elif action=='receipt-revoke-behind-insert':
  gate=controller['pid'];app=int(sql(f'SELECT pid FROM pg_stat_activity WHERE {gate}=ANY(pg_blocking_pids(pid)) LIMIT 1'))
  revoke=subprocess.Popen(query+['-c',f'''DELETE FROM organization_access.company_permissions WHERE "MembershipId"='{target}' AND "Permission"='inventory.receipts.create';'''],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);holders.append(revoke);controller['revoke']=revoke
  stop=time.monotonic()+15
  while int(sql(f'SELECT count(*) FROM pg_stat_activity WHERE {app}=ANY(pg_blocking_pids(pid))'))<1:
   if time.monotonic()>stop:raise TimeoutError('grant revocation not physically blocked behind receipt transaction')
   time.sleep(.03)
  print(f'RECEIPT_API_INSERT_FIRST grant waits behind app_pid={app} fixture_gate={gate}',flush=True)
 elif action=='receipt-insert-off':
  revoke=controller['revoke'];assert revoke.wait(timeout=10)==0
  sql('DROP TRIGGER receipt_api_fixture_gate ON inventory.receipt_intents; DROP FUNCTION inventory.receipt_api_fixture_gate();')
 elif action=='receipt-claim-hold':
  holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);holders.append(holder)
  holder.stdin.write('BEGIN; LOCK TABLE integrations.receipt_dispatches IN SHARE ROW EXCLUSIVE MODE;\n\\echo LOCKED\n');holder.stdin.flush();binding.marker(holder,b'LOCKED');controller['holder']=holder
 elif action=='receipt-discovery-hold':
  (state/'receipt-discovery.sql').write_text(sql("SELECT pg_get_functiondef('inventory.pending_receipt_dispatch(integer,integer)'::regprocedure)"))
  sql('''CREATE OR REPLACE FUNCTION inventory.pending_receipt_dispatch(max_items integer,scan_offset integer) RETURNS TABLE("TenantId" uuid,"LegalEntityId" uuid,"ReceiptId" uuid) LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$ SELECT NULL::uuid,NULL::uuid,NULL::uuid WHERE false $$''')
 elif action=='receipt-discovery-release':sql((state/'receipt-discovery.sql').read_text())
 elif action.startswith('receipt-hold:'):
  source=str(uuid.UUID(action.split(':')[1]));holder=subprocess.Popen(query+['-f','-'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);holders.append(holder)
  holder.stdin.write(f"BEGIN; SELECT pg_advisory_xact_lock(hashtextextended('receipt-source:{t}:{source}',0)); SELECT pg_backend_pid();\n\\echo LOCKED\n");holder.stdin.flush()
  output=binding.marker(holder,b'LOCKED').splitlines();controller.update(holder=holder,pid=int([v for v in output if v.isdigit()][-1]))
 elif action.startswith('receipt-wait:'):
  count=int(action.split(':')[1]);pid=controller['pid'];stop=time.monotonic()+15
  while int(sql(f"SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND {pid}=ANY(pg_blocking_pids(pid))"))<count:
   if time.monotonic()>stop:raise TimeoutError('physical API receipt budget waiters missing')
   time.sleep(.03)
  print(f'RECEIPT_PHYSICAL_API_BARRIER holder={pid} waiters={count}',flush=True)
 elif action=='receipt-release':
  holder=controller['holder'];holder.stdin.write('COMMIT;\n\\q\n');holder.stdin.flush();holder.stdin.close();holder.wait(timeout=5)
 elif action.startswith('receipt-permission:'):
  mode=action.split(':')[1];assert mode in ('remove','restore','company','site','warehouse')
  where=f'''"MembershipId"='{target}' AND "Permission"='inventory.receipts.create' '''
  if mode=='remove':
   (state/'receipt-grant.json').write_text(sql(f'SELECT row_to_json(p) FROM organization_access.company_permissions p WHERE {where}'));sql(f'DELETE FROM organization_access.company_permissions WHERE {where}')
  elif mode=='restore':
   sql(f'DELETE FROM organization_access.company_permissions WHERE {where}')
   data=(state/'receipt-grant.json').read_text().replace("'","''");sql(f"INSERT INTO organization_access.company_permissions SELECT * FROM json_populate_record(NULL::organization_access.company_permissions,'{data}')")
  else:
   sql(f'DELETE FROM organization_access.company_permissions WHERE {where}')
   site="NULL" if mode in ('company','warehouse') else "'"+s+"'";warehouse="NULL" if mode in ('company','site') else "'"+w+"'"
   sql(f"INSERT INTO organization_access.company_permissions VALUES('{uuid.uuid4()}','{target}','{t}','{c}','inventory.receipts.create',{site},{warehouse})")
 elif action.startswith('receipt-audit:'):
  receipt=str(uuid.UUID(action.split(':')[1]));logs=binding.run(command+['logs','--no-color','api'])
  assert any(json.loads(line.split('|',1)[-1].strip()).get('State',{}).get('ResourceId')==receipt for line in logs.splitlines() if line.split('|',1)[-1].strip().startswith('{')),'successful receipt audit must identify committed command UUID'
 elif action.startswith('receipt-state:'):
  receipt=str(uuid.UUID(action.split(':')[1]))
  (state/'control/receipt-state.json').write_text(sql(f'''SELECT json_build_object('dispatch',(SELECT row_to_json(d) FROM integrations.receipt_dispatches d WHERE "ReceiptId"='{receipt}'),'outcome',(SELECT row_to_json(o) FROM inventory.receipt_outcomes o WHERE "ReceiptId"='{receipt}'),'count',(SELECT count(*) FROM inventory.receipt_intents),'outbox',(SELECT count(*) FROM inventory.receipt_outbox),'sales',(SELECT count(*) FROM workshop.administrative_outbox))'''))
 elif action.startswith('receipt-config:'):
  mode=action.split(':')[1];assert mode in ('original','changed','missing')
  host=json.loads((state/'giobby.json').read_text());g=host['ExternalAdministration']['Giobby'];g['Receipt']=json.loads((state/'receipt-original.json').read_text())
  if mode=='changed':g['Receipt']['Storage']='XX'
  elif mode=='missing':del g['Receipt']
  (state/'giobby.json').write_text(json.dumps(host));binding.run(command+['restart','api'],timeout=60)
 else:raise ValueError('unknown receipt fixture control')
 return True
binding.EXTRA_CONTROL=control
if __name__=='__main__':binding.main()
