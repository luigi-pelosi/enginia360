import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, positive, record, uuid } from './contracts';
type Context = Readonly<{ legalEntityId: string; legalEntityName: string; siteId: string; siteName: string }>;
type Choice = Readonly<{ id: string; label: string; version?: number; directCreationEnabled?: boolean }>;
function choices(value: unknown, label: string, versioned = false): Choice[] {
  check(Array.isArray(value)); return value.map(v => { const r = record(v); check(uuid(r.id) && typeof r[label] === 'string' && (!versioned || (positive(r.version) && typeof r.directCreationEnabled === 'boolean'))); return { id: r.id, label: r[label] as string, version: r.version as number | undefined, directCreationEnabled: r.directCreationEnabled as boolean | undefined }; });
}
export default function CreateOrder({ onCreated, onError }: Readonly<{ onCreated: (id: string) => Promise<void>; onError: (error: unknown) => void }>) {
  const [contexts, setContexts] = useState<readonly Context[]>([]), [scope, setScope] = useState('');
  const [types, setTypes] = useState<Choice[]>([]), [payers, setPayers] = useState<Choice[]>([]), [vehicles, setVehicles] = useState<Choice[]>([]);
  const [documentTypeId, setType] = useState(''), [payerId, setPayer] = useState(''), [vehicleId, setVehicle] = useState(''), [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('Caricamento contesti…');
  const pending = useRef<Record<string, unknown> | undefined>(undefined), generation = useRef(0);
  async function loadContexts() {
    try { const values = await request('/api/v1/workshop/contexts'); check(Array.isArray(values)); const rows = values.map(v => { const r = record(v); check(uuid(r.legalEntityId) && uuid(r.siteId) && typeof r.legalEntityName === 'string' && typeof r.siteName === 'string'); return r as Context; }); setContexts(rows); setScope(rows.length ? '0' : ''); setMessage(rows.length ? 'Contesti di creazione verificati; autorizzazione rivalutata al comando.' : 'Nessun contesto di creazione. La lettura per UUID resta disponibile.'); } catch(e) { setMessage((e as Error).message); onError(e); }
  }
  useEffect(() => { void loadContexts(); return () => { generation.current++; }; }, []);
  useEffect(() => { const gen = ++generation.current; setTypes([]); setPayers([]); setVehicles([]); setType(''); setPayer(''); setVehicle(''); const c = contexts[Number(scope)]; if (scope === '' || !c) return;
    void (async () => { try { const q = '?legalEntityId='+c.legalEntityId+'&siteId='+c.siteId; const [t,v,p] = await Promise.all([request('/api/v1/workshop/document-types'+q), request('/api/v1/workshop/vehicles'+q), request('/api/v1/counterparties?legalEntityId='+c.legalEntityId+'&search=')]); if (gen !== generation.current) return; setTypes(choices(t,'name',true)); setVehicles(choices(v,'label')); setPayers(choices(p,'legalName')); } catch(e) { if (gen === generation.current) { setMessage((e as Error).message); onError(e); } } })();
  }, [scope, contexts]);
  async function create() {
    const c = contexts[Number(scope)], type = types.find(t => t.id === documentTypeId);
    if (!pending.current && (!c || !type?.directCreationEnabled || !payerId || !vehicleId)) return;
    setBusy(true);
    pending.current ??= { id: crypto.randomUUID(), legalEntityId: c.legalEntityId, siteId: c.siteId, documentTypeId, configurationVersion: type!.version, payerId, vehicleId };
    try { const response = record(await request('/api/v1/workshop/orders', pending.current)); check(response.id === pending.current.id); const id = response.id as string; pending.current = undefined; await onCreated(id); }
    catch(e) {
      if (e instanceof ApiError && e.status < 500) {
        pending.current = undefined; setTypes([]); setType('');
        setMessage((e as Error).message+' Aggiorna contesti e configurazione prima di ricreare.');
      } else setMessage('Esito da riconciliare. UUID: '+pending.current?.id+'. Riprova invia solo lo stesso comando. '+(e as Error).message);
      onError(e);
    }
    finally { setBusy(false); }
  }
  return <section><h2>Nuova commessa</h2><p role="status">{message}</p><button type="button" disabled={busy || !!pending.current} onClick={() => void loadContexts()}>Aggiorna contesti</button>
    <form onSubmit={e => { e.preventDefault(); void create(); }}><fieldset disabled={busy || !!pending.current}><label>Società / sede<select value={scope} onChange={e => setScope(e.target.value)}><option value="">Seleziona</option>{contexts.map((c,i) => <option key={c.legalEntityId+c.siteId} value={i}>{c.legalEntityName} / {c.siteName}</option>)}</select></label>
    <label>Tipo documento<select aria-label="Tipo documento" value={documentTypeId} onChange={e => setType(e.target.value)}><option value="">Seleziona</option>{types.map(t => <option key={t.id} value={t.id} disabled={!t.directCreationEnabled}>{t.label} · v{t.version}</option>)}</select></label>
    <label>Ricerca pagante<input maxLength={200} value={search} onChange={e => setSearch(e.target.value)} /></label><button type="button" onClick={() => { const c = contexts[Number(scope)]; if (c) void request('/api/v1/counterparties?legalEntityId='+c.legalEntityId+'&search='+encodeURIComponent(search)).then(v => setPayers(choices(v,'legalName'))).catch(onError); }}>Cerca pagante</button>
    <label>Pagante<select aria-label="Pagante" value={payerId} onChange={e => setPayer(e.target.value)}><option value="">Seleziona</option>{payers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}</select></label>
    <label>Veicolo<select aria-label="Veicolo" value={vehicleId} onChange={e => setVehicle(e.target.value)}><option value="">Seleziona</option>{vehicles.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}</select></label><p>L'intestatario è risolto dal server; non cambia il pagante.</p></fieldset>
    <button disabled={busy || (!pending.current && (!documentTypeId || !payerId || !vehicleId))}>{pending.current ? 'Riprova comando identico' : 'Crea commessa'}</button></form></section>;
}
