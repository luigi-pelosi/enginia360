const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json', 'utf8'));
const origin = 'https://app.r00.test:8443';
const base = '/api/v1/workshop';
const checks = [];
function pass(name) { checks.push(name); console.log('PASS R03B ' + name); }
async function json(page, path, options = {}) {
  return page.evaluate(async ({ path, options }) => { const r = await fetch(path, options); return { status: r.status, value: await r.json().catch(() => null) }; }, { path, options });
}
async function csrf(page) { return (await json(page, '/auth/csrf')).value.requestToken; }
async function post(page, path, body, token) {
  const t = token === undefined ? await csrf(page) : token;
  return json(page, path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(t ? { 'X-CSRF-TOKEN': t } : {}) }, body: JSON.stringify(body) });
}
async function control(action) {
  fs.writeFileSync('/run/control/request.tmp', action); fs.renameSync('/run/control/request.tmp','/run/control/request');
  for (let i = 0; i < 300; i++) {
    if (fs.existsSync('/run/control/ack')) { assert.equal(fs.readFileSync('/run/control/ack', 'utf8'), action); fs.unlinkSync('/run/control/ack'); return; }
    await new Promise(r => setTimeout(r, 100));
  }
  assert.fail('ephemeral controller did not acknowledge ' + action);
}
async function login(browser, index) {
  const context = await browser.newContext(); const page = await context.newPage();
  await page.goto(origin + '/'); await page.getByRole('button', { name: 'Accedi', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Accedi', exact: true }).click();
  await page.locator('#username').fill(fixture.users[index].username); await page.locator('#password').fill(fixture.users[index].password);
  await Promise.all([page.waitForURL(u => u.hostname === 'app.r00.test'), page.locator('#kc-login').click()]);
  return { context, page };
}
// Independent exact decimal oracle (BigInt micro units): D67 net per line HALF_UP6, tax on the fiscal aggregate HALF_UP6.
const micro = s => { const [i, f = ''] = s.split('.'); return BigInt(i) * 1000000n + BigInt((f + '000000').slice(0, 6)); };
const hund = s => { const [i, f = ''] = s.split('.'); return BigInt(i) * 100n + BigInt((f + '00').slice(0, 2)); };
const half = (n, d) => (2n * n + d) / (2n * d);
const net = l => half(micro(l.q) * micro(l.p) * (10000n - hund(l.d)), 10000000000n);
const fmt = m => (m / 1000000n).toString() + '.' + (m % 1000000n).toString().padStart(6, '0');
function oracle(lines) { const b = lines.reduce((a, l) => a + net(l), 0n); const t = half(b * 22n, 100n); return { net: fmt(b), tax: fmt(t), total: fmt(b + t) }; }
const uid = () => crypto.randomUUID();
const ctx = fixture.contexts[0], data = fixture.workshop[0];
const policyVersion = 9, structureVersion = 1;
function envelope(type, revision, extra = {}) {
  return { type, commandId: uid(), expectedRevision: revision, expectedLinePolicyVersion: policyVersion, expectedStructurePolicyVersion: structureVersion,
    groupId: null, lineId: null, title: null, description: null, catalogItemId: null, catalogVersion: null, quantity: null, unitPrice: null, discountPercent: null, ...extra };
}
const cmd = (page, orderId, body) => post(page, `${base}/orders/${orderId}/editor/commands`, body);
const editor = (page, orderId) => json(page, `${base}/orders/${orderId}/editor`);
async function createOrder(page, documentTypeId = data.documentTypeId, configurationVersion = 7) {
  const id = uid();
  const r = await post(page, `${base}/orders`, { id, legalEntityId: ctx.legalEntityId, siteId: ctx.siteId, documentTypeId, configurationVersion, payerId: data.payerId, vehicleId: data.vehicleId });
  assert(r.status === 201, 'order creation ' + r.status); return id;
}
(async () => {
 const browser=await chromium.launch({headless:true});
 try {
  const probe=await browser.newPage(); let ready=false;
  for(let i=0;i<40;i++){try{if((await probe.goto(origin+'/auth/session')).status()===200){ready=true;break;}}catch{} await new Promise(r=>setTimeout(r,500));} assert(ready);
  const {page}=await login(browser,0);
  const order=await createOrder(page), group=uid(), entry=uid();
  assert.equal((await cmd(page,order,envelope('AddGroup',0,{groupId:group,title:'Tempo effettivo'}))).status,201);
  assert.notEqual(group,order);
  const path=`${base}/orders/${order}/actual-time/own`;
  const body={commandId:uid(),entryId:entry,workingGroupId:group,expectedOwnRevision:0,expectedGroupVersion:1,workDate:'2024-02-29',durationSeconds:3671,note:'Fatto mio <testo>'};
  const saved=await post(page,path,body);
  assert.equal(saved.status,201,'own operator must persist real group/date/duration/note: '+JSON.stringify(saved));
  assert.equal(saved.value.appliedOwnRevision,1);
  await page.reload();
  const read=await json(page,path);
  assert.equal(read.status,200);
  assert.equal(read.value.ownRevision,1);
  assert.equal(read.value.entries.length,1);
  assert.deepEqual([read.value.entries[0].entryId,read.value.entries[0].workingGroupId,read.value.entries[0].workDate,read.value.entries[0].durationSeconds,read.value.entries[0].note],[entry,group,body.workDate,3671,body.note]);
  assert.equal((await editor(page,order)).value.revision,1,'time never advances commercial revision');
  pass('persisted verified own operator / independent revision / refresh');
  await page.goto(origin+'/ui01-runtime.html#order='+order);
  await page.getByText('Valori salvati riletti — revisione 1',{exact:true}).waitFor();
  const panel=page.getByText('Tempo effettivo mio',{exact:true});
  assert.equal(await panel.count(),1,'own-time panel must be reachable in the actual runtime workspace');
  await panel.click();
  const own=page.getByRole('region',{name:'Consuntivo personale'});
  await own.getByText(body.note,{exact:true}).waitFor();
  await own.getByLabel('Lavorazione tempo').selectOption(group);
  await own.getByLabel('Data lavoro').fill('2025-01-02');
  await own.getByLabel('Durata effettiva (secondi)').fill('125');
  await own.getByLabel('Nota tempo').fill('Registrato dalla UI reale');
  await own.getByRole('button',{name:'Registra tempo',exact:true}).click();
  await own.getByText('Registrato dalla UI reale',{exact:true}).waitFor();
  await page.reload(); await page.getByText('Tempo effettivo mio',{exact:true}).click();
  await page.getByRole('region',{name:'Consuntivo personale'}).getByText('Registrato dalla UI reale',{exact:true}).waitFor();
  pass('actual UI record, authoritative reread and browser refresh');
  const correction={commandId:uid(),expectedOwnRevision:2,expectedEntryVersion:1,workDate:'2023-12-31',durationSeconds:4321,note:'Corretto',correctionNote:'Verifica durata'};
  const corrected=await post(page,path+'/'+entry+'/corrections',correction);
  const history=await json(page,path+'/'+entry+'/history');
  assert.deepEqual([corrected.status,history.status],[200,200],'own correction and immutable old/new history must be available');
  assert.equal(corrected.value.entryVersion,2);
  assert.equal(history.value.versions.length,2);
  assert.deepEqual(history.value.versions.map(v=>[v.version,v.workDate,v.durationSeconds,v.note]),[[1,body.workDate,3671,body.note],[2,correction.workDate,4321,correction.note]]);
  assert.equal(history.value.versions[1].correctionNote,correction.correctionNote);
  assert.equal(history.value.versions[0].internalIdentityId,history.value.versions[1].internalIdentityId);
  assert.equal(history.value.versions[1].commandId,correction.commandId);
  assert(history.value.versions.every(v=>v.recordedAt));
  pass('own correction preserves old/new actor/server time/command history');
  const originalReplay=await post(page,path,body),correctReplay=await post(page,path+'/'+entry+'/corrections',correction);
  assert.deepEqual([originalReplay.status,correctReplay.status],[200,200],'old exact receipts survive later versions');
  assert.deepEqual(originalReplay.value,saved.value);assert.deepEqual(correctReplay.value,corrected.value);
  assert.equal((await post(page,path,{...body,note:'collision'})).status,409);
  assert.equal((await post(page,path+'/'+entry+'/corrections',{...correction,note:'collision'})).status,409);
  assert.equal((await json(page,path)).value.ownRevision,3);
  assert.equal((await json(page,path+'/'+entry+'/history')).value.versions.length,2);
  pass('immutable exact receipts / canonical command collision / no duplicate versions');
  const b=await login(browser,5),foreign=await login(browser,1);
  assert.deepEqual((await json(b.page,path)).value.entries,[],'same tenant fully own-authorized B sees no A entries');
  assert.equal((await json(b.page,path+'/'+entry+'/history')).status,404);
  assert.equal((await post(b.page,path+'/'+entry+'/corrections',correction)).status,404);
  assert.equal((await post(b.page,path,body)).status,409);
  assert.equal((await json(foreign.page,path)).status,404);
  assert.equal((await json(foreign.page,path+'/'+entry+'/history')).status,404);
  pass('same-tenant own membership and foreign-tenant historical isolation');
  await control('permissions:B:workshop.actual-time.read-own,workshop.actual-time.write-own,workshop.groups.write');
  const removed=await cmd(b.page,order,envelope('RemoveEmptyGroup',1,{groupId:group}));
  assert.equal(removed.status,409,'group with ONLY another operator time cannot be removed');
  assert.equal(removed.value.code,'group_not_empty');
  assert.equal(JSON.stringify(removed).includes(entry),false);
  pass('minimal group reference prevents other-operator empty-group removal');
  for(const bad of [{tenantId:ctx.tenantId},{membershipId:fixture.adminMembershipId},{internalIdentityId:uid()},{operatorId:uid()},{durationSeconds:0},{durationSeconds:-1},{durationSeconds:1.5},{durationSeconds:'1'},{durationSeconds:2147483648},{workDate:'2023-02-29'},{workDate:'2024-2-29'},{note:'x'.repeat(501)},{note:'x'+String.fromCharCode(10)},{entryId:'00000000-0000-0000-0000-000000000000'}]){
    assert.equal((await post(page,path,{...body,commandId:uid(),entryId:uid(),expectedOwnRevision:3,...bad})).status,400,JSON.stringify(bad));
  }
  assert.equal((await post(page,path,{...body,entryId:uid(),commandId:uid(),expectedOwnRevision:3},null)).status,400,'CSRF required');
  for(const permissions of ['workshop.orders.create','workshop.lines.edit','workshop.groups.write','workshop.actual-time.read-own','']){
    await control('permissions:B:'+permissions);
    assert.equal((await post(b.page,path,{...body,entryId:uid(),commandId:uid()})).status,403,'exact own-write not inferred '+permissions);
    assert.equal((await json(b.page,path)).status,permissions==='workshop.actual-time.read-own'?200:403,'exact own-read '+permissions);
  }
  await control('permissions:B:workshop.actual-time.read-own,workshop.actual-time.write-own');
  assert.equal((await json(page,path)).value.ownRevision,3);
  pass('strict payload, CSRF and individually isolated operative grants');
  await control('workshop-capability:false');
  assert.equal((await json(page,path)).status,200,'capability off retains own historical reads');
  assert.equal((await json(page,path+'/'+entry+'/history')).status,200);
  assert.equal((await post(page,path,{...body,commandId:uid(),entryId:uid(),expectedOwnRevision:3})).status,403,'capability off blocks new writes');
  const disabledReplay=await post(page,path,body);
  assert.equal(disabledReplay.status,200,'capability off must not block authorized exact historical receipt replay');
  assert.deepEqual(disabledReplay.value,saved.value);
  await control('workshop-capability:true');
  pass('disabled capability historical reads and exact replay / new writes denied');
  await page.getByRole('region',{name:'Consuntivo personale'}).getByRole('button',{name:'Rileggi tempi miei'}).click();
  const current=page.getByRole('region',{name:'Consuntivo personale'}).getByRole('listitem').filter({has:page.getByText('Corretto',{exact:true})});
  await current.waitFor();
  assert.equal(await current.getByRole('button',{name:'Storico mio'}).count(),1,'own UI must expose bounded saved history');
  await current.getByRole('button',{name:'Storico mio'}).click();
  await page.getByRole('region',{name:'Storico tempo mio'}).getByText(body.note,{exact:true}).waitFor();
  await current.getByRole('button',{name:'Correggi tempo mio'}).click();
  await page.getByRole('region',{name:'Consuntivo personale'}).getByLabel('Durata effettiva (secondi)').fill('5432');
  await page.getByLabel('Motivo correzione').fill('Correzione dalla UI');
  await page.getByRole('button',{name:'Salva correzione tempo'}).click();
  await page.getByRole('region',{name:'Consuntivo personale'}).getByText('5432 secondi',{exact:false}).waitFor();
  assert.equal((await json(page,path+'/'+entry+'/history')).value.versions.length,3);
  pass('actual correction UI / bounded history / authoritative current');
  const lostBodies=[];
  let lossDone;const loss=new Promise(resolve=>lossDone=resolve);
  await page.route('**/actual-time/own',async route=>{if(route.request().method()==='POST'){lostBodies.push([route.request().url(),route.request().postData()]);await route.fetch();await route.abort('failed');lossDone();}else await route.continue();});
  const timePanel=page.getByRole('region',{name:'Consuntivo personale'});
  await timePanel.getByLabel('Lavorazione tempo').selectOption(group);
  await timePanel.getByLabel('Data lavoro').fill('2026-01-01');
  await timePanel.getByLabel('Durata effettiva (secondi)').fill('77');
  await timePanel.getByLabel('Nota tempo').fill('Risposta persa UI');
  await timePanel.getByRole('button',{name:'Registra tempo',exact:true}).click();
  await loss;
  await timePanel.getByRole('status').filter({hasText:/incerto|fetch|disponibile/}).waitFor();
  assert.equal(await timePanel.getByRole('button',{name:'Riprova tempo identico'}).count(),1,'accepted response loss must freeze exact command and expose explicit identical retry');
  await page.unroute('**/actual-time/own');
  await page.route('**/actual-time/own',async route=>{if(route.request().method()==='POST')lostBodies.push([route.request().url(),route.request().postData()]);await route.continue();});
  await timePanel.getByRole('button',{name:'Riprova tempo identico'}).click();
  await timePanel.getByText('Risposta persa UI',{exact:true}).waitFor();
  assert.equal(lostBodies.length,2);assert.deepEqual(lostBodies[0],lostBodies[1]);
  const lostCommand=JSON.parse(lostBodies[0][1]).commandId;
  assert.equal((await json(page,path)).value.ownRevision,5);
  await page.unroute('**/actual-time/own');
  pass('real accepted-response loss / byte-identical URL UUID payload retry / single persisted receipt');
  const collisionOrder=await createOrder(page),collisionGroup=uid(),collisionEntry=uid();
  assert.equal((await cmd(page,collisionOrder,envelope('AddGroup',0,{groupId:collisionGroup,title:'Rollback riferimento'}))).status,201);
  const hiddenCollision=await post(b.page,`${base}/orders/${collisionOrder}/actual-time/own`,{...body,entryId:collisionEntry,workingGroupId:collisionGroup});
  assert.equal(hiddenCollision.status,409,'RLS-hidden command collision is a controlled conflict with atomic first-reference rollback');
  assert.deepEqual((await json(b.page,`${base}/orders/${collisionOrder}/actual-time/own`)).value.entries,[]);
  pass('hidden command collision controlled / first group-reference atomic rollback');
  const token=await csrf(page);
  async function serialized(orderId,first,second){
    if(fixture.poolSize>=4)await control('hold-order:'+orderId);
    const one=first();if(fixture.poolSize>=4)await control('wait-order:1');else await one;
    const two=second();if(fixture.poolSize>=4){await control('wait-order:2');await control('release-order');}
    return Promise.all([one,two]);
  }
  const correctionRace={commandId:uid(),expectedOwnRevision:5,expectedEntryVersion:3,workDate:'2023-12-31',durationSeconds:6000,note:'Corretto',correctionNote:'Concorrenza'};
  const [winning,stale]=await serialized(order,()=>post(page,path+'/'+entry+'/corrections',correctionRace,token),()=>post(page,path+'/'+entry+'/corrections',{...correctionRace,commandId:uid(),durationSeconds:6001},token));
  assert.equal(winning.status,200);assert.equal(stale.status,409);assert.equal(stale.value.code,'actual_time_revision_changed');
  for(const phase of ['delete','closure','rename'])for(const timeFirst of [true,false]){
    const race=await createOrder(page),rg=uid();assert.equal((await cmd(page,race,envelope('AddGroup',0,{groupId:rg,title:'Serializzazione '+phase}))).status,201);
    const rp=`${base}/orders/${race}/actual-time/own`,timeBody={...body,commandId:uid(),entryId:uid(),workingGroupId:rg};
    const time=()=>post(page,rp,timeBody,token);
    const other=()=>phase==='closure'?post(page,`${base}/orders/${race}/technical-closure`,{id:uid(),expectedRevision:1},token):post(page,`${base}/orders/${race}/editor/commands`,envelope(phase==='delete'?'RemoveEmptyGroup':'RenameGroup',1,{groupId:rg,...(phase==='rename'?{title:'Rinominata'}:{})}),token);
    const values=await serialized(race,timeFirst?time:other,timeFirst?other:time),tr=values[timeFirst?0:1],otherResult=values[timeFirst?1:0];
    assert.equal(otherResult.status,phase==='closure'?201:phase==='delete'&&timeFirst?409:200,JSON.stringify(values));
    assert.equal(tr.status,timeFirst?201:phase==='delete'?404:409,JSON.stringify(values));
    if(timeFirst){assert.equal((await json(page,rp)).value.entries[0].workingGroupId,rg);assert.equal((await post(page,rp,timeBody)).status,200);}
    if(phase==='closure'&&timeFirst){assert.equal((await json(page,rp+'/'+timeBody.entryId+'/history')).status,200);assert.equal((await post(page,rp+'/'+timeBody.entryId+'/corrections',{...correctionRace,commandId:uid(),expectedOwnRevision:1,expectedEntryVersion:1})).value.code,'order_technically_closed');}
  }
  const retry={...body,commandId:uid(),entryId:uid(),expectedOwnRevision:6};
  const retries=await serialized(order,()=>post(page,path,retry,token),()=>post(page,path,retry,token));assert.deepEqual(retries.map(r=>r.status),[201,200]);assert.deepEqual(retries[0].value,retries[1].value);
  pass(fixture.poolSize>=4?'pool4 separate SQL-connection barriers: corrections, identical retries, time vs closure/delete/rename BOTH orders':'pool1 completion: corrections/retry/time vs closure/delete/rename both orders');
  const service=uid(),service2=uid();
  for(const [lineId,q,p] of [[service,'1.123456','42.123456'],[service2,'0.000001','1.000001']]){
    const rev=(await editor(page,order)).value.revision;
    assert.equal((await cmd(page,order,envelope('AddCommercialLine',rev,{lineId,groupId:group,catalogItemId:data.serviceId,catalogVersion:8,quantity:q,unitPrice:p,discountPercent:'5'}))).status,201);
  }
  assert.equal((await cmd(page,order,envelope('AddNote',3,{lineId:uid(),groupId:group,description:'Note esclusa dalla fonte'}))).status,201);
  const before=(await editor(page,order)).value.summary;
  await control('effects-before');
  const bounded={...body,commandId:uid(),entryId:uid(),expectedOwnRevision:7,workDate:'0001-01-01',durationSeconds:2147483647,note:''};
  assert.equal((await post(page,path,bounded)).status,201,'Int32 technical bound is not a business day limit');
  assert.equal((await post(page,path+'/'+bounded.entryId+'/corrections',{commandId:uid(),expectedOwnRevision:8,expectedEntryVersion:1,workDate:'9999-12-31',durationSeconds:86401,note:'',correctionNote:''})).status,200);
  await control('effects-after');
  assert.deepEqual((await editor(page,order)).value.summary,before);
  const expected=oracle([{q:'1.123456',p:'42.123456',d:'5'},{q:'0.000001',p:'1.000001',d:'5'}]);
  assert.deepEqual([before.netAmount,before.taxAmount,before.total],[expected.net,expected.tax,expected.total]);assert.equal(before.lines.length,2);
  assert.equal((await post(page,`${base}/orders/${order}/technical-closure`,{id:uid(),expectedRevision:4})).status,201);
  const invoiceId=uid(),invoiceBody={id:invoiceId,orderId:order,documentTypeId:data.invoiceTypeId,configurationVersion:6,documentDate:'2026-10-24',currency:'EUR',reference:'SYNTHETIC-R03B'};
  const invoice=await post(page,'/api/v1/billing/workshop-invoices',invoiceBody);assert.equal(invoice.status,201,JSON.stringify(invoice));assert.equal(invoice.value.sourceRevision,4);assert.deepEqual(invoice.value.summary,before);
  assert.deepEqual((await post(page,'/api/v1/billing/workshop-invoices',invoiceBody)).value,invoice.value);
  const confirmation={id:uid(),configurationVersion:6};const confirmed=await post(page,`/api/v1/billing/workshop-invoices/${invoiceId}/confirmation`,confirmation);assert.equal(confirmed.status,201);assert.deepEqual((await post(page,`/api/v1/billing/workshop-invoices/${invoiceId}/confirmation`,confirmation)).value,confirmed.value);
  const journalId=uid(),journalBody={id:journalId,invoiceId,chartVersion:5};const journal=await post(page,'/api/v1/accounting/invoice-journal-entries',journalBody);assert.equal(journal.status,201);assert.equal(journal.value.balanced,true);assert.equal(journal.value.totalDebit,expected.total);assert.equal(journal.value.totalCredit,expected.total);assert.deepEqual((await post(page,'/api/v1/accounting/invoice-journal-entries',journalBody)).value,journal.value);
  assert.deepEqual((await post(page,path,body)).value,saved.value,'exact replay survives technical closure');
  const fc=fixture.contexts[1],fd=fixture.workshop[1],fo=uid(),fg=uid(),fl=uid();
  assert.equal((await post(foreign.page,`${base}/orders`,{id:fo,legalEntityId:fc.legalEntityId,siteId:fc.siteId,documentTypeId:fd.documentTypeId,configurationVersion:7,payerId:fd.payerId,vehicleId:fd.vehicleId})).status,201);
  assert.equal((await cmd(foreign.page,fo,envelope('AddGroup',0,{groupId:fg,title:'Tempi esterni locali'}))).status,201);
  assert.equal((await cmd(foreign.page,fo,envelope('AddCommercialLine',1,{lineId:fl,groupId:fg,catalogItemId:fd.serviceId,catalogVersion:8,quantity:'1.123456',unitPrice:'42.123456',discountPercent:'5'}))).status,201);
  assert.equal((await cmd(foreign.page,fo,envelope('AddNote',2,{lineId:uid(),groupId:fg,description:'Non amministrativa'}))).status,201);
  const fp=`${base}/orders/${fo}/actual-time/own`,ft={...body,commandId:uid(),entryId:uid(),workingGroupId:fg};
  assert.equal((await post(foreign.page,fp,ft)).status,201);assert.equal((await post(foreign.page,fp+'/'+ft.entryId+'/corrections',{...correction,commandId:uid(),expectedOwnRevision:1})).status,200);
  const externalSummary=(await editor(foreign.page,fo)).value.summary;
  assert.equal(externalSummary.lines.length,1);assert.equal(externalSummary.revision,3);
  assert.equal((await post(foreign.page,`${base}/orders/${fo}/technical-closure`,{id:uid(),expectedRevision:3})).status,201);
  const externalId=uid(),externalBody={id:externalId,expectedRevision:3};assert.equal((await post(foreign.page,`${base}/orders/${fo}/administrative-requests`,externalBody)).status,201);assert.equal((await post(foreign.page,`${base}/orders/${fo}/administrative-requests`,externalBody)).status,200);
  pass('actual times/corrections -> technical closure/internal Billing confirmation/Accounting balanced idempotent q6; external pinned summary excludes Note+time; SQL no stock/quantity/outbox/billed effects');
  fs.writeFileSync('/run/control/result.json',JSON.stringify({checks,entry,order,lostCommand,collisionGroup,collisionEntry,invoiceId,journalId,snapshot:before,externalId,externalSummary,duration:6000,commercialRevision:4}));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
