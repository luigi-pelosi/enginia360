const assert = require('node:assert/strict');
const fs = require('node:fs');
const https = require('node:https');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json', 'utf8'));
const origin = 'https://app.r00.test:8443';
let stage = 'trusted TLS startup';
const checks = [];
function passed(name) { checks.push(name); console.log('PASS ' + name); }
function requestStatus(url, options={}) {
  return new Promise((resolve,reject)=>{
    const request=https.get(url,{servername:new URL(url).hostname,...options},response=>{response.resume();resolve(response.statusCode);});
    request.on('error',reject);request.setTimeout(5000,()=>request.destroy(new Error('request timeout')));
  });
}
async function control(action) {
  try { fs.unlinkSync('/run/control/ack'); } catch {}
  fs.writeFileSync('/run/control/request',action);
  for (let attempt=0;attempt<600;attempt++) {
    if (fs.existsSync('/run/control/ack') && fs.readFileSync('/run/control/ack','utf8')===action) return;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  throw new Error('Lifecycle acknowledgement timeout');
}
async function json(page, path, options = {}) {
  return page.evaluate(async ({path, options}) => {
    const response = await fetch(path, options);
    let value;
    try { value = await response.json(); } catch { value = null; }
    return { status: response.status, value, location: response.headers.get('location'), cache: response.headers.get('cache-control') };
  }, {path, options});
}
async function csrf(page) { return (await json(page, '/auth/csrf')).value.requestToken; }
async function tokenError(parameters) {
  const body=new URLSearchParams({client_id:'runtime-browser',client_secret:fixture.clientSecret,...parameters}).toString();
  return new Promise((resolve,reject)=>{
    const request=https.request('https://idp.r00.test:8443/realms/runtime/protocol/openid-connect/token',{
      method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded','Content-Length':Buffer.byteLength(body)},
    },response=>{
      let data='';response.on('data',chunk=>{data+=chunk;if(data.length>65536) request.destroy(new Error('response limit'));});response.on('end',()=>{
        try { const value=JSON.parse(data);resolve({status:response.statusCode,error:value.error,description:value.error_description}); }
        catch { reject(new Error('invalid provider response')); }
      });
    });
    request.on('error',reject);request.setTimeout(5000,()=>request.destroy(new Error('provider timeout')));request.end(body);
  });
}
async function login(browser, index, holdCallback=false) {
  const context = await browser.newContext();
  const page = await context.newPage();
  let callbackUrl;
  page.on('request', request => { if (new URL(request.url()).pathname === '/signin-oidc') callbackUrl = request.url(); });

  await page.goto(origin + '/auth/session');
  const token = await csrf(page);

  const authorize = page.waitForRequest(request => new URL(request.url()).hostname === 'idp.r00.test' && new URL(request.url()).pathname.endsWith('/auth'));
  await page.evaluate(token => {
    const form = document.createElement('form');
    form.method = 'POST'; form.action = '/auth/login';
    const input = document.createElement('input');
    input.name = '__RequestVerificationToken'; input.value = token;
    form.append(input); document.body.append(form); form.submit();
  }, token);
  const authorizeRequest = await authorize;
  await page.waitForURL(url => url.hostname === 'idp.r00.test');
  const query = new URL(authorizeRequest.url()).searchParams;

  if (!query.has('request_uri')) {
    assert.equal(query.get('response_type'), 'code');
    assert.equal(query.get('code_challenge_method'), 'S256');
    assert(query.get('state')); assert(query.get('nonce')); assert(query.get('code_challenge'));
  } else {
    assert.equal(query.get('client_id'), 'runtime-browser');

  }
  await page.locator('#username').fill(fixture.users[index].username);
  await page.locator('#password').fill(fixture.users[index].password);
  if (holdCallback) {
    // Intercept the *first* request in the redirect chain, not its callback descendant.
    // Only this negative fixture uses interception; positive browser logins are untouched.
    let complete;
    const held = new Promise(resolve => { complete=resolve; });
    await page.route(url=>url.hostname==='idp.r00.test' && url.pathname.endsWith('/login-actions/authenticate'),async route=>{
      if(route.request().method()!=='POST') return route.continue();
      const response=await route.fetch({maxRedirects:0});
      callbackUrl=response.headers().location;
      assert.equal(new URL(callbackUrl).hostname,'app.r00.test');
      assert.equal(new URL(callbackUrl).pathname,'/signin-oidc');
      await route.fulfill({status:200,contentType:'text/plain',body:'Acceptance holds this callback for the negative PKCE exchange.'});
      complete();
    });
    await page.locator('#kc-login').click();
    await held;
    await page.goto(origin+'/auth/session');
    return {context,page,callbackUrl};
  }
  try {
    await Promise.all([page.waitForURL(url => url.hostname === 'app.r00.test'), page.locator('#kc-login').click()]);
  } catch (error) {
    console.log('IDP_FORM_DIAGNOSTIC ' + JSON.stringify(await page.evaluate(() => ({title:document.title, inputs:[...document.querySelectorAll('input')].map(input=>input.name), error:document.querySelector('#input-error, .kc-feedback-text')?.textContent}))));
    throw error;
  }
  await page.waitForLoadState('domcontentloaded');
  return {context, page, callbackUrl};
}
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const probe = await browser.newContext();
    const first = await probe.newPage();
    let ready = false;
    for (let attempt = 0; attempt < 40; attempt++) {
      try {
        const response = await first.goto(origin + '/auth/session');
        if (response.status() === 200) { ready = true; break; }
      } catch {}
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    assert(ready, 'TLS app readiness');
    assert.equal((await json(first, '/api/v1/organization/contexts')).status, 401);
    assert.equal((await json(first, '/auth/login', {method:'POST'})).status, 400);
    assert.equal((await json(first, '/auth/logout', {method:'POST'})).status, 400);
    assert.equal((await json(first, '/signin-oidc?code=forged&state=forged')).status, 400);
    assert.equal((await json(first, '/auth/session')).value.authenticated, false);
    passed('anonymous API401, login/logout CSRF400 and forged callback400 over CA-trusted TLS');
    stage='strict TLS and Host boundary';
    const untrusted=await chromium.launch({headless:true,env:{...process.env,HOME:'/tmp/untrusted-browser-home'}});
    try {
      const untrustedPage=await untrusted.newPage();
      await assert.rejects(untrustedPage.goto(origin+'/auth/session'),error=>error.message.includes('ERR_CERT_AUTHORITY_INVALID'));
    } finally { await untrusted.close(); }
    await assert.rejects(requestStatus('https://api:8443/health/live'),{code:'ERR_TLS_CERT_ALTNAME_INVALID'});
    assert.equal(await requestStatus(origin+'/auth/session',{headers:{Host:'forged.invalid'}}),400);
    assert.equal(await requestStatus('https://api.r00.test:8443/auth/session',{headers:{'X-Forwarded-Proto':'https','X-Forwarded-Host':'app.r00.test:8443'}}),400);
    for(const path of ['/API/v1/DEVELOPMENT/LOGIN/','/api/v1/organization/Database-Session/descendant','/ADMIN/']) {
      const denied=await first.request.get(origin+path);
      assert.equal(denied.status(),404);assert.equal(denied.headers()['x-r00-edge-denial'],'1');
    }
    passed('TLS hostname verification, exact edge/backend Host and protected edge routes');
    stage='confidential client, direct grant disabled and actual PKCE rejection';
    assert.equal((await tokenError({grant_type:'password',username:fixture.users[0].username,password:fixture.users[0].password})).error,'unauthorized_client');
    const invalidClient=await tokenError({grant_type:'authorization_code',code:'invalid',client_secret:'incorrect'});
    assert.equal(invalidClient.status,401);
    assert(['invalid_client','unauthorized_client'].includes(invalidClient.error));
    const held=await login(browser,0,true);
    const wrongVerifier=await tokenError({grant_type:'authorization_code',redirect_uri:origin+'/signin-oidc',code:new URL(held.callbackUrl).searchParams.get('code'),code_verifier:'wrong-verifier-'.repeat(5)});
    console.log('PKCE_REJECTION ' + JSON.stringify({...wrongVerifier,description:String(wrongVerifier.description).replace(/[A-Za-z0-9_.-]{40,}/g,'[redacted]').slice(0,160)}));
    assert.equal(wrongVerifier.status,400);assert.equal(wrongVerifier.error,'invalid_grant');assert.match(wrongVerifier.description,/PKCE|code.verifier/i);
    assert.equal((await json(held.page,'/auth/session')).value.authenticated,false);
    await held.context.close();
    passed('real confidential client authentication, disabled password grant and provider PKCE verifier rejection');
    stage = 'real confidential code+S256 browser login';
    const a = await login(browser, 0);
    assert.equal((await json(a.page, '/auth/session')).value.authenticated, true);
    assert.equal(new URL(a.page.url()).search, '');
    const cookies = await a.context.cookies(origin);
    const session = cookies.find(cookie => cookie.name === '__Host-enginia360-session');
    assert(session && session.secure && session.httpOnly);
    assert.equal(session.path, '/'); assert.equal(session.sameSite, 'Lax'); assert.equal(session.expires, -1);
    assert(!cookies.some(cookie => cookie.name.includes('Nonce') || cookie.name.includes('Correlation')));
    const replayCallback = await a.context.request.get(a.callbackUrl, {maxRedirects:0});
    assert.equal(replayCallback.status(),400);
    const stores = await a.page.evaluate(() => ({local:Object.keys(localStorage), session:Object.keys(sessionStorage), visible:document.cookie}));
    assert.deepEqual(stores.local, []); assert.deepEqual(stores.session, []); assert(!stores.visible.includes('__Host-enginia360'));
    passed('actual Chromium/Keycloak login, secure opaque HttpOnly cookie, no JS tokens/storage/callback query');
    stage = 'cookie authorized write/read and CSRF negative';
    const contexts = await json(a.page, '/api/v1/organization/contexts');
    assert.equal(contexts.status, 200); assert.equal(contexts.value.length, 1);
    assert.equal(contexts.value[0].tenantId, fixture.contexts[0].tenantId);
    assert.equal(contexts.value[0].readPermission, 'organization-context.read', 'own exact read grant is visible');
    assert.equal(contexts.value[0].capability, 'organization-context');
    assert.equal(contexts.value[0].canWrite, true);
    const tampered = await json(a.page, '/api/v1/organization/contexts?tenantId='+fixture.contexts[2].tenantId+'&legalEntityId='+fixture.contexts[2].legalEntityId, {headers:{'X-Tenant-Id':fixture.contexts[2].tenantId,'X-User-Id':'forged'}});
    assert.deepEqual(tampered.value, contexts.value, 'client context cannot widen own grants');
    const body = JSON.stringify({...fixture.contexts[0], message:'Synthetic R00 browser note'});
    const created = await json(a.page, '/api/v1/organization/context-notes', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':await csrf(a.page)},body});
    assert.equal(created.status, 201);
    assert.equal((await json(a.page, '/api/v1/organization/context-notes/' + created.value.id)).value.message, 'Synthetic R00 browser note');
    const missing = await json(a.page, '/api/v1/organization/context-notes', {method:'POST',headers:{'Content-Type':'application/json'},body});
    assert.equal(missing.status, 400, 'cookie write without antiforgery must be denied');
    for (const method of ['POST','PUT','PATCH','DELETE']) {
      for (const path of ['/api/v1/organization/context-notes','/API/v1/organization/context-notes','/api/v1/workshop/orders']) {
        assert.equal((await json(a.page,path,{method,headers:{'Content-Type':'application/json'},body})).status,400);
      }
    }
    assert.equal((await json(a.page,'/api/v1/organization/context-notes',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':'invalid'},body})).status,400);
    const foreignToken = await csrf(first);
    assert.equal((await json(a.page,'/api/v1/organization/context-notes',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':foreignToken},body})).status,400);
    const forgedOrigin = await a.context.request.post(origin+'/api/v1/organization/context-notes',{
      headers:{'Content-Type':'application/json','X-CSRF-TOKEN':await csrf(a.page),'Origin':'https://other.r00.test:8443'},data:body,maxRedirects:0,
    });
    assert.equal(forgedOrigin.status(),400);
    const simpleForm = await a.context.request.post(origin+'/api/v1/organization/context-notes',{form:{message:'Denied'},maxRedirects:0});
    assert.equal(simpleForm.status(),400);
    passed('real cookie API write/reread and missing-CSRF rejection');
    stage = 'scope and cross-tenant isolation';
    const b = await login(browser, 1);
    const c = await login(browser, 2);
    assert.equal((await json(b.page, '/api/v1/organization/context-notes', {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-TOKEN':await csrf(b.page)},body:JSON.stringify({...fixture.contexts[1],message:'Denied'})})).status, 403);
    assert.equal((await json(c.page, '/api/v1/organization/context-notes/' + created.value.id)).status, 404);
    const fake = await json(a.page, '/api/v1/organization/contexts', {headers:{Authorization:'Bearer invalid'}});
    assert.equal(fake.status,401);
    const cross = await json(a.page, '/api/v1/organization/context-notes', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':await csrf(a.page)},body:JSON.stringify({...fixture.contexts[2],message:'Denied'})});
    assert.equal(cross.status,403);
    for(const context of fixture.deniedContexts) {
      assert.equal((await json(a.page,'/api/v1/organization/context-notes',{
        method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':await csrf(a.page)},
        body:JSON.stringify({...context,message:'Denied same-tenant scope'}),
      })).status,403);
    }
    for (let i=0;i<20;i++) {
      const values = await Promise.all([json(a.page,'/api/v1/organization/contexts'),json(c.page,'/api/v1/organization/contexts')]);
      assert.equal(values[0].value[0].tenantId,fixture.contexts[0].tenantId);
      assert.equal(values[1].value[0].tenantId,fixture.contexts[2].tenantId);
    }
    passed('insufficient action, cross-tenant read/write, fake bearer no fallback and concurrent identity alternation');
    stage = 'R01.b real limited mandate grant panel';
    const delegate = await login(browser,5);
    assert.deepEqual((await json(delegate.page,'/api/v1/organization/contexts')).value,[]);
    await a.page.goto(origin+'/');
    await a.page.locator('#grant-admin').waitFor({state:'visible'});
    assert.equal(await a.page.locator('#grant-options option').count(),2);
    assert.equal(await a.page.locator('#grant-apply').isDisabled(),true,'explicit confirmation required');
    assert.match(await a.page.locator('#grant-scope').textContent(),/Scadenza:/);
    await a.page.locator('#grant-options').selectOption('0');
    await a.page.locator('#grant-confirm').check();
    await a.page.locator('#grant-apply').click();
    await a.page.getByText('Permesso aggiornato e riletto.',{exact:true}).waitFor();
    assert.equal((await json(delegate.page,'/api/v1/organization/contexts')).value.length,1);
    assert.equal((await json(delegate.page,'/api/v1/organization/contexts')).value[0].canWrite,false);
    assert.deepEqual((await json(delegate.page,'/api/v1/organization/grant-administration')).value,[]);
    const grantBase={...fixture.contexts[0],mandateId:fixture.mandates[0],targetMembershipId:fixture.grantTargetMembershipId,action:'organization-context.read',operation:'grant'};
    const grantCommand=async(page,changes={},token=true)=>json(page,'/api/v1/organization/grant-commands',{
      method:'POST',headers:{'Content-Type':'application/json',...(token?{'X-CSRF-TOKEN':await csrf(page)}:{})},
      body:JSON.stringify({commandId:crypto.randomUUID(),...grantBase,...changes}),
    });
    assert.equal((await grantCommand(a.page,{},false)).status,400);
    for (const change of [{targetMembershipId:fixture.adminMembershipId},{targetMembershipId:crypto.randomUUID()},
      {action:'common-master.edit'},{legalEntityId:fixture.deniedContexts[0].legalEntityId},
      {siteId:fixture.deniedContexts[1].siteId},{warehouseId:fixture.deniedContexts[2].warehouseId},fixture.contexts[2]])
      assert.equal((await grantCommand(a.page,change)).status,403);
    assert.equal((await grantCommand(c.page)).status,403);
    assert.equal((await grantCommand(delegate.page)).status,403);
    // A new command is NOT an idempotent retry: existing resource conflicts visibly.
    await a.page.locator('#grant-confirm').check();
    await a.page.locator('#grant-apply').click();
    await a.page.getByText('Conflitto: comando o permesso già utilizzato. Aggiorna con Riprova prima di una nuova conferma.',{exact:true}).waitFor();
    assert.equal(await a.page.locator('#grant-admin').isVisible(),false);
    await a.page.locator('#retry').click();
    await a.page.locator('#grant-admin').waitFor({state:'visible'});
    await a.page.locator('#grant-options').selectOption('1');
    await a.page.locator('#grant-confirm').check();
    await a.page.locator('#grant-apply').click();
    await a.page.getByText('Permesso aggiornato e riletto.',{exact:true}).waitFor();
    const delegatedWrite=await json(delegate.page,'/api/v1/organization/context-notes',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':await csrf(delegate.page)},body:JSON.stringify({...fixture.contexts[0],message:'Synthetic delegated write'})});
    assert.equal(delegatedWrite.status,201);
    assert.equal((await json(delegate.page,'/api/v1/organization/context-notes/'+delegatedWrite.value.id)).status,200);
    await a.page.locator('#grant-operation').selectOption('revoke');
    await a.page.locator('#grant-confirm').check();
    await a.page.locator('#grant-apply').click();
    await a.page.getByText('Permesso aggiornato e riletto.',{exact:true}).waitFor();
    assert.equal((await json(delegate.page,'/api/v1/organization/contexts')).value[0].canWrite,false);
    await control('mandate-revoke');
    assert.deepEqual((await json(delegate.page,'/api/v1/organization/contexts')).value,[]);
    assert.equal((await json(delegate.page,'/api/v1/organization/context-notes/'+delegatedWrite.value.id)).status,404);
    assert.equal((await grantCommand(a.page,{operation:'revoke'})).status,403);
    await a.page.locator('#retry').click();
    await a.page.getByText('Sessione attiva.',{exact:true}).waitFor();
    assert.equal(await a.page.locator('#grant-admin').isVisible(),false);
    passed('R01.b real confirmed grant/revoke, immediate read/write effects, CSRF and manipulated action/resource/target denials, revoked mandate and no subdelegation');
    stage = 'R01 own grant revocation and disabled capability history';
    assert.equal((await json(b.page, '/api/v1/organization/contexts')).value[0].canWrite, false);
    await control('capability-disable');
    const disabled = (await json(a.page, '/api/v1/organization/contexts')).value[0];
    assert.equal(disabled.capabilityEnabled, false);
    assert.equal(disabled.canWrite, false);
    assert.equal((await json(a.page, '/api/v1/organization/context-notes/'+created.value.id)).status, 200, 'authorized historical read survives capability off');
    assert.equal((await json(a.page, '/api/v1/organization/context-notes', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':await csrf(a.page)},body})).status, 403);
    await control('capability-remove');
    const unconfigured = (await json(a.page, '/api/v1/organization/contexts')).value;
    assert.equal(unconfigured.length, 1, 'own read scope remains visible without capability setup');
    assert.equal(unconfigured[0].capabilityEnabled, null, 'missing activation is not enabled or hidden');
    assert.equal(unconfigured[0].canWrite, false);
    await control('capability-restore');
    await control('write-revoke');
    assert.equal((await json(a.page, '/api/v1/organization/contexts')).value[0].canWrite, false);
    assert.equal((await json(a.page, '/api/v1/organization/context-notes', {method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':await csrf(a.page)},body})).status, 403);
    await control('write-restore');
    await control('read-revoke');
    assert.deepEqual((await json(a.page, '/api/v1/organization/contexts')).value, []);
    assert.equal((await json(a.page, '/api/v1/organization/context-notes/'+created.value.id)).status, 404);
    assert.equal((await json(c.page, '/api/v1/organization/contexts')).value.length, 1, 'pooled foreign principal does not inherit revocation');
    await control('read-restore');
    passed('R01 own exact grants, no client tenant trust, off/unconfigured capability, historical read and immediate grant revocation');
    stage = 'missing binding and membership';
    const unbound = await login(browser,3);
    assert.equal((await json(unbound.page,'/auth/session')).value.authenticated,false);
    const empty = await login(browser,4);
    assert.deepEqual((await json(empty.page,'/api/v1/organization/contexts')).value,[]);
    await empty.page.goto(origin+'/');
    await empty.page.getByText('Sessione attiva, nessun contesto assegnato.',{exact:true}).waitFor();
    assert.equal(await empty.page.locator('#contexts option').count(),0);
    assert.equal(await empty.page.locator('#assigned').isVisible(),false);
    passed('no auto-provisioning, unbound login denied and bound identity without membership has empty context');
    stage = 'binding removal invalidates a live browser ticket';
    await control('binding-revoke');
    assert.equal((await json(c.page,'/api/v1/organization/contexts')).status,401);
    assert.equal((await json(c.page,'/auth/session')).value.authenticated,false);
    passed('removed binding revokes next cookie request without cached grants');
    stage = 'database outage and recovery';
    await control('database-outage');
    const unavailable = await json(b.page,'/api/v1/organization/contexts');
    assert.equal(unavailable.status,503);
    assert.equal(unavailable.location,null);
    assert(!JSON.stringify(unavailable.value).includes('Password'));
    await control('database-recover');
    assert.equal((await json(b.page,'/api/v1/organization/contexts')).status,200);
    passed('real database outage503 fail-closed/no redirect and recovery200');
    stage = 'local logout replay';
    const copied = await browser.newContext();
    await copied.addCookies(cookies);
    const replay = await copied.newPage();
    await replay.goto(origin+'/auth/session');
    const token = await csrf(a.page);
    await control('identity-outage');
    const loggedOut = a.page.waitForResponse(response => new URL(response.url()).pathname === '/auth/logout' && response.status() === 302);
    await a.page.evaluate(token => {
      const form=document.createElement('form'); form.method='POST'; form.action='/auth/logout';
      const input=document.createElement('input');input.name='__RequestVerificationToken';input.value=token;form.append(input);document.body.append(form);form.submit();
    },token);
    await loggedOut;
    await a.page.waitForURL(origin+'/');
    assert.equal((await json(replay,'/api/v1/organization/contexts')).status,401);
    assert.equal((await json(replay,'/auth/session')).value.authenticated,false);
    await control('identity-recover');
    passed('local logout revokes copied-cookie replay');
    stage = 'API restart and new login recovery';
    await control('api-restart');
    let recovered;
    for(let attempt=0;attempt<40;attempt++) {
      recovered=await json(b.page,'/auth/session');
      if(recovered.status===200) break;
      await new Promise(resolve=>setTimeout(resolve,250));
    }
    assert.equal(recovered.status,200);
    assert.equal(recovered.value.authenticated,false);
    assert.equal((await json(b.page,'/api/v1/organization/contexts')).status,401);
    const renewed=await login(browser,1);
    assert.equal((await json(renewed.page,'/api/v1/organization/contexts')).status,200);
    passed('API restart rejects old copied cookie; new real browser login recovers');
    stage = 'minimal real runtime access shell';
    await first.goto(origin+'/');
    await first.getByRole('button',{name:'Accedi',exact:true}).waitFor({state:'visible'});
    await first.getByRole('button',{name:'Accedi',exact:true}).click();
    await first.locator('#username').fill(fixture.users[0].username);
    await first.locator('#password').fill(fixture.users[0].password);
    await Promise.all([first.waitForURL(origin+'/'),first.locator('#kc-login').click()]);
    await first.getByLabel('Nota tecnica').fill('Synthetic shell persisted note');
    await first.getByRole('button',{name:'Salva e rileggi nota'}).click();
    await first.getByText('Nota riletta: Synthetic shell persisted note',{exact:true}).waitFor();
    assert.match(await first.locator('#scope').textContent(), /organization-context.read/);
    assert.match(await first.locator('#scope').textContent(), /Società.*Sede.*Magazzino/);
    assert.match(await first.locator('#capability').textContent(), /organization-context.*Attiva/);
    await renewed.page.goto(origin+'/');
    await renewed.page.getByText('Sessione attiva.',{exact:true}).waitFor();
    assert.equal(await renewed.page.locator('#write').isDisabled(),true, 'read-only grant cannot advertise write');
    await control('capability-disable');
    await first.getByRole('button',{name:'Riprova',exact:true}).click();
    await first.getByText('organization-context: Disabilitata — consultazione storica autorizzata.',{exact:true}).waitFor();
    assert.equal(await first.locator('#write').isDisabled(),true);
    await control('read-revoke');
    await first.getByRole('button',{name:'Riprova',exact:true}).click();
    await first.getByText('Sessione attiva, nessun contesto assegnato.',{exact:true}).waitFor();
    assert.equal(await first.locator('#contexts option').count(),0);
    assert.equal(await first.locator('#scope').textContent(),'');
    await control('read-restore');
    await first.getByRole('button',{name:'Riprova',exact:true}).click();
    await first.getByText('Sessione attiva.',{exact:true}).waitFor();
    await control('api-restart');
    for (let attempt=0;attempt<40;attempt++) {
      if ((await json(first,'/auth/session')).status===200) break;
      await new Promise(resolve=>setTimeout(resolve,250));
    }
    await first.getByRole('button',{name:'Riprova',exact:true}).click();
    await first.getByText('Accesso richiesto.',{exact:true}).waitFor();
    assert.equal(await first.locator('#assigned').isVisible(),false);
    assert.equal(await first.locator('#contexts option').count(),0);
    passed('R01 Italian own scope/capability selection, read-only/off grants, revocation refresh and session expiry clear stale context');
    passed('real minimal access shell login, assigned-context read and supported note write/reread');
    const finalSession = await login(browser,1);
    assert.equal((await json(finalSession.page,'/api/v1/organization/contexts')).status,200);
    console.log('R00_BROWSER_RESULT ' + JSON.stringify({engine:'Chromium',passed:checks.length,skipped:0,phase:process.env.R00_BROWSER_PHASE}));
  } finally { await browser.close(); }
})().catch(error => { console.error('FAIL ' + stage + ': ' + error.name); console.error((error.stack || '').split('\n').filter(line => line.includes('/acceptance/')).join('\n')); process.exitCode=1; });
