const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync('/run/fixture.json','utf8'));
const origin='https://app.r00.test:8443';
const path='/api/v1/platform/tenants';
async function control(action){
 try{fs.unlinkSync('/run/control/ack');}catch{}
 fs.writeFileSync('/run/control/request',action);
 for(let i=0;i<600;i++){
  if(fs.existsSync('/run/control/ack')&&fs.readFileSync('/run/control/ack','utf8')===action)return;
  await new Promise(r=>setTimeout(r,100));
 }
 throw new Error('authority control timeout');
}
async function request(page,url=path,options={}){
 return page.evaluate(async({url,options})=>{
  const r=await fetch(url,options);let value;try{value=await r.json();}catch{value=null;}
  return {status:r.status,value,cache:[...new Set((r.headers.get('cache-control')||'').split(',').map(x=>x.trim()))].join(',')};
 },{url,options});
}
async function login(browser,index,pending=false,invitation=null){
 const context=await browser.newContext();const page=await context.newPage();
 await page.goto(origin+'/auth/session');
 const token=(await request(page,'/auth/csrf')).value.requestToken;
 await page.evaluate(({token,path})=>{const f=document.createElement('form');f.method='POST';f.action=path;const i=document.createElement('input');i.name='__RequestVerificationToken';i.value=token;f.append(i);document.body.append(f);f.submit();},{token,path:pending?'/auth/onboarding/login/'+invitation:'/auth/login'});
 await page.waitForURL(u=>u.hostname==='idp.r00.test');
 await page.locator('#username').fill(fixture.users[index].username);
 await page.locator('#password').fill(fixture.users[index].password);
 await Promise.all([page.waitForURL(u=>u.hostname==='app.r00.test'),page.locator('#kc-login').click()]);
 await page.waitForLoadState('domcontentloaded');
 if(!pending)assert.equal((await request(page,'/auth/session')).value.authenticated,true,'real OIDC session');
 return {context,page};
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try {
  const anonymous=await browser.newPage();
  for(let i=0;i<60;i++){try{await anonymous.goto(origin+'/auth/session');break;}catch(e){if(i===59)throw e;await new Promise(r=>setTimeout(r,500));}}
  const cp='/api/v1/document-types';const uuid=()=>require('node:crypto').randomUUID();
  const post=async(page,url,body)=>request(page,url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(page,'/auth/csrf')).value.requestToken},body:JSON.stringify(body)});
  const env=(kind,values)=>({commandId:uuid(),kind,resourceId:null,expectedRevision:0,...values});
  assert.equal((await request(anonymous,cp)).status,401);
  const owner=await login(browser,4);await control('grant');const tenant=fixture.contexts[0].tenantId;const company=fixture.contexts[0].legalEntityId;
  const roles='/api/v1/platform/tenant-roles/'+tenant;
  const second=await post(owner.page,path+'/'+tenant+'/commands',{commandId:uuid(),operation:'create',kind:'company',tenantId:tenant,resourceId:null,parentId:tenant,name:'Synthetic second company',expectedRevision:0});
  assert.equal(second.status,200);const other=second.value.snapshot.resourceId;
  let directory=(await request(owner.page,roles)).value;
  assert.deepEqual(directory.actions,['organization-context.read','organization-context.write','counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write','counterparties.extensions.read','counterparties.extensions.write','catalog.shared.read','catalog.shared.create','catalog.shared.edit','document-types.read','document-types.create','document-types.edit','documents.read','documents.save','documents.confirm','inventory.document-effects.apply','inventory.quantities.read','inventory.policy.read','inventory.policy.manage']);
  const member=directory.memberships.find(m=>m.membershipId===fixture.grantTargetMembershipId);assert.ok(member);
  const permissions=[];
  await owner.page.goto(origin+'/users?tenant='+tenant);
  for(const action of ['document-types.read','document-types.create','document-types.edit']){
   await owner.page.getByLabel('Nome permesso',{exact:true}).fill('Synthetic '+action);
   await owner.page.getByLabel('Azione supportata').selectOption(action);
   await owner.page.getByLabel('Scope società esatta').selectOption(company);
   assert.equal(await owner.page.getByLabel('Scope magazzino esatto').count(),0);
   await owner.page.getByRole('button',{name:'Salva permesso',exact:true}).click();
   await owner.page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
   const p=(await request(owner.page,roles)).value.permissions.find(p=>p.action===action&&p.legalEntityId===company);assert.ok(p);assert.equal(p.siteId,null);assert.equal(p.warehouseId,null);permissions.push(p);
  }
  const roleBody=env('role',{label:'Synthetic company type operator',permissionIds:permissions.map(p=>p.resourceId)});
  const roleReply=await post(owner.page,roles,roleBody);assert.equal(roleReply.status,200);const role=roleReply.value.snapshot;let roleRevision=1;
  async function updateRole(ids){const r=await post(owner.page,roles,{...roleBody,commandId:uuid(),resourceId:role.resourceId,expectedRevision:roleRevision,permissionIds:ids});assert.equal(r.status,200);roleRevision++;}
  const assignment=env('assignment',{roleId:role.resourceId,membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,active:true});
  const assigned=await post(owner.page,roles,assignment);assert.equal(assigned.status,200);
  const operator=await login(browser,5);const page=operator.page;
  const chooser=(await request(page,cp)).value;assert.deepEqual(chooser.companies.map(c=>c.id),[company]);
  assert.equal((await request(page,roles)).status,403);assert.equal((await request(page,cp+'?legalEntityId='+other)).status,403);
  await page.goto(origin+'/document-types');await page.getByLabel('Società autorizzata').selectOption(company);await page.getByRole('button',{name:'Apri società',exact:true}).click();
  const journeys=[];
  for(const [effect,italian] of [['Load','Carico'],['Unload','Scarico'],['Transfer','Trasferimento'],['None','Nessun effetto']]){
   await page.getByRole('button',{name:'Nuova tipologia',exact:true}).click();await page.getByLabel('Descrizione',{exact:true}).fill('Synthetic '+effect);
   await page.getByRole('combobox',{name:'Effetto sulle quantità',exact:true}).selectOption(effect);await page.getByRole('button',{name:'Crea tipologia',exact:true}).click();
   await page.getByRole('heading',{name:'Dettaglio: Synthetic '+effect,exact:true}).waitFor();
   const first=(await request(page,cp+'?legalEntityId='+company+'&search='+effect)).value.items.find(i=>i.label==='Synthetic '+effect);assert.ok(first);assert.equal(first.effect,effect);assert.equal(first.revision,1);
   await page.getByLabel('Cerca tipologie').fill('Synthetic '+effect);await page.getByRole('button',{name:'Cerca',exact:true}).click();await page.getByRole('link',{name:first.label,exact:true}).click();
   await page.getByLabel('Descrizione',{exact:true}).fill('x'.repeat(101));await page.getByRole('button',{name:'Salva nuova versione',exact:true}).click();
   await page.getByRole('status').filter({hasText:'Comando rifiutato'}).waitFor();assert.equal(await page.getByRole('button',{name:'Riprova stesso comando'}).count(),0);
   await page.getByLabel('Descrizione',{exact:true}).fill('Synthetic edited '+effect);await page.getByRole('combobox',{name:'Effetto sulle quantità',exact:true}).selectOption(effect==='None'?'Load':'None');
   await page.getByRole('button',{name:'Salva nuova versione',exact:true}).click();await page.getByRole('heading',{name:'Dettaglio: Synthetic edited '+effect,exact:true}).waitFor();
   const current=(await request(page,cp+'?legalEntityId='+company+'&id='+first.id+'&revision=1')).value;assert.equal(current.detail.revision,2);assert.deepEqual(current.selectedVersion,first);journeys.push(current.detail);
   const csrfBody={commandId:uuid(),operation:'create',legalEntityId:company,documentTypeId:null,expectedRevision:0,label:'Must not exist CSRF',effect};
   for(const headers of [{'Content-Type':'application/json'},{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(page,'/auth/csrf')).value.requestToken+'tampered'}]){
    const refused=await request(page,cp+'/commands',{method:'POST',headers,body:JSON.stringify(csrfBody)});assert.equal(refused.status,400);assert.equal(refused.value.error,'csrf_invalid');
   }
   const nojs=await browser.newContext({javaScriptEnabled:false});await nojs.addCookies(await operator.context.cookies());const np=await nojs.newPage();
   const response=await np.goto(origin+'/document-types?legalEntityId='+company+'&id='+first.id+'&revision=1');const html=await np.content();const headers=await response.allHeaders();
   assert.match(headers['cache-control'],/private/);assert.match(headers['cache-control'],/no-store/);assert.match(html,new RegExp('Synthetic edited '+effect));assert.match(html,new RegExp(italian));
   await np.getByRole('heading',{name:'Versione selezionata: 1',exact:true}).waitFor();
   fs.writeFileSync('/evidence/mvp06-'+effect+'-nojs.html',html);fs.writeFileSync('/evidence/mvp06-'+effect+'-nojs-headers.json',JSON.stringify(headers,null,2));
   await np.getByLabel('Cerca tipologie').fill('edited '+effect);await np.getByRole('button',{name:'Cerca',exact:true}).click();await np.getByRole('link',{name:'Synthetic edited '+effect,exact:true}).click();
   await np.getByRole('link',{name:'Versione 1: Synthetic '+effect,exact:true}).click();await np.getByRole('heading',{name:'Versione selezionata: 1',exact:true}).waitFor();
   for(const viewport of [{width:390,height:844},{width:1920,height:1080}]){await np.setViewportSize(viewport);assert.equal(await np.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await np.screenshot({path:'/evidence/mvp06-'+effect+'-nojs-'+viewport.width+'.png',fullPage:true});}
   await nojs.close();
  }
  // Same customer, second company: directory remains permission-minimized until
  // the exact company actions are configured; no organization read grant needed.
  for(const action of ['document-types.read','document-types.create','document-types.edit']){
   const reply=await post(owner.page,roles,env('permission',{label:'Second '+action,action,legalEntityId:other,siteId:null,warehouseId:null}));assert.equal(reply.status,200);permissions.push(reply.value.snapshot);
  }
  await updateRole(permissions.map(p=>p.resourceId));
  await page.goto(origin+'/document-types');await page.getByLabel('Società autorizzata').selectOption(other);await page.getByRole('button',{name:'Apri società',exact:true}).click();
  assert.equal((await request(page,cp+'?legalEntityId='+other)).value.items.length,0);assert.equal((await request(page,cp+'?legalEntityId='+other+'&id='+journeys[0].id+'&revision=1')).status,404);
  await page.getByRole('button',{name:'Nuova tipologia',exact:true}).click();await page.getByLabel('Descrizione',{exact:true}).fill('Synthetic independent company');await page.getByRole('combobox',{name:'Effetto sulle quantità',exact:true}).selectOption('Transfer');await page.getByRole('button',{name:'Crea tipologia',exact:true}).click();
  await page.getByRole('heading',{name:'Dettaglio: Synthetic independent company',exact:true}).waitFor();
  const secondType=(await request(page,cp+'?legalEntityId='+other)).value.items[0];assert.equal(secondType.effect,'Transfer');assert.notEqual(secondType.id,journeys[0].id);
  const selected=journeys[0];const detailPath=cp+'?legalEntityId='+company+'&id='+selected.id;const uiPath='/document-types?legalEntityId='+company+'&id='+selected.id;
  const hydrating=await browser.newContext();await hydrating.addCookies(await operator.context.cookies());const hp=await hydrating.newPage();let releaseHydration;let sawChunk;
  const seen=new Promise(resolve=>{sawChunk=resolve;});const gate=new Promise(resolve=>{releaseHydration=resolve;});
  await hp.route('**/_next/static/chunks/app/document-types/page-*.js',async route=>{sawChunk();await gate;await route.continue();});
  try{
   await hp.goto(origin+uiPath,{waitUntil:'commit'});await hp.getByRole('heading',{name:'Dettaglio: '+selected.label,exact:true}).waitFor();
   await Promise.race([seen,new Promise((_,reject)=>setTimeout(()=>reject(new Error('document-types chunk not intercepted')),10000))]);
   assert.equal(await hp.getByRole('button',{name:'Salva nuova versione',exact:true}).isDisabled(),true);assert.equal(await hp.getByRole('button',{name:'Nuova tipologia',exact:true}).isDisabled(),true);assert.equal(await hp.getByRole('button',{name:'Cerca',exact:true}).isDisabled(),false);
   fs.writeFileSync('/evidence/mvp06-before-hydration.html',await hp.content());releaseHydration();await hp.waitForFunction(()=>!document.querySelector('.document-type-command fieldset')?.disabled);
   fs.writeFileSync('/evidence/mvp06-hydration-boundary.json',JSON.stringify({actualClientChunkDelayed:true,ssrReadAvailable:true,mutationDisabledBeforeHydration:true,mutationEnabledAfterHydration:true}));
  }finally{releaseHydration();await hydrating.close();}
  const unrelated=await login(browser,1);assert.equal((await request(unrelated.page,detailPath)).status,403);await unrelated.page.goto(origin+uiPath);assert.doesNotMatch(await unrelated.page.content(),/Synthetic edited Load/);
  const invitation=await post(owner.page,roles+'/onboarding',{commandId:uuid(),operation:'invite',resourceId:null,expectedRevision:0});assert.equal(invitation.status,200);const pending=await login(browser,3,true,invitation.value.snapshot.invitationId);assert.equal((await request(pending.page,cp)).status,401);
  const jwt=await browser.newContext();const token=await jwt.request.post('https://idp.r00.test:8443/realms/runtime/protocol/openid-connect/token',{form:{grant_type:'password',client_id:'runtime-bearer-proof',client_secret:fixture.clientSecret,username:fixture.users[5].username,password:fixture.users[5].password}});assert.equal(token.status(),200);const bearer={Authorization:'Bearer '+(await token.json()).access_token};
  assert.equal((await jwt.request.get(origin+detailPath,{headers:bearer})).status(),200);
  const jwtCommand={commandId:uuid(),operation:'create',legalEntityId:company,documentTypeId:null,expectedRevision:0,label:'Synthetic JWT',effect:'None'};
  const jwtReply=await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:jwtCommand});assert.equal(jwtReply.status(),201);const jwtSnapshot=(await jwtReply.json()).snapshot;
  const jwtEdit={...jwtCommand,commandId:uuid(),operation:'edit',documentTypeId:jwtSnapshot.id,expectedRevision:1,label:'Synthetic JWT changed',effect:'Unload'};assert.equal((await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:jwtEdit})).status(),201);
  const jwtReplay=await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:jwtCommand});assert.equal((await jwtReplay.json()).state,'replayed');
  // Real HTTP/1.1 chunked bodies (no Content-Length), trusted TLS and a real
  // signed IdP bearer. Each hostile stream must refuse without a SQL effect.
  const streamed=[];
  for(const effect of ['Load','Unload','Transfer','None']){
   const valid={...jwtCommand,commandId:uuid(),label:'Must not persist chunked',effect};const raw=JSON.stringify(valid);
   for(const [kind,body] of [['duplicate',raw.slice(0,-1)+',"effect":"None"}'],['nul',raw.replace('Must not persist chunked','\\u0000')],['surrogate',raw.replace('Must not persist chunked','\\ud800')],['oversized',' '.repeat(8193)+raw],['deep',raw.slice(0,-1)+',"extra":{"a":{"b":{"c":1}}}}']]){
    const result=await new Promise((resolve,reject)=>{const req=require('node:https').request(origin+cp+'/commands',{method:'POST',ca:fs.readFileSync('/run/tls/ca.crt'),headers:{...bearer,'Content-Type':'application/json','Transfer-Encoding':'chunked'}},res=>{let data='';res.on('data',c=>data+=c);res.on('end',()=>resolve({status:res.statusCode,cache:res.headers['cache-control'],body:data}));res.on('error',reject);});req.on('error',reject);req.write(body.slice(0,31));req.end(body.slice(31));});
    assert.equal(result.status,400,kind);assert.match(result.cache,/no-store/);streamed.push({kind,effect,status:result.status,transferEncoding:'chunked',contentLength:false});
   }
  }
  fs.writeFileSync('/evidence/mvp06-chunked-inputs.json',JSON.stringify(streamed,null,2));
  // Frozen UUID/route/body/company survives ACK loss, CSRF refusal and reread loss.
  await page.goto(origin+uiPath);const bytes=[];const requests=[];let dropped=false;
  await page.route('**/api/v1/document-types/commands',async route=>{bytes.push(route.request().postData());requests.push({url:route.request().url(),method:route.request().method()});if(!dropped){dropped=true;const response=await route.fetch();assert.equal(response.status(),201);await route.abort('failed');}else await route.continue();});
  await page.getByLabel('Descrizione',{exact:true}).fill('Synthetic uncertain type');await page.getByRole('button',{name:'Salva nuova versione',exact:true}).click();await page.getByRole('button',{name:'Riprova stesso comando'}).waitFor();
  const beforeNav=page.url();await page.locator('a[href="/"]').first().click();assert.equal(page.url(),beforeNav);assert.equal(await page.getByLabel('Società autorizzata').count(),0,'uncertain state hides stale company/data');
  let csrfRefused=false;await page.route('**/auth/csrf',async route=>{if(!csrfRefused){csrfRefused=true;await route.fulfill({status:403,body:'{}'});}else await route.continue();});
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();await page.unroute('**/auth/csrf');
  let readFailed=false;await page.route('**/api/v1/document-types?*',async route=>{if(!readFailed){readFailed=true;await route.abort('failed');}else await route.continue();});
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();await page.unroute('**/api/v1/document-types?*');
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('heading',{name:'Dettaglio: Synthetic uncertain type',exact:true}).waitFor();
  assert.equal(bytes.length,3);assert.ok(bytes.every(b=>b===bytes[0]));assert.ok(requests.every(r=>r.url===origin+cp+'/commands'&&r.method==='POST'));await page.unroute('**/api/v1/document-types/commands');
  fs.writeFileSync('/evidence/mvp06-retry-envelope.json',JSON.stringify({serializedBodies:bytes,requests,identicalAttempts:bytes.length,recoveryHorizon:'live-page-only'},null,2));
  const layouts=[];for(const viewport of [{width:390,height:844},{width:1366,height:768},{width:1920,height:1080}]){await page.setViewportSize(viewport);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);let measured=0;for(const e of await page.locator('.document-types-workspace input,.document-types-workspace select,.document-types-workspace button').all()){if(!await e.isVisible())continue;const box=await e.boundingBox();assert.ok(box&&box.width>0&&box.x>=0&&box.x+box.width<=viewport.width);measured++;}assert.ok(measured>=7);await page.screenshot({path:'/evidence/mvp06-editor-'+viewport.width+'.png',fullPage:true});layouts.push({viewport,measured,horizontalOverflow:false});}
  fs.writeFileSync('/evidence/mvp06-editor-viewports.json',JSON.stringify(layouts,null,2));
  const refused=async()=>{assert.equal((await request(page,detailPath)).status,403);assert.equal((await jwt.request.get(origin+detailPath,{headers:bearer})).status(),403);const ssr=await operator.context.request.get(origin+uiPath);assert.doesNotMatch(await ssr.text(),/Synthetic uncertain type/);assert.match(ssr.headers()['cache-control'],/no-store/);};
  const readPermission=permissions.find(p=>p.action==='document-types.read'&&p.legalEntityId===company);
  const movedRead=env('permission',{resourceId:readPermission.resourceId,expectedRevision:1,label:readPermission.label,action:'document-types.read',legalEntityId:other,siteId:null,warehouseId:null});
  assert.equal((await post(owner.page,roles,movedRead)).status,200);await refused();
  assert.deepEqual((await request(page,cp)).value.companies.map(c=>c.id),[other]);assert.equal((await request(page,cp+'?legalEntityId='+other)).status,200);
  assert.equal((await post(owner.page,roles,{...movedRead,commandId:uuid(),expectedRevision:2,legalEntityId:company})).status,200);
  const createPermission=permissions.find(p=>p.action==='document-types.create'&&p.legalEntityId===company);
  const changed=env('permission',{resourceId:createPermission.resourceId,expectedRevision:1,label:createPermission.label,action:'document-types.edit',legalEntityId:company,siteId:null,warehouseId:null});assert.equal((await post(owner.page,roles,changed)).status,200);
  const denied={...jwtCommand,commandId:uuid()};assert.equal((await post(page,cp+'/commands',denied)).status,403);assert.equal((await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:denied})).status(),403);
  assert.equal((await post(owner.page,roles,{...changed,commandId:uuid(),expectedRevision:2,action:'document-types.create'})).status,200);
  await updateRole([]);await refused();assert.equal((await post(page,cp+'/commands',JSON.parse(bytes[0]))).status,403);await updateRole(permissions.map(p=>p.resourceId));
  const revoked={...assignment,commandId:uuid(),resourceId:assigned.value.snapshot.resourceId,expectedRevision:1,active:false};assert.equal((await post(owner.page,roles,revoked)).status,200);await refused();assert.equal((await post(owner.page,roles,{...revoked,commandId:uuid(),expectedRevision:2,active:true})).status,200);
  await control('doctype-binding-replace');assert.ok([401,403].includes((await request(page,detailPath)).status));assert.ok([401,403].includes((await jwt.request.get(origin+detailPath,{headers:bearer})).status()));await control('doctype-binding-restore');
  const resumed=await login(browser,5);assert.equal((await request(resumed.page,detailPath)).status,200);
  const disabled={commandId:uuid(),membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,expectedRevision:member.accessRevision,enabled:false};assert.equal((await post(owner.page,roles+'/membership-access',disabled)).status,200);assert.ok([401,403].includes((await request(resumed.page,detailPath)).status));assert.ok([401,403].includes((await jwt.request.get(origin+detailPath,{headers:bearer})).status()));
  await resumed.page.goto(origin+uiPath);assert.doesNotMatch(await resumed.page.content(),/Synthetic uncertain type/);
  await control('doctype-audit-readback');
  // Preserve the original exact six-definition/twelve-audit readback above.
  // Add separate persisted paging acceptance; passing-first regression coverage.
  assert.equal((await post(owner.page,roles+'/membership-access',{...disabled,commandId:uuid(),expectedRevision:disabled.expectedRevision+1,enabled:true})).status,200);
  const pagingUser=await login(browser,5);const paging=[];
  for(let i=0;i<21;i++){
   const result=await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:{...jwtCommand,commandId:uuid(),label:'Synthetic paging '+i}});assert.equal(result.status(),201);paging.push((await result.json()).snapshot);
  }
  for(let revision=1;revision<=23;revision++){
   const result=await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:{...jwtCommand,commandId:uuid(),operation:'edit',documentTypeId:paging[0].id,expectedRevision:revision,label:'Synthetic paging 0 revision '+revision,effect:['Load','Unload','Transfer','None'][revision%4]}});assert.equal(result.status(),201);
  }
  const pagingResults=[];
  for(const javaScriptEnabled of [false,true]){
   const context=await browser.newContext({javaScriptEnabled});await context.addCookies(await pagingUser.context.cookies());const pp=await context.newPage();
   const response=await pp.goto(origin+'/document-types?legalEntityId='+company+'&search=Synthetic%20paging');assert.match(response.headers()['cache-control'],/no-store/);
   assert.equal(await pp.getByRole('link',{name:/^Synthetic paging /}).count(),20);await pp.getByRole('link',{name:'Pagina successiva',exact:true}).click();assert.equal(await pp.getByRole('link',{name:/^Synthetic paging /}).count(),1);
   await pp.getByRole('link',{name:'Torna alla prima pagina',exact:true}).click();assert.equal(await pp.getByRole('link',{name:/^Synthetic paging /}).count(),20);
   await pp.goto(origin+'/document-types?legalEntityId='+company+'&id='+paging[0].id);assert.equal(await pp.getByRole('link',{name:/^Versione [0-9]+:/}).count(),20);
   await pp.getByRole('link',{name:'Versioni precedenti',exact:true}).click();assert.equal(await pp.getByRole('link',{name:/^Versione [0-9]+:/}).count(),4);
   await pp.getByRole('link',{name:'Versione 1: Synthetic paging 0',exact:true}).click();await pp.getByRole('heading',{name:'Versione selezionata: 1',exact:true}).waitFor();
   await pp.getByRole('link',{name:'Versioni più recenti',exact:true}).click();assert.equal(await pp.getByRole('link',{name:/^Versione [0-9]+:/}).count(),20);
   fs.writeFileSync('/evidence/mvp06-paging-'+javaScriptEnabled+'.html',await pp.content());pagingResults.push({javaScriptEnabled,listPages:[20,1],historyPages:[20,4],selectedHistoricalVersion:1});await context.close();
  }
  fs.writeFileSync('/evidence/mvp06-paging-results.json',JSON.stringify(pagingResults,null,2));
  await control('doctype-paging-readback');
  fs.writeFileSync('/evidence/mvp06-browser-result.json',JSON.stringify({oidc:true,jwt:true,fourEffects:true,companyIsolation:true,noJs:true,csrfRefusal:true,exactRetry:true,currentRolePermissionAssignmentRevoke:true,currentBindingRevoke:true,currentDisable:true,standaloneWithoutMasterSetup:true},null,2));
  console.log('PASS MVP06 real OIDC/JWT company types, immutable history, SSR/noJS and current authority');
 }catch(error){let n=0;for(const context of browser.contexts())for(const page of context.pages()){if(page.url().startsWith(origin+'/document-types')||page.url().startsWith(origin+'/users')){fs.writeFileSync('/evidence/mvp06-failure-'+n+'.html',await page.content());await page.screenshot({path:'/evidence/mvp06-failure-'+n+'.png',fullPage:true});n++;}}throw error;
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
