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
  const browser = await chromium.launch({ headless: true });
  try {
    const probe = await browser.newPage();
    await until(async () => { try { return (await probe.goto(origin+'/auth/session')).status(); } catch { return 0; } }, v => v === 200, 'TLS API ready');
    let { page } = await login(browser, 0);
    const { order } = await simpleOrder(page);
    assert.equal((await post(page, `${base}/orders/${order}/technical-closure`, { id: uid(), expectedRevision: 2 })).status, 201);
    await control('hold-dispatch');
    const requestId = uid();
    const queued = await post(page, `${base}/orders/${order}/administrative-requests`, { id: requestId, expectedRevision: 2 });
    assert.equal(queued.status, 201, JSON.stringify(queued));
    assert.equal(queued.value.delivery.state, 'Queued');
    await control('traffic');
    const traffic = () => JSON.parse(fs.readFileSync('/run/control/traffic.json', 'utf8'));
    assert.deepEqual(traffic(), {A: [], B: []}, 'creation/queue must not send HTTP');
    await control('restart:B');
    await until(() => json(page, '/auth/session'), r => r.status === 200, 'recreated API serving trusted TLS');
    await control('release-dispatch');
    ({ page } = await login(browser, 0).catch(async error => { for (const c of browser.contexts()) for (const p of c.pages()) console.error('PAGE', p.url(), await p.locator('body').innerText().catch(() => '')); throw error; }));
    let history;
    await until(async () => { history = await json(page, `${base}/orders/${order}/administrative-requests`); return history; }, h => h.status === 200 && h.value[0].delivery.state !== 'Queued', 'worker processed queued request after restart');
    await control('traffic');
    assert.deepEqual(traffic().B, [], 'B MUST receive ZERO POST/GET for request queued under A');
    assert.equal(history.value[0].delivery.state, 'NeedsReconciliation', 'controlled hold');
    assert.equal(history.value[0].delivery.lastError, 'destination_binding_mismatch');
    const heldPanel = await openPanel(page, order, 2);
    await heldPanel.getByText('Destinazione diversa/non verificata; nessun invio.', {exact: true}).waitFor();
    assert.equal(await heldPanel.getByText(/Confermata/).count(), 0);
    assert.deepEqual(history.value[0].connectorBinding, queued.value.connectorBinding);
    assert.equal(JSON.stringify(history).includes('http'), false, 'no connector URL in client history');
    pass('request-time binding: A queue without HTTP, B restart receives ZERO POST/GET, readable controlled hold');
    await control('restart:A');
    await until(() => json(page, '/auth/session'), r => r.status === 200, 'original A restored');
    ({page} = await login(browser, 0));
    const reconcileId = uid();
    assert.equal((await post(page, `${base}/orders/${order}/administrative-requests/${requestId}/reconciliation`, {id: reconcileId})).status, 202);
    await until(() => state(page, order), r => r.value?.request?.status === 'Confirmed', 'original request resumed on A');
    await control('logs-safe');
    const {order: unknownOrder} = await simpleOrder(page);
    assert.equal((await post(page, `${base}/orders/${unknownOrder}/technical-closure`, {id: uid(), expectedRevision: 2})).status, 201);
    await control('hold-dispatch');
    const unknownId = uid();
    assert.equal((await post(page, `${base}/orders/${unknownOrder}/administrative-requests`, {id: unknownId, expectedRevision: 2})).status, 201);
    await control('traffic'); const beforeUnknown = traffic().A;
    await control('restart:Unknown');
    await until(() => json(page, '/auth/session'), r => r.status === 200, 'unknown protocol keeps core API up');
    await control('release-dispatch');
    ({page} = await login(browser, 0));
    await until(() => state(page, unknownOrder), r => r.value?.request?.delivery.state !== 'Queued', 'unknown protocol hold');
    await control('traffic');
    assert.deepEqual(traffic().A, beforeUnknown, 'UNKNOWN protocol MUST refuse before ANY HTTP');
    assert.equal((await state(page, unknownOrder)).value.request.delivery.state, 'NeedsReconciliation');
    pass('unknown host protocol holds pending requests without HTTP and without blocking core UI/history');
    const {order: refusedOrder} = await simpleOrder(page);
    assert.equal((await post(page, `${base}/orders/${refusedOrder}/technical-closure`, {id: uid(), expectedRevision: 2})).status, 201);
    const unconfigured = await post(page, `${base}/orders/${refusedOrder}/administrative-requests`, {id: uid(), expectedRevision: 2});
    assert.equal(unconfigured.status, 409, 'unverified protocol creation must be a controlled refusal, not SQL failure');
    assert.equal(unconfigured.value.code, 'destination_binding_unverified');
    await control('restart:Missing');
    await until(() => json(page, '/auth/session').catch(() => ({status: 0})), r => r.status === 200, 'MISSING descriptor MUST keep core API/UI/history available', 15000);
    ({page} = await login(browser, 0));
    assert.equal((await state(page, order)).value.request.status, 'Confirmed', 'historical terminal receipt unchanged without descriptor');
    await control('traffic'); assert.deepEqual(traffic().B, []);
    pass('missing descriptor keeps core UI/history available without retarget or fallback');
    await control('restart:A');
    await until(() => json(page, '/auth/session'), r => r.status === 200, 'original host for historical read');
    ({page} = await login(browser, 0));
    const historicalId = uid();
    fs.writeFileSync('/run/control/historical.json', JSON.stringify({order: refusedOrder, requestId: historicalId, summary: (await editor(page, refusedOrder)).value.summary}));
    await control('historical-request');
    await until(() => state(page, refusedOrder), r => r.value?.request?.delivery.state === 'NeedsReconciliation', 'unbound historical hold');
    const historical = (await state(page, refusedOrder)).value.request;
    assert.equal(historical.connectorBinding, null);
    assert.equal(historical.status, 'Pending');
    await control('refuse-historical-backfill');
    const resumed = [];
    async function restart(target, crash = false) {
      await control((crash ? 'crash:' : 'restart:') + target);
      await until(() => json(page, '/auth/session').catch(() => ({status: 0})), r => r.status === 200, 'restarted API '+target);
      ({page} = await login(browser, 0));
    }
    for (const mode of ['receive', 'hold-response']) {
      await control('simulator:'+mode);
      const {order: pendingOrder} = await simpleOrder(page);
      assert.equal((await post(page, `${base}/orders/${pendingOrder}/technical-closure`, {id: uid(), expectedRevision: 2})).status, 201);
      const pendingId = uid();
      const pending = await post(page, `${base}/orders/${pendingOrder}/administrative-requests`, {id: pendingId, expectedRevision: 2});
      assert.equal(pending.status, 201);
      if (mode === 'receive') await until(() => state(page, pendingOrder), r => r.value?.request?.delivery.state === 'Received', 'acquisition is not confirmation');
      else await control('wait-inflight');
      await restart('B', mode === 'hold-response');
      await until(() => state(page, pendingOrder), r => r.value?.request?.delivery.state === 'NeedsReconciliation', 'changed host hold after '+mode);
      await control('traffic'); assert.deepEqual(traffic().B, [], 'B receives neither POST nor GET after '+mode);
      const hold = (await state(page, pendingOrder)).value.request;
      assert.equal(hold.status, 'Pending'); assert.deepEqual(hold.connectorBinding, pending.value.connectorBinding);
      await control('simulator-complete');
      await restart('A');
      const recovery = {id: uid()};
      assert.equal((await post(page, `${base}/orders/${pendingOrder}/administrative-requests/${pendingId}/reconciliation`, recovery)).status, 202);
      await until(() => state(page, pendingOrder), r => r.value?.request?.status === 'Confirmed', 'original status recovery '+mode);
      assert.equal((await post(page, `${base}/orders/${pendingOrder}/administrative-requests/${pendingId}/reconciliation`, recovery)).status, 200);
      await control('remote-effects');
      const effect = JSON.parse(fs.readFileSync('/run/control/effects.json')).find(e => e.requestId === pendingId);
      assert.equal(effect.posts, 1, 'same UUID one effect, no blind resubmission');
      assert(effect.statusQueries >= 1, 'resumed through original Status');
      resumed.push({order: pendingOrder, requestId: pendingId, mode, effect});
      pass(mode+': changed B ZERO HTTP, original A explicit recovery uses Status with one POST/effect');
    }
    await control('simulator:complete');
    const {order: pathOrder} = await simpleOrder(page);
    assert.equal((await post(page, `${base}/orders/${pathOrder}/technical-closure`, {id: uid(), expectedRevision: 2})).status, 201);
    await control('hold-dispatch'); const pathId = uid();
    const pathRequest = await post(page, `${base}/orders/${pathOrder}/administrative-requests`, {id: pathId, expectedRevision: 2});
    assert.equal(pathRequest.status, 201);
    await control('traffic'); const beforePath = traffic();
    await restart('Path'); await control('release-dispatch');
    await until(() => state(page, pathOrder), r => r.value?.request?.delivery.state === 'NeedsReconciliation', 'same host changed path hold');
    await control('traffic'); assert.deepEqual(traffic(), beforePath, 'changed base path never dispatches');
    await restart('Equivalent');
    assert.equal((await post(page, `${base}/orders/${pathOrder}/administrative-requests/${pathId}/reconciliation`, {id: uid()})).status, 202);
    await until(() => state(page, pathOrder), r => r.value?.request?.status === 'Confirmed', 'canonical equivalent host restores original descriptor');
    pass('same hostname changed path held; uppercase hostname canonical equivalent resumes original UUID');
    const {order: revokedOrder} = await simpleOrder(page);
    assert.equal((await post(page, `${base}/orders/${revokedOrder}/technical-closure`, {id: uid(), expectedRevision: 2})).status, 201);
    const revokedId = uid(), revokedBody = {id: revokedId, expectedRevision: 2};
    const revokedToken = await csrf(page);
    let pendingCreate;
    if (fixture.poolSize >= 4) {
      await control('hold-order:'+revokedOrder);
      pendingCreate = post(page, `${base}/orders/${revokedOrder}/administrative-requests`, revokedBody, revokedToken);
      await control('wait-order:1');
    }
    await control('admin-create:false');
    if (fixture.poolSize >= 4) await control('release-order');
    const deniedCreate = pendingCreate ? await pendingCreate : await post(page, `${base}/orders/${revokedOrder}/administrative-requests`, revokedBody);
    assert.equal(deniedCreate.status, 403, 'grant revoked before request/binding/outbox commit MUST refuse');
    assert.equal((await state(page, revokedOrder)).value.request, null);
    assert.equal((await post(page, `${base}/orders/${revokedOrder}/administrative-requests`, revokedBody)).status, 403);
    await control('admin-create:true');
    assert.equal((await post(page, `${base}/orders/${revokedOrder}/administrative-requests`, revokedBody)).status, 201);
    pass('exact runtime create grant revocation serializes before request/binding/outbox commit');
    fs.writeFileSync('/run/control/result.json', JSON.stringify({checks, order, requestId, queued, history, unknownOrder, unknownId, refusedOrder, historicalId, resumed, pathOrder, pathId, revokedOrder, revokedId}));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
