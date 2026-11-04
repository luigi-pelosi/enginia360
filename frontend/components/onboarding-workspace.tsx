"use client";
import React, { useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { HttpFailure, readJson } from "../lib/organization";
import { onboardingPath, type OnboardingInitial, type OnboardingData, type PendingStatus } from "../lib/onboarding";

async function authenticate(path: string) {
  const csrf = await readJson("/auth/csrf");
  const form = document.createElement("form");
  form.method = "POST"; form.action = path;
  const input = document.createElement("input");
  input.type = "hidden"; input.name = "__RequestVerificationToken"; input.value = csrf.requestToken;
  form.append(input); document.body.append(form); form.submit();
}

export function PendingOnboardingWorkspace({ status, initial, invitation }: { status: number; initial: PendingStatus | null; invitation: string | null }) {
  const [data, setData] = useState(initial);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function action(path?: string) {
    if (busy) return;
    setBusy(true);
    try {
      if (path) await authenticate(path);
      else { setData(await readJson("/auth/onboarding/status")); setMessage("Stato corrente riletto."); }
    } catch { setData(null); setMessage("Sessione scaduta, invito non disponibile o servizio temporaneamente indisponibile. Ripeti l’accesso dal link ricevuto, senza creare altre richieste."); }
    finally { setBusy(false); }
  }
  async function logout() {
    if (busy) return;
    setBusy(true);
    try {
      const csrf = await readJson("/auth/onboarding/csrf");
      const response = await fetch("/auth/onboarding/logout", { method: "POST", headers: { "X-CSRF-TOKEN": csrf.requestToken }, cache: "no-store", credentials: "same-origin" });
      if (!response.ok) throw new Error("Logout refused");
      window.location.assign("/onboarding");
    } catch { setMessage("Chiusura sessione non verificata. Riprova oppure attendi la scadenza della sessione."); }
    finally { setBusy(false); }
  }
  return <section className="organization tenant-role-workspace onboarding-workspace">
    <p className="eyebrow">Primo ingresso federato · D98</p><h1>Richiesta di accesso al tenant</h1>
    <p>Il link identifica soltanto il percorso: non prova la tua identità e non concede permessi.
      Autenticati con il provider configurato; il responsabile utenti del tenant verifica e approva il soggetto federato esatto.</p>
    {message && <p role="status">{message}</p>}
    {data ? <Card className="role-panel">
      <h2>{data.approved ? "Associazione approvata" : "In attesa di approvazione"}</h2>
      <p>Richiesta {data.requestId} · Tenant {data.tenantId} · revisione {data.revision}</p>
      <p>Prova valida fino a {data.expiresAt}. Comunica il codice richiesta al responsabile attraverso il canale privato concordato.</p>
      <p>Questa sessione consente solo la lettura del tuo stato, non la consultazione degli altri utenti o dei contesti aziendali.</p>
      {data.approved && <p>L’associazione nasce con accesso disabilitato e senza ruoli o deleghe.
        Il responsabile deve abilitare l’accesso e assegnare separatamente i permessi necessari.
        Poi esegui un nuovo accesso federato ordinario: nessuna promozione automatica della sessione pendente.</p>}
      <Button className="onboarding-command" disabled={busy} onClick={() => void action()}>Rileggi il mio stato</Button>{" "}
      <Button className="onboarding-command" disabled={busy} variant="outline" onClick={() => void logout()}>Chiudi sessione pendente</Button>{" "}
      {data.approved && <Button className="onboarding-command" disabled={busy} onClick={() => void action("/auth/login")}>Accedi dopo l’approvazione</Button>}
    </Card> : <>
      {status >= 500 && <p role="alert">Servizio temporaneamente non disponibile.</p>}
      {status === 403 && <p role="alert">Richiesta non disponibile: prova o invito scaduti, revocati o non corrispondenti alla sessione.</p>}
      {!invitation && <p>Apri il link privato di invito ricevuto dal responsabile utenti. Non è disponibile un elenco pubblico dei clienti.</p>}
      {invitation && <Button className="onboarding-command" disabled={busy} onClick={() => void action("/auth/onboarding/login/" + invitation)}>Autenticati per richiedere accesso</Button>}
    </>}
    <noscript><style>{".onboarding-command{display:none!important}"}</style><p>Lo stato è leggibile senza JavaScript. Per iniziare o ripetere l’accesso e per i comandi serve JavaScript con protezione CSRF.</p></noscript>
  </section>;
}

type Frozen = { readonly path: string; readonly body: string; uncertain: boolean };
export function OnboardingAdministration({ initial }: { initial: OnboardingInitial }) {
  const [data, setData] = useState<OnboardingData | null>(initial.data);
  const [status, setStatus] = useState(initial.status);
  const [pending, setPending] = useState<Frozen | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const fence = useRef<Frozen | null>(null);
  useEffect(() => {
    const unload = (e: BeforeUnloadEvent) => { if (fence.current) e.preventDefault(); };
    const navigation = (e: MouseEvent) => { if (fence.current && (e.target as Element).closest("a")) { e.preventDefault(); e.stopImmediatePropagation(); } };
    window.addEventListener("beforeunload", unload); document.addEventListener("click", navigation, true);
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigation, true); };
  }, []);
  async function send(command: Frozen) {
    if (busy) return;
    setBusy(true); setMessage("");
    try {
      const csrf = await readJson("/auth/csrf");
      await readJson(command.path, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-TOKEN": csrf.requestToken }, body: command.body });
      command.uncertain = true;
      const current = await readJson(command.path);
      setData(current); setStatus(200); setPending(null); fence.current = null;
      setMessage("Comando registrato con audit atomico. Stato corrente riletto; nessun ruolo o potere amministrativo automatico.");
    } catch (error) {
      if (error instanceof HttpFailure && [400, 409].includes(error.status) && !command.uncertain) {
        setPending(null); fence.current = null;
        try { setData(await readJson(command.path)); } catch (readError) { setData(null); setStatus(readError instanceof HttpFailure ? readError.status : 503); }
        setMessage("Comando rifiutato. Rileggi la richiesta o correggi i dati prima di un nuovo tentativo.");
      } else {
        command.uncertain = true;
        if (error instanceof HttpFailure && [401, 403].includes(error.status)) { setData(null); setStatus(error.status); }
        setMessage("Esito da verificare: riprova esclusivamente lo stesso comando. Tenant, destinatario e contenuto restano congelati. Il ricaricamento forzato o un nuovo accesso non conservano questo tentativo.");
      }
    } finally { setBusy(false); }
  }
  function command(operation: string, resourceId: string | null, expectedRevision: number) {
    if (!data || busy || fence.current) return;
    const frozen = { path: onboardingPath + "/" + data.tenantId + "/onboarding", body: JSON.stringify({ commandId: crypto.randomUUID(), operation, resourceId, expectedRevision }), uncertain: false };
    fence.current = frozen; setPending(frozen); void send(frozen);
  }
  return <section className="organization tenant-role-workspace onboarding-administration">
    <p className="eyebrow">Gestione utenti · D98</p><h1>Inviti e primo ingresso federato</h1>
    <p>La sola delega struttura non consente questa gestione. L’approvazione crea esclusivamente binding e membership disabilitata.
      Abilitazione e assegnazione ruoli sono comandi distinti e auditati nella gestione utenti.</p>
    <a href="/users">Gestione utenti, accesso e ruoli</a>
    {message && <p role="status">{message}</p>}
    {status === 401 && <Button onClick={() => void authenticate("/auth/login").catch(() => setMessage("Accesso non disponibile."))}>Accedi con identità federata</Button>}
    {status === 403 && <p role="alert">Autorità gestione utenti assente, disabilitata o revocata.</p>}
    {status >= 500 && <p role="alert">Servizio temporaneamente non disponibile.</p>}
    {pending && <Card className="role-panel"><p>Comando congelato; recupero limitato alla pagina corrente.</p><Button disabled={busy} onClick={() => void send(pending)}>Riprova stesso comando</Button></Card>}
    {!!initial.tenants.length && status === 200 && <form method="get" action="/onboarding-admin"><fieldset disabled={busy || !!pending}>
      <label>Tenant destinatario<select name="tenant" required defaultValue={data?.tenantId || ""}><option value="">Seleziona tenant</option>
        {initial.tenants.map(t => <option key={t.id} value={t.id}>{t.name} · {t.id}</option>)}</select></label>
      <Button type="submit">Apri primo ingresso del tenant</Button></fieldset></form>}
    {data && status === 200 && <>
      <p>{data.mode === "owner" ? "Autorità globale verificata · destinazione esplicita" : "Delega utenti corrente verificata"} · Tenant {data.tenantId}</p>
      <noscript><style>{".onboarding-command{display:none!important}"}</style><p>Letture SSR disponibili; comandi con JavaScript e CSRF.</p></noscript>
      <Card className="role-panel"><h2>Inviti privati</h2>
        <p>Crea un link e consegnalo personalmente tramite un canale privato esistente. Nessun invio email automatico.
          Scadenza 24 ore, una sola richiesta per invito; il destinatario deve autenticarsi. Invito o prova scaduti: revoca e genera un nuovo link.</p>
        <Button className="onboarding-command" disabled={busy || !!pending} onClick={() => command("invite", null, 0)}>Crea invito privato</Button>
        {data.invitations.map(i => <article key={i.invitationId}>
          <p>Invito {i.invitationId} · {i.active ? "attivo" : "revocato"} · revisione {i.revision} · scadenza {i.expiresAt}</p>
          {i.active && <p>Link relativo sullo stesso sito privato: <a href={"/onboarding?invitation=" + i.invitationId}>{"/onboarding?invitation=" + i.invitationId}</a></p>}
          <Button className="onboarding-command" disabled={busy || !!pending || !i.active} onClick={() => command("revoke", i.invitationId, i.revision)}>Revoca invito</Button>
        </article>)}
      </Card>
      <Card className="role-panel"><h2>Richieste autenticate del tenant</h2>
        <p>Confronta codice richiesta e identità federata esatta con il destinatario nel canale privato concordato. Non dedurre identità dall’email o dal link.</p>
        {!data.requests.length && <p>Nessuna richiesta autenticata.</p>}
        {data.requests.map(r => <article key={r.requestId}>
          <h3>Richiesta {r.requestId}</h3><p>Issuer verificato: {r.issuer}</p><p>Soggetto opaco verificato: <code>{r.subject}</code></p>
          <p>Revisione {r.revision} · prova fino a {r.expiresAt} · {r.approved ? "associazione approvata" : r.available ? "in attesa di approvazione" : "non approvabile: scaduta o revocata"}</p>
          {r.approved && <p>Membership {r.membershipId} · identità interna {r.internalIdentityId}. Stato accesso corrente nella gestione utenti, non nello snapshot di approvazione.</p>}
          <Button className="onboarding-command" disabled={busy || !!pending || r.approved || !r.available} onClick={() => command("approve", r.requestId, r.revision)}>Approva associazione senza abilitare o assegnare ruoli</Button>
        </article>)}
      </Card>
    </>}
  </section>;
}
