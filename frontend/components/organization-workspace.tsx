"use client";
import React, { useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader } from "./ui/card";
import {
  directoryPath,
  readJson,
  HttpFailure,
  type InitialOrganization,
  type Edit,
  type Kind,
  type OrganizationNode,
  type Hierarchy,
  type OrganizationMembership,
} from "../lib/organization";
export function OrganizationWorkspace({
  initial,
}: {
  initial: InitialOrganization;
}) {
  const [status, setStatus] = useState(initial.status),
    [tenants, setTenants] = useState(initial.tenants),
    [hierarchy, setHierarchy] = useState(initial.hierarchy);
  const owner = initial.mode !== "delegate";
  const [memberships, setMemberships] = useState<OrganizationMembership[]>(initial.memberships || []);
  const [memberId, setMemberId] = useState("");
  const [selected, setSelected] = useState(initial.hierarchy?.tenant.id || ""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const [edit, setEdit] = useState<Edit | null>(null),
    [name, setName] = useState("");
  const generation = useRef(0),
    sending = useRef(false),
    pending = useRef<{ route: string; body: string } | null>(null);
  const [uncertain, setUncertain] = useState(false);
  const frozen = busy || uncertain;
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (pending.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    const guard = (event: MouseEvent) => {
      if (pending.current && (event.target as Element)?.closest("a")) {
        event.preventDefault();
        event.stopImmediatePropagation();
        setMessage("Navigazione bloccata: risolvere prima il comando incerto.");
      }
    };
    window.addEventListener("beforeunload", warn);
    document.addEventListener("click", guard, true);
    return () => {
      window.removeEventListener("beforeunload", warn);
      document.removeEventListener("click", guard, true);
    };
  }, []);
  function failure(error: unknown) {
    const code = error instanceof HttpFailure ? error.status : 503;
    setMessage(
      code === 409
        ? "Conflitto: dati aggiornati da un altro comando. Rileggere e riprovare."
        : code === 400
          ? "Dati non validi o protezione CSRF non valida."
          : code === 404
            ? "Destinatario non disponibile."
            : "Servizio non disponibile. Riprovare.",
    );
    if (code === 401 || code === 403) {
      setStatus(code);
      setHierarchy(null);
      setTenants([]);
    }
  }
  async function auth(action: "login" | "logout") {
    try {
      const { requestToken } = await readJson("/auth/csrf");
      const form = document.createElement("form");
      form.method = "POST";
      form.action = "/auth/" + action;
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "__RequestVerificationToken";
      input.value = requestToken;
      form.append(input);
      document.body.append(form);
      form.submit();
    } catch (error) {
      failure(error);
    }
  }
  async function selectTarget(id: string) {
    const current = ++generation.current;
    setSelected(id);
    setMemberships([]);
    setMemberId("");
    setHierarchy(null);
    setEdit(null);
    setMessage("");
    if (!id) return;
    try {
      const value = await readJson(directoryPath + "/" + id);
      const grants = owner ? await readJson(directoryPath + "/" + id + "/delegations") : null;
      if (current === generation.current) { setHierarchy(value); setMemberships(grants?.memberships || []); }
    } catch (error) {
      if (current === generation.current) failure(error);
    }
  }
  const trigger = useRef<HTMLElement | null>(null);
  function cancel() {
    if (pending.current) return;
    setEdit(null);
    trigger.current?.focus();
  }
  function begin(
    kind: Kind,
    operation: "create" | "rename",
    node: OrganizationNode | null,
    parentId: string | null,
  ) {
    if (pending.current) return;
    trigger.current = document.activeElement as HTMLElement;
    setEdit({ kind, operation, node, parentId });
    setName(operation === "rename" ? node!.name : "");
    setMessage("");
  }
  async function reread(target: string) {
    const directory = await readJson(owner ? directoryPath : directoryPath + "/workspace");
    const current = await readJson(directoryPath + "/" + target);
    const grants = owner ? await readJson(directoryPath + "/" + target + "/delegations") : null;
    setMemberships(grants?.memberships || []);
    setTenants(directory.tenants);
    setSelected(target);
    setHierarchy(current);
    setStatus(200);
    history.replaceState(null, "", "/organization?tenant=" + target);
  }
  async function sendPending() {
    if (!pending.current || sending.current) return;
    sending.current = true;
    setBusy(true);
    ++generation.current;
    setMessage("Invio in corso");
    let accepted = false;
    try {
      const { requestToken } = await readJson("/auth/csrf");
      const result = await readJson(pending.current.route, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": requestToken,
        },
        body: pending.current.body,
      });
      accepted = true;
      await reread(result.snapshot.tenantId);
      pending.current = null;
      setUncertain(false);
      setEdit(null);
      setMessage("Salvato e riletto dal server");
    } catch (error) {
      failure(error);
      const code = error instanceof HttpFailure ? error.status : 503;
      if (!accepted && !uncertain && [400, 404, 409].includes(code)) {
        pending.current = null;
        setUncertain(false);
        if (code === 409) {
          setEdit(null);
          try {
            await reread(selected);
          } catch (readError) {
            failure(readError);
          }
        }
      } else {
        setUncertain(true);
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!edit || sending.current || pending.current) return;
    const payload = {
      commandId: crypto.randomUUID(),
      operation: edit.operation,
      kind: edit.kind,
      tenantId:
        edit.kind === "tenant" && edit.operation === "create" ? null : selected,
      resourceId: edit.node?.id || null,
      parentId: edit.parentId,
      name,
      expectedRevision: edit.node?.revision || 0,
    };
    pending.current = {
      route: payload.tenantId
        ? directoryPath + "/" + payload.tenantId + "/commands"
        : directoryPath,
      body: JSON.stringify(payload),
    };
    await sendPending();
  }
  async function delegate(operation: "grant" | "revoke") {
    if (!owner || pending.current || sending.current || !selected) return;
    const member = memberships.find(m => m.membershipId === memberId);
    if (!member) return;
    pending.current = {
      route: directoryPath + "/" + selected + "/delegations",
      body: JSON.stringify({ commandId: crypto.randomUUID(), operation, membershipId: member.membershipId, internalIdentityId: member.internalIdentityId, bindingHash: member.bindingHash, expectedRevision: member.revision }),
    };
    await sendPending();
  }
  const labels: Record<Kind, string> = {
    tenant: "tenant",
    company: "società",
    site: "sede",
    warehouse: "magazzino",
  };
  const newLabels: Partial<Record<Kind, string>> = {
    company: "Nuova società",
    site: "Nuova sede",
    warehouse: "Nuovo magazzino",
  };
  function branch(node: OrganizationNode, kind: Kind) {
    const next: Kind | null =
      kind === "tenant"
        ? "company"
        : kind === "company"
          ? "site"
          : kind === "site"
            ? "warehouse"
            : null;
    const children =
      next === "company"
        ? hierarchy!.companies
        : next === "site"
          ? hierarchy!.sites
          : next === "warehouse"
            ? hierarchy!.warehouses
            : [];
    return (
      <article className="organization-branch" key={node.id}>
        <h3>{kind === "tenant" ? "Dettagli tenant" : node.name}</h3>
        <p>
          {labels[kind]} · Revisione {node.revision}
        </p>
        <div className="organization-actions">
          {(owner || kind !== "tenant") && <Button
            disabled={frozen}
            variant="outline"
            onClick={() => begin(kind, "rename", node, node.parentId || null)}
          >
            Rinomina {labels[kind]}
          </Button>}
          {next && (
            <Button
              disabled={frozen}
              variant="outline"
              onClick={() => begin(next, "create", null, node.id)}
            >
              {newLabels[next]}
            </Button>
          )}
        </div>
        {next &&
          (children.some((child) => child.parentId === node.id) ? (
            children
              .filter((child) => child.parentId === node.id)
              .map((child) => branch(child, next))
          ) : (
            <p className="muted">Nessun elemento: {labels[next]}</p>
          ))}
      </article>
    );
  }
  return (
    <section className="organization">
      <div className="page-heading">
        <p className="eyebrow">Piattaforma / Organizzazione</p>
        <h1>Amministrazione organizzativa</h1>
        <p>
          La presenza nel menu non concede permessi. Nessun contesto aziendale
          viene attivato.
        </p>
      </div>
      {status === 401 ? (
        <>
          <p>Sessione assente o scaduta</p>
          <Button onClick={() => auth("login")}>
            Accedi con identità federata
          </Button>
        </>
      ) : (
        <>
          <Button
            variant="outline"
            disabled={frozen}
            onClick={() => auth("logout")}
          >
            Esci dalla sessione
          </Button>
          {status === 200 ? (
            <>
              <p>{owner ? "Autorità globale verificata" : "Delega organizzativa verificata"}</p>
              {tenants.length === 0 && (
                <p>
                  Nessun tenant disponibile. Crea il primo tenant con il comando
                  dedicato.
                </p>
              )}
              <div className="organization-toolbar">
                <label>
                  Tenant destinatario
                  <select
                    value={selected}
                    disabled={frozen}
                    onChange={(e) => selectTarget(e.target.value)}
                  >
                    <option value="">Seleziona un tenant</option>
                    {tenants.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </label>
                {owner && <Button
                  disabled={frozen}
                  onClick={() => begin("tenant", "create", null, null)}
                >
                  Nuovo tenant
                </Button>}
                <Button
                  disabled={frozen}
                  variant="outline"
                  onClick={() =>
                    selected ? selectTarget(selected) : location.reload()
                  }
                >
                  Rileggi dal server
                </Button>
              </div>
              {hierarchy ? (
                <Card>
                  <CardHeader>
                    <h2>{hierarchy.tenant.name}</h2>
                    <p>
                      Struttura del tenant destinatario · Nessun accesso ai dati
                      operativi
                    </p>
                  </CardHeader>
                  <CardContent>
                    {branch(hierarchy.tenant, "tenant")}
                    {owner && <section aria-label="Delega struttura organizzativa">
                      <h3>Delega struttura organizzativa</h3>
                      <p>Solo struttura di questo tenant. Nessuna gestione utenti o accesso operativo.</p>
                      <label>Membership esistente
                        <select value={memberId} disabled={frozen} onChange={e => setMemberId(e.target.value)}>
                          <option value="">Seleziona una membership verificata</option>
                          {memberships.map(m => <option key={m.membershipId} value={m.membershipId}>
                            {m.internalIdentityId} · {m.active ? "Attiva" : "Non attiva"} · Revisione {m.revision}
                          </option>)}
                        </select>
                      </label>
                      {memberships.length === 0 && <p>Nessuna membership verificata disponibile.</p>}
                      <Button disabled={frozen || !memberId} onClick={() => delegate("grant")}>Concedi delega struttura</Button>
                      <Button disabled={frozen || !memberId} variant="outline" onClick={() => delegate("revoke")}>Revoca delega struttura</Button>
                    </section>}
                  </CardContent>
                </Card>
              ) : (
                <p>
                  Seleziona esplicitamente un tenant per consultarne la
                  struttura.
                </p>
              )}
              <noscript>
                <ul>
                  {tenants.map((t) => (
                    <li key={t.id}>
                      <a href={"/organization?tenant=" + t.id}>{t.name}</a>
                    </li>
                  ))}
                </ul>
              </noscript>
              {edit && (
                <Card>
                  <CardContent>
                    <form
                      onSubmit={save}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") {
                          event.preventDefault();
                          cancel();
                        }
                      }}
                    >
                      <h2>
                        {edit.operation === "create" ? "Creazione" : "Rinomina"}{" "}
                        {labels[edit.kind]}
                      </h2>
                      <label>
                        Nome
                        <input
                          autoFocus
                          value={name}
                          disabled={frozen}
                          onChange={(e) => setName(e.target.value)}
                          required
                        />
                      </label>
                      <Button disabled={frozen} type="submit">
                        Salva
                      </Button>
                      <Button
                        disabled={frozen}
                        type="button"
                        variant="outline"
                        onClick={cancel}
                      >
                        Annulla
                      </Button>
                    </form>
                  </CardContent>
                </Card>
              )}
            </>
          ) : (
            <p>
              {status === 403
                ? "Autorità amministrativa assente o revocata"
                : "Servizio non disponibile. Nessun dato autorizzato disponibile."}
            </p>
          )}
        </>
      )}
      {uncertain && (
        <aside role="alert">
          <p>Esito incerto. Contesto e comando congelati.</p>
          <p>
            Non chiudere questa pagina. Ripetere soltanto lo stesso comando; la
            rilettura dal server confermerà lo stato corrente.
          </p>
          <Button disabled={busy} onClick={() => sendPending()}>
            Riprova lo stesso comando
          </Button>
        </aside>
      )}
      <p role="status" aria-live="polite">
        {message}
      </p>
      <noscript>
        JavaScript necessario per accesso, uscita e modifiche; le letture
        autenticate sono disponibili lato server.
      </noscript>
    </section>
  );
}
