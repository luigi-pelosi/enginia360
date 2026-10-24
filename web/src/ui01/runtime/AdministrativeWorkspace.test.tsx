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
