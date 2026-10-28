const assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync('/run/fixture.json','utf8')),origin='https://app.r00.test:8443',checks=[];
const uid=()=>crypto.randomUUID(),pass=name=>{checks.push(name);console.log('PASS R04B2B3 '+name);};
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
(async()=>{
 const browser=await chromium.launch({headless:true});let stage='start';
 try{
  const {page}=await login(browser,0),ctx=fixture.contexts[0],data=fixture.workshop[0],supplier=fixture.purchasePrices.supplierId,item=fixture.purchasePrices.catalogItemId;
  const order=uid(),lines=[];let revision=0;
  assert.equal((await post(page,'/api/v1/workshop/orders',{id:order,legalEntityId:ctx.legalEntityId,siteId:ctx.siteId,documentTypeId:data.documentTypeId,configurationVersion:7,payerId:data.payerId,vehicleId:data.vehicleId})).status,201);
  async function editor(type,extra){const r=await post(page,`/api/v1/workshop/orders/${order}/editor/commands`,{type,commandId:uid(),expectedRevision:revision,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,groupId:null,lineId:null,title:null,description:null,catalogItemId:null,catalogVersion:null,quantity:null,unitPrice:null,discountPercent:null,...extra});assert.equal(r.status,201,JSON.stringify(r));revision=r.value.appliedRevision;}
  for(let i=0;i<7;i++){const group=uid(),line=uid();lines.push(line);await editor('AddGroup',{groupId:group,title:'Acquisto '+i});await editor('AddCommercialLine',{lineId:line,groupId:group,catalogItemId:item,catalogVersion:8,quantity:'3',unitPrice:'111',discountPercent:'0'});}
  const url=line=>`/api/v1/inventory/orders/${order}/lines/${line}/purchase-intents`,state=line=>json(page,url(line)+'?warehouseId='+ctx.warehouseId);
  const quote=line=>json(page,url(line)+`/quote?warehouseId=${ctx.warehouseId}&supplierId=${supplier}`);
  async function accept(line,quantity,price){const st=(await state(line)).value,q=(await quote(line)).value.quote;assert.equal(q.sourcePresent,false);const b={id:uid(),warehouseId:ctx.warehouseId,supplierId:supplier,sourceRevision:st.source.revision,supplierRevision:st.suppliers[0].revision,mappingRevision:st.suppliers[0].mappingRevision,quantity,quoteRevision:q.revision,catalogVersion:q.catalogVersion,authorityVersion:q.authorityVersion,manualUnitPurchasePrice:price};const r=await post(page,url(line)+'/accepted',b);assert.equal(r.status,201,JSON.stringify(r));return b.id;}
  const ref=id=>'E360-PO-'+id.replaceAll('-','');
  stage='unpriced never dispatched';
  const st0=(await state(lines[0])).value,legacy={id:uid(),warehouseId:ctx.warehouseId,supplierId:supplier,sourceRevision:st0.source.revision,supplierRevision:st0.suppliers[0].revision,mappingRevision:st0.suppliers[0].mappingRevision,quantity:'1'};
  assert.equal((await post(page,url(lines[0]),legacy)).status,201);
  stage='happy path exact readback';
  const first=await accept(lines[1],'2','12.345678');
  const done=await until(first,s=>s.outcome,'confirmed outcome');
  assert.equal(done.dispatch.State,'Completed');assert.match(done.outcome.ExternalReference,/^GiobbyPurchaseOrder-30[0-9]$/);assert.equal(done.dispatch.ExternalReference,done.outcome.ExternalReference);assert.equal(done.salesOutbox,0);
  let docs=await effects();assert.equal(docs.length,1);const sent=docs[0].body;
  assert.equal(sent.reference,ref(first));assert.equal(sent.idDocumentType,2);assert.equal(sent.idContact,null);assert.equal(sent.idVendor,'GBV-4711');assert.deepEqual(sent.payments,[]);assert.equal(sent.rows.length,1);assert.equal(sent.rows[0].price,12.345678);assert.equal(sent.rows[0].quantity,2);assert.equal(sent.rows[0].idMaterial,'owned-product-1');
  assert.equal((await po(legacy.id)).dispatch,null);assert.equal((await po(legacy.id)).outcome,null);
  assert.equal((await posts()).length,1);
  let traffic=await wire();assert(traffic.every(c=>c.authVerified&&(c.path==='/loggeduser'||/^\/purchases\//.test(c.path))),'only declared purchase-order endpoints');
  pass('priced Held intent dispatched once, exact readback confirms; unpriced 0028 intent has no dispatch/outcome; no sales outbox');
  stage='lost response recovered by lookup';
  await control('po-mode:lost-response-empty');
  const lost=await accept(lines[2],'1','7.5');
  await until(lost,s=>s.dispatch&&s.dispatch.State==='Uncertain'&&s.dispatch.Failures>=1,'uncertain after timeout');
  await sleep(2500);assert.equal((await posts()).length,2,'empty lookup never authorizes second POST');assert.equal((await po(lost)).outcome,null);
  await control('po-mode:complete');
  const rec=await until(lost,s=>s.outcome,'lost-success recovery');assert.equal(rec.dispatch.State,'Completed');
  assert.equal((await posts()).length,2,'recovery used GET only');docs=await effects();assert.equal(docs.length,2);
  pass('timeout persisted Uncertain, empty lookup held with no replay, later lookup + exact readback completed without a second POST');
  stage='500 holds';
  await control('po-mode:500');const failed=await accept(lines[3],'1','3');
  await until(failed,s=>s.dispatch&&s.dispatch.State==='Uncertain','uncertain after 500');
  await control('po-mode:complete');await sleep(3000);
  assert.equal((await posts()).length,3);assert.equal((await po(failed)).outcome,null);assert.equal((await effects()).length,2);
  pass('HTTP 500 holds Uncertain; later healthy provider never receives a second POST for that attempt');
  stage='readback mismatch';
  await control('po-mode:mismatch');const bad=await accept(lines[4],'1','4');
  await until(bad,s=>s.dispatch&&s.dispatch.State==='Uncertain'&&s.dispatch.LastError==='readback_mismatch','mismatch held');
  await control('po-mode:complete');await sleep(2500);assert.equal((await po(bad)).outcome,null);assert.equal((await posts()).length,4);
  pass('divergent provider row is never confirmed');
  stage='claim barrier';
  const before=(await posts()).length;
  await control('po-hold');
  const a=await accept(lines[5],'1','5'),b=await accept(lines[5],'1','6');
  await control('po-wait');
  assert.equal((await posts()).length,before,'nothing is sent while the claim barrier holds');
  await control('po-release');
  await until(a,s=>s.outcome,'first released');await until(b,s=>s.outcome,'second released');
  assert.equal((await posts()).length,before+2);docs=await effects();const refs=docs.map(d=>d.reference);assert.equal(new Set(refs).size,refs.length);
  assert(refs.includes(ref(a))&&refs.includes(ref(b)));
  pass('pool'+fixture.poolSize+' '+(fixture.poolSize===1?'completion with discovery gate':'physical pg_blocking_pids claim barrier')+', one POST per intent');
  stage='isolation and redaction';
  const peer=await login(browser,1);assert.equal((await post(peer.page,url(lines[1])+'/accepted',{id:uid(),warehouseId:ctx.warehouseId,supplierId:supplier,sourceRevision:1,supplierRevision:1,mappingRevision:1,quantity:'1',quoteRevision:0,catalogVersion:8,authorityVersion:1,manualUnitPurchasePrice:'1'})).status,404);
  assert.equal((await wire()).filter(c=>/sales/.test(c.path)).length,0);assert.equal((await po(first)).salesOutbox,0);
  await control('po-logs-safe');
  pass('foreign tenant cannot create, no sales traffic or outbox, API logs redact token/vendor/payload');
  fs.writeFileSync('/run/control/result.json',JSON.stringify({checks,pool:fixture.poolSize}));
 }catch(e){fs.writeFileSync('/run/control/failure-po.txt',stage+'\n'+String(e.stack||e));throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
