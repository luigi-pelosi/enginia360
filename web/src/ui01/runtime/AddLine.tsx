import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, decimal, positive, record, uuid, type Order, type Summary } from './contracts';
type Catalog = Readonly<{ id: string; kind: 'Service' | 'Part'; label: string; version: number }>;
export default function AddLine({ order, summary, onSaved, onError }: Readonly<{ order: Order; summary: Summary; onSaved: () => Promise<void>; onError: (error: unknown) => void }>) {
  const [catalog, setCatalog] = useState<readonly Catalog[]>([]), [itemId, setItem] = useState(''), [policy, setPolicy] = useState('');
  const [quantity, setQuantity] = useState(''), [price, setPrice] = useState(''), [discount, setDiscount] = useState('');
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('Catalogo in lettura…'), [blocked, setBlocked] = useState(false);
  const pending = useRef<Record<string, unknown> | undefined>(undefined), active = useRef(true), first = useRef<HTMLInputElement>(null);
  async function loadCatalog() { setBlocked(false); try { const value = await request('/api/v1/workshop/catalog?legalEntityId='+order.legalEntityId+'&siteId='+order.siteId); check(Array.isArray(value)); const rows = value.map(v => { const r = record(v); check(uuid(r.id) && ['Service','Part'].includes(r.kind as string) && typeof r.label === 'string' && positive(r.version)); return r as Catalog; }); if (active.current) { setCatalog(rows); setMessage('Case001: massimo una Service e una Part, unico gruppo ID commessa. Nessun prezzo da catalogo.'); } } catch(e) { if (active.current) { setCatalog([]); setMessage('Catalogo non disponibile: il selettore richiede orders.create. '+(e as Error).message); onError(e); } } }
  useEffect(() => { active.current = true; void loadCatalog(); return () => { active.current = false; }; }, [order.id]);
  const item = catalog.find(c => c.id === itemId);
  const config = /^\d{1,9}$/.test(policy) ? Number(policy) : 0;
  const valid = item && positive(config) && decimal(quantity) && /[1-9]/.test(quantity) && decimal(price) && /^\d{1,3}(?:\.\d{1,2})?$/.test(discount) && Number(discount) <= 100 && !summary.lines.some(l => l.kind === item.kind);
  async function save() {
    if (busy || blocked || (!pending.current && !valid)) { first.current?.focus(); return; }
    setBusy(true); pending.current ??= { id: crypto.randomUUID(), catalogItemId: item!.id, catalogVersion: item!.version, configurationVersion: config, expectedRevision: summary.revision, quantity, unitPrice: price, discountPercent: discount };
    try { const row = record(await request('/api/v1/workshop/orders/'+order.id+'/lines', pending.current)); check(row.id === pending.current.id); pending.current = undefined; setMessage('Scrittura accettata; riepilogo da rileggere.'); await onSaved(); if (active.current) { setQuantity(''); setPrice(''); setDiscount(''); setItem(''); } }
    catch(e) { if (!active.current) return; if (e instanceof ApiError && e.status < 500) { pending.current = undefined; setBlocked(true); } setMessage((e as Error).message+(pending.current ? ' Esito incerto: riprova solo lo stesso comando.' : ' Rileggi e aggiorna prima di un nuovo tentativo.')); onError(e); }
    finally { if (active.current) setBusy(false); }
  }
  return <section className="ui01-group"><h2>Aggiunta persistita</h2><p role="status">{message}</p><p>Versione configurazione righe non esposta dal server: inserire il valore del setup, nessun default o derivazione dal documento. Il server verifica versione e permessi.</p>
    <button disabled={busy || !!pending.current} onClick={() => void loadCatalog()}>Aggiorna catalogo e permesso</button>
    <form onSubmit={e => { e.preventDefault(); void save(); }} onKeyDown={e => { if (e.key === 'Escape' && !pending.current && !busy) { setQuantity(''); setPrice(''); setDiscount(''); setItem(''); first.current?.focus(); } }}>
    <fieldset disabled={busy || !!pending.current || blocked}><label>Articolo / prestazione<select aria-label="Articolo / prestazione" value={itemId} onChange={e => setItem(e.target.value)}><option value="">Seleziona</option>{catalog.map(c => <option key={c.id} value={c.id} disabled={summary.lines.some(l => l.kind === c.kind)}>{c.kind} · {c.label}</option>)}</select></label>
    <label>Versione configurazione righe (setup)<input value={policy} onChange={e => setPolicy(e.target.value)} /></label>
    <label>Quantità<input ref={first} value={quantity} onChange={e => setQuantity(e.target.value)} /></label><label>Prezzo unitario<input value={price} onChange={e => setPrice(e.target.value)} /></label><label>Sconto %<input value={discount} onChange={e => setDiscount(e.target.value)} /></label>
    </fieldset><p>Input esclusi dal riepilogo salvato. Punto decimale; quantità positiva/prezzo non negativo, 6 cifre intere e 6 decimali; sconto 0–100, 2 decimali. Nessun totale client.</p>
    <button disabled={busy || blocked || (!pending.current && !valid)}>{pending.current ? 'Riprova comando identico' : 'Aggiungi riga'}</button></form></section>;
}
