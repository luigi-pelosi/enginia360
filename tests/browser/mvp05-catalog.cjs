const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const pendingRequests=new WeakMap();
function track(page){
 const active=new Map();pendingRequests.set(page,active);
 page.on('request',request=>active.set(request,{method:request.method(),path:new URL(request.url()).pathname}));
 for(const event of ['requestfinished','requestfailed'])page.on(event,request=>active.delete(request));
 return page;
}
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
 const context=await browser.newContext();const page=track(await context.newPage());
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
 const geometry=page=>page.evaluate(()=>({innerWidth,innerHeight,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,visualWidth:visualViewport?.width,readyState:document.readyState,fonts:document.fonts.status,overflowing:[...document.querySelectorAll('body *')].map(element=>({tag:element.tagName,className:typeof element.className==='string'?element.className:'',x:element.getBoundingClientRect().x,width:element.getBoundingClientRect().width})).filter(box=>box.width>0&&(box.x<0||box.x+box.width>innerWidth)).slice(0,40)})).catch(()=>null);
 try {
  const anonymous=track(await browser.newPage());
  for(let i=0;i<60;i++){try{await anonymous.goto(origin+'/auth/session');break;}catch(e){if(i===59)throw e;await new Promise(r=>setTimeout(r,500));}}
  const cp='/api/v1/catalog/management';
  assert.equal((await request(anonymous,cp)).status,401);
  const owner=await login(browser,4);await control('grant');
  const tenant=fixture.contexts[0].tenantId;
  const roles='/api/v1/platform/tenant-roles/'+tenant;
  const directory=(await request(owner.page,roles)).value;
  assert.deepEqual(directory.actions,['organization-context.read','organization-context.write','counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write','counterparties.extensions.read','counterparties.extensions.write','catalog.shared.read','catalog.shared.create','catalog.shared.edit','document-types.read','document-types.create','document-types.edit','documents.read','documents.save','documents.confirm','inventory.document-effects.apply','inventory.quantities.read','inventory.policy.read','inventory.policy.manage','documents.develop','document-types.paths.manage']);
  const member=directory.memberships.find(m=>m.membershipId===fixture.grantTargetMembershipId);assert.ok(member);
  const post=async(page,path,body)=>request(page,path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(page,'/auth/csrf')).value.requestToken},body:JSON.stringify(body)});
  const uuid=()=>require('node:crypto').randomUUID();
  const env=(kind,values)=>({commandId:uuid(),kind,resourceId:null,expectedRevision:0,...values});
  const invitation=await post(owner.page,roles+'/onboarding',{commandId:uuid(),operation:'invite',resourceId:null,expectedRevision:0});assert.equal(invitation.status,200);
  const pending=await login(browser,3,true,invitation.value.snapshot.invitationId);
  assert.equal((await request(pending.page,cp)).status,401);
  const permissions=[];
  // All new finite actions are configured through the actual Italian D97 editor.
  await owner.page.goto(origin+'/users?tenant='+tenant);
  for(const action of ['catalog.shared.read','catalog.shared.create','catalog.shared.edit']){
   await owner.page.getByLabel('Nome permesso',{exact:true}).fill('Synthetic '+action);
   await owner.page.getByLabel('Azione supportata').selectOption(action);
   assert.equal(await owner.page.getByLabel('Scope magazzino esatto').count(),0);
   assert.equal(await owner.page.getByLabel('Scope società esatta').count(),0);
   await owner.page.getByRole('button',{name:'Salva permesso',exact:true}).click();
   await owner.page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
   const permission=(await request(owner.page,roles)).value.permissions.find(p=>p.action===action);assert.ok(permission);
   assert.equal(permission.legalEntityId,null);assert.equal(permission.siteId,null);assert.equal(permission.warehouseId,null);permissions.push(permission);
  }
  const roleBody=env('role',{label:'Synthetic catalog operator',permissionIds:permissions.map(p=>p.resourceId)});
  const roleReply=await post(owner.page,roles,roleBody);assert.equal(roleReply.status,200);const role=roleReply.value.snapshot;
  const assignment=env('assignment',{roleId:role.resourceId,membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,active:true});
  const assigned=await post(owner.page,roles,assignment);assert.equal(assigned.status,200);
  const operator=await login(browser,5);const page=operator.page;
  assert.equal((await request(page,cp)).status,200);assert.equal((await request(page,roles)).status,403);
  assert.equal((await request(page,cp)).value.authority.state,'missing');
  await control('master-setup');
  const journeys=[];
  for(const [kind,italian] of [['Article','Articolo'],['Service','Servizio']]){
   await page.goto(origin+'/catalog');await page.getByRole('button',{name:'Nuovo articolo o servizio',exact:true}).click();
   await page.getByRole('combobox',{name:'Tipo',exact:true}).selectOption(kind);await page.getByLabel('Descrizione',{exact:true}).fill('Synthetic standalone '+kind);
   await page.getByRole('button',{name:'Crea identità catalogo',exact:true}).click();
   await page.getByRole('heading',{name:'Dettaglio: Synthetic standalone '+kind}).waitFor();
   const item=(await request(page,cp+'?search='+kind+'&kind='+kind)).value.items.find(i=>i.label==='Synthetic standalone '+kind);assert.ok(item);
   assert.equal(item.kind,kind);assert.equal(item.revision,1);
   await page.getByLabel('Cerca articoli e servizi').fill('standalone '+kind);await page.getByLabel('Filtro tipo').selectOption(kind);
   await page.getByRole('button',{name:'Cerca',exact:true}).click();await page.getByRole('link',{name:item.label,exact:true}).click();
   await page.getByRole('heading',{name:'Dettaglio: '+item.label}).waitFor();
   await page.getByLabel('Descrizione',{exact:true}).fill('x'.repeat(101));await page.getByRole('button',{name:'Salva identità catalogo',exact:true}).click();
   await page.getByRole('status').filter({hasText:'Comando rifiutato'}).waitFor();assert.equal(await page.getByRole('button',{name:'Riprova stesso comando'}).count(),0);
   await page.getByLabel('Descrizione',{exact:true}).fill('Synthetic edited '+kind);await page.getByRole('button',{name:'Salva identità catalogo',exact:true}).click();
   await page.getByRole('heading',{name:'Dettaglio: Synthetic edited '+kind}).waitFor();
   const actual=(await request(page,cp+'?id='+item.id)).value.detail;assert.equal(actual.revision,2);assert.equal(actual.kind,kind);
   journeys.push(actual);
   const csrfBody={commandId:uuid(),operation:'create',itemId:null,expectedRevision:0,authorityVersion:1,kind,label:'Must not exist CSRF '+kind};
   const missingCsrf=await request(page,cp+'/commands',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(csrfBody)});
   assert.equal(missingCsrf.status,400);assert.equal(missingCsrf.value.error,'csrf_invalid');
   const currentCsrf=(await request(page,'/auth/csrf')).value.requestToken;
   const changedCsrf=await request(page,cp+'/commands',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':currentCsrf+'tampered'},body:JSON.stringify(csrfBody)});
   assert.equal(changedCsrf.status,400);assert.equal(changedCsrf.value.error,'csrf_invalid');assert.equal((await request(page,cp+'?search=Must%20not%20exist%20CSRF')).value.items.length,0);
   const nojs=await browser.newContext({javaScriptEnabled:false});await nojs.addCookies(await operator.context.cookies());
   const nojsPage=track(await nojs.newPage());const response=await nojsPage.goto(origin+'/catalog?id='+item.id);const html=await nojsPage.content();
   assert.match(html,new RegExp('Synthetic edited '+kind));assert.match(html,new RegExp(italian));
   const headers=await response.allHeaders();assert.match(headers['cache-control'],/private/);assert.match(headers['cache-control'],/no-store/);
   fs.writeFileSync('/evidence/mvp05-'+kind+'-nojs.html',html);fs.writeFileSync('/evidence/mvp05-'+kind+'-nojs-headers.json',JSON.stringify(headers,null,2));
   await nojsPage.getByLabel('Cerca articoli e servizi').fill('edited '+kind);await nojsPage.getByLabel('Filtro tipo').selectOption(kind);await nojsPage.getByRole('button',{name:'Cerca',exact:true}).click();
   await nojsPage.getByRole('link',{name:'Synthetic edited '+kind,exact:true}).click();await nojsPage.getByRole('heading',{name:'Dettaglio: Synthetic edited '+kind}).waitFor();
   for(const viewport of [{width:390,height:844},{width:1366,height:768},{width:1920,height:1080}]){
    await nojsPage.setViewportSize(viewport);assert.equal(await nojsPage.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await nojsPage.screenshot({path:'/evidence/mvp05-'+kind+'-nojs-'+viewport.width+'.png',fullPage:true});
   }
   await nojs.close();
  }
  const article=journeys.find(i=>i.kind==='Article');const detailPath=cp+'?id='+article.id;
  // Delay the actual catalog client chunk: SSR reads are usable, but mutation
  // forms must not submit as native GET before their handlers are installed.
  const hydrating=await browser.newContext();await hydrating.addCookies(await operator.context.cookies());
  const hydrationPage=track(await hydrating.newPage());let releaseHydration;let sawChunk;
  const chunkSeen=new Promise(resolve=>{sawChunk=resolve;});
  const chunkGate=new Promise(resolve=>{releaseHydration=resolve;});
  await hydrationPage.route('**/_next/static/chunks/app/catalog/page-*.js',async route=>{sawChunk();await chunkGate;await route.continue();});
  try {
   await hydrationPage.goto(origin+'/catalog?id='+article.id,{waitUntil:'commit'});
   await hydrationPage.getByRole('heading',{name:'Dettaglio: Synthetic edited Article'}).waitFor();
   await Promise.race([chunkSeen,new Promise((_,reject)=>setTimeout(()=>reject(new Error('catalog chunk not intercepted')),10000))]);
   assert.equal(await hydrationPage.getByRole('button',{name:'Salva identità catalogo',exact:true}).isDisabled(),true);
   assert.equal(await hydrationPage.getByRole('button',{name:'Nuovo articolo o servizio',exact:true}).isDisabled(),true);
   assert.equal(await hydrationPage.getByLabel('Descrizione',{exact:true}).isDisabled(),true);
   assert.equal(await hydrationPage.getByRole('button',{name:'Cerca',exact:true}).isDisabled(),false);
   const html=await hydrationPage.content();fs.writeFileSync('/evidence/mvp05-before-hydration.html',html);
   releaseHydration();
   await hydrationPage.waitForFunction(()=>!document.querySelector('.catalog-command fieldset')?.disabled);
   assert.equal(await hydrationPage.getByRole('button',{name:'Salva identità catalogo',exact:true}).isDisabled(),false);
   fs.writeFileSync('/evidence/mvp05-hydration-boundary.json',JSON.stringify({actualClientChunkDelayed:true,ssrReadAvailable:true,mutationDisabledBeforeHydration:true,mutationEnabledAfterHydration:true},null,2));
  } finally {releaseHydration();await hydrating.close();}
  await pending.page.goto(origin+'/catalog?id='+article.id);assert.doesNotMatch(await pending.page.content(),/Synthetic edited Article/);
  const unrelated=await login(browser,1);assert.equal((await request(unrelated.page,detailPath)).status,403);
  await unrelated.page.goto(origin+'/catalog?id='+article.id);assert.doesNotMatch(await unrelated.page.content(),/Synthetic edited Article/);
  assert.equal((await request(page,cp+'?tenant='+fixture.contexts.find(c=>c.tenantId!==tenant).tenantId)).status,400);
  // Provider-signed JWT, not an application-issued or mocked identity.
  const jwt=await browser.newContext();const token=await jwt.request.post('https://idp.r00.test:8443/realms/runtime/protocol/openid-connect/token',{form:{grant_type:'password',client_id:'runtime-bearer-proof',client_secret:fixture.clientSecret,username:fixture.users[5].username,password:fixture.users[5].password}});
  assert.equal(token.status(),200);const bearer={Authorization:'Bearer '+(await token.json()).access_token};
  assert.equal((await jwt.request.get(origin+detailPath,{headers:bearer})).status(),200);
  assert.equal((await jwt.request.get(origin+detailPath,{headers:{Authorization:bearer.Authorization+'bad'}})).status(),401);
  for(const kind of ['Article','Service']){
   const command={commandId:uuid(),operation:'create',itemId:null,expectedRevision:0,authorityVersion:1,kind,label:'Synthetic JWT '+kind};
   const reply=await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:command});assert.equal(reply.status(),201);const snapshot=(await reply.json()).snapshot;
   const edit={...command,commandId:uuid(),operation:'edit',itemId:snapshot.id,expectedRevision:1,label:'Synthetic JWT edited '+kind};
   assert.equal((await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:edit})).status(),201);
   const current=await (await jwt.request.get(origin+cp+'?id='+snapshot.id,{headers:bearer})).json();assert.equal(current.detail.revision,2);assert.equal(current.detail.label,edit.label);
   const replay=await (await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:command})).json();assert.equal(replay.state,'replayed');assert.deepEqual(replay.snapshot,snapshot);
  }
  // Frozen exact bytes: lost accepted response -> CSRF refusal -> historical ACK/GET failure -> live read.
  await page.goto(origin+'/catalog?id='+article.id);const bytes=[];const retryRequests=[];let dropped=false;
  await page.route('**/api/v1/catalog/management/commands',async route=>{bytes.push(route.request().postData());retryRequests.push({url:route.request().url(),method:route.request().method()});if(!dropped){dropped=true;await route.fetch();await route.abort('failed');}else await route.continue();});
  await page.getByLabel('Descrizione',{exact:true}).fill('Synthetic uncertain Article');await page.getByRole('button',{name:'Salva identità catalogo',exact:true}).click();
  await page.getByRole('button',{name:'Riprova stesso comando'}).waitFor();assert.equal(await page.getByLabel('Descrizione',{exact:true}).isDisabled(),true);
  const beforeNav=page.url();await page.locator('a[href="/"]').first().click();assert.equal(page.url(),beforeNav);
  let csrfRefused=false;await page.route('**/auth/csrf',async route=>{if(!csrfRefused){csrfRefused=true;await route.fulfill({status:403,body:'{}'});}else await route.continue();});
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();await page.unroute('**/auth/csrf');
  let readFailed=false;await page.route('**/api/v1/catalog/management?*',async route=>{if(!readFailed){readFailed=true;await route.abort('failed');}else await route.continue();});
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Riprova stesso comando'}).count(),1);await page.unroute('**/api/v1/catalog/management?*');
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('heading',{name:'Dettaglio: Synthetic uncertain Article'}).waitFor();
  assert.equal(bytes.length,3);assert.ok(bytes.every(body=>body===bytes[0]));await page.unroute('**/api/v1/catalog/management/commands');
  assert.ok(retryRequests.every(r=>r.url===origin+cp+'/commands'&&r.method==='POST'));
  fs.writeFileSync('/evidence/mvp05-retry-envelope.json',JSON.stringify({path:cp+'/commands',body:JSON.parse(bytes[0]),serializedBodies:bytes,requests:retryRequests,serializedBodySha256:require('node:crypto').createHash('sha256').update(bytes[0],'utf8').digest('hex'),identicalAttempts:bytes.length,recoveryHorizon:'live-page-only'},null,2));
  const layouts=[];
  for(const viewport of [{width:390,height:844},{width:1366,height:768},{width:1920,height:1080}]){
   await page.setViewportSize(viewport);await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   let measured=0;for(const element of await page.locator('.catalog-workspace input,.catalog-workspace select,.catalog-workspace button').all()){
    if(!await element.isVisible())continue;const box=await element.boundingBox();assert.ok(box&&box.width>0&&box.x>=0&&box.x+box.width<=viewport.width);measured++;
   }
   assert.equal(measured,6);await page.screenshot({path:'/evidence/mvp05-editor-'+viewport.width+'.png',fullPage:true});layouts.push({viewport,measured,horizontalOverflow:false});
  }
  fs.writeFileSync('/evidence/mvp05-editor-viewports.json',JSON.stringify(layouts,null,2));
  // All three configurable security objects affect already-open cookie and JWT sessions.
  const refused=async()=>{
   assert.equal((await request(page,detailPath)).status,403);assert.equal((await jwt.request.get(origin+detailPath,{headers:bearer})).status(),403);
   const deniedSsr=await operator.context.request.get(origin+'/catalog?id='+article.id);assert.doesNotMatch(await deniedSsr.text(),/Synthetic uncertain Article/);assert.match(deniedSsr.headers()['cache-control'],/no-store/);
  };
  const createPermission=permissions.find(p=>p.action==='catalog.shared.create');
  const changed=env('permission',{resourceId:createPermission.resourceId,expectedRevision:1,label:createPermission.label,action:'catalog.shared.edit',legalEntityId:null,siteId:null,warehouseId:null});
  assert.equal((await post(owner.page,roles,changed)).status,200);
  const createDenied={commandId:uuid(),operation:'create',itemId:null,expectedRevision:0,authorityVersion:1,kind:'Article',label:'Must not exist'};
  assert.equal((await post(page,cp+'/commands',createDenied)).status,403);assert.equal((await jwt.request.post(origin+cp+'/commands',{headers:bearer,data:createDenied})).status(),403);
  assert.equal((await post(owner.page,roles,{...changed,commandId:uuid(),expectedRevision:2,action:'catalog.shared.create'})).status,200);
  const emptied={...roleBody,commandId:uuid(),resourceId:role.resourceId,expectedRevision:1,permissionIds:[]};
  assert.equal((await post(owner.page,roles,emptied)).status,200);await refused();assert.equal((await post(page,cp+'/commands',JSON.parse(bytes[0]))).status,403);
  assert.equal((await post(owner.page,roles,{...emptied,commandId:uuid(),expectedRevision:2,permissionIds:permissions.map(p=>p.resourceId)})).status,200);
  const revoked={...assignment,commandId:uuid(),resourceId:assigned.value.snapshot.resourceId,expectedRevision:1,active:false};
  assert.equal((await post(owner.page,roles,revoked)).status,200);await refused();assert.equal((await post(owner.page,roles,{...revoked,commandId:uuid(),expectedRevision:2,active:true})).status,200);
  // Replacing the actual trusted tuple also revokes open OIDC/JWT catalog access.
  await control('catalog-binding-replace');
  assert.ok([401,403].includes((await request(page,detailPath)).status));assert.ok([401,403].includes((await jwt.request.get(origin+detailPath,{headers:bearer})).status()));
  await page.goto(origin+'/catalog?id='+article.id);assert.doesNotMatch(await page.content(),/Synthetic uncertain Article/);
  await control('catalog-binding-restore');
  const resumed=await login(browser,5);assert.equal((await request(resumed.page,detailPath)).status,200);assert.equal((await jwt.request.get(origin+detailPath,{headers:bearer})).status(),200);
  const disabled={commandId:uuid(),membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,expectedRevision:member.accessRevision,enabled:false};
  assert.equal((await post(owner.page,roles+'/membership-access',disabled)).status,200);
  assert.ok([401,403].includes((await request(resumed.page,detailPath)).status));assert.ok([401,403].includes((await jwt.request.get(origin+detailPath,{headers:bearer})).status()));
  await resumed.page.goto(origin+'/catalog?id='+article.id);assert.doesNotMatch(await resumed.page.content(),/Synthetic uncertain Article/);
  await control('catalog-audit-readback');
  fs.writeFileSync('/evidence/mvp05-browser-result.json',JSON.stringify({oidc:true,jwt:true,articleAndService:true,noJs:true,csrfRefusal:true,csrfMissingAndChangedValidPayload:true,exactRetry:true,currentRolePermissionAssignmentRevoke:true,currentBindingRevoke:true,currentDisable:true,standalone:true},null,2));
  console.log('PASS MVP05 actual OIDC/JWT articles AND services, persisted Next SSR/noJS and current authorization');
 } catch(error) {
  const diagnostics=[];
  for(const context of browser.contexts())for(const page of context.pages()){
   const url=new URL(page.url());
   if(url.hostname==='app.r00.test'&&['/catalog','/users'].includes(url.pathname)){
    const index=diagnostics.length;const prefix='/evidence/mvp05-failure-'+index;
    const beforeScreenshot=await geometry(page);const pending=[...(pendingRequests.get(page)?.values()||[])];
    fs.writeFileSync(prefix+'.html',await page.content());
    await page.screenshot({path:prefix+'.png',fullPage:true});
    diagnostics.push({path:url.pathname,viewport:page.viewportSize(),beforeScreenshot,afterScreenshot:await geometry(page),pendingRequests:pending,buttons:await page.getByRole('button').allTextContents(),headings:await page.getByRole('heading').allTextContents()});
   }
  }
  fs.writeFileSync('/evidence/mvp05-failure-state.json',JSON.stringify(diagnostics,null,2));throw error;
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
