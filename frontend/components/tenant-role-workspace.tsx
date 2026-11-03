"use client";
import React, { useEffect, useRef, useState, type FormEvent } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { HttpFailure, readJson } from "../lib/organization";
import {
  tenantRolePath,
  type InitialTenantRoles,
  type TenantRoleData,
} from "../lib/tenant-roles";

type Frozen = { readonly path: string; readonly readPath: string; readonly body: string; uncertain: boolean };
export function TenantRoleWorkspace({
  initial,
}: {
  initial: InitialTenantRoles;
}) {
  const [data, setData] = useState<TenantRoleData | null>(initial.data);
  const [status, setStatus] = useState(initial.status);
  const [pending, setPending] = useState<Frozen | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [permissionId, setPermissionId] = useState("");
  const [roleId, setRoleId] = useState("");
  const fence = useRef<Frozen | null>(null);
  useEffect(() => {
    const unload = (event: BeforeUnloadEvent) => {
      if (fence.current) event.preventDefault();
    };
    const navigation = (event: MouseEvent) => {
      if (fence.current && (event.target as Element).closest("a")) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", navigation, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", navigation, true);
    };
  }, []);
  async function login() {
    try {
      const csrf = await readJson("/auth/csrf");
      const form = document.createElement("form");
      form.method = "POST";
      form.action = "/auth/login";
      const input = document.createElement("input");
      input.name = "__RequestVerificationToken";
      input.value = csrf.requestToken;
      form.append(input);
      document.body.append(form);
      form.submit();
    } catch {
      setMessage("Accesso temporaneamente non disponibile.");
    }
  }
  async function send(command: Frozen) {
    if (busy) return;
    setBusy(true);
    setMessage("");
    try {
      const csrf = await readJson("/auth/csrf");
      await readJson(command.path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": csrf.requestToken,
        },
        body: command.body,
      });
      command.uncertain = true;
      const current = await readJson(command.readPath);
      setData(current);
      setStatus(200);
      setPending(null);
      fence.current = null;
      setMessage(
        "Modifica verificata: stato corrente riletto e audit persistito.",
      );
    } catch (error) {
      if (
        error instanceof HttpFailure &&
        (error.status === 400 || error.status === 409) &&
        !command.uncertain
      ) {
        // A definite first refusal cannot have committed this command. Once an
        // acceptance or network loss is possible, never discard the frozen bytes.
        setPending(null);
        fence.current = null;
        try {
          setData(await readJson(command.readPath));
        } catch (readError) {
          setData(null);
          setStatus(readError instanceof HttpFailure ? readError.status : 503);
        }
        setMessage(
          "Comando rifiutato: correggi i dati o aggiorna la pagina per rileggere lo stato corrente.",
        );
        return;
      }
      command.uncertain = true;
      if (
        error instanceof HttpFailure &&
        (error.status === 401 || error.status === 403)
      ) {
        setData(null);
        setStatus(error.status);
      }
      setMessage(
        "Esito da verificare. Riprova lo stesso comando senza cambiare destinatario. Il ricaricamento forzato non conserva il tentativo.",
      );
    } finally {
      setBusy(false);
    }
  }
  function submit(event: FormEvent<HTMLFormElement>, kind: string) {
    event.preventDefault();
    if (!data || fence.current || busy) return;
    const values = new FormData(event.currentTarget);
    const text = (name: string) => String(values.get(name) || "");
    const member = data.memberships.find(
      (m) => m.membershipId === text("membershipId"),
    );
    const active =
      (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") !==
      "revoke";
    let payload: Record<string, unknown> = {
      commandId: crypto.randomUUID(),
      kind,
      resourceId: null,
      expectedRevision: 0,
    };
    if (kind === "membership-access" && member) {
      payload = {
        commandId: payload.commandId,
        membershipId: member.membershipId,
        internalIdentityId: member.internalIdentityId,
        bindingHash: member.bindingHash,
        expectedRevision: member.accessRevision,
        enabled: active,
      };
    } else if (kind === "delegation" && member) {
      payload = {
        ...payload,
        resourceId: member.resourceId,
        expectedRevision: member.revision,
        membershipId: member.membershipId,
        internalIdentityId: member.internalIdentityId,
        bindingHash: member.bindingHash,
        active,
      };
    } else if (kind === "permission") {
      const prior = data.permissions.find((p) => p.resourceId === permissionId);
      const scope = data.warehouses.find(
        (w) => w.warehouseId === text("warehouseId"),
      );
      if (!scope) return;
      payload = {
        ...payload,
        resourceId: prior?.resourceId || null,
        expectedRevision: prior?.revision || 0,
        label: text("label"),
        action: text("action"),
        legalEntityId: scope.legalEntityId,
        siteId: scope.siteId,
        warehouseId: scope.warehouseId,
      };
    } else if (kind === "role") {
      const prior = data.roles.find((r) => r.resourceId === roleId);
      payload = {
        ...payload,
        resourceId: prior?.resourceId || null,
        expectedRevision: prior?.revision || 0,
        label: text("label"),
        permissionIds: values.getAll("permissionIds"),
      };
    } else if (kind === "assignment" && member) {
      const prior = data.assignments.find(
        (a) =>
          a.membershipId === member.membershipId && a.roleId === text("roleId"),
      );
      payload = {
        ...payload,
        resourceId: prior?.resourceId || null,
        expectedRevision: prior?.revision || 0,
        roleId: text("roleId"),
        membershipId: member.membershipId,
        internalIdentityId: member.internalIdentityId,
        bindingHash: member.bindingHash,
        active,
      };
    } else return;
    const frozen = {
      path: tenantRolePath + "/" + data.tenantId + (kind === "membership-access" ? "/membership-access" : ""),
      readPath: tenantRolePath + "/" + data.tenantId,
      body: JSON.stringify(payload),
      uncertain: false,
    };
    fence.current = frozen;
    setPending(frozen);
    void send(frozen);
  }
  const permission = data?.permissions.find(
    (p) => p.resourceId === permissionId,
  );
  const role = data?.roles.find((r) => r.resourceId === roleId);
  const memberOptions = data?.memberships.map((m) => (
    <option key={m.membershipId} value={m.membershipId}>
      Utente {m.internalIdentityId.slice(0, 8)} ·{" "}
      {m.active ? "delega utenti attiva" : "nessuna delega utenti"}
    </option>
  ));
  return (
    <section className="organization tenant-role-workspace">
      <p className="eyebrow">Amministrazione tenant · D97</p>
      <h1>Gestione utenti, ruoli e permessi</h1>
      <p>
        Solo utenti già registrati. Nomi dei ruoli e permessi non nominano
        amministratori. L’accesso al tenant è distinto dalle deleghe; inviti e primo ingresso federato restano un incremento futuro.
      </p>
      {status === 401 && (
        <Button onClick={() => void login()}>
          Accedi con identità federata
        </Button>
      )}
      {status === 403 && (
        <p role="alert">Autorità gestione utenti assente o revocata.</p>
      )}
      {status >= 500 && (
        <p role="alert">Servizio temporaneamente non disponibile.</p>
      )}
      {message && <p role="status">{message}</p>}
      {pending && (
        <Card className="role-panel">
          <p>
            Comando congelato: destinatario, identificativo e contenuto non
            possono cambiare. Recupero solo nella pagina corrente.
          </p>
          <Button disabled={busy} onClick={() => void send(pending)}>
            Riprova stesso comando
          </Button>
        </Card>
      )}
      {initial.tenants.length > 0 && status === 200 && (
        <form method="get" action="/users">
          <fieldset disabled={!!pending || busy}>
            <label>
              Tenant gestione utenti
              <select
                name="tenant"
                defaultValue={data?.tenantId || ""}
                required
              >
                <option value="">Seleziona tenant</option>
                {initial.tenants.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} · {t.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </label>
            <Button type="submit">Apri gestione utenti</Button>
          </fieldset>
        </form>
      )}
      {data && status === 200 && (
        <>
          <p>
            {data.mode === "owner"
              ? "Autorità globale verificata"
              : "Delega gestione utenti verificata"}{" "}
            · Tenant {data.tenantId}
          </p>
          <noscript>
            <p>
              Le letture SSR funzionano senza JavaScript; i comandi richiedono
              JavaScript e protezione CSRF.
            </p>
            <style>{".role-command{display:none!important}"}</style>
          </noscript>
          <Card className="role-panel">
            <h2>Accesso al tenant degli utenti esistenti</h2>
            <p>La disabilitazione impedisce nuovi utilizzi senza cancellare ruoli,
              deleghe, dati o lavori già accettati. La riabilitazione non rinnova
              permessi scaduti o revocati e non crea nuove autorità.</p>
            {data.memberships.map((member) => (
              <form key={member.membershipId} className="membership-command"
                onSubmit={(event) => submit(event, "membership-access")}>
                <input type="hidden" name="membershipId" value={member.membershipId} />
                <p>Utente {member.internalIdentityId} · membership {member.membershipId}</p>
                <p>Accesso al tenant: {member.accessEnabled ? "abilitato" : "disabilitato"}
                  {" "}· revisione accesso {member.accessRevision}</p>
                <p>Delega gestione utenti: {member.active ? "attiva" : "non attiva"}
                  {" "}· Delega struttura: {member.organizationDelegationActive ? "attiva" : "non attiva"}</p>
                {member.isCurrentIdentity && <p role="note">Attenzione: disabilitando il proprio accesso
                  si perde la gestione del tenant. Il ripristino richiede il SUPER ADMIN.</p>}
                {!member.canEnableAccess && data.mode !== "owner" && <p>
                  La riabilitazione di questo destinatario richiede il SUPER ADMIN;
                  non può ripristinare implicitamente poteri amministrativi.</p>}
                <fieldset className="role-command" disabled={!!pending || busy}>
                  <Button type="submit" value="grant"
                    disabled={member.accessEnabled || !member.canEnableAccess}>
                    Abilita accesso al tenant
                  </Button>{" "}
                  <Button type="submit" value="revoke" variant="outline"
                    disabled={!member.accessEnabled}>Disabilita accesso al tenant</Button>
                </fieldset>
              </form>
            ))}
          </Card>
          {data.mode === "owner" && (
            <Card className="role-command role-panel">
              <h2>Delega gestione utenti distinta</h2>
              <form onSubmit={(event) => submit(event, "delegation")}>
                <fieldset disabled={!!pending || busy}>
                  <label>
                    Destinatario delega utenti
                    <select name="membershipId" required>
                      <option value="">Seleziona utente esistente</option>
                      {memberOptions}
                    </select>
                  </label>
                  <Button type="submit" value="grant">
                    Concedi gestione utenti
                  </Button>{" "}
                  <Button type="submit" value="revoke" variant="outline">
                    Revoca gestione utenti
                  </Button>
                </fieldset>
              </form>
            </Card>
          )}
          <Card className="role-panel">
            <h2>Definizioni dei permessi</h2>
            <ul>
              {data.permissions.map((p) => (
                <li key={p.resourceId}>
                  {p.label} · {p.action} · revisione {p.revision}
                </li>
              ))}
            </ul>
            <form
              className="role-command"
              onSubmit={(event) => submit(event, "permission")}
            >
              <fieldset disabled={!!pending || busy}>
                <label>
                  Permesso da modificare
                  <select
                    value={permissionId}
                    onChange={(event) => setPermissionId(event.target.value)}
                  >
                    <option value="">Nuovo permesso</option>
                    {data.permissions.map((p) => (
                      <option key={p.resourceId} value={p.resourceId}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div
                  key={
                    permission
                      ? permission.resourceId + ":" + permission.revision
                      : "new-permission"
                  }
                >
                  <label>
                    Nome permesso
                    <input
                      name="label"
                      required
                      defaultValue={permission?.label || ""}
                    />
                  </label>
                  <label>
                    Azione supportata
                    <select
                      name="action"
                      defaultValue={permission?.action || data.actions[0]}
                    >
                      {data.actions.map((action) => (
                        <option key={action}>{action}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Scope magazzino esatto
                    <select
                      name="warehouseId"
                      required
                      defaultValue={permission?.warehouseId || ""}
                    >
                      <option value="">Seleziona magazzino</option>
                      {data.warehouses.map((w) => (
                        <option key={w.warehouseId} value={w.warehouseId}>
                          {w.name} · {w.legalEntityId.slice(0, 8)} /{" "}
                          {w.siteId.slice(0, 8)} / {w.warehouseId.slice(0, 8)}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <Button type="submit">Salva permesso</Button>
              </fieldset>
            </form>
          </Card>
          <Card className="role-panel">
            <h2>Ruoli configurabili</h2>
            <ul>
              {data.roles.map((r) => (
                <li key={r.resourceId}>
                  {r.label} · {r.permissionIds?.length || 0} permessi ·
                  revisione {r.revision}
                </li>
              ))}
            </ul>
            <form
              className="role-command"
              onSubmit={(event) => submit(event, "role")}
            >
              <fieldset disabled={!!pending || busy}>
                <label>
                  Ruolo da modificare
                  <select
                    value={roleId}
                    onChange={(event) => setRoleId(event.target.value)}
                  >
                    <option value="">Nuovo ruolo</option>
                    {data.roles.map((r) => (
                      <option key={r.resourceId} value={r.resourceId}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </label>
                <div
                  key={
                    role ? role.resourceId + ":" + role.revision : "new-role"
                  }
                >
                  <label>
                    Nome ruolo
                    <input
                      name="label"
                      required
                      defaultValue={role?.label || ""}
                    />
                  </label>
                  <fieldset>
                    <legend>Permessi del ruolo</legend>
                    {data.permissions.map((p) => (
                      <label key={p.resourceId}>
                        <input
                          type="checkbox"
                          name="permissionIds"
                          value={p.resourceId}
                          defaultChecked={role?.permissionIds?.includes(
                            p.resourceId,
                          )}
                        />
                        {p.label} · {p.action}
                      </label>
                    ))}
                  </fieldset>
                </div>
                <Button type="submit">Salva ruolo</Button>
              </fieldset>
            </form>
          </Card>
          <Card className="role-panel">
            <h2>Assegnazione a utenti esistenti</h2>
            <ul>
              {data.assignments.map((a) => (
                <li key={a.resourceId}>
                  Utente{" "}
                  {data.memberships
                    .find((m) => m.membershipId === a.membershipId)
                    ?.internalIdentityId.slice(0, 8)}{" "}
                  · {data.roles.find((r) => r.resourceId === a.roleId)?.label} ·{" "}
                  {a.active ? "attivo" : "revocato"} · revisione {a.revision}
                </li>
              ))}
            </ul>
            <form
              className="role-command"
              onSubmit={(event) => submit(event, "assignment")}
            >
              <fieldset disabled={!!pending || busy}>
                <label>
                  Utente assegnazione
                  <select name="membershipId" required>
                    <option value="">Seleziona utente esistente</option>
                    {memberOptions}
                  </select>
                </label>
                <label>
                  Ruolo assegnazione
                  <select name="roleId" required>
                    <option value="">Seleziona ruolo</option>
                    {data.roles.map((r) => (
                      <option key={r.resourceId} value={r.resourceId}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </label>
                <Button type="submit" value="grant">
                  Assegna ruolo
                </Button>{" "}
                <Button type="submit" value="revoke" variant="outline">
                  Revoca assegnazione
                </Button>
              </fieldset>
            </form>
          </Card>
        </>
      )}
    </section>
  );
}
