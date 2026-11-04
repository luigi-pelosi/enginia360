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
  const cp='/api/v1/counterparties/management';
  assert.equal((await request(anonymous,cp)).status,401);
  const owner=await login(browser,4);await control('grant');
  const tenant=fixture.contexts[0].tenantId;const company=fixture.contexts[0].legalEntityId;
  const roles='/api/v1/platform/tenant-roles/'+tenant;
  const catalog=await request(owner.page,roles);assert.equal(catalog.status,200);
  assert.deepEqual(catalog.value.actions,['organization-context.read','organization-context.write','counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write','counterparties.extensions.read','counterparties.extensions.write','catalog.shared.read','catalog.shared.create','catalog.shared.edit','document-types.read','document-types.create','document-types.edit']);
  const member=catalog.value.memberships.find(m=>m.membershipId===fixture.grantTargetMembershipId);assert.ok(member);
  const post=async(page,path,body)=>request(page,path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(page,'/auth/csrf')).value.requestToken},body:JSON.stringify(body)});
  const env=(kind,values)=>({commandId:require('node:crypto').randomUUID(),kind,resourceId:null,expectedRevision:0,...values});
  const invitation=await post(owner.page,roles+'/onboarding',{commandId:require('node:crypto').randomUUID(),operation:'invite',resourceId:null,expectedRevision:0});
  assert.equal(invitation.status,200);
  const pendingIdentity=await login(browser,3,true,invitation.value.snapshot.invitationId);
  const pendingStatus=await request(pendingIdentity.page,'/auth/onboarding/status');
  assert.equal(pendingStatus.status,200);assert.equal(pendingStatus.value.approved,false);
  assert.equal((await request(pendingIdentity.page,'/auth/session')).value.authenticated,false);
  assert.ok((await pendingIdentity.context.cookies()).some(c=>c.name==='__Host-enginia360-pending'));
  assert.equal((await request(pendingIdentity.page,cp)).status,401,'actual pending ticket never enters new business port');
  // Real permission editor now selects scope by executable action, not warehouse-only.
  await owner.page.goto(origin+'/users?tenant='+tenant);
  await owner.page.getByLabel('Nome permesso',{exact:true}).fill('Synthetic UI shared read');
  await owner.page.getByLabel('Azione supportata').selectOption('counterparties.shared.read');
  assert.equal(await owner.page.getByLabel('Scope magazzino esatto').count(),0);
  await owner.page.getByRole('button',{name:'Salva permesso',exact:true}).click();
  await owner.page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  const refreshed=(await request(owner.page,roles)).value;
  const permissions=[refreshed.permissions.find(p=>p.label==='Synthetic UI shared read').resourceId];
  await owner.page.getByLabel('Nome permesso',{exact:true}).fill('Synthetic UI company read');
  await owner.page.getByLabel('Azione supportata').selectOption('counterparties.extensions.read');
  await owner.page.getByLabel('Scope società esatta').selectOption(company);
  assert.equal(await owner.page.getByLabel('Scope magazzino esatto').count(),0);
  await owner.page.getByRole('button',{name:'Salva permesso',exact:true}).click();
  await owner.page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  permissions.push((await request(owner.page,roles)).value.permissions.find(p=>p.label==='Synthetic UI company read').resourceId);
  for(const action of ['counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write','counterparties.extensions.write']){
   const r=await post(owner.page,roles,env('permission',{label:'Synthetic '+action,action,legalEntityId:action.includes('.extensions.')?company:null,siteId:null,warehouseId:null}));
   assert.equal(r.status,200);permissions.push(r.value.snapshot.resourceId);
  }
  const roleBody=env('role',{label:'Synthetic operator not SUPER ADMIN',permissionIds:permissions});
  const role=(await post(owner.page,roles,roleBody)).value.snapshot;
  const assignment=env('assignment',{roleId:role.resourceId,membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,active:true});
  const assigned=await post(owner.page,roles,assignment);assert.equal(assigned.status,200);
  const operator=await login(browser,5);const page=operator.page;
  assert.equal((await request(page,cp)).status,200);
  assert.equal((await request(page,roles)).status,403,'operative roles do not grant administration');
  await control('master-setup');
  await page.goto(origin+'/counterparties');
  await page.getByRole('button',{name:'Nuova controparte',exact:true}).click();
  await page.getByLabel('Denominazione',{exact:true}).fill('Synthetic standalone MVP04');
  await page.getByRole('button',{name:'Crea controparte',exact:true}).click();
  await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  await page.getByRole('heading',{name:'Dettaglio: Synthetic standalone MVP04'}).waitFor();
  const initial=(await request(page,cp+'?search=standalone%20MVP04')).value.items.find(i=>i.legalName==='Synthetic standalone MVP04');assert.ok(initial);
  await page.getByLabel('Cerca controparti').fill('standalone MVP04');
  await page.getByRole('button',{name:'Cerca',exact:true}).click();
  await page.getByRole('link',{name:'Synthetic standalone MVP04',exact:true}).click();
  await page.getByRole('heading',{name:'Dettaglio: Synthetic standalone MVP04'}).waitFor();
  const detailPath=cp+'?id='+initial.id;
  await pendingIdentity.page.goto(origin+'/counterparties?id='+initial.id);
  assert.doesNotMatch(await pendingIdentity.page.content(),/Synthetic standalone MVP04/);
  const ungrantedCompany=fixture.deniedContexts.find(c=>c.legalEntityId!==company);assert.ok(ungrantedCompany);
  assert.equal((await request(page,detailPath+'&company='+ungrantedCompany.legalEntityId)).status,403);
  const same=(await request(page,detailPath)).value.detail;assert.equal(same.revision,1);assert.equal(same.fiscalIdentifier,'');
  // Fresh CSRF, definite invalid input correction, then real persisted edit.
  await page.getByLabel('Denominazione',{exact:true}).fill('x'.repeat(201));
  await page.getByRole('button',{name:'Salva dati comuni',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Comando rifiutato'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Riprova stesso comando'}).count(),0);
  await page.getByLabel('Denominazione',{exact:true}).fill('Synthetic edited MVP04');
  await page.getByRole('button',{name:'Salva dati comuni',exact:true}).click();
  await page.getByRole('heading',{name:'Dettaglio: Synthetic edited MVP04'}).waitFor();
  await page.getByLabel('Fornitore (ruolo aziendale)').check();
  await page.getByRole('button',{name:'Salva ruolo fornitore',exact:true}).click();
  await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  assert.equal((await request(page,detailPath)).value.detail.isSupplier,true);
  await page.getByLabel('Fornitore (ruolo aziendale)').uncheck();
  await page.getByRole('button',{name:'Salva ruolo fornitore',exact:true}).click();
  await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  assert.equal((await request(page,detailPath)).value.detail.isSupplier,false);
  await page.getByLabel('Fornitore (ruolo aziendale)').check();
  await page.getByRole('button',{name:'Salva ruolo fornitore',exact:true}).click();
  await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  assert.equal((await request(page,detailPath)).value.detail.isSupplier,true);
  await page.getByLabel('Società destinazioni').selectOption(company);
  await page.getByRole('button',{name:'Apri destinazioni societarie'}).click();
  await page.getByLabel('Indirizzo destinazione').fill('Synthetic company address');
  await page.getByRole('button',{name:'Salva destinazione privata'}).click();
  await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  const destinations=(await request(page,detailPath+'&company='+company)).value.destinations;assert.equal(destinations.length,1);
  await page.getByLabel('Destinazione da modificare').selectOption(destinations[0].id);
  await page.getByLabel('Indirizzo destinazione').fill('Synthetic company address updated');
  await page.getByRole('button',{name:'Salva destinazione privata'}).click();
  await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  const after=(await request(page,detailPath+'&company='+company)).value;
  assert.equal(after.detail.revision,5);assert.equal(after.destinations[0].revision,2);
  const foreign=fixture.contexts.find(c=>c.tenantId!==tenant);assert.ok(foreign);
  assert.equal((await request(page,detailPath+'&company='+foreign.legalEntityId)).status,403);
  assert.equal((await request(page,cp+'/commands',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).status,400,'cookie commands without CSRF refuse');
  // Real authenticated no-JavaScript SSR; no supplied identity props.
  const nojs=await browser.newContext({javaScriptEnabled:false});await nojs.addCookies(await operator.context.cookies());
  const nojsPage=await nojs.newPage();const ssr=await nojsPage.goto(origin+'/counterparties?id='+initial.id+'&company='+company);
  const html=await nojsPage.content();assert.match(html,/Synthetic edited MVP04/);assert.match(html,/Synthetic company address updated/);
  assert.match((await ssr.allHeaders())['cache-control'],/no-store/);assert.match((await ssr.allHeaders())['cache-control'],/private/);
  fs.writeFileSync('/evidence/mvp04-nojs.html',html);fs.writeFileSync('/evidence/mvp04-nojs-headers.json',JSON.stringify(await ssr.allHeaders(),null,2));
  const unrelated=await login(browser,1);assert.equal((await request(unrelated.page,detailPath)).status,403);
  await unrelated.page.goto(origin+'/counterparties?id='+initial.id);assert.doesNotMatch(await unrelated.page.content(),/Synthetic edited MVP04/);
  // Actual provider-signed JWT uses the very same current role lookup.
  const jwt=await browser.newContext();const token=await jwt.request.post('https://idp.r00.test:8443/realms/runtime/protocol/openid-connect/token',{form:{grant_type:'password',client_id:'runtime-bearer-proof',client_secret:fixture.clientSecret,username:fixture.users[5].username,password:fixture.users[5].password}});
  assert.equal(token.status(),200);const bearer={Authorization:'Bearer '+(await token.json()).access_token};
  assert.equal((await jwt.request.get(origin+detailPath,{headers:bearer})).status(),200);
  assert.equal((await jwt.request.get(origin+detailPath,{headers:{Authorization:bearer.Authorization+'bad'}})).status(),401);
  // Accepted response loss -> CSRF refusal -> replay acceptance/read failure -> exact retry.
  const bytes=[];let dropped=false;
  await page.route('**/api/v1/counterparties/management/commands',async route=>{
   bytes.push(route.request().postData());if(!dropped){dropped=true;await route.fetch();await route.abort('failed');}else await route.continue();
  });
  await page.getByLabel('Denominazione',{exact:true}).fill('Synthetic uncertain MVP04');
  await page.getByRole('button',{name:'Salva dati comuni',exact:true}).click();await page.getByRole('button',{name:'Riprova stesso comando'}).waitFor();
  assert.equal(await page.getByLabel('Denominazione',{exact:true}).isDisabled(),true);
  const beforeNav=page.url();await page.locator('a[href="/"]').first().click();assert.equal(page.url(),beforeNav);
  let csrfRefused=false;
  await page.route('**/auth/csrf',async route=>{if(!csrfRefused){csrfRefused=true;await route.fulfill({status:403,body:'{}'});}else await route.continue();});
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();
  await page.unroute('**/auth/csrf');let readFailed=false;
  await page.route('**/api/v1/counterparties/management?*',async route=>{if(!readFailed){readFailed=true;await route.abort('failed');}else await route.continue();});
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Riprova stesso comando'}).count(),1);
  await page.unroute('**/api/v1/counterparties/management?*');
  await page.getByRole('button',{name:'Riprova stesso comando'}).click();await page.getByRole('heading',{name:'Dettaglio: Synthetic uncertain MVP04'}).waitFor();
  assert.equal(bytes.length,3);assert.ok(bytes.every(body=>body===bytes[0]));await page.unroute('**/api/v1/counterparties/management/commands');
  fs.writeFileSync('/evidence/mvp04-retry-envelope.json',JSON.stringify({path:cp+'/commands',body:JSON.parse(bytes[0]),identicalAttempts:bytes.length},null,2));
  // Measure actual authorized interactive forms too, not only the noJS read view.
  const editorLayouts=[];
  for(const viewport of [{width:390,height:844},{width:1366,height:768},{width:1920,height:1080}]){
   await page.setViewportSize(viewport);
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   await page.getByRole('button',{name:'Salva dati comuni',exact:true}).waitFor();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   const controls=page.locator('.counterparty-workspace input,.counterparty-workspace textarea,.counterparty-workspace select,.counterparty-workspace button');
   let measured=0;
   for(const control of await controls.all()){
    if(!await control.isVisible())continue;
    const rect=await control.boundingBox();assert.ok(rect && rect.width>0 && rect.x>=0 && rect.x+rect.width<=viewport.width,'interactive control clipped at '+viewport.width);
    measured++;
   }
   assert.equal(measured,14,'all actual shared/role/private-company controls must be present');
   await page.screenshot({path:'/evidence/mvp04-editor-'+viewport.width+'.png',fullPage:true});
   editorLayouts.push({width:viewport.width,height:viewport.height,measuredControls:measured,horizontalOverflow:false});
  }
  fs.writeFileSync('/evidence/mvp04-editor-viewports.json',JSON.stringify(editorLayouts,null,2));
  // Current permission/role and membership state revoke existing cookie/JWT sessions.
  const emptied={...roleBody,commandId:require('node:crypto').randomUUID(),resourceId:role.resourceId,expectedRevision:1,permissionIds:[]};
  assert.equal((await post(owner.page,roles,emptied)).status,200);
  assert.equal((await request(page,detailPath)).status,403);assert.equal((await jwt.request.get(origin+detailPath,{headers:bearer})).status(),403);
  assert.equal((await post(page,cp+'/commands',JSON.parse(bytes[0]))).status,403,'authorization before historical replay');
  assert.equal((await post(owner.page,roles,{...emptied,commandId:require('node:crypto').randomUUID(),expectedRevision:2,permissionIds:permissions})).status,200);
  const disable={commandId:require('node:crypto').randomUUID(),membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,expectedRevision:member.accessRevision,enabled:false};
  assert.equal((await post(owner.page,roles+'/membership-access',disable)).status,200);
  assert.ok([401,403].includes((await request(page,detailPath)).status));assert.ok([401,403].includes((await jwt.request.get(origin+detailPath,{headers:bearer})).status()));
  for(const viewport of [{width:390,height:844},{width:1366,height:768},{width:1920,height:1080}]){
   await nojsPage.setViewportSize(viewport);assert.equal(await nojsPage.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await nojsPage.screenshot({path:'/evidence/mvp04-'+viewport.width+'.png',fullPage:true});
  }
  await control('counterparty-audit-readback');
  fs.writeFileSync('/evidence/mvp04-browser-result.json',JSON.stringify({oidc:true,jwt:true,noJs:true,csfrRefusal:true,exactRetry:true,currentRoleRevoke:true,currentDisable:true,standalone:true},null,2));
  console.log('PASS MVP04 real OIDC/JWT SSR/noJS tenant/company isolation role enforcement create edit supplier destination and uncertainty');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
