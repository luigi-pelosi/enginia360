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
}
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const anonymous=await browser.newPage();
  for(let i=0;i<60;i++){
   try{await anonymous.goto(origin+'/auth/session');break;}catch(e){if(i===59)throw e;await new Promise(r=>setTimeout(r,500));}
  }
  assert.equal((await request(anonymous)).status,401,'organization directory must deny anonymous, not be absent');
  const ordinary=await login(browser,0),owner=await login(browser,4);
  assert.equal((await request(owner.page)).status,403,'binding alone is not authority');
  assert.equal((await request(ordinary.page)).status,403,'ordinary note permission cannot administer');
  await control('grant');
  const directory=await request(owner.page);
  assert.equal(directory.status,200);assert.equal(directory.cache,'no-store');
  assert.equal(directory.value.state,'ok');
  assert.ok(directory.value.tenants.length>=3);
  assert.deepEqual((await request(owner.page,'/api/v1/organization/contexts')).value,[]);
  const csrf=(await request(owner.page,'/auth/csrf')).value.requestToken;
  const payload=(kind='tenant',tenantId=null,parentId=null)=>({commandId:require('node:crypto').randomUUID(),operation:'create',kind,tenantId,resourceId:null,parentId,name:'Synthetic '+kind,expectedRevision:0});
  const post=(url,p,token=csrf)=>request(owner.page,url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':token},body:JSON.stringify(p)});
  const create=payload();
  assert.equal((await post(path,create,'')).status,400,'CSRF required');
  const first=await post(path,create);assert.equal(first.status,200,'persistent organization command HTTP missing');
  assert.equal(first.cache,'no-store');assert.equal(first.value.state,'applied');
  const tenant=first.value.snapshot.resourceId;
  assert.equal((await request(owner.page,path+'/'+tenant)).value.companies.length,0);
  let parent=tenant;const resources=[first.value.snapshot];
  for(const kind of ['company','site','warehouse']){
   const result=await post(path+'/'+tenant+'/commands',payload(kind,tenant,parent));
   assert.equal(result.status,200);assert.equal(result.value.state,'applied');
   assert.equal(result.value.snapshot.parentId,parent);parent=result.value.snapshot.resourceId;resources.push(result.value.snapshot);
  }
  for(const snap of resources){
   const rename={...payload(snap.kind,tenant,snap.parentId),operation:'rename',resourceId:snap.resourceId,name:'Renamed '+snap.kind,expectedRevision:1};
   const result=await post(path+'/'+tenant+'/commands',rename);assert.equal(result.status,200);assert.equal(result.value.snapshot.revision,2);
   assert.deepEqual((await post(path+'/'+tenant+'/commands',rename)).value,{state:'replayed',snapshot:result.value.snapshot});
   assert.equal((await post(path+'/'+tenant+'/commands',{...rename,commandId:require('node:crypto').randomUUID()})).status,409);
  }
  assert.deepEqual((await post(path,create)).value,{state:'replayed',snapshot:first.value.snapshot},'create replay is historical after rename');
  assert.equal((await request(owner.page,path+'/'+tenant)).value.tenant.name,'Renamed tenant');
  assert.equal((await post(path,{...payload(),name:'x\u0000y'})).status,400,'JSON NUL is invalid input, not a store outage');
  assert.equal((await post(path,{...payload(),name:'\ud800'})).status,400,'unpaired Unicode surrogate is invalid input');
  console.log('PASS MVP02B real HTTP all create/rename persisted incomplete hierarchy optimistic revision exact replay CSRF');
  const commandRoute=path+'/'+tenant+'/commands';
  const concurrent=payload();
  const creates=await Promise.all(Array.from({length:4},()=>post(path,concurrent)));
  assert.deepEqual(creates.map(x=>x.value.state).sort(),['applied','replayed','replayed','replayed']);
  for(const response of creates)assert.deepEqual(response.value.snapshot,creates[0].value.snapshot);
  const update={...payload('tenant',tenant),operation:'rename',resourceId:tenant,name:'Concurrent A',expectedRevision:2};
  const updates=await Promise.all([post(commandRoute,update),post(commandRoute,{...update,commandId:require('node:crypto').randomUUID(),name:'Concurrent B'})]);
  assert.deepEqual(updates.map(x=>x.status).sort(),[200,409]);
  assert.equal((await request(owner.page,path+'/'+tenant)).value.tenant.revision,3);
  const ordinaryCsrf=(await request(ordinary.page,'/auth/csrf')).value.requestToken;
  const denied=await request(ordinary.page,commandRoute,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':ordinaryCsrf,'X-Role':'SUPER ADMIN','X-Tenant-ID':tenant},body:JSON.stringify(update)});
  assert.equal(denied.status,403);assert.deepEqual(denied.value,{state:'forbidden'});
  for(let i=0;i<12;i++){
   const [yes,no]=await Promise.all([request(owner.page,path+'/'+tenant),request(ordinary.page,path+'/'+tenant)]);
   assert.equal(yes.status,200);assert.equal(no.status,403);assert.deepEqual(no.value,{state:'forbidden'});
  }
  const foreign=directory.value.tenants[0].id;
  assert.equal((await post(commandRoute,payload('company',foreign,foreign))).status,404,'body target cannot override verified route');
  assert.equal((await post(commandRoute,payload('site',tenant,foreign))).status,404,'foreign parent cannot enter target hierarchy');
  for(const bad of [{...payload(),name:''},{...payload(),name:' '.repeat(10)},{...payload(),name:'x'.repeat(101)},{...payload(),resourceId:tenant},{...payload(),expectedRevision:2147483647},{...payload(),extra:true}])assert.equal((await post(path,bad)).status,400);
  for(const body of ['{','null',JSON.stringify(create).replace('{','{"operation":"rename",'),' '.repeat(16385)+'{}']){
   assert.equal((await request(owner.page,path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':csrf},body})).status,400);
  }
  await control('store-deny');
  assert.equal((await request(owner.page)).status,503);assert.equal((await post(path,create)).status,503);
  await control('store-restore');assert.equal((await request(owner.page)).status,200);
  await control('revoke');
  assert.equal((await request(owner.page,path+'/'+tenant)).status,403);assert.equal((await post(path,create)).status,403,'replay rechecks current authority');
  assert.equal((await request(owner.page,'/auth/session')).value.authenticated,true);
  await control('grant');assert.equal((await post(path,create)).value.state,'replayed');
  await control('binding-loss');assert.equal((await request(owner.page)).status,401);
  await control('revoke');await control('readback');await control('audit-readback');
  console.log('PASS MVP02B HTTP pool concurrency/create/replay/stale update; wrong target/parent; closed inputs; note-only denial; no target leak; store failure; revoke and binding-loss');
  console.log('PASS MVP02B real TLS OIDC directory metadata authority and no ordinary grants');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
