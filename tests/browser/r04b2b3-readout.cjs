const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync('/run/fixture.json','utf8')),origin='https://app.r00.test:8443',checks=[];
const uid=()=>crypto.randomUUID(),pass=name=>{checks.push(name);console.log('PASS R04B2B3-READOUT '+name);};
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
  const watched=new WeakSet(),payloads=[];
  async function openPanel(line){if(!watched.has(page)){watched.add(page);page.on('response',async r=>{if(/\/purchase-intents\?warehouseId=/.test(r.url()))payloads.push(await r.text().catch(()=>''));});}
   await page.goto('about:blank');await page.goto(origin+'/ui01-runtime.html#order='+order);await page.getByLabel('Workspace commessa').waitFor();await page.getByText('Operazioni materiali',{exact:true}).click();
   const material=page.getByRole('region',{name:'Operazioni materiali'});await material.getByLabel('Riga ricambio').selectOption(line);await material.getByLabel('Magazzino materiali').selectOption(ctx.warehouseId);
   const panel=page.getByRole('region',{name:"Richiesta d'acquisto"});await panel.getByText(/^Residuo richiedibile:/).waitFor();return panel;}
  const reread=async panel=>{await panel.getByRole('button',{name:'Rileggi richieste e quotazione'}).click();await panel.getByRole('button',{name:'Rileggi richieste e quotazione'}).waitFor();};
  // The worker advances asynchronously: reread the authoritative server state until the expected readout appears (bounded).
  const see=async(panel,text,ms=45000)=>{const stop=Date.now()+ms;for(;;){if(await panel.getByText(text).count()>0)return;assert(Date.now()<stop,'readout not shown: '+text);await sleep(1000);await reread(panel);}};
  const QUEUED="Non inviata · in coda per l'invio",UNCERTAIN="In verifica · esito dell'ordine incerto: nessun nuovo invio automatico",CONFIG='Non inviata · configurazione acquisti mancante: richiesta trattenuta',NOT_SENDABLE='Non inviabile · richiesta senza prezzo: mai inviata';
  const NOTE="Lo stato dell'ordine non modifica le giacenze locali: il magazzino resta governato da Giobby.";
  stage='unpriced legacy never dispatched';
  const st0=(await state(lines[0])).value,legacy={id:uid(),warehouseId:ctx.warehouseId,supplierId:supplier,sourceRevision:st0.source.revision,supplierRevision:st0.suppliers[0].revision,mappingRevision:st0.suppliers[0].mappingRevision,quantity:'1'};
  assert.equal((await post(page,url(lines[0]),legacy)).status,201);
  stage='queued while dispatch is paused, then confirmed after the fake dispatch';
  await control('po-mode:complete');await control('capability:external-administration:false');await sleep(500);
  const A=await accept(lines[1],'1','9');
  let panel=await openPanel(lines[1]);
  await see(panel,QUEUED);
  assert.equal(await panel.getByText(/connettore d'acquisto non ancora attivo/).count(),0,'obsolete connector text is gone once a readout exists');
  assert.equal((await po(A)).outcome,null);
  pass('priced intent not yet sent reads «Non inviata · in coda»');
  await control('capability:external-administration:true');
  const done=await until(A,s=>s.outcome,'queued intent dispatched');
  await see(panel,'Confermata · riferimento ordine Giobby: '+done.outcome.ExternalReference);
  await panel.getByText(NOTE).waitFor();
  const names=await panel.getByRole('button').allInnerTexts();
  assert.deepEqual(names.filter(n=>!["Crea richiesta d'acquisto",'Rileggi richieste e quotazione'].includes(n)),[],'no new dispatch/cancel/receipt action');
  assert.equal((await po(A)).salesOutbox,0);
  pass('queued -> confirmed with the verified Giobby order reference after the fake dispatch; order status is not stock authority; no new action');
  stage='uncertain';
  await control('po-mode:500');const B=await accept(lines[2],'1','3');
  await until(B,s=>s.dispatch&&s.dispatch.State==='Uncertain','uncertain after 500');
  panel=await openPanel(lines[2]);await see(panel,UNCERTAIN);
  assert.equal(await panel.getByText(/Confermata|Non inviata/).count(),0);
  pass('fake provider failure reads «In verifica» and never as confirmed');
  stage='held purchase configuration';
  await control('po-mode:complete');
  await control('capability:external-administration:false');await configure('missing');
  const C=await accept(lines[0],'1','10');await control('capability:external-administration:true');await sleep(1500);
  await configure('original');
  await until(C,s=>s.dispatch?.LastError==='destination_binding_mismatch','held creation mapping');
  panel=await openPanel(lines[0]);
  await see(panel,NOT_SENDABLE);await see(panel,CONFIG);
  const legacyState=(await state(lines[0])).value.intents.find(i=>i.id===legacy.id);
  assert.deepEqual(legacyState.dispatch,{state:'not_sendable',reason:'unpriced',externalReference:null});assert.equal(legacyState.outcome,undefined);
  assert.equal((await po(legacy.id)).dispatch,null,'unpriced legacy intent never has a dispatch row');
  pass('unpriced legacy intent reads «Non inviabile»; held creation mapping reads «configurazione acquisti mancante» without naming host settings');
  stage='layout';
  panel=await openPanel(lines[1]);await see(panel,'Confermata · riferimento ordine Giobby: '+done.outcome.ExternalReference);
  for(const [width,height] of [[1920,1080],[1366,768]]){
   await page.setViewportSize({width,height});
   await page.locator('.ui01-document').evaluate(e=>{e.scrollTop=e.scrollHeight;});
   const add=page.getByRole('button',{name:'Aggiungi riga',exact:true});await add.scrollIntoViewIfNeeded();await add.focus();
   const box=await add.evaluate(e=>{const r=e.getBoundingClientRect(),f=document.querySelector('.ui01-summary').getBoundingClientRect();return {top:r.top,bottom:r.bottom,footer:f.top};});
   console.log('READOUT_LAYOUT '+JSON.stringify({width,height,box}));
   assert(box.top>=0&&box.bottom<=box.footer,'Aggiungi riga reachable with the readout shown at '+width+'x'+height);}
  await page.setViewportSize({width:1920,height:1080});
  assert(await page.locator('aside.ui01-context').count()===1&&!(await panel.evaluate(e=>!!e.closest('aside.ui01-context'))),'purchase panel keeps its existing placement in the material operations; the readout adds no region to the context aside');
  pass('layout: Aggiungi riga reachable at 1920x1080 and 1366x768 with the readout shown');
  stage='grant removal';
  await control('po-grant:remove');
  await reread(panel);await panel.getByText("Lettura richieste d'acquisto non disponibile.").waitFor();
  assert.doesNotMatch(await panel.innerText(),/Confermata|GiobbyPurchaseOrder|In verifica|Non inviata|Non inviabile/);
  const denied=await state(lines[1]);assert([403,404].includes(denied.status),'state refused without the purchase grant');assert.doesNotMatch(JSON.stringify(denied.value),/GiobbyPurchaseOrder|dispatch/);
  await control('po-grant:restore');await see(panel,/Confermata · riferimento ordine Giobby/);
  pass('removing the purchase grant hides the readout and reference at once; restoring the same grant shows them again, no new grant or scope');
  stage='isolation and redaction';
  const peer=await login(browser,1);
  const peerRead=await json(peer.page,url(lines[1])+'?warehouseId='+ctx.warehouseId);assert([403,404].includes(peerRead.status),'foreign tenant cannot read dispatch state');assert.doesNotMatch(JSON.stringify(peerRead.value),/GiobbyPurchaseOrder|dispatch/);
  const wireLeak=payloads.join('\n');assert(wireLeak.includes('"dispatch"'),'readout payloads were observed');
  for(const forbidden of ['GBV-4711','owned-product','idDocument','destination_binding_mismatch','mapping_missing','source_unavailable','readback_mismatch','LastError','E360-PO-','synthetic-runtime-token','"outcome"'])assert(!wireLeak.includes(forbidden),'readout payload leaked '+forbidden);
  assert.doesNotMatch(await page.locator('body').innerText(),/GBV|vendorId|idDocument|E360-PO-/);
  assert.equal((await wire()).filter(c=>/sales/.test(c.path)).length,0);
  await control('po-logs-safe');
  pass('foreign tenant sees nothing; readout payloads, page and API logs expose no vendor id, provider id, error code, correlation reference or secret');
  fs.writeFileSync('/run/control/result.json',JSON.stringify({checks,pool:fixture.poolSize}));
 }catch(e){fs.writeFileSync('/run/control/failure-po.txt',stage+'\n'+String(e.stack||e));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
