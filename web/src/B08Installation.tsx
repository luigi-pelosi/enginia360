import { useEffect, useRef, useState } from 'react';

type Entry = { installation: { id: string; quantity: string }; stockEffect: 'Pending' | 'Consumed'; consumption: { installationId: string; quantity: string } | null };
type State = { picked: string; installed: string; remainingToInstall: string; installations: Entry[] };
const record = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const decimal = (x: unknown): x is string => typeof x === 'string' && /^\d{1,6}(\.\d{1,6})?$/.test(x);
const uuid = (x: unknown): x is string => typeof x === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(x);

export default function B08Installation({url, token, onChanged}: {url: string; token: string; onChanged?: () => void}) {
  const [state, setState] = useState<State>();
  const [quantity, setQuantity] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const alive = useRef(true);
  const pending = useRef<{key: string; id: string} | undefined>(undefined);
  const target = url;
  async function api(payload?: unknown): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(target, {method: payload === undefined ? 'GET' : 'POST',
        headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
        ...(payload === undefined ? {} : {body: JSON.stringify(payload)})});
    } catch {
      throw new Error('Installazione non confermata. Rileggi oppure riprova lo stesso tentativo.');
    }
    if (!response.ok) {
      if (response.status === 409) {
        const result: unknown = await response.json().catch(() => null);
        if (record(result) && result.code === 'exceeds_uninstalled') throw new Error('Quantità superiore al prelevato non installato. Nessuna installazione registrata.');
      }
      throw new Error('Installazione non confermata. Rileggi oppure riprova lo stesso tentativo.');
    }
    return response.json();
  }
  async function read() {
    const value = await api();
    if (!record(value) || ![value.picked, value.installed, value.remainingToInstall].every(decimal)
      || !Array.isArray(value.installations) || !value.installations.every(x => record(x) && record(x.installation)
        && uuid(x.installation.id) && decimal(x.installation.quantity) && ['Pending','Consumed'].includes(x.stockEffect as string)
        && (x.stockEffect === 'Pending' ? x.consumption === null : record(x.consumption)
          && x.consumption.installationId === x.installation.id && x.consumption.quantity === x.installation.quantity))) throw new Error();
    return value as State;
  }
  async function reload() {
    setBusy(true); setError('');
    try {
      const saved = await read();
      if (alive.current) {
        setState(saved);
        if (saved.installations.some(x => x.stockEffect === 'Consumed')) onChanged?.();
        if (saved.installations.some(x => x.installation.id === pending.current?.id && x.stockEffect === 'Consumed')) pending.current = undefined;
      }
    } catch { if (alive.current) { setState(undefined); setError('Stato installazione non disponibile. Rileggi installazioni prima di continuare.'); } }
    finally { if (alive.current) setBusy(false); }
  }
  useEffect(() => { alive.current = true; void reload(); return () => { alive.current = false; }; }, [target, token]);
  async function install(retry?: Entry) {
    if (busy || !state) return;
    const requested = retry?.installation.quantity ?? quantity;
    if (!decimal(requested) || !/[1-9]/.test(requested)) { setError('Inserisci una quantità positiva con massimo sei decimali.'); return; }
    if (retry) pending.current = {key: requested, id: retry.installation.id};
    else if (pending.current?.key !== requested) pending.current = {key: requested, id: crypto.randomUUID()};
    setBusy(true); setError('');
    try {
      await api({id: pending.current.id, quantity: requested});
      try {
        const saved = await read();
        if (alive.current) { setState(saved); if (saved.installations.some(x => x.installation.id === pending.current?.id && x.stockEffect === 'Consumed')) pending.current = undefined; onChanged?.(); }
      } catch { if (alive.current) { setState(undefined); setError('Stato installazione non disponibile. Rileggi installazioni prima di continuare.'); } }
    } catch (failure) { if (alive.current) setError(failure instanceof Error ? failure.message : 'Installazione non confermata.'); }
    finally { if (alive.current) setBusy(false); }
  }
  return <section aria-label="Installazioni">
    <h4>Installazione ricambio</h4>
    <p>Il prelievo o la consegna al tecnico non dimostrano installazione. Quantità esplicita; nessun completamento automatico.</p>
    <label>Quantità da installare<input inputMode="decimal" value={quantity} disabled={busy} onChange={event => setQuantity(event.target.value)}/></label>
    <button disabled={busy || !state} onClick={() => void install()}>Installa quantità esplicita</button>
    <button disabled={busy} onClick={() => void reload()}>Rileggi installazioni</button>
    {state && <div aria-live="polite"><p>Installato: {state.installed}</p><p>Prelevato non installato: {state.remainingToInstall}</p>
      {state.installations.map(x => <div key={x.installation.id}><p>{x.installation.quantity} · {x.stockEffect === 'Consumed' ? 'Consumo confermato' : 'Installazione registrata — consumo in attesa; recupero necessario'}</p>
        {x.stockEffect === 'Pending' && <button disabled={busy} onClick={() => void install(x)}>Recupera consumo</button>}</div>)}</div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
