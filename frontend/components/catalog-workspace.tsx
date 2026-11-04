"use client";
import React, { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { HttpFailure, readJson } from "../lib/organization";
import { catalogPath, catalogReadPath, kindLabel, type CatalogData, type CatalogQuery, type CatalogKind } from "../lib/catalog";

type Frozen = { readonly path: string; readonly body: string; readonly operation: string; readonly query: CatalogQuery; uncertain: boolean };
export function CatalogWorkspace({ initial }: { initial: { status: number; data: CatalogData | null; query: CatalogQuery } }) {
  const [data, setData] = useState(initial.data); const [status, setStatus] = useState(initial.status);
  const [query, setQuery] = useState(initial.query); const [creating, setCreating] = useState(false);
  const [pending, setPending] = useState<Frozen | null>(null); const [busy, setBusy] = useState(false); const [message, setMessage] = useState("");
  const fence = useRef<Frozen | null>(null);
  // SSR reads work immediately; a mutation must never fall back to native GET
  // submission before React has installed its CSRF/frozen-command handler.
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => { setHydrated(true); }, []);
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
    if (busy) return; setBusy(true); setMessage("");
    try {
      const csrf = await readJson("/auth/csrf");
      const result = await readJson(command.path, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrf.requestToken }, body: command.body });
      command.uncertain = true;
      const currentQuery = { ...command.query, after: undefined, id: command.operation === "create" ? result.snapshot.id : command.query.id };
      const current = await readJson(catalogReadPath(currentQuery));
      setData(current); setQuery(currentQuery); setCreating(false); setStatus(200); setPending(null); fence.current = null;
      setMessage("Modifica accettata; stato corrente riletto. Prezzi e giacenze non modificati.");
    } catch (error) {
      if (error instanceof HttpFailure && [400, 409].includes(error.status) && !command.uncertain) {
        setPending(null); fence.current = null;
        try { setData(await readJson(catalogReadPath(command.query))); } catch (readError) { setData(null); setStatus(readError instanceof HttpFailure ? readError.status : 503); }
        setMessage("Comando rifiutato. Correggi i campi o usa lo stato aggiornato; nessuna fusione automatica."); return;
      }
      command.uncertain = true;
      if (error instanceof HttpFailure && [401, 403].includes(error.status)) { setData(null); setStatus(error.status); }
      setMessage("Esito da verificare: riprova lo stesso comando. UUID, destinazione e contenuto restano congelati. Un ricaricamento forzato non conserva il tentativo.");
    } finally { setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>, operation: "create" | "edit") {
    event.preventDefault(); if (!data || fence.current || busy) return;
    const values = new FormData(event.currentTarget);
    const request = { commandId: crypto.randomUUID(), operation, itemId: operation === "create" ? null : data.detail?.id,
      expectedRevision: operation === "create" ? 0 : data.detail?.revision, authorityVersion: data.authority.version,
      kind: operation === "create" ? String(values.get("kind")) as CatalogKind : data.detail?.kind, label: String(values.get("label") || "") };
    const command = { path: catalogPath + "/commands", body: JSON.stringify(request), operation, query: { ...query, id: data.detail?.id }, uncertain: false };
    fence.current = command; setPending(command); void send(command);
  }
  const detail = data?.detail; const local = data?.authority.state === "local";
  function link(values: CatalogQuery) { return "/catalog" + catalogReadPath(values).slice(catalogPath.length); }
  return <section className="organization catalog-workspace">
    <p className="eyebrow">Catalogo condiviso nel tenant</p><h1>Articoli e servizi</h1>
    <p>Identità comuni alle società, separate da prezzi, condizioni e giacenze. Cerca prima di creare: etichette uguali non vengono fuse automaticamente.</p>
    {status === 401 && <Button onClick={() => void login()}>Accedi con identità federata</Button>}
    {status === 403 && <p role="alert">Accesso o permesso assente, disabilitato o revocato.</p>}
    {status === 404 && <p role="alert">Identità catalogo non disponibile.</p>}
    {status === 400 && <p role="alert">Parametri non validi.</p>}
    {status >= 500 && <p role="alert">Servizio temporaneamente non disponibile.</p>}
    {message && <p role="status">{message}</p>}
    {pending && <Card className="role-panel"><p>Comando congelato. Recupero limitato alla pagina aperta.</p><Button disabled={busy} onClick={() => void send(pending)}>Riprova stesso comando</Button></Card>}
    {data && status === 200 && <>
      <p>Autorità catalogo: {local ? "locale" : data.authority.state === "external" ? "esterna: modifiche non consentite" : "setup esplicito richiesto al titolare"} · versione {data.authority.version}</p>
      <noscript><p>Elenco, ricerca, selezione e dettaglio sono disponibili senza JavaScript. Le modifiche richiedono JavaScript e CSRF.</p><style>{".catalog-command{display:none!important}"}</style></noscript>
      <form method="get" action="/catalog"><fieldset disabled={!!pending || busy}>
        <label>Cerca articoli e servizi<input name="search" defaultValue={query.search || ""} /></label>
        <label>Filtro tipo<select name="kind" defaultValue={query.kind || ""}><option value="">Tutti</option><option value="Article">Articoli</option><option value="Service">Servizi</option></select></label>
        <Button type="submit">Cerca</Button>
      </fieldset></form>
      <Card className="role-panel"><h2>Elenco catalogo</h2><ul>{data.items.slice(0, 20).map(item => <li key={item.id}><a href={link({ search: query.search, kind: query.kind, id: item.id })}>{item.label}</a> · {kindLabel(item.kind)}</li>)}</ul>
        {!data.items.length && <p>Nessun risultato.</p>}
        {data.items.length > 20 && <a href={link({ search: query.search, kind: query.kind, after: data.items[19].id })}>Pagina successiva</a>}
        {query.after && <a href={link({ search: query.search, kind: query.kind })}>Torna alla prima pagina</a>}
        <Button className="catalog-command" disabled={!hydrated || !!pending || busy || !local || !data.canCreate} onClick={() => setCreating(true)}>Nuovo articolo o servizio</Button>
      </Card>
      {creating && <Card className="role-panel catalog-command"><h2>Nuova identità catalogo</h2><form onSubmit={e => submit(e, "create")}><fieldset disabled={!hydrated || !!pending || busy || !local || !data.canCreate}>
        <label>Tipo<select name="kind" required defaultValue=""><option value="">Seleziona tipo</option><option value="Article">Articolo</option><option value="Service">Servizio</option></select></label>
        <label>Descrizione<input name="label" required /></label><p>Massimo 100 caratteri Unicode. Nessun codice univoco o prezzo richiesto.</p>
        <Button type="submit">Crea identità catalogo</Button><Button type="button" variant="outline" onClick={() => setCreating(false)}>Annulla</Button>
      </fieldset></form></Card>}
      {detail && <Card className="role-panel"><h2>Dettaglio: {detail.label}</h2><dl><dt>Tipo</dt><dd>{kindLabel(detail.kind)}</dd><dt>Descrizione</dt><dd>{detail.label}</dd><dt>Revisione condivisa</dt><dd>{detail.revision}</dd></dl>
        <p>Il tipo resta quello scelto alla creazione; nessuna riclassificazione di identità referenziate.</p>
        {!creating && <form className="catalog-command" key={detail.id + ":" + detail.revision} onSubmit={e => submit(e, "edit")}><fieldset disabled={!hydrated || !!pending || busy || !local || !data.canEdit}>
          <label>Descrizione<input name="label" required defaultValue={detail.label} /></label><Button type="submit">Salva identità catalogo</Button>
        </fieldset></form>}
      </Card>}
    </>}
  </section>;
}
