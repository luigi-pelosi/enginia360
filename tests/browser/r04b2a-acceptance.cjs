const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json', 'utf8'));
const origin = 'https://app.r00.test:8443';
const checks = [];
const pass = (name) => { checks.push(name); console.log('PASS R04B2A ' + name); };
const uid = () => crypto.randomUUID();
const json = (page, path, options = {}) => page.evaluate(async ({ path, options }) => { const r = await fetch(path, options); return { status: r.status, value: await r.json().catch(() => null) }; }, { path, options });
const csrf = async (page) => (await json(page, '/auth/csrf')).value.requestToken;
async function post(page, path, body, token) {
  const t = token === undefined ? await csrf(page) : token;
  return json(page, path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(t ? { 'X-CSRF-TOKEN': t } : {}) }, body: typeof body === 'string' ? body : JSON.stringify(body) });
}
async function control(action) {
  fs.writeFileSync('/run/control/request.tmp', action); fs.renameSync('/run/control/request.tmp', '/run/control/request');
  for (let i = 0; i < 400; i++) {
    if (fs.existsSync('/run/control/ack')) { assert.equal(fs.readFileSync('/run/control/ack', 'utf8'), action); fs.unlinkSync('/run/control/ack'); return; }
    await new Promise((r) => setTimeout(r, 100));
  }
  assert.fail('ephemeral controller did not acknowledge ' + action);
}
const read = (name) => JSON.parse(fs.readFileSync('/run/control/' + name, 'utf8'));
const counts = async () => { await control('purchase-counts'); return read('purchase-counts.json'); };
const row = async (id) => { await control('purchase-row:' + id); return read('purchase-row.json'); };
async function login(browser, index) {
  const context = await browser.newContext(); const page = await context.newPage();
  await page.goto(origin + '/'); await page.getByRole('button', { name: 'Accedi', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Accedi', exact: true }).click();
  await page.locator('#username').fill(fixture.users[index].username); await page.locator('#password').fill(fixture.users[index].password);
  await Promise.all([page.waitForURL((u) => u.hostname === 'app.r00.test'), page.locator('#kc-login').click()]);
  return { context, page };
}
const ctx = fixture.contexts[0], data = fixture.workshop[0], pool = fixture.poolSize;
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const { page } = await login(browser, 0);
    // Order with three independent Part lines of quantity 3 (UI line, race line, role/mapping/grant line).
    const order = uid(); let revision = 0;
    assert.equal((await post(page, '/api/v1/workshop/orders', { id: order, legalEntityId: ctx.legalEntityId, siteId: ctx.siteId, documentTypeId: data.documentTypeId, configurationVersion: 7, payerId: data.payerId, vehicleId: data.vehicleId })).status, 201);
    const lines = [];
    async function command(type, fields) {
      const r = await post(page, `/api/v1/workshop/orders/${order}/editor/commands`, { type, commandId: uid(), expectedRevision: revision, expectedLinePolicyVersion: 9, expectedStructurePolicyVersion: 1,
        groupId: null, lineId: null, title: null, description: null, catalogItemId: null, catalogVersion: null, quantity: null, unitPrice: null, discountPercent: null, ...fields });
      assert.equal(r.status, 201, JSON.stringify(r)); revision = r.value.appliedRevision;
    }
    for (let i = 0; i < 3; i++) {
      const group = uid(), line = uid(); lines.push(line);
      await command('AddGroup', { groupId: group, title: 'Materiali ' + i });
      await command('AddCommercialLine', { lineId: line, groupId: group, catalogItemId: data.partId, catalogVersion: 8, quantity: '3', unitPrice: '1', discountPercent: '0' });
    }
    const url = (line) => `/api/v1/inventory/orders/${order}/lines/${line}/purchase-intents`;
    const stateOf = (line) => json(page, url(line) + '?warehouseId=' + ctx.warehouseId);
    const body = (line, over = {}, st) => ({ id: uid(), warehouseId: ctx.warehouseId, supplierId: st.suppliers[0].id, sourceRevision: st.source.revision, supplierRevision: st.suppliers[0].revision, mappingRevision: st.suppliers[0].mappingRevision, quantity: '1', ...over });

    // --- anonymous / CSRF / strict body / foreign tenant: separate from exact-action tests
    const st0 = (await stateOf(lines[0])).value;
    assert.equal(st0.state, 'ready'); assert.equal(st0.remaining, '3.000000');
    assert.deepEqual(st0.suppliers.map((s) => s.name), ['Fornitore sintetico'], 'only IsSupplier + verified current-company mapping');
    assert(!JSON.stringify(st0).match(/GBV|vendorId|Giobby/i), 'no ERP identifier reaches the browser');
    const anon = await browser.newPage(); await anon.goto(origin + '/');
    assert.equal((await post(anon, url(lines[0]), body(lines[0], {}, st0), 'none')).status, 401);
    await anon.close();
    assert.equal((await post(page, url(lines[0]), body(lines[0], {}, st0), '')).status, 400, 'missing CSRF'); // csrf_invalid
    assert.equal((await post(page, url(lines[0]), { ...body(lines[0], {}, st0), vendorId: 'GBV-X' })).status, 400, 'browser cannot send an external ID');
    assert.equal((await post(page, url(lines[0]), { ...body(lines[0], {}, st0), destination: 'x' })).status, 400, 'browser cannot send a destination');
    const foreign = await login(browser, 1);
    assert.equal((await post(foreign.page, url(lines[0]), body(lines[0], {}, st0))).status, 403, 'foreign tenant identity: no leak');
    assert.equal((await json(foreign.page, url(lines[0]) + '?warehouseId=' + ctx.warehouseId)).status, 404, 'foreign source is not found, never disclosed');
    assert.deepEqual(await counts().then((c) => [c.intents, c.outbox]), [0, 0]);
    pass('401 anonymous, CSRF, strict body, foreign tenant refused with no writes (independent of exact-action tests)');

    // --- real DOM happy path with lost accepted response
    await page.goto(origin + '/ui01-runtime.html#order=' + order); await page.getByLabel('Workspace commessa').waitFor();
    await page.getByText('Operazioni materiali', { exact: true }).click();
    const material = page.getByRole('region', { name: 'Operazioni materiali' });
    await material.getByLabel('Riga ricambio').selectOption(lines[0]); await material.getByLabel('Magazzino materiali').selectOption(ctx.warehouseId);
    const panel = page.getByRole('region', { name: "Richiesta d'acquisto" });
    await panel.getByText('Residuo richiedibile: 3').waitFor();
    assert.equal(await panel.getByLabel('Fornitore').locator('option').count(), 2, 'placeholder plus exactly one mapped supplier');
    await panel.getByLabel('Fornitore').selectOption({ label: 'Fornitore sintetico' }); await panel.getByLabel('Quantità da richiedere').fill('2');
    await panel.getByLabel('Prezzo acquisto mancante').fill('0'); // D91 explicit missing-cost completion; original retry/cap/snapshot assertions below remain unchanged.
    const posts = []; let dropped = false;
    page.on('request', (r) => { if (r.method() === 'POST' && r.url().endsWith('/purchase-intents/accepted')) posts.push({ url: r.url(), body: r.postData() }); });
    await page.route('**/purchase-intents/accepted', async (route) => {
      if (route.request().method() === 'POST' && !dropped) { dropped = true; await route.fetch(); await route.abort('failed'); } else await route.continue();
    });
    await panel.getByRole('button', { name: "Crea richiesta d'acquisto" }).click();
    await panel.getByText("Esito richiesta d'acquisto incerto: riprova solo il comando identico.").waitFor();
    for (const label of ['Fornitore', 'Quantità da richiedere']) assert(await panel.getByLabel(label).isDisabled());
    assert(await material.getByLabel('Riga ricambio').isDisabled(), 'ancestor selector frozen while command outcome is uncertain');
    await panel.getByRole('button', { name: 'Riprova richiesta identica' }).click();
    await panel.getByText('Richiesta registrata e riletta dal server.').waitFor();
    await panel.getByText('Residuo richiedibile: 1').waitFor();
    await panel.getByText(/In attesa — connettore d'acquisto non ancora attivo/).waitFor();
    assert.equal(posts.length, 2); assert.deepEqual(posts[1], posts[0], 'byte-identical URL and body');
    assert(!(await page.locator('body').innerText()).match(/GBV|vendorId/i));
    const first = JSON.parse(posts[0].body);
    const db = await row(first.id);
    assert.equal(db.Quantity, '2.000000'); assert.equal(db.Payload.supplierId, first.supplierId);
    assert.equal(db.Supplier.vendorId, 'GBV-4711'); assert.equal(db.Supplier.vendorName, 'Synthetic Supplier S.r.l.');
    assert.equal(db.Source.lineId, lines[0]); assert.equal(db.Source.quantity, '3.000000'); assert.match(db.Destination.fingerprint, /^[0-9a-f]{64}$/);
    assert.equal(db.Destination.kind, 'GiobbyPurchaseV1');
    let c = await counts(); assert.deepEqual([c.intents, c.outbox, c.held, c.quantity], [1, 1, 1, '2.000000']);
    pass('real UI create, lost accepted response, identical retry, authoritative reread and SQL: one intent, one Held outbox, frozen vendor/source/destination');
    await page.unroute('**/purchase-intents/accepted');

    // --- cumulative cap, replay and conflicts (API, new UUIDs, same line)
    let st = (await stateOf(lines[0])).value;
    const over = await post(page, url(lines[0]), body(lines[0], { quantity: '2' }, st));
    assert.equal(over.status, 409); assert.equal(over.value.state, 'exceeds_remaining');
    const one = body(lines[0], { quantity: '1' }, st);
    assert.equal((await post(page, url(lines[0]), one)).status, 201);
    assert.equal((await post(page, url(lines[0]), one)).status, 200, 'exact replay');
    assert.equal((await post(page, url(lines[0]), { ...one, quantity: '0.5' })).status, 409, 'changed payload');
    assert.equal((await post(page, url(lines[0]), body(lines[0], { quantity: '0.000001' }, st))).status, 409, 'line fully consumed: new UUID cannot reset the cap');
    c = await counts(); assert.deepEqual([c.intents, c.outbox, c.quantity], [2, 2, '3.000000']);
    for (const bad of ['0', '-1', '1.0000001', '1000000', '1e1', ' 1', 'NaN', '']) assert.equal((await post(page, url(lines[1]), body(lines[1], { quantity: bad }, st0))).status, 400, 'quantity ' + bad);
    for (const [field, value] of [['sourceRevision', 2147483647], ['supplierRevision', 2147483647], ['mappingRevision', 2147483647]]) assert.equal((await post(page, url(lines[1]), body(lines[1], { [field]: value }, st0))).status, 409, field + ' int max');
    for (const field of ['sourceRevision', 'supplierRevision', 'mappingRevision']) assert((await post(page, url(lines[1]), body(lines[1], { [field]: 2147483648 }, st0))).status === 400, field + ' beyond int');
    c = await counts(); assert.equal(c.intents, 2);
    pass('D90 cumulative cap, exact replay, payload conflict, q6 and int bounds: controlled refusals, no partial rows');

    // --- atomicity: fixture-only triggers (insert + deferred commit)
    for (const [table, mode] of [['purchase_intents', 'on'], ['purchase_intent_outbox', 'on'], ['purchase_intent_outbox', 'deferred']]) {
      await control(`purchase-fault:${table}:${mode}`);
      try { assert((await post(page, url(lines[1]), body(lines[1], {}, st0))).status >= 500); } finally { await control(`purchase-fault:${table}:off`); }
      c = await counts(); assert.deepEqual([c.intents, c.outbox], [2, 2], `${table}/${mode} rolled back`);
    }
    pass('rollback at intent insert, outbox insert and deferred commit: zero partial facts');

    // --- concurrency on physical connections (line 1: remaining 3): competing new UUIDs, then identical retries
    const need = pool === 1 ? 1 : 2;
    let race = (await stateOf(lines[1])).value;
    await control('hold-line:' + lines[1]);
    const a = post(page, url(lines[1]), body(lines[1], { quantity: '2' }, race)), b = post(page, url(lines[1]), body(lines[1], { quantity: '2' }, race));
    await control('wait-blocked:' + need); await control('release-commit');
    const statuses = (await Promise.all([a, b])).map((r) => r.status).sort();
    assert.deepEqual(statuses, [201, 409], 'two new UUIDs competing for remaining 3 with qty 2 each: at most one commits');
    c = await counts(); assert.equal(c.quantity, '5.000000');
    race = (await stateOf(lines[1])).value; assert.equal(race.remaining, '1.000000');
    const same = body(lines[1], { quantity: '1' }, race);
    await control('hold-line:' + lines[1]);
    const identical = [post(page, url(lines[1]), same), post(page, url(lines[1]), same), post(page, url(lines[1]), same)];
    await control('wait-blocked:' + need); await control('release-commit');
    const results = (await Promise.all(identical)).map((r) => r.status).sort();
    assert.equal(results.filter((s) => s === 201).length, 1); assert(results.every((s) => s === 201 || s === 200));
    c = await counts(); assert.deepEqual([c.intents, c.outbox, c.quantity], [4, 4, '6.000000']);
    pass('pg_blocking_pids-observed line lock: new-UUID race commits at most remaining; identical retries create one intent/outbox');

    // --- authority races (line 2): the controller holds the real SQL lock/row first, then the writer is observed blocked
    st = (await stateOf(lines[2])).value;
    const stale = body(lines[2], {}, st);
    await control('purchase-hold-mapping');
    const mappingRace = post(page, url(lines[2]), stale);
    await control('wait-blocked:1'); await control('release-commit');
    assert.equal((await mappingRace).status, 409, 'mapping revision committed first: stale frozen mapping refused');
    c = await counts(); assert.equal(c.intents, 4);
    st = (await stateOf(lines[2])).value; assert.equal(st.suppliers[0].mappingRevision, 2);
    const fresh = body(lines[2], { quantity: '1' }, st);
    assert.equal((await post(page, url(lines[2]), fresh)).status, 201);
    assert.equal((await row(fresh.id)).Supplier.vendorId, 'GBV-4712', 'new intent freezes the new mapping revision');
    assert.equal((await row(first.id)).Supplier.vendorId, 'GBV-4711', 'existing intent is not retargeted by the mapping change');
    await control('purchase-hold-grant');
    const grantRace = post(page, url(lines[2]), body(lines[2], { quantity: '1' }, st));
    await control('wait-blocked:1'); await control('release-commit');
    assert.equal((await grantRace).status, 403, 'exact grant revoked first: no write');
    await control('purchase-restore-grant');
    await control('purchase-hold-role');
    const roleRace = post(page, url(lines[2]), body(lines[2], { quantity: '1' }, st));
    await control('wait-blocked:1'); await control('release-commit');
    assert.equal((await roleRace).status, 409, 'supplier role cleared first: no write');
    assert.equal((await post(page, url(lines[2]), body(lines[2], { quantity: '1' }, st))).status, 409, 'later request also refused; committed intents immutable');
    c = await counts(); assert.deepEqual([c.intents, c.outbox, c.held], [5, 5, 5]);
    assert.equal((await stateOf(lines[2])).value.suppliers.length, 0, 'chooser no longer offers the cleared supplier');
    pass('mapping, exact grant and supplier-role changes serialize before the purchase write (controller-held locks); frozen history not retargeted');

    // --- sales-order dispatcher and Giobby fake never see a purchase intent
    assert.deepEqual([c.salesOutbox, c.salesDispatches], [0, 0]);
    await control('traffic'); assert.deepEqual(read('traffic.json'), { A: [], B: [] }, 'no purchasing HTTP writer: Giobby fake received no request');
    await control('logs-safe');
    pass('no sales-order dispatch row and zero HTTP traffic for purchase intents; outbox visibly Held');
    fs.writeFileSync('/run/control/result.json', JSON.stringify({ checks, order, lines, intents: c.intents }));
  } finally { await browser.close(); }
})().catch((e) => { console.error(e); process.exitCode = 1; });
