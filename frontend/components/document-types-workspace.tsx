"use client";
import React, { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { HttpFailure, readJson } from "../lib/organization";
import { documentTypesPath, documentTypesReadPath, effectLabels, type DocumentTypesData, type DocumentTypesQuery, type QuantityEffect, type DocumentTypeVersion } from "../lib/document-types";

type Frozen = { readonly path: string; readonly body: string; readonly operation: string; readonly query: DocumentTypesQuery; uncertain: boolean };
export function DocumentTypesWorkspace({ initial }: { initial: { status: number; data: DocumentTypesData | null; query: DocumentTypesQuery } }) {
  const [data, setData] = useState(initial.data); const [status, setStatus] = useState(initial.status);
  const [query, setQuery] = useState(initial.query); const [creating, setCreating] = useState(false);
  const [pending, setPending] = useState<Frozen | null>(null); const [busy, setBusy] = useState(false); const [message, setMessage] = useState("");
  const fence = useRef<Frozen | null>(null);
  const [targets,setTargets]=useState<ReadonlyArray<DocumentTypeVersion>>(initial.data?.items || []);
  const [targetSearch,setTargetSearch]=useState("");
  const [targetId,setTargetId]=useState("");
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => { setHydrated(true); }, []);
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (fence.current) event.preventDefault(); };
    const navigation = (event: MouseEvent) => { if (fence.current && event.target instanceof Element && event.target.closest("a")) { event.preventDefault(); event.stopImmediatePropagation(); } };
    window.addEventListener("beforeunload", unload); document.addEventListener("click", navigation, true);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigation, true); };
  }, []);
  async function login() {
    try {
      const csrf = await readJson("/auth/csrf"); const form = document.createElement("form"); form.method = "POST"; form.action = "/auth/login";
      const input = document.createElement("input"); input.name = "__RequestVerificationToken"; input.value = csrf.requestToken; form.append(input); document.body.append(form); form.submit();
    } catch { setMessage("Accesso temporaneamente non disponibile."); }
  }
  async function send(command: Frozen) {
    if (busy) return; setBusy(true); setMessage("");
    try {
      const csrf = await readJson("/auth/csrf");
      const result = await readJson(command.path, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrf.requestToken }, body: command.body });
      command.uncertain = true;
      const currentQuery = { legalEntityId: command.query.legalEntityId, search: command.query.search, id: command.operation === "path" ? command.query.id : result.snapshot.id };
      const current = await readJson(documentTypesReadPath(currentQuery));
      setData(current); setQuery(currentQuery); setCreating(false); setStatus(200); setPending(null); fence.current = null;
      setMessage("Versione accettata; stato corrente riletto. Nessun documento o movimento di magazzino creato.");
    } catch (error) {
      if (error instanceof HttpFailure && [400, 409].includes(error.status) && !command.uncertain) {
        setPending(null); fence.current = null;
        try { setData(await readJson(documentTypesReadPath(command.query))); setStatus(200); } catch (readError) { setData(null); setStatus(readError instanceof HttpFailure ? readError.status : 503); }
        setMessage("Comando rifiutato. Correggi i campi o usa la revisione aggiornata; nessuna fusione automatica."); return;
      }
      command.uncertain = true;
      setData(null); setStatus(error instanceof HttpFailure ? error.status : 503);
      setMessage("Esito da verificare: riprova lo stesso comando. UUID, società, destinazione e contenuto restano congelati. Un ricaricamento forzato non conserva il tentativo.");
    } finally { setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>, operation: "create" | "edit") {
    event.preventDefault(); if (!data?.selectedCompanyId || fence.current || busy || !hydrated) return;
    const values = new FormData(event.currentTarget);
    const request = { commandId: crypto.randomUUID(), operation, legalEntityId: data.selectedCompanyId,
      documentTypeId: operation === "create" ? null : data.detail?.id, expectedRevision: operation === "create" ? 0 : data.detail?.revision,
      label: String(values.get("label") || ""), effect: String(values.get("effect") || "") };
    const command = { path: documentTypesPath + "/commands", body: JSON.stringify(request), operation,
      query: { legalEntityId: data.selectedCompanyId, search: query.search, id: data.detail?.id }, uncertain: false };
    fence.current = command; setPending(command); void send(command);
  }
  async function targetChoices(after?:string) {
    if(fence.current||busy||!data?.selectedCompanyId)return;setBusy(true);
    try{const current=await readJson(documentTypesReadPath({legalEntityId:data.selectedCompanyId,search:targetSearch,after}));setTargets(current.items);}catch{setMessage("Destinazioni non disponibili o permesso revocato.");}finally{setBusy(false);}
  }
  function savePath(event:FormEvent<HTMLFormElement>) {
    event.preventDefault();if(!data?.detail||!data.selectedCompanyId||fence.current||busy||!hydrated||!targetId)return;
    const values=new FormData(event.currentTarget);const prior=data.paths?.find(p=>p.sourceTypeId===data.detail?.id&&p.destinationTypeId===targetId);
    const request={commandId:crypto.randomUUID(),operation:"path",legalEntityId:data.selectedCompanyId,sourceTypeId:data.detail.id,destinationTypeId:targetId,expectedRevision:prior?.revision||0,enabled:values.get("enabled")==="on",allowCrossSite:values.get("allowCrossSite")==="on"};
    const command={path:documentTypesPath+"/commands",body:JSON.stringify(request),operation:"path",query:{legalEntityId:data.selectedCompanyId,id:data.detail.id},uncertain:false};fence.current=command;setPending(command);void send(command);
  }
  function link(values: DocumentTypesQuery) { return "/document-types" + documentTypesReadPath(values).slice(documentTypesPath.length); }
  const detail = data?.detail; const version = data?.selectedVersion;
  const company = data?.companies.find(c => c.id === data.selectedCompanyId);
  const options = Object.entries(effectLabels).map(([effect, label]) => <option key={effect} value={effect}>{label}</option>);
  return <section className="organization document-types-workspace">
    <p className="eyebrow">Configurazione esclusiva della società</p><h1>Tipologie documentali</h1>
    <p>Ogni società configura descrizione ed effetto supportato. Salvare una tipologia non crea documenti e non modifica le giacenze.</p>
    {status === 401 && !pending && <Button disabled={!hydrated} onClick={() => void login()}>Accedi con identità federata</Button>}
    {status === 403 && <p role="alert">Accesso o permesso societario assente, disabilitato o revocato.</p>}
    {status === 404 && <p role="alert">Tipologia o versione non disponibile nella società autorizzata.</p>}
    {status === 400 && <p role="alert">Parametri non validi.</p>}
    {status >= 500 && <p role="alert">Servizio temporaneamente non disponibile.</p>}
    {message && <p role="status">{message}</p>}
    {pending && <Card className="role-panel"><p>Comando congelato. Recupero limitato alla pagina aperta; nessun recupero offline durabile.</p><Button disabled={!hydrated || busy} onClick={() => void send(pending)}>Riprova stesso comando</Button></Card>}
    <noscript><p>Società, elenco, ricerca, dettaglio e versioni storiche sono consultabili senza JavaScript. Le modifiche richiedono JavaScript e CSRF.</p><style>{".document-type-command{display:none!important}"}</style></noscript>
    {data && status === 200 && <>
      <form method="get" action="/document-types"><fieldset disabled={!!pending || busy}>
        <label>Società autorizzata<select name="legalEntityId" required defaultValue={data.selectedCompanyId || ""}><option value="">Seleziona società</option>{data.companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <Button type="submit">Apri società</Button>
      </fieldset></form>
      {!company && <p>Seleziona una società per consultare le sue tipologie.</p>}
      {company && <>
        <h2>Società: {company.name}</h2>
        <form method="get" action="/document-types"><fieldset disabled={!!pending || busy}>
          <input type="hidden" name="legalEntityId" value={company.id} /><label>Cerca tipologie<input name="search" defaultValue={query.search || ""} /></label><Button type="submit">Cerca</Button>
        </fieldset></form>
        <Card className="role-panel"><h2>Tipologie della società</h2><ul>{data.items.slice(0, 20).map(item => <li key={item.id}><a href={link({ legalEntityId: company.id, search: query.search, id: item.id })}>{item.label}</a> · {effectLabels[item.effect]} · versione {item.revision}</li>)}</ul>
          {!data.items.length && <p>Nessun risultato.</p>}
          {data.items.length > 20 && <a href={link({ legalEntityId: company.id, search: query.search, after: data.items[19].id })}>Pagina successiva</a>}
          {query.after && <a href={link({ legalEntityId: company.id, search: query.search })}>Torna alla prima pagina</a>}
          <Button className="document-type-command" disabled={!hydrated || !!pending || busy || !data.canCreate} onClick={() => setCreating(true)}>Nuova tipologia</Button>
        </Card>
        {creating && <Card className="role-panel document-type-command"><h2>Nuova tipologia documentale</h2><form onSubmit={e => submit(e, "create")}><fieldset disabled={!hydrated || !!pending || busy || !data.canCreate}>
          <label>Descrizione<input name="label" required /></label><p>Massimo 100 caratteri Unicode. Nessun codice, formula o campo fiscale richiesto.</p>
          <label>Effetto sulle quantità<select name="effect" required defaultValue=""><option value="">Seleziona effetto</option>{options}</select></label>
          <Button type="submit">Crea tipologia</Button><Button type="button" variant="outline" onClick={() => setCreating(false)}>Annulla</Button>
        </fieldset></form></Card>}
        {detail && <Card className="role-panel"><h2>Dettaglio: {detail.label}</h2><dl><dt>Versione corrente</dt><dd>{detail.revision}</dd><dt>Effetto corrente</dt><dd>{effectLabels[detail.effect]}</dd></dl>
          <p>La modifica crea una nuova versione immutabile. Non riscrive le versioni precedenti o i fatti confermati. Il momento di applicazione alle operazioni documentali sarà definito nel percorso documenti.</p>
          {!creating && <form className="document-type-command" key={detail.id + ":" + detail.revision} onSubmit={e => submit(e, "edit")}><fieldset disabled={!hydrated || !!pending || busy || !data.canEdit}>
            <label>Descrizione<input name="label" required defaultValue={detail.label} /></label>
            <label>Effetto sulle quantità<select name="effect" required defaultValue={detail.effect}>{options}</select></label>
            <Button type="submit">Salva nuova versione</Button>
          </fieldset></form>}
          <h3>Percorsi di sviluppo dalla tipologia</h3><p>Identità stabile sorgente → destinazione: disabilitare e riabilitare non azzera i residui. Stessa sede per default; niente ereditarietà tenant o override sede. La creazione diretta resta disponibile.</p>
          <ul>{(data.paths||[]).map(p=><li key={p.destinationTypeId}>Destinazione {p.destinationTypeId} · versione {p.revision} · {p.enabled?"abilitato":"disabilitato"} · {p.allowCrossSite?"sedi diverse della stessa società ammesse":"solo stessa sede"}<Button className="document-type-command" disabled={!hydrated||!!pending||busy||!data.canManagePaths} onClick={()=>setTargetId(p.destinationTypeId)}>Modifica percorso {p.destinationTypeId}</Button></li>)}</ul>
          <form className="document-type-command" onSubmit={savePath}><fieldset disabled={!hydrated||!!pending||busy||!data.canManagePaths}>
           <label>Cerca tipologia destinazione<input value={targetSearch} onChange={e=>setTargetSearch(e.target.value)}/></label><Button type="button" onClick={()=>void targetChoices()}>Cerca destinazioni</Button>
           <label>Tipologia destinazione<select required value={targetId} onChange={e=>setTargetId(e.target.value)}><option value="">Scegli destinazione</option>{targets.slice(0,20).map(t=><option key={t.id} value={t.id}>{t.label}</option>)}{targetId&&!targets.some(t=>t.id===targetId)&&<option value={targetId}>Destinazione configurata {targetId}</option>}</select></label>
           {targets.length>20&&<Button type="button" onClick={()=>void targetChoices(targets[19].id)}>Altre destinazioni</Button>}
           <div key={targetId+":"+(data.paths?.find(p=>p.destinationTypeId===targetId)?.revision||0)}><label><input type="checkbox" name="enabled" defaultChecked={data.paths?.find(p=>p.destinationTypeId===targetId)?.enabled??true}/>Percorso abilitato</label><label><input type="checkbox" name="allowCrossSite" defaultChecked={data.paths?.find(p=>p.destinationTypeId===targetId)?.allowCrossSite??false}/>Consenti sedi diverse nella stessa società</label></div>
           <Button type="submit">Salva percorso versionato</Button>
          </fieldset></form>
          <h3>Storico delle versioni</h3><p>Versioni applicate alla configurazione, non conferme di documenti.</p>
          <ul>{data.history.slice(0, 20).map(v => <li key={v.revision}><a href={link({ legalEntityId: company.id, id: detail.id, revision: String(v.revision), beforeRevision: query.beforeRevision })}>Versione {v.revision}: {v.label}</a> · {effectLabels[v.effect]}</li>)}</ul>
          {data.history.length > 20 && <a href={link({ legalEntityId: company.id, id: detail.id, beforeRevision: String(data.history[19].revision) })}>Versioni precedenti</a>}
          {query.beforeRevision && <a href={link({ legalEntityId: company.id, id: detail.id })}>Versioni più recenti</a>}
          {version && <div aria-label="Versione storica selezionata"><h3>Versione selezionata: {version.revision}</h3><dl><dt>Descrizione storica</dt><dd>{version.label}</dd><dt>Effetto storico</dt><dd>{effectLabels[version.effect as QuantityEffect]}</dd><dt>Registrata il</dt><dd>{version.occurredAt}</dd></dl></div>}
        </Card>}
      </>}
    </>}
  </section>;
}
