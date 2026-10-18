import { FormEvent, useRef, useState } from 'react';
type Destination = {id:string;counterpartyId:string;ownerLegalEntityId:string;address:string;published:boolean};
type Company = { legalEntityId: string; legalEntityName: string };
type Counterparty = { id:string; tenantId:string; legalName:string; fiscalIdentifier:string; registeredOffice:string };
const uuid = (value:unknown): value is string => typeof value==='string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const text = (value:unknown, max:number): value is string => typeof value==='string' && value.trim().length>0 && value.length<=max;
function companyList(value:unknown): Company[] {
    if(!Array.isArray(value) || !value.every(x=>x && uuid(x.legalEntityId) && text(x.legalEntityName,100))) throw new Error('Invalid companies');
    return value as Company[];
}
function counterpartyList(value:unknown): Counterparty[] {
    if(!Array.isArray(value) || !value.every(x=>x && uuid(x.id) && uuid(x.tenantId) && text(x.legalName,200) && text(x.fiscalIdentifier,100) && text(x.registeredOffice,500))) throw new Error('Invalid counterparties');
    return value as Counterparty[];
}
function destinationList(value:unknown): Destination[] {
    if(!Array.isArray(value) || !value.every(x=>x && uuid(x.id) && uuid(x.counterpartyId) && uuid(x.ownerLegalEntityId) && text(x.address,500) && typeof x.published==='boolean')) throw new Error('Invalid destinations');
    return value as Destination[];
}
export default function B03TestApp() {
    const [username,setUsername]=useState('');
    const [password,setPassword]=useState('');
    const [token,setToken]=useState('');
    const [companies,setCompanies]=useState<Company[]>([]);
    const [company,setCompany]=useState<Company>();
    const [rows,setRows]=useState<Counterparty[]>([]);
    const [error,setError]=useState('');
    const [current,setCurrent]=useState<Counterparty>();
    const [destinations,setDestinations]=useState<Destination[]>([]);
    const [address,setAddress]=useState('');
    const [editing,setEditing]=useState<Counterparty>();
    const generation=useRef(0);
    async function login(event:FormEvent) {
        event.preventDefault(); setError('');
        try {
            const response=await fetch('/api/v1/development/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});
            if(!response.ok) throw new Error();
            const body=await response.json() as {accessToken:unknown};
            if(!text(body?.accessToken,16000)) throw new Error();
            const contexts=await fetch('/api/v1/counterparties/companies',{headers:{Authorization:`Bearer ${body.accessToken}`}});
            if(!contexts.ok) throw new Error();
            const list=companyList(await contexts.json());
            setCompanies([...new Map(list.map(x=>[x.legalEntityId,x])).values()]);
            setToken(body.accessToken); setPassword('');
        } catch { setError('Accesso non riuscito. Riprova con una identità sintetica autorizzata.'); }
    }
    async function select(selected:Company) {
        const version=++generation.current;
        setRows([]); setEditing(undefined); setCurrent(undefined); setDestinations([]); setCompany(selected); setError('');
        try {
            const response=await fetch(`/api/v1/counterparties?legalEntityId=${selected.legalEntityId}`,{headers:{Authorization:`Bearer ${token}`}});
            if(!response.ok) throw new Error();
            const data=counterpartyList(await response.json());
            if(version===generation.current) setRows(data);
        } catch { if(version===generation.current) setError('Lettura non autorizzata o non disponibile. Seleziona una società autorizzata e riprova.'); }
    }
    async function loadDestinations(cp:Counterparty) {
        if(!company) return;
        const version=++generation.current;
        setCurrent(cp); setDestinations([]); setError('');
        try {
            const response=await fetch(`/api/v1/counterparties/${cp.id}/destinations?legalEntityId=${company.legalEntityId}`,{headers:{Authorization:`Bearer ${token}`}});
            if(!response.ok) throw new Error();
            const data=destinationList(await response.json());
            if(version===generation.current) setDestinations(data);
        } catch { if(version===generation.current) setError('Destinazioni non disponibili. Riprova con una società autorizzata.'); }
    }
    async function createDestination(event:FormEvent) {
        event.preventDefault(); if(!company || !current) return; setError('');
        const version=generation.current;
        try {
            const response=await fetch(`/api/v1/counterparties/${current.id}/destinations`,{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify({legalEntityId:company.legalEntityId,address})});
            if(!response.ok) throw new Error();
            if(version===generation.current) { setAddress(''); await loadDestinations(current); }
        } catch { if(version===generation.current) setError('Destinazione non salvata. Verifica indirizzo e permessi, quindi riprova.'); }
    }
    async function publish(destination:Destination) {
        if(!company || !current) return; setError('');
        const version=generation.current;
        try {
            const response=await fetch(`/api/v1/counterparties/destinations/${destination.id}/publication`,{method:'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify({legalEntityId:company.legalEntityId})});
            if(!response.ok) throw new Error();
            if(version===generation.current) await loadDestinations(current);
        } catch { if(version===generation.current) setError('Pubblicazione rifiutata. Serve il permesso specifico sulla società proprietaria; sede o magazzino non bastano.'); }
    }
    async function saveCommon(event:FormEvent) {
        event.preventDefault(); if(!editing || !company) return; setError('');
        const version=generation.current;
        try {
            const response=await fetch(`/api/v1/counterparties/${editing.id}`,{method:'PUT',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:JSON.stringify({legalEntityId:company.legalEntityId,legalName:editing.legalName,fiscalIdentifier:editing.fiscalIdentifier,registeredOffice:editing.registeredOffice})});
            if(!response.ok) throw new Error();
            if(version===generation.current) { setEditing(undefined); await select(company); }
        } catch { if(version===generation.current) setError('Modifica comune rifiutata. Serve il permesso specifico; verifica i campi e riprova.'); }
    }
    return <main><h1>Controparti · prova privata B03</h1><p>Solo identità e dati sintetici. Nessuna validazione fiscale.</p>
      {!token ? <form onSubmit={login} className="status-card form">
        <label>Utente sintetico<input required value={username} onChange={e=>setUsername(e.target.value)}/></label>
        <label>Password sintetica<input required type="password" value={password} onChange={e=>setPassword(e.target.value)}/></label>
        <button>Accedi</button></form> : <>
        <section aria-label="Società autorizzate">{companies.map(x=><button key={x.legalEntityId} onClick={()=>void select(x)}>{x.legalEntityName}</button>)}</section>
        {company && <p>Società selezionata: {company.legalEntityName}</p>}
        {rows.map(x=><section key={x.id} className="status-card"><h2>{x.legalName}</h2><p>{x.fiscalIdentifier}</p><p>{x.registeredOffice}</p><small>Identità comune: {x.id}</small><button onClick={()=>void loadDestinations(x)}>Destinazioni</button><button onClick={()=>setEditing({...x})}>Modifica campi comuni</button></section>)}
        {editing && <form onSubmit={saveCommon} className="status-card form"><p>La modifica interessa l’anagrafica comune alle società del tenant.</p>
          <label>Ragione sociale comune<input required maxLength={200} value={editing.legalName} onChange={e=>setEditing({...editing,legalName:e.target.value})}/></label>
          <label>Identificativo fiscale comune<input required maxLength={100} value={editing.fiscalIdentifier} onChange={e=>setEditing({...editing,fiscalIdentifier:e.target.value})}/></label>
          <label>Sede legale comune<input required maxLength={500} value={editing.registeredOffice} onChange={e=>setEditing({...editing,registeredOffice:e.target.value})}/></label>
          <button>Salva campi comuni</button></form>}
        {current && <section><h2>Destinazioni di {current.legalName}</h2>
          {destinations.map(x=><article key={x.id}><p>{x.address}</p><p>{x.published?'Condivisa nel tenant':'Riservata alla società proprietaria'}</p>{!x.published && x.ownerLegalEntityId===company?.legalEntityId && <button onClick={()=>void publish(x)}>Condividi nel tenant</button>}</article>)}
          <form onSubmit={createDestination} className="status-card form"><label>Indirizzo operativo<input required maxLength={500} value={address} onChange={e=>setAddress(e.target.value)}/></label><button>Aggiungi destinazione privata</button></form>
        </section>}
      </>}{error && <p role="alert">{error}</p>}</main>;
}
