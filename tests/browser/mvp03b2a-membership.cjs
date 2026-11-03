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
 try {
  const anonymous=await browser.newPage();
  for(let i=0;i<60;i++){try{await anonymous.goto(origin+'/auth/session');break;}catch(e){if(i===59)throw e;await new Promise(r=>setTimeout(r,500));}}
  const owner=await login(browser,4); await control('grant');
  const scope=fixture.contexts[0]; const route='/api/v1/platform/tenant-roles/'+scope.tenantId;
  const get=page=>request(page,route); const commands=new Set();
  const post=async(page,url,body)=>{
   const r=await request(page,url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':(await request(page,'/auth/csrf')).value.requestToken},body:JSON.stringify(body)});
   if(r.value?.state==='applied'&&url.endsWith('/membership-access'))commands.add(body.commandId); return r;
  };
  const initial=await get(owner.page); assert.equal(initial.status,200); assert.equal(initial.cache,'no-store');
  const ordinary=initial.value.memberships.find(m=>m.membershipId===fixture.adminMembershipId);
  const delegate=initial.value.memberships.find(m=>m.membershipId===fixture.grantTargetMembershipId);
  assert.equal(ordinary.accessEnabled,true); assert.equal(ordinary.accessRevision,0);
  const grant={commandId:require('node:crypto').randomUUID(),kind:'delegation',resourceId:null,expectedRevision:0,membershipId:delegate.membershipId,internalIdentityId:delegate.internalIdentityId,bindingHash:delegate.bindingHash,active:true};
  assert.equal((await post(owner.page,route,grant)).status,200);
  const user=await login(browser,0); const admin=await login(browser,5);
  const tokenContext=await browser.newContext();
  const tr=await tokenContext.request.post('https://idp.r00.test:8443/realms/runtime/protocol/openid-connect/token',{form:{grant_type:'password',client_id:'runtime-bearer-proof',client_secret:fixture.clientSecret,username:fixture.users[0].username,password:fixture.users[0].password}});
  assert.equal(tr.status(),200); const headers={Authorization:'Bearer '+(await tr.json()).access_token};
  const bearer=()=>tokenContext.request.get(origin+'/api/v1/organization/contexts',{headers});
  assert.equal((await request(user.page,'/api/v1/organization/contexts')).value.length,1);
  assert.equal((await (await bearer()).json()).length,1);
  const command=(m,enabled)=>({commandId:require('node:crypto').randomUUID(),membershipId:m.membershipId,internalIdentityId:m.internalIdentityId,bindingHash:m.bindingHash,expectedRevision:m.accessRevision,enabled});
  const disable=command(ordinary,false);
  assert.equal((await request(owner.page,route+'/membership-access',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(disable)})).status,400,'cookie command requires current CSRF');
  assert.equal((await post(admin.page,route+'/membership-access',disable)).status,200);
  assert.deepEqual((await request(user.page,'/api/v1/organization/contexts')).value,[]);
  assert.deepEqual(await (await bearer()).json(),[],'same signed JWT rechecks current state');
  assert.equal((await request(user.page,'/auth/session')).value.authenticated,true,'disable is not implicit session deletion');
  const nojs=await browser.newContext({javaScriptEnabled:false,storageState:await owner.context.storageState()});
  const ssr=await nojs.newPage(); const response=await ssr.goto(origin+'/users?tenant='+scope.tenantId);
  assert.ok(response.headers()['cache-control'].includes('no-store'));
  assert.match(await ssr.locator('body').innerText(),/Accesso al tenant: disabilitato/);
  assert.match(await ssr.locator('body').innerText(),/Delega gestione utenti/);
  assert.match(await ssr.locator('body').innerText(),/Delega struttura/);
  assert.equal(await ssr.getByRole('button',{name:'Disabilita accesso al tenant',exact:true}).count(),0,'no-JS retains state but no actionable membership command');
  fs.writeFileSync('/evidence/membership-disabled-ssr.html',await ssr.content());
  fs.writeFileSync('/evidence/membership-disabled-ssr-headers.json',JSON.stringify(Object.fromEntries(Object.entries(response.headers()).filter(([key])=>['cache-control','vary','content-type','content-security-policy','x-content-type-options','x-frame-options','referrer-policy'].includes(key))),null,2));
  const foreign=await request(admin.page,'/api/v1/platform/tenant-roles/'+fixture.contexts[1].tenantId);
  assert.equal(foreign.status,403);
  await admin.page.goto(origin+'/users');
  assert.equal(await admin.page.getByRole('note').filter({hasText:/Attenzione: disabilitando il proprio accesso/}).isVisible(),true,'self-disable warning visible to the current delegate');
  const memberForm=admin.page.locator('form.membership-command').filter({hasText:ordinary.membershipId});
  assert.equal(await memberForm.count(),1,'exact membership target selector');
  let attempts=0;let failRead=false; const bodies=[];
  await admin.page.route('**/api/v1/platform/tenant-roles/'+scope.tenantId+'**',async r=>{
   if(r.request().method()==='POST'&&r.request().url().endsWith('/membership-access')){
    bodies.push(r.request().postData()); attempts++;
    const response=await r.fetch(); const value=await response.json();
    if(value.state==='applied')commands.add(JSON.parse(r.request().postData()).commandId);
    if(attempts===1){await r.abort('failed');return;}
    if(attempts===2)failRead=true;
    await r.fulfill({response});return;
   }
   if(failRead&&r.request().method()==='GET'){failRead=false;await r.fulfill({status:503,contentType:'application/json',body:'{}'});return;}
   await r.continue();
  });
  await memberForm.getByRole('button',{name:'Abilita accesso al tenant',exact:true}).click();
  await admin.page.getByRole('status').filter({hasText:'Esito da verificare'}).waitFor();
  assert.equal(await memberForm.getByRole('button',{name:'Disabilita accesso al tenant',exact:true}).isDisabled(),true);
  const frozenURL=admin.page.url();await admin.page.getByRole('navigation').getByRole('link',{name:'Panoramica',exact:true}).click();assert.equal(admin.page.url(),frozenURL);
  for(let i=0;i<2;i++){
   await admin.page.getByRole('button',{name:'Riprova stesso comando',exact:true}).click();
   await admin.page.getByRole('status').filter({hasText:i===0?'Esito da verificare':'Modifica verificata'}).waitFor();
  }
  assert.equal(bodies.length,3);assert.equal(new Set(bodies).size,1,'in-page uncertainty retries identical UUID/target/revision/body');
  assert.deepEqual(Object.keys(JSON.parse(bodies[0])).sort(),['bindingHash','commandId','enabled','expectedRevision','internalIdentityId','membershipId']);
  await admin.page.unroute('**/api/v1/platform/tenant-roles/'+scope.tenantId+'**');
  assert.equal((await (await bearer()).json()).length,1);assert.equal((await request(user.page,'/api/v1/organization/contexts')).value.length,1);
  assert.equal((await post(admin.page,route+'/membership-access',disable)).value.state,'replayed');
  assert.equal((await (await bearer()).json()).length,1,'historical replay does not undo later enable');
  // Disable an actual current user administrator. Open cookie, current SSR and
  // signed bearer administration must all lose authority without deleting grant.
  const current=(await get(owner.page)).value.memberships.find(m=>m.membershipId===delegate.membershipId);
  const selfDisable=command(current,false);assert.equal((await post(admin.page,route+'/membership-access',selfDisable)).status,200);
  assert.equal((await get(admin.page)).status,403);assert.equal((await post(admin.page,route+'/membership-access',selfDisable)).status,403,'authority checked before replay');
  await admin.page.reload();assert.equal(await admin.page.getByRole('button',{name:'Salva ruolo',exact:true}).count(),0);
  const disabled=(await get(owner.page)).value.memberships.find(m=>m.membershipId===delegate.membershipId);
  assert.equal(disabled.active,true,'disable preserves separate delegation');
  assert.equal((await post(owner.page,route+'/membership-access',command(disabled,true))).status,200);
  assert.equal((await get(admin.page)).status,200,'explicit owner restore preserves still-current delegation');
  await owner.page.goto(origin+'/users?tenant='+scope.tenantId);
  for(const width of [1440,1024,390]){
   await owner.page.setViewportSize({width,height:900});await owner.page.screenshot({path:'/evidence/membership-'+width+'.png',fullPage:true});
   assert.equal(await owner.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  }
  fs.writeFileSync('/run/control/expected.json',JSON.stringify({commands:[...commands]}));await control('membership-audit-readback');
  fs.writeFileSync('/evidence/membership-browser-results.json',JSON.stringify({oidc:true,bearer:true,currentSSR:true,csrf:true,noStore:true,frozenIdenticalAttempts:bodies.length,operationalReadiness:false},null,2));
  await nojs.close();await tokenContext.close();
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
