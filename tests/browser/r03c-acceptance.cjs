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
  const orders = {}, requests = {}, technical = {};
  try {
    const probe = await browser.newPage(); let ready = false;
    for (let i = 0; i < 40; i++) { try { if ((await probe.goto(origin + '/auth/session')).status() === 200) { ready = true; break; } } catch { } await new Promise(r => setTimeout(r, 500)); } assert(ready);
    const { page } = await login(browser, 0);

    // ---- editor commands versus closure: both serializations, separate SQL connections at pool 4, completion at pool 1.
    const token = await csrf(page);
    async function serialized(order, first, second) {
      if (fixture.poolSize >= 4) await control('hold-order:' + order);
      const one = first(); if (fixture.poolSize >= 4) await control('wait-order:1'); else await one;
      const two = second(); if (fixture.poolSize >= 4) { await control('wait-order:2'); await control('release-order'); }
      return Promise.all([one, two]);
    }
    for (const closureFirst of [true, false]) {
      const race = await simpleOrder(page); orders[closureFirst ? 'raceClosureFirst' : 'raceEditFirst'] = race.order;
      const close = () => post(page, `${base}/orders/${race.order}/technical-closure`, { id: uid(), expectedRevision: 2 }, token);
      const edit = () => cmd(page, race.order, envelope('AddNote', 2, { lineId: uid(), groupId: race.group, description: 'Concorrenza' }), token);
      const values = await serialized(race.order, closureFirst ? close : edit, closureFirst ? edit : close);
      const [closeResult, editResult] = closureFirst ? [values[0], values[1]] : [values[1], values[0]];
      if (closureFirst) { assert.equal(closeResult.status, 201, JSON.stringify(values)); assert.equal(editResult.value.code, 'order_technically_closed'); technical.raceClosureFirst = 2; }
      else { assert.equal(editResult.status, 201); assert.equal(closeResult.status, 409); assert.equal(closeResult.value.code, 'revision_changed'); assert.equal((await state(page, race.order)).value.status, 'Open'); assert.equal((await post(page, `${base}/orders/${race.order}/technical-closure`, { id: uid(), expectedRevision: 3 })).status, 201); technical.raceEditFirst = 3; }
    }
    pass(fixture.poolSize >= 4 ? 'pool4 separate SQL-connection barriers: closure vs editor command both orders, frozen revision' : 'pool1 completion: closure vs editor command both orders, frozen revision');


    // ---- main order: two groups, repeated Service/Part, a Note; persisted revision 7 above the 5 rows.
    const main = await createOrder(page); orders.main = main;
    const [gA, gB] = [uid(), uid()];
    let rev = 0;
    const apply = async (type, fields) => { const r = await cmd(page, main, envelope(type, rev, fields)); assert.equal(r.status, 201, JSON.stringify(r)); rev = r.value.appliedRevision; };
    await apply('AddGroup', { groupId: gA, title: 'Freni' }); await apply('AddGroup', { groupId: gB, title: 'Tagliando' });
    for (const [kind, group, quantity, price] of [['serviceId', gA, '1.5', '40'], ['serviceId', gB, '2', '12.345678'], ['partId', gA, '2', '20.1'], ['partId', gB, '1', '7.77']])
      await apply('AddCommercialLine', { lineId: uid(), groupId: group, catalogItemId: data[kind], catalogVersion: 8, quantity, unitPrice: price, discountPercent: '5' });
    await apply('AddNote', { lineId: uid(), groupId: gA, description: 'Nota esclusa dallo snapshot' });
    assert.equal(rev, 7); assert.notEqual(gA, main);
    const before = (await editor(page, main)).value;
    assert.equal(before.summary.revision, 7); assert.equal(before.summary.lines.length, 4); assert.equal(before.rows.length, 5);

    // ---- technical closure through the real runtime UI with the fresh server revision, keyboard activation and focus.
    await control('simulator:unavailable');
    const panel = await openPanel(page, main, 7);
    await panel.getByText('Requisito carcassa: Clear', { exact: true }).waitFor();
    await panel.getByText(PROVIDER, { exact: true }).waitFor();
    assert.equal(await panel.getByText('Requisito informativo: non prova che tutta la commessa sia chiudibile.').count(), 1);
    assert.equal((await actions(page, main)).value.commercialRevision, 7);
    assert.equal(await panel.getByRole('button', { name: 'Richiedi registrazione amministrativa' }).count(), 0, 'no request before the technical fact');
    const noCsrf = await post(page, `${base}/orders/${main}/technical-closure`, { id: uid(), expectedRevision: 7 }, null);
    assert.equal(noCsrf.status, 400, 'CSRF is required'); assert.equal((await state(page, main)).value.status, 'Open');
    const closeButton = panel.getByRole('button', { name: 'Chiudi tecnicamente' });
    await closeButton.focus(); await page.keyboard.press('Enter');
    await status(panel).filter({ hasText: 'Chiusa tecnicamente alla revisione 7; stato riletto dal server.' }).waitFor();
    assert.equal(await page.evaluate(() => document.activeElement && document.activeElement.id), 'closure-status', 'status receives keyboard focus after a command');
    assert.equal((await editor(page, main)).value.capabilities.closed, true);
    assert.equal((await cmd(page, main, envelope('AddNote', 7, { lineId: uid(), groupId: gA, description: 'dopo chiusura' }))).value.code, 'order_technically_closed');
    technical.main = 7;
    const closedState = (await state(page, main)).value; assert.equal(closedState.status, 'TechnicallyClosed'); assert.equal(closedState.request, null);
    pass('real UI technical closure with fresh revision 7, keyboard activation, focus and editor read-only; no automatic request');

    // ---- administrative request while the simulator is down: waiting, never confirmed; lost response retried byte-identically.
    const lostRequest = await lostResponse(page, '**/administrative-requests', 'request');
    await panel.getByRole('button', { name: 'Richiedi registrazione amministrativa' }).click();
    await lostRequest.dropped;
    await status(panel).filter({ hasText: 'Esito incerto: riprova solo il comando identico.' }).waitFor();
    await panel.getByRole('button', { name: 'Riprova comando identico' }).click();
    await status(panel).filter({ hasText: 'Richiesta amministrativa registrata sullo snapshot della revisione 7' }).waitFor();
    await lostRequest.finish();
    requests.main = JSON.parse(lostRequest.bodies[0][1]).id;
    assert.equal(JSON.parse(lostRequest.bodies[0][1]).expectedRevision, 7);
    await panel.getByText(/^Snapshot richiesta: revisione 7 · 4 righe · 2 lavorazioni$/).waitFor();
    const pinned = (await state(page, main)).value.request;
    const byId = summary => ({ ...summary, lines: [...summary.lines].sort((x, y) => x.id.localeCompare(y.id)) });
    assert.equal(pinned.id, requests.main); assert.deepEqual(byId(pinned.summary), byId(before.summary), 'request snapshot equals the editor values frozen at closure');
    assert.equal(pinned.destinationVersion, 14); assert.equal(pinned.destination, 'External');
    const waiting = await panel.getByText(/Esito non verificato|In coda|Nuovo tentativo|Tentativi automatici esauriti/).first().textContent();
    assert.equal(await panel.getByText(/Confermata/).count(), 0, 'simulator down is waiting, never confirmed: ' + waiting);
    assert.equal((await post(page, `${base}/orders/${main}/administrative-requests`, { id: uid(), expectedRevision: 7 })).value.code, 'already_requested');
    pass('request queued while simulator down: waiting not confirmed, frozen closure revision, pinned multigroup snapshot, byte-identical lost-response retry, one request');

    // ---- automatic attempts exhausted -> explicit verification (never a forced confirmation); Received is non-conclusive.
    await panel.getByText('Tentativi automatici esauriti: serve verifica e ripresa.', { exact: true }).waitFor({ timeout: 90000 });
    const exhausted = (await actions(page, main)).value;
    assert.equal(exhausted.mayRequestReconciliation, true); assert.equal(exhausted.canCompleteAdministrative, false);
    assert.equal(await panel.getByRole('button', { name: /forza|conferma ricevuta/i }).count(), 0);
    await control('simulator:receive');
    const reconcileBodies = [];
    await page.route('**/reconciliation', route => { if (route.request().method() === 'POST') reconcileBodies.push([route.request().url(), route.request().postData()]); return route.continue(); });
    await panel.getByRole('button', { name: 'Verifica e riprendi richiesta' }).click();
    await panel.getByText('Ricevuta dal simulatore: solo acquisizione, non conferma di business.', { exact: true }).waitFor({ timeout: 60000 });
    await page.unroute('**/reconciliation');
    assert.equal(reconcileBodies.length, 1);
    const replay = await json(page, reconcileBodies[0][0], { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': await csrf(page) }, body: reconcileBodies[0][1] });
    assert.equal(replay.status, 200); assert.equal(replay.value.replayed, true);
    assert.equal(await panel.getByRole('button', { name: 'Chiudi amministrativamente' }).count(), 0, 'Received never offers administrative closure');
    const early = await post(page, `${base}/orders/${main}/administrative-closure`, { id: uid() });
    assert.equal(early.status, 409); assert.equal(early.value.code, 'external_confirmation_required');
    assert.equal(await panel.getByText(/Confermata|AMM-SIM/).count(), 0, 'no invented acknowledgement or reference');
    pass('needs-reconciliation -> verified recovery, replay 200 without a second receipt, Received is non-conclusive and cannot close administratively');

    // ---- Completed with a stable simulator reference -> Workshop-confirmed -> administrative closure (lost response retried).
    await control('simulator-complete');
    const confirmedText = await panel.getByText(/^Confermata dal simulatore · riferimento AMM-SIM-\d{6} \(nessuna fattura fiscale, nessun incasso\)\.$/).textContent({ timeout: 60000 });
    const reference = /riferimento (AMM-SIM-\d{6})/.exec(confirmedText)[1];
    const lostClose = await lostResponse(page, '**/administrative-closure', 'administrative closure');
    await panel.getByRole('button', { name: 'Chiudi amministrativamente' }).click();
    await lostClose.dropped;
    await status(panel).filter({ hasText: 'Esito incerto: riprova solo il comando identico.' }).waitFor();
    await panel.getByRole('button', { name: 'Riprova comando identico' }).click();
    await status(panel).filter({ hasText: 'Chiusa amministrativamente · riferimento ' + reference + '; stato riletto dal server.' }).waitFor();
    await lostClose.finish();
    assert.deepEqual(JSON.parse(lostClose.bodies[0][1]), { id: JSON.parse(lostClose.bodies[0][1]).id });
    const done = (await state(page, main)).value; assert.equal(done.status, 'AdministrativelyClosed'); assert.equal(done.administrativeClosure.externalReference, reference);
    assert.equal(done.request.status, 'Confirmed'); assert.equal(done.request.externalReference, reference);
    await panel.getByText('Chiusa amministrativamente · riferimento ' + reference + ' (contratto simulato; nessun incasso né riconsegna).').waitFor();
    assert.equal((await post(page, `${base}/orders/${main}/administrative-closure`, { id: uid() })).value.code, 'already_closed');
    technical.main = 7;
    pass('simulator Completed -> Workshop Confirmed with stable reference -> UI administrative closure; truthful label; replay protected');

    // ---- rejected path.
    await control('simulator:reject');
    const rej = await simpleOrder(page); orders.rejected = rej.order;
    assert.equal((await post(page, `${base}/orders/${rej.order}/technical-closure`, { id: uid(), expectedRevision: 2 })).status, 201); technical.rejected = 2;
    const rejPanel = await openPanel(page, rej.order, 2);
    await rejPanel.getByRole('button', { name: 'Richiedi registrazione amministrativa' }).click();
    await rejPanel.getByText('Rifiutata dal simulatore · codice synthetic_refusal. Nessun nuovo invio né conferma forzata.', { exact: true }).waitFor({ timeout: 60000 });
    requests.rejected = (await state(page, rej.order)).value.request.id;
    const rejActions = (await actions(page, rej.order)).value;
    assert.deepEqual([rejActions.canCompleteAdministrative, rejActions.mayRequestReconciliation, rejActions.canRequestAdministrative], [false, false, false]);
    assert.equal(await rejPanel.getByRole('button', { name: 'Chiudi amministrativamente' }).count(), 0);
    assert.equal((await post(page, `${base}/orders/${rej.order}/administrative-closure`, { id: uid() })).status, 409);
    assert.equal((await post(page, `${base}/orders/${rej.order}/administrative-requests/${requests.rejected}/reconciliation`, { id: uid() })).status, 409);
    pass('rejected path: final business refusal with code, no closure, no recovery override');

    // ---- lost response at the simulator: stable id, status lookup, one remote effect.
    await control('simulator:lost-response');
    const lost = await simpleOrder(page); orders.lost = lost.order;
    assert.equal((await post(page, `${base}/orders/${lost.order}/technical-closure`, { id: uid(), expectedRevision: 2 })).status, 201); technical.lost = 2;
    requests.lost = uid();
    assert.equal((await post(page, `${base}/orders/${lost.order}/administrative-requests`, { id: requests.lost, expectedRevision: 2 })).status, 201);
    await until(async () => (await state(page, lost.order)).value, s => s.status === 'AdministrativelyConfirmed', 'lost-response request confirmed through status lookup');
    await control('simulator:complete');
    pass('simulator committed but response lost: Uncertain persisted, status lookup, confirmed once with the same request id');

    // ---- carcass requirement: Blocked is a requirement only; the POST stays the authority; accepted receipt clears it.
    const blocked = await createOrder(page); orders.blocked = blocked;
    const bg = uid(), bl = uid();
    assert.equal((await cmd(page, blocked, envelope('AddGroup', 0, { groupId: bg, title: 'Sostituzione' }))).status, 201);
    assert.equal((await cmd(page, blocked, envelope('AddCommercialLine', 1, { lineId: bl, groupId: bg, catalogItemId: data.partId, catalogVersion: 8, quantity: '2', unitPrice: '30', discountPercent: '0' }))).status, 201);
    const reservation = { id: uid(), warehouseId: ctx.warehouseId, catalogVersion: 8, quantity: '2' }, pick = uid();
    assert.equal((await post(page, `/api/v1/inventory/orders/${blocked}/lines/${bl}/reservations`, reservation)).status, 201);
    assert.equal((await post(page, `/api/v1/inventory/orders/${blocked}/lines/${bl}/reservations/${reservation.id}/picks`, { id: pick, quantity: '2' })).status, 201);
    const installed = await post(page, `${base}/orders/${blocked}/lines/${bl}/picks/${pick}/installations`, { id: uid(), quantity: '2' });
    assert.equal(installed.status, 201, JSON.stringify(installed));
    const blockedPanel = await openPanel(page, blocked, 2);
    await blockedPanel.getByText('Requisito carcassa: Blocked', { exact: true }).waitFor();
    await blockedPanel.getByText('Da rientrare 2 su 2', { exact: true }).waitFor();
    assert.equal(await blockedPanel.getByRole('button', { name: 'Chiudi tecnicamente' }).isDisabled(), true);
    const refused = await post(page, `${base}/orders/${blocked}/technical-closure`, { id: uid(), expectedRevision: 2 });
    assert.equal(refused.status, 409); assert.equal(refused.value.code, 'technical_requirements_pending');
    assert.equal((await state(page, blocked)).value.status, 'Open');
    assert.equal((await post(page, `/api/v1/inventory/orders/${blocked}/lines/${bl}/carcass-returns`, { id: uid(), warehouseId: ctx.warehouseId, quantity: '2', description: 'Sintetico' })).status, 201);
    const clearGate = await json(page, `${base}/orders/${blocked}/technical-closure-gate`);
    assert.equal(clearGate.value.status, 'Clear', 'accepted carcass receipt clears the server requirement: ' + JSON.stringify(clearGate));
    await blockedPanel.getByRole('button', { name: 'Rileggi stato' }).click();
    await blockedPanel.getByText('Requisito carcassa: Clear', { exact: true }).waitFor();
    await blockedPanel.getByRole('button', { name: 'Chiudi tecnicamente' }).click();
    await status(blockedPanel).filter({ hasText: 'Chiusa tecnicamente alla revisione 2; stato riletto dal server.' }).waitFor();
    technical.blocked = 2;
    assert.equal((await actions(page, blocked)).value.technicalClosure.revision, 2);
    pass('carcass gate Blocked -> POST 409 without a fact -> accepted carcass receipt -> Clear -> real UI closure; no extra closure condition');

    // ---- exact grant matrix on one technically closed order (no request is ever created here).
    const matrix = await simpleOrder(page); orders.matrix = matrix.order;
    assert.equal((await post(page, `${base}/orders/${matrix.order}/technical-closure`, { id: uid(), expectedRevision: 2 })).status, 201); technical.matrix = 2;
    const user = await login(browser, 5), p5 = user.page, mpath = `${base}/orders/${matrix.order}`;
    assert.equal((await json(user.page, mpath + '/closure-actions')).status, 200);
    const probe5 = async grants => { await control('permissions:M:' + grants); return (await actions(p5, matrix.order)).value; };
    let a = await probe5('workshop.administrative-requests.create,workshop.administrative-requests.reconcile,workshop.orders.complete-administrative');
    assert.deepEqual([a.canReadAdministrativeState, a.canRequestAdministrative, a.mayRequestReconciliation, a.canCompleteAdministrative], [false, false, false, false], 'write without read');
    assert(a.actionReasons.some(r => r.action === 'requestAdministrative' && r.code === 'administrative_read_required'));
    assert.equal(JSON.stringify(a).includes('already_requested'), false);
    assert.equal((await json(p5, mpath + '/closure-state')).status, 404); assert.equal((await json(p5, mpath + '/administrative-requests')).status, 404);
    assert.equal((await post(p5, mpath + '/administrative-closure', { id: uid() })).value.code, 'external_confirmation_required', 'the backend command keeps its own rules, advice never replaces them');
    a = await probe5('workshop.administrative-requests.read');
    assert.deepEqual([a.canReadAdministrativeState, a.canRequestAdministrative, a.mayRequestReconciliation, a.canCompleteAdministrative], [true, false, false, false], 'read without any write');
    for (const action of ['requestAdministrative', 'reconcile', 'completeAdministrative']) assert(a.actionReasons.some(r => r.action === action && r.code === 'not_authorized'), action);
    assert.equal((await json(p5, mpath + '/closure-state')).status, 200);
    assert.equal((await post(p5, mpath + '/administrative-requests', { id: uid(), expectedRevision: 2 })).status, 403);
    assert.equal((await post(p5, mpath + '/administrative-closure', { id: uid() })).status, 403);
    assert.equal((await post(p5, mpath + '/technical-closure', { id: uid(), expectedRevision: 2 })).status, 403);
    a = await probe5('workshop.administrative-requests.read,workshop.administrative-requests.create');
    assert.equal(a.canRequestAdministrative, true); assert.equal(a.canCompleteAdministrative, false); assert.equal(a.mayRequestReconciliation, false);
    a = await probe5('');
    assert.deepEqual([a.canReadAdministrativeState, a.canCompleteTechnical, a.canRequestAdministrative], [false, false, false], 'orders.read only');
    const foreign = await login(browser, 1);
    assert.equal((await actions(foreign.page, matrix.order)).status, 404, 'foreign tenant');
    const anonymous = await (await browser.newContext()).newPage(); await anonymous.goto(origin + '/auth/session');
    assert.equal((await json(anonymous, mpath + '/closure-actions')).status, 401);
    // Technical-only operator closes through the real UI: administrative state is explicitly unauthorized, not "no request".
    const only = await simpleOrder(page); orders.technicalOnly = only.order;
    await control('permissions:T:workshop.orders.complete-technical');
    const onlyPanel = await openPanel(p5, only.order, 2);
    await onlyPanel.getByText('Stato amministrativo non autorizzato.', { exact: true }).waitFor();
    assert.equal(await onlyPanel.getByText('Richiesta amministrativa non registrata.').count(), 0);
    await onlyPanel.getByRole('button', { name: 'Chiudi tecnicamente' }).click();
    await status(onlyPanel).filter({ hasText: 'Chiusa tecnicamente alla revisione 2; stato riletto dal server.' }).waitFor();
    technical.technicalOnly = 2;
    pass('grant matrix: write-without-read, read-without-write, orders.read-only, foreign tenant, anonymous 401, technical-only real UI');

    // ---- capability off keeps authorized history readable and stops new use.
    const off = await simpleOrder(page); orders.capabilityOff = off.order;
    assert.equal((await post(page, `${base}/orders/${off.order}/technical-closure`, { id: uid(), expectedRevision: 2 })).status, 201); technical.capabilityOff = 2;
    await control('capability:external-administration:false');
    const offActions = (await actions(page, off.order)).value;
    assert.equal(offActions.canReadAdministrativeState, true); assert.equal(offActions.canRequestAdministrative, false);
    assert(offActions.actionReasons.some(r => r.action === 'requestAdministrative' && r.code === 'capability_disabled'));
    assert.equal((await state(page, main)).status, 200); assert.equal((await state(page, main)).value.status, 'AdministrativelyClosed');
    assert.equal((await post(page, `${base}/orders/${off.order}/administrative-requests`, { id: uid(), expectedRevision: 2 })).status, 403);
    await control('capability:external-administration:true');
    pass('external capability off: history readable, new request denied with a named reason');

    // ---- internal destination preserved: Billing claim and balanced Accounting, never an external request.
    await control('destination:Internal:15');
    const internal = await simpleOrder(page); orders.internal = internal.order;
    assert.equal((await post(page, `${base}/orders/${internal.order}/technical-closure`, { id: uid(), expectedRevision: 2 })).status, 201); technical.internal = 2;
    const internalActions = (await actions(page, internal.order)).value;
    assert(internalActions.actionReasons.some(r => r.action === 'requestAdministrative' && r.code === 'administrative_destination_missing'));
    assert.equal((await post(page, `${base}/orders/${internal.order}/administrative-requests`, { id: uid(), expectedRevision: 2 })).value.code, 'administrative_destination_missing');
    const summary = (await editor(page, internal.order)).value.summary;
    const invoiceId = uid(), invoiceBody = { id: invoiceId, orderId: internal.order, documentTypeId: data.invoiceTypeId, configurationVersion: 6, documentDate: '2026-10-24', currency: 'EUR', reference: 'SYNTHETIC-R03C' };
    const invoice = await post(page, '/api/v1/billing/workshop-invoices', invoiceBody); assert.equal(invoice.status, 201, JSON.stringify(invoice)); assert.equal(invoice.value.sourceRevision, 2); assert.deepEqual(byIdOf(invoice.value.summary), byIdOf(summary));
    const confirmation = { id: uid(), configurationVersion: 6 }; assert.equal((await post(page, `/api/v1/billing/workshop-invoices/${invoiceId}/confirmation`, confirmation)).status, 201);
    const journalId = uid(), journalBody = { id: journalId, invoiceId, chartVersion: 5 };
    const journal = await post(page, '/api/v1/accounting/invoice-journal-entries', journalBody); assert.equal(journal.status, 201); assert.equal(journal.value.balanced, true);
    assert.deepEqual((await post(page, '/api/v1/accounting/invoice-journal-entries', journalBody)).value, journal.value);
    const lateRequest = await post(page, `${base}/orders/${internal.order}/administrative-requests`, { id: uid(), expectedRevision: 2 });
    assert.equal(lateRequest.status, 409);
    pass('internal destination: closure -> Billing confirmation -> balanced idempotent Accounting; external request refused');

    // ---- session loss in the real UI clears the panel.
    const revoked = await login(browser, 0);
    const revokedPanel = await openPanel(revoked.page, main, 7);
    await revokedPanel.getByText('Requisito carcassa: Clear', { exact: true }).waitFor();
    await revoked.context.clearCookies();
    await revokedPanel.getByRole('button', { name: 'Rileggi stato' }).click();
    await revoked.page.getByText('Sessione terminata. Accedi nuovamente.', { exact: true }).first().waitFor();
    assert.equal(await revoked.page.getByText('Requisito carcassa: Clear').count(), 0);
    assert.equal(await revoked.page.getByText(reference).count(), 0, 'stable reference removed on session loss');
    pass('401 clears the closure panel data in the real browser');

    fs.writeFileSync('/run/control/result.json', JSON.stringify({ checks, orders, requests, technical, reference, mainSnapshot: byIdOf(before.summary), journalId, invoiceId }));
  } catch (error) {
    // Diagnostics only: visible text of every open synthetic page, never credentials.
    let n = 0;
    for (const context of browser.contexts()) for (const page of context.pages()) {
      try { fs.writeFileSync('/run/control/failure-' + (++n) + '.txt', (await page.locator('body').innerText({ timeout: 3000 })).slice(0, 6000)); await page.screenshot({ path: '/run/control/failure-' + n + '.png' }); } catch { }
    }
    throw error;
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
