# MVP03.b.2b — contratto eseguibile del primo ingresso federato

Refs #166 / #142. **Sorgente completa; prove finali locali eseguite il 4 novembre 2026.**
La consegna rimane **NON VERIFICATA** fino a CI exact-head, merge e readback del
coordinatore. Nessuna validazione intermedia: test, build e audit sono iniziati
soltanto dopo il completamento dell'intero punto. MVP03.b mantiene
`runtimeDelivered=false` fino alla chiusura finale del parent. D98 non viene
riconfermata né sostituita.

## Tracciamento e scelte tecniche minime

- `BrowserSessionModule`: il vero handler OIDC verifica codice, HTTPS discovery,
  firma, issuer, audience, lifetime, state/correlation, nonce e PKCE. Il callback
  `OnTicketReceived` conserva l'issuer validato dall'handler e un solo `sub`.
  Il resolver ordinario rimane un lookup esatto; JWT non associati restano negati.
- `PendingOnboarding`: soltanto un login iniziato da `/auth/onboarding/login/{invitation}`
  può trasformare il callback **non associato** in richiesta pendente. La proprietà
  invito viaggia nello state protetto del vero handler; non è prova d'identità.
  Nessun issuer/subject/email è accettato dal browser come autenticazione.
- Schema/cookie `pending-onboarding` separato da `browser-or-bearer`: nessun
  `NameIdentifier` applicativo, nessuna authority, nessun grant. Non partecipa a
  `RequireAuthorization`, `/auth/session`, directory utenti, company contexts o
  SSR protetto. Solo status/CSRF/logout di onboarding selezionano quel ticket.
  Un header Authorization non valido non ripiega sulla pending cookie.
- Cookie `__Host-enginia360-pending`, Secure/HttpOnly/Lax, lifetime assoluto massimo
  15 minuti, ticket store process-local bounded condiviso ma protezione cookie
  per scheme separata, senza persistenza/renewal. Il restart invalida i ticket,
  non la richiesta SQL. Nessuna durable-claim o global reload recovery dichiarata.
- `0041_federated_onboarding.sql`: private invitations/requests/audit, FORCE RLS,
  owner non-BYPASS e nessun DML/SELECT applicativo sulle nuove tabelle. L'app
  ottiene soltanto EXECUTE dei quattro ingressi finiti. Le GUC derivano dai veri
  handler, come nel confine di fiducia preesistente; un accesso SQL con credenziali
  applicative non è un nuovo identity provider.

## Flusso operativo minimo e isolamento

Il delegato utenti corrente usa `/onboarding-admin` nel proprio tenant;
SUPER ADMIN seleziona esplicitamente un tenant dal proprio elenco già autorizzato.
La sola delega struttura non basta. La directory pending è tenant-scoped, non un
elenco pubblico di clienti. Il pending vede soltanto il proprio requestId,
tenantId, revisione, scadenza e stato; non la directory o i subject altrui.
Il delegato vede issuer e opaque subject esatti **delle sole richieste del tenant**,
confrontandoli e confrontando il codice richiesta nel canale privato concordato.

`invite` genera UUID casuale, revisione1 e scadenza24h; l'UI presenta un link relativo
sullo stesso sito privato. Copia/consegna umana tramite canale esistente: nessun
servizio email, outbox, acquisto o configurazione account IdP. UUID e link sono
routing/context, mai bearer authority. Una sola richiesta autenticata per invito;
un altro soggetto non può sostituirla. Link ricevuto senza autentica federata non
rivela tenant o richieste. La prova pending dura15m dal callback, non viene
rinnovata al refresh. Revoca invito o scadenza impediscono nuova approvazione.
Dopo scadenza: revocare l'invito e crearne uno nuovo; nessun riutilizzo implicito
per una diversa identità. Logout chiude soltanto la sessione pending.

## Comandi e atomicità

Payload chiuso: `commandId`, `operation` (`invite|revoke|approve`), `resourceId`
(null per nuovo invito, UUID dell'invito/richiesta altrimenti), `expectedRevision`.
Nessun ID interno, tenant alternativo, subject o permesso nel payload. Target
route validato con l'autorità corrente; revisione massima2147483646 per comando.
Tutti gli ingressi acquisiscono777036 prima delle righe: stesso ordine delle
revoche owner/deleghe/0040 e delle modifiche ai ruoli. Actor binding esatto e
membership enabled per i delegati sono ricontrollati prima dell'effetto e replay.

`approve` inserisce **prima associazione** con nuovi ID casuali e senza UPSERT:
binding univoco(issuer,subject)/PK internalId + membership con unicità globale
IdentitySubject + access state **Enabled=false, Revision=1** + aggiornamento
request + audit minimizzato immutabile nella stessa transazione. Il default
tecnico disabilitato evita qualsiasi business grant; non introduce un nuovo
workflow di dominio. `command_membership_access`0040 abilita successivamente;
D97 assegna separatamente ruoli. Nessun grant, ruolo, delega o SUPER ADMIN implicito.
L'accesso normale può autenticare un'identità disabilitata, ma i consumer0040
continuano a negare i suoi utilizzi.

Conflitti esistenti, anche nascosti da RLS, non causano merge/rebind, takeover,
seconda membership o divulgazione di altri tenant. Vincoli univoci restano quelli
pubblicati; collisione durante insert usa savepoint/rollback completo e risposta
uniforme forbidden. Fallimento audit a insert o commit differito annulla ogni
nuova riga. Replay identico restituisce snapshot storico solo dopo verifica di
actor corrente ed esatto binding/membership target già creato; non riscrive
access state o grant e non annulla disable/revoche/rebind successivi. Chiave usata
con payload diverso dà conflict; nuovo UUID con vecchia revisione non ripete effetto.
Audit non contiene issuer/subject/email/token: actor interno, binding hash,
authority/revisione, tenant autorizzato, requestId, prima/dopo, timestamp/esito.
Dinieghi minimizzati senza target/payload estranei. Nessun token o tuple nei log.

## UI e trasporto

Next SSR italiano `/onboarding` e `/onboarding-admin`; accesso dal pannello `/users`.
GET privati su allowlist finita del transport HTTPS esistente, solo Cookie
incoming e Host fissato, SNI privato esplicito, no-store, nessuna service credential.
Nessuna cache shared di identità/stato. Nessun dato dal DB in Next.
Comandi richiedono CSRF del browser appena acquisito, origin check e same-site;
letture SSR funzionano senza JS. Nessun comando dentro stato noscript nascosto.
Esito incerto: route/tenant/requestId/revisione/commandId/JSON bytes congelati,
controlli e navigazione ordinaria bloccati. Lost ACK→CSRF refusal→replay→GET fallito
mantiene gli stessi bytes; completamento solo dopo GET autorevole. Un primo400/409
certo libera la form. Il reload forzato/nuovo login perde il tentativo in memoria:
non è un recupero durevole. Dopo approvazione il pending rimane isolato; un nuovo
login ordinario dal provider configurato usa il normale resolver, senza fallback.

## Fonti e risultati della validazione finale locale

Evidenze durevoli: `/root/.hermes/evidence/enginia360-mvp03b2b/final/`.
Ogni comando finale conserva START/EXIT/END, HEAD/tree e hash completi dei file,
compresi fixture e sorgenti non tracciati. I fallimenti rimangono non-passanti.

- Campagne onboarding finali pool4 e pool1: 18 test SQL e 10 test API reali per pool,
  tutti eseguiti senza skip; OIDC/JWT, UI/SSR/CSRF/retry, readback binding/membership/
  stato accesso/audit e 9 screenshot per pool (con/senza JS,390/1024/1440px).
- Consumer membership0040: 18 test SQL e 76 test API per pool1/4, nessuno skip runtime;
  runner e catalogo storico mantengono tutti i nomi attesi, con i quattro ingressi
  onboarding aggiunti esplicitamente.
- Frontend verificato in container Node fissato: 20 test, build e typecheck; audit
  senza vulnerabilità. Consumer UI storico:196 test, build e audit passati.
  API fast in SDK fissato: 187 passati e 25 opt-in runtime non eseguiti in quel job;
  tali skip NON sono prova runtime, coperta dalle campagne isolate dedicate.
- Correzioni finali: inventory aggiunta per le sole tre nuove tabelle (90 record
  precedenti invariati), query della fixture da 100 righe circoscritte senza cambiare
  assertion o deadline, footer SSR onboarding corretto dopo RED su HTML reale.
  Nuove prove di snapshot vecchio, grant invariati e layout sono regressioni,
  non RED retroattivi dell'implementazione. Migrazioni0001–0040 byte-identiche,
  0041 verificata solo in ambienti effimeri; nessun lock dipendenze modificato.
- Prima della consegna servono ancora tutti i job/step realmente selezionati da
  PR e dispatch exact-head `full_architecture=false`, con artefatti riletti.
  Il ledger del coordinatore/PR identifica gli SHA/run finali senza confondere
  test locali su overlay sorgente con una prova del deploy protetto.

Fonti eseguibili mantenute:

- SQL `scripts/test-mvp03b2b-onboarding.py`: percorso delegato, scope/proof, binding
  occupato/uniqueness, replay/rebind, scadenza/revoca, privati/ACL/RLS, audit
  insert/deferred rollback, concorrenza con connessioni fisiche e ordini revoca.
- `FederatedOnboardingTests.cs`: handler OIDC reale firmato, pending cookie,
  API normali negate, header bearer senza fallback, approvazioni concorrenti,
  fresh ordinary login, parsing bounded. Le suite precedenti rimangono selezionate
  per autenticazione OIDC/JWT normale, globale,0040 e consumer interessati.
- `tests/browser/mvp03b2b-onboarding.cjs`: TLS Keycloak sintetico, UI/SSR italiana,
  pending/default isolation, JWT unbound prima e stesso JWT bound dopo approval,
  enable e role espliciti, disable/replay, no-store/noJS, CSRF, retry exact bytes,
  screenshot con/senza JS390/1024/1440px. Fixture IdP preesistente, nessuna modifica account reale.
- Runner effimero `scripts/run-mvp03b2b-tests.py`, pool1 e4; hardening inclusa
  istanza browser viva, SQL readback,40 migrazioni pubblicate byte-identiche,
  source head/tree e digest artefatti, cleanup limitato a risorse possedute.
- CI PR-only e dispatch exact-head `full_architecture=false`, job dedicato due
  pool con pipefail e artifact; mapping finito preserva consumer misti e ignoti
  fail-closed. Nessuna pipeline avviata durante implementazione.

## Gate di consegna e limiti rimasti

Le prove locali non sostituiscono la verifica exact-head selezionata e il merge/
readback del coordinatore. IdP operativo, retention/privacy, MFA, disponibilità,
recovery e commissioning restano gate non provati. Durate/token sono scelte
tecniche minime; nessun uso reale o deployment è autorizzato. Le40 migrazioni
pubblicate e i vecchi record inventory/lock sono preservati;0041 è nuova ed è
stata applicata soltanto in fixture effimere.
Rollback operativo prima di adozione: disabilitare UI/endpoint nuovi con rilascio
correttivo; non cancellare binding/membership/audit eventualmente approvati e non
rimuovere migration da un ledger già applicato. Il coordinatore gestisce merge e tracking; la PR di consegna usa solo Refs #166/#142.
