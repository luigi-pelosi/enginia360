"use client";
import React, { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { HttpFailure, readJson } from "../lib/organization";
import { counterpartyPath, counterpartyReadPath, type CounterpartyData, type CounterpartyQuery } from "../lib/counterparties";

type Frozen = { readonly path: string; readonly body: string; readonly operation: string; readonly query: CounterpartyQuery; uncertain: boolean };
export function CounterpartyWorkspace({ initial }: { initial: { status: number; data: CounterpartyData | null; query: CounterpartyQuery } }) {
  const [data, setData] = useState(initial.data);
  const [status, setStatus] = useState(initial.status);
  const [query, setQuery] = useState(initial.query);
  const [creating, setCreating] = useState(false);
  const [destinationId, setDestinationId] = useState("");
  const [pending, setPending] = useState<Frozen | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const fence = useRef<Frozen | null>(null);
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => { if (fence.current) event.preventDefault(); };
    const navigation = (event: MouseEvent) => { if (fence.current && (event.target as Element).closest("a")) { event.preventDefault(); event.stopImmediatePropagation(); } };
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
    if (busy) return;
    setBusy(true); setMessage("");
    try {
      const csrf = await readJson("/auth/csrf");
      const result = await readJson(command.path, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrf.requestToken }, body: command.body });
      command.uncertain = true;
      const currentQuery = { ...command.query, after: undefined, id: command.operation === "create" ? result.snapshot.id : command.query.id };
      const current = await readJson(counterpartyReadPath(currentQuery));
      setData(current); setQuery(currentQuery); setCreating(false); setStatus(200); setDestinationId("");
      setPending(null); fence.current = null;
      setMessage("Modifica accettata; stato corrente riletto. Il ruolo fornitore non è un ruolo di sicurezza.");
    } catch (error) {
      if (error instanceof HttpFailure && (error.status === 400 || error.status === 409) && !command.uncertain) {
        setPending(null); fence.current = null;
        try { setData(await readJson(counterpartyReadPath(command.query))); } catch (readError) { setData(null); setStatus(readError instanceof HttpFailure ? readError.status : 503); }
        setMessage("Comando rifiutato. Correggi i campi o usa lo stato aggiornato; nessuna fusione automatica."); return;
      }
      command.uncertain = true;
      if (error instanceof HttpFailure && [401, 403].includes(error.status)) { setData(null); setStatus(error.status); }
      setMessage("Esito da verificare: riprova lo stesso comando. UUID, destinazione e contenuto restano congelati. Un ricaricamento forzato non conserva il tentativo.");
    } finally { setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>, operation: string) {
    event.preventDefault(); if (!data || fence.current || busy) return;
    const values = new FormData(event.currentTarget); const text = (name: string) => String(values.get(name) || "");
    const destination = data.destinations?.find(d => d.id === destinationId);
    const request: Record<string, unknown> = { commandId: crypto.randomUUID(), operation, counterpartyId: operation === "create" ? null : data.detail?.id, expectedRevision: operation === "create" ? 0 : data.detail?.revision };
    if (operation.startsWith("destination-")) {
      request.legalEntityId = data.companyId; request.destinationId = destination?.id || null; request.expectedRevision = destination?.revision || 0; request.address = text("address");
    } else {
      request.authorityVersion = data.authority.version;
      if (operation === "supplier-role") request.isSupplier = values.get("isSupplier") === "on";
      else { request.legalName = text("legalName"); request.fiscalIdentifier = text("fiscalIdentifier"); request.registeredOffice = text("registeredOffice"); }
    }
    const command = { path: counterpartyPath + "/commands", body: JSON.stringify(request), operation, query: { ...query, id: data.detail?.id }, uncertain: false };
    fence.current = command; setPending(command); void send(command);
  }
  const detail = data?.detail; const local = data?.authority.state === "local";
  const destination = data?.destinations?.find(d => d.id === destinationId);
  const company = data?.companies.find(c => c.id === data.companyId);
  function fields() { return <>
    <label>Denominazione<input name="legalName" required defaultValue={creating ? "" : detail?.legalName || ""} /></label>
    <label>Identificativo fiscale (facoltativo)<input name="fiscalIdentifier" defaultValue={creating ? "" : detail?.fiscalIdentifier || ""} /></label>
    <label>Sede legale (facoltativa)<textarea name="registeredOffice" defaultValue={creating ? "" : detail?.registeredOffice || ""} /></label>
  </>; }
  return <section className="organization counterparty-workspace">
    <p className="eyebrow">Anagrafiche condivise nel tenant</p><h1>Controparti e ruoli aziendali</h1>
    <p>Identità e ruolo fornitore sono comuni alle società. Destinazioni e permessi sono separati. Cerca prima di creare: i duplicati non vengono fusi e il dato fiscale non è una chiave univoca.</p>
    {status === 401 && <Button onClick={() => void login()}>Accedi con identità federata</Button>}
    {status === 403 && <p role="alert">Accesso o permesso assente, disabilitato o revocato.</p>}
    {status === 404 && <p role="alert">Controparte non disponibile.</p>}
    {status === 400 && <p role="alert">Parametri non validi.</p>}
    {status >= 500 && <p role="alert">Servizio temporaneamente non disponibile.</p>}
    {message && <p role="status">{message}</p>}
    {pending && <Card className="role-panel"><p>Comando congelato. Recupero limitato alla pagina aperta.</p><Button disabled={busy} onClick={() => void send(pending)}>Riprova stesso comando</Button></Card>}
    {data && status === 200 && <>
      <p>Autorità anagrafica: {data.authority.state === "local" ? "locale" : data.authority.state === "external" ? "esterna: modifiche comuni non consentite" : "setup esplicito richiesto al titolare"} · versione {data.authority.version}</p>
      <noscript><p>Elenco, ricerca, selezione e dettaglio sono disponibili senza JavaScript. Le modifiche richiedono JavaScript e CSRF.</p><style>{".counterparty-command{display:none!important}"}</style></noscript>
      <form method="get" action="/counterparties"><fieldset disabled={!!pending || busy}><label>Cerca controparti<input name="search" defaultValue={query.search || ""} /></label><Button type="submit">Cerca</Button></fieldset></form>
      <Card className="role-panel"><h2>Elenco controparti</h2><ul>{data.items.slice(0, 20).map(c => <li key={c.id}><a href={"/counterparties?" + new URLSearchParams({ ...(query.search ? { search: query.search } : {}), id: c.id }).toString()}>{c.legalName}</a>{c.isSupplier ? " · Fornitore" : ""}</li>)}</ul>{data.items.length === 0 && <p>Nessun risultato.</p>}
        {data.items.length > 20 && <a href={"/counterparties?" + new URLSearchParams({ ...(query.search ? { search: query.search } : {}), after: data.items[19].id }).toString()}>Pagina successiva</a>}
        {query.after && <a href={"/counterparties?" + new URLSearchParams({ search: query.search || "" }).toString()}>Torna alla prima pagina</a>}
        <Button className="counterparty-command" disabled={!!pending || busy || !local || !data.canCreate} onClick={() => setCreating(true)}>Nuova controparte</Button>
      </Card>
      {creating && <Card className="role-panel counterparty-command"><h2>Nuova identità condivisa</h2><form onSubmit={e => submit(e, "create")}><fieldset disabled={!!pending || busy || !local || !data.canCreate}>{fields()}<Button type="submit">Crea controparte</Button><Button type="button" variant="outline" onClick={() => setCreating(false)}>Annulla</Button></fieldset></form></Card>}
      {detail && <Card className="role-panel"><h2>Dettaglio: {detail.legalName}</h2><dl><dt>Denominazione</dt><dd>{detail.legalName}</dd><dt>Identificativo fiscale</dt><dd>{detail.fiscalIdentifier || "Non indicato"}</dd><dt>Sede legale</dt><dd>{detail.registeredOffice || "Non indicata"}</dd><dt>Ruolo aziendale</dt><dd>{detail.isSupplier ? "Fornitore" : "Nessun ruolo fornitore"}</dd><dt>Revisione condivisa</dt><dd>{detail.revision}</dd></dl>
        {!creating && <form key={detail.id + ":" + detail.revision} className="counterparty-command" onSubmit={e => submit(e, "edit")}><fieldset disabled={!!pending || busy || !local || !data.canEdit}>{fields()}<Button type="submit">Salva dati comuni</Button></fieldset></form>}
        <form key={"supplier:" + detail.id + ":" + detail.revision} className="counterparty-command" onSubmit={e => submit(e, "supplier-role")}><fieldset disabled={!!pending || busy || !local || !data.canWriteRoles}><label><input type="checkbox" name="isSupplier" defaultChecked={detail.isSupplier} />Fornitore (ruolo aziendale)</label><Button type="submit">Salva ruolo fornitore</Button></fieldset></form>
        <h3>Destinazioni della società</h3><p>Visibili solo nello scope autorizzato; nessuna pubblicazione o mappatura ERP da questo editor.</p>
        <form method="get" action="/counterparties"><fieldset disabled={!!pending || busy}><input type="hidden" name="id" value={detail.id} /><label>Società destinazioni<select name="company" defaultValue={data.companyId || ""} required><option value="">Seleziona società</option>{data.companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label><Button type="submit">Apri destinazioni societarie</Button></fieldset></form>
        {data.companyId && <><ul>{data.destinations?.map(d => <li key={d.id}>{d.address} · {d.published ? "pubblicata, sola lettura" : "riservata"} · revisione {d.revision}</li>)}</ul><form className="counterparty-command" onSubmit={e => submit(e, destination ? "destination-edit" : "destination-create")}><fieldset disabled={!!pending || busy || !company?.canWrite}><label>Destinazione da modificare<select value={destinationId} onChange={e => setDestinationId(e.target.value)}><option value="">Nuova destinazione privata</option>{data.destinations?.filter(d => !d.published).map(d => <option key={d.id} value={d.id}>{d.address}</option>)}</select></label><label key={destination ? destination.id + ":" + destination.revision : "new-destination"}>Indirizzo destinazione<textarea name="address" required defaultValue={destination?.address || ""} /></label><Button type="submit">Salva destinazione privata</Button></fieldset></form></>}
      </Card>}
    </>}
  </section>;
}
