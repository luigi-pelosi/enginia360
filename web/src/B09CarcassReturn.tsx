import { useEffect, useRef, useState } from 'react';

type Return = { id: string; quantity: string; description: string; location: string; locationConfigurationVersion: number };
type State = { requiredInstalled: string; returned: string; outstanding: string; returns: Return[] };
type Gate = { status: 'Blocked' | 'Clear'; requirements: { lineId: string; outstanding: string }[] };
type Props = { url: string; orderId: string; warehouse: string; token: string; refresh: number };
const record = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const decimal = (x: unknown): x is string => typeof x === 'string' && /^\d{1,6}(\.\d{1,6})?$/.test(x);
const uuid = (x: unknown): x is string => typeof x === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(x);
const text = (x: unknown, max: number): x is string => typeof x === 'string' && x.length > 0 && x.length <= max;
const validDescription = (x: string) => x.length > 0 && x.length <= 200 && x === x.trim() && !/[\u0000-\u001f\u007f-\u009f]/.test(x);

// D73: one explicit command must cover the whole outstanding carcass residual; never trimmed or completed client-side.
export default function B09CarcassReturn({url, orderId, warehouse, token, refresh}: Props) {
  const [state, setState] = useState<State>();
  const [gate, setGate] = useState<Gate>();
  const [quantity, setQuantity] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const generation = useRef(0);
  const pending = useRef<{key: string; id: string} | undefined>(undefined);
  const lineId = url.split('/').pop();
  async function api(path: string, payload?: unknown): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(path, {method: payload === undefined ? 'GET' : 'POST',
        headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
        ...(payload === undefined ? {} : {body: JSON.stringify(payload)})});
    } catch {
      throw new Error('Rientro non confermato. Rileggi oppure riprova lo stesso tentativo.');
    }
    if (!response.ok) {
      if (response.status === 409) {
        const result: unknown = await response.json().catch(() => null);
        if (record(result) && result.code === 'must_cover_outstanding' && decimal(result.outstanding))
          throw new Error(`Il rientro deve coprire esattamente tutto il residuo (${result.outstanding}). Nessun rientro registrato.`);
        if (record(result) && result.code === 'nothing_outstanding') throw new Error('Nessun residuo carcassa da rientrare. Nessun rientro registrato.');
        if (record(result) && result.code === 'carcass_configuration_missing') throw new Error('Ubicazione carcasse non configurata. Nessun rientro registrato.');
      }
      throw new Error('Rientro non confermato. Rileggi oppure riprova lo stesso tentativo.');
    }
    return response.json();
  }
  async function read(): Promise<[State, Gate]> {
    const value = await api(`${url}/carcass-returns?warehouseId=${warehouse}`);
    if (!record(value) || ![value.requiredInstalled, value.returned, value.outstanding].every(decimal) || !Array.isArray(value.returns)
      || !value.returns.every(x => record(x) && uuid(x.id) && decimal(x.quantity) && text(x.description, 200) && text(x.location, 100)
        && Number.isInteger(x.locationConfigurationVersion))) throw new Error();
    const closure = await api(url.replace('/inventory/', '/workshop/').replace(/\/lines\/.*$/, '') + '/technical-closure-gate');
    if (!record(closure) || closure.orderId !== orderId || !['Blocked', 'Clear'].includes(closure.status as string) || !Array.isArray(closure.requirements)
      || !closure.requirements.every(x => record(x) && uuid(x.lineId) && decimal(x.outstanding))) throw new Error();
    return [value as State, closure as Gate];
  }
  async function reload() {
    const current = ++generation.current;
    setBusy(true); setError('');
    try {
      const [saved, closure] = await read();
      if (current === generation.current) {
        setState(saved); setGate(closure);
        if (saved.returns.some(x => x.id === pending.current?.id)) pending.current = undefined;
      }
    } catch { if (current === generation.current) { setState(undefined); setGate(undefined); setError('Stato rientro carcassa non disponibile. Rileggi prima di continuare.'); } }
    finally { if (current === generation.current) setBusy(false); }
  }
  useEffect(() => { void reload(); return () => { generation.current++; }; }, [url, warehouse, token, refresh]);
  async function receive() {
    if (busy || !state) return;
    if (!decimal(quantity) || !/[1-9]/.test(quantity)) { setError('Inserisci una quantità positiva con massimo sei decimali.'); return; }
    if (!validDescription(description)) { setError('Inserisci una descrizione da 1 a 200 caratteri, senza spazi iniziali o finali.'); return; }
    const key = JSON.stringify([warehouse, quantity, description]);
    if (pending.current?.key !== key) pending.current = {key, id: crypto.randomUUID()};
    const current = generation.current;
    setBusy(true); setError('');
    try {
      await api(`${url}/carcass-returns`, {id: pending.current.id, warehouseId: warehouse, quantity, description});
      try {
        const [saved, closure] = await read();
        if (current === generation.current) { setState(saved); setGate(closure); pending.current = undefined; }
      } catch { if (current === generation.current) { setState(undefined); setError('Stato rientro carcassa non disponibile. Rileggi prima di continuare.'); } }
    } catch (failure) { if (current === generation.current) setError(failure instanceof Error ? failure.message : 'Rientro non confermato.'); }
    finally { if (current === generation.current) setBusy(false); }
  }
  const outstanding = gate?.requirements.find(x => x.lineId === lineId)?.outstanding;
  return <section aria-label="Rientro carcassa">
    <h3>Rientro carcassa</h3>
    <p>Particolare sostituito, distinto dal ricambio nuovo: non rientra in giacenza né in disponibilità. Ogni rientro copre esattamente tutto il residuo.</p>
    <label>Descrizione carcassa<input value={description} maxLength={200} disabled={busy} onChange={event => setDescription(event.target.value)}/></label>
    <label>Quantità carcassa<input inputMode="decimal" value={quantity} disabled={busy} onChange={event => setQuantity(event.target.value)}/></label>
    <button disabled={busy || !state} onClick={() => void receive()}>Registra rientro carcassa</button>
    <button disabled={busy} onClick={() => void reload()}>Rileggi rientro carcassa</button>
    {state && <div aria-live="polite"><p>Installato con carcassa richiesta: {state.requiredInstalled}</p><p>Rientrato: {state.returned}</p>
      <p>Residuo carcassa da rientrare: {state.outstanding}</p>
      {state.returns.map(x => <p key={x.id}>{x.quantity} · {x.description} · Ubicazione carcasse: {x.location} (configurazione {x.locationConfigurationVersion})</p>)}</div>}
    {gate && <p>{gate.status === 'Clear'
      ? (gate.requirements.length === 0 ? 'Chiusura tecnica: nessun requisito carcassa in sospeso' : 'Chiusura tecnica: requisito carcassa soddisfatto')
      : `Chiusura tecnica bloccata: carcassa da rientrare ${outstanding ?? ''}`.trim()}</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
