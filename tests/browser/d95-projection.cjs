const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json','utf8'));
const origin = 'https://app.r00.test:8443';
const projected = process.env.D95_PHASE === 'after';
assert(['before','after'].includes(process.env.D95_PHASE));
const ctx = fixture.contexts[1], id = fixture.workshop[1].payerId;
const json = (page,path,options={}) => page.evaluate(async ({path,options})=>{
  const r=await fetch(path,options); return {status:r.status,value:await r.json().catch(()=>null)};
},{path,options});
(async()=>{
 const browser = await chromium.launch({headless:true});
 try {
  const page = await browser.newPage();
  await page.goto(origin+'/'); await page.getByRole('button',{name:'Accedi',exact:true}).click();
  await page.locator('#username').fill(fixture.users[1].username);
  await page.locator('#password').fill(fixture.users[1].password);
  await Promise.all([page.waitForURL(u=>u.hostname==='app.r00.test'),page.locator('#kc-login').click()]);
  await page.goto(origin+'/ui01-runtime.html');
  await page.getByRole('heading',{name:'Nuova commessa',exact:true}).waitFor();
  await page.getByLabel('Ricerca pagante',{exact:true}).fill('Synthetic payerId');
  await page.getByRole('button',{name:'Cerca pagante',exact:true}).click();
  await page.getByRole('option',{name:'Synthetic payerId',exact:true}).waitFor({state:'attached'});
  await page.getByLabel('Pagante',{exact:true}).selectOption(id);
  await page.getByText('Autorità esterna: modifica locale rifiutata; letture disponibili.',{exact:true}).waitFor();
  const role = page.getByRole('checkbox',{name:'Ruolo fornitore',exact:true});
  await role.waitFor();
  assert(await role.isDisabled());
  assert.equal(await role.isChecked(),projected);
  assert.equal(await page.getByRole('button',{name:'Salva ruolo fornitore',exact:true}).count(),0);
  assert.equal(await page.getByLabel('Denominazione comune',{exact:true}).count(),0);
  const endpoint='/api/v1/counterparties/'+id;
  const state=await json(page,endpoint+'/edit-state?legalEntityId='+ctx.legalEntityId);
  assert.equal(state.status,200);
  assert.equal(state.value.counterparty.isSupplier,projected);
  assert.equal(state.value.revision,projected?1:0);
  assert.equal(state.value.counterparty.legalName,'Synthetic payerId');
  const csrf=(await json(page,'/auth/csrf')).value.requestToken;
  for(const [suffix, fields] of [['/supplier-role',{isSupplier:false}],['',{legalName:'Unauthorized',fiscalIdentifier:'SYNTHETIC',registeredOffice:'Synthetic office'}]]) {
   const denied=await json(page,endpoint+suffix,{method:'PUT',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':csrf},body:JSON.stringify({legalEntityId:ctx.legalEntityId,commandId:crypto.randomUUID(),authorityVersion:1,expectedRevision:projected?1:0,...fields})});
   assert.equal(denied.status,409); assert.equal(denied.value.state,'external');
  }
  const vendor=await json(page,endpoint+'/supplier-erp-identity?legalEntityId='+ctx.legalEntityId);
  assert.equal(vendor.status,200); assert.equal(vendor.value.isSupplier,projected);
  if(projected) {
   assert.equal(vendor.value.vendor.vendorId,'D95-PRIVATE-B');
   assert.equal(vendor.value.vendor.vendorName,'Company B vendor hint');
  } else assert.equal(vendor.value.vendor,null);
  const shared=await json(page,endpoint+'?legalEntityId='+ctx.legalEntityId);
  assert.equal(shared.status,200);
  assert.equal(JSON.stringify(shared).includes('D95-PRIVATE-B'),false);
  assert.equal(JSON.stringify(state).includes('D95-PRIVATE-B'),false);
  const selectors=await json(page,'/api/v1/counterparties?legalEntityId='+ctx.legalEntityId+'&search=Synthetic');
  assert.equal(selectors.status,200); assert.equal(JSON.stringify(selectors).includes('D95-PRIVATE-B'),false);
  await page.screenshot({path:'/run/control/d95-'+process.env.D95_PHASE+'.png'});
  fs.writeFileSync('/run/control/d95-'+process.env.D95_PHASE+'.json',JSON.stringify({state:state.value,vendor:vendor.value}));
  console.log('PASS D95 real OIDC/TLS/API/Italian DOM '+process.env.D95_PHASE+': supplier='+projected+' disabled; ordinary common/role edits409; private company vendor absent from shared reads; skipped=0');
 } finally {await browser.close();}
})().catch(e=>{console.error(e.name+': '+e.message);process.exitCode=1;});
