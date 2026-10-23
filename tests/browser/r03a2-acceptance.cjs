const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json', 'utf8'));
const origin = 'https://app.r00.test:8443';
const base = '/api/v1/workshop';
const checks = [];
function pass(name) { checks.push(name); console.log('PASS R03A ' + name); }
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
 const browser = await chromium.launch({headless:true});
 try {
  const probe=await browser.newPage(); let ready=false;
  for(let i=0;i<40;i++){try{if((await probe.goto(origin+'/auth/session')).status()===200){ready=true;break;}}catch{} await new Promise(r=>setTimeout(r,500));} assert(ready);
  const {page}=await login(browser,0);
  const order=await createOrder(page), g=uid(), line=uid();
  assert.equal((await cmd(page,order,envelope('AddGroup',0,{groupId:g,title:'Correction'}))).status,201);
  assert.equal((await cmd(page,order,envelope('AddCommercialLine',1,{lineId:line,groupId:g,catalogItemId:data.partId,catalogVersion:8,quantity:'4',unitPrice:'12.345678',discountPercent:'5'}))).status,201);
  const edit=envelope('EditCommercialLine',2,{lineId:line,quantity:'5'});
  const changed=await cmd(page,order,edit);
  assert.equal(changed.status,200,'P2 uncommitted Part quantity correction must succeed: '+JSON.stringify(changed));
  assert.equal((await editor(page,order)).value.rows[0].line.quantity,'5');
  pass('P2 quantity correction without active commitments');
  const g2=uid();
  assert.equal((await cmd(page,order,envelope('AddGroup',3,{groupId:g2,title:'Destination'}))).status,201);
  const reassigned=await cmd(page,order,envelope('EditCommercialLine',4,{lineId:line,groupId:g2,catalogItemId:data.alternatePartId,catalogVersion:11}));
  assert.equal(reassigned.status,200,'P2 explicit catalog/group structural correction must succeed: '+JSON.stringify(reassigned));
  const moved=(await editor(page,order)).value.rows[0];
  assert.deepEqual([moved.workingGroupId,moved.line.catalogItemId,moved.line.catalogVersion,moved.line.catalogLabel],[g2,data.alternatePartId,11,'Synthetic alternate Part']);
  pass('P2 explicit catalog/version/group correction');
  const noStock=await post(page,`/api/v1/inventory/orders/${order}/lines/${line}/reservations`,{id:uid(),warehouseId:ctx.warehouseId,catalogVersion:11,quantity:'1'});assert.equal(noStock.status,409);assert.equal(noStock.value.code,'insufficient_available');
  const removed=await cmd(page,order,envelope('RemoveLine',5,{lineId:line}));
  assert.equal(removed.status,200,'P2 uncommitted Part removal must succeed: '+JSON.stringify(removed));
  assert.equal((await editor(page,order)).value.rows.length,0);
  pass('P2 uncommitted Part tombstone removal');
  const race=await createOrder(page), rg=uid(), rl=uid();
  assert.equal((await cmd(page,race,envelope('AddGroup',0,{groupId:rg,title:'Race'}))).status,201);
  assert.equal((await cmd(page,race,envelope('AddCommercialLine',1,{lineId:rl,groupId:rg,catalogItemId:data.partId,catalogVersion:8,quantity:'5',unitPrice:'1',discountPercent:'0'}))).status,201);
  const token=await csrf(page);
  // Freeze both authenticated requests before starting; no scheduler sleeps stand in for a barrier.
  const reserveBody={id:uid(),warehouseId:ctx.warehouseId,catalogVersion:8,quantity:'4'};
  const send=(path,body)=>post(page,path,body,token);
  if(fixture.poolSize>=4) await control('hold-line:'+ctx.tenantId+':'+rl);
  const editing=send(`${base}/orders/${race}/editor/commands`,envelope('EditCommercialLine',2,{lineId:rl,quantity:'2'}));
  if(fixture.poolSize>=4) await control('wait-line:1'); else await editing;
  const reserving=send(`/api/v1/inventory/orders/${race}/lines/${rl}/reservations`,reserveBody);
  if(fixture.poolSize>=4){await control('wait-line:2'); await control('release-line');}
  const [er,rr]=await Promise.all([editing,reserving]);
  assert.equal(er.status,200,JSON.stringify(er));
  assert.equal(rr.status,409,'edit wins: Reserve must re-read fresh quantity 2 under lock, not stale pretransaction 5: '+JSON.stringify(rr));
  assert.equal(rr.value.code,'exceeds_remaining');
  pass(fixture.poolSize>=4?'separate-connection barrier edit wins: Reserve fresh snapshot':'pool1 same-connection public-contract fresh snapshot');
  // Failed reservation has no durable commitment: the same line remains structurally editable.
  assert.equal((await cmd(page,race,envelope('EditCommercialLine',3,{lineId:rl,quantity:'3'}))).status,200);
  const activeEdit=envelope('EditCommercialLine',4,{lineId:rl,quantity:'4'}), reservation={...reserveBody,id:uid(),quantity:'2'};
  if(fixture.poolSize>=4) await control('hold-line:'+ctx.tenantId+':'+rl);
  const reserveFirst=send(`/api/v1/inventory/orders/${race}/lines/${rl}/reservations`,reservation);
  if(fixture.poolSize>=4) await control('wait-line:1'); else await reserveFirst;
  const editSecond=send(`${base}/orders/${race}/editor/commands`,activeEdit);
  if(fixture.poolSize>=4){await control('wait-line:2'); await control('release-line');}
  const [winner,denied]=await Promise.all([reserveFirst,editSecond]);
  assert.equal(winner.status,201,JSON.stringify(winner)); assert.equal(denied.status,409); assert.equal(denied.value.code,'active_material_commitments');
  assert.equal((await editor(page,race)).value.revision,4);
  for(const [fields,status,code] of [[{groupId:g},404,'group_not_found'],[{catalogItemId:data.serviceId,catalogVersion:8},400,null],[{catalogItemId:data.partId,catalogVersion:7},409,'catalog_version_changed'],[{catalogItemId:data.partId},400,null]]){
    const invalid=await cmd(page,race,envelope('EditCommercialLine',4,{lineId:rl,...fields}));assert.equal(invalid.status,status);if(code)assert.equal(invalid.value.code,code);
  }
  assert.equal((await cmd(page,race,envelope('EditCommercialLine',4,{lineId:rl,catalogItemId:data.alternatePartId,catalogVersion:11}))).value.code,'active_material_commitments');
  assert.equal((await cmd(page,race,envelope('RemoveLine',4,{lineId:rl}))).value.code,'active_material_commitments');
  pass((fixture.poolSize>=4?'separate-connection reserve wins':'pool1 active reservation')+' denies edit/removal; failed reserve leaves editable; invalid catalog/kind/group refused');
  let rev=4;
  async function apply(type,fields){const r=await cmd(page,race,envelope(type,rev,fields));assert([200,201].includes(r.status),JSON.stringify(r));rev=r.value.appliedRevision;return r;}
  const pickId=uid();
  assert.equal((await post(page,`/api/v1/inventory/orders/${race}/lines/${rl}/reservations/${reservation.id}/picks`,{id:pickId,quantity:'2'})).status,201);
  assert.equal((await cmd(page,race,envelope('EditCommercialLine',rev,{lineId:rl,quantity:'9'}))).value.code,'active_material_commitments');
  const installId=uid(), installPath=`${base}/orders/${race}/lines/${rl}/picks/${pickId}/installations`, installBody={id:installId,quantity:'2'};
  const installed=await post(page,installPath,installBody); assert.equal(installed.status,201,JSON.stringify(installed));
  assert.equal(installed.value.stockEffect,'Consumed'); assert.equal(installed.value.installation.workingGroupId,rg);assert.equal(installed.value.installation.quantity,'2');
  assert.deepEqual((await post(page,installPath,installBody)).value,installed.value);
  assert.equal((await cmd(page,race,envelope('EditCommercialLine',rev,{lineId:rl,quantity:'9'}))).value.code,'active_material_commitments');
  const blocked=await post(page,`${base}/orders/${race}/technical-closure`,{id:uid(),expectedRevision:rev}); assert.equal(blocked.value.code,'technical_requirements_pending');
  const carcassId=uid(), carcassBody={id:carcassId,warehouseId:ctx.warehouseId,quantity:'2',description:'Synthetic replaced component'};
  const returned=await post(page,`/api/v1/inventory/orders/${race}/lines/${rl}/carcass-returns`,carcassBody); assert.equal(returned.status,201,JSON.stringify(returned)); assert.equal(returned.value.workingGroupId,rg);
  assert.deepEqual((await post(page,`/api/v1/inventory/orders/${race}/lines/${rl}/carcass-returns`,carcassBody)).value,returned.value);
  assert.equal((await cmd(page,race,envelope('RemoveLine',rev,{lineId:rl}))).value.code,'active_material_commitments','carcass is not a new-part compensation');
  await apply('EditCommercialLine',{lineId:rl,unitPrice:'12.345678',discountPercent:'5',description:'Commercial edit with active consumption'});
  const secondGroup=uid(); await apply('AddGroup',{groupId:secondGroup,title:'Second working group'});
  const services=[uid(),uid()],part2=uid(),note=uid();
  for(const [id,kind,group,q,p] of [[services[0],'Service',rg,'1.5','40.123456'],[services[1],'Service',secondGroup,'2','35.5'],[part2,'Part',secondGroup,'1','9.999999']])await apply('AddCommercialLine',{lineId:id,groupId:group,catalogItemId:kind==='Part'?data.partId:data.serviceId,catalogVersion:8,quantity:q,unitPrice:p,discountPercent:'0'});
  await apply('AddNote',{lineId:note,groupId:secondGroup,description:'Excluded from fiscal sources'});
  await apply('EditCommercialLine',{lineId:services[0],quantity:'1.75'});
  assert.equal((await cmd(page,race,envelope('EditCommercialLine',rev,{lineId:rl,groupId:secondGroup}))).value.code,'active_material_commitments');
  const r2=uid(),pk2=uid(),in2=uid(),ca2=uid();
  assert.equal((await post(page,`/api/v1/inventory/orders/${race}/lines/${part2}/reservations`,{id:r2,warehouseId:ctx.warehouseId,catalogVersion:8,quantity:'1'})).status,201);
  const picked2=await post(page,`/api/v1/inventory/orders/${race}/lines/${part2}/reservations/${r2}/picks`,{id:pk2,quantity:'1'});assert.equal(picked2.status,201);assert.equal(picked2.value.workingGroupId,secondGroup);
  const installed2=await post(page,`${base}/orders/${race}/lines/${part2}/picks/${pk2}/installations`,{id:in2,quantity:'1'});assert.equal(installed2.status,201);assert.equal(installed2.value.installation.workingGroupId,secondGroup);assert.equal(installed2.value.stockEffect,'Consumed');
  const returned2=await post(page,`/api/v1/inventory/orders/${race}/lines/${part2}/carcass-returns`,{id:ca2,warehouseId:ctx.warehouseId,quantity:'1',description:'Second group carcass'});assert.equal(returned2.status,201);assert.equal(returned2.value.workingGroupId,secondGroup);
  assert.notEqual(secondGroup,race);assert.notEqual(secondGroup,rg);
  const snapshot=(await editor(page,race)).value.summary;
  const expected=oracle([{q:'3',p:'12.345678',d:'5'},{q:'1.75',p:'40.123456',d:'0'},{q:'2',p:'35.5',d:'0'},{q:'1',p:'9.999999',d:'0'}]);
  assert.deepEqual([snapshot.netAmount,snapshot.taxAmount,snapshot.total],[expected.net,expected.tax,expected.total]);assert.equal(snapshot.lines.length,4);assert.equal(snapshot.revision,rev);
  const closeBody={id:uid(),expectedRevision:rev}; assert.equal((await post(page,`${base}/orders/${race}/technical-closure`,closeBody)).status,201);
  assert.equal((await cmd(page,race,envelope('EditCommercialLine',rev,{lineId:rl,unitPrice:'1'}))).value.code,'order_technically_closed');
  const invoiceId=uid(),invoiceBody={id:invoiceId,orderId:race,documentTypeId:data.invoiceTypeId,configurationVersion:6,documentDate:'2026-10-23',currency:'EUR',reference:'SYNTHETIC-R03A2'};
  const invoice=await post(page,'/api/v1/billing/workshop-invoices',invoiceBody);assert.equal(invoice.status,201,JSON.stringify(invoice));assert.equal(invoice.value.sourceRevision,rev);assert.deepEqual(invoice.value.summary,snapshot);
  assert.deepEqual((await post(page,'/api/v1/billing/workshop-invoices',invoiceBody)).value,invoice.value);
  const confirmationBody={id:uid(),configurationVersion:6};const confirmed=await post(page,`/api/v1/billing/workshop-invoices/${invoiceId}/confirmation`,confirmationBody);assert.equal(confirmed.status,201,JSON.stringify(confirmed));assert.equal(confirmed.value.status,'Confirmed');
  assert.deepEqual((await post(page,`/api/v1/billing/workshop-invoices/${invoiceId}/confirmation`,confirmationBody)).value,confirmed.value);
  const journalId=uid(),journalBody={id:journalId,invoiceId,chartVersion:5};const journal=await post(page,'/api/v1/accounting/invoice-journal-entries',journalBody);assert.equal(journal.status,201,JSON.stringify(journal));
  assert.equal(journal.value.balanced,true);assert.equal(journal.value.totalDebit,expected.total);assert.equal(journal.value.totalCredit,expected.total);assert.equal(journal.value.difference,'0.000000');
  assert.deepEqual((await post(page,'/api/v1/accounting/invoice-journal-entries',journalBody)).value,journal.value);
  assert.equal((await json(page,`/api/v1/billing/workshop-invoices/${invoiceId}`)).value.journalEntryId,journalId);
  pass('actual pick/install/consumption/carcass non-order group then multi-Service/Part/Note edited source technical closure Billing confirmation Accounting balanced idempotent q6');
  const reader=await login(browser,5);const readCmd=envelope('EditCommercialLine',2,{lineId:uid(),quantity:'2'});
  assert.equal((await cmd(reader.page,order,readCmd)).status,403,'same tenant read without exact edit grant');
  await control('permissions:edit-only:workshop.lines.edit');
  assert.equal((await cmd(reader.page,order,edit)).status,200,'authorized replay after removal returns frozen receipt');
  await control('permissions:revoked:workshop.orders.read');assert.equal((await cmd(reader.page,order,edit)).status,403,'revocation denies identical retry');await reader.context.close();
  assert.equal((await post(page,`${base}/orders/${order}/editor/commands`,edit,'')).status,400,'CSRF');
  assert.equal((await cmd(page,order,{...edit,commandId:uid(),expectedRevision:1})).value.code,'revision_changed');
  const foreign=await login(browser,1),fc=fixture.contexts[1],fd=fixture.workshop[1],fo=uid(),fg=uid(),fl=uid();
  assert.equal((await cmd(foreign.page,order,edit)).status,404,'cross tenant target invisible');
  assert.equal((await post(foreign.page,`${base}/orders`,{id:fo,legalEntityId:fc.legalEntityId,siteId:fc.siteId,documentTypeId:fd.documentTypeId,configurationVersion:7,payerId:fd.payerId,vehicleId:fd.vehicleId})).status,201);
  assert.equal((await cmd(foreign.page,fo,envelope('AddGroup',0,{groupId:fg,title:'External group'}))).status,201);
  assert.equal((await cmd(foreign.page,fo,envelope('AddCommercialLine',1,{lineId:fl,groupId:fg,catalogItemId:fd.serviceId,catalogVersion:8,quantity:'1.123456',unitPrice:'42.123456',discountPercent:'5'}))).status,201);
  const collision=await cmd(foreign.page,fo,envelope('EditCommercialLine',2,{commandId:edit.commandId,lineId:fl,quantity:'2'}));assert.equal(collision.status,409,'RLS-hidden command collision must rollback projection/history/revision');assert.equal((await editor(foreign.page,fo)).value.revision,2);assert.equal((await editor(foreign.page,fo)).value.rows[0].version,1);
  assert.equal((await cmd(foreign.page,fo,envelope('EditCommercialLine',2,{lineId:fl,quantity:'2'}))).status,200);
  const externalSummary=(await editor(foreign.page,fo)).value.summary;assert.equal((await post(foreign.page,`${base}/orders/${fo}/technical-closure`,{id:uid(),expectedRevision:3})).status,201);
  const externalId=uid(),externalBody={id:externalId,expectedRevision:3};const ext=await post(foreign.page,`${base}/orders/${fo}/administrative-requests`,externalBody);assert.equal(ext.status,201,JSON.stringify(ext));
  const history=await json(foreign.page,`${base}/orders/${fo}/administrative-requests`);assert.equal(history.status,200);assert.equal(history.value.length,1);
  assert.equal((await post(foreign.page,`${base}/orders/${fo}/administrative-requests`,externalBody)).status,200);
  await foreign.context.close();pass('real exact grant/revoke/replay/CSRF/cross-tenant/hidden-collision rollback; existing external administrative snapshot path');
  const uiOrder=await createOrder(page),uiGroup=uid(),uiPart=uid();
  assert.equal((await cmd(page,uiOrder,envelope('AddGroup',0,{groupId:uiGroup,title:'UI structural'}))).status,201);
  assert.equal((await cmd(page,uiOrder,envelope('AddCommercialLine',1,{lineId:uiPart,groupId:uiGroup,catalogItemId:data.partId,catalogVersion:8,quantity:'4',unitPrice:'1',discountPercent:'0'}))).status,201);
  await page.goto(origin+'/ui01-runtime.html#order='+uiOrder);
  await page.getByText('Valori salvati riletti — revisione 2',{exact:true}).waitFor();
  await page.locator('#row-'+uiPart).click();
  assert.equal(await page.getByLabel('Quantità riga',{exact:true}).count(),1,'real Part structural quantity control must be exposed after server proof');
  await page.getByLabel('Quantità riga',{exact:true}).fill('5');
  await page.getByRole('button',{name:'Applica',exact:true}).click();
  await page.getByText('Valori salvati riletti — revisione 3',{exact:true}).waitFor();
  assert.equal((await editor(page,uiOrder)).value.rows[0].line.quantity,'5');
  const uiSecond=uid();assert.equal((await cmd(page,uiOrder,envelope('AddGroup',3,{groupId:uiSecond,title:'UI destination'}))).status,201);
  await page.reload();await page.getByText('Valori salvati riletti — revisione 4',{exact:true}).waitFor();await page.locator('#row-'+uiPart).click();await page.getByLabel('Quantità riga',{exact:true}).waitFor();
  assert.equal(await page.getByLabel('Lavorazione della riga').count(),1,'explicit supported group correction control');
  await page.getByLabel('Lavorazione della riga').selectOption(uiSecond);
  await page.getByLabel('Ricerca sostituisci articolo / prestazione',{exact:true}).fill('Synthetic alternate');await page.getByLabel('Ricerca sostituisci articolo / prestazione',{exact:true}).press('Enter');
  await page.getByLabel('Sostituisci articolo / prestazione',{exact:true}).selectOption(data.alternatePartId);
  await page.getByRole('button',{name:'Applica',exact:true}).click();await page.getByText('Valori salvati riletti — revisione 5',{exact:true}).waitFor();
  assert.deepEqual([(await editor(page,uiOrder)).value.rows[0].workingGroupId,(await editor(page,uiOrder)).value.rows[0].line.catalogItemId],[uiSecond,data.alternatePartId]);
  const removeButton=page.locator('tr',{has:page.locator('#row-'+uiPart)}).getByRole('button',{name:'Rimuovi',exact:true});
  assert.equal(await removeButton.isDisabled(),false);
  await removeButton.click();await page.getByText('Valori salvati riletti — revisione 6',{exact:true}).waitFor();assert.equal((await editor(page,uiOrder)).value.rows.length,0);
  pass('actual structural Part quantity and tombstone removal through supported UI controls');
  const ua=await createOrder(page),uag=uid(),ual=uid();
  await cmd(page,ua,envelope('AddGroup',0,{groupId:uag,title:'Active UI'}));await cmd(page,ua,envelope('AddCommercialLine',1,{lineId:ual,groupId:uag,catalogItemId:data.partId,catalogVersion:8,quantity:'4',unitPrice:'1',discountPercent:'0'}));
  assert.equal((await post(page,`/api/v1/inventory/orders/${ua}/lines/${ual}/reservations`,{id:uid(),warehouseId:ctx.warehouseId,catalogVersion:8,quantity:'1'})).status,201);
  await page.goto(origin+'/');await page.goto(origin+'/ui01-runtime.html#order='+ua);await page.getByText('Valori salvati riletti — revisione 2',{exact:true}).waitFor();await page.locator('#row-'+ual).click();
  await page.getByLabel('Quantità riga',{exact:true}).fill('5');await page.getByRole('button',{name:'Applica',exact:true}).click();
  await page.getByText('Impegni logistici attivi: modifica solo prezzo, sconto e descrizione, oppure rileggi la commessa.',{exact:true}).waitFor();assert.equal((await editor(page,ua)).value.revision,2);
  await page.getByLabel('Quantità riga',{exact:true}).fill('4');await page.getByLabel('Prezzo riga',{exact:true}).fill('2.123456');
  let lostBody='';await page.route('**/editor/commands',async route=>{lostBody=route.request().postData();const response=await route.fetch();assert.equal(response.status(),200);await response.body();await route.abort('failed');});
  await page.getByRole('button',{name:'Applica',exact:true}).click();await page.getByRole('button',{name:'Riprova comando identico',exact:true}).waitFor();
  assert.equal(await page.getByLabel('Quantità riga',{exact:true}).isDisabled(),true,'uncertain command must freeze editable controls');
  await page.unroute('**/editor/commands');let retryBody='';await page.route('**/editor/commands',async route=>{retryBody=route.request().postData();await route.continue();});
  await page.getByRole('button',{name:'Riprova comando identico',exact:true}).click();await page.getByText('Valori salvati riletti — revisione 3',{exact:true}).waitFor();assert.equal(retryBody,lostBody);await page.unroute('**/editor/commands');
  const lostCommand=JSON.parse(lostBody).commandId;assert.equal((await editor(page,ua)).value.rows[0].line.unitPrice,'2.123456');
  pass('actual active-commitment UI denial, allowed commercial edit, accepted-lost frozen byte-identical retry and authoritative reread');
  fs.writeFileSync('/run/control/result.json',JSON.stringify({checks,order,line,race,rl,rg,reservationId:reservation.id,pickId,installId,carcassId,invoiceId,journalId,rev,snapshot,secondGroup,r2,pk2,in2,ca2,externalId,externalSummary,fo,fl,uiOrder,uiPart,ua,ual,lostCommand}));
 }catch(e){console.error(e.stack||e);process.exitCode=1;}finally{await browser.close();}
})();
