import { useEffect, useRef, useState } from "react";
import B07Picking from './B07Picking';
import B09CarcassReturn from './B09CarcassReturn';

type State = { physical: string; available: string; reserved: string; remaining: string; reservations: { id: string }[] };
type Warehouse = { id: string; name: string };
type Props = { order: { id: string; legalEntityId: string; siteId: string }; line: { id: string; catalogVersion: number }; token: string };
const record = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null;
const uuid = (x: unknown): x is string => typeof x === 'string' && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(x);
const decimal = (x: unknown): x is string => typeof x === 'string' && /^\d{1,6}(\.\d{1,6})?$/.test(x);

export default function B06Reservations({ order, line, token }: Props) {
  const [warehouses, setWarehouses] = useState<Warehouse[]>([]);
  const [warehouse, setWarehouse] = useState('');
  const [quantity, setQuantity] = useState('');
  const [state, setState] = useState<State>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef<{ key: string; id: string } | undefined>(undefined);
  const generation = useRef(0);
  const [installed, setInstalled] = useState(0);
  const url = `/api/v1/inventory/orders/${order.id}/lines/${line.id}`;
  async function api(path: string, payload?: unknown) {
    const response = await fetch(path, {
      method: payload === undefined ? 'GET' : 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      ...(payload === undefined ? {} : { body: JSON.stringify(payload) })
    });
    if (!response.ok) {
      if (response.status === 409) {
        const value: unknown = await response.json();
        if (record(value) && value.code === 'insufficient_available') throw new Error('Disponibilità insufficiente. Nessuna prenotazione eseguita.');
        if (record(value) && value.code === 'exceeds_remaining') throw new Error('La quantità supera il residuo della riga.');
      }
      throw new Error('Operazione non confermata. Rileggi lo stato o riprova lo stesso tentativo.');
    }
    return response.json() as Promise<unknown>;
  }
  async function read(selected: string): Promise<State> {
    const value = await api(url + '?warehouseId=' + selected);
    if (!record(value) || !['physical', 'available', 'reserved', 'remaining'].every(k => decimal(value[k]))
      || !Array.isArray(value.reservations) || !value.reservations.every(x => record(x) && uuid(x.id))) throw new Error();
    return value as State;
  }
  async function reload(selected = warehouse) {
    const current = ++generation.current;
    setBusy(true); setError(''); setState(undefined);
    try {
      const rows = await api(`/api/v1/inventory/warehouses?legalEntityId=${order.legalEntityId}&siteId=${order.siteId}`);
      if (!Array.isArray(rows) || !rows.every(x => record(x) && uuid(x.id) && typeof x.name === 'string' && x.name.length <= 200)) throw new Error();
      const saved = selected && rows.some(x => x.id === selected) ? await read(selected) : undefined;
      if (current === generation.current) {
        setWarehouses(rows); setState(saved);
        if (saved?.reservations.some(x => x.id === pending.current?.id)) pending.current = undefined;
      }
    } catch { if (current === generation.current) setError('Stato non disponibile. Rileggi prenotazioni o riseleziona il contesto.'); }
    finally { if (current === generation.current) setBusy(false); }
  }
  useEffect(() => { void reload(''); return () => { generation.current++; }; }, [order.id, line.id, token]);
  async function reserve() {
    if (busy || !state || !warehouse) return;
    if (!decimal(quantity) || !/[1-9]/.test(quantity)) { setError('Inserisci una quantità positiva con massimo sei decimali.'); return; }
    const key = JSON.stringify([warehouse, quantity, line.catalogVersion]);
    if (pending.current?.key !== key) pending.current = {key, id: crypto.randomUUID()};
    const current = generation.current;
    setBusy(true); setError('');
    try {
      await api(url + '/reservations', {id: pending.current.id, warehouseId: warehouse, quantity, catalogVersion: line.catalogVersion});
      // Keep the command ID until the committed state is reread, including a lost response.
      try {
        const saved = await read(warehouse);
        if (current === generation.current) { setState(saved); pending.current = undefined; }
      } catch {
        if (current === generation.current) { setState(undefined); setError('Stato non disponibile. Rileggi prenotazioni prima di continuare.'); }
      }
    } catch (failure) { if (current === generation.current) setError(failure instanceof Error ? failure.message : 'Operazione non confermata.'); }
    finally { if (current === generation.current) setBusy(false); }
  }
  return <section aria-label="Prenotazioni">
    <h3>Prenotazione ricambio</h3>
    <p>Quantità esplicita, mai ridotta automaticamente. Nessun prelievo o consumo.</p>
    <label>Magazzino prenotazione<select value={warehouse} disabled={busy} onChange={event => { setWarehouse(event.target.value); void reload(event.target.value); }}>
      <option value="">Seleziona</option>{warehouses.map(x => <option key={x.id} value={x.id}>{x.name}</option>)}
    </select></label>
    <label>Quantità da prenotare<input inputMode="decimal" value={quantity} disabled={busy} onChange={event => setQuantity(event.target.value)}/></label>
    <button disabled={busy || !state || !warehouse} onClick={() => void reserve()}>Prenota quantità esplicita</button>
    <button disabled={busy} onClick={() => void reload()}>Rileggi prenotazioni</button>
    {state && <div aria-live="polite"><p>Fisico: {state.physical}</p><p>Disponibile: {state.available}</p><p>Prenotato sulla riga: {state.reserved}</p><p>Residuo da prenotare: {state.remaining}</p></div>}
    {import.meta.env.VITE_B07_TEST_UI === 'true' && state?.reservations.map(x =>
      <B07Picking key={x.id} url={url} reservationId={x.id} token={token} onChanged={() => { setInstalled(value => value + 1); const current = generation.current; void read(warehouse).then(saved => { if (current === generation.current) setState(saved); }).catch(() => { if (current === generation.current) { setState(undefined); setError('Stato stock non disponibile. Rileggi prenotazioni.'); } }); }}/>) }
    {import.meta.env.VITE_B09_TEST_UI === 'true' && state && warehouse &&
      <B09CarcassReturn url={url} orderId={order.id} warehouse={warehouse} token={token} refresh={installed}/>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
