const assert=require('node:assert/strict');
const fs=require('node:fs');
const {randomUUID}=require('node:crypto');
const {chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync('/run/fixture.json','utf8'));
const origin='https://app.r00.test:8443';
async function control(action){try{fs.unlinkSync('/run/control/ack')}catch{}fs.writeFileSync('/run/control/request',action);for(let i=0;i<600;i++){if(fs.existsSync('/run/control/ack')&&fs.readFileSync('/run/control/ack','utf8')===action)return;await new Promise(r=>setTimeout(r,100))}throw Error('control timeout')}
async function request(page,url,options={}){return page.evaluate(async({url,options})=>{const r=await fetch(url,options);let value=null;try{value=await r.json()}catch{}return {status:r.status,value,cache:r.headers.get('cache-control')}},{url,options})}
async function post(page,path,payload){return request(page,path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(page,'/auth/csrf')).value.requestToken},body:JSON.stringify(payload)})}
async function authenticate(page,index,path='/auth/login'){
 const token=(await request(page,'/auth/csrf')).value.requestToken;
 await page.evaluate(({path,token})=>{const f=document.createElement('form');f.method='POST';f.action=path;const i=document.createElement('input');i.name='__RequestVerificationToken';i.value=token;f.append(i);document.body.append(f);f.submit()},{path,token});
 await page.waitForURL(u=>u.hostname==='idp.r00.test'||u.pathname==='/');
 if(new URL(page.url()).hostname==='idp.r00.test'){
  await page.locator('#username').fill(fixture.users[index].username);await page.locator('#password').fill(fixture.users[index].password);
  await Promise.all([page.waitForURL(u=>u.hostname==='app.r00.test'),page.locator('#kc-login').click()]);
 }
 await page.waitForLoadState('domcontentloaded');
}
async function login(browser,index){const context=await browser.newContext();const page=await context.newPage();await page.goto(origin+'/auth/session');await authenticate(page,index);assert.equal((await request(page,'/auth/session')).value.authenticated,true);return {context,page}}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const anonymous=await browser.newPage();for(let i=0;i<60;i++){try{await anonymous.goto(origin+'/auth/session');break}catch(e){if(i===59)throw e;await new Promise(r=>setTimeout(r,500))}}
  const owner=await login(browser,4);await control('grant');
  const scope=fixture.contexts[0];const roles='/api/v1/platform/tenant-roles/'+scope.tenantId;const route=roles+'/onboarding';
  const directory=(await request(owner.page,roles)).value;
  const delegate=directory.memberships.find(m=>m.membershipId===fixture.grantTargetMembershipId);
  const grant={commandId:randomUUID(),kind:'delegation',resourceId:null,expectedRevision:0,membershipId:delegate.membershipId,internalIdentityId:delegate.internalIdentityId,bindingHash:delegate.bindingHash,active:true};
  assert.equal((await post(owner.page,roles,grant)).status,200);
  const admin=await login(browser,5);await admin.page.goto(origin+'/onboarding-admin');
  await admin.page.getByRole('button',{name:'Crea invito privato',exact:true}).click();
  await admin.page.getByRole('status').filter({hasText:'Comando registrato'}).waitFor();
  let current=(await request(admin.page,route)).value;assert.equal(current.invitations.length,1);assert.equal(current.requests.length,0);
  const invitation=current.invitations[0].invitationId;
  const invitationLink=await admin.page.getByRole('link',{name:'/onboarding?invitation='+invitation,exact:true}).getAttribute('href');
  assert.equal(invitationLink,'/onboarding?invitation='+invitation,'private copyable link is relative and bound to this invitation');
  const pendingContext=await browser.newContext();const pending=await pendingContext.newPage();await pending.goto(origin+invitationLink);
  assert.equal((await request(pending,route)).status,401);assert.equal((await request(pending,'/auth/onboarding/status')).status,401);
  assert.equal((await request(pending,'/auth/onboarding/login/'+invitation,{method:'POST'})).status,400,'initiation requires CSRF');
  await Promise.all([pending.waitForURL(u=>u.hostname==='idp.r00.test'),pending.getByRole('button',{name:'Autenticati per richiedere accesso',exact:true}).click()]);
  await pending.locator('#username').fill(fixture.users[3].username);await pending.locator('#password').fill(fixture.users[3].password);
  await Promise.all([pending.waitForURL(u=>u.hostname==='app.r00.test'),pending.locator('#kc-login').click()]);
  await pending.waitForLoadState('domcontentloaded');
  const status=(await request(pending,'/auth/onboarding/status')).value;assert.equal(status.approved,false);assert.equal(status.tenantId,scope.tenantId);
  assert.equal((await request(pending,'/auth/session')).value.authenticated,false);
  assert.equal((await request(pending,'/api/v1/organization/contexts')).status,401);
  assert.equal((await request(pending,roles)).status,401);
  assert.equal((await request(pending,'/api/v1/platform/tenants')).status,401);
  const allCookies=await pendingContext.cookies();assert.ok(allCookies.some(c=>c.name==='__Host-enginia360-pending'&&c.httpOnly&&c.secure));assert.ok(!allCookies.some(c=>c.name==='__Host-enginia360-session'));
  const tokenContext=await browser.newContext();
  const token=await tokenContext.request.post('https://idp.r00.test:8443/realms/runtime/protocol/openid-connect/token',{form:{grant_type:'password',client_id:'runtime-bearer-proof',client_secret:fixture.clientSecret,username:fixture.users[3].username,password:fixture.users[3].password}});
  assert.equal(token.status(),200);const headers={Authorization:'Bearer '+(await token.json()).access_token};
  const bearer=path=>tokenContext.request.get(origin+path,{headers});
  assert.equal((await bearer('/api/v1/organization/contexts')).status(),401,'trusted unbound JWT never becomes ordinary');
  assert.equal((await request(admin.page,'/api/v1/platform/tenant-roles/'+fixture.contexts[1].tenantId+'/onboarding')).status,403);
  const own=(await request(admin.page,'/api/v1/platform/tenant-roles/onboarding/workspace')).value;assert.ok(!('tenants' in own));
  await admin.page.reload();assert.match(await admin.page.locator('body').innerText(),new RegExp(status.requestId));
  const nojs=await browser.newContext({javaScriptEnabled:false,storageState:await pendingContext.storageState()});
  for(const path of ['/users','/organization','/onboarding-admin']){
   const isolated=await nojs.newPage();const result=await isolated.goto(origin+path);
   assert.ok(result.headers()['cache-control'].includes('no-store'));
   const html=await isolated.content();assert.ok(!html.includes(status.requestId));assert.ok(!html.includes(scope.tenantId));
   assert.doesNotMatch(await isolated.locator('body').innerText(),/Soggetto opaco verificato|Delega utenti corrente verificata|Autorità globale verificata/);
   fs.writeFileSync('/evidence/pending-protected-'+path.slice(1)+'.html',html);await isolated.close();
  }
  const cookieIsolation=await browser.newContext();const pendingCookie=allCookies.find(c=>c.name==='__Host-enginia360-pending');
  assert.equal((await (await cookieIsolation.request.get(origin+'/auth/session',{headers:{Cookie:'__Host-enginia360-session='+pendingCookie.value}})).json()).authenticated,false,'pending ticket cannot be renamed into normal scheme');
  const pendingCsrf=(await request(pending,'/auth/onboarding/csrf')).value.requestToken;
  assert.equal((await request(pending,'/api/v1/organization/context-notes',{method:'POST',headers:{'X-CSRF-TOKEN':pendingCsrf,'Content-Type':'application/json'},body:JSON.stringify({...scope,message:'Pending cannot write'})})).status,401);
  assert.equal((await cookieIsolation.request.post(origin+'/auth/onboarding/logout',{headers:{Cookie:allCookies.map(c=>c.name+'='+c.value).join('; '),Origin:'https://foreign.test','X-CSRF-TOKEN':pendingCsrf}})).status(),400,'cross-origin pending command denied');
  await cookieIsolation.close();
  const ssr=await nojs.newPage();const response=await ssr.goto(origin+'/onboarding');assert.ok(response.headers()['cache-control'].includes('no-store'));
  assert.match(await ssr.locator('body').innerText(),/In attesa di approvazione/);assert.doesNotMatch(await ssr.content(),/Soggetto opaco verificato/);
  assert.match(await ssr.locator('footer').innerText(),/sessione pendente consente solo lo stato della richiesta, non accesso aziendale/);
  fs.writeFileSync('/evidence/pending-ssr.html',await ssr.content());fs.writeFileSync('/evidence/pending-ssr-headers.json',JSON.stringify(response.headers(),null,2));
  const adminNojs=await browser.newContext({javaScriptEnabled:false,storageState:await admin.context.storageState()});const read=await adminNojs.newPage();const ar=await read.goto(origin+'/onboarding-admin');
  assert.match(await read.locator('body').innerText(),/Soggetto opaco verificato/);assert.equal(await read.getByRole('button',{name:'Approva associazione senza abilitare o assegnare ruoli'}).count(),0);
  assert.match(await read.locator('footer').innerText(),/Sessione gestita dal backend/);
  fs.writeFileSync('/evidence/approval-ssr.html',await read.content());fs.writeFileSync('/evidence/approval-ssr-headers.json',JSON.stringify(ar.headers(),null,2));
  const commands=[];let attempts=0;let failRead=false;let refuseCsrf=false;
  await admin.page.route('**/auth/csrf',async r=>{if(refuseCsrf){refuseCsrf=false;await r.fulfill({status:400,contentType:'application/json',body:'{"error":"csrf_invalid"}'});return}await r.continue()});
  await admin.page.route('**'+route,async r=>{
   if(r.request().method()==='POST'){
    commands.push(r.request().postData());attempts++;const result=await r.fetch();
    if(attempts===1){refuseCsrf=true;await r.abort('failed');return}
    if(attempts===2)failRead=true;await r.fulfill({response:result});return;
   }
   if(failRead){failRead=false;await r.fulfill({status:503,contentType:'application/json',body:'{}'});return}await r.continue();
  });
  await admin.page.getByRole('button',{name:'Approva associazione senza abilitare o assegnare ruoli',exact:true}).click();
  await admin.page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();
  const frozen=admin.page.url();await admin.page.getByRole('link',{name:'Gestione utenti, accesso e ruoli',exact:true}).click();assert.equal(admin.page.url(),frozen);
  for(let i=0;i<3;i++){await admin.page.getByRole('button',{name:'Riprova stesso comando',exact:true}).click();await admin.page.getByRole('status').filter({hasText:i===2?'Comando registrato':'Esito da verificare'}).waitFor();}
  assert.equal(commands.length,3);assert.equal(new Set(commands).size,1,'same exact UUID/route/body across lost ACK, CSRF refusal, replay and failed reread');
  await admin.page.unroute('**'+route);await admin.page.unroute('**/auth/csrf');
  const approval=JSON.parse(commands[0]);assert.equal((await post(admin.page,route,approval)).value.state,'replayed');
  assert.equal((await request(pending,'/auth/onboarding/status')).value.approved,true);assert.equal((await request(pending,'/auth/session')).value.authenticated,false);
  // Capture the pending ticket before fresh normal login intentionally revokes it.
  for(const width of [390,1024,1440]){
   await ssr.setViewportSize({width,height:900});await ssr.reload();
   assert.match(await ssr.locator('body').innerText(),/Associazione approvata/);
   assert.equal(await ssr.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await ssr.screenshot({path:'/evidence/pending-nojs-'+width+'.png',fullPage:true});
  }
  await pending.goto(origin+'/onboarding');
  await Promise.all([pending.waitForURL(u=>u.hostname==='app.r00.test'&&u.pathname==='/'),pending.getByRole('button',{name:'Accedi dopo l’approvazione',exact:true}).click()]);
  assert.equal((await request(pending,'/auth/session')).value.authenticated,true);
  assert.deepEqual((await request(pending,'/api/v1/organization/contexts')).value,[]);
  assert.deepEqual(await (await bearer('/api/v1/organization/contexts')).json(),[],'same earlier JWT resolves new binding without reload fallback');
  const membership=(await request(admin.page,roles)).value.memberships.find(m=>!directory.memberships.some(x=>x.membershipId===m.membershipId));assert.equal(membership.accessEnabled,false);assert.equal(membership.active,false);
  await admin.page.goto(origin+'/users');const form=admin.page.locator('form.membership-command').filter({hasText:membership.membershipId});await form.getByRole('button',{name:'Abilita accesso al tenant',exact:true}).click();await admin.page.getByRole('status').filter({hasText:'Modifica verificata'}).waitFor();
  assert.deepEqual((await request(pending,'/api/v1/organization/contexts')).value,[],'enable alone confers no implicit scope');
  assert.deepEqual(await (await bearer('/api/v1/organization/contexts')).json(),[],'enable alone confers no bearer scope');
  const permission={commandId:randomUUID(),kind:'permission',resourceId:null,expectedRevision:0,label:'Explicit onboarding context',action:'organization-context.read',...scope};delete permission.tenantId;
  const p=(await post(admin.page,roles,permission)).value.snapshot;
  const r=(await post(admin.page,roles,{commandId:randomUUID(),kind:'role',resourceId:null,expectedRevision:0,label:'Explicit onboarding role',permissionIds:[p.resourceId]})).value.snapshot;
  const assignment={commandId:randomUUID(),kind:'assignment',resourceId:null,expectedRevision:0,membershipId:membership.membershipId,internalIdentityId:membership.internalIdentityId,bindingHash:membership.bindingHash,roleId:r.resourceId,active:true};
  assert.equal((await post(admin.page,roles,assignment)).status,200);
  assert.equal((await request(pending,'/api/v1/organization/contexts')).value.length,1);assert.equal((await (await bearer('/api/v1/organization/contexts')).json()).length,1);
  const noteBody={...scope,message:'Synthetic approved federated subject read/write'};
  assert.equal((await post(pending,'/api/v1/organization/context-notes',noteBody)).status,403,'explicit read assignment does not grant write');
  const writePermission={...permission,commandId:randomUUID(),label:'Explicit onboarding write',action:'organization-context.write'};
  const wp=(await post(admin.page,roles,writePermission)).value.snapshot;
  assert.equal((await post(admin.page,roles,{commandId:randomUUID(),kind:'role',resourceId:r.resourceId,expectedRevision:1,label:'Explicit onboarding role',permissionIds:[p.resourceId,wp.resourceId]})).status,200);
  const created=await post(pending,'/api/v1/organization/context-notes',noteBody);assert.equal(created.status,201);
  assert.equal((await request(pending,'/api/v1/organization/context-notes/'+created.value.id)).status,200);
  assert.equal((await bearer('/api/v1/organization/context-notes/'+created.value.id)).status(),200);
  const bearerWrite=await tokenContext.request.post(origin+'/api/v1/organization/context-notes',{headers:{...headers,'Content-Type':'application/json'},data:noteBody});assert.equal(bearerWrite.status(),201);
  const bearerNote=await bearerWrite.json();assert.equal((await request(pending,'/api/v1/organization/context-notes/'+bearerNote.id)).status,200);
  assert.equal((await post(admin.page,roles+'/membership-access',{commandId:randomUUID(),membershipId:membership.membershipId,internalIdentityId:membership.internalIdentityId,bindingHash:membership.bindingHash,expectedRevision:2,enabled:false})).status,200);
  assert.equal((await post(admin.page,route,approval)).value.state,'replayed');assert.deepEqual((await request(pending,'/api/v1/organization/contexts')).value,[]);assert.deepEqual(await (await bearer('/api/v1/organization/contexts')).json(),[]);
  assert.equal((await post(pending,'/api/v1/organization/context-notes',noteBody)).status,403,'disable defeats existing open normal cookie');
  assert.equal((await bearer('/api/v1/organization/context-notes/'+created.value.id)).status(),404,'disable defeats same previously signed bearer');
  await admin.page.goto(origin+'/onboarding-admin');
  const layouts=[];
  for(const width of [390,1024,1440]){
   await admin.page.setViewportSize({width,height:900});
   await admin.page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   assert.equal(await admin.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await admin.page.screenshot({path:'/evidence/onboarding-'+width+'.png',fullPage:true});
   await read.setViewportSize({width,height:900});await read.reload();
   assert.match(await read.locator('body').innerText(),/associazione approvata/);
   assert.equal(await read.getByRole('button',{name:'Approva associazione senza abilitare o assegnare ruoli'}).count(),0);
   assert.equal(await read.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await read.screenshot({path:'/evidence/onboarding-nojs-'+width+'.png',fullPage:true});layouts.push(width);
  }
  fs.writeFileSync('/evidence/layout-results.json',JSON.stringify({widths:layouts,noHorizontalOverflow:true},null,2));
  await control('onboarding-audit-readback');
  fs.writeFileSync('/evidence/browser-results.json',JSON.stringify({trustedOidc:true,unboundJwtDenied:true,sameJwtBoundAfterApproval:true,pendingDefaultIsolation:true,tenantIsolation:true,csrf:true,noStore:true,noJsSSR:true,frozenAttempts:commands.length,exactBytes:new Set(commands).size===1,initialDisabled:true,enableAloneNoScopes:true,explicitEnableAndRole:true,normalCookieAndSameBearerReadWrite:true,pendingProtectedSSRIsolation:true,namespacedCookieIsolation:true,noJsLayouts:layouts,replayAfterDisable:true},null,2));
  console.log('PASS MVP03B2B trusted OIDC pending and bound JWT/UI/SSR/CSRF/exact frozen retry');
 } finally {await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
