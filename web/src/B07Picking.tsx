import { useEffect, useRef, useState } from 'react';

type Pick = { id: string; quantity: string; originLocation: string; placementLocation: string | null; pickingListId: string };
type State = { reservationId: string; reserved: string; picked: string; remainingToPick: string; picks: Pick[] };
const record = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const decimal = (x: unknown): x is string => typeof x === 'string' && /^\d{1,6}(\.\d{1,6})?$/.test(x);
const uuid = (x: unknown): x is string => typeof x === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(x);

export default function B07Picking({url, reservationId, token}: {url: string; reservationId: string; token: string}) {
  const [state, setState] = useState<State>();
  const [quantity, setQuantity] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const alive = useRef(true);
  const pending = useRef<{key: string; id: string} | undefined>(undefined);
  const target = `${url}/reservations/${reservationId}/picks`;
  async function api(payload?: unknown): Promise<unknown> {
    let response: Response;
    try {
      response = await fetch(target, {method: payload === undefined ? 'GET' : 'POST',
        headers: {Authorization: `Bearer ${token}`, 'Content-Type': 'application/json'},
        ...(payload === undefined ? {} : {body: JSON.stringify(payload)})});
    } catch {
      throw new Error('Prelievo non confermato. Rileggi oppure riprova lo stesso tentativo.');
    }
    if (!response.ok) {
      if (response.status === 409) {
        const result: unknown = await response.json().catch(() => null);
        if (record(result) && result.code === 'exceeds_unpicked') throw new Error('Quantità superiore al residuo prenotato da prelevare. Nessun prelievo eseguito.');
      }
      throw new Error('Prelievo non confermato. Rileggi oppure riprova lo stesso tentativo.');
    }
    return response.json();
  }
  async function read() {
    const value = await api();
    if (!record(value) || value.reservationId !== reservationId || ![value.reserved, value.picked, value.remainingToPick].every(decimal)
      || !Array.isArray(value.picks) || !value.picks.every(x => record(x) && uuid(x.id) && uuid(x.pickingListId) && decimal(x.quantity)
        && typeof x.originLocation === 'string' && x.originLocation.length <= 100
        && (x.placementLocation === null || typeof x.placementLocation === 'string' && x.placementLocation.length <= 100))) throw new Error();
    return value as State;
  }
  async function reload() {
    setBusy(true); setError('');
    try {
      const saved = await read();
      if (alive.current) {
        setState(saved);
        if (saved.picks.some(x => x.id === pending.current?.id)) pending.current = undefined;
      }
    } catch { if (alive.current) { setState(undefined); setError('Stato prelievo non disponibile. Rileggi prelievi prima di continuare.'); } }
    finally { if (alive.current) setBusy(false); }
  }
  useEffect(() => { alive.current = true; void reload(); return () => { alive.current = false; }; }, [target, token]);
  async function pick() {
    if (busy || !state) return;
    if (!decimal(quantity) || !/[1-9]/.test(quantity)) { setError('Inserisci una quantità positiva con massimo sei decimali.'); return; }
    if (pending.current?.key !== quantity) pending.current = {key: quantity, id: crypto.randomUUID()};
    setBusy(true); setError('');
    try {
      await api({id: pending.current.id, quantity});
      try {
        const saved = await read();
        if (alive.current) { setState(saved); pending.current = undefined; }
      } catch { if (alive.current) { setState(undefined); setError('Stato prelievo non disponibile. Rileggi prelievi prima di continuare.'); } }
    } catch (failure) { if (alive.current) setError(failure instanceof Error ? failure.message : 'Prelievo non confermato.'); }
    finally { if (alive.current) setBusy(false); }
  }
  return <section aria-label="Prelievi">
    <h3>Prelievo ricambio</h3>
    <p>Prenotazione: {reservationId}. Prelievo distinto da consegna, installazione e consumo.</p>
    <label>Quantità da prelevare<input inputMode="decimal" value={quantity} disabled={busy} onChange={event => setQuantity(event.target.value)}/></label>
    <button disabled={busy || !state} onClick={() => void pick()}>Preleva quantità esplicita</button>
    <button disabled={busy} onClick={() => void reload()}>Rileggi prelievi</button>
    {state && <div aria-live="polite"><p>Prelevato: {state.picked}</p><p>Ancora prenotato da prelevare: {state.remainingToPick}</p>
      {state.picks.map(x => <p key={x.id}>Lista prelievo {x.pickingListId} · {x.quantity} · Origine: {x.originLocation} · {x.placementLocation === null ? 'Senza area di preparazione; nessun transito' : `Collocazione interna: ${x.placementLocation}`}</p>)}</div>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
