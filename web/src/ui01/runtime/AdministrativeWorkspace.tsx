import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, record } from './contracts';
import type { Editor } from './editorContracts';
import { parseActions, parseClosureState, parseGate, parseTechnical, type Actions, type ClosureState, type Gate } from './administrativeContracts';

// R03.c: the EXISTING closure commands, read advice and states. Provider truth: the registered adapter is a synthetic simulator, never Giobby.
type Frozen = Readonly<{ kind: 'technical'; url: string; body: string; commandId: string; orderId: string; revision: number }>;
const PROVIDER = 'Simulatore amministrativo v1 · nessun collegamento Giobby';
const NO_PROVIDER = 'Connettore amministrativo non registrato · nessun collegamento Giobby';

export default function AdministrativeWorkspace({ editor, onError, onChanged }: Readonly<{ editor: Editor; onError: (e: unknown) => void; onChanged: () => Promise<void> }>) {
  const id = editor.order.id, base = '/api/v1/workshop/orders/' + id;
  const [actions, setActions] = useState<Actions>(), [gate, setGate] = useState<Gate>(), [closure, setClosure] = useState<ClosureState>();
  const [actionsError, setActionsError] = useState(''), [gateError, setGateError] = useState(''), [stateError, setStateError] = useState('');
  const [message, setMessage] = useState('Lettura…'), [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
  const gen = useRef(0), epoch = useRef(0), pending = useRef(false), frozen = useRef<Frozen | undefined>(undefined), status = useRef<HTMLParagraphElement>(null);

  function clear() { gen.current++; epoch.current++; frozen.current = undefined; setActions(undefined); setGate(undefined); setClosure(undefined); setUncertain(false); setBusy(false); pending.current = false; }
  function failed(e: unknown) { if (e instanceof ApiError && e.status === 401) { clear(); setMessage(e.message); onError(e); return true; } return false; }

  async function readAll(): Promise<'ok' | 'failed' | 'stale'> {
    const g = ++gen.current;
    const a = await request(base + '/closure-actions').then(v => ({ status: 'fulfilled' as const, value: parseActions(v, id) }), reason => ({ status: 'rejected' as const, reason }));
    const gt = await request(base + '/technical-closure-gate').then(v => ({ status: 'fulfilled' as const, value: parseGate(v, id) }), reason => ({ status: 'rejected' as const, reason }));
    if (g !== gen.current) return 'stale';
    for (const r of [a, gt]) if (r.status === 'rejected' && failed(r.reason)) return 'stale';
    setActions(a.status === 'fulfilled' ? a.value : undefined); setActionsError(a.status === 'rejected' ? (a.reason as Error).message : '');
    setGate(gt.status === 'fulfilled' ? gt.value : undefined); setGateError(gt.status === 'rejected' ? (gt.reason as Error).message : '');
    setClosure(undefined); setStateError('');
    if (a.status === 'fulfilled' && a.value.canReadAdministrativeState) {
      try {
        const s = parseClosureState(await request(base + '/closure-state'), id);
        if (g !== gen.current) return 'stale';
        setClosure(s);
      } catch (e) { if (g !== gen.current || failed(e)) return 'stale'; setStateError((e as Error).message); }
    }
    return a.status === 'fulfilled' ? 'ok' : 'failed';
  }
  useEffect(() => { void readAll().then(r => { if (r === 'ok') setMessage('Stato riletto dal server.'); }).catch(() => { }); return () => { gen.current++; epoch.current++; }; }, [id]);

  async function post(command: Frozen) {
    pending.current = true; setBusy(true);
    const g = epoch.current;
    try {
      const csrf = record(await request('/auth/csrf')); check(typeof csrf.requestToken === 'string');
      if (g !== epoch.current) return;
      const response = await fetch(command.url, { method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'Content-Type': 'application/json', 'X-CSRF-TOKEN': csrf.requestToken as string }, body: command.body });
      if (!response.ok) { const failure = await response.json().catch(() => null); throw new ApiError(response.status, failure?.code ?? failure?.error); }
      const receipt = parseTechnical(await response.json(), id);
      check(receipt.id === command.commandId && receipt.revision === command.revision);
      if (g !== epoch.current) return;
      frozen.current = undefined; setUncertain(false);
      setMessage('Chiusa tecnicamente alla revisione ' + receipt.revision + '; rilettura in corso.');
      try { await onChanged(); } catch { /* the editor reports its own reread */ }
      const reread = await readAll();
      if (reread === 'ok') setMessage('Chiusa tecnicamente alla revisione ' + receipt.revision + '; stato riletto dal server.');
      else if (reread === 'failed' && g === epoch.current) setMessage('Comando registrato; stato attuale non verificato. Rileggi stato.');
    } catch (e) {
      if (g !== epoch.current) return;
      if (e instanceof ApiError && e.status < 500) { frozen.current = undefined; setUncertain(false); if (!failed(e)) setMessage(e.message); }
      else { setUncertain(true); setMessage('Esito incerto: riprova solo il comando identico.'); }
    } finally { pending.current = false; if (g === epoch.current) setBusy(false); }
  }
  function closeTechnically() {
    if (pending.current || uncertain || !actions) return;
    const commandId = crypto.randomUUID();
    frozen.current = Object.freeze({ kind: 'technical', url: base + '/technical-closure', body: JSON.stringify({ id: commandId, expectedRevision: actions.commercialRevision }), commandId, orderId: id, revision: actions.commercialRevision });
    void post(frozen.current);
  }

  const fresh = actions !== undefined && actions.commercialRevision === editor.revision;
  const technical = actions?.technicalClosure ?? null;
  return <section aria-label="Chiusura e attesa amministrativa"><h2>Chiusura e attesa amministrativa</h2>
    <p>{actions?.administrativeRuntime.kind === 'SimulatorV1' ? PROVIDER : NO_PROVIDER}</p>
    <p role="status" id="closure-status" tabIndex={-1} ref={status}>{message}</p>
    <button disabled={busy} onClick={() => void readAll().then(r => { if (r === 'ok') setMessage('Stato riletto dal server.'); })}>Rileggi stato</button>
    <section aria-label="Requisito carcassa">{gateError ? <p role="alert">{gateError}</p> : gate ? <><p>Requisito carcassa: {gate.status}</p><p>Requisito informativo: non prova che tutta la commessa sia chiudibile.</p></> : <p>Requisito carcassa non verificato.</p>}
      {gate?.requirements.map(r => <p key={r.lineId + r.catalogItemId}>Da rientrare {r.outstanding} su {r.requiredInstalled}</p>)}</section>
    <section aria-label="Chiusura tecnica">{actionsError ? <p role="alert">{actionsError}</p> : technical ? <p>Chiusa tecnicamente alla revisione {technical.revision}</p> : <p>Aperta: revisione commerciale {actions?.commercialRevision ?? 'non verificata'}</p>}
      {!technical && actions && !fresh && <p>Revisione commessa cambiata: rileggi la commessa prima di chiudere.</p>}
      {uncertain && frozen.current && <button disabled={busy} onClick={() => void post(frozen.current!)}>Riprova comando identico</button>}
      {actions && !technical && <button disabled={busy || uncertain || !fresh || !actions.canCompleteTechnical || gate?.status !== 'Clear'} onClick={closeTechnically}>Chiudi tecnicamente</button>}
</section>
    {stateError && <p role="alert">{stateError}</p>}{closure && null}
  </section>;
}
