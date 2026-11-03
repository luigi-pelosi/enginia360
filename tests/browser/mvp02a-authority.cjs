const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync('/run/fixture.json','utf8'));
const origin='https://app.r00.test:8443';
const path='/api/v1/platform/administration-eligibility';
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
  assert.equal((await request(anonymous)).status,401,'anonymous platform route must deny authentication, not be absent');
  assert.equal((await request(anonymous,path,{headers:{'X-Correlation-ID':fixture.authorityIdentity,'X-Role':'SUPER ADMIN'}})).status,401);
  const token=Buffer.from(JSON.stringify({alg:'none'})).toString('base64url')+'.'+Buffer.from(JSON.stringify({sub:fixture.authorityIdentity,role:'SUPER ADMIN'})).toString('base64url')+'.';
  assert.equal((await request(anonymous,path,{headers:{Authorization:'Bearer '+token}})).status,401);
  console.log('PASS MVP02A anonymous forged-role/correlation/unsigned bearer denied');
  const ordinary=await login(browser,0);const owner=await login(browser,4);
  assert.equal((await request(owner.page)).status,403,'binding without membership is not authority by default');
  assert.equal((await request(ordinary.page)).status,403,'signed external role is not authority');
  await control('grant');
  for(let i=0;i<12;i++){
   const [yes,no]=await Promise.all([request(owner.page),request(ordinary.page)]);
   assert.deepEqual(yes,{status:200,value:{canAdministerPlatform:true},cache:'no-store'});
   assert.equal(no.status,403);assert.equal(no.cache,'no-store');
  }
  assert.deepEqual((await request(owner.page,'/api/v1/organization/contexts')).value,[],'global authority grants no ordinary membership');
  console.log('PASS MVP02A membership-free owner and alternating identities current SQL RLS');
  const csrf=(await request(owner.page,'/auth/csrf')).value.requestToken;
  assert.equal((await request(owner.page,path,{method:'POST'})).status,400,'new path protected by existing CSRF');
  assert.equal((await request(owner.page,path,{method:'POST',headers:{'X-CSRF-TOKEN':csrf}})).status,405,'no web authority command');
  await control('store-deny');assert.equal((await request(owner.page)).status,503,'authority store fail closed');await control('store-restore');
  assert.equal((await request(owner.page)).status,200);
  await control('revoke');assert.equal((await request(owner.page)).status,403,'active session authority revocation');
  assert.equal((await request(owner.page,'/auth/session')).value.authenticated,true,'session remains authenticated after authority revoke');
  console.log('PASS MVP02A existing CSRF no-store no web grant store failure and active-session revoke');
  await control('grant');assert.equal((await request(owner.page)).status,200);
  await control('binding-loss');assert.equal((await request(owner.page)).status,401);
  await control('revoke');await control('readback');
  console.log('PASS MVP02A revoke after binding loss CLI exact immutable readback');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
