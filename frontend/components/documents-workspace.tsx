"use client";
import React, { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { HttpFailure, readJson } from "../lib/organization";
import { documentsPath, documentsReadPath, type DocumentsData, type DocumentsQuery, type DocumentLine, type CatalogChoice } from "../lib/documents";
import { effectLabels, type DocumentTypeVersion } from "../lib/document-types";

type Frozen = { readonly path: string; readonly body: string; readonly operation: string; readonly query: DocumentsQuery; uncertain: boolean };
const refusalMessages: Readonly<Record<string,string>> = {
 insufficient_stock: "Conferma rifiutata: quantità insufficienti. La bozza è conservata e nessuna riga è stata movimentata.",
 config_changed: "La configurazione del tipo o della società è cambiata. Rileggi e verifica il nuovo effetto prima di confermare nuovamente.",
 catalog_changed: "Un articolo o servizio è cambiato. Seleziona la versione corrente e salva esplicitamente la bozza.",
 draft_requires_save: "Il tipo corrente richiede magazzini differenti. Modifica e salva la bozza prima della conferma.",
 quantity_overflow: "Quantità oltre il limite tecnico di memorizzazione: nessuna modifica applicata.",
 already_confirmed: "Documento già confermato: nessun secondo movimento. Rileggi il fatto esistente.",
};
class DocumentFailure extends HttpFailure { constructor(status:number,public state:string){super(status);} }
export function DocumentsWorkspace({initial}:{initial:{status:number;data:DocumentsData|null;query:DocumentsQuery}}) {
 const [data,setData]=useState(initial.data); const [query,setQuery]=useState(initial.query); const [status,setStatus]=useState(initial.status);
 const [hydrated,setHydrated]=useState(false); const [busy,setBusy]=useState(false); const [pending,setPending]=useState<Frozen|null>(null); const fence=useRef<Frozen|null>(null);
 const [message,setMessage]=useState(""); const [creating,setCreating]=useState(false);
 const [title,setTitle]=useState(initial.data?.detail?.title || ""); const [typeId,setTypeId]=useState(initial.data?.detail?.documentTypeId || "");
 const [lines,setLines]=useState<ReadonlyArray<DocumentLine>>(initial.data?.detail?.lines || []);
 const [catalog,setCatalog]=useState<ReadonlyArray<CatalogChoice>>(initial.data?.catalog || []);
 const [types,setTypes]=useState<ReadonlyArray<DocumentTypeVersion>>(initial.data?.types || []);
 const [catalogSearch,setCatalogSearch]=useState(""); const [typeSearch,setTypeSearch]=useState("");
 const [catalogAfter,setCatalogAfter]=useState<string|undefined>(); const [typeAfter,setTypeAfter]=useState<string|undefined>();
 useEffect(()=>{setHydrated(true);},[]);
 useEffect(()=>{
  const unload=(event:BeforeUnloadEvent)=>{if(fence.current)event.preventDefault();};
  const navigation=(event:MouseEvent)=>{if(fence.current && event.target instanceof Element && event.target.closest("a")){event.preventDefault();event.stopImmediatePropagation();}};
  window.addEventListener("beforeunload",unload);document.addEventListener("click",navigation,true);
  return()=>{window.removeEventListener("beforeunload",unload);document.removeEventListener("click",navigation,true);};
 },[]);
 function resetEditor(current:DocumentsData) {
  setTitle(current.detail?.title || "");setTypeId(current.detail?.documentTypeId || "");setLines(current.detail?.lines || []);
  setCatalog(current.catalog);setTypes(current.types);setCatalogAfter(undefined);setTypeAfter(undefined);
 }
 async function login(){try{const csrf=await readJson("/auth/csrf");const form=document.createElement("form");form.method="POST";form.action="/auth/login";const input=document.createElement("input");input.name="__RequestVerificationToken";input.value=csrf.requestToken;form.append(input);document.body.append(form);form.submit();}catch{setMessage("Accesso temporaneamente non disponibile.");}}
 async function send(command:Frozen) {
  if(busy)return;setBusy(true);setMessage("");
  try {
   const csrf=await readJson("/auth/csrf");
   const response=await fetch(command.path,{method:"POST",headers:{"Content-Type":"application/json","X-CSRF-TOKEN":csrf.requestToken},body:command.body,cache:"no-store",redirect:"error",signal:AbortSignal.timeout(12000)});
   if(!response.ok){let state="";try{state=(await response.json()).state || "";}catch{}throw new DocumentFailure(response.status,state);}
   const result=await response.json();
   command.uncertain=true;
   const currentQuery={...command.query,id:command.operation==="policy"?command.query.id:result.snapshot.id};
   const current=await readJson(documentsReadPath(currentQuery));
   setData(current);setQuery(currentQuery);resetEditor(current);setCreating(false);setStatus(200);setPending(null);fence.current=null;
   setMessage(command.operation==="confirm"?"Documento confermato: stato, righe e movimenti riletti. Nessun effetto duplicato.":command.operation==="policy"?"Regola societaria salvata con versione e audit. Nessuna quantità è stata corretta automaticamente.":"Bozza salvata e riletta. Nessuna variazione di magazzino.");
  } catch(error) {
   if(error instanceof HttpFailure && [400,409].includes(error.status) && !command.uncertain) {
    setPending(null);fence.current=null;
    try{const current=await readJson(documentsReadPath(command.query));setData(current);setTypes(current.types);setStatus(200);}catch(readError){setData(null);setStatus(readError instanceof HttpFailure?readError.status:503);}
    setMessage(error instanceof DocumentFailure && refusalMessages[error.state] || "Comando rifiutato. Nessuna conferma parziale. Rileggi configurazione e quantità e correggi i dati prima di riprovare.");return;
   }
   command.uncertain=true;setData(null);setStatus(error instanceof HttpFailure?error.status:503);
   setMessage("Esito da verificare: riprova lo stesso comando. UUID, destinatario e contenuto restano congelati anche dopo una rilettura fallita. Un ricaricamento forzato non conserva il tentativo.");
  }finally{setBusy(false);}
 }
 function submit(operation:"create"|"save"|"confirm"|"policy",allowNegative?:boolean) {
  if(!data || !query.legalEntityId || !hydrated || fence.current || busy)return;
  const base={commandId:crypto.randomUUID(),operation,legalEntityId:query.legalEntityId};
  const selected=types.find(t=>t.id===typeId);
  const request=operation==="policy"?{...base,expectedRevision:data.policy?.revision,allowNegative:!!allowNegative}
   :operation==="confirm"?{...base,siteId:query.siteId,documentId:data.detail?.id,expectedRevision:data.detail?.revision,expectedTypeRevision:types.find(t=>t.id===data.detail?.documentTypeId)?.revision,expectedPolicyRevision:data.policy?.revision}
   :{...base,siteId:query.siteId,documentId:operation==="create"?null:data.detail?.id,expectedRevision:operation==="create"?0:data.detail?.revision,documentTypeId:typeId,expectedTypeRevision:selected?.revision,title,
    lines:lines.map(l=>({id:l.id,itemId:l.itemId,catalogRevision:l.catalogRevision,quantity:l.quantity,warehouseId:l.warehouseId,destinationWarehouseId:l.destinationWarehouseId}))};
  const command={path:documentsPath+"/commands",body:JSON.stringify(request),operation,query:{legalEntityId:query.legalEntityId,siteId:query.siteId,warehouseId:operation==="policy"?query.warehouseId:undefined,id:operation==="create"?undefined:data.detail?.id},uncertain:false};
  fence.current=command;setPending(command);void send(command);
 }
 async function choices(selection:"catalog"|"types",after?:string) {
  if(fence.current || busy)return;setBusy(true);
  try{const current=await readJson(documentsReadPath({legalEntityId:query.legalEntityId,siteId:query.siteId,selection,search:selection==="catalog"?catalogSearch:typeSearch,selectionAfter:after}));
   if(selection==="catalog"){setCatalog(current.catalog);setCatalogAfter(after);}else{setTypes(current.types);setTypeAfter(after);}
  }catch{setMessage("Selezione non disponibile o permesso revocato.");}finally{setBusy(false);}
 }
 function editLine(id:string,change:Partial<DocumentLine>){setLines(old=>old.map(l=>l.id===id?{...l,...change}:l));}
 function addItem(item:CatalogChoice){setLines(old=>[...old,{id:crypto.randomUUID(),itemId:item.id,catalogRevision:item.revision,kind:item.kind,label:item.label,quantity:"1",warehouseId:null,destinationWarehouseId:null}]);}
 function link(q:DocumentsQuery){return "/documents"+documentsReadPath(q).slice(documentsPath.length);}
 const company=data?.companies.find(c=>c.id===query.legalEntityId);const site=data?.sites.find(s=>s.id===query.siteId);const detail=data?.detail;
 const type=types.find(t=>t.id===typeId);const currentType=types.find(t=>t.id===detail?.documentTypeId);
 const hasUnsavedChanges=!!detail && !creating && (title!==detail.title || typeId!==detail.documentTypeId || JSON.stringify(lines)!==JSON.stringify(detail.lines));
 const locked=!hydrated || !!pending || busy;const editable=!!data?.canSave && (creating || detail?.state==="Draft");
 const warehouseName=(id:string)=>data?.warehouses.find(w=>w.id===id)?.name || "Magazzino del documento";
 const dedupTypes=Array.from(new Map(types.filter(Boolean).map(t=>[t.id,t])).values());
 return <section className="organization documents-workspace">
  <p className="eyebrow">Documenti e inventario continuo</p><h1>Documenti e quantità</h1>
  <p>Solo la conferma movimenta gli articoli. Salvare una bozza non modifica le giacenze. I servizi non hanno stock fisico.</p>
  {status===401 && !pending && <Button disabled={!hydrated} onClick={()=>void login()}>Accedi con identità federata</Button>}
  {status===403 && <p role="alert">Accesso o permesso assente, disabilitato o revocato.</p>}
  {status===404 && <p role="alert">Documento non disponibile nel contesto autorizzato.</p>}
  {status===400 && <p role="alert">Parametri non validi.</p>}
  {status>=500 && <p role="alert">Servizio temporaneamente non disponibile.</p>}
  {message && <p role="status">{message}</p>}
  {pending && <Card className="role-panel"><p>Comando congelato; recupero limitato alla pagina aperta.</p><Button disabled={!hydrated || busy} onClick={()=>void send(pending)}>Riprova stesso comando</Button></Card>}
  <noscript><p>Società, sedi, ricerca, documenti, righe e provenienza sono consultabili senza JavaScript. I comandi richiedono JavaScript e CSRF.</p><style>{".document-command{display:none!important}"}</style></noscript>
  {data && status===200 && <>
   <form method="get" action="/documents"><fieldset disabled={!!pending || busy}><label>Società autorizzata<select name="legalEntityId" required defaultValue={query.legalEntityId || ""}><option value="">Seleziona società</option>{data.companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label><Button type="submit">Apri società</Button></fieldset></form>
   {company && <><h2>Società: {company.name}</h2>
    <form method="get" action="/documents"><fieldset disabled={!!pending || busy}><input type="hidden" name="legalEntityId" value={company.id}/><label>Sede autorizzata<select name="siteId" required defaultValue={query.siteId || ""}><option value="">Seleziona sede</option>{data.sites.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select></label><Button type="submit">Apri sede</Button></fieldset></form>
    {data.policy && <Card className="role-panel"><h2>Quantità insufficienti</h2><p>Regola societaria corrente · versione {data.policy.revision}: {data.policy.allowNegative?"stock negativo consentito":"conferma bloccata se stock insufficiente"}. La stessa regola vale per lo scarico dei trasferimenti.</p>
     <form className="document-command" onSubmit={e=>{e.preventDefault();submit("policy",new FormData(e.currentTarget).get("allowNegative")==="on");}} key={data.policy.revision}><fieldset disabled={locked || creating || hasUnsavedChanges || !data.canManagePolicy}><label><input type="checkbox" name="allowNegative" defaultChecked={data.policy.allowNegative}/>Consenti quantità negative per questa società</label><Button type="submit">Salva regola societaria</Button></fieldset></form>
     {!!data.policyHistory.length && <details><summary>Ultime 20 versioni della regola</summary><ul>{data.policyHistory.slice(0,20).map(p=><li key={p.revision}>Versione {p.revision} · {p.allowNegative?"consenti negativo":"blocca insufficienza"} · {p.occurredAt}</li>)}</ul></details>}
    </Card>}
    {site && <><h2>Sede: {site.name}</h2>
     {site.canReadDocuments && <>
      <form method="get" action="/documents"><fieldset disabled={!!pending || busy}><input type="hidden" name="legalEntityId" value={company.id}/><input type="hidden" name="siteId" value={site.id}/><label>Cerca documenti<input name="search" defaultValue={query.search || ""}/></label><Button type="submit">Cerca</Button></fieldset></form>
      <Card className="role-panel"><h2>Documenti della sede</h2><ul>{data.items.slice(0,20).map(d=><li key={d.id}><a href={link({legalEntityId:company.id,siteId:site.id,id:d.id})}>{d.title}</a> · {d.state==="Draft"?"Bozza":"Confermato"} · revisione {d.revision}</li>)}</ul>{!data.items.length && <p>Nessun documento trovato.</p>}
       {data.items.length>20 && <a href={link({legalEntityId:company.id,siteId:site.id,search:query.search,after:data.items[19].id})}>Pagina documenti successiva</a>}
       {query.after && !query.warehouseId && <a href={link({legalEntityId:company.id,siteId:site.id})}>Prima pagina documenti</a>}
       <Button className="document-command" disabled={locked || creating || hasUnsavedChanges || !data.canSave} onClick={()=>{setCreating(true);setTitle("");setTypeId("");setLines([]);}}>Nuovo documento</Button>
      </Card>
      {(creating || detail) && <Card className="role-panel"><h2>{creating?"Nuovo documento":detail?.title}</h2>
       {detail && !creating && <p>Stato: {detail.state==="Draft"?"Bozza":"Confermato"} · revisione {detail.revision} · {detail.confirmedAt}</p>}
       {editable && <form className="document-command" onSubmit={(e:FormEvent)=>{e.preventDefault();submit(creating?"create":"save");}}><fieldset disabled={locked}>
        <label>Titolo documento<input required value={title} onChange={e=>setTitle(e.target.value)}/></label>
        <label>Tipologia della società<select required value={typeId} onChange={e=>setTypeId(e.target.value)}><option value="">Seleziona tipologia</option>{dedupTypes.map(t=><option key={t.id} value={t.id}>{t.label} · {effectLabels[t.effect]} · v{t.revision}</option>)}</select></label>
        <p>Effetto corrente: {type?effectLabels[type.effect]:"scegli tipologia"}. Un cambio non riassegna né cancella i magazzini delle righe.</p>
        <label>Cerca tipologie<input value={typeSearch} onChange={e=>setTypeSearch(e.target.value)}/></label><Button type="button" onClick={()=>void choices("types")}>Cerca tipologie</Button>
        {types.length>20 && <Button type="button" onClick={()=>void choices("types",types[19].id)}>Altre tipologie</Button>}{typeAfter && <Button type="button" onClick={()=>void choices("types")}>Prime tipologie</Button>}
        <label>Cerca articoli o servizi<input value={catalogSearch} onChange={e=>setCatalogSearch(e.target.value)}/></label><Button type="button" onClick={()=>void choices("catalog")}>Cerca catalogo</Button>
        <ul>{catalog.slice(0,20).map(item=><li key={item.id}>{item.label} · {item.kind==="Article"?"Articolo":"Servizio"} · versione {item.revision} <Button type="button" onClick={()=>addItem(item)}>Aggiungi {item.label}</Button></li>)}</ul>
        {catalog.length>20 && <Button type="button" onClick={()=>void choices("catalog",catalog[19].id)}>Altri articoli e servizi</Button>}{catalogAfter && <Button type="button" onClick={()=>void choices("catalog")}>Prima pagina catalogo</Button>}
        <h3>Righe modificabili</h3>{!lines.length && <p>Aggiungi almeno una riga dal catalogo.</p>}
        {lines.map((line,index)=><fieldset className="document-line" key={line.id}><legend>Riga {index+1}: {line.label} · versione {line.catalogRevision}</legend>
         <label>Quantità riga {index+1}<input inputMode="decimal" required value={line.quantity} onChange={e=>editLine(line.id,{quantity:e.target.value})}/></label>
         {line.kind==="Service"?<p>Servizio: nessun magazzino o movimento fisico.</p>:<>
          <label>Magazzino riga {index+1}<select value={line.warehouseId || ""} onChange={e=>editLine(line.id,{warehouseId:e.target.value || null})}><option value="">Nessun magazzino</option>{data.warehouses.filter(w=>w.canApply).map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
          <label>Destinazione trasferimento riga {index+1}<select value={line.destinationWarehouseId || ""} onChange={e=>editLine(line.id,{destinationWarehouseId:e.target.value || null})}><option value="">Nessuna destinazione</option>{data.warehouses.filter(w=>w.canApply).map(w=><option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
         </>}
         <Button type="button" onClick={()=>setLines(old=>old.filter(l=>l.id!==line.id))}>Rimuovi riga {index+1}</Button>
        </fieldset>)}
        <p>Quantità decimali con punto, fino a sei decimali; nessun prezzo o dato fiscale richiesto.</p><Button type="submit">{creating?"Crea bozza":"Salva bozza"}</Button>
       </fieldset></form>}
       {detail && !creating && <>
        <h3>Righe salvate</h3><ol>{detail.lines.map((line,index)=><li key={line.id} id={"line-"+line.id}>{line.label} · {line.kind==="Article"?"Articolo":"Servizio"} · quantità {line.quantity} · catalogo v{line.catalogRevision}
         {line.warehouseId && <> · {warehouseName(line.warehouseId)}</>}{line.destinationWarehouseId && <> → {warehouseName(line.destinationWarehouseId)}</>}
         <a href={link({legalEntityId:company.id,siteId:site.id,id:detail.id})+"#line-"+line.id}>Riga {index+1}</a>
        </li>)}</ol>
        {detail.appliedConfiguration?<p>Configurazione applicata e immutabile: {detail.appliedConfiguration.documentType.label} · {effectLabels[detail.appliedConfiguration.documentType.effect]} · tipo v{detail.appliedConfiguration.documentType.revision} · policy v{detail.appliedConfiguration.policy.revision} ({detail.appliedConfiguration.policy.allowNegative?"negativo consentito":"blocco insufficienza"}).</p>
         :<><p>Prossima conferma delle sole righe salvate: {currentType?effectLabels[currentType.effect]:"tipo da rileggere"}, versione tipo {currentType?.revision}, policy {data.policy?.revision}. Tutte le righe oppure nessuna. Per avviare una nuova giacenza usa un carico documentato e confermato.</p>
          {hasUnsavedChanges && <p role="note">Modifiche non salvate: salva la bozza prima di confermare le righe.</p>}
          <Button className="document-command" disabled={locked || hasUnsavedChanges || !data.canConfirm || !currentType || !data.policy} onClick={()=>submit("confirm")}>Conferma documento e applica quantità</Button>
         </>}
       </>}
      </Card>}
     </>}
     <Card className="role-panel"><h2>Quantità per magazzino</h2><p>Autorità documentale MVP separata dallo stock ERP storico. Assenza di saldo MVP significa zero, non reset dei dati legacy.</p><ul>{data.warehouses.filter(w=>w.canReadStock).map(w=><li key={w.id}><a href={link({legalEntityId:company.id,siteId:site.id,warehouseId:w.id})}>{w.name}</a></li>)}</ul>
      {query.warehouseId && <><h3>{warehouseName(query.warehouseId)}</h3><ul>{data.balances.slice(0,20).map(b=><li key={b.itemId}>{b.label || "Articolo documentato"} · quantità {b.quantity}</li>)}</ul>{!data.balances.length && <p>Nessun saldo documentale presente: zero per le chiavi non ancora movimentate.</p>}
       {data.balances.length>20 && <a href={link({legalEntityId:company.id,siteId:site.id,warehouseId:query.warehouseId,after:data.balances[19].itemId})}>Altre quantità</a>}
      </>}
     </Card>
     {(detail || query.warehouseId) && <Card className="role-panel"><h2>Movimenti e provenienza</h2><ul>{data.ledger.slice(0,20).map(l=><li key={l.id}>{l.label} · {warehouseName(l.warehouseId)} · {l.leg==="in"?"Carico":"Scarico"} {l.quantity} · {l.occurredAt} · catalogo v{l.catalogRevision}
       {l.canReadDocument?<a href={link({legalEntityId:company.id,siteId:site.id,id:l.documentId})+"#line-"+l.lineId}>Documento e riga sorgente</a>:<span>Documento non consultabile con i permessi correnti</span>}
       {data.warehouses.find(w=>w.id===l.warehouseId)?.canReadStock && <a href={link({legalEntityId:company.id,siteId:site.id,warehouseId:l.warehouseId})}>Quantità del magazzino</a>}
      </li>)}</ul>{!data.ledger.length && <p>Nessun movimento: le bozze, i servizi e i tipi senza effetto non modificano lo stock.</p>}
      {data.ledger.length>20 && <a href={link({...query,ledgerAfter:data.ledger[19].id})}>Altri movimenti</a>}
     </Card>}
    </>}
   </>}
  </>}
 <a href="/">Torna alla panoramica</a>
 </section>;
}
