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
async function login(browser,index){
 const context=await browser.newContext();const page=await context.newPage();
 await page.goto(origin+'/auth/session');
 const token=(await request(page,'/auth/csrf')).value.requestToken;
 await page.evaluate(token=>{const f=document.createElement('form');f.method='POST';f.action='/auth/login';const i=document.createElement('input');i.name='__RequestVerificationToken';i.value=token;f.append(i);document.body.append(f);f.submit();},token);
 await page.waitForURL(u=>u.hostname==='idp.r00.test');
 await page.locator('#username').fill(fixture.users[index].username);
 await page.locator('#password').fill(fixture.users[index].password);
 await Promise.all([page.waitForURL(u=>u.hostname==='app.r00.test'),page.locator('#kc-login').click()]);
 await page.waitForLoadState('domcontentloaded');
 assert.equal((await request(page,'/auth/session')).value.authenticated,true,'real OIDC session');
 return {context,page};
}(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const anonymous=await browser.newPage();
  for(let i=0;i<60;i++){try{await anonymous.goto(origin+'/auth/session');break;}catch(e){if(i===59)throw e;await new Promise(r=>setTimeout(r,500));}}
  assert.equal((await request(anonymous,'/api/v1/platform/tenant-roles/workspace')).status,401,'tenant role read route must exist and require authentication');
  const owner=await login(browser,4);await control('grant');
  const result=await request(owner.page,'/api/v1/platform/tenant-roles/'+fixture.contexts[0].tenantId);
  assert.equal(result.status,200,'real authenticated role read route missing');
  assert.equal(result.value.mode,'owner');assert.equal(result.cache,'no-store');
  console.log('PASS MVP03B1 real OIDC owner selector');
  const route='/api/v1/platform/tenant-roles/'+fixture.contexts[0].tenantId;
  const member=result.value.memberships.find(m=>m.membershipId===fixture.grantTargetMembershipId);
  const command={commandId:require('node:crypto').randomUUID(),kind:'delegation',resourceId:null,expectedRevision:0,membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,active:true};
  const csrf=(await request(owner.page,'/auth/csrf')).value.requestToken;
  const granted=await request(owner.page,route,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':csrf},body:JSON.stringify(command)});
  assert.equal(granted.status,200,'real user-administration mutation route missing');
  assert.equal(granted.value.state,'applied');
  const appliedIds=new Set([command.commandId]); let noteCount=0;
  const delegated=await login(browser,5);
  const post=async(page,body)=>{const reply=await request(page,route,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(page,'/auth/csrf')).value.requestToken},body:JSON.stringify(body)});if(reply.value?.state==='applied')appliedIds.add(body.commandId);return reply;};
  const envelope=(kind,values)=>({commandId:require('node:crypto').randomUUID(),kind,resourceId:null,expectedRevision:0,...values});
  const scope=fixture.contexts[0];
  const permission=envelope('permission',{label:'Configured HTTP read',action:'organization-context.read',legalEntityId:scope.legalEntityId,siteId:scope.siteId,warehouseId:scope.warehouseId});
  const definition=await post(delegated.page,permission);assert.equal(definition.status,200);
  const role=envelope('role',{label:'SUPER ADMIN',permissionIds:[definition.value.snapshot.resourceId]});
  const composed=await post(delegated.page,role);assert.equal(composed.status,200);
  assert.deepEqual((await request(delegated.page,'/api/v1/organization/contexts')).value,[]);
  const assignment=envelope('assignment',{roleId:composed.value.snapshot.resourceId,membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,active:true});
  const assigned=await post(delegated.page,assignment);assert.equal(assigned.status,200);
  const contexts=await request(delegated.page,'/api/v1/organization/contexts');
  assert.equal(contexts.status,200);assert.equal(contexts.value.length,1,'configured role is not consumed by actual authenticated API');
  assert.equal(contexts.value[0].warehouseId,scope.warehouseId);assert.equal(contexts.value[0].canWrite,false);
  console.log('PASS MVP03B1 actual current role-backed context authorization');
  const ordinary=await login(browser,0);
  const ordinaryMember=result.value.memberships.find(m=>m.membershipId!==member.membershipId);
  assert.ok(ordinaryMember);
  assert.equal((await post(delegated.page,envelope('assignment',{roleId:composed.value.snapshot.resourceId,membershipId:ordinaryMember.membershipId,internalIdentityId:ordinaryMember.internalIdentityId,bindingHash:ordinaryMember.bindingHash,active:true}))).status,200);
  const overlap=await request(ordinary.page,'/api/v1/organization/contexts');
  assert.equal(overlap.value.length,1,'independent legacy and role origins must not duplicate the authorized context');
  const noteBody={...scope,message:'Synthetic current role consumption'};
  const note=async(page,body=noteBody)=>request(page,'/api/v1/organization/context-notes',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(page,'/auth/csrf')).value.requestToken},body:JSON.stringify(body)});
  assert.equal((await note(delegated.page)).status,403,'read role alone cannot write');
  const writeEdit={...permission,commandId:require('node:crypto').randomUUID(),resourceId:definition.value.snapshot.resourceId,expectedRevision:1,action:'organization-context.write'};
  assert.equal((await post(delegated.page,writeEdit)).status,200);
  assert.deepEqual((await request(delegated.page,'/api/v1/organization/contexts')).value,[],'permission edit immediately removes read on same session');
  const createdNote=await note(delegated.page);assert.equal(createdNote.status,201);noteCount++;
  assert.equal((await request(delegated.page,'/api/v1/organization/context-notes/'+createdNote.value.id)).status,404,'write permission is not read');
  const secondRead=await post(delegated.page,envelope('permission',{...permission,label:'Read again',commandId:require('node:crypto').randomUUID()}));assert.equal(secondRead.status,200);
  const roleEdit={...role,commandId:require('node:crypto').randomUUID(),resourceId:composed.value.snapshot.resourceId,expectedRevision:1,permissionIds:[definition.value.snapshot.resourceId,secondRead.value.snapshot.resourceId]};
  assert.equal((await post(delegated.page,roleEdit)).status,200);
  assert.equal((await request(delegated.page,'/api/v1/organization/contexts')).value[0].canWrite,true);
  assert.equal((await request(delegated.page,'/api/v1/organization/context-notes/'+createdNote.value.id)).status,200,'actual GetNote consumes role read');
  assert.equal((await note(ordinary.page)).status,201,'overlapping legacy and role write origins must not cause duplicate authorization failure');noteCount++;
  assert.equal((await post(delegated.page,{...roleEdit,commandId:require('node:crypto').randomUUID(),expectedRevision:2,permissionIds:[]})).status,200);
  assert.equal((await note(delegated.page)).status,403,'role edit removes write immediately');
  assert.equal((await post(delegated.page,{...roleEdit,commandId:require('node:crypto').randomUUID(),expectedRevision:3})).status,200);
  assert.deepEqual((await post(delegated.page,role)).value,{state:'replayed',snapshot:composed.value.snapshot},'real HTTP replay is historical after role edits');
  assert.equal((await post(delegated.page,{...role,label:'Changed payload with identical key'})).status,409);
  const concurrentRole=envelope('role',{label:'Concurrent technical composition',permissionIds:[]});
  const concurrent=await Promise.all(Array.from({length:4},()=>post(delegated.page,concurrentRole)));
  assert.deepEqual(concurrent.map(r=>r.value.state).sort(),['applied','replayed','replayed','replayed']);
  for(const response of concurrent)assert.deepEqual(response.value.snapshot,concurrent[0].value.snapshot);
  assert.equal((await post(delegated.page,{...assignment,commandId:require('node:crypto').randomUUID(),resourceId:assigned.value.snapshot.resourceId,expectedRevision:1,active:false})).status,200);
  assert.equal((await note(delegated.page)).status,403,'assignment revocation defeats open session');
  assert.equal((await request(delegated.page,'/auth/session')).value.authenticated,true);
  const tokenContext=await browser.newContext();
  const tokenResponse=await tokenContext.request.post('https://idp.r00.test:8443/realms/runtime/protocol/openid-connect/token',{form:{grant_type:'password',client_id:'runtime-bearer-proof',client_secret:fixture.clientSecret,username:fixture.users[5].username,password:fixture.users[5].password}});
  assert.equal(tokenResponse.status(),200);const accessToken=(await tokenResponse.json()).access_token;
  const bearerHeaders={Authorization:'Bearer '+accessToken};
  assert.equal((await tokenContext.request.get(origin+route,{headers:bearerHeaders})).status(),200,'actual signed bearer consumes current user-administration grant');
  assert.deepEqual(await (await tokenContext.request.get(origin+'/api/v1/organization/contexts',{headers:bearerHeaders})).json(),[]);
  assert.equal((await tokenContext.request.get(origin+route,{headers:{Authorization:'Bearer '+accessToken+'bad'}})).status(),401);
  const ordinaryDenied=await request(ordinary.page,route);assert.equal(ordinaryDenied.status,403);
  const orgRoute=path+'/'+scope.tenantId+'/delegations';
  const organizationCandidates=(await request(owner.page,orgRoute)).value.memberships;
  const organizationMember=organizationCandidates.find(m=>m.membershipId===ordinaryMember.membershipId);
  const organizationGrant={commandId:require('node:crypto').randomUUID(),operation:'grant',membershipId:organizationMember.membershipId,internalIdentityId:organizationMember.internalIdentityId,bindingHash:organizationMember.bindingHash,expectedRevision:0};
  assert.equal((await request(owner.page,orgRoute,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':csrf},body:JSON.stringify(organizationGrant)})).status,200);
  assert.equal((await request(ordinary.page,path+'/'+scope.tenantId)).status,200);
  assert.equal((await request(ordinary.page,route)).status,403,'real organization-only administrator has no user administration');
  for(const foreign of [fixture.contexts[1],fixture.contexts[2]])assert.equal((await request(delegated.page,'/api/v1/platform/tenant-roles/'+foreign.tenantId)).status,403);
  for(const bad of [{...permission,action:'*'},{...permission,warehouseId:fixture.contexts[1].warehouseId},{...permission,legalEntityId:null},{...role,permissionIds:['*']},{...role,permissionIds:[definition.value.snapshot.resourceId,definition.value.snapshot.resourceId]}])assert.ok([400,403].includes((await post(delegated.page,{...bad,commandId:require('node:crypto').randomUUID()})).status));
  for(const body of ['{','null','{"kind":"role","kind":"permission"}',JSON.stringify({...permission,label:'x\u0000y'}),JSON.stringify({...permission,label:'\ud800'}),' '.repeat(16385)+'{}'])assert.equal((await request(delegated.page,route,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(delegated.page,'/auth/csrf')).value.requestToken},body})).status,400);
  assert.equal((await request(delegated.page,route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(role)})).status,400,'real cookie CSRF refusal');
  const hugeNumber=JSON.stringify(role).replace('"expectedRevision":0','"expectedRevision":1e999999999');
  assert.equal((await request(delegated.page,route,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(delegated.page,'/auth/csrf')).value.requestToken},body:hugeNumber})).status,400,'JSON numeric exponent must be refused before PostgreSQL conversion');
  console.log('PASS MVP03B1 real API writes reads edits revoke bearer scope CSRF parser and independent legacy origin regressions');
  await owner.page.goto(origin+'/users?tenant='+scope.tenantId);
  assert.equal(await owner.page.getByRole('heading',{name:'Gestione utenti, ruoli e permessi',exact:true}).count(),1,'actual Next SSR role workspace route missing');
  assert.match(await owner.page.locator('footer').innerText(),/Sessione gestita dal backend/,'users workspace must not claim authentication unavailable');
  const uiSave=async(page,button)=>{
   const responsePromise=page.waitForResponse(r=>r.url()===origin+route&&r.request().method()==='POST');
   await page.getByRole('button',{name:button,exact:true}).click();
   const response=await responsePromise;assert.equal(response.status(),200);const result=await response.json();
   if(result.state==='applied')appliedIds.add(JSON.parse(response.request().postData()).commandId);
   await page.getByRole('status').filter({hasText:'Modifica verificata'}).waitFor();return result.snapshot;
  };
  await owner.page.getByLabel('Destinatario delega utenti').selectOption(member.membershipId);
  await uiSave(owner.page,'Revoca gestione utenti');
  assert.equal((await request(delegated.page,route)).status,403,'UI owner revoke current authority');
  await uiSave(owner.page,'Concedi gestione utenti');
  await delegated.page.goto(origin+'/users');
  await delegated.page.getByText('Delega gestione utenti verificata',{exact:false}).waitFor();
  assert.equal(await delegated.page.getByRole('button',{name:'Concedi gestione utenti',exact:true}).count(),0);
  await delegated.page.getByLabel('Nome permesso',{exact:true}).fill('UI read');
  await delegated.page.getByLabel('Azione supportata').selectOption('organization-context.read');
  await delegated.page.getByLabel('Scope magazzino esatto').selectOption(scope.warehouseId);
  const uiPermission=await uiSave(delegated.page,'Salva permesso');
  await delegated.page.getByLabel('Nome ruolo',{exact:true}).fill('UI configured role');
  await delegated.page.getByRole('checkbox',{name:'UI read · organization-context.read',exact:true}).check();
  const uiRole=await uiSave(delegated.page,'Salva ruolo');
  await delegated.page.getByLabel('Utente assegnazione').selectOption(member.membershipId);
  await delegated.page.getByLabel('Ruolo assegnazione').selectOption(uiRole.resourceId);
  await uiSave(delegated.page,'Assegna ruolo');
  assert.equal((await request(delegated.page,'/api/v1/organization/contexts')).value.length,1,'actual UI role assignment is consumed');
  await delegated.page.getByLabel('Ruolo da modificare').selectOption(uiRole.resourceId);
  await delegated.page.getByLabel('Nome ruolo',{exact:true}).fill('UI configured role edited');
  await delegated.page.getByRole('checkbox',{name:'UI read · organization-context.read',exact:true}).uncheck();
  await uiSave(delegated.page,'Salva ruolo');
  assert.deepEqual((await request(delegated.page,'/api/v1/organization/contexts')).value,[],'actual UI role edit removes current access');
  await delegated.page.getByRole('checkbox',{name:'UI read · organization-context.read',exact:true}).check();
  await uiSave(delegated.page,'Salva ruolo');
  assert.equal((await tokenContext.request.get(origin+'/api/v1/organization/contexts',{headers:bearerHeaders})).status(),200);
  assert.equal((await (await tokenContext.request.get(origin+'/api/v1/organization/contexts',{headers:bearerHeaders})).json()).length,1,'current signed bearer operative positive');
  const nojs=await browser.newContext({javaScriptEnabled:false});await nojs.addCookies(await delegated.context.cookies());const nojsPage=await nojs.newPage();
  const nojsResponse=await nojsPage.goto(origin+'/users');const nojsHtml=await nojsResponse.text();
  assert.match(nojsHtml,/UI configured role/);assert.match(nojsHtml,/UI read/);assert.match(nojsResponse.headers()['cache-control'],/private|no-store/);
  fs.writeFileSync('/evidence/roles-nojs.html',nojsHtml);fs.writeFileSync('/evidence/roles-nojs-headers.json',JSON.stringify({'cache-control':nojsResponse.headers()['cache-control'],'content-type':nojsResponse.headers()['content-type']}));
  const deniedSSR=await ordinary.page.context().request.get(origin+'/users');assert.doesNotMatch(await deniedSSR.text(),/UI configured role/);
  await delegated.page.getByLabel('Permesso da modificare').selectOption(uiPermission.resourceId);
  await delegated.page.getByLabel('Nome permesso',{exact:true}).fill('x'.repeat(101));
  const refused=delegated.page.waitForResponse(r=>r.url()===origin+route&&r.request().method()==='POST');
  await delegated.page.getByRole('button',{name:'Salva permesso',exact:true}).click();assert.equal((await refused).status(),400);
  await delegated.page.getByRole('status').filter({hasText:/Esito da verificare|Comando rifiutato/}).waitFor();
  assert.equal(await delegated.page.getByLabel('Nome permesso',{exact:true}).isDisabled(),false,'definite first-attempt validation refusal must allow correction without discarding an uncertain accepted command');
  await delegated.page.getByLabel('Nome permesso',{exact:true}).fill('😀'.repeat(100));await uiSave(delegated.page,'Salva permesso');
  for(const viewport of [{width:1440,height:1000},{width:1024,height:768},{width:390,height:844}]){
   await delegated.page.setViewportSize(viewport);await delegated.page.screenshot({path:'/evidence/roles-'+viewport.width+'.png',fullPage:true});
   assert.equal(await delegated.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,'no horizontal overflow at '+viewport.width);
  }
  await delegated.page.setViewportSize({width:1440,height:1000});
  await delegated.page.getByLabel('Permesso da modificare').selectOption(uiPermission.resourceId);
  await delegated.page.getByLabel('Nome permesso',{exact:true}).fill('UI read edited');
  let attempt=0;const frozenBodies=[];let denyReread=false;
  await delegated.page.route('**/api/v1/platform/tenant-roles/'+scope.tenantId,async intercepted=>{
   if(intercepted.request().method()==='POST'){
    attempt++;frozenBodies.push(intercepted.request().postData());const response=await intercepted.fetch();
    if((await response.json()).state==='applied')appliedIds.add(JSON.parse(intercepted.request().postData()).commandId);
    if(attempt===1){await intercepted.abort('failed');return;}
    if(attempt===2)denyReread=true;
    await intercepted.fulfill({response});return;
   }
   if(denyReread){denyReread=false;await intercepted.fulfill({status:503,contentType:'application/json',body:'{}'});return;}
   await intercepted.continue();
  });
  await delegated.page.getByRole('button',{name:'Salva permesso',exact:true}).click();
  await delegated.page.getByRole('button',{name:'Riprova stesso comando',exact:true}).waitFor();
  await delegated.page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();
  assert.equal(await delegated.page.getByLabel('Nome ruolo',{exact:true}).isDisabled(),true);
  const frozenUrl=delegated.page.url();await delegated.page.getByRole('navigation').getByRole('link',{name:'Panoramica',exact:true}).click();assert.equal(delegated.page.url(),frozenUrl,'SPA links fenced during uncertain mutation');
  await delegated.page.route('**/auth/csrf',async intercepted=>{await intercepted.fulfill({status:400,contentType:'application/json',body:'{}'});});
  await delegated.page.getByRole('button',{name:'Riprova stesso comando',exact:true}).click();await delegated.page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();
  await delegated.page.unroute('**/auth/csrf');
  await delegated.page.getByRole('button',{name:'Riprova stesso comando',exact:true}).click();await delegated.page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();
  await delegated.page.getByRole('button',{name:'Riprova stesso comando',exact:true}).click();await delegated.page.getByRole('status').filter({hasText:'Modifica verificata'}).waitFor();
  assert.equal(frozenBodies.length,3);assert.equal(new Set(frozenBodies).size,1,'lost response/CSRF/reread-failure retry preserves exact bytes');
  await delegated.page.unroute('**/api/v1/platform/tenant-roles/'+scope.tenantId);
  await uiSave(delegated.page,'Revoca assegnazione');
  assert.deepEqual((await request(delegated.page,'/api/v1/organization/contexts')).value,[],'UI assignment revoke immediate');
  await owner.page.reload();await owner.page.getByLabel('Destinatario delega utenti').selectOption(member.membershipId);await uiSave(owner.page,'Revoca gestione utenti');
  assert.equal((await request(delegated.page,route)).status,403);assert.equal((await tokenContext.request.get(origin+route,{headers:bearerHeaders})).status(),403,'revoked useradmin denies valid bearer');
  await delegated.page.reload();assert.equal(await delegated.page.getByLabel('Nome ruolo',{exact:true}).count(),0);
  fs.writeFileSync('/run/control/expected.json',JSON.stringify({commands:[...appliedIds],notes:noteCount}));await control('role-audit-readback');
  fs.writeFileSync('/evidence/browser-results.json',JSON.stringify({oidc:true,bearer:true,noJS:true,currentAPIConsumers:['ListContexts','CreateNote','GetNote'],appliedCommands:appliedIds.size,notes:noteCount,frozenIdenticalAttempts:frozenBodies.length,viewports:[1440,1024,390],operationalReadiness:false},null,2));
  console.log('PASS MVP03B1 UI grant/revoke configurable permission/role existing-user assignment live API noJS cache layout frozen retry audit SQL');
  await nojs.close();await tokenContext.close();
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
