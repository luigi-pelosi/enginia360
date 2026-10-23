import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, positive, record, uuid } from './contracts';
type Authority = Readonly<{ state: 'missing' | 'local' | 'external'; canEdit: boolean; version?: number; sourceId?: string; profileId?: string; direction?: string }>;
type Common = Readonly<{ id: string; legalName: string; fiscalIdentifier: string; registeredOffice: string }>;
export function parseAuthority(value: unknown): Authority {
  const r=record(value);
  check(['missing','local','external'].includes(String(r.state)) && typeof r.canEdit==='boolean');
  if(r.state!=='missing') check(positive(r.version) && uuid(r.sourceId) && uuid(r.profileId) && r.direction===(r.state==='local'?'Enginia360ToExternal':'ExternalToEnginia360'));
  return r as Authority;
}
export default function MasterAuthority({ companyId, counterpartyId, onError }: Readonly<{ companyId: string; counterpartyId?: string; onError: (e: unknown)=>void }>) {
  const [authority,setAuthority]=useState<Authority>(), [message,setMessage]=useState('Verifica autorità…');
  const [common,setCommon]=useState<Common>(), [revision,setRevision]=useState<number>(), [busy,setBusy]=useState(false);
  const generation=useRef(0), pending=useRef<Record<string,unknown> | undefined>(undefined);
  async function load(saved=false) {
    const gen=++generation.current; setAuthority(undefined); setCommon(undefined); setRevision(undefined); setMessage('Verifica autorità…');
    try {
      let value: Authority, rev: number | undefined;
      if(counterpartyId) {
        const state=record(await request('/api/v1/counterparties/'+counterpartyId+'/edit-state?legalEntityId='+companyId));
        const data=record(state.counterparty);
        check(state.state==='ready' && Number.isSafeInteger(state.revision) && (state.revision as number)>=0 && data.id===counterpartyId && ['legalName','fiscalIdentifier','registeredOffice'].every(k=>typeof data[k]==='string'));
        value=parseAuthority(state.authority); rev=state.revision as number;
        if(gen!==generation.current) return;
        setCommon(data as Common); setRevision(rev);
      } else value=parseAuthority(await request('/api/v1/counterparties/authority?legalEntityId='+companyId));
      if(gen!==generation.current) return;
      setAuthority(value); setMessage(saved?'Dati comuni salvati e riletti — revisione '+rev:value.state==='missing'?'Profilo assente: modifica comune bloccata; ricerca e selezione disponibili.':value.state==='external'?'Autorità esterna: modifica locale rifiutata; letture disponibili.':'Enginia360 autorevole: modifica comune soggetta al permesso specifico.');
    } catch(e) { if(gen===generation.current) { setMessage((saved?'Scrittura accettata; dati comuni non verificati. Rileggi autorità. ':'')+(e as Error).message); onError(e); } }
  }
  useEffect(()=>{ pending.current=undefined; void load(); return ()=>{generation.current++;}; },[companyId,counterpartyId]);
  async function save() {
    if(!pending.current && (!common || authority?.state!=='local' || !authority.canEdit || revision===undefined)) return;
    pending.current??={legalEntityId:companyId,commandId:crypto.randomUUID(),authorityVersion:authority!.version,expectedRevision:revision,legalName:common!.legalName,fiscalIdentifier:common!.fiscalIdentifier,registeredOffice:common!.registeredOffice};
    const gen=generation.current; setBusy(true);
    try {
      const outcome=record(await request('/api/v1/counterparties/'+counterpartyId,pending.current,'PUT'));
      check(outcome.state==='applied' || outcome.state==='replayed');
      if(gen!==generation.current) return;
      pending.current=undefined; await load(true);
    } catch(e) {
      if(gen!==generation.current) return;
      if(e instanceof ApiError && e.status<500) {
        pending.current=undefined; setAuthority(undefined); setCommon(undefined);
        setMessage(e.code==='external'?'Autorità esterna: modifica locale rifiutata. Rileggi autorità.':e.code==='missing'?'Profilo assente: modifica comune rifiutata. Rileggi autorità.':(e as Error).message+' Rileggi autorità.');
      } else setMessage('Esito modifica incerto: riprova solo il comando identico.');
      onError(e);
    } finally { setBusy(false); }
  }
  const editable=authority?.state==='local' && authority.canEdit;
  return <section><h2>Autorità anagrafica condivisa</h2><p role="status">{message}</p>
    {authority?.version && <p>Versione {authority.version} · {authority.direction}<br/>Sorgente {authority.sourceId}<br/>Profilo {authority.profileId}</p>}
    {authority && !authority.canEdit && <p>Permesso specifico di modifica comune assente.</p>}
    <button type="button" disabled={busy || !!pending.current} onClick={()=>void load()}>Rileggi autorità</button>
    {common && editable && <form onSubmit={e=>{e.preventDefault();void save();}}><fieldset disabled={busy || !!pending.current}>
      <label>Denominazione comune<input aria-label="Denominazione comune" maxLength={200} required value={common.legalName} onChange={e=>setCommon({...common,legalName:e.target.value})}/></label>
      <label>Identificativo fiscale comune<input aria-label="Identificativo fiscale comune" maxLength={100} required value={common.fiscalIdentifier} onChange={e=>setCommon({...common,fiscalIdentifier:e.target.value})}/></label>
      <label>Sede legale comune<input aria-label="Sede legale comune" maxLength={500} required value={common.registeredOffice} onChange={e=>setCommon({...common,registeredOffice:e.target.value})}/></label>
      <p>Modifica dell'identità condivisa nel tenant, non della testata o degli importi salvati.</p></fieldset>
      <button disabled={busy}>{pending.current?'Riprova modifica identica':'Salva dati comuni'}</button></form>}
  </section>;
}
