import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, record } from './contracts';
import type { Editor } from './editorContracts';
import { parseActions, parseAdministrativeClosure, parseClosureState, parseGate, parseRequest, parseTechnical, type Actions, type AdministrativeRequest, type ClosureState, type Gate } from './administrativeContracts';

// R03.c: the EXISTING closure commands, read advice and states. Provider truth: the registered adapter is a synthetic simulator, never Giobby.
type Frozen = Readonly<{ kind: 'technical' | 'request' | 'reconcile' | 'close'; url: string; body: string; commandId: string; orderId: string; revision: number; requestId?: string; reference?: string }>;
const PROVIDER = 'Simulatore amministrativo v1 · nessun collegamento Giobby';
const NO_PROVIDER = 'Connettore amministrativo non registrato · nessun collegamento Giobby';
const DELIVERY: Record<string, string> = {
  Queued: 'In coda: richiesta salvata, nessuna conferma di business.',
  Received: 'Ricevuta dal simulatore: solo acquisizione, non conferma di business.',
  Retrying: 'Nuovo tentativo programmato: nessuna conferma di business.',
  Uncertain: 'Esito non verificato: verifica in corso, nessun nuovo invio.',
  NeedsReconciliation: 'Tentativi automatici esauriti: serve verifica e ripresa.',
  Completed: 'Consegna completata; conferma di business locale non ancora verificata.',
  Rejected: 'Rifiuto ricevuto dal simulatore; esito di business locale non ancora verificato.',
};
const WHY: Record<string, string> = {
  not_authorized: 'permesso mancante', capability_disabled: 'funzione disattivata per la società', route_unavailable: 'non disponibile in questo profilo',
  reconciliation_not_available: 'non necessaria o non ancora consentita', administrative_read_required: 'serve la lettura dello stato amministrativo',
};
// Business status first; transport state only explains a still pending request (D40).
function describe(r: AdministrativeRequest): string {
  if (r.status === 'Confirmed') return 'Confermata dal simulatore · riferimento ' + r.externalReference + ' (nessuna fattura fiscale, nessun incasso).';
  if (r.status === 'Rejected') return 'Rifiutata dal simulatore · codice ' + r.rejectionCode + '. Nessun nuovo invio né conferma forzata.';
  if (r.delivery.state === 'NeedsReconciliation' && r.delivery.lastError === 'destination_binding_mismatch')
    return 'Destinazione diversa/non verificata; nessun invio.';
  return DELIVERY[r.delivery.state];
}
const compatible = (a: Actions, s: ClosureState) => (a.technicalClosure?.id ?? null) === (s.technicalClosure?.id ?? null) && (a.technicalClosure?.revision ?? null) === (s.technicalClosure?.revision ?? null);

export default function AdministrativeWorkspace({ editor, onError, onChanged, pollMs = 2000 }: Readonly<{ editor: Editor; onError: (e: unknown) => void; onChanged: () => Promise<void>; pollMs?: number }>) {
  const id = editor.order.id, base = '/api/v1/workshop/orders/' + id;
  const [actions, setActions] = useState<Actions>(), [gate, setGate] = useState<Gate>(), [closure, setClosure] = useState<ClosureState>();
  const [actionsError, setActionsError] = useState(''), [gateError, setGateError] = useState(''), [stateError, setStateError] = useState(''), [inconsistent, setInconsistent] = useState(false);
  const [message, setMessage] = useState('Lettura…'), [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const gen = useRef(0), epoch = useRef(0), pending = useRef(false), polls = useRef(0), frozen = useRef<Frozen | undefined>(undefined), status = useRef<HTMLParagraphElement>(null);

  function clear() { gen.current++; epoch.current++; frozen.current = undefined; setActions(undefined); setGate(undefined); setClosure(undefined); setUncertain(false); setInconsistent(false); setBusy(false); pending.current = false; }
  function failed(e: unknown) { if (e instanceof ApiError && e.status === 401) { clear(); setMessage(e.message); onError(e); return true; } return false; }

  async function readAll(attempt = 0): Promise<'ok' | 'failed' | 'stale'> {
    const g = ++gen.current;
    // A malformed contract is a section error exactly like a failed request.
    const settle = <T,>(path: string, parse: (v: unknown) => T) => request(path).then(parse).then(value => ({ status: 'fulfilled' as const, value }), reason => ({ status: 'rejected' as const, reason }));
    const a = await settle(base + '/closure-actions', v => parseActions(v, id));
    const gt = await settle(base + '/technical-closure-gate', v => parseGate(v, id));
    if (g !== gen.current) return 'stale';
    for (const r of [a, gt]) if (r.status === 'rejected' && failed(r.reason)) return 'stale';
    setActions(a.status === 'fulfilled' ? a.value : undefined); setActionsError(a.status === 'rejected' ? (a.reason as Error).message : '');
    setGate(gt.status === 'fulfilled' ? gt.value : undefined); setGateError(gt.status === 'rejected' ? (gt.reason as Error).message : '');
    setInconsistent(false);
    if (!(a.status === 'fulfilled' && a.value.canReadAdministrativeState)) { setClosure(undefined); setStateError(''); }
    if (a.status === 'fulfilled' && a.value.canReadAdministrativeState) {
      try {
        const s = parseClosureState(await request(base + '/closure-state'), id);
        if (g !== gen.current) return 'stale';
        // Two public reads are not one transaction: incompatible closures are never merged; one bounded re-read, then writes stay off.
        if (!compatible(a.value, s)) { if (attempt < 1) return readAll(attempt + 1); setClosure(undefined); setInconsistent(true); return 'ok'; }
        setClosure(s); setStateError('');
      } catch (e) { if (g !== gen.current || failed(e)) return 'stale'; setClosure(undefined); setStateError((e as Error).message); }
    }
    return a.status === 'fulfilled' ? 'ok' : 'failed';
  }
  const reread = () => void readAll().then(r => { if (r === 'ok') setMessage('Stato riletto dal server.'); }).catch(() => setMessage('Lettura non riuscita: stato non verificato.'));
  useEffect(() => { polls.current = 0; void readAll().then(r => { if (r === 'ok') setMessage('Stato riletto dal server.'); }).catch(() => { }); return () => { gen.current++; epoch.current++; }; }, [id]);

  // Finite read-only polling while a request is pending; suspended by commands, errors, 401 and terminal outcomes.
  const waiting = closure?.request?.status === 'Pending' && !busy && !uncertain && !inconsistent;
  useEffect(() => {
    if (!waiting || polls.current >= 20) return;
    const timer = setTimeout(() => { polls.current++; void readAll().catch(() => { }); }, Math.min(pollMs * 2 ** Math.min(polls.current, 4), 15000));
    return () => clearTimeout(timer);
  }, [waiting, closure]);
  useEffect(() => { if (closure?.request?.status !== 'Pending') polls.current = 0; }, [closure]);

  async function post(command: Frozen) {
    pending.current = true; setBusy(true);
    const g = epoch.current;
    try {
      const csrf = record(await request('/auth/csrf')); check(typeof csrf.requestToken === 'string');
      if (g !== epoch.current) return;
      const response = await fetch(command.url, { method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf.requestToken as string }, body: command.body });
      if (!response.ok) { const failure = await response.json().catch(() => null); throw new ApiError(response.status, failure?.code ?? failure?.error); }
      const body = await response.json();
      // Dynamic delivery may have progressed on replay: verify identity and the pinned snapshot, never byte equality of the response.
      let done: string;
      if (command.kind === 'technical') { const r = parseTechnical(body, id); check(r.id === command.commandId && r.revision === command.revision); done = 'Chiusa tecnicamente alla revisione ' + command.revision; }
      else if (command.kind === 'request') { const r = parseRequest(body, id); check(r.id === command.commandId && r.summary.revision === command.revision); done = 'Richiesta amministrativa registrata sullo snapshot della revisione ' + command.revision; }
      else if (command.kind === 'reconcile') { check(typeof record(body).replayed === 'boolean'); done = 'Verifica della richiesta pianificata (nessun esito di business modificato)'; }
      else { const r = parseAdministrativeClosure(body, id); check(r.id === command.commandId && r.requestId === command.requestId && r.externalReference === command.reference); done = 'Chiusa amministrativamente · riferimento ' + r.externalReference; }
      if (g !== epoch.current) return;
      frozen.current = undefined; setUncertain(false);
      setMessage(done + '; rilettura in corso.');
      try { await onChanged(); } catch { /* the editor reports its own reread */ }
      const result = await readAll();
      if (result === 'ok') setMessage(done + '; stato riletto dal server.');
      else if (result === 'failed' && g === epoch.current) setMessage('Comando registrato; stato attuale non verificato. Rileggi stato.');
    } catch (e) {
      if (g !== epoch.current) return;
      if (e instanceof ApiError && e.status < 500) { frozen.current = undefined; setUncertain(false); if (!failed(e)) setMessage(e.message); }
      else { setUncertain(true); setMessage('Esito incerto: riprova solo il comando identico.'); }
    } finally { pending.current = false; if (g === epoch.current) { setBusy(false); setTimeout(() => status.current?.focus(), 0); } }
  }
  function begin(kind: Frozen['kind'], url: string, body: (commandId: string) => object, revision: number, extra: Partial<Frozen> = {}) {
    if (pending.current || uncertain || inconsistent) return;
    const commandId = crypto.randomUUID();
    frozen.current = Object.freeze({ kind, url: base + url, body: JSON.stringify({ id: commandId, ...body(commandId) }), commandId, orderId: id, revision, ...extra });
    polls.current = 0; void post(frozen.current);
  }

  const fresh = actions !== undefined && actions.commercialRevision === editor.revision;
  const technical = actions?.technicalClosure ?? null, req = closure?.request ?? null;
  const readable = actions?.canReadAdministrativeState === true;
  const reason = (action: string) => actions?.actionReasons.find(r => r.action === action)?.code ?? '';
  const canReconcile = actions?.mayRequestReconciliation && req?.status === 'Pending' && req.delivery.state === 'NeedsReconciliation' && !inconsistent;
  return <section aria-label="Chiusura e attesa amministrativa"><h2>Chiusura e attesa amministrativa</h2>
    <p>{actions?.administrativeRuntime.kind === 'SimulatorV1' ? PROVIDER : NO_PROVIDER}</p>
    <p role="status" id="closure-status" tabIndex={-1} ref={status}>{message}</p>
    <button disabled={busy} onClick={reread}>Rileggi stato</button>
    {inconsistent && <p role="alert">Letture non coerenti: nessuna azione finché lo stato non è riletto.</p>}
    <section aria-label="Requisito carcassa">{gateError ? <p role="alert">{gateError}</p> : gate ? <><p>Requisito carcassa: {gate.status}</p><p>Requisito informativo: non prova che tutta la commessa sia chiudibile.</p></> : <p>Requisito carcassa non verificato.</p>}
      {gate?.requirements.map(r => <p key={r.lineId + r.catalogItemId}>Da rientrare {r.outstanding} su {r.requiredInstalled}</p>)}</section>
    <section aria-label="Chiusura tecnica">{actionsError ? <p role="alert">{actionsError}</p> : technical ? <p>Chiusa tecnicamente alla revisione {technical.revision}</p> : <p>Aperta: revisione commerciale {actions?.commercialRevision ?? 'non verificata'}</p>}
      {!technical && actions && !fresh && <p>Revisione commessa cambiata: rileggi la commessa prima di chiudere.</p>}
      {uncertain && frozen.current && <button disabled={busy} onClick={() => void post(frozen.current!)}>Riprova comando identico</button>}
      {actions && !technical && !inconsistent && <button disabled={busy || uncertain || !fresh || !actions.canCompleteTechnical || gate?.status !== 'Clear'}
        onClick={() => begin('technical', '/technical-closure', () => ({ expectedRevision: actions.commercialRevision }), actions.commercialRevision)}>Chiudi tecnicamente</button>}</section>
    <section aria-label="Richiesta amministrativa">{actions && !readable ? <><p>{reason('readAdministrativeState') === 'route_unavailable' ? 'Stato amministrativo non disponibile in questo profilo.' : 'Stato amministrativo non autorizzato.'}</p>
      <p>Per richiedere o chiudere serve la lettura dello stato amministrativo.</p></>
      : stateError ? <p role="alert">{stateError}</p> : req ? <>
      <p>{describe(req)}</p>
      <p>Snapshot richiesta: revisione {req.summary.revision} · {req.summary.lines.length} righe · {new Set(req.summary.lines.map(l => l.workingGroupId)).size} lavorazioni</p>
      <p>Imponibile {req.summary.netAmount} · IVA {req.summary.taxAmount} · <strong>{req.summary.total} EUR</strong></p></> : closure ? <p>Richiesta amministrativa non registrata.</p> : null}
      {closure?.administrativeClosure && <p>Chiusa amministrativamente · riferimento {closure.administrativeClosure.externalReference} (contratto simulato; nessun incasso né riconsegna).</p>}
      {req?.status === 'Pending' && req.delivery.state === 'NeedsReconciliation' && !canReconcile && actions && <p>Ripresa non disponibile: {WHY[reason('reconcile')] ?? 'rileggi lo stato'}.</p>}
      {actions?.canRequestAdministrative && !req && !inconsistent && <button disabled={busy || uncertain}
        onClick={() => begin('request', '/administrative-requests', () => ({ expectedRevision: technical!.revision }), technical!.revision)}>Richiedi registrazione amministrativa</button>}
      {canReconcile && <button disabled={busy || uncertain}
        onClick={() => begin('reconcile', '/administrative-requests/' + req!.id + '/reconciliation', () => ({}), 0, { requestId: req!.id })}>Verifica e riprendi richiesta</button>}
      {actions?.canCompleteAdministrative && req?.status === 'Confirmed' && !closure?.administrativeClosure && !inconsistent && <button disabled={busy || uncertain}
        onClick={() => begin('close', '/administrative-closure', () => ({}), 0, { requestId: req.id, reference: req.externalReference! })}>Chiudi amministrativamente</button>}</section>
  </section>;
}
