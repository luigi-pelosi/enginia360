import { useEffect, useRef, useState } from 'react';
import { request } from './workshopApi';
import { check, positive, record, uuid } from './contracts';
type Scope = Readonly<{ legalEntityId: string; siteId: string; label: string }>;
type Item = Readonly<{ id: string; revision: number; closed: boolean }>;
// Read-only reopening: own organization scopes (not the create-only workshop contexts) + exact workshop.orders.read on the list endpoint.
export default function OrderList({ onOpen, onError }: Readonly<{ onOpen: (id: string) => void; onError: (error: unknown) => void }>) {
  const [scopes, setScopes] = useState<readonly Scope[]>([]), [selected, setSelected] = useState('0'), [items, setItems] = useState<readonly Item[]>([]);
  const [message, setMessage] = useState('Elenco commesse non caricato.'), [busy, setBusy] = useState(false), [trail, setTrail] = useState<readonly string[]>([]), [full, setFull] = useState(false);
  const generation = useRef(0);
  useEffect(() => { let active = true; void request('/api/v1/organization/contexts').then(value => {
    check(Array.isArray(value));
    const seen = new Set<string>(), rows: Scope[] = [];
    for (const v of value) { const r = record(v); check(uuid(r.legalEntityId) && uuid(r.siteId)); const key = r.legalEntityId + ':' + r.siteId; if (seen.has(key)) continue; seen.add(key); rows.push({ legalEntityId: r.legalEntityId, siteId: r.siteId, label: String(r.legalEntityName) + ' / ' + String(r.siteName) }); }
    if (active) setScopes(rows);
  }).catch(e => { if (active) onError(e); }); return () => { active = false; generation.current++; }; }, []);
  async function load(after: string, nextTrail: readonly string[]) {
    const scope = scopes[Number(selected)]; if (!scope) { setMessage('Nessun contesto assegnato.'); return; }
    const gen = ++generation.current; setBusy(true); setMessage('Lettura elenco…'); setItems([]);
    try {
      const raw = await request('/api/v1/workshop/orders?legalEntityId=' + scope.legalEntityId + '&siteId=' + scope.siteId + (after ? '&after=' + after : ''));
      check(Array.isArray(raw) && raw.length <= 20);
      const parsed = raw.map(v => { const r = record(v); check(uuid(r.id) && typeof r.closed === 'boolean' && Number.isSafeInteger(r.revision) && positive((r.revision as number) + 1)); return { id: r.id as string, revision: r.revision as number, closed: r.closed as boolean }; });
      if (gen !== generation.current) return;
      setItems(parsed); setTrail(nextTrail); setFull(parsed.length === 20); setMessage(parsed.length ? 'Commesse del contesto autorizzato' : 'Nessuna commessa in questa pagina.');
    } catch (e) { if (gen === generation.current) { setMessage((e as Error).message); onError(e); } } finally { if (gen === generation.current) setBusy(false); }
  }
  return <details open><summary>Riapri commessa</summary>
    <label>Contesto<select aria-label="Contesto elenco" value={selected} onChange={e => { setSelected(e.target.value); setItems([]); setTrail([]); }}>{scopes.map((s, i) => <option key={i} value={i}>{s.label}</option>)}</select></label>
    <button disabled={busy || scopes.length === 0} onClick={() => void load('', [])}>Elenca commesse</button>
    <p role="status">{message}</p>
    <ul>{items.map(i => <li key={i.id}><button onClick={() => onOpen(i.id)}>Apri {i.id}</button> rev {i.revision}{i.closed ? ' · chiusa' : ''}</li>)}</ul>
    <button disabled={busy || trail.length === 0} onClick={() => { const t = trail.slice(0, -1); void load(t.at(-1) ?? '', t); }}>Pagina precedente</button>
    <button disabled={busy || !full} onClick={() => void load(items.at(-1)!.id, [...trail, items.at(-1)!.id])}>Pagina successiva</button></details>;
}
