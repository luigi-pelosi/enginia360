const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync('/run/fixture.json','utf8')),origin='https://app.r00.test:8443',checks=[];
const uid=()=>crypto.randomUUID(),pass=name=>{checks.push(name);console.log('PASS R04B3 '+name);};
const json=(page,path,options={})=>page.evaluate(async({path,options})=>{const r=await fetch(path,options);return {status:r.status,value:await r.json().catch(()=>null)};},{path,options});
async function post(page,path,body,token){const t=token===undefined?(await json(page,'/auth/csrf')).value.requestToken:token;return json(page,path,{method:'POST',headers:{'Content-Type':'application/json',...(t?{'X-CSRF-TOKEN':t}:{})},body:typeof body==='string'?body:JSON.stringify(body)});}
async function control(action){fs.writeFileSync('/run/control/request.tmp',action);fs.renameSync('/run/control/request.tmp','/run/control/request');for(let i=0;i<600;i++){if(fs.existsSync('/run/control/ack')){assert.equal(fs.readFileSync('/run/control/ack','utf8'),action);fs.unlinkSync('/run/control/ack');return;}await new Promise(r=>setTimeout(r,100));}assert.fail('controller missing '+action);}
const read=name=>JSON.parse(fs.readFileSync('/run/control/'+name,'utf8'));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function po(intent){await control('po-state:'+intent);return read('po-state.json');}
async function until(intent,accept,what,ms=90000){const stop=Date.now()+ms;let last;while(Date.now()<stop){last=await po(intent);if(accept(last))return last;await sleep(250);}assert.fail('timeout waiting for '+what+' '+JSON.stringify(last));}
async function wire(){await control('traffic');return read('traffic.json').A;}
const posts=async()=>(await wire()).filter(c=>c.method==='POST');
async function effects(){await control('remote-effects');return read('effects.json');}
async function login(browser,index){const context=await browser.newContext(),page=await context.newPage();await page.goto(origin+'/');await page.getByRole('button',{name:'Accedi',exact:true}).click();await page.locator('#username').fill(fixture.users[index].username);await page.locator('#password').fill(fixture.users[index].password);await Promise.all([page.waitForURL(u=>u.hostname==='app.r00.test'),page.locator('#kc-login').click()]);return {context,page};}
async function waitForTlsApi(browser) {
 const probe = await browser.newPage(), deadline = Date.now() + 30000;
 try {
  while (Date.now() < deadline) {
   try {
    const response = await probe.goto(origin+'/auth/session', {timeout: 3000, waitUntil: 'domcontentloaded'});
    if (response?.status() === 200 && (await response.json()).authenticated === false) return;
   } catch { /* The isolated API may still be starting; never relax TLS validation. */ }
   await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.fail('Real TLS API session endpoint did not become ready before login');
 } finally { await probe.close(); }
}
(async()=>{
 const browser=await chromium.launch({headless:true});let stage='start';
 try{
  await waitForTlsApi(browser);
  let {page}=await login(browser,0);
  async function configure(mode){await control('po-config:'+mode);const stop=Date.now()+30000;while((await json(page,'/auth/session').catch(()=>({status:0}))).status!==200){assert(Date.now()<stop,'API restart readiness');await sleep(100);}({page}=await login(browser,0));}
  const ctx=fixture.contexts[0],data=fixture.workshop[0],supplier=fixture.purchasePrices.supplierId,item=fixture.purchasePrices.catalogItemId;
  const order=uid(),lines=[];let revision=0;
  assert.equal((await post(page,'/api/v1/workshop/orders',{id:order,legalEntityId:ctx.legalEntityId,siteId:ctx.siteId,documentTypeId:data.documentTypeId,configurationVersion:7,payerId:data.payerId,vehicleId:data.vehicleId})).status,201);
  async function editor(type,extra){const r=await post(page,`/api/v1/workshop/orders/${order}/editor/commands`,{type,commandId:uid(),expectedRevision:revision,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,groupId:null,lineId:null,title:null,description:null,catalogItemId:null,catalogVersion:null,quantity:null,unitPrice:null,discountPercent:null,...extra});assert.equal(r.status,201,JSON.stringify(r));revision=r.value.appliedRevision;}
  for(let i=0;i<3;i++){const group=uid(),line=uid();lines.push(line);await editor('AddGroup',{groupId:group,title:'Acquisto '+i});await editor('AddCommercialLine',{lineId:line,groupId:group,catalogItemId:item,catalogVersion:8,quantity:'3',unitPrice:'111',discountPercent:'0'});}
  const url=line=>`/api/v1/inventory/orders/${order}/lines/${line}/purchase-intents`,state=line=>json(page,url(line)+'?warehouseId='+ctx.warehouseId);
  const quote=line=>json(page,url(line)+`/quote?warehouseId=${ctx.warehouseId}&supplierId=${supplier}`);
  async function accept(line,quantity,price){const st=(await state(line)).value,q=(await quote(line)).value.quote;assert.equal(q.sourcePresent,false);const b={id:uid(),warehouseId:ctx.warehouseId,supplierId:supplier,sourceRevision:st.source.revision,supplierRevision:st.suppliers[0].revision,mappingRevision:st.suppliers[0].mappingRevision,quantity,quoteRevision:q.revision,catalogVersion:q.catalogVersion,authorityVersion:q.authorityVersion,manualUnitPurchasePrice:price};const r=await post(page,url(line)+'/accepted',b);assert.equal(r.status,201,JSON.stringify(r));return b.id;}
  const source=await accept(lines[0],'3','12.345678');
  await until(source,s=>s.outcome,'confirmed source purchase');
  await control('receipt-grant');
  const receiptUrl=`/api/v1/inventory/purchase-intents/${source}/receipts`;
  const command={id:uid(),quantity:'0.123456'};
  assert.equal((await post(page,receiptUrl,command,null)).status,400,'CSRF required');
  await control('receipt-permission:remove');
  assert.equal((await post(page,receiptUrl,command)).status,403,'purchase permission never grants receiving');
  for(const scope of ['company','site','warehouse']){await control('receipt-permission:'+scope);assert.equal((await post(page,receiptUrl,command)).status,403,'partial scope refused '+scope);}
  await control('receipt-permission:restore');
  const peer=await login(browser,1);assert.equal((await json(peer.page,receiptUrl)).status,404,'foreign source hidden');
  assert.equal((await post(page,receiptUrl,{...command,id:'00000000-0000-0000-0000-000000000000'})).status,400);
  const receipt=await post(page,receiptUrl,command);
  assert.equal(receipt.status,201,JSON.stringify(receipt));
  async function receiptState(id){await control('receipt-state:'+id);return read('receipt-state.json');}
  const deadline=Date.now()+30000;let delivered;
  do {delivered=await receiptState(command.id);if(delivered.outcome)break;await sleep(200);} while(Date.now()<deadline);
  assert(delivered.outcome,'known ACK must be saved then exact receipt detail confirms');
  assert.equal(delivered.dispatch.Attempts,1);
  const replay=await post(page,receiptUrl,command);assert.equal(replay.status,200);assert.deepEqual(replay.value,{...receipt.value,state:'replayed'});
  assert.equal((await post(page,receiptUrl,{...command,quantity:'1'})).status,409);
  let overlay=(await json(page,receiptUrl)).value;assert.equal(overlay.acceptedQuantity,'0.123456');assert.equal(overlay.remainingQuantity,'2.876544');assert.equal(overlay.nonAuthoritative,true);assert.equal(overlay.erpPerOrderResidual,null);
  await control('receipt-audit:'+command.id);
  pass('authenticated dedicated-grant receipt creation from confirmed frozen source');
  const source2=await accept(lines[1],'3','12.345678');await until(source2,s=>s.outcome,'second confirmed source');
  const u2=`/api/v1/inventory/purchase-intents/${source2}/receipts`,lost={id:uid(),quantity:'2'};
  await control('po-mode:lost-response-empty');assert.equal((await post(page,u2,lost)).status,201);
  let stop=Date.now()+30000,lostState;
  do {lostState=await receiptState(lost.id);if(lostState.dispatch?.LastError==='ack_unknown')break;await sleep(200);}while(Date.now()<stop);
  assert.equal(lostState.dispatch.State,'Uncertain');assert.equal(lostState.dispatch.KnownDocumentId,null);assert.equal(lostState.outcome,null);
  await control('po-mode:complete');await sleep(1500);
  overlay=(await json(page,u2)).value;assert.equal(overlay.uncertainQuantity,'2.000000');assert.equal(overlay.remainingQuantity,'1.000000');
  assert(overlay.receipts[0].delivery,'backend readout must expose current technical delivery without cross-module DB');
  assert.equal(overlay.receipts[0].delivery.state,'Uncertain');
  assert.equal((await post(page,u2,{id:uid(),quantity:'2'})).status,409);
  const cs=(await json(page,'/auth/csrf')).value.requestToken;
  if(fixture.poolSize>1)await control('receipt-hold:'+source2);
  const pending=[post(page,u2,{id:uid(),quantity:'1'},cs),post(page,u2,{id:uid(),quantity:'1'},cs)];
  if(fixture.poolSize>1){await control('receipt-wait:2');await control('receipt-release');}
  assert.deepEqual((await Promise.all(pending)).map(r=>r.status).sort(),[201,409]);
  await sleep(1500);assert.equal((await receiptState(lost.id)).outcome,null);
  const receiptPosts=(await wire()).filter(c=>c.method==='POST'&&c.path==='/purchases/goodsreceipt');assert.equal(receiptPosts.length,3,'one confirmed fraction, one unknown receipt and one remaining-unit receipt; never second POST');
  assert.equal((await state(lines[1])).value.remaining,'0.000000','receipt never replenishes D90');
  pass('accepted+uncertain cumulative cap, lost ACK HOLD/no blind POST, physical pool4 budget barrier or pool1 completion');
  const source3=await accept(lines[2],'3','12.345678');await until(source3,s=>s.outcome,'binding source');
  await control('receipt-discovery-hold');
  const u3=`/api/v1/inventory/purchase-intents/${source3}/receipts`,frozen={id:uid(),quantity:'1'};
  assert.equal((await post(page,u3,frozen)).status,201);
  const beforeBinding=(await wire()).filter(c=>c.method==='POST').length;
  await control('receipt-config:changed');await waitForTlsApi(browser);({page}=await login(browser,0));
  await control('receipt-discovery-release');await sleep(2500);
  assert.equal((await wire()).filter(c=>c.method==='POST').length,beforeBinding);
  assert.equal((await receiptState(frozen.id)).dispatch.LastError,'destination_binding_mismatch');
  assert.equal((await post(page,u3,frozen)).status,200,'exact replay keeps old mapping');
  await control('receipt-config:original');await waitForTlsApi(browser);({page}=await login(browser,0));
  stop=Date.now()+30000;do {delivered=await receiptState(frozen.id);if(delivered.outcome)break;await sleep(200);}while(Date.now()<stop);assert(delivered.outcome);
  pass('creation-time binding frozen before first worker HTTP, mismatch holds and restoring exact binding confirms');
  if(fixture.poolSize>1){
   const token=(await json(page,'/auth/csrf')).value.requestToken;
   await control('receipt-revoke-hold');const blocked=post(page,receiptUrl,{id:uid(),quantity:'1'},token);
   await control('receipt-wait:1');await control('receipt-release');assert.equal((await blocked).status,403);
   await control('receipt-permission:restore');
   await control('receipt-insert-hold');const inserted=post(page,receiptUrl,{id:uid(),quantity:'1'},token);
   await control('receipt-wait:1');await control('receipt-revoke-behind-insert');await control('receipt-release');
   assert.equal((await inserted).status,201);await control('receipt-insert-off');
   assert.equal((await post(page,receiptUrl,command)).status,403,'revoked grant also denies exact retry');
   await control('receipt-permission:restore');
   pass('real API grant revocation both physical lock orderings, no authorization snapshot race');
  }
  await control('receipt-claim-hold'); // TERM harness stops here with Chromium and an actual SQL receipt claim lock alive.
  await control('receipt-release');
  fs.writeFileSync('/run/control/result.json',JSON.stringify({checks,pool:fixture.poolSize}));
 }catch(e){fs.writeFileSync('/run/control/failure-receipt.txt',stage+'\n'+String(e.stack||e));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
