const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json','utf8'));
const origin = 'https://app.r00.test:8443';
const checks = [];
function pass(name) { checks.push(name); console.log('PASS UI01B '+name); }
async function json(page,path,options={}) { return page.evaluate(async ({path,options}) => { const r=await fetch(path,options); return { status:r.status, value:await r.json().catch(()=>null) }; },{path,options}); }
async function post(page,path,body,token) { const csrf=token===undefined ? (await json(page,'/auth/csrf')).value.requestToken : token; return json(page,path,{method:'POST',headers:{'Content-Type':'application/json',...(csrf ? {'X-CSRF-TOKEN':csrf} : {})},body:JSON.stringify(body)}); }
async function put(page,path,body) { const csrf=(await json(page,'/auth/csrf')).value.requestToken; return json(page,path,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':csrf},body:JSON.stringify(body)}); }
async function control(action) {
  fs.writeFileSync('/run/control/request',action);
  for(let i=0;i<80;i++) {
    if(fs.existsSync('/run/control/ack')) { assert.equal(fs.readFileSync('/run/control/ack','utf8'),action); fs.unlinkSync('/run/control/ack'); return; }
    await new Promise(r=>setTimeout(r,100));
  }
  assert.fail('ephemeral database controller did not acknowledge '+action);
}
async function paging(page, noun, label) {
  await page.getByLabel('Ricerca '+noun,{exact:true}).fill('Page');
  async function fetchPage(button) {
    const response=page.waitForResponse(r=>new URL(r.url()).searchParams.get('search')==='Page' && r.request().method()==='GET');
    await page.getByRole('button',{name:button,exact:true}).click();
    const r=await response; assert.equal(r.status(),200); const rows=await r.json();
    await page.waitForFunction(({label,ids})=>JSON.stringify(Array.from(document.querySelector('select[aria-label="'+label+'"]').options).map(o=>o.value).filter(Boolean))===JSON.stringify(ids),{label,ids:rows.map(r=>r.id)});
    return rows.map(r=>r.id);
  }
  const ids=await fetchPage('Cerca '+noun);
  assert.equal(ids.length,20);
  ids.push(...await fetchPage('Pagina successiva '+noun));
  ids.push(...await fetchPage('Pagina successiva '+noun));
  assert.equal(ids.length,51); assert.equal(new Set(ids).size,51); assert.deepEqual(ids,[...ids].sort());
  assert(await page.getByRole('button',{name:'Pagina successiva '+noun,exact:true}).isDisabled());
  assert.deepEqual(await fetchPage('Prima pagina '+noun),ids.slice(0,20));
}
async function login(browser,index) {
  const context=await browser.newContext(); const page=await context.newPage();
  await page.goto(origin+'/'); await page.getByRole('button',{name:'Accedi',exact:true}).waitFor();
  const authorize=page.waitForRequest(r=>new URL(r.url()).hostname==='idp.r00.test' && new URL(r.url()).pathname.endsWith('/auth'));
  await page.getByRole('button',{name:'Accedi',exact:true}).click();
  const query=new URL((await authorize).url()).searchParams;
  if (query.has('request_uri')) assert.equal(query.get('client_id'),'runtime-browser');
  else { assert.equal(query.get('response_type'),'code'); assert.equal(query.get('code_challenge_method'),'S256'); }
  await page.locator('#username').fill(fixture.users[index].username); await page.locator('#password').fill(fixture.users[index].password);
  await Promise.all([page.waitForURL(u=>u.hostname==='app.r00.test'),page.locator('#kc-login').click()]);
  return {context,page};
}
(async()=>{
 const browser=await chromium.launch({headless:true}); let stage='startup';
 try {
  const probe=await browser.newPage(); let ready=false;
  for(let i=0;i<40;i++){try{if((await probe.goto(origin+'/auth/session')).status()===200){ready=true;break;}}catch{} await new Promise(r=>setTimeout(r,500));} assert(ready);
  assert.equal((await json(probe,'/api/v1/workshop/contexts')).status,401);
  pass('anonymous denied over trusted TLS');
  stage='real OIDC login'; const a=await login(browser,0); const page=a.page;
  let cspErrors=0; page.on('console',m=>{if (/Content Security Policy|violates.*directive/i.test(m.text())) cspErrors++;});
  page.on('pageerror',e=>console.error('APP_JS_ERROR '+e.message));
  assert.equal((await json(page,'/auth/session')).value.authenticated,true);
  stage='R02 bounded selector queries';
  const ctx=fixture.contexts[0];
  stage='R02b authority read API';
  const authorityEndpoint='/api/v1/counterparties/authority?legalEntityId='+ctx.legalEntityId;
  const authority=await json(page,authorityEndpoint); assert.equal(authority.status,200,'authorized authority read must exist');
  assert.equal(authority.value.state,'missing');
  pass('R02b missing setup visible without blocking reads');
  const editEndpoint='/api/v1/counterparties/'+fixture.workshop[0].payerId;
  const editBody={legalEntityId:ctx.legalEntityId,commandId:crypto.randomUUID(),authorityVersion:0,expectedRevision:0,legalName:'Synthetic edited payer',fiscalIdentifier:'SYNTHETIC',registeredOffice:'Synthetic office'};
  const refused=await put(page,editEndpoint,editBody); assert.equal(refused.status,409,'missing authority must refuse dependent write explicitly'); assert.equal(refused.value.state,'missing');
  const scope='legalEntityId='+ctx.legalEntityId+'&siteId='+ctx.siteId;
  const selectors=['/api/v1/counterparties?'+scope,'/api/v1/workshop/vehicles?'+scope,'/api/v1/workshop/catalog?'+scope];
  const sizes=[];
  for(const endpoint of selectors) {
    const result=await json(page,endpoint+'&limit=1'); assert.equal(result.status,200); sizes.push(result.value.length);
  }
  assert.deepEqual(sizes,[1,1,1],'each owning-module query must bound actual database results');
  pass('R02 bounded results in all three PostgreSQL selectors');
  stage='R02 literal search and stable paging';
  const searched=[];
  for(const endpoint of selectors) {
    const empty=await json(page,endpoint+'&search=NoSuchMaster'); searched.push(empty.value);
  }
  assert.deepEqual(searched,[[],[],[]],'literal search must execute in each owning query');
  for(const endpoint of selectors) {
    assert.equal((await json(page,endpoint)).value.length,20);
    assert.equal((await json(page,endpoint+'&limit=50')).value.length,50);
    const all=(await json(page,endpoint+'&limit=50&search=Synthetic')).value;
    assert(all.length>=1); assert.deepEqual(all.map(x=>x.id),all.map(x=>x.id).sort());
    const collected=[]; let after='';
    for(let n=0;n<=all.length;n++) {
      const r=await json(page,endpoint+'&search=Synthetic&limit=1'+(after?'&after='+after:'')); assert.equal(r.status,200);
      if(!r.value.length) break;
      assert.equal(r.value.length,1); collected.push(r.value[0]); after=r.value[0].id;
    }
    assert.deepEqual(collected,all,'exclusive UUID pagination cannot repeat or omit stable rows');
    for(const term of ['synthetic','Sýnthetic','%','_']) assert.deepEqual((await json(page,endpoint+'&search='+encodeURIComponent(term))).value,[]);
    assert((await json(page,endpoint+'&search=Synthetic')).value.length>0);
    for(const query of ['limit=0','limit=51','limit=-1','limit=x','after=broken','search='+('x'.repeat(201))]) assert.equal((await json(page,endpoint+'&'+query)).status,400,query.split('=')[0]);
  }
  pass('R02 literal case/diacritic-sensitive search, wildcard escaping, empty result, UUID keyset paging and input caps');
  stage='R02 exact action context and tenant boundaries';
  assert.deepEqual(Object.keys((await json(page,selectors[1]+'&search=Synthetic')).value[0]).sort(),['id','label']);
  assert.deepEqual(Object.keys((await json(page,selectors[2]+'&search=Synthetic')).value[0]).sort(),['id','kind','label','version']);
  for(const [n, endpoint] of selectors.entries()) {
    const r=await json(page,endpoint+'&search=Synthetic&tenantId='+fixture.contexts[1].tenantId+'&identitySubject='+fixture.contexts[1].tenantId);
    assert.equal(r.status,200);
    const forbidden=n===0?[fixture.workshop[1].payerId,fixture.workshop[1].holderId]:n===1?[fixture.workshop[1].vehicleId]:[fixture.workshop[1].serviceId,fixture.workshop[1].partId];
    assert(r.value.every(x=>!forbidden.includes(x.id)));
    const wrong=endpoint.replace(ctx.legalEntityId,fixture.deniedContexts[0].legalEntityId);
    assert.equal((await json(page,wrong)).status,403);
    if(n>0) assert.equal((await json(page,endpoint.replace(ctx.siteId,fixture.contexts[1].siteId))).status,403);
  }
  const destinations=(await json(page,'/api/v1/counterparties/'+fixture.workshop[0].payerId+'/destinations?legalEntityId='+ctx.legalEntityId)).value;
  assert.deepEqual(destinations.map(x=>x.id),[fixture.publishedDestinationId]);
  assert.equal((await json(page,'/api/v1/counterparties/destinations/'+fixture.privateDestinationId+'?legalEntityId='+ctx.legalEntityId)).status,404);
  const onlyRead=await login(browser,5), membershipOnly=await login(browser,4);
  assert.deepEqual(await Promise.all(selectors.map(async e=>(await json(onlyRead.page,e)).status)),[200,403,403]);
  assert.deepEqual(await Promise.all(selectors.map(async e=>(await json(membershipOnly.page,e)).status)),[403,403,403]);
  await onlyRead.context.close(); await membershipOnly.context.close();
  pass('R02 same-tenant other-company minimal choices, private destination hidden/published visible, tenant/identity tampering and exact distinct actions denied');
  stage='editor route'; await page.goto(origin+'/ui01-runtime.html');
  await page.getByRole('heading',{name:'Nuova commessa',exact:true}).waitFor();
  stage='document selectors';
  await page.getByRole('heading',{name:'Autorità anagrafica condivisa',exact:true}).waitFor({timeout:5000});
  await page.getByText('Profilo assente: modifica comune bloccata; ricerca e selezione disponibili.',{exact:true}).waitFor();
  await page.getByRole('option',{name:'Synthetic document · v7',exact:true}).waitFor({state:'attached'});
  stage='R02 actual database outage and recovery';
  await control('database-outage');
  assert.equal((await json(page,authorityEndpoint)).status,503);
  await page.getByRole('button',{name:'Rileggi autorità',exact:true}).click();
  await page.getByRole('heading',{name:'Autorità anagrafica condivisa',exact:true}).locator('..').getByText(/Servizio non disponibile/).waitFor();
  for(const endpoint of selectors) assert.equal((await json(page,endpoint+'&search=Synthetic')).status,503);
  await page.getByLabel('Ricerca veicolo',{exact:true}).fill('Synthetic vehicle');
  await page.getByRole('button',{name:'Cerca veicolo',exact:true}).click();
  await page.getByText(/Veicolo: Servizio non disponibile/).waitFor();
  assert.equal(await page.getByLabel('Veicolo',{exact:true}).locator('option').count(),1);
  await control('database-recover');
  await page.getByRole('button',{name:'Rileggi autorità',exact:true}).click();
  await page.getByText('Profilo assente: modifica comune bloccata; ricerca e selezione disponibili.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Cerca veicolo',exact:true}).click();
  await page.getByRole('option',{name:'Synthetic vehicle',exact:true}).waitFor({state:'attached'});
  pass('R02 actual paused PostgreSQL yields selector503 and empty UI; unpause explicit retry recovers');
  stage='R02 real UI search paging and stale context response';
  await paging(page,'pagante','Pagante'); await paging(page,'veicolo','Veicolo');
  let release, captured, fulfilled;
  const held=new Promise(resolve=>{release=resolve;}), received=new Promise(resolve=>{captured=resolve;}), completed=new Promise(resolve=>{fulfilled=resolve;});
  const hold=async route=>{const response=await route.fetch(); assert.equal(response.status(),200); captured(); await held; await route.fulfill({response}); fulfilled();};
  await page.route('**/api/v1/counterparties?**search=Synthetic**',hold);
  await page.getByLabel('Ricerca pagante',{exact:true}).fill('Synthetic');
  await page.getByRole('button',{name:'Cerca pagante',exact:true}).click(); await received;
  await page.getByLabel('Società / sede',{exact:true}).selectOption('');
  release(); await completed; await page.unroute('**/api/v1/counterparties?**search=Synthetic**',hold);
  assert.equal(await page.getByLabel('Pagante',{exact:true}).locator('option').count(),1);
  assert(await page.getByRole('button',{name:'Cerca pagante',exact:true}).isDisabled());
  await page.getByLabel('Società / sede',{exact:true}).selectOption('0');
  await page.getByRole('option',{name:'Synthetic document · v7',exact:true}).waitFor({state:'attached'});
  pass('R02 UI traverses 51 actual payer/vehicle rows without duplicates; delayed real response discarded after context clear');
  await page.getByLabel('Tipo documento',{exact:true}).selectOption(fixture.workshop[0].documentTypeId);
  stage='payer select';
  await page.getByLabel('Ricerca pagante',{exact:true}).fill('Synthetic payerId');
  await page.getByRole('button',{name:'Cerca pagante',exact:true}).click();
  await page.getByRole('option',{name:'Synthetic payerId',exact:true}).waitFor({state:'attached'});
  await page.getByLabel('Pagante',{exact:true}).selectOption(fixture.workshop[0].payerId);
  stage='vehicle select';
  await page.getByLabel('Ricerca veicolo',{exact:true}).fill('Synthetic vehicle');
  await page.getByRole('button',{name:'Cerca veicolo',exact:true}).click();
  await page.getByRole('option',{name:'Synthetic vehicle',exact:true}).waitFor({state:'attached'});
  await page.getByLabel('Veicolo',{exact:true}).selectOption(fixture.workshop[0].vehicleId);
  assert.equal(await page.getByLabel('Pagante',{exact:true}).inputValue(),fixture.workshop[0].payerId);
  await page.getByRole('button',{name:'Crea commessa',exact:true}).click();
  await page.getByText('Valori salvati riletti — revisione 0',{exact:true}).waitFor();
  const orderId=new URLSearchParams(new URL(page.url()).hash.slice(1)).get('order'); assert(orderId);
  const order=(await json(page,'/api/v1/workshop/orders/'+orderId)).value;
  assert.equal(order.payerId,fixture.workshop[0].payerId); assert.equal(order.vehicleHolderId,fixture.workshop[0].holderId); assert.notEqual(order.payerId,order.vehicleHolderId); assert.equal(order.configurationVersion,7);
  pass('native OIDC S256 → real selectors/server v7 → create/read immutable independent payer/holder');
  stage='add service and part';
  await paging(page,'articolo / prestazione','Articolo / prestazione');
  pass('R02 UI traverses 51 actual catalog identities with stable cursor and no prices/stock');
  let firstBody;
  for(const [kind,quantity,price,discount,revision] of [['Service','1.123456','45.654321','12.34',1],['Part','2.000001','12.123456','0.01',2]]) {
    await page.getByLabel('Ricerca articolo / prestazione',{exact:true}).fill('Synthetic '+kind);
    await page.getByRole('button',{name:'Cerca articolo / prestazione',exact:true}).click();
    await page.getByRole('option',{name:kind+' · Synthetic '+kind,exact:true}).waitFor({state:'attached'});
    await page.getByLabel('Articolo / prestazione',{exact:true}).selectOption(fixture.workshop[0][kind.toLowerCase()+'Id']);
    await page.getByLabel('Versione configurazione righe (setup)',{exact:true}).fill('9');
    await page.getByLabel('Quantità',{exact:true}).fill(quantity); await page.getByLabel('Prezzo unitario',{exact:true}).fill(price); await page.getByLabel('Sconto %',{exact:true}).fill(discount);
    if(kind==='Service') await page.route('**/api/v1/workshop/orders/*/lines',async route=>{firstBody=route.request().postData(); const response=await route.fetch(); assert.equal(response.status(),201); await route.abort('connectionreset'); await page.unroute('**/api/v1/workshop/orders/*/lines');});
    if(kind==='Part') await page.route('**/commercial-summary',route=>route.abort('connectionreset'));
    await page.getByLabel('Quantità',{exact:true}).fill('1,5'); assert(await page.getByRole('button',{name:'Aggiungi riga',exact:true}).isDisabled()); await page.getByLabel('Quantità',{exact:true}).fill(quantity);
    if(kind==='Service') { await page.getByLabel('Quantità',{exact:true}).focus(); await page.keyboard.press('Tab'); assert(await page.getByLabel('Prezzo unitario',{exact:true}).evaluate(e=>e===document.activeElement)); await page.getByLabel('Sconto %',{exact:true}).press('Enter'); }
    else await page.getByRole('button',{name:'Aggiungi riga',exact:true}).click();
    if(kind==='Service') { await page.getByRole('button',{name:'Riprova comando identico',exact:true}).waitFor(); const replay=page.waitForRequest(r=>r.method()==='POST' && new URL(r.url()).pathname.endsWith('/lines')); await page.getByRole('button',{name:'Riprova comando identico',exact:true}).click(); assert.equal((await replay).postData(),firstBody); }
    if(kind==='Part') { await page.getByText(/Scrittura accettata; riepilogo non verificato/).waitFor(); await page.unroute('**/commercial-summary'); await page.getByRole('button',{name:'Rileggi commessa',exact:true}).click(); }
    await page.getByText('Valori salvati riletti — revisione '+revision,{exact:true}).waitFor();
  }
  const saved=(await json(page,'/api/v1/workshop/orders/'+orderId+'/commercial-summary')).value;
  assert.equal(saved.revision,2); assert.equal(saved.lines.length,2); for(const l of saved.lines){assert.equal(l.payerId,order.payerId);assert.equal(l.workingGroupId,orderId);assert.equal(l.configurationVersion,9);assert.match(l.netAmount,/^\d+\.\d{6}$/);}
  fs.writeFileSync('/run/control/result.json',JSON.stringify({order,summary:saved}));
  pass('Service and Part q6 writes → authoritative summary revision2; policy9/catalog8 preserved');
  pass('negative transport fault: accepted Service response dropped, exact UUID/payload replay, no duplicate');
  pass('negative read fault: accepted Part then summary unavailable, explicit real read recovery without second command');
  stage='reopen'; await page.reload(); await page.getByText('Valori salvati riletti — revisione 2',{exact:true}).waitFor();
  assert.deepEqual((await json(page,'/api/v1/workshop/orders/'+orderId+'/commercial-summary')).value,saved);
  const second=await a.context.newPage(); await second.goto(origin+'/ui01-runtime.html#order='+orderId); await second.getByText('Valori salvati riletti — revisione 2',{exact:true}).waitFor();
  assert.deepEqual(await page.evaluate(()=>({local:Object.keys(localStorage),session:Object.keys(sessionStorage)})),{local:[],session:[]});
  pass('reload and new-page known UUID reread from API without browser document storage');
  stage='negative HTTP'; const endpoint='/api/v1/workshop/orders/'+orderId+'/lines';
  const body={id:crypto.randomUUID(),catalogItemId:fixture.workshop[0].serviceId,catalogVersion:8,configurationVersion:9,expectedRevision:0,quantity:'1.123456',unitPrice:'45.654321',discountPercent:'12.34'};
  assert.equal((await post(page,endpoint,body,'')).status,400); assert.equal((await post(page,endpoint,body,'corrupt')).status,400); assert.equal((await post(page,endpoint,body)).status,409);
  const b=await login(browser,1); assert.equal((await json(b.page,'/api/v1/workshop/orders/'+orderId)).status,404); assert.equal((await post(b.page,endpoint,body)).status,404);
  const limited=await login(browser,5); assert.equal((await post(limited.page,endpoint,body)).status,403);
  assert.deepEqual((await json(limited.page,'/api/v1/workshop/contexts')).value,[]);
  await limited.page.goto(origin+'/ui01-runtime.html#order='+orderId); await limited.page.getByText('Valori salvati riletti — revisione 2',{exact:true}).waitFor();
  assert.equal((await json(page,'/api/v1/workshop/orders/'+fixture.workshop[1].vehicleId)).status,404);
  assert.deepEqual((await json(page,'/api/v1/workshop/orders/'+orderId+'/commercial-summary')).value,saved);
  pass('missing/corrupt CSRF, stale revision/duplicate kind, foreign tenant and missing exact add action denied');
  pass('read-only identity with empty creation contexts reopens authorized known order');
  stage='R02b real owner setup and local common edit';
  await control('authority-external');
  assert.equal((await json(page,authorityEndpoint)).value.state,'external');
  const external=await put(page,editEndpoint,{...editBody,authorityVersion:1}); assert.equal(external.status,409); assert.equal(external.value.state,'external');
  await page.getByRole('button',{name:'Rileggi autorità',exact:true}).click();
  await page.getByText('Autorità esterna: modifica locale rifiutata; letture disponibili.',{exact:true}).waitFor();
  assert.equal(await page.getByLabel('Denominazione comune',{exact:true}).count(),0);
  assert.deepEqual((await json(page,'/api/v1/workshop/orders/'+orderId+'/commercial-summary')).value,saved);
  await control('authority-local');
  await page.getByRole('button',{name:'Rileggi autorità',exact:true}).click();
  await page.getByLabel('Denominazione comune',{exact:true}).waitFor();
  await page.getByLabel('Denominazione comune',{exact:true}).fill('Synthetic edited payer');
  let commonPayload;
  await page.route('**/api/v1/counterparties/'+fixture.workshop[0].payerId,async route=>{
    if(route.request().method()!=='PUT') return route.continue();
    commonPayload=route.request().postData();const response=await route.fetch();assert.equal(response.status(),200);await route.abort('connectionreset');await page.unroute('**/api/v1/counterparties/'+fixture.workshop[0].payerId);
  });
  await page.getByRole('button',{name:'Salva dati comuni',exact:true}).click();
  await page.getByRole('button',{name:'Riprova modifica identica',exact:true}).waitFor();
  assert(await page.getByLabel('Denominazione comune',{exact:true}).isDisabled());
  const commonReplay=page.waitForRequest(r=>r.method()==='PUT' && new URL(r.url()).pathname===editEndpoint);
  await page.getByRole('button',{name:'Riprova modifica identica',exact:true}).click();assert.equal((await commonReplay).postData(),commonPayload);
  await page.getByText('Dati comuni salvati e riletti — revisione 1',{exact:true}).waitFor();
  assert.equal(await page.getByLabel('Denominazione comune',{exact:true}).inputValue(),'Synthetic edited payer');
  const common=(await json(page,editEndpoint+'?legalEntityId='+ctx.legalEntityId)).value; assert.equal(common.legalName,'Synthetic edited payer');
  assert.deepEqual((await json(page,'/api/v1/workshop/orders/'+orderId)).value,order);
  assert.deepEqual((await json(page,'/api/v1/workshop/orders/'+orderId+'/commercial-summary')).value,saved);
  assert.equal((await put(limited.page,editEndpoint,{...editBody,authorityVersion:2,expectedRevision:1})).status,403);
  assert.equal((await put(b.page,editEndpoint,{...editBody,legalEntityId:fixture.contexts[1].legalEntityId,authorityVersion:2,expectedRevision:1})).status,403);
  const stale=await put(page,editEndpoint,{...editBody,authorityVersion:1,expectedRevision:1}); assert.equal(stale.status,409);assert.equal(stale.value.state,'stale_authority');
  const invalid=await put(page,editEndpoint,{legalEntityId:ctx.legalEntityId,legalName:'Invalid command',fiscalIdentifier:'SYNTHETIC',registeredOffice:'Synthetic office'}); assert.equal(invalid.status,400);
  const proof=JSON.parse(fs.readFileSync('/run/control/result.json','utf8')); proof.common=common; proof.authority=(await json(page,authorityEndpoint)).value; fs.writeFileSync('/run/control/result.json',JSON.stringify(proof));
  pass('R02b trusted TLS owner tool establishes explicit external/local source; external/missing/stale write denied; actual UI PUT and API reread preserve saved order/q6 and exact grants');
  stage='layout'; for(const [width,height] of [[1920,1080],[1366,768]]) {
    await page.setViewportSize({width,height});
    const measure=await page.evaluate(()=>({width:innerWidth,height:innerHeight,bottom:document.querySelector('.ui01-summary').getBoundingClientRect().bottom})); assert.deepEqual(measure,{width,height,bottom:height});
    await page.locator('.ui01-document').evaluate(e=>{e.scrollTop=e.scrollHeight;});
    const reachable=await page.getByRole('button',{name:'Aggiungi riga',exact:true}).evaluate(e=>{const r=e.getBoundingClientRect(), footer=document.querySelector('.ui01-summary').getBoundingClientRect(); return r.top>=0 && r.bottom<=footer.top;}); assert(reachable,'add control reachable above sticky summary after document scroll');
    await page.screenshot({path:'/run/control/ui01b-'+width+'x'+height+'.png'});
  }
  assert.equal(cspErrors,0,'no app CSP violations with actual Ant Design button/styles');
  const response=await page.request.get(origin+'/ui01-runtime.html'); const nonce=(await response.text()).match(/name="style-nonce" content="([a-f0-9]{32})"/)[1]; assert(response.headers()['content-security-policy'].includes("'nonce-"+nonce+"'"));
  const again=await page.request.get(origin+'/ui01-runtime.html'); assert.notEqual((await again.text()).match(/name="style-nonce" content="([a-f0-9]{32})"/)[1],nonce);
  pass('actual desktop1920x1080 and laptop1366x768 sticky-summary screenshots synthetic only');
  stage='logout'; await page.goto(origin+'/'); await page.getByRole('button',{name:'Esci da Enginia360',exact:true}).waitFor(); await page.getByRole('button',{name:'Esci da Enginia360',exact:true}).click();
  await second.getByRole('button',{name:'Riprova sessione',exact:true}).click(); await second.getByText('Sessione terminata. Accedi nuovamente.',{exact:true}).waitFor(); assert.equal(await second.getByRole('heading',{name:'Aggiunta persistita',exact:true}).count(),0);
  assert.equal((await json(second,authorityEndpoint)).status,401);
  assert.equal(await second.getByRole('heading',{name:'Autorità anagrafica condivisa',exact:true}).count(),0);
  pass('local logout invalidates existing editor session and clears document/write controls');
  console.log('UI01B_CHECK_COUNT '+checks.length+' skipped=0');
 } catch(e) { console.error('UI01B_FAILED_STAGE '+stage+' '+e.name+' '+(stage.includes('login') ? String(e.message).split('\n')[0] : String(e.message))); process.exitCode=1; } finally {await browser.close();}
})();
