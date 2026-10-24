// R06.b.1 synthetic ephemeral restore rehearsal: phased real Chromium/OIDC browser. Phases: seed, marker2, readback.
// Only existing authorized APIs are used. No tokens/cookies are ever written to the control files.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync('/run/fixture.json', 'utf8'));
const phase = process.env.R06B1_PHASE;
const origin = 'https://app.r00.test:8443';
const base = '/api/v1/workshop';
const ctx = fixture.contexts[0], data = fixture.workshop[0];
const fctx = fixture.contexts[1], fdata = fixture.workshop[1];
const uid = () => crypto.randomUUID();
const checks = [];
function pass(name) { checks.push(name); console.log('PASS R06B1 ' + phase + ' ' + name); }
async function json(page, path, options = {}) {
  return page.evaluate(async ({ path, options }) => { const r = await fetch(path, options); return { status: r.status, value: await r.json().catch(() => null) }; }, { path, options });
}
async function csrf(page) { return (await json(page, '/auth/csrf')).value.requestToken; }
async function post(page, path, body, token) {
  const t = token === undefined ? await csrf(page) : token;
  return json(page, path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(t ? { 'X-CSRF-TOKEN': t } : {}) }, body: JSON.stringify(body) });
}
async function login(browser, index) {
  // A NEW context per login: no cookie, ticket or CSRF state survives from before the destruction of cluster A.
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(origin + '/'); await page.getByRole('button', { name: 'Accedi', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Accedi', exact: true }).click();
  await page.locator('#username').fill(fixture.users[index].username); await page.locator('#password').fill(fixture.users[index].password);
  await Promise.all([page.waitForURL(u => u.hostname === 'app.r00.test'), page.locator('#kc-login').click()]);
  return { context, page };
}
function envelope(type, revision, extra = {}) {
  return { type, commandId: uid(), expectedRevision: revision, expectedLinePolicyVersion: 9, expectedStructurePolicyVersion: 1,
    groupId: null, lineId: null, title: null, description: null, catalogItemId: null, catalogVersion: null, quantity: null, unitPrice: null, discountPercent: null, ...extra };
}
const cmd = (page, orderId, body) => post(page, `${base}/orders/${orderId}/editor/commands`, body);
const editor = (page, orderId) => json(page, `${base}/orders/${orderId}/editor`);
async function createOrder(page) {
  const id = uid();
  const r = await post(page, `${base}/orders`, { id, legalEntityId: ctx.legalEntityId, siteId: ctx.siteId, documentTypeId: data.documentTypeId, configurationVersion: 7, payerId: data.payerId, vehicleId: data.vehicleId });
  assert.equal(r.status, 201, 'order creation ' + JSON.stringify(r)); return id;
}
async function ready(browser) {
  const probe = await browser.newPage();
  for (let i = 0; i < 240; i++) {
    try { if ((await probe.goto(origin + '/auth/session')).status() === 200) { await probe.close(); return; } } catch {}
    await new Promise(r => setTimeout(r, 500));
  }
  assert.fail('API/web not usable within the bounded readiness window');
}
// Every operation that the seed performs is recorded once so readback replays the exact same URL/UUID/payload.
const receipts = [];
async function record(page, name, path, body, expected = [201], actor = 'A', volatile = false) {
  const first = await post(page, path, body);
  assert(expected.includes(first.status), name + ' ' + JSON.stringify(first));
  const replay = await post(page, path, body);
  assert.equal(replay.status, 200, name + ' exact replay in seed ' + JSON.stringify(replay));
  // volatile: the live dispatcher state (attempts/lastError) legitimately moves while the API runs; identity is still compared.
  if (!volatile) assert.deepEqual(replay.value, first.value, name + ' replay value');
  receipts.push({ name, actor, volatile, path, body, firstStatus: first.status, replayStatus: replay.status, value: first.value });
  return first;
}
async function projection(a, b, f, ids) {
  const out = {};
  const inv = `/api/v1/inventory/orders/${ids.order}/lines/${ids.partLine}`;
  out.editor = (await editor(a, ids.order)).value;
  out.markerEditor = (await editor(a, ids.markerOrder)).value;
  const ownPath = `${base}/orders/${ids.order}/actual-time/own`;
  out.ownA = (await json(a, ownPath)).value;
  out.ownAHistory = (await json(a, `${ownPath}/${ids.entry}/history`)).value;
  out.ownB = (await json(b, ownPath)).value;
  out.ownForeign = (await json(f, `${base}/orders/${ids.foreignOrder}/actual-time/own`)).value;
  out.foreignEditor = (await editor(f, ids.foreignOrder)).value;
  out.lineState = (await json(a, `${inv}?warehouseId=${ctx.warehouseId}`)).value;
  out.releaseHistory = (await json(a, `${inv}/reservations/${ids.releasedReservation}/releases`)).value;
  out.pickHistory = (await json(a, `${inv}/reservations/${ids.pickedReservation}/picks`)).value;
  out.carcass = (await json(a, `${inv}/carcass-returns?warehouseId=${ctx.warehouseId}`)).value;
  out.installations = (await json(a, `${base}/orders/${ids.order}/lines/${ids.partLine}/picks/${ids.pick}/installations`)).value;
  return out;
}

async function seed(browser) {
  await ready(browser);
  const A = await login(browser, 0), B = await login(browser, 5), F = await login(browser, 1);
  const a = A.page;
  const order = await createOrder(a);
  const g1 = uid(), g2 = uid(), serviceLine = uid(), partLine = uid(), noteLine = uid();
  const step = async (body) => { const r = await cmd(a, order, body); assert.equal(r.status, 201, JSON.stringify(r)); return r; };
  let rev = 0;
  for (const body of [
    () => envelope('AddGroup', rev, { groupId: g1, title: 'Materiali' }),
    () => envelope('AddGroup', rev, { groupId: g2, title: 'Tempo effettivo' }),
    () => envelope('AddCommercialLine', rev, { lineId: serviceLine, groupId: g2, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '1.5', unitPrice: '20', discountPercent: '5' }),
    () => envelope('AddCommercialLine', rev, { lineId: partLine, groupId: g1, catalogItemId: data.partId, catalogVersion: 8, quantity: '3', unitPrice: '10', discountPercent: '0' }),
    () => envelope('AddNote', rev, { lineId: noteLine, groupId: g1, description: 'Nota sintetica R06.b.1' })]) {
    const r = await step(body()); rev = r.value.appliedRevision;
  }
  pass('real order/group/line/note commands persisted');
  // Own time: operator A (create + correction) and operator B of the SAME tenant on the same order.
  const ownPath = `${base}/orders/${order}/actual-time/own`, entry = uid(), entryB = uid();
  const created = await record(a, 'own-time create A', ownPath, { commandId: uid(), entryId: entry, workingGroupId: g2, expectedOwnRevision: 0, expectedGroupVersion: 1, workDate: '2024-02-29', durationSeconds: 3671, note: 'Fatto mio <testo>' });
  const corrected = await record(a, 'own-time correction A', `${ownPath}/${entry}/corrections`, { commandId: uid(), expectedOwnRevision: 1, expectedEntryVersion: 1, workDate: '2023-12-31', durationSeconds: 4321, note: 'Corretto', correctionNote: 'Verifica durata' }, [200]);
  assert.equal(corrected.value.entryVersion, 2);
  await record(B.page, 'own-time create B', ownPath, { commandId: uid(), entryId: entryB, workingGroupId: g2, expectedOwnRevision: 0, expectedGroupVersion: 1, workDate: '2025-05-05', durationSeconds: 900, note: 'Tempo di B' }, [201], 'B');
  pass('own-time create/correction/receipts for two operators of one tenant');
  // Material: reserve 2 / release 1 (never picked), second reservation reserve 2 -> pick 1 -> install 0.5.
  const inv = `/api/v1/inventory/orders/${order}/lines/${partLine}`;
  const releasedReservation = uid(), pickedReservation = uid(), release = uid(), pick = uid(), install = uid();
  await record(a, 'reserve 2 (to be partially released)', inv + '/reservations', { id: releasedReservation, warehouseId: ctx.warehouseId, quantity: '2', catalogVersion: 8 });
  await record(a, 'explicit release 1', `${inv}/reservations/${releasedReservation}/releases`, { id: release, quantity: '1' });
  await record(a, 'reserve 2 (to be picked)', inv + '/reservations', { id: pickedReservation, warehouseId: ctx.warehouseId, quantity: '2', catalogVersion: 8 });
  await record(a, 'pick 1', `${inv}/reservations/${pickedReservation}/picks`, { id: pick, quantity: '1' });
  await record(a, 'install 0.5', `${base}/orders/${order}/lines/${partLine}/picks/${pick}/installations`, { id: install, quantity: '0.5' });
  await record(a, 'carcass return 0.5', `${inv}/carcass-returns`, { id: uid(), warehouseId: ctx.warehouseId, quantity: '0.5', description: 'Carcassa sintetica' });
  pass('reservation/release/pick/install/carcass return through existing authorized commands');
  // Commercial snapshot: technical closure -> internal Billing -> confirmation -> balanced Accounting journal.
  const closure = await record(a, 'technical closure', `${base}/orders/${order}/technical-closure`, { id: uid(), expectedRevision: (await editor(a, order)).value.revision });
  const invoiceId = uid();
  const invoice = await record(a, 'billing invoice', '/api/v1/billing/workshop-invoices', { id: invoiceId, orderId: order, documentTypeId: data.invoiceTypeId, configurationVersion: 6, documentDate: '2026-10-24', currency: 'EUR', reference: 'SYNTHETIC-R06B1' });
  await record(a, 'billing confirmation', `/api/v1/billing/workshop-invoices/${invoiceId}/confirmation`, { id: uid(), configurationVersion: 6 });
  const journal = await record(a, 'accounting journal', '/api/v1/accounting/invoice-journal-entries', { id: uid(), invoiceId, chartVersion: 5 });
  assert.equal(journal.value.balanced, true);
  pass('technical closure, Billing snapshot, confirmation and balanced Accounting journal');
  // Foreign tenant: its own order, own-time and an external administrative request.
  const fo = uid(), fg = uid(), fl = uid();
  assert.equal((await post(F.page, `${base}/orders`, { id: fo, legalEntityId: fctx.legalEntityId, siteId: fctx.siteId, documentTypeId: fdata.documentTypeId, configurationVersion: 7, payerId: fdata.payerId, vehicleId: fdata.vehicleId })).status, 201);
  assert.equal((await cmd(F.page, fo, envelope('AddGroup', 0, { groupId: fg, title: 'Tempi esterni' }))).status, 201);
  assert.equal((await cmd(F.page, fo, envelope('AddCommercialLine', 1, { lineId: fl, groupId: fg, catalogItemId: fdata.serviceId, catalogVersion: 8, quantity: '1.123456', unitPrice: '42.123456', discountPercent: '5' }))).status, 201);
  const fEntry = uid();
  await record(F.page, 'own-time foreign tenant', `${base}/orders/${fo}/actual-time/own`, { commandId: uid(), entryId: fEntry, workingGroupId: fg, expectedOwnRevision: 0, expectedGroupVersion: 1, workDate: '2024-02-29', durationSeconds: 60, note: 'Esterno' }, [201], 'F');
  await record(F.page, 'foreign technical closure', `${base}/orders/${fo}/technical-closure`, { id: uid(), expectedRevision: (await editor(F.page, fo)).value.revision }, [201], 'F');
  const admin = await record(F.page, 'external administrative request', `${base}/orders/${fo}/administrative-requests`, { id: uid(), expectedRevision: (await editor(F.page, fo)).value.revision }, [201], 'F', true);
  pass('foreign tenant order, own time and external administrative request');
  // Pre-dump marker: an ordinary existing command (new order carrying a note). Its id/text live OUTSIDE cluster A.
  const markerOrder = await createOrder(a), mg = uid();
  assert.equal((await cmd(a, markerOrder, envelope('AddGroup', 0, { groupId: mg, title: 'Marker' }))).status, 201);
  assert.equal((await cmd(a, markerOrder, envelope('AddNote', 1, { lineId: uid(), groupId: mg, description: 'R06B1 PRE-DUMP MARKER' }))).status, 201);
  pass('pre-dump marker committed');
  // A replay returns the CURRENT representation (e.g. the invoice is Confirmed after confirmation), so the
  // expectation is the replay value taken once all seed commands are complete, not the first response.
  const actors = { A: a, B: B.page, F: F.page };
  for (const r of receipts) {
    const replay = await post(actors[r.actor], r.path, r.body);
    assert.equal(replay.status, r.replayStatus, 'final replay ' + r.name);
    r.finalValue = r.volatile ? { id: replay.value.id } : replay.value;
  }
  const ids = { order, g1, g2, serviceLine, partLine, entry, entryB, releasedReservation, pickedReservation, release, pick, install, invoiceId, foreignOrder: fo, markerOrder };
  const baseline = await projection(a, B.page, F.page, ids);
  fs.writeFileSync('/run/control/seed.json', JSON.stringify({ checks, ids, receipts, baseline, adminRequestId: admin.value && admin.value.id, tenantId: ctx.tenantId, foreignTenantId: fctx.tenantId }));
}

async function marker2(browser) {
  await ready(browser);
  const A = await login(browser, 0);
  const order = await createOrder(A.page), g = uid();
  assert.equal((await cmd(A.page, order, envelope('AddGroup', 0, { groupId: g, title: 'Marker dopo dump' }))).status, 201);
  assert.equal((await cmd(A.page, order, envelope('AddNote', 1, { lineId: uid(), groupId: g, description: 'R06B1 POST-DUMP MARKER' }))).status, 201);
  fs.writeFileSync('/run/control/marker2.json', JSON.stringify({ order }));
  pass('post-dump marker committed');
}

async function readback(browser) {
  const seeded = JSON.parse(fs.readFileSync('/run/control/expected.json', 'utf8'));
  await ready(browser);
  const started = Date.now();
  const A = await login(browser, 0), B = await login(browser, 5), F = await login(browser, 1);
  const a = A.page, ids = seeded.ids;
  pass('new browser contexts completed OIDC authorization-code/PKCE login through the trusted CA');
  // 1. Semantic HTTP projection must be exactly the pre-dump one.
  const now = await projection(a, B.page, F.page, ids);
  assert.deepEqual(now, seeded.baseline, 'HTTP projection differs from the pre-dump baseline');
  assert(now.markerEditor, 'pre-dump marker order readable');
  pass('authorized HTTP projection identical (editor, own-time, history, material, release history)');
  // 2. Every recorded command replays with the exact original receipt (identical URL/UUID/payload).
  for (const r of seeded.receipts) {
    const who = { A: a, B: B.page, F: F.page }[r.actor];
    const replay = await post(who, r.path, r.body);
    assert.equal(replay.status, r.replayStatus, 'replay status ' + r.name + ' ' + JSON.stringify(replay));
    assert.deepEqual(r.volatile ? { id: replay.value.id } : replay.value, r.finalValue, 'receipt ' + r.name);
  }
  pass('all ' + seeded.receipts.length + ' original receipts replay exactly with no new effect');
  // 3. Ownership isolation inside one tenant and across tenants.
  const ownPath = `${base}/orders/${ids.order}/actual-time/own`;
  assert.deepEqual(now.ownA.entries.map(e => e.entryId), [ids.entry]);
  assert.deepEqual(now.ownB.entries.map(e => e.entryId), [ids.entryB]);
  assert.equal((await json(B.page, `${ownPath}/${ids.entry}/history`)).status, 404, 'other operator of the same tenant cannot read A history');
  assert.equal((await json(a, `${ownPath}/${ids.entryB}/history`)).status, 404, 'A cannot read B history');
  assert.equal((await json(F.page, ownPath)).status, 404, 'foreign tenant denied (list)');
  assert.equal((await json(F.page, `${ownPath}/${ids.entry}/history`)).status, 404, 'foreign tenant denied (history)');
  const correction = seeded.receipts.find(r => r.name === 'own-time correction A');
  assert.equal((await post(B.page, correction.path, correction.body)).status, 404, 'other operator cannot replay/apply A correction');
  assert.equal((await post(F.page, correction.path, correction.body)).status, 404);
  assert.equal((await post(a, `${ownPath}`, seeded.receipts[0].body, null)).status, 400, 'CSRF still required');
  assert.equal((await json(F.page, `${base}/orders/${ids.order}/editor`)).status, 404, 'foreign tenant cannot read the order');
  assert.equal((await json(F.page, `/api/v1/inventory/orders/${ids.order}/lines/${ids.partLine}/reservations/${ids.releasedReservation}/releases`)).status === 200, false, 'foreign tenant cannot read release history');
  const anonymous = await browser.newPage(); await anonymous.goto(origin + '/');
  assert.equal((await json(anonymous, ownPath)).status, 401, 'anonymous denied');
  pass('own-time ownership isolation: same-tenant other operator, foreign tenant, anonymous, CSRF');
  // 4. Release history / immutable material facts survived exactly.
  const hist = now.releaseHistory;
  assert.equal(hist.released, '1'); assert.equal(hist.releases.length, 1); assert.equal(hist.releases[0].id, ids.release);
  assert.equal(now.pickHistory.picks.length, 1); assert.equal(now.installations.installations.length, 1);
  pass('release history, pick and installation facts present');
  fs.writeFileSync('/run/control/readback.json', JSON.stringify({ checks, millis: Date.now() - started }));
}

(async () => {
  assert(['seed', 'marker2', 'readback'].includes(phase), 'unknown R06B1_PHASE');
  const browser = await chromium.launch({ headless: true });
  try { await { seed, marker2, readback }[phase](browser); } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
