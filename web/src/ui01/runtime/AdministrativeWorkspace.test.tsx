import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AdministrativeWorkspace from './AdministrativeWorkspace';
import { parseEditor } from './editorContracts';
import { editorView, id, summary } from './editorFixtures';
import { actions, administrativeClosure, closureId, delivery, gate, request, requestId, state, technical } from './administrativeFixtures';
const editor = parseEditor({ ...editorView, revision: 9, summary: { ...summary, revision: 9 } }, id);
const base = '/api/v1/workshop/orders/' + id;
type Handler = (options?: RequestInit) => Response | Promise<Response>;
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
function server(routes: Record<string, Handler | unknown>) {
  const calls: { path: string; options?: RequestInit }[] = [];
  const fetch = vi.fn(async (path: string, options?: RequestInit) => {
    calls.push({ path, options });
    if (path === '/auth/csrf') return json({ requestToken: 'test-only' });
    const route = routes[(options?.method ?? 'GET') + ' ' + path];
    if (route === undefined) return json({}, 404);
    return typeof route === 'function' ? (route as Handler)(options) : json(route);
  });
  vi.stubGlobal('fetch', fetch);
  return { fetch, calls, posts: () => calls.filter(c => c.options?.method === 'POST') };
}
const noop = () => { };
const open = (over: Record<string, unknown> = {}) => ({ ['GET ' + base + '/closure-actions']: actions(over), ['GET ' + base + '/technical-closure-gate']: gate(), ['GET ' + base + '/closure-state']: state('Open') });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

test('open order: the carcass gate is a requirement only and technical closure posts the fresh server revision with a fixed command id', async () => {
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(closureId as `${string}-${string}-${string}-${string}-${string}`);
  let closed = false;
  const s = server({
    ['GET ' + base + '/closure-actions']: () => json(closed ? actions({ technicalClosure: technical, canCompleteTechnical: false, canRequestAdministrative: true, actionReasons: [] }) : actions()),
    ['GET ' + base + '/technical-closure-gate']: gate(),
    ['GET ' + base + '/closure-state']: () => json(closed ? state('TechnicallyClosed') : state('Open')),
    ['POST ' + base + '/technical-closure']: () => { closed = true; return json(technical, 201); },
  });
  const onChanged = vi.fn(async () => { });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={onChanged} />);
  expect(await screen.findByText('Requisito carcassa: Clear')).toBeTruthy();
  expect(screen.getByText(/non prova che tutta la commessa sia chiudibile/)).toBeTruthy();
  fireEvent.click(await screen.findByRole('button', { name: 'Chiudi tecnicamente' }));
  await screen.findByText('Chiusa tecnicamente alla revisione 9; stato riletto dal server.');
  expect(screen.getByText('Chiusa tecnicamente alla revisione 9')).toBeTruthy();
  const [post] = s.posts();
  expect(post.path).toBe(base + '/technical-closure');
  expect(post.options?.body).toBe(JSON.stringify({ id: closureId, expectedRevision: 9 }));
  expect(onChanged).toHaveBeenCalledOnce();
  expect(screen.queryByRole('button', { name: 'Chiudi tecnicamente' })).toBeNull();
});

test('lost response keeps one frozen command: retry is byte-identical with the same id, never a new revision or uuid', async () => {
  const uuid = vi.spyOn(crypto, 'randomUUID').mockReturnValue(closureId as `${string}-${string}-${string}-${string}-${string}`);
  let attempts = 0, applied = false;
  const s = server({
    ...open(),
    ['POST ' + base + '/technical-closure']: () => { attempts++; applied = true; if (attempts === 1) throw new TypeError('network'); return json(technical, 200); },
    ['GET ' + base + '/closure-actions']: () => json(applied ? actions({ technicalClosure: technical, canCompleteTechnical: false, commercialRevision: 11 }) : actions()),
  });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Chiudi tecnicamente' }));
  await screen.findByText('Esito incerto: riprova solo il comando identico.');
  expect(screen.queryByRole('button', { name: 'Chiudi tecnicamente' })?.hasAttribute('disabled')).toBe(true);
  uuid.mockReturnValue('abababab-abab-4bab-8bab-abababababab');
  fireEvent.click(screen.getByRole('button', { name: 'Riprova comando identico' }));
  await screen.findByText('Chiusa tecnicamente alla revisione 9; stato riletto dal server.');
  const [first, second] = s.posts();
  expect(second.path).toBe(first.path);
  expect(second.options?.body).toBe(first.options?.body);
  expect(first.options?.body).toBe(JSON.stringify({ id: closureId, expectedRevision: 9 }));
});

test('accepted command with a failed reread reports a registered but unverified state and offers no new write', async () => {
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(closureId as `${string}-${string}-${string}-${string}-${string}`);
  let applied = false;
  server({
    ...open(),
    ['POST ' + base + '/technical-closure']: () => { applied = true; return json(technical, 201); },
    ['GET ' + base + '/closure-actions']: () => applied ? json({}, 503) : json(actions()),
  });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Chiudi tecnicamente' }));
  await screen.findByText('Comando registrato; stato attuale non verificato. Rileggi stato.');
  expect(screen.queryByRole('button', { name: 'Chiudi tecnicamente' })).toBeNull();
  expect(screen.queryByText('Requisito carcassa: Clear')).toBeTruthy();
});

test('401 clears every panel datum and the frozen command before notifying the session owner', async () => {
  let revoked = false;
  const onError = vi.fn();
  server({ ...open(), ['GET ' + base + '/closure-actions']: () => revoked ? json({}, 401) : json(actions({ commercialRevision: 9 })) });
  render(<AdministrativeWorkspace editor={editor} onError={onError} onChanged={async () => { }} />);
  await screen.findByText('Requisito carcassa: Clear');
  revoked = true;
  fireEvent.click(screen.getByRole('button', { name: 'Rileggi stato' }));
  await waitFor(() => expect(onError).toHaveBeenCalledOnce());
  expect(screen.queryByText('Requisito carcassa: Clear')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Chiudi tecnicamente' })).toBeNull();
  expect(screen.getByRole('status').textContent).toBe('Sessione terminata. Accedi nuovamente.');
});

test('a slow older read can never overwrite a newer one', async () => {
  let call = 0; const releases: (() => void)[] = [];
  server({ ...open(),
    ['GET ' + base + '/closure-actions']: () => { const n = ++call; return new Promise<Response>(resolve => { releases.push(() => resolve(json(actions({ commercialRevision: n === 1 ? 9 : 9, canCompleteTechnical: n !== 1 })))); }); },
  });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await waitFor(() => expect(releases).toHaveLength(1));
  fireEvent.click(screen.getByRole('button', { name: 'Rileggi stato' }));
  await waitFor(() => expect(releases).toHaveLength(2));
  releases[1](); await screen.findByRole('button', { name: 'Chiudi tecnicamente' });
  releases[0](); await new Promise(r => setTimeout(r, 20));
  expect((screen.getByRole('button', { name: 'Chiudi tecnicamente' }) as HTMLButtonElement).disabled).toBe(false);
});

test('a refused command (409) drops the frozen id; the next attempt starts from a fresh read with a new id', async () => {
  const ids = [closureId, 'abababab-abab-4bab-8bab-abababababab'];
  vi.spyOn(crypto, 'randomUUID').mockImplementation(() => ids.shift() as `${string}-${string}-${string}-${string}-${string}`);
  let refusals = 0;
  const s = server({ ...open(), ['POST ' + base + '/technical-closure']: () => { refusals++; return refusals === 1 ? json({ code: 'revision_changed', revision: 10 }, 409) : json(technical, 201); } });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Chiudi tecnicamente' }));
  await screen.findByText(/Conflitto/);
  expect(screen.queryByRole('button', { name: 'Riprova comando identico' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Chiudi tecnicamente' }));
  await waitFor(() => expect(s.posts()).toHaveLength(2));
  expect(JSON.parse(s.posts()[1].options!.body as string).id).toBe('abababab-abab-4bab-8bab-abababababab');
});

const closed = (over: Record<string, unknown> = {}) => actions({ technicalClosure: technical, canCompleteTechnical: false, canRequestAdministrative: true, actionReasons: [], ...over });
const awaiting = (delivery_: Record<string, unknown> = {}, over: Record<string, unknown> = {}) => state('AwaitingAdministrativeConfirmation', { request: request({ delivery: delivery(String(delivery_.state ?? 'Queued'), delivery_), ...over }) });
const serve = (a: unknown, st: unknown, extra: Record<string, Handler | unknown> = {}) => server({ ['GET ' + base + '/closure-actions']: a, ['GET ' + base + '/technical-closure-gate']: gate(), ['GET ' + base + '/closure-state']: st, ...extra });

test('administrative request posts the frozen technical-closure revision, not the current commercial or row count', async () => {
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(requestId as `${string}-${string}-${string}-${string}-${string}`);
  let requested = false;
  const s = server({
    ['GET ' + base + '/closure-actions']: () => json(requested ? closed({ canRequestAdministrative: false, actionReasons: [{ action: 'requestAdministrative', code: 'already_requested' }] }) : closed({ commercialRevision: 10 })),
    ['GET ' + base + '/technical-closure-gate']: gate(),
    ['GET ' + base + '/closure-state']: () => json(requested ? awaiting() : state('TechnicallyClosed')),
    ['POST ' + base + '/administrative-requests']: () => { requested = true; return json(request(), 201); },
  });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Richiedi registrazione amministrativa' }));
  await screen.findByText('In coda: richiesta salvata, nessuna conferma di business.');
  expect(s.posts()[0].options?.body).toBe(JSON.stringify({ id: requestId, expectedRevision: 9 }));
  expect(screen.queryByRole('button', { name: 'Richiedi registrazione amministrativa' })).toBeNull();
  expect(screen.getByText('Simulatore amministrativo v1 · nessun collegamento Giobby')).toBeTruthy();
});

test.each([
  ['Queued', {}, 'In coda: richiesta salvata, nessuna conferma di business.'],
  ['Received', {}, 'Ricevuta dal simulatore: solo acquisizione, non conferma di business.'],
  ['Retrying', { attempts: 1 }, 'Nuovo tentativo programmato: nessuna conferma di business.'],
  ['Uncertain', { attempts: 1 }, 'Esito non verificato: verifica in corso, nessun nuovo invio.'],
  ['NeedsReconciliation', { attempts: 4, failures: 4 }, 'Tentativi automatici esauriti: serve verifica e ripresa.'],
  ['Completed', {}, 'Consegna completata; conferma di business locale non ancora verificata.'],
  ['Rejected', {}, 'Rifiuto ricevuto dal simulatore; esito di business locale non ancora verificato.'],
])('pending request with delivery %s is shown truthfully and never as confirmed', async (name, extra, text) => {
  serve(closed({ canRequestAdministrative: false }), awaiting({ state: name, ...extra }));
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText(text);
  expect(screen.queryByText(/Confermata/)).toBeNull();
  expect(screen.getByText('Simulatore amministrativo v1 · nessun collegamento Giobby')).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Chiudi amministrativamente' })).toBeNull();
});

test.each(['destination_binding_mismatch'])('destination hold %s exposes no-send reason instead of exhausted-retries advice', async lastError => {
  serve(closed({ canRequestAdministrative: false }), awaiting({ state: 'NeedsReconciliation', lastError }));
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Destinazione diversa/non verificata; nessun invio.');
  expect(screen.queryByText(/Tentativi automatici esauriti/)).toBeNull();
  expect(screen.queryByText(/Confermata/)).toBeNull();
});

test('confirmed and rejected business outcomes carry the stable reference or the code and keep the pinned snapshot visible', async () => {
  const confirmed = request({ status: 'Confirmed', externalReference: 'AMM-SIM-000001', outcomeAt: '2026-10-24T08:02:00+00:00', delivery: delivery('Completed') });
  serve(closed({ canRequestAdministrative: false }), state('AdministrativelyConfirmed', { request: confirmed }));
  const view = render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Confermata dal simulatore · riferimento AMM-SIM-000001 (nessuna fattura fiscale, nessun incasso).');
  expect(screen.getByText(/Snapshot richiesta: revisione 9 · 4 righe · 2 lavorazioni/)).toBeTruthy();
  expect(screen.getByText('44.835000 EUR')).toBeTruthy();
  view.unmount();
  serve(closed({ canRequestAdministrative: false }), state('AdministrativeRejected', { request: request({ status: 'Rejected', rejectionCode: 'synthetic_refusal', outcomeAt: '2026-10-24T08:02:00+00:00', delivery: delivery('Rejected') }) }));
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Rifiutata dal simulatore · codice synthetic_refusal. Nessun nuovo invio né conferma forzata.');
});

const reconcileCommand = '12121212-1212-4212-8212-121212121212';
test('reconciliation is a bounded retry of verification: advisory-gated, frozen, replayable, never a forced confirmation', async () => {
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(reconcileCommand as `${string}-${string}-${string}-${string}-${string}`);
  let verified = false;
  const s = server({
    ['GET ' + base + '/closure-actions']: () => json(closed({ canRequestAdministrative: false, mayRequestReconciliation: !verified })),
    ['GET ' + base + '/technical-closure-gate']: gate(),
    ['GET ' + base + '/closure-state']: () => json(verified ? awaiting({ state: 'Uncertain' }) : awaiting({ state: 'NeedsReconciliation', attempts: 4, failures: 4 })),
    ['POST ' + base + '/administrative-requests/' + requestId + '/reconciliation']: () => { verified = true; return json({ replayed: false }, 202); },
  });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Verifica e riprendi richiesta' }));
  await screen.findByText('Esito non verificato: verifica in corso, nessun nuovo invio.');
  expect(s.posts()[0].options?.body).toBe(JSON.stringify({ id: reconcileCommand }));
  expect(screen.queryByRole('button', { name: /forza|conferma ricevuta/i })).toBeNull();
  expect(screen.queryByRole('button', { name: 'Verifica e riprendi richiesta' })).toBeNull();
});

test('without the reconcile advice the exhausted state offers no recovery button', async () => {
  serve(closed({ canRequestAdministrative: false, mayRequestReconciliation: false, actionReasons: [{ action: 'reconcile', code: 'not_authorized' }] }), awaiting({ state: 'NeedsReconciliation', attempts: 4, failures: 4 }));
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Tentativi automatici esauriti: serve verifica e ripresa.');
  expect(screen.queryByRole('button', { name: 'Verifica e riprendi richiesta' })).toBeNull();
  expect(screen.getByText('Ripresa non disponibile: permesso mancante.')).toBeTruthy();
});

const confirmed = () => request({ status: 'Confirmed', externalReference: 'AMM-SIM-000001', outcomeAt: '2026-10-24T08:02:00+00:00', delivery: delivery('Completed') });
test('administrative closure needs the Workshop-confirmed outcome, posts only the command id and validates the stable reference', async () => {
  const closeId = '13131313-1313-4313-8313-131313131313';
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(closeId as `${string}-${string}-${string}-${string}-${string}`);
  let done = false;
  const s = server({
    ['GET ' + base + '/closure-actions']: () => json(closed({ canRequestAdministrative: false, canCompleteAdministrative: !done })),
    ['GET ' + base + '/technical-closure-gate']: gate(),
    ['GET ' + base + '/closure-state']: () => json(done ? state('AdministrativelyClosed', { request: confirmed(), administrativeClosure: { ...administrativeClosure, id: closeId } }) : state('AdministrativelyConfirmed', { request: confirmed() })),
    ['POST ' + base + '/administrative-closure']: () => { done = true; return json({ ...administrativeClosure, id: closeId }, 201); },
  });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Chiudi amministrativamente' }));
  await screen.findByText('Chiusa amministrativamente · riferimento AMM-SIM-000001; stato riletto dal server.');
  expect(s.posts()[0].options?.body).toBe(JSON.stringify({ id: closeId }));
  expect(screen.getByText(/nessun incasso né riconsegna/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: 'Chiudi amministrativamente' })).toBeNull();
});

test('a closure receipt for another request or reference is rejected as an unverified outcome', async () => {
  vi.spyOn(crypto, 'randomUUID').mockReturnValue('13131313-1313-4313-8313-131313131313' as `${string}-${string}-${string}-${string}-${string}`);
  serve(closed({ canRequestAdministrative: false, canCompleteAdministrative: true }), state('AdministrativelyConfirmed', { request: confirmed() }),
    { ['POST ' + base + '/administrative-closure']: () => json({ ...administrativeClosure, id: '13131313-1313-4313-8313-131313131313', externalReference: 'AMM-SIM-999999' }, 201) });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Chiudi amministrativamente' }));
  await screen.findByText('Esito incerto: riprova solo il comando identico.');
});

test('write grants without the administrative read leave the technical panel usable and never call the administrative reads', async () => {
  const s = serve(actions({ canReadAdministrativeState: false, canRequestAdministrative: false, actionReasons: [{ action: 'readAdministrativeState', code: 'not_authorized' }, { action: 'requestAdministrative', code: 'administrative_read_required' }] }), state('Open'));
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Stato amministrativo non autorizzato.');
  expect(screen.getByRole('button', { name: 'Chiudi tecnicamente' })).toBeTruthy();
  expect(screen.getByText('Per richiedere o chiudere serve la lettura dello stato amministrativo.')).toBeTruthy();
  expect(s.calls.some(c => c.path.endsWith('/closure-state') || c.path.endsWith('/administrative-requests'))).toBe(false);
  expect(screen.queryByText('Richiesta amministrativa non registrata.')).toBeNull();
});

test('each section fails alone: a state error keeps the gate and technical closure, a gate error never reads as Clear', async () => {
  serve(closed({ canRequestAdministrative: false }), () => json({}, 503), {});
  const view = render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Servizio non disponibile o richiesta non valida. Riprova.');
  expect(screen.getByText('Requisito carcassa: Clear')).toBeTruthy();
  expect(screen.getByText('Chiusa tecnicamente alla revisione 9')).toBeTruthy();
  view.unmount();
  server({ ['GET ' + base + '/closure-actions']: actions(), ['GET ' + base + '/technical-closure-gate']: () => json({}, 503), ['GET ' + base + '/closure-state']: state('Open') });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Requisito carcassa non verificato.');
  expect(screen.queryByText(/Requisito carcassa: Clear/)).toBeNull();
  expect((screen.getByRole('button', { name: 'Chiudi tecnicamente' }) as HTMLButtonElement).disabled).toBe(true);
});

test('incompatible advice and state disable every write instead of merging them', async () => {
  serve(actions(), state('TechnicallyClosed'));
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Letture non coerenti: nessuna azione finché lo stato non è riletto.');
  expect(screen.queryByRole('button', { name: 'Chiudi tecnicamente' })).toBeNull();
});

test('after a command the status is focused for keyboard users', async () => {
  vi.spyOn(crypto, 'randomUUID').mockReturnValue(closureId as `${string}-${string}-${string}-${string}-${string}`);
  serve(actions(), state('Open'), { ['POST ' + base + '/technical-closure']: () => json({}, 409) });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  const button = await screen.findByRole('button', { name: 'Chiudi tecnicamente' });
  button.focus(); fireEvent.click(button);
  await screen.findByText(/Conflitto/);
  expect(document.activeElement).toBe(screen.getByRole('status'));
});

test('a pending request is polled by reads only, finitely, and stops at the terminal business outcome', async () => {
  let reads = 0;
  const s = server({
    ['GET ' + base + '/closure-actions']: closed({ canRequestAdministrative: false }),
    ['GET ' + base + '/technical-closure-gate']: gate(),
    ['GET ' + base + '/closure-state']: () => { reads++; return json(reads < 3 ? awaiting({ state: 'Queued' }) : state('AdministrativelyConfirmed', { request: confirmed() })); },
  });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} pollMs={5} />);
  await screen.findByText(/Confermata dal simulatore/);
  const after = reads; await new Promise(r => setTimeout(r, 60));
  expect(reads).toBe(after);
  expect(s.posts()).toHaveLength(0);
});

test('regression: an explicit reread replaces a Blocked carcass requirement with the new server Clear', async () => {
  let cleared = false;
  server({ ...open(), ['GET ' + base + '/technical-closure-gate']: () => json(gate(cleared ? 'Clear' : 'Blocked')) });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Requisito carcassa: Blocked');
  expect((screen.getByRole('button', { name: 'Chiudi tecnicamente' }) as HTMLButtonElement).disabled).toBe(true);
  cleared = true;
  fireEvent.click(screen.getByRole('button', { name: 'Rileggi stato' }));
  await screen.findByText('Requisito carcassa: Clear');
  expect((screen.getByRole('button', { name: 'Chiudi tecnicamente' }) as HTMLButtonElement).disabled).toBe(false);
});

test('a malformed read is a visible section error, never a silent no-op', async () => {
  server({ ...open(), ['GET ' + base + '/closure-actions']: { orderId: id } });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Contratto server non valido o non supportato.');
  expect(screen.getByText('Requisito carcassa: Clear')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Rileggi stato' }));
  await screen.findByText('Contratto server non valido o non supportato.');
  expect(screen.queryByRole('button', { name: 'Chiudi tecnicamente' })).toBeNull();
});

test('regression: a commercial revision different from the editor the operator sees disables technical closure', async () => {
  server({ ...open({ commercialRevision: 10 }) });
  render(<AdministrativeWorkspace editor={editor} onError={noop} onChanged={async () => { }} />);
  await screen.findByText('Revisione commessa cambiata: rileggi la commessa prima di chiudere.');
  expect((screen.getByRole('button', { name: 'Chiudi tecnicamente' }) as HTMLButtonElement).disabled).toBe(true);
});
