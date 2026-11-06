// Final-phase synthetic integration: ONE generated owner/database/identity chain.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {randomUUID:uuid}=require('node:crypto');
const {chromium}=require('playwright');
const {documentDevelopmentJourney,login,request,post,control,origin}=require('./mvp08-document-development.cjs');
const fixture=JSON.parse(fs.readFileSync('/run/fixture.json','utf8'));
const tenants='/api/v1/platform/tenants', docs='/api/v1/documents';
const envelope=(kind,values)=>({commandId:uuid(),kind,resourceId:null,expectedRevision:0,...values});
let activePage;
async function accepted(page,path,body,status=200){const reply=await post(page,path,body);assert.equal(reply.status,status,JSON.stringify(reply));return reply.value.snapshot;}

(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const anonymous=await browser.newPage();
  for(let i=0;i<60;i++){try{await anonymous.goto(origin+'/auth/session');break;}catch(e){if(i===59)throw e;await new Promise(r=>setTimeout(r,500));}}
  assert.equal((await request(anonymous,docs)).status,401);
  const owner=await login(browser,4);activePage=owner.page;
  assert.equal((await request(owner.page,tenants)).status,403,'registration is not owner authority');
  await control('grant'); // existing explicit offline authority tool + exact audit replay
  const create=(kind,tenantId,parentId,name)=>({commandId:uuid(),operation:'create',kind,tenantId,resourceId:null,parentId,name,expectedRevision:0});
  const tenant=(await accepted(owner.page,tenants,create('tenant',null,null,'MVP09 synthetic integrated tenant'))).resourceId;
  const org=tenants+'/'+tenant+'/commands';
  const company=(await accepted(owner.page,org,create('company',tenant,tenant,'MVP09 company'))).resourceId;
  const site=(await accepted(owner.page,org,create('site',tenant,company,'MVP09 site'))).resourceId;
  const warehouse=(await accepted(owner.page,org,create('warehouse',tenant,site,'MVP09 warehouse'))).resourceId;
  const destination=(await accepted(owner.page,org,create('warehouse',tenant,site,'MVP09 transfer destination'))).resourceId;
  const ungrantedCompany=(await accepted(owner.page,org,create('company',tenant,tenant,'MVP09 ungranted company'))).resourceId;
  const ungrantedSite=(await accepted(owner.page,org,create('site',tenant,company,'MVP09 ungranted site'))).resourceId;
  const ctx={tenantId:tenant,legalEntityId:company,siteId:site,warehouseId:warehouse};
  fs.writeFileSync('/evidence/mvp09-created-context.json',JSON.stringify(ctx));
  await control('register-trusted'); // synthetic fixture-only binding/membership, ZERO grants
  const roles='/api/v1/platform/tenant-roles/'+tenant;
  const directory=(await request(owner.page,roles)).value;
  const trusted=directory.memberships.find(m=>m.membershipId!==undefined);assert.equal(directory.memberships.length,1);assert.ok(trusted);
  assert.equal((await request(owner.page,docs)).status,403,'global authority is not business access');
  const orgDelegation=tenants+'/'+tenant+'/delegations';
  const candidate=(await request(owner.page,orgDelegation)).value.memberships.find(m=>m.membershipId===trusted.membershipId);assert.ok(candidate);
  await accepted(owner.page,orgDelegation,{commandId:uuid(),operation:'grant',membershipId:candidate.membershipId,internalIdentityId:candidate.internalIdentityId,bindingHash:candidate.bindingHash,expectedRevision:candidate.revision});
  const admin=await login(browser,5);
  assert.equal((await request(admin.page,roles)).status,403,'organization delegation alone cannot administer users');
  assert.equal((await request(admin.page,docs)).status,403,'organization delegation is not a business grant');
  await accepted(admin.page,org,{commandId:uuid(),operation:'rename',kind:'warehouse',tenantId:tenant,resourceId:warehouse,parentId:site,name:'MVP09 delegated warehouse',expectedRevision:1});
  await accepted(owner.page,roles,envelope('delegation',{membershipId:trusted.membershipId,internalIdentityId:trusted.internalIdentityId,bindingHash:trusted.bindingHash,active:true}));
  assert.equal((await request(admin.page,roles)).status,200);
  assert.equal((await request(admin.page,docs)).status,403,'user administration does not grant business actions');
  assert.equal((await request(admin.page,'/api/v1/platform/tenant-roles/'+fixture.contexts[1].tenantId)).status,403);
  // Public first federated association and approval: no direct SQL grant bypass.
  await admin.page.goto(origin+'/onboarding-admin?tenant='+tenant);
  await admin.page.getByRole('button',{name:'Crea invito privato',exact:true}).click();
  await admin.page.getByRole('status').filter({hasText:'Comando registrato'}).waitFor();
  const invitations=(await request(admin.page,roles+'/onboarding')).value.invitations;assert.equal(invitations.length,1);
  const pendingContext=await browser.newContext();const pending=await pendingContext.newPage();
  await pending.goto(origin+'/onboarding?invitation='+invitations[0].invitationId);
  await Promise.all([pending.waitForURL(u=>u.hostname==='idp.r00.test'),pending.getByRole('button',{name:'Autenticati per richiedere accesso',exact:true}).click()]);
  await pending.locator('#username').fill(fixture.users[3].username);await pending.locator('#password').fill(fixture.users[3].password);
  await Promise.all([pending.waitForURL(u=>u.hostname==='app.r00.test'),pending.locator('#kc-login').click()]);await pending.waitForLoadState('domcontentloaded');
  const pendingStatus=(await request(pending,'/auth/onboarding/status')).value;assert.equal(pendingStatus.approved,false);assert.equal(pendingStatus.tenantId,tenant);
  assert.equal((await request(pending,docs)).status,401);
  await admin.page.reload();await admin.page.getByRole('button',{name:'Approva associazione senza abilitare o assegnare ruoli',exact:true}).click();await admin.page.getByRole('status').filter({hasText:'Comando registrato'}).waitFor();
  const member=(await request(admin.page,roles)).value.memberships.find(m=>m.membershipId!==trusted.membershipId);assert.ok(member);assert.equal(member.accessEnabled,false);assert.equal(member.active,false);
  assert.deepEqual((await request(admin.page,roles)).value.roles,[]);
  const operator=await login(browser,3);activePage=operator.page;
  assert.equal((await request(operator.page,docs)).status,403,'approved disabled membership has no business access');
  await admin.page.goto(origin+'/users?tenant='+tenant);
  await admin.page.locator('form.membership-command').filter({hasText:member.membershipId}).getByRole('button',{name:'Abilita accesso al tenant',exact:true}).click();await admin.page.getByRole('status').filter({hasText:'Modifica verificata'}).waitFor();
  assert.equal((await request(operator.page,docs)).status,403,'enable alone assigns no permissions');
  const permissions=[];
  const definitions=[
   ...['documents.read','documents.save','documents.confirm','documents.develop'].map(action=>({action,scope:'site',value:site})),
   ...['inventory.policy.read','inventory.policy.manage','document-types.read','document-types.create','document-types.edit','document-types.paths.manage','counterparties.extensions.read','counterparties.extensions.write'].map(action=>({action,scope:'company',value:company})),
   ...['catalog.shared.read','catalog.shared.create','catalog.shared.edit','counterparties.shared.read','counterparties.shared.create','counterparties.shared.edit','counterparties.business-roles.write'].map(action=>({action,scope:'tenant'})),
   ...[warehouse,destination].flatMap(w=>['inventory.document-effects.apply','inventory.quantities.read'].map(action=>({action,scope:'warehouse',value:w})))];
  for(const d of definitions){
   await admin.page.getByLabel('Nome permesso',{exact:true}).fill('MVP09 '+d.action+(d.value||''));await admin.page.getByLabel('Azione supportata').selectOption(d.action);
   if(d.scope!=='tenant')await admin.page.getByLabel(d.scope==='site'?'Scope sede esatta':d.scope==='company'?'Scope società esatta':'Scope magazzino esatto').selectOption(d.value);
   await admin.page.getByRole('button',{name:'Salva permesso',exact:true}).click();await admin.page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
   const p=(await request(admin.page,roles)).value.permissions.find(p=>p.label==='MVP09 '+d.action+(d.value||''));assert.ok(p);permissions.push(p);
  }
  // Role administrator assigns actions she does NOT personally possess.
  assert.equal((await request(admin.page,docs)).status,403);
  const rolePayload=envelope('role',{label:'MVP09 explicit business operator',permissionIds:permissions.map(p=>p.resourceId)});
  const role=await accepted(admin.page,roles,rolePayload);
  await accepted(admin.page,roles,envelope('assignment',{roleId:role.resourceId,membershipId:member.membershipId,internalIdentityId:member.internalIdentityId,bindingHash:member.bindingHash,active:true}));
  assert.equal((await request(operator.page,docs)).status,200);assert.equal((await request(operator.page,roles)).status,403);
  await control('counterparty-master-setup');await control('master-setup');
  const page=operator.page;const cp='/api/v1/counterparties/management';
  await page.goto(origin+'/counterparties');await page.getByRole('button',{name:'Nuova controparte',exact:true}).click();await page.getByLabel('Denominazione',{exact:true}).fill('MVP09 shared synthetic supplier');await page.getByRole('button',{name:'Crea controparte',exact:true}).click();await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  const supplier=(await request(page,cp+'?search=MVP09%20shared')).value.items.find(x=>x.legalName==='MVP09 shared synthetic supplier');assert.ok(supplier);
  await page.getByLabel('Fornitore (ruolo aziendale)').check();await page.getByRole('button',{name:'Salva ruolo fornitore',exact:true}).click();await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  await page.getByLabel('Società destinazioni').selectOption(company);await page.getByRole('button',{name:'Apri destinazioni societarie'}).click();await page.getByLabel('Indirizzo destinazione').fill('MVP09 company-only address');await page.getByRole('button',{name:'Salva destinazione privata'}).click();await page.getByRole('status').filter({hasText:'stato corrente riletto'}).waitFor();
  const supplierRead=(await request(page,cp+'?id='+supplier.id+'&company='+company)).value;assert.equal(supplierRead.detail.isSupplier,true);assert.equal(supplierRead.destinations.length,1);
  const sharedSupplierRead=await request(page,cp+'?id='+supplier.id);assert.equal(sharedSupplierRead.status,200);assert.deepEqual(sharedSupplierRead.value.detail,supplierRead.detail);assert.equal('destinations' in sharedSupplierRead.value,false);assert.equal((await request(page,cp+'?id='+supplier.id+'&company='+ungrantedCompany)).status,403);
  const denied=[];
  for(const scope of [{legalEntityId:fixture.contexts[1].legalEntityId,siteId:fixture.contexts[1].siteId},{legalEntityId:ungrantedCompany,siteId:site},{legalEntityId:company,siteId:ungrantedSite}]){const r=await request(page,docs+'?legalEntityId='+scope.legalEntityId+'&siteId='+scope.siteId);assert.equal(r.status,403);denied.push({scope,status:r.status});}
  // Reuse the REAL existing remaining UI/API/SQL journey on this new principal,
  // company and catalog, not a subprocess running an independent old green suite.
  const journey=await documentDevelopmentJourney({browser,owner,operator,ctx,roles,permissions,role,rolePayload,operatorIndex:3});
  // The reused journey ends in a current role revocation. Explicitly restore only
  // its existing permission IDs, on the SAME open session and same generated data.
  await accepted(admin.page,roles,{...rolePayload,commandId:uuid(),resourceId:role.resourceId,expectedRevision:5,permissionIds:permissions.map(p=>p.resourceId)});
  const {article,service,types}=journey, effectDocuments={}, effectReadbacks={};const read=docs+'?legalEntityId='+company+'&siteId='+site;
  for(const [effect,quantity] of [['Load','2'],['Unload','1'],['Transfer','1'],['None','2']]){
   const before=(await request(page,read+'&warehouseId='+warehouse)).value.balances;
   const body={commandId:uuid(),operation:'create',legalEntityId:company,siteId:site,documentId:null,expectedRevision:0,documentTypeId:types[effect].id,expectedTypeRevision:1,title:'MVP09 integrated '+effect,lines:[{id:uuid(),itemId:article.id,catalogRevision:1,quantity,warehouseId:effect==='None'?null:warehouse,destinationWarehouseId:effect==='Transfer'?destination:null},{id:uuid(),itemId:service.id,catalogRevision:1,quantity:'0.500001',warehouseId:null,destinationWarehouseId:null}]};
   const draft=await accepted(page,docs+'/commands',body,201);effectDocuments[effect]=draft.id;
   const saved=(await request(page,read+'&id='+draft.id)).value;assert.equal(saved.detail.state,'Draft');assert.equal(saved.ledger.length,0);assert.deepEqual((await request(page,read+'&warehouseId='+warehouse)).value.balances,before,'Draft changes no stock');
   await page.goto(origin+'/documents?legalEntityId='+company+'&siteId='+site+'&id='+draft.id);await page.getByRole('button',{name:'Conferma documento e applica quantità',exact:true}).click();await page.getByRole('status').filter({hasText:'Documento confermato'}).waitFor();
   const current=(await request(page,read+'&id='+draft.id)).value;assert.equal(current.detail.state,'Confirmed');assert.equal(current.detail.appliedConfiguration.documentType.effect,effect);assert.equal(current.detail.appliedConfiguration.policy.allowNegative,false);assert.equal(current.ledger.length,{Load:1,Unload:1,Transfer:2,None:0}[effect]);effectReadbacks[effect]=current;
  }
  await page.goto(origin+'/documents?legalEntityId='+company+'&siteId='+site);assert.equal(await page.locator('nav[aria-label="Navigazione principale"] a[aria-current="page"]').count(),1);assert.equal(await page.locator('.context-note strong').innerText(),'Contesto del modulo');
  const nojs=await browser.newContext({javaScriptEnabled:false});await nojs.addCookies(await operator.context.cookies());const native=await nojs.newPage();const response=await native.goto(origin+'/counterparties?id='+supplier.id+'&company='+company);const headers=await response.allHeaders();assert.match(headers['cache-control'],/private/);assert.match(headers['cache-control'],/no-store/);assert.match(await native.content(),/MVP09 company-only address/);fs.writeFileSync('/evidence/mvp09-supplier-nojs.html',await native.content());fs.writeFileSync('/evidence/mvp09-ssr-headers.json',JSON.stringify(headers));
  const foreign=await login(browser,1);await foreign.page.goto(native.url());assert.doesNotMatch(await foreign.page.content(),/MVP09 shared synthetic supplier|MVP09 company-only address/);assert.equal((await request(foreign.page,read+'&id='+journey.hop.id)).status,403);
  for(const width of [390,1366,1920]){await native.setViewportSize({width,height:900});assert.equal(await native.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await native.screenshot({path:'/evidence/mvp09-supplier-'+width+'.png',fullPage:true});}
  assert.equal((await request(page,docs+'/commands',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({commandId:uuid(),operation:'policy',legalEntityId:company,expectedRevision:0,allowNegative:false})})).status,400);
  const specification={ctx,member,trustedMembershipId:trusted.membershipId,requestId:pendingStatus.requestId,supplierId:supplier.id,catalogIds:[article.id,service.id],groupedId:journey.grouped.id,hopId:journey.hop.id,effectDocuments,foreignCompany:fixture.contexts[1].legalEntityId};
  fs.writeFileSync('/evidence/mvp09-journey-spec.json',JSON.stringify(specification));fs.writeFileSync('/evidence/mvp09-http-readbacks.json',JSON.stringify({supplierRead,sharedSupplierRead:sharedSupplierRead.value,effectReadbacks,denied}));await control('integrated-readback');
  fs.writeFileSync('/evidence/mvp09-browser.json',JSON.stringify({browserVersion:browser.version(),playwrightVersion:require('playwright/package.json').version,headless:true,realOidc:true,sameOwnerDatabaseFixtureChain:true,firstMembershipDisabled:true,automaticRoles:false,explicitEnableAndD97Editor:true,adminWithoutBusinessGrants:true,noJs:true,privateNoStore:true,csrf:true,fixtureOnlyBootstrap:true,operationalReadiness:false}));
  await nojs.close();await foreign.context.close();await pendingContext.close();await operator.context.close();await admin.context.close();await owner.context.close();await anonymous.close();console.log('PASS MVP09 ONE persisted seven-domain federated journey');
 }catch(error){if(activePage){try{fs.writeFileSync('/evidence/mvp09-failure.html',await activePage.content());fs.writeFileSync('/evidence/mvp09-failure.json',JSON.stringify({url:activePage.url(),error:String(error)}));await activePage.screenshot({path:'/evidence/mvp09-failure.png',fullPage:false});}catch{}}throw error;}finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
