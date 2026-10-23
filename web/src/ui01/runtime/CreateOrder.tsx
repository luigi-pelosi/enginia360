import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, positive, record, uuid } from './contracts';
import MasterSearch, { type MasterChoice } from './MasterSearch';
import MasterAuthority from './MasterAuthority';
type Context = Readonly<{ legalEntityId: string; legalEntityName: string; siteId: string; siteName: string }>;
type Choice = Readonly<{ id: string; label: string; version?: number; directCreationEnabled?: boolean }>;
function choices(value: unknown, label: string, versioned = false): Choice[] {
  check(Array.isArray(value)); return value.map(v => { const r = record(v); check(uuid(r.id) && typeof r[label] === 'string' && (!versioned || (positive(r.version) && typeof r.directCreationEnabled === 'boolean'))); return { id: r.id, label: r[label] as string, version: r.version as number | undefined, directCreationEnabled: r.directCreationEnabled as boolean | undefined }; });
}
export default function CreateOrder({ onCreated, onError }: Readonly<{ onCreated: (id: string) => Promise<void>; onError: (error: unknown) => void }>) {
  const [contexts, setContexts] = useState<readonly Context[]>([]), [scope, setScope] = useState('');
  const [types, setTypes] = useState<Choice[]>([]), [payer, setPayer] = useState<MasterChoice>(), [vehicle, setVehicle] = useState<MasterChoice>();
  const [documentTypeId, setType] = useState('');
  const payerId = payer?.id, vehicleId = vehicle?.id;
  const context = scope === '' ? undefined : contexts[Number(scope)];
  const payerEndpoint = context ? '/api/v1/counterparties?legalEntityId='+context.legalEntityId : undefined;
  const vehicleEndpoint = context ? '/api/v1/workshop/vehicles?legalEntityId='+context.legalEntityId+'&siteId='+context.siteId : undefined;
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('Caricamento contesti…');
  const pending = useRef<Record<string, unknown> | undefined>(undefined), generation = useRef(0), contextGeneration = useRef(0);
  async function loadContexts() {
    const gen = ++contextGeneration.current;
    setContexts([]); setScope('');
    try { const values = await request('/api/v1/workshop/contexts'); check(Array.isArray(values)); const rows = values.map(v => { const r = record(v); check(uuid(r.legalEntityId) && uuid(r.siteId) && typeof r.legalEntityName === 'string' && typeof r.siteName === 'string'); return r as Context; }); if (gen !== contextGeneration.current) return; setContexts(rows); setScope(rows.length ? '0' : ''); setMessage(rows.length ? 'Contesti di creazione verificati; autorizzazione rivalutata al comando.' : 'Nessun contesto di creazione. La lettura per UUID resta disponibile.'); } catch(e) { if (gen === contextGeneration.current) { setMessage((e as Error).message); onError(e); } }
  }
  useEffect(() => { void loadContexts(); return () => { generation.current++; contextGeneration.current++; }; }, []);
  useEffect(() => { const gen = ++generation.current; setTypes([]); setType(''); setPayer(undefined); setVehicle(undefined); const c = contexts[Number(scope)]; if (scope === '' || !c) return;
    void (async () => { try { const q = '?legalEntityId='+c.legalEntityId+'&siteId='+c.siteId; const t = await request('/api/v1/workshop/document-types'+q); if (gen !== generation.current) return; setTypes(choices(t,'name',true)); } catch(e) { if (gen === generation.current) { setMessage((e as Error).message); onError(e); } } })();
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
    <form onSubmit={e => { e.preventDefault(); void create(); }}><fieldset disabled={busy || !!pending.current}><label>Società / sede<select aria-label="Società / sede" value={scope} onChange={e => setScope(e.target.value)}><option value="">Seleziona</option>{contexts.map((c,i) => <option key={c.legalEntityId+c.siteId} value={i}>{c.legalEntityName} / {c.siteName}</option>)}</select></label>
    <label>Tipo documento<select aria-label="Tipo documento" value={documentTypeId} onChange={e => setType(e.target.value)}><option value="">Seleziona</option>{types.map(t => <option key={t.id} value={t.id} disabled={!t.directCreationEnabled}>{t.label} · v{t.version}</option>)}</select></label>
    <MasterSearch key={'payer:'+(vehicleEndpoint ?? 'none')} endpoint={payerEndpoint} label="Pagante" legalName value={payer} onChange={setPayer} onError={onError} />
    <MasterSearch key={vehicleEndpoint ?? 'no-vehicle-context'} endpoint={vehicleEndpoint} label="Veicolo" value={vehicle} onChange={setVehicle} onError={onError} />
    <p>L'intestatario è risolto dal server; non cambia il pagante.</p></fieldset>
    <button disabled={busy || (!pending.current && (!documentTypeId || !payerId || !vehicleId))}>{pending.current ? 'Riprova comando identico' : 'Crea commessa'}</button></form>{context && <MasterAuthority key={context.legalEntityId} companyId={context.legalEntityId} counterpartyId={payerId} onError={onError} />}</section>;
}
