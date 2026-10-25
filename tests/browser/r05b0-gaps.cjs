// R05.b.0 declared proof gaps: idempotency/concurrency, refusals, atomicity and lease/reconciliation races.
// Real trusted-TLS OIDC Chromium -> API -> PostgreSQL, two isolated synthetic simulators (A bound, B foreign). Synthetic data only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json', 'utf8'));
const origin = 'https://app.r00.test:8443';
const base = '/api/v1/workshop';
const checks = [];
const ZERO = '00000000-0000-0000-0000-000000000000';
function pass(name) { checks.push(name); console.log('PASS R05B0-GAP ' + name); }
async function json(page, path, options = {}) {
  return page.evaluate(async ({ path, options }) => { const r = await fetch(path, options); const text = await r.text(); let value = null; try { value = JSON.parse(text); } catch {} return { status: r.status, value, text }; }, { path, options });
}
async function csrf(page) { return (await json(page, '/auth/csrf')).value.requestToken; }
// token: undefined -> fetch a real token; null -> deliberately omit the header.
async function post(page, path, body, token) {
  const t = token === undefined ? await csrf(page) : token;
  return json(page, path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(t ? { 'X-CSRF-TOKEN': t } : {}) }, body: typeof body === 'string' ? body : JSON.stringify(body) });
}
async function control(action) {
  fs.writeFileSync('/run/control/request.tmp', action); fs.renameSync('/run/control/request.tmp', '/run/control/request');
  for (let i = 0; i < 600; i++) {
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
const policyVersion = 9, structureVersion = 1;
function envelope(type, revision, extra = {}) {
  return { type, commandId: uid(), expectedRevision: revision, expectedLinePolicyVersion: policyVersion, expectedStructurePolicyVersion: structureVersion,
    groupId: null, lineId: null, title: null, description: null, catalogItemId: null, catalogVersion: null, quantity: null, unitPrice: null, discountPercent: null, ...extra };
}
// Technically closed order at revision 2 for the given fixture tenant index.
async function closedOrder(page, index) {
  const ctx = fixture.contexts[index], data = fixture.workshop[index], order = uid(), group = uid();
  const created = await post(page, `${base}/orders`, { id: order, legalEntityId: ctx.legalEntityId, siteId: ctx.siteId, documentTypeId: data.documentTypeId, configurationVersion: 7, payerId: data.payerId, vehicleId: data.vehicleId });
  assert.equal(created.status, 201, 'order ' + created.text);
  const commands = `${base}/orders/${order}/editor/commands`;
  assert.equal((await post(page, commands, envelope('AddGroup', 0, { groupId: group, title: 'Lavorazione sintetica' }))).status, 201);
  assert.equal((await post(page, commands, envelope('AddCommercialLine', 1, { lineId: uid(), groupId: group, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '1', unitPrice: '10.5', discountPercent: '0' }))).status, 201);
  assert.equal((await post(page, `${base}/orders/${order}/technical-closure`, { id: uid(), expectedRevision: 2 })).status, 201);
  return order;
}
const requestPath = order => `${base}/orders/${order}/administrative-requests`;
async function counts(order, request) {
  await control(`counts:${order}:${request}`);
  return JSON.parse(fs.readFileSync('/run/control/counts.json', 'utf8'));
}
const rows = (c, n) => assert.deepEqual([c.requests, c.bindings, c.outbox], [n, n, n], 'request/binding/outbox rows ' + JSON.stringify(c));
async function totals() { const c = await counts(uid(), uid()); return [c.totalRequests, c.totalBindings, c.totalOutbox]; }
async function dispatchRow(request) {
  await control('dispatch-read:' + request);
  return JSON.parse(fs.readFileSync('/run/control/dispatch.json', 'utf8'));
}
async function traffic() { await control('traffic'); return JSON.parse(fs.readFileSync('/run/control/traffic.json', 'utf8')); }
const withoutDelivery = view => { const { delivery, ...rest } = view; return rest; };
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const probe = await browser.newPage();
    await until(async () => { try { return (await probe.goto(origin + '/auth/session')).status(); } catch { return 0; } }, v => v === 200, 'TLS API ready');
    let { page } = await login(browser, 0);
    const { page: foreign } = await login(browser, 1);
    const { page: readOnly } = await login(browser, 5);
    // Dispatch discovery is held so request/binding/outbox rows stay observable; nothing is sent to any simulator.
    await control('hold-dispatch');
    const initial = await traffic();
    assert.deepEqual(initial, { A: [], B: [] }, 'no HTTP before any request');

    // ---- Gap 1: identical-UUID concurrency -----------------------------------------------------------------
    const order1 = await closedOrder(page, 0), id1 = uid(), token = await csrf(page);
    const burst = await Promise.all(Array.from({ length: 8 }, () => post(page, requestPath(order1), { id: id1, expectedRevision: 2 }, token)));
    const statuses = burst.map(r => r.status).sort();
    assert.deepEqual(statuses, [200, 200, 200, 200, 200, 200, 200, 201], 'one creation, seven replays: ' + statuses);
    const reference = JSON.stringify(withoutDelivery(burst[0].value));
    for (const r of burst) assert.equal(JSON.stringify(withoutDelivery(r.value)), reference, 'identical response for every retry');
    assert(burst[0].value.connectorBinding, 'response carries the frozen binding');
    rows(await counts(order1, id1), 1);
    pass('8 concurrent identical-UUID retries: exactly one request/binding/outbox row and the same response');

    const order2 = await closedOrder(page, 0);
    const before = await totals();
    const changedRevision = await post(page, requestPath(order1), { id: id1, expectedRevision: 3 });
    assert.equal(changedRevision.status, 409, 'same UUID with a different revision');
    const otherOrder = await post(page, requestPath(order2), { id: id1, expectedRevision: 2 });
    assert.equal(otherOrder.status, 409, 'same UUID against a different order');
    rows(await counts(order2, id1), 1); // id1 still maps to the single original rows; order2 gained nothing
    const order2Only = await counts(order2, uid()); rows(order2Only, 0);
    assert.deepEqual(await totals(), before, 'conflicts persisted nothing');
    pass('same UUID with different revision or different order: controlled 409, no new row');

    const order3 = await closedOrder(page, 0);
    const race = await Promise.all(Array.from({ length: 6 }, () => post(page, requestPath(order3), { id: uid(), expectedRevision: 2 }, token)));
    const raceStatuses = race.map(r => r.status).sort();
    assert.deepEqual(raceStatuses, [201, 409, 409, 409, 409, 409], 'distinct UUIDs on one order: one creation: ' + raceStatuses);
    for (const r of race.filter(r => r.status === 409)) assert.equal(r.value.code, 'already_requested');
    rows(await counts(order3, uid()), 1);
    pass('6 concurrent distinct UUIDs on one order: exactly one request/binding/outbox, others already_requested');

    // Foreign-tenant UUID collision: tenant 1 owns X; tenant 0 reuses X on its own order.
    const foreignOrder = await closedOrder(foreign, 1), foreignId = uid();
    assert.equal((await post(foreign, requestPath(foreignOrder), { id: foreignId, expectedRevision: 2 })).status, 201, 'foreign tenant creates its own request');
    const order4 = await closedOrder(page, 0);
    const collision = await post(page, requestPath(order4), { id: foreignId, expectedRevision: 2 });
    assert.equal(collision.status, 409, 'foreign UUID collision: ' + collision.text);
    for (const secret of [foreignOrder, fixture.contexts[1].tenantId, fixture.contexts[1].legalEntityId, 'connectorBinding', 'fingerprint'])
      assert.equal(collision.text.includes(secret), false, 'collision response discloses nothing about the other tenant');
    assert.deepEqual(await counts(order4, uid()).then(c => [c.requests, c.bindings, c.outbox]), [0, 0, 0], 'tenant 0 order gained no row');
    const owner = await (async () => { await control('binding-owner:' + foreignId); return JSON.parse(fs.readFileSync('/run/control/binding-owner.json', 'utf8')); })();
    assert.equal(owner.tenant, fixture.contexts[1].tenantId); assert.equal(owner.bindingTenant, fixture.contexts[1].tenantId); assert.equal(owner.order, foreignOrder);
    rows(await counts(foreignOrder, foreignId), 1);
    pass('foreign-tenant UUID collision: controlled 409 without disclosure, no binding written for the colliding tenant, foreign rows untouched');

    // Invalid and boundary payloads: nothing persisted.
    const order5 = await closedOrder(page, 0), valid = uid();
    const beforeInvalid = await totals();
    const invalid = {
      'empty UUID': { id: ZERO, expectedRevision: 2 }, 'negative revision': { id: valid, expectedRevision: -1 },
      'missing id': { expectedRevision: 2 }, 'non-UUID id': { id: 'not-a-uuid', expectedRevision: 2 },
      'revision above int32': { id: valid, expectedRevision: 2147483648 }, 'fractional revision': { id: valid, expectedRevision: 2.5 },
      'string revision': { id: valid, expectedRevision: '2' }, 'null revision': { id: valid, expectedRevision: null },
      'unknown destination': { id: valid, expectedRevision: 2, destination: 'External' }, 'unknown provider': { id: valid, expectedRevision: 2, provider: 'giobby' },
      'unknown url': { id: valid, expectedRevision: 2, url: 'http://simulator-b:8080/' }, 'unknown source': { id: valid, expectedRevision: 2, source: 'client' },
      'unknown connectorBinding': { id: valid, expectedRevision: 2, connectorBinding: { kind: 'SimulatorV1', protocolVersion: 1, destinationFingerprint: 'a'.repeat(64) } },
      'unknown baseUrl': { id: valid, expectedRevision: 2, baseUrl: 'http://simulator-b:8080/' }
    };
    for (const [name, body] of Object.entries(invalid)) {
      const r = await post(page, requestPath(order5), body);
      assert.equal(r.status, 400, name + ' -> ' + r.status + ' ' + r.text);
      assert.equal(r.text.includes('Exception') || r.text.includes('at Enginia360'), false, name + ' leaks no stack');
    }
    for (const [name, raw] of [['JSON null', 'null'], ['array', '[]'], ['truncated JSON', '{"id":']]) {
      const r = await post(page, requestPath(order5), raw);
      assert.equal(r.status, 400, name + ' -> ' + r.status + ' ' + r.text);
    }
    const maxBound = await post(page, requestPath(order5), { id: valid, expectedRevision: 2147483647 });
    assert.equal(maxBound.status, 409, 'max int32 revision is a controlled revision conflict'); assert.equal(maxBound.value.code, 'revision_changed');
    assert.deepEqual(await totals(), beforeInvalid, 'no invalid or boundary payload persisted anything');
    rows(await counts(order5, valid), 0);
    pass('invalid, unknown-member and max-bound payloads: 400/409 and zero rows in request/binding/outbox');

    // ---- Gap 2: refusals ----------------------------------------------------------------------------------
    const order6 = await closedOrder(page, 0), id6 = uid(), body6 = { id: id6, expectedRevision: 2 };
    const expectRefused = async (name, result, allowed) => {
      assert(allowed.includes(result.status), `${name}: ${result.status} ${result.text}`);
      rows(await counts(order6, id6), 0);
      console.log(`REFUSED ${name} -> ${result.status}`);
    };
    await expectRefused('missing CSRF', await post(page, requestPath(order6), body6, null), [400]);
    await expectRefused('wrong CSRF', await post(page, requestPath(order6), body6, 'forged'), [400]);
    await expectRefused('wrong tenant', await post(foreign, requestPath(order6), body6), [404]);
    await expectRefused('read-only membership', await post(readOnly, requestPath(order6), body6), [403, 404]);
    await control('capability:external-administration:false');
    await expectRefused('external-administration capability disabled', await post(page, requestPath(order6), body6), [403]);
    await control('capability:external-administration:true');
    await control('capability:workshop:false');
    await expectRefused('workshop capability disabled', await post(page, requestPath(order6), body6), [403, 404]);
    await control('capability:workshop:true');
    const accepted = await post(page, requestPath(order6), body6);
    assert.equal(accepted.status, 201, 'the same valid request succeeds once every blocker is removed: ' + accepted.text);
    rows(await counts(order6, id6), 1);
    pass('missing/forged CSRF, wrong tenant, read-only role and disabled capabilities: refused with zero rows; the same body succeeds afterwards');

    // ---- Gap 3: atomicity ----------------------------------------------------------------------------------
    for (const [table, mode, label] of [['administrative_requests', 'on', 'after request insert'], ['administrative_bindings', 'on', 'after binding insert'],
                                        ['administrative_outbox', 'on', 'after outbox insert'], ['administrative_outbox', 'deferred', 'at commit after all three inserts']]) {
      const order = await closedOrder(page, 0), id = uid(), body = { id, expectedRevision: 2 };
      await control(`fault:${table}:${mode}`);
      let failed;
      try { failed = await post(page, requestPath(order), body); } finally { await control(`fault:${table}:off`); }
      assert(failed.status >= 500, `${label}: forced failure surfaces as a server error, got ${failed.status}`);
      assert.equal(failed.text.includes('synthetic atomicity fault'), false, label + ': internal error text not disclosed');
      rows(await counts(order, id), 0);
      const retried = await post(page, requestPath(order), body);
      assert.equal(retried.status, 201, label + ': retry of the same UUID after the fault is removed: ' + retried.text);
      rows(await counts(order, id), 1);
      pass(`atomicity ${label}: request, binding and outbox rolled back together; same UUID then commits all three once`);
    }
    await control('release-dispatch');

    // ---- Gap 4: lease and reconciliation races -------------------------------------------------------------
    await control('simulator:receive');
    const order7 = await closedOrder(page, 0), id7 = uid();
    assert.equal((await post(page, requestPath(order7), { id: id7, expectedRevision: 2 })).status, 201);
    const stateOf = () => json(page, `${base}/orders/${order7}/closure-state`);
    await until(stateOf, r => r.value?.request?.delivery.state === 'Received', 'acquired under A');
    const effectOf = async () => { await control('remote-effects'); return JSON.parse(fs.readFileSync('/run/control/effects.json')).find(e => e.requestId === id7); };
    async function restart(target) {
      await control('restart:' + target);
      await until(() => json(page, '/auth/session').catch(() => ({ status: 0 })), r => r.status === 200, 'restarted API ' + target);
      ({ page } = await login(browser, 0));
    }
    await restart('B');
    const held = await until(() => dispatchRow(id7), r => r?.State === 'NeedsReconciliation', 'Received claim path refuses B');
    assert.equal(held.LastError, 'destination_binding_mismatch');
    const attempts = held.Attempts;
    const baseline = await effectOf();
    assert.equal(baseline.posts, 1);
    let lastUpdate = held.UpdatedAt;
    const expectHeld = async (what) => {
      const row = await until(() => dispatchRow(id7), r => r?.State === 'NeedsReconciliation' && r.LastError === 'destination_binding_mismatch' && r.UpdatedAt !== lastUpdate, what);
      lastUpdate = row.UpdatedAt;
      assert.equal(row.Attempts, attempts, what + ': no attempt consumed');
      assert.equal(row.LeaseUntil, null, what + ': lease released');
      assert.deepEqual((await traffic()).B, [], what + ': simulator B received ZERO HTTP');
      assert.deepEqual(await effectOf(), baseline, what + ': simulator A saw no further POST or Status for this request');
    };
    pass('Received claim path under B: NeedsReconciliation/destination_binding_mismatch, B counters zero, SQL readback');
    for (const forced of ['Queued', 'Retrying', 'Uncertain', 'Received']) {
      await control(`dispatch-set:${id7}:${forced}`);
      await expectHeld(`stale-lease ${forced} claim`);
      pass(`stale expired lease in ${forced} claim path refused before HTTP (SQL readback, B counters zero)`);
    }
    const recon = () => post(page, `${base}/orders/${order7}/administrative-requests/${id7}/reconciliation`, { id: uid() });
    assert.equal((await recon()).status, 202);
    await expectHeld('reconcile-resume under B');
    pass('reconcile-resume while configured for B: back to NeedsReconciliation, B counters zero, attempts unchanged');
    const sameCommand = uid();
    const concurrent = await Promise.all([sameCommand, sameCommand, uid(), uid(), uid(), uid()].map(id => post(page, `${base}/orders/${order7}/administrative-requests/${id7}/reconciliation`, { id })));
    for (const r of concurrent) assert([200, 202, 409].includes(r.status), 'controlled reconcile status ' + r.status + ' ' + r.text);
    assert(concurrent.some(r => r.status === 202), 'at least one reconciliation accepted');
    await expectHeld('concurrent reconciles under B');
    const racing = await Promise.all([control(`dispatch-set:${id7}:Uncertain`), recon(), recon(), recon()]);
    await new Promise(r => setTimeout(r, 1500));
    await until(() => dispatchRow(id7), r => r?.State === 'NeedsReconciliation' && r.LastError === 'destination_binding_mismatch' && r.LeaseUntil === null, 'stale lease racing reconcile settles on hold');
    assert.equal((await dispatchRow(id7)).Attempts, attempts);
    assert.deepEqual((await traffic()).B, [], 'stale lease racing reconciles: B received ZERO HTTP');
    pass('stale-lease worker racing concurrent reconciles never reaches B: hold, attempts unchanged, B counters zero');
    await restart('A');
    await control('simulator-complete');
    assert.equal((await recon()).status, 202);
    await until(stateOf, r => r.value?.request?.status === 'Confirmed', 'original destination A resumes through Status');
    await control('remote-effects');
    const effect = JSON.parse(fs.readFileSync('/run/control/effects.json')).find(e => e.requestId === id7);
    assert.equal(effect.posts, 1, 'one POST ever'); assert(effect.statusQueries >= 1);
    assert.deepEqual((await traffic()).B, [], 'B never contacted for the whole gap suite');
    pass('restoring the original destination resumes the same UUID via Status with one POST/effect; B never contacted');
    fs.writeFileSync('/run/control/result.json', JSON.stringify({ checks, order1, id1, foreignId, order7, id7 }));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
