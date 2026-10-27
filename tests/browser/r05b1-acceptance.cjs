const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json', 'utf8'));
const origin = 'https://app.r00.test:8443';
const base = '/api/v1/workshop';
const checks = [];
const PROVIDER = 'Simulatore amministrativo v1 · nessun collegamento Giobby';
function pass(name) { checks.push(name); console.log('PASS R03C ' + name); }
async function json(page, path, options = {}) {
  return page.evaluate(async ({ path, options }) => { const r = await fetch(path, options); return { status: r.status, value: await r.json().catch(() => null) }; }, { path, options });
}
async function csrf(page) { return (await json(page, '/auth/csrf')).value.requestToken; }
async function post(page, path, body, token) {
  const t = token === undefined ? await csrf(page) : token;
  return json(page, path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(t ? { 'X-CSRF-TOKEN': t } : {}) }, body: JSON.stringify(body) });
}
async function control(action) {
  fs.writeFileSync('/run/control/request.tmp', action); fs.renameSync('/run/control/request.tmp', '/run/control/request');
  for (let i = 0; i < 300; i++) {
    if (fs.existsSync('/run/control/ack')) { assert.equal(fs.readFileSync('/run/control/ack', 'utf8'), action); fs.unlinkSync('/run/control/ack'); return; }
    await new Promise(r => setTimeout(r, 100));
  }
  assert.fail('ephemeral controller did not acknowledge ' + action);
}
async function until(read, accept, what, ms = 60000) {
  const stop = Date.now() + ms; let last;
  while (Date.now() < stop) { last = await read(); if (accept(last)) return last; await new Promise(r => setTimeout(r, 300)); }
  assert.fail('timed out waiting for ' + what + ': ' + JSON.stringify(last));
}
async function login(browser, index) {
  const context = await browser.newContext(); const page = await context.newPage();
  await page.goto(origin + '/'); await page.getByRole('button', { name: 'Accedi', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Accedi', exact: true }).click();
  await page.locator('#username').fill(fixture.users[index].username); await page.locator('#password').fill(fixture.users[index].password);
  await Promise.all([page.waitForURL(u => u.hostname === 'app.r00.test'), page.locator('#kc-login').click()]);
  return { context, page };
}
const uid = () => crypto.randomUUID();
const ctx = fixture.contexts[0], data = fixture.workshop[0];
const policyVersion = 9, structureVersion = 1;
function envelope(type, revision, extra = {}) {
  return { type, commandId: uid(), expectedRevision: revision, expectedLinePolicyVersion: policyVersion, expectedStructurePolicyVersion: structureVersion,
    groupId: null, lineId: null, title: null, description: null, catalogItemId: null, catalogVersion: null, quantity: null, unitPrice: null, discountPercent: null, ...extra };
}
const cmd = (page, orderId, body, token) => post(page, `${base}/orders/${orderId}/editor/commands`, body, token);
const editor = (page, orderId) => json(page, `${base}/orders/${orderId}/editor`);
const actions = (page, orderId) => json(page, `${base}/orders/${orderId}/closure-actions`);
const state = (page, orderId) => json(page, `${base}/orders/${orderId}/closure-state`);
async function createOrder(page) {
  const id = uid();
  const r = await post(page, `${base}/orders`, { id, legalEntityId: ctx.legalEntityId, siteId: ctx.siteId, documentTypeId: data.documentTypeId, configurationVersion: 7, payerId: data.payerId, vehicleId: data.vehicleId });
  assert(r.status === 201, 'order creation ' + r.status); return id;
}
// One group plus one Service line: revision 2.
async function simpleOrder(page) {
  const order = await createOrder(page), group = uid();
  assert.equal((await cmd(page, order, envelope('AddGroup', 0, { groupId: group, title: 'Lavorazione sintetica' }))).status, 201);
  assert.equal((await cmd(page, order, envelope('AddCommercialLine', 1, { lineId: uid(), groupId: group, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '1', unitPrice: '10.5', discountPercent: '0' }))).status, 201);
  return { order, group };
}
const panelOf = page => page.getByRole('region', { name: 'Chiusura e attesa amministrativa' });
async function openPanel(page, order, revision) {
  await page.goto(origin + '/ui01-runtime.html#order=' + order);
  await page.reload();
  await page.getByText('Valori salvati riletti — revisione ' + revision, { exact: true }).waitFor();
  await page.locator('summary', { hasText: 'Chiusura e attesa amministrativa' }).click();
  const panel = panelOf(page); await panel.waitFor();
  return panel;
}
const status = panel => panel.locator('#closure-status');
const byIdOf = summary => ({ ...summary, lines: [...summary.lines].sort((x, y) => x.id.localeCompare(y.id)) });
async function lostResponse(page, urlPattern, label) {
  const bodies = []; let lost; const dropped = new Promise(resolve => { lost = resolve; });
  await page.route(urlPattern, async route => {
    if (route.request().method() !== 'POST') return route.continue();
    bodies.push([route.request().url(), route.request().postData()]);
    if (bodies.length === 1) { await route.fetch(); await route.abort('failed'); lost(); } else await route.continue();
  });
  return { bodies, dropped, finish: async () => { await page.unroute(urlPattern); assert.equal(bodies.length, 2, label + ' retried once'); assert.deepEqual(bodies[0], bodies[1], label + ' byte-identical URL and payload'); } };
}
(async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const probe = await browser.newPage();
    await until(async () => { try {return (await probe.goto(origin+'/auth/session')).status();} catch {return 0;} }, v => v === 200, 'TLS API ready');
    let {page} = await login(browser, 0);
    const {order} = await simpleOrder(page);
    const requestPath = o => `${base}/orders/${o}/administrative-requests`;
    const closedOrder = async () => { const {order:o} = await simpleOrder(page); assert.equal((await post(page, `${base}/orders/${o}/technical-closure`, {id:uid(),expectedRevision:2})).status,201); return o; };
    const traffic = async () => { await control('traffic'); return JSON.parse(fs.readFileSync('/run/control/traffic.json')); };
    const held = o => until(() => state(page,o), r => r.value?.request?.delivery.state === 'NeedsReconciliation', 'uncertain hold');
    const confirm = o => until(() => state(page,o), r => r.value?.request?.status === 'Confirmed', 'matching readback confirmation');
    const resume = async (o,r) => { assert.equal((await post(page,requestPath(o)+`/${r}/reconciliation`,{id:uid()})).status,202); };
    async function restart(target) { await control('restart:'+target); await until(() => json(page,'/auth/session').catch(()=>({status:0})),r=>r.status===200,'restart '+target); ({page}=await login(browser,0)); }
    assert.equal((await post(page, `${base}/orders/${order}/technical-closure`, {id:uid(), expectedRevision:2})).status, 201);
    await control('hold-dispatch');
    const requestId = uid(), body={id:requestId,expectedRevision:2};
    assert.equal((await post(page,requestPath(order),body,null)).status,400,'CSRF required on binding producer');
    assert.equal((await post(page,requestPath(order),{...body,auth:'forged'})).status,400,'payload cannot choose auth');
    await control('admin-create:false');
    assert.equal((await post(page,requestPath(order),body)).status,403,'exact create grant required');
    await control('admin-create:true');
    const token=await csrf(page);
    const burst=await Promise.all(Array.from({length:4},()=>post(page,requestPath(order),body,token)));
    assert.deepEqual(burst.map(r=>r.status).sort(),[200,200,200,201]);
    const queued=burst.find(r=>r.status===201);
    assert.equal(queued.value.connectorBinding.kind,'GiobbyV1');
    await control(`counts:${order}:${requestId}`);
    const count=JSON.parse(fs.readFileSync('/run/control/counts.json'));
    assert.deepEqual([count.requests,count.bindings,count.outbox],[1,1,1]);
    assert.deepEqual(await traffic(),{A:[],B:[]});
    const {page:foreign}=await login(browser,1);
    assert.equal((await json(foreign,requestPath(order))).status,404,'cross-tenant history hidden');
    await restart('B'); await control('release-dispatch'); await held(order);
    assert.deepEqual(await traffic(),{A:[],B:[]},'A queued then B restart: Submit AND Status blocked');
    await restart('A'); await resume(order,requestId); await held(order);
    assert.equal((await state(page,order)).value.request.delivery.lastError,'lookup_empty','empty lookup never authorizes resubmit');
    assert((await traffic()).A.every(c=>c.method==='GET'));
    pass('Giobby request-time atomic binding, concurrent exact replay, CSRF/grant/RLS; A-to-B zero HTTP; empty recovery holds without POST');
    const ok=await closedOrder(), okId=uid();
    assert.equal((await post(page,requestPath(ok),{id:okId,expectedRevision:2})).status,201);
    await confirm(ok);
    const panel=await openPanel(page,ok,2);
    await panel.getByText('Giobby · ordine cliente (candidato tecnico) · conversione manuale in fattura',{exact:true}).waitFor();
    await panel.getByText(/Confermata dal gestionale · riferimento GiobbyOrder-/).waitFor();
    pass('real DOM+fetch declares actual Giobby protocol; exact readback persisted as Confirmed (not invoice)');
    await control('simulator:ack-only');
    const ack=await closedOrder(), ackId=uid();
    assert.equal((await post(page,requestPath(ack),{id:ackId,expectedRevision:2})).status,201);
    await held(ack);
    assert.equal((await state(page,ack)).value.request.status,'Pending','HTTP200 idDocument alone is NOT business completion');
    await restart('B'); await resume(ack,ackId); await held(ack);
    assert.deepEqual((await traffic()).B,[],'Status for an already submitted A request blocked on B');
    await control('simulator:complete'); await restart('A'); await resume(ack,ackId); await confirm(ack);
    pass('ack-only HTTP200 held, Status retarget blocked, original A restored and exact GET confirms without another POST');
    await control('simulator:500');
    const failed=await closedOrder(), failedId=uid();
    assert.equal((await post(page,requestPath(failed),{id:failedId,expectedRevision:2})).status,201);
    await confirm(failed); // 500 persisted a synthetic effect, then lookup+exact readback recovers it, never rejects/reposts.
    pass('HTTP500 ambiguity resolved through typed bounded GET+readback; no duplicate POST');
    await control('simulator:timeout');
    const timed=await closedOrder(), timedId=uid();
    assert.equal((await post(page,requestPath(timed),{id:timedId,expectedRevision:2})).status,201);
    await held(timed);
    assert.equal((await state(page,timed)).value.request.status,'Pending');
    await control('simulator:complete'); await resume(timed,timedId); await confirm(timed);
    pass('real TLS timeout holds after receiver commit; explicit recovery is GET-only');
    await control('simulator:empty');
    const empty=await closedOrder(), emptyId=uid();
    assert.equal((await post(page,requestPath(empty),{id:emptyId,expectedRevision:2})).status,201);
    await held(empty); await resume(empty,emptyId); await held(empty);
    assert.equal((await state(page,empty)).value.request.delivery.lastError,'lookup_empty');
    pass('empty lookup stays ambiguous even after explicit reconciliation; no blind resubmit');
    await control('simulator:redirect');
    const redirect=await closedOrder(), redirectId=uid();
    assert.equal((await post(page,requestPath(redirect),{id:redirectId,expectedRevision:2})).status,201);
    await held(redirect); assert.deepEqual((await traffic()).B,[],'credential-bearing redirect denied by actual HTTP handler');
    pass('actual 307 redirect never forwards token or business request to B');
    await control('remote-effects');
    const effects=JSON.parse(fs.readFileSync('/run/control/effects.json'));
    assert.equal(effects.length,5);
    for (const id of [okId,ackId,failedId,timedId,emptyId]) assert.equal(effects.filter(e=>e.requestId==='E360-'+id.replaceAll('-','')).length,1,'single remote effect '+id);
    const wire=await traffic();
    assert.equal(wire.A.filter(c=>c.method==='POST').length,6,'five effects plus refused redirect, no duplicate POST');
    assert(wire.A.every(c=>c.authVerified)); assert.deepEqual(wire.B,[]);
    assert(wire.A.every(c=>c.path==='/loggeduser'||/^\/sales\/(orders|\d+\/orders)(\?|$)/.test(c.path)),'no invoice/proforma/purchase/stock endpoints EVER');
    await control('logs-safe');
    // Regression: the same immutable transaction fence rolls all three rows back under each fixture-only fault.
    await control('hold-dispatch');
    for (const [table,mode] of [['administrative_requests','on'],['administrative_bindings','on'],['administrative_outbox','on'],['administrative_outbox','deferred']]) {
      const o=await closedOrder(), r=uid();
      await control(`fault:${table}:${mode}`);
      try {assert((await post(page,requestPath(o),{id:r,expectedRevision:2})).status>=500);} finally {await control(`fault:${table}:off`);}
      await control(`counts:${o}:${r}`); const c=JSON.parse(fs.readFileSync('/run/control/counts.json'));
      assert.deepEqual([c.requests,c.bindings,c.outbox],[0,0,0]);
    }
    pass('Giobby creation transaction rollback after request/binding/outbox and deferred commit: zero partial facts');
    fs.writeFileSync('/run/control/result.json',JSON.stringify({checks,order,requestId,ok,okId,ack,ackId,failed,timed,empty,effects,wire}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
