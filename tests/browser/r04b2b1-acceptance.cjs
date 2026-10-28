const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync('/run/fixture.json','utf8'));
const origin='https://app.r00.test:8443',checks=[];
const pass=name=>{checks.push(name);console.log('PASS R04B2B1 '+name);};
const uid=()=>crypto.randomUUID();
const json=(page,path,options={})=>page.evaluate(async({path,options})=>{const r=await fetch(path,options);return {status:r.status,value:await r.json().catch(()=>null)};},{path,options});
async function write(page,path,body,method='PUT',token){const t=token===undefined?(await json(page,'/auth/csrf')).value.requestToken:token;return json(page,path,{method,headers:{'Content-Type':'application/json',...(t?{'X-CSRF-TOKEN':t}:{})},body:typeof body==='string'?body:JSON.stringify(body)});}
async function control(action){fs.writeFileSync('/run/control/request.tmp',action);fs.renameSync('/run/control/request.tmp','/run/control/request');for(let i=0;i<400;i++){if(fs.existsSync('/run/control/ack')){assert.equal(fs.readFileSync('/run/control/ack','utf8'),action);fs.unlinkSync('/run/control/ack');return;}await new Promise(r=>setTimeout(r,100));}assert.fail('controller missing '+action);}
const read=name=>JSON.parse(fs.readFileSync('/run/control/'+name,'utf8'));
async function counts(){await control('price-counts');return read('price-counts.json');}
async function row(id){await control('price-row:'+id);return read('price-row.json');}
async function login(browser,index){const context=await browser.newContext(),page=await context.newPage();await page.goto(origin+'/');await page.getByRole('button',{name:'Accedi',exact:true}).click();await page.locator('#username').fill(fixture.users[index].username);await page.locator('#password').fill(fixture.users[index].password);await Promise.all([page.waitForURL(u=>u.hostname==='app.r00.test'),page.locator('#kc-login').click()]);return {context,page};}
(async()=>{
 const browser=await chromium.launch({headless:true});let stage='start';
 try{
  const {page}=await login(browser,0),ctx=fixture.contexts[0],data=fixture.workshop[0],supplier=fixture.purchasePrices.supplierId,item=fixture.purchasePrices.catalogItemId;
  const url=(s=supplier,i=item)=>`/api/v1/catalog/suppliers/${s}/items/${i}/purchase-price`;
  const get=()=>json(page,url()+'?legalEntityId='+ctx.legalEntityId);
  const body=(st,extra={})=>({legalEntityId:ctx.legalEntityId,commandId:uid(),expectedRevision:st.revision,supplierRevision:st.supplier.revision,catalogVersion:st.item.version,authorityVersion:st.authorityVersion,unitPurchasePrice:'0',...extra});
  const good={legalEntityId:ctx.legalEntityId,commandId:uid(),expectedRevision:0,supplierRevision:0,catalogVersion:8,authorityVersion:1,unitPurchasePrice:'0'};
  stage='exact permissions before owner grant';
  assert.equal((await get()).status,403,'trusted admin/common-edit title without exact list read is denied');assert.equal((await write(page,url(),good)).status,403,'trusted admin has no implicit price management');
  assert.equal((await counts()).prices,0);
  await control('price-owner-grants');
  let st=(await get()).value;assert.equal(st.state,'ready');assert.equal(st.entry,null);assert.equal(st.revision,0);assert.equal(st.provisionalUnitPurchasePrice,'0.000000');assert.equal(st.requiresManualPrice,true);assert.equal(st.canManage,true);
  const anon=await browser.newPage();await anon.goto(origin+'/');assert.equal((await json(anon,url()+'?legalEntityId='+ctx.legalEntityId)).status,401);await anon.close();
  assert.equal((await write(page,url(),good,'PUT','')).status,400,'CSRF');
  for(const extra of [{salesPrice:'1'},{tenantId:ctx.tenantId},{currency:'EUR'},{vendorId:'V1'}])assert.equal((await write(page,url(),{...good,...extra})).status,400,'closed pricing body');
  const foreign=await login(browser,1);assert.equal((await json(foreign.page,url()+'?legalEntityId='+ctx.legalEntityId)).status,403);assert.equal((await write(foreign.page,url(),good)).status,403);
  const sameTenant=await login(browser,5);assert.equal((await json(sameTenant.page,url()+'?legalEntityId='+ctx.legalEntityId)).status,403);assert.equal((await write(sameTenant.page,url(),good)).status,403);
  assert.equal((await json(page,url()+'?legalEntityId='+fixture.contexts[1].legalEntityId)).status,403);
  pass('real authenticated same-tenant admin/no-exact-action and trusted peer negatives, owner CLI TLS grant+exact replay/audit, anonymous/CSRF/closed-body/foreign company and tenant');

  stage='existing Held intent';
  const order=uid(),group=uid(),line=uid();
  assert.equal((await write(page,'/api/v1/workshop/orders',{id:order,legalEntityId:ctx.legalEntityId,siteId:ctx.siteId,documentTypeId:data.documentTypeId,configurationVersion:7,payerId:data.payerId,vehicleId:data.vehicleId},'POST')).status,201);
  async function editor(type,revision,extra){const r=await write(page,`/api/v1/workshop/orders/${order}/editor/commands`,{type,commandId:uid(),expectedRevision:revision,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,groupId:null,lineId:null,title:null,description:null,catalogItemId:null,catalogVersion:null,quantity:null,unitPrice:null,discountPercent:null,...extra},'POST');assert.equal(r.status,201,JSON.stringify(r));return r.value.appliedRevision;}
  let revision=await editor('AddGroup',0,{groupId:group,title:'Listino sintetico'});await editor('AddCommercialLine',revision,{lineId:line,groupId:group,catalogItemId:item,catalogVersion:8,quantity:'3',unitPrice:'111',discountPercent:'0'});
  const intentUrl=`/api/v1/inventory/orders/${order}/lines/${line}/purchase-intents`,intentState=(await json(page,intentUrl+'?warehouseId='+ctx.warehouseId)).value;
  assert.equal((await write(page,intentUrl,{id:uid(),warehouseId:ctx.warehouseId,supplierId:supplier,sourceRevision:intentState.source.revision,supplierRevision:intentState.suppliers[0].revision,mappingRevision:intentState.suppliers[0].mappingRevision,quantity:'1'},'POST')).status,201);
  await control('price-intent-hash');const heldBefore=read('price-intent-hash.json');

  stage='real DOM explicit zero lost response';
  await page.goto(origin+'/ui01-runtime.html#order='+order);await page.getByLabel('Workspace commessa').waitFor();
  await page.getByText('Listini acquisto fornitori',{exact:true}).click();const panel=page.getByRole('region',{name:'Listini acquisto fornitori'});
  await panel.getByLabel('UUID fornitore listino').fill(supplier);await panel.getByLabel('UUID articolo listino').fill(item);await panel.getByRole('button',{name:'Rileggi listino'}).click();await panel.getByText(/Prezzo assente: 0.000000 provvisorio/).waitFor();assert.equal(await panel.getByLabel('Prezzo unitario acquisto').inputValue(),'');
  const writes=[];let dropped=false;
  page.on('request',r=>{if(r.method()==='PUT'&&r.url().endsWith('/purchase-price'))writes.push({url:r.url(),body:r.postData()});});
  await page.route('**/purchase-price',async route=>{if(route.request().method()==='PUT'&&!dropped){dropped=true;await route.fetch();await route.abort('failed');}else await route.continue();});
  await panel.getByLabel('Prezzo unitario acquisto').fill('0');await panel.getByRole('button',{name:'Salva prezzo acquisto'}).click();await panel.getByText('Esito prezzo incerto: riprova solo il comando identico.').waitFor();
  for(const label of ['UUID fornitore listino','UUID articolo listino','Prezzo unitario acquisto'])assert(await panel.getByLabel(label).isDisabled());assert(await page.getByLabel('UUID commessa',{exact:true}).isDisabled());
  await page.getByText('Listini acquisto fornitori',{exact:true}).click();assert(await panel.isVisible(),'uncertain command stays mounted');
  await panel.getByRole('button',{name:'Riprova prezzo identico'}).click();await panel.getByText('Prezzo salvato e riletto — revisione 1').waitFor();await panel.getByText('Prezzo presente: 0.000000').waitFor();
  assert.equal(writes.length,2);assert.deepEqual(writes[0],writes[1]);const first=JSON.parse(writes[0].body),firstRow=await row(first.commandId);assert.equal(firstRow.UnitPurchasePrice,'0.000000');assert.equal(firstRow.Revision,1);assert.equal(firstRow.ActorMembershipId,fixture.adminMembershipId);assert.equal(firstRow.CatalogVersion,8);assert.equal(firstRow.SupplierRevision,0);assert.equal(firstRow.AuthorityVersion,1);assert.equal((await counts()).prices,1);
  await page.unroute('**/purchase-price');
  await panel.getByLabel('Prezzo unitario acquisto').fill('12.345678');await panel.getByRole('button',{name:'Salva prezzo acquisto'}).click();await panel.getByText('Prezzo salvato e riletto — revisione 2').waitFor();
  assert.deepEqual(await row(first.commandId),firstRow,'old audited revision is byte-value unchanged');
  assert.equal((await write(page,url(),writes[0].body)).value.revision,1,'old UUID returns original revision after later price');
  assert.equal((await write(page,url(),{...first,unitPurchasePrice:'0.000001'})).status,409);
  st=(await get()).value;assert.equal(st.requiresManualPrice,false);assert.equal(st.provisionalUnitPurchasePrice,null);assert.equal(st.entry.unitPurchasePrice,'12.345678');assert.equal(st.history.length,2);
  const missing=await json(page,url(supplier,data.serviceId)+'?legalEntityId='+ctx.legalEntityId);assert.equal(missing.value.entry,null);assert.equal(missing.value.provisionalUnitPurchasePrice,'0.000000');assert.equal(missing.value.requiresManualPrice,true);
  pass('actual DOM explicit zero, accepted-response loss byte-identical UUID/body retry, authoritative reread and one audit; q6 new revision and old revision/replay unchanged; PRESENT0 separate from MISSING without sales fallback');

  stage='bounded refusals';
  for(const value of ['1.0000001','-1','1000000','1e1','NaN',' 1',''])assert.equal((await write(page,url(),body(st,{unitPurchasePrice:value}))).status,400,'q6 '+value);
  for(const field of ['expectedRevision','supplierRevision','catalogVersion','authorityVersion'])assert.equal((await write(page,url(),body(st,{[field]:2147483648}))).status,400,'int overflow '+field);
  assert.equal((await write(page,url(),body(st,{commandId:'00000000-0000-0000-0000-000000000000'}))).status,400);
  assert.equal((await counts()).prices,2);
  await control('price-permission:manage:deny');assert.equal((await write(page,url(),body(st))).status,403);assert.equal((await write(page,url(),writes[0].body)).status,403,'replay needs current exact grant');assert.equal((await get()).value.canManage,false);await control('price-permission:manage:allow');
  await control('price-capability:false');assert.equal((await write(page,url(),body(st))).status,403);assert.equal((await get()).value.entry.unitPurchasePrice,'12.345678');assert.equal((await get()).value.canManage,false);
  await panel.getByRole('button',{name:'Rileggi listino'}).click();await panel.getByText('Listino riletto dal server.').waitFor();assert(await panel.getByLabel('Prezzo unitario acquisto').isDisabled());assert.equal(await panel.getByRole('button',{name:'Salva prezzo acquisto'}).count(),0);await control('price-capability:true');
  pass('controlled q6/int/empty-ID refusals, current exact grant removal including replay, disabled write capability retains authorized historical API/UI reads');

  stage='real API physical concurrency';
  for(const identical of [true,false]){
   st=(await get()).value;const command=body(st,{unitPurchasePrice:identical?'2.000001':'3.000001'});
   await control('price-hold-master');const a=write(page,url(),command),b=write(page,url(),identical?command:{...command,commandId:uid(),unitPurchasePrice:'4.000001'});
   await control('price-wait:'+(fixture.poolSize===1?1:2));await control('price-release');
   const results=await Promise.all([a,b]);assert.deepEqual(results.map(r=>r.status).sort(),identical?[200,201]:[201,409]);
   const readback=(await get()).value;assert.equal(readback.revision,st.revision+1);assert.equal(readback.entry.revision,readback.revision);assert.equal(readback.entry.unitPurchasePrice,results.find(r=>r.status===201)===results[0]?command.unitPurchasePrice:(identical?command.unitPurchasePrice:'4.000001'));
  }
  assert.equal((await counts()).prices,4);
  pass('pool'+fixture.poolSize+' actual API new-UUID optimistic collision and concurrent identical retries, physical pg_blocking_pids barrier, coherent price+revision, one audit per successful version');

  stage='transaction rollback';
  for(const mode of ['on','deferred']){
   st=(await get()).value;await control('price-fault:'+mode);
   try{assert((await write(page,url(),body(st,{unitPurchasePrice:'6'}))).status>=500);}finally{await control('price-fault:off');}
   assert.equal((await counts()).prices,4);assert.equal((await get()).value.revision,4);
  }
  await control('price-intent-hash');assert.deepEqual(read('price-intent-hash.json'),heldBefore,'pre-existing Held intent/source/outbox never repriced/backfilled');
  const totals=await counts();assert.equal(totals.intents,1);assert.equal(totals.held,1);assert.equal(totals.salesOutbox,0);
  await control('traffic');assert.deepEqual(read('traffic.json'),{A:[],B:[]});
  pass('fixture-only insert/deferred-commit faults roll back all list facts; existing0028 Held intent immutable; no dispatch, sales outbox or fake-ERP HTTP');

  stage='layout';await panel.getByRole('button',{name:'Rileggi listino'}).click();await panel.getByText('Listino riletto dal server.').waitFor();
  for(const [width,height] of [[1920,1080],[1366,768]]){
   await page.setViewportSize({width,height});
   const save=panel.getByRole('button',{name:'Salva prezzo acquisto'});await save.scrollIntoViewIfNeeded();await save.focus();
   assert(await save.evaluate(e=>document.activeElement===e));
   const priceBox=await save.evaluate(e=>{const r=e.getBoundingClientRect(),f=document.querySelector('.ui01-summary').getBoundingClientRect();return {top:r.top,bottom:r.bottom,footer:f.top};});assert(priceBox.top>=0&&priceBox.bottom<=priceBox.footer,'price save reachable above summary');
   await page.screenshot({path:`/run/control/price-layout-${width}.png`});
   await page.getByText('Listini acquisto fornitori',{exact:true}).click();assert(!(await panel.isVisible()),'price panel collapsed for the unchanged legacy reachability assertion');
   await page.locator('.ui01-document').evaluate(e=>{e.scrollTop=e.scrollHeight;});
   const old=await page.getByRole('button',{name:'Aggiungi riga',exact:true}).evaluate(e=>{const r=e.getBoundingClientRect(),f=document.querySelector('.ui01-summary').getBoundingClientRect();return {top:r.top,bottom:r.bottom,footer:f.top};});console.log('PRICE_LAYOUT '+JSON.stringify({width,height,old,priceBox}));assert(old.top>=0&&old.bottom<=old.footer,'existing add control reachable at bottom without weakening laptop assertion');
   await page.getByText('Listini acquisto fornitori',{exact:true}).click();await panel.waitFor();
   await panel.getByLabel('UUID fornitore listino').fill(supplier);await panel.getByLabel('UUID articolo listino').fill(item);await panel.getByRole('button',{name:'Rileggi listino'}).click();await panel.getByRole('button',{name:'Salva prezzo acquisto'}).waitFor();
  }
  await control('price-capture-layout');pass('actual expanded price panel and existing add controls reachable at desktop1920/laptop1366 with sticky summary, native focus and captures');
  fs.writeFileSync('/run/control/result.json',JSON.stringify({checks,pool:fixture.poolSize,prices:4,held:1,zeroExternalTraffic:true}));
 }catch(e){fs.writeFileSync('/run/control/failure-prices.txt',stage+'\n'+String(e.stack||e));throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
