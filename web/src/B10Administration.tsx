import { useEffect, useRef, useState } from 'react';

type Delivery = { state: string; attempts: number };
type Request = { id: string; status: 'Pending' | 'Confirmed' | 'Rejected'; externalReference: string | null; rejectionCode: string | null; delivery: Delivery };
type State = { status: string; technicalClosure: { id: string } | null; request: Request | null; administrativeClosure: { externalReference: string } | null };
type Props = { orderId: string; revision: number; token: string };
const record = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const uuid = (x: unknown): x is string => typeof x === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(x);
const reference = (x: unknown): x is string => typeof x === 'string' && /^[A-Za-z0-9][A-Za-z0-9-]{0,63}$/.test(x);
const code = (x: unknown): x is string => typeof x === 'string' && /^[a-z0-9_]{1,64}$/.test(x);
const STATUSES = ['Open', 'TechnicallyClosed', 'AwaitingAdministrativeConfirmation', 'AdministrativelyConfirmed', 'AdministrativeRejected', 'AdministrativelyClosed'];
const DELIVERY: Record<string, string> = { Queued: 'in coda', Received: 'ricevuta (sola acquisizione)', Retrying: 'nuovo tentativo programmato',
  Completed: 'elaborazione completata', Rejected: 'rifiutata', Uncertain: 'esito incerto — verifica prima di reinviare',
  NeedsReconciliation: 'tentativi automatici esauriti — riconciliazione autorizzata richiesta' };
const REFUSALS: Record<string, string> = {
  technical_requirements_pending: 'Chiusura tecnica rifiutata: carcassa da rientrare. Nessuna chiusura registrata.',
  revision_changed: 'Valori della commessa cambiati: rileggi prima di continuare.',
  order_technically_closed: 'Commessa già chiusa tecnicamente.',
  already_closed: 'Chiusura già registrata con un altro comando. Rileggi lo stato.',
  technical_closure_required: 'Chiudi tecnicamente la commessa prima della richiesta amministrativa.',
  already_requested: 'Richiesta amministrativa già registrata. Rileggi lo stato.',
  administrative_destination_missing: 'Destinazione amministrativa della società non configurata. Nessuna richiesta registrata.',
  external_confirmation_required: 'Chiusura amministrativa bloccata: manca la conferma di business del gestionale esterno.',
};
const UNCONFIRMED = 'Operazione non confermata. Rileggi oppure riprova lo stesso tentativo.';

function parse(x: unknown, orderId: string): State {
  if (!record(x) || x.orderId !== orderId || !STATUSES.includes(x.status as string)) throw new Error();
  const technical = x.technicalClosure, request = x.request, administrative = x.administrativeClosure;
  if (technical !== null && !(record(technical) && uuid(technical.id) && technical.orderId === orderId)) throw new Error();
  if (request !== null && !(record(request) && uuid(request.id) && request.orderId === orderId && ['Pending', 'Confirmed', 'Rejected'].includes(request.status as string)
    && (request.status === 'Confirmed' ? reference(request.externalReference) : request.externalReference === null)
    && (request.status === 'Rejected' ? code(request.rejectionCode) : request.rejectionCode === null)
    && record(request.delivery) && typeof request.delivery.state === 'string' && request.delivery.state in DELIVERY
    && Number.isInteger(request.delivery.attempts) && Number(request.delivery.attempts) >= 0)) throw new Error();
  if (administrative !== null && !(record(administrative) && reference(administrative.externalReference))) throw new Error();
  return x as State;
}

// D37/D40: technical closure, durable request, and administrative closure only after a business confirmation.
export default function B10Administration({orderId, revision, token}: Props) {
  const [state, setState] = useState<State>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const generation = useRef(0);
  const pending = useRef<Record<string, string>>({});
  async function api(path: string, payload?: unknown): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(`/api/v1/workshop/orders/${orderId}${path}`, {method: payload === undefined ? 'GET' : 'POST',
        headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'}, ...(payload === undefined ? {} : {body: JSON.stringify(payload)})});
    } catch { throw new Error(UNCONFIRMED); }
    if (!response.ok) {
      const result: unknown = response.status === 409 ? await response.json().catch(() => null) : null;
      throw new Error(record(result) && typeof result.code === 'string' && REFUSALS[result.code] || UNCONFIRMED);
    }
    return response.json();
  }
  async function reload() {
    const current = ++generation.current;
    setBusy(true); setError('');
    try { const value = parse(await api('/closure-state'), orderId); if (current === generation.current) setState(value); }
    catch { if (current === generation.current) { setState(undefined); setError('Stato amministrativo non disponibile. Rileggi prima di continuare.'); } }
    finally { if (current === generation.current) setBusy(false); }
  }
  useEffect(() => { void reload(); return () => { generation.current++; }; }, [orderId, token]);
  async function command(action: string, path: string, body: Record<string, unknown>) {
    if (busy) return;
    // The command ID survives a lost response until the committed state is reread.
    const key = `${action}:${revision}`;
    pending.current[key] ??= crypto.randomUUID();
    const current = generation.current;
    setBusy(true); setError('');
    try {
      await api(path, {id: pending.current[key], ...body});
      delete pending.current[key];
      const value = parse(await api('/closure-state'), orderId);
      if (current === generation.current) setState(value);
    } catch (failure) { if (current === generation.current) setError(failure instanceof Error ? failure.message : UNCONFIRMED); }
    finally { if (current === generation.current) setBusy(false); }
  }
  const request = state?.request;
  const text = !state ? '' : {
    Open: 'Commessa aperta: chiusura tecnica non registrata',
    TechnicallyClosed: 'Completata tecnicamente — richiesta amministrativa da inviare',
    AwaitingAdministrativeConfirmation: 'Completata tecnicamente — in attesa di conferma amministrativa',
    AdministrativelyConfirmed: `Confermata dal gestionale amministrativo · riferimento ${request?.externalReference ?? ''}`,
    AdministrativeRejected: `Rifiutata dal gestionale amministrativo (${request?.rejectionCode ?? ''}): riconciliazione richiesta`,
    AdministrativelyClosed: `Chiusa amministrativamente · riferimento ${state.administrativeClosure?.externalReference ?? ''}`,
  }[state.status];
  return <section aria-label="Chiusura amministrativa">
    <h3>Chiusura e destinazione amministrativa</h3>
    <p>La ricezione della richiesta non è una conferma: solo l'elaborazione completata con riferimento esterno consente la chiusura amministrativa. Nessuna fattura, incasso o registrazione reale.</p>
    <button disabled={busy || !state || state.status !== 'Open'} onClick={() => void command('technical', '/technical-closure', {expectedRevision: revision})}>Chiudi tecnicamente</button>
    <button disabled={busy || !state || state.status !== 'TechnicallyClosed'} onClick={() => void command('request', '/administrative-requests', {expectedRevision: revision})}>Invia al gestionale amministrativo</button>
    <button disabled={busy || !state || state.status !== 'AdministrativelyConfirmed'} onClick={() => void command('administrative', '/administrative-closure', {})}>Chiudi amministrativamente</button>
    <button disabled={busy || !request || request.delivery.state !== 'NeedsReconciliation'} onClick={() => void command('reconcile', `/administrative-requests/${request!.id}/reconciliation`, {})}>Verifica e riprendi richiesta</button>
    <button disabled={busy} onClick={() => void reload()}>Rileggi stato amministrativo</button>
    {state && <div aria-live="polite"><p>{text}</p>
      {request && <p>Consegna al gestionale: {DELIVERY[request.delivery.state]} · tentativi {request.delivery.attempts}</p>}</div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
