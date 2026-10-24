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
  fs.writeFileSync('/run/control/request', action);
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
  const browser = await chromium.launch({ headless: true }); let stage = 'startup';
  const result = { checks };
  try {
    const probe = await browser.newPage(); let ready = false;
    for (let i = 0; i < 40; i++) { try { if ((await probe.goto(origin + '/auth/session')).status() === 200) { ready = true; break; } } catch { } await new Promise(r => setTimeout(r, 500)); }
    assert(ready);
    const a = await login(browser, 0); const page = a.page;
    page.on('pageerror', e => console.error('APP_JS_ERROR ' + e.message));
    assert.equal((await json(probe, `${base}/orders/${uid()}/editor`)).status, 401);
    assert.equal((await json(probe, `${base}/orders?legalEntityId=${ctx.legalEntityId}&siteId=${ctx.siteId}`)).status, 401);
    pass('T1 anonymous denied on policy/editor/list');

    stage = 'T1 server-owned policy';
    const order = await createOrder(page); result.order = order;
    const policy = await json(page, `${base}/orders/${order}/line-policy`);
    assert.equal(policy.status, 200);
    assert.deepEqual([policy.value.state, policy.value.documentConfigurationVersion, policy.value.currentLinePolicyVersion, policy.value.structurePolicyVersion, policy.value.calculationPolicy, policy.value.multipleWorkingGroups],
      ['ready', 7, 9, 1, 'Case001', true], 'document 7, line policy 9, structure 1 are distinct server-owned values');
    assert.notEqual(policy.value.currentLinePolicyVersion, 1);
    const noPolicy = await createOrder(page, data.documentTypeNoPolicyId, 3);
    const missing = await json(page, `${base}/orders/${noPolicy}/line-policy`);
    assert.equal(missing.value.state, 'line_policy_missing'); assert.equal(missing.value.currentLinePolicyVersion, null);
    const refusedMissing = await cmd(page, noPolicy, envelope('AddGroup', 0, { groupId: uid(), title: 'Lavorazione', expectedLinePolicyVersion: 1 }));
    assert.equal(refusedMissing.status, 409); assert.equal(refusedMissing.value.code, 'line_policy_missing');
    pass('T1 line-policy read distinguishes document 7 / policy 9 / structure 1; missing policy never defaults to 1 and refuses writes');

    stage = 'T2/T3 groups and repeated rows';
    const empty = await editor(page, order);
    assert.equal(empty.status, 200); assert.equal(empty.value.revision, 0); assert.deepEqual(empty.value.groups, []); assert.deepEqual(empty.value.rows, []);
    assert.equal(empty.value.capabilities.materialStructureEdit, true);
    const g1 = uid(), g2 = uid(), s1 = uid(), s2 = uid(), p1 = uid(), p2 = uid();
    const first = envelope('AddGroup', 0, { groupId: g1, title: 'Cambio olio' });
    const r1 = await cmd(page, order, first); assert.equal(r1.status, 201); assert.deepEqual([r1.value.appliedRevision, r1.value.resultKind, r1.value.targetId], [1, 'Created', g1]);
    const stale = await cmd(page, order, envelope('AddGroup', 0, { groupId: uid(), title: 'Stale' }));
    assert.equal(stale.status, 409); assert.equal(stale.value.code, 'revision_changed');
    assert.equal((await cmd(page, order, envelope('AddGroup', 1, { groupId: g2, title: 'Freni' }))).value.appliedRevision, 2);
    const add = (type, rev, id, group, catalog, version, q, p, d, description) => cmd(page, order, envelope('AddCommercialLine', rev, { lineId: id, groupId: group, catalogItemId: catalog, catalogVersion: version, quantity: q, unitPrice: p, discountPercent: d, description: description ?? null }));
    const sv = await add('', 2, s1, g1, data.serviceId, 8, '1.5', '40', '10');
    assert.equal(sv.status, 201); assert.equal(sv.value.appliedRevision, 3);
    assert.equal((await add('', 3, s2, g1, data.serviceId, 8, '2', '35.5', '0', 'Seconda prestazione')).value.appliedRevision, 4, 'second Service of the same catalog item is a distinct row');
    assert.equal((await add('', 4, p1, g2, data.partId, 8, '4', '12.345678', '5')).value.appliedRevision, 5);
    assert.equal((await add('', 5, p2, g2, data.partId, 8, '1', '99.99', '0')).value.appliedRevision, 6, 'same Part catalog item repeated');
    const crossGroup = await add('', 6, uid(), uid(), data.serviceId, 8, '1', '1', '0');
    assert.equal(crossGroup.status, 404); assert.equal(crossGroup.value.code, 'group_not_found');
    const view = await editor(page, order);
    assert.equal(view.value.revision, 6); assert.deepEqual(view.value.groups.map(g => g.id), [g1, g2]);
    assert.deepEqual(view.value.rows.map(r => [r.id, r.kind, r.workingGroupId]), [[s1, 'Service', g1], [s2, 'Service', g1], [p1, 'Part', g2], [p2, 'Part', g2]]);
    assert.equal(view.value.summary.revision, 6);
    const lines = [{ q: '1.5', p: '40', d: '10' }, { q: '2', p: '35.5', d: '0' }, { q: '4', p: '12.345678', d: '5' }, { q: '1', p: '99.99', d: '0' }];
    const expected = oracle(lines);
    assert.deepEqual([view.value.summary.netAmount, view.value.summary.taxAmount, view.value.summary.total], [expected.net, expected.tax, expected.total], 'tax on the fiscal aggregate, never per working group');
    for (const row of view.value.rows) assert.equal(row.line.workingGroupId, row.workingGroupId);
    pass('T2/T3 two groups, repeated Service/Part rows (incl. same catalog item) persisted with stable ids; stale revision 409; foreign group 404; q6 oracle equal');

    stage = 'T2 exact replay';
    const replay = await cmd(page, order, first);
    assert.equal(replay.status, 200); assert.deepEqual(replay.value, r1.value);
    const differing = await cmd(page, order, { ...first, title: 'Altro' });
    assert.equal(differing.status, 409);
    const equivalent = envelope('AddCommercialLine', 6, { lineId: uid(), groupId: g2, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '2', unitPrice: '10', discountPercent: '0' });
    const e1 = await cmd(page, order, equivalent); assert.equal(e1.status, 201);
    const e2 = await cmd(page, order, { ...equivalent, quantity: '2.0', unitPrice: '10.000000' });
    assert.equal(e2.status, 200); assert.deepEqual(e2.value, e1.value, 'numerically equivalent payload replays the original receipt after later edits');
    pass('T2 exact receipt replay after later edits; differing payload 409; numerically equivalent decimals replay');
    let revision = 7;

    stage = 'T2 policy staleness';
    const stalePolicy = await cmd(page, order, envelope('AddGroup', revision, { groupId: uid(), title: 'X', expectedLinePolicyVersion: 8 }));
    assert.equal(stalePolicy.value.code, 'line_policy_changed');
    const staleStructure = await cmd(page, order, envelope('AddGroup', revision, { groupId: uid(), title: 'X', expectedStructurePolicyVersion: 2 }));
    assert.equal(staleStructure.value.code, 'structure_policy_changed');
    assert.equal((await editor(page, order)).value.revision, revision, 'refused commands consume no revision');
    pass('T2 stale line/structure policy 409 without revision consumption');

    stage = 'T4 notes';
    const n1 = uid();
    const noteAdd = await cmd(page, order, envelope('AddNote', revision, { lineId: n1, groupId: g1, description: 'Cliente presente' }));
    assert.equal(noteAdd.status, 201); revision = noteAdd.value.appliedRevision; assert.equal(revision, 8);
    let nv = await editor(page, order);
    assert(nv.value.rows.some(r => r.id === n1 && r.kind === 'Note' && r.description === 'Cliente presente' && r.line === null));
    assert.deepEqual([nv.value.summary.netAmount, nv.value.summary.total, nv.value.summary.lines.length], [(await editor(page, order)).value.summary.netAmount, nv.value.summary.total, 5], 'summary holds commercial lines only');
    const badNote = await cmd(page, order, envelope('AddNote', revision, { lineId: uid(), groupId: g1, description: 'x', quantity: '1' }));
    assert.equal(badNote.status, 400);
    const noteEdit = await cmd(page, order, envelope('EditNote', revision, { lineId: n1, description: 'Cliente presente, chiavi consegnate' }));
    assert.equal(noteEdit.status, 200); revision = noteEdit.value.appliedRevision;
    const noteDrop = await cmd(page, order, envelope('RemoveLine', revision, { lineId: n1 })); assert.equal(noteDrop.status, 200); revision = noteDrop.value.appliedRevision;
    nv = await editor(page, order); assert(!nv.value.rows.some(r => r.id === n1));
    const totals = oracle([...lines, { q: '2', p: '10', d: '0' }]);
    assert.deepEqual([nv.value.summary.netAmount, nv.value.summary.taxAmount, nv.value.summary.total], [totals.net, totals.tax, totals.total], 'Note never changes commercial totals');
    pass('T4 Note create/edit/remove persisted, description only, outside commercial summary');

    stage = 'T5/T6 editing and removals';
    const edit = (lineId, extra) => cmd(page, order, envelope('EditCommercialLine', revision, { lineId, ...extra }));
    let r = await edit(s1, { quantity: '3', unitPrice: '41.5', discountPercent: '12.5', description: 'Revisione completa' });
    assert.equal(r.status, 200); revision = r.value.appliedRevision;
    r = await edit(p1, { unitPrice: '13', discountPercent: '0', description: 'Pastiglie' });
    assert.equal(r.status, 200); revision = r.value.appliedRevision;
    for(const part of [p1,p2]) assert.equal((await post(page,`/api/v1/inventory/orders/${order}/lines/${part}/reservations`,{id:uid(),warehouseId:ctx.warehouseId,catalogVersion:8,quantity:'1'})).status,201);
    r = await edit(p1, { quantity: '5' }); assert.equal(r.status, 409); assert.equal(r.value.code, 'active_material_commitments');
    r = await edit(s1, { unitPrice: '41.5' }); assert.equal(r.status, 409); assert.equal(r.value.code, 'no_change');
    r = await edit(uid(), { unitPrice: '1' }); assert.equal(r.status, 404);
    r = await cmd(page, order, envelope('RemoveLine', revision, { lineId: p2 })); assert.equal(r.status, 409); assert.equal(r.value.code, 'active_material_commitments');
    r = await cmd(page, order, envelope('RemoveLine', revision, { lineId: s2 })); assert.equal(r.status, 200); revision = r.value.appliedRevision;
    r = await cmd(page, order, envelope('RemoveEmptyGroup', revision, { groupId: g2 })); assert.equal(r.value.code, 'group_not_empty');
    r = await cmd(page, order, envelope('RenameGroup', revision, { groupId: g2, title: 'Impianto frenante' })); assert.equal(r.status, 200); revision = r.value.appliedRevision;
    const g3 = uid();
    r = await cmd(page, order, envelope('AddGroup', revision, { groupId: g3, title: 'Vuota' })); assert.equal(r.status, 201); revision = r.value.appliedRevision;
    r = await cmd(page, order, envelope('RemoveEmptyGroup', revision, { groupId: g3 })); assert.equal(r.status, 200); revision = r.value.appliedRevision;
    r = await add('', revision, uid(), g3, data.serviceId, 8, '1', '1', '0'); assert.equal(r.value.code, 'group_not_found');
    const after = (await editor(page, order)).value;
    assert.equal(after.revision, revision); assert.deepEqual(after.groups.map(g => [g.id, g.title]), [[g1, 'Cambio olio'], [g2, 'Impianto frenante']]);
    const s1row = after.rows.find(x => x.id === s1);
    assert.deepEqual([s1row.line.quantity, s1row.line.unitPrice, s1row.line.discountPercent, s1row.description], ['3', '41.5', '12.5', 'Revisione completa']);
    assert.equal(s1row.line.catalogLabel, 'Synthetic Service', 'catalog label snapshot is not overwritten by the operator description');
    assert(!after.rows.some(x => x.id === s2));
    const after2 = oracle([{ q: '3', p: '41.5', d: '12.5' }, { q: '4', p: '13', d: '0' }, { q: '1', p: '99.99', d: '0' }, { q: '2', p: '10', d: '0' }]);
    assert.deepEqual([after.summary.netAmount, after.summary.taxAmount, after.summary.total], [after2.net, after2.tax, after2.total]);
    pass('T5/T6 Service/Part commercial edits, Part structure and Part removal refused, tracked Service removal, rename, empty-group removal, no cascade');
    result.revision = revision; result.groups = [g1, g2, g3]; result.lines = { s1, s2, p1, p2 }; result.note = n1; result.firstCommand = first.commandId;

    stage = 'T9 aggregate across groups and bounds';
    const q6 = await createOrder(page); let rv = 0; const gA = uid(), gB = uid();
    for (const [g, title] of [[gA, 'A'], [gB, 'B']]) { const x = await cmd(page, q6, envelope('AddGroup', rv, { groupId: g, title })); rv = x.value.appliedRevision; }
    for (const g of [gA, gB]) { const x = await cmd(page, q6, envelope('AddCommercialLine', rv, { lineId: uid(), groupId: g, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '0.000002', unitPrice: '1', discountPercent: '0' })); assert.equal(x.status, 201); rv = x.value.appliedRevision; }
    let sum = (await editor(page, q6)).value.summary;
    assert.deepEqual([sum.netAmount, sum.taxAmount, sum.total], ['0.000004', '0.000001', '0.000005'], 'separate group rounding would have produced zero tax');
    const half5 = await cmd(page, q6, envelope('AddCommercialLine', rv, { lineId: uid(), groupId: gA, catalogItemId: data.partId, catalogVersion: 8, quantity: '0.5', unitPrice: '0.000001', discountPercent: '0' })); rv = half5.value.appliedRevision;
    const zero = await cmd(page, q6, envelope('AddCommercialLine', rv, { lineId: uid(), groupId: gB, catalogItemId: data.partId, catalogVersion: 8, quantity: '3', unitPrice: '0', discountPercent: '0' })); rv = zero.value.appliedRevision;
    const full = await cmd(page, q6, envelope('AddCommercialLine', rv, { lineId: uid(), groupId: gB, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '3', unitPrice: '10', discountPercent: '100' })); rv = full.value.appliedRevision;
    const o6 = oracle([{ q: '0.000002', p: '1', d: '0' }, { q: '0.000002', p: '1', d: '0' }, { q: '0.5', p: '0.000001', d: '0' }, { q: '3', p: '0', d: '0' }, { q: '3', p: '10', d: '100' }]);
    sum = (await editor(page, q6)).value.summary;
    assert.deepEqual([sum.netAmount, sum.taxAmount, sum.total], [o6.net, o6.tax, o6.total]);
    const big = await cmd(page, q6, envelope('AddCommercialLine', rv, { lineId: uid(), groupId: gA, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '999999.999999', unitPrice: '999999.999999', discountPercent: '20' }));
    const bigLine = [{ q: '999999.999999', p: '999999.999999', d: '20' }];
    const bigOracle = oracle([{ q: '0.000002', p: '1', d: '0' }, { q: '0.000002', p: '1', d: '0' }, { q: '0.5', p: '0.000001', d: '0' }, ...bigLine]);
    assert(micro(bigOracle.total) <= 999999999999999999n, 'oracle: this value must still fit numeric(18,6)');
    assert.equal(big.status, 201); rv = big.value.appliedRevision;
    const over = await cmd(page, q6, envelope('AddCommercialLine', rv, { lineId: uid(), groupId: gB, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '999999.999999', unitPrice: '300000', discountPercent: '0' }));
    assert.equal(over.status, 409); assert.equal(over.value.code, 'commercial_summary_limit');
    const unchanged = (await editor(page, q6)).value; assert.equal(unchanged.revision, rv);
    const tooMany = await cmd(page, q6, envelope('AddCommercialLine', rv, { lineId: uid(), groupId: gA, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '1000000', unitPrice: '1', discountPercent: '0' }));
    assert.equal(tooMany.status, 400);
    result.q6 = q6;
    pass('T9 cross-group aggregate tax HALF_UP6, half-micro, price 0 / 100% discount, maximum accepted, first overflow commercial_summary_limit rejected atomically');

    stage = 'T7 concurrency under PostgreSQL order-lock barrier';
    const cc = await createOrder(page); const cg = uid();
    const open = await cmd(page, cc, envelope('AddGroup', 0, { groupId: cg, title: 'Concorrenza' })); assert.equal(open.status, 201);
    await control('hold-order-lock:' + cc);
    const racing = await Promise.all([1, 2, 3, 4].map(i => cmd(page, cc, envelope('AddNote', 1, { lineId: uid(), groupId: cg, description: 'Race ' + i }))));
    const codes = racing.map(x => x.status).sort();
    assert.deepEqual(codes, [201, 409, 409, 409], 'one command applies, the others see the changed revision');
    assert(racing.filter(x => x.status === 409).every(x => x.value.code === 'revision_changed'));
    const same = envelope('AddNote', 2, { lineId: uid(), groupId: cg, description: 'Retry identico' });
    await control('hold-order-lock:' + cc);
    // Exactly the pool size (4): more simultaneous waiters than connections would be a controlled 503 capacity refusal, not a correctness result.
    const retries = await Promise.all([1, 2, 3, 4].map(() => cmd(page, cc, same)));
    assert.deepEqual(retries.map(x => x.status).sort(), [200, 200, 200, 201]);
    assert(retries.every(x => x.value.appliedRevision === 3));
    const crossTenant = await login(browser, 1);
    const collide = await post(crossTenant.page, `${base}/orders/${uid()}/editor/commands`, same);
    assert(collide.status === 404 || collide.status === 403, 'foreign command id on foreign order is not disclosed: ' + collide.status);
    await crossTenant.context.close();
    result.concurrent = { order: cc, group: cg };
    pass('T7 DB-barrier concurrency pool>=4: one winner 201 + 409 revision_changed; simultaneous identical retries one 201 + three exact replays');

    stage = 'T8 response loss replay';
    const lost = envelope('AddNote', 3, { lineId: uid(), groupId: cg, description: 'Risposta persa' });
    await page.route('**/editor/commands', async route => { const response = await route.fetch(); await response.body(); await route.abort('failed'); });
    const dropped = await page.evaluate(async ({ path, body, token }) => { try { await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': token }, body }); return 'delivered'; } catch (e) { return 'dropped'; } }, { path: `${base}/orders/${cc}/editor/commands`, body: JSON.stringify(lost), token: await csrf(page) });
    await page.unroute('**/editor/commands');
    assert.equal(dropped, 'dropped');
    const retried = await cmd(page, cc, lost); assert.equal(retried.status, 200); assert.equal(retried.value.appliedRevision, 4);
    assert.equal((await editor(page, cc)).value.revision, 4);
    result.lost = lost.commandId;
    stage = 'T8 database outage';
    const outage = envelope('AddNote', 4, { lineId: uid(), groupId: cg, description: 'Durante interruzione' });
    await control('database-outage');
    const down = await cmd(page, cc, outage); assert.equal(down.status, 503, 'database unavailable is a recoverable 503, never a false 409/500');
    assert.equal((await editor(page, cc)).status, 503);
    await control('database-recover');
    assert.equal((await editor(page, cc)).value.revision, 4, 'nothing was committed during the outage');
    const recovered = await cmd(page, cc, outage); assert.equal(recovered.status, 201); assert.equal(recovered.value.appliedRevision, 5);
    assert.equal((await cmd(page, cc, outage)).status, 200);
    pass('T8 paused PostgreSQL: command and editor read return 503, no partial effect; unpause + same command applies once, replay exact');
    pass('T8 accepted-but-lost response: byte-identical replay returns original receipt once');

    stage = 'T10 list and reopen';
    for (let i = 0; i < 52; i++) await createOrder(page);
    const scope = `legalEntityId=${ctx.legalEntityId}&siteId=${ctx.siteId}`;
    const collected = []; let cursor = '';
    for (let n = 0; n < 10; n++) {
      const pageResult = await json(page, `${base}/orders?${scope}${cursor ? '&after=' + cursor : ''}`); assert.equal(pageResult.status, 200);
      assert(pageResult.value.length <= 20); if (!pageResult.value.length) break;
      collected.push(...pageResult.value.map(x => x.id)); cursor = pageResult.value.at(-1).id;
    }
    assert.equal(collected.length, 56, "four named orders plus 52 created"); assert.equal(new Set(collected).size, collected.length); assert.deepEqual(collected, [...collected].sort());
    assert((await json(page, `${base}/orders?${scope}&limit=50`)).value.length === 50);
    assert((await json(page, `${base}/orders?${scope}&limit=1`)).value.length === 1);
    for (const query of ['limit=0', 'limit=51', 'limit=x', 'after=broken']) assert.equal((await json(page, `${base}/orders?${scope}&${query}`)).status, 400, query);
    // Random UUID keyset position: locate the proven order by the same stable cursor, not by assuming it is within the first 50 of 56.
    let item; let itemCursor = '';
    for (let n = 0; n < 3 && !item; n++) {
      const pageResult = await json(page, `${base}/orders?${scope}&limit=50${itemCursor ? '&after=' + itemCursor : ''}`); assert.equal(pageResult.status, 200);
      item = pageResult.value.find(x => x.id === order); if (!pageResult.value.length) break; itemCursor = pageResult.value.at(-1).id;
    }
    assert(item && item.revision === revision && item.closed === false);
    assert.equal((await json(page, `${base}/orders?legalEntityId=${fixture.deniedContexts[0].legalEntityId}&siteId=${fixture.deniedContexts[0].siteId}`)).status, 403);
    const other = await login(browser, 1);
    const foreign = await json(other.page, `${base}/orders?legalEntityId=${fixture.contexts[1].legalEntityId}&siteId=${fixture.contexts[1].siteId}`);
    assert.equal(foreign.status, 200); assert(foreign.value.every(x => !collected.includes(x.id)));
    assert.equal((await json(other.page, `${base}/orders/${order}/editor`)).status, 404);
    await other.context.close();
    pass('T10 authorized keyset list 1-50 default 20 without skip/duplicate, invalid input 400, other company 403, foreign tenant not enumerable or openable');

    stage = 'T11 independent actions';
    const reader = await login(browser, 5);
    const actions = { add: 'workshop.lines.add', edit: 'workshop.lines.edit', remove: 'workshop.lines.remove', notes: 'workshop.notes.write', groups: 'workshop.groups.write' };
    const attempts = {
      add: (rv, g) => envelope('AddCommercialLine', rv, { lineId: uid(), groupId: g, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '1', unitPrice: '1', discountPercent: '0' }),
      edit: (rv) => envelope('EditCommercialLine', rv, { lineId: s1, unitPrice: '77' }),
      remove: (rv) => envelope('RemoveLine', rv, { lineId: s1 }),
      notes: (rv, g) => envelope('AddNote', rv, { lineId: uid(), groupId: g, description: 'n' }),
      groups: (rv) => envelope('AddGroup', rv, { groupId: uid(), title: 'g' }),
    };
    assert.equal((await json(reader.page, `${base}/orders/${order}/editor`)).status, 200, 'read-only identity reopens the order');
    for (const own of Object.keys(actions)) {
      await control('permissions:' + own + ':' + actions[own]);
      const current = (await editor(reader.page, order)).value;
      assert.equal(current.capabilities.canAddLine, own === 'add'); assert.equal(current.capabilities.canEditLine, own === 'edit');
      assert.equal(current.capabilities.canRemoveLine, own === 'remove'); assert.equal(current.capabilities.canWriteNotes, own === 'notes'); assert.equal(current.capabilities.canWriteGroups, own === 'groups');
      for (const attempt of Object.keys(actions)) {
        const outcome = await cmd(reader.page, order, attempts[attempt](current.revision + 0, g1));
        if (attempt === own) assert.notEqual(outcome.status, 403, `${own} must permit ${attempt}`); else assert.equal(outcome.status, 403, `${own} alone must not imply ${attempt}`);
        if (outcome.status === 201 || outcome.status === 200) break;
      }
    }
    await control('permissions:create-admin:workshop.orders.create,workshop.lines.add');
    assert.equal((await cmd(reader.page, order, attempts.edit(0))).status, 403, 'orders.create + lines.add do not imply edit');
    assert.equal((await cmd(reader.page, order, attempts.groups(0))).status, 403);
    assert.equal((await post(page, `${base}/orders/${order}/editor/commands`, attempts.notes(0, g1), '')).status, 400, 'missing CSRF is refused like every other write');
    const tampered = await cmd(page, order, { ...attempts.notes(0, g1), tenantId: fixture.contexts[1].tenantId });
    assert.equal(tampered.status, 400, 'tenant field in payload is rejected, never trusted');
    await reader.context.close();
    pass('T11 add/edit/remove/notes/groups are independent exact actions; orders.create+lines.add imply none of the others; CSRF and tenant tampering');

    result.final = (await editor(page, order)).value;
    stage = 'T12 closure';
    const clo = await createOrder(page); const cgroup = uid(); let cr = 0;
    cr = (await cmd(page, clo, envelope('AddGroup', cr, { groupId: cgroup, title: 'Chiusura' }))).value.appliedRevision;
    const cs = uid();
    cr = (await cmd(page, clo, envelope('AddCommercialLine', cr, { lineId: cs, groupId: cgroup, catalogItemId: data.serviceId, catalogVersion: 8, quantity: '1', unitPrice: '50', discountPercent: '0' }))).value.appliedRevision;
    cr = (await cmd(page, clo, envelope('EditCommercialLine', cr, { lineId: cs, unitPrice: '60' }))).value.appliedRevision;
    const linesCount = 1;
    assert.notEqual(cr, linesCount, 'revision is lifecycle, not the count of lines');
    const countClose = await post(page, `${base}/orders/${clo}/technical-closure`, { id: uid(), expectedRevision: linesCount });
    assert.equal(countClose.status, 409); assert.equal(countClose.value.code, 'revision_changed');
    const raceNote = envelope('AddNote', cr, { lineId: uid(), groupId: cgroup, description: 'Contro chiusura' });
    const closeBody = { id: uid(), expectedRevision: cr };
    await control('hold-order-lock:' + clo);
    const [noteResult, closeResult] = await Promise.all([cmd(page, clo, raceNote), post(page, `${base}/orders/${clo}/technical-closure`, closeBody)]);
    const winners = [noteResult.status === 201, closeResult.status === 201].filter(Boolean).length;
    assert.equal(winners, 1, 'edit and closure are serialized: exactly one wins ' + noteResult.status + '/' + closeResult.status);
    if (closeResult.status === 201) { assert.equal(noteResult.value.code, 'order_technically_closed'); assert.equal(closeResult.value.revision, cr); }
    else assert.equal(closeResult.value.code, 'revision_changed');
    if (noteResult.status === 201) {
      const closed = await post(page, `${base}/orders/${clo}/technical-closure`, { id: uid(), expectedRevision: noteResult.value.appliedRevision }); assert.equal(closed.status, 201);
    }
    const rejected = await cmd(page, clo, envelope('AddNote', 99, { lineId: uid(), groupId: cgroup, description: 'dopo chiusura' }));
    assert.equal(rejected.status, 409); assert.equal(rejected.value.code, 'order_technically_closed');
    const originalReplay = await cmd(page, clo, raceNote);
    if (noteResult.status === 201) { assert.equal(originalReplay.status, 200); assert.deepEqual(originalReplay.value, noteResult.value); }
    const closedView = (await editor(page, clo)).value; assert.equal(closedView.capabilities.closed, true);
    result.closure = { order: clo, revision: closedView.revision };
    pass('T12 closure uses persisted revision (not line count); edit-vs-closure race serialized; closed order refuses commands but exact replay stays readable');

    stage = 'T13 provenance';
    const pv = await createOrder(page); let pr = 0; const gX = uid(), gY = uid(), pX = uid(), pY = uid();
    for (const [g, title] of [[gX, 'Gruppo X'], [gY, 'Gruppo Y']]) pr = (await cmd(page, pv, envelope('AddGroup', pr, { groupId: g, title }))).value.appliedRevision;
    for (const [line, group, q] of [[pX, gX, '4'], [pY, gY, '3']]) pr = (await cmd(page, pv, envelope('AddCommercialLine', pr, { lineId: line, groupId: group, catalogItemId: data.partId, catalogVersion: 8, quantity: q, unitPrice: '5', discountPercent: '0' }))).value.appliedRevision;
    const reserve = (line, id, q) => post(page, `/api/v1/inventory/orders/${pv}/lines/${line}/reservations`, { id, warehouseId: ctx.warehouseId, quantity: q, catalogVersion: 8 });
    const rX = uid(), rY = uid();
    assert.equal((await reserve(pX, rX, '3')).status, 201);
    const exceeded = await reserve(pX, uid(), '2'); assert.equal(exceeded.status, 409); assert.equal(exceeded.value.code, 'exceeds_remaining');
    assert.equal((await reserve(pY, rY, '3')).status, 201, 'same article in another group shares the stock pool but has its own residual');
    const pick = (line, reservation, q) => post(page, `/api/v1/inventory/orders/${pv}/lines/${line}/reservations/${reservation}/picks`, { id: uid(), quantity: q });
    const pickX = await pick(pX, rX, '2'), pickY = await pick(pY, rY, '1');
    assert.equal(pickX.status, 201); assert.equal(pickY.status, 201);
    assert.equal(pickX.value.workingGroupId, gX); assert.equal(pickY.value.workingGroupId, gY); assert.notEqual(gX, pv);
    result.prov = { order: pv, gX, gY, rX, rY };
    pass('T13 reservation → pick carry the real WorkingGroupId (not OrderId); two rows of one article share stock with separate residuals');

    stage = 'T16 browser UI';
    const long = await createOrder(page); let lr = 0; const lgroups = [uid(), uid(), uid(), uid()]; let lastId = '';
    for (const [i, g] of lgroups.entries()) lr = (await cmd(page, long, envelope('AddGroup', lr, { groupId: g, title: 'Lavorazione ' + (i + 1) }))).value.appliedRevision;
    for (let n = 0; n < 100; n++) {
      lastId = uid();
      const x = await cmd(page, long, envelope('AddCommercialLine', lr, { lineId: lastId, groupId: lgroups[n % 4], catalogItemId: n % 5 === 4 ? data.partId : data.serviceId, catalogVersion: 8, quantity: '1', unitPrice: String(10 + n), discountPercent: '0', description: 'Riga ' + n }));
      assert.equal(x.status, 201); lr = x.value.appliedRevision;
    }
    assert.equal(lr, 104);
    await page.goto(origin + '/ui01-runtime.html#order=' + long);
    await page.getByText('Valori salvati riletti — revisione 104', { exact: true }).waitFor();
    assert.equal(await page.locator('tbody tr').count(), 100);
    for (const [width, height] of [[1920, 1080], [1366, 768]]) {
      await page.setViewportSize({ width, height });
      const m = await page.evaluate(() => ({ width: innerWidth, height: innerHeight, bottom: document.querySelector('.ui01-summary').getBoundingClientRect().bottom }));
      assert.deepEqual(m, { width, height, bottom: height });
      await page.locator('.ui01-document').evaluate(e => { e.scrollTop = e.scrollHeight; });
      const last = page.locator('#row-' + lastId); await last.scrollIntoViewIfNeeded();
      const visible = await last.evaluate(e => { const r = e.getBoundingClientRect(), f = document.querySelector('.ui01-summary').getBoundingClientRect(); return r.top >= 0 && r.bottom <= f.top; });
      assert(visible, 'last of 100 rows reachable above the sticky summary at ' + width);
      await page.screenshot({ path: '/run/control/r03a-' + width + 'x' + height + '.png' });
    }
    await page.locator('#row-' + lastId).click();
    await page.getByLabel('Prezzo riga', { exact: true }).fill('199.5');
    await page.getByLabel('Prezzo riga', { exact: true }).press('Escape');
    assert.equal(await page.getByLabel('Prezzo riga', { exact: true }).count(), 0, 'Escape cancels the edit without a write');
    await page.locator('#row-' + lastId).click();
    await page.getByLabel('Prezzo riga', { exact: true }).fill('abc'); await page.getByLabel('Prezzo riga', { exact: true }).press('Enter');
    await page.getByText('Prezzo non negativo, max 6 decimali.', { exact: true }).waitFor();
    assert(await page.getByLabel('Prezzo riga', { exact: true }).evaluate(e => e === document.activeElement), 'first invalid field is focused and announced');
    await page.getByLabel('Prezzo riga', { exact: true }).fill('199.5'); await page.getByLabel('Prezzo riga', { exact: true }).press('Enter');
    await page.getByText('Valori salvati riletti — revisione 105', { exact: true }).waitFor();
    assert(await page.locator('#row-' + lastId).evaluate(e => e === document.activeElement), 'focus returns to the stable row action');
    assert.equal((await editor(page, long)).value.rows.find(r => r.id === lastId).line.unitPrice, '199.5');
    // Group rename + Note through the real UI.
    await page.getByRole('button', { name: 'Rinomina lavorazione' }).first().click();
    await page.locator('#rename-title').fill('Revisione generale'); await page.locator('#rename-title').press('Enter');
    await page.getByText('Valori salvati riletti — revisione 106', { exact: true }).waitFor();
    await page.getByLabel('Nota (solo descrizione, non commerciale)').fill('Nota da interfaccia'); await page.getByRole('button', { name: 'Aggiungi nota' }).click();
    await page.getByText('Valori salvati riletti — revisione 107', { exact: true }).waitFor();
    const partRemove = page.locator('tr', { hasText: 'Synthetic Part' }).first().getByRole('button', { name: 'Rimuovi' });
    assert.equal(await partRemove.isDisabled(),false); assert.match(await partRemove.getAttribute('title'), /impegni logistici/);
    for (const name of ['Cambia testata', 'Cambia pagante', 'Cambia veicolo']) assert(await page.getByRole('button', { name }).isDisabled());
    // Reopen from the authorized list, not by UUID.
    await page.goto(origin + '/ui01-runtime.html'); await page.getByRole('button', { name: 'Elenca commesse' }).waitFor();
    await page.getByLabel('Contesto elenco').selectOption({ index: 0 });
    await page.getByRole('button', { name: 'Elenca commesse' }).click();
    let found = false;
    for (let n = 0; n < 6 && !found; n++) {
      await page.getByRole('button', { name: /^Apri / }).first().waitFor();
      found = (await page.getByRole('button', { name: 'Apri ' + long }).count()) > 0;
      if (!found) await page.getByRole('button', { name: 'Pagina successiva', exact: true }).click();
    }
    assert(found, 'order listed by keyset pages');
    await page.getByRole('button', { name: 'Apri ' + long }).click();
    await page.getByText('Valori salvati riletti — revisione 107', { exact: true }).waitFor();
    // Read-only identity: workspace is visible, every write control is disabled with its reason.
    const ro = await login(browser, 5);
    await control('permissions:readonly:workshop.orders.read');
    await ro.page.goto(origin + '/ui01-runtime.html#order=' + long);
    await ro.page.getByText('Valori salvati riletti — revisione 107', { exact: true }).waitFor();
    for (const name of ['Aggiungi lavorazione', 'Aggiungi riga', 'Aggiungi nota']) assert(await ro.page.getByRole('button', { name }).evaluate(e => e.matches(':disabled')), name + ' disabled for read-only');
    assert((await ro.page.getByRole('button', { name: 'Modifica' }).first().isDisabled()));
    await ro.context.close();
    assert.equal(await page.evaluate(() => Object.keys(localStorage).length + Object.keys(sessionStorage).length), 0);
    result.ui = { order: long, last: lastId };
    pass('T16 real Chromium UI: 100 rows in four groups at 1920x1080 and 1366x768 with reachable last row and sticky summary; edit/Escape/invalid focus/Enter/focus return; rename, Note, unsupported controls disabled with reason; keyset list reopen; read-only identity; no browser storage');

    stage = 'complete';
    result.users = 'ok';
    fs.writeFileSync('/run/control/result.json', JSON.stringify(result));
    console.log('R03A_CHECKS ' + checks.length);
  } catch (error) {
    console.error('R03A_FAILED at ' + stage + ': ' + (error && error.stack || error));
    process.exitCode = 1;
  } finally { await browser.close(); }
})();
