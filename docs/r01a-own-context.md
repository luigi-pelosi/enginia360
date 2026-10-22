# R01.a — proprio contesto organizzativo e capability

## Contratto e stato

Subincremento #56 di R01 #41, D74–D77. Implementazione bounded, non R01.b né UI01.b. Esiti remoti e SHA sono registrati nella PR/issue dopo l'esecuzione, non anticipati qui.

Riutilizza `GET /api/v1/organization/contexts`: principal interno già verificato da OIDC/cookie o bearer, membership e tenant risolti dal server dentro transazione RLS. Restituisce soltanto le tuple società/sede/magazzino con **proprio** grant `organization-context.read` esatto. La scelta non concede un permesso e parametri query/header tenant/utente non sono autorità. Nessuna directory di utenti, lista dei grant altrui, inventario completo di capability, estensioni/prezzi/stock o segreto del connettore.

Estensione immutabile del contratto esistente: `capability=organization-context`, `readPermission=organization-context.read`, `canWrite` vero solo con attivazione true e proprio `organization-context.write` sulla medesima tupla. `capabilityEnabled` ora è nullable: true attiva, false disabilitata, null non configurata. La left join conserva il contesto autorizzato anche senza attivazione; null non diventa true. Non si uniscono ingenuamente i grant `company_permissions` di altre azioni. Non è un inventario amministrativo generale: gli altri moduli mantengono le rispettive letture/azioni.

Shell italiana esistente, solo nel nginx R00 effimero: selezione, azione/scope e stato capability visibili; read-only/off/non configurata non pubblicizzano la scrittura della nota tecnica esistente. Nessun nuovo comando o editor commessa. Vuoto valido senza provisioning; ogni Riprova svuota contesti/opzioni/scope precedenti, rilegge sessione/CSRF/grant; expiry e indisponibilità hanno messaggio e recupero. Il server rivaluta l'autorizzazione a ogni richiesta anche se una pagina aperta non è ancora aggiornata: `canWrite` è proiezione informativa, non credenziale né promessa di grant futuro.

Storico: `GetNote` conserva il proprio controllo read esatto indipendente dall'attivazione, già esistente e riesercitato; off nega nuove note ma non lo storico autorizzato. Revoca read nasconde contesto e nota alla richiesta successiva; revoca write nega immediatamente la nuova scrittura senza attendere cookie expiry. Nessun nuovo grant/capability è creato dal codice applicativo, nessuna migrazione/privilegio DB è necessario.

## D77 e consegna successiva R01.b

Conferma e provenienza esatte nel registro D77 e sintesi attiva nel dossier 02/piano/backlog/issue #41. Proprietario/operatore trusted inizializza **offline**, con verifica identità e tracciamento, binding/membership e mandato limitato. Nessuna operazione di provisioning reale è stata eseguita. L'app web non ottiene questo potere.

R01.b resta aperta, separata: un percorso grant operativo allowlistato verso **altra membership già trusted del medesimo tenant**, solo azioni/scope esplicitamente delegati nel mandato valido. Concessione/rinnovo/revoca del mandato e binding restano owner; niente self-grant, allargamento mandato, subdelega o creazione di altri admin. Prima del codice fissare il grant operativo concreto nel contratto e provare: mandatario/bersaglio/scope, mandato revocato e race con revoca, atomicità/idempotenza, privilegi DB minimi e audit minimizzato correlabile. Possesso di un grant non implica delegabilità. Nessun invito/account linking/onboarding, entitlement o attivazione capability; lifecycle/create/dedup/rimozione R02 non decisi da D77. Questa specifica non dichiara implementati comandi o journal amministrativo conforme.

## RED → GREEN eseguito

Comando per ciascun tracer: `timeout 600 python3 scripts/run-r00b-tests.py`, log scratch `r01a-red*.log` / `r01a-green*.log`.

| Tracer | RED reale | GREEN reale |
|---|---|---|
| Proprio grant visibile | Chromium login reale riuscito, `readPermission` undefined invece di organization-context.read | query correlata propria, azione/capability/canWrite e tamper query/header verificati |
| Attivazione assente | dopo SQL di sola fixture, `contexts.length` 0 invece di 1 | left join, null esplicito e canWrite false; capability off conserva storico, nega nuova nota |
| Shell scope/capability | login e nota/rilettura riusciti, locator #scope assente | rendering italiano, read-only/off disabilitati, refresh dopo revoca svuota opzioni/scope; session expiry rimuove contesto |
| Registro D77 | guard fermo a 76 decisioni rifiuta D77; due mutation accettate erroneamente (`0 == 0`) | D1–D77 univoci, sintesi attiva e limiti della delega obbligatori |
| Impact guard | script documentale non mappato rifiutato | mapping esplicito guard-only; nuove assertion sui path R01 selezionano browser/migrations e API dirette, non Accounting/architettura |

La prima prova UI dopo riavvio ha correttamente mostrato transitorio servizio indisponibile: fixture corretta per attendere HTTP 200 prima dell'assert di sessione scaduta, non timeout ampliato. Un altro tentativo ha passato 14 assert Chromium ma fallito il conteggio pool finale perché il nuovo riavvio finale lasciava zero connessioni: la fixture ora riapre una vera sessione e lettura autorizzata prima dell'assert invariato di **un** backend. Nessuno di questi tentativi è dichiarato suite passata.

## Verifiche locali finali

- `python3 scripts/test-ci-impact.py`: 8 test; guard C00 PASS e `test-productization-consistency.py`: 15 test, incluse due nuove mutation D77. Guard runtime/CI: r00a 4, TLS 1, lifecycle 3, CI runtime 7. `git diff --check` pulito.
- `timeout 300 python3 scripts/test-r00b-lifecycle.py --actual`: PASS TERM con PostgreSQL sospeso e Chromium vivo, cleanup inventari verificato. Il primo tentativo ha realmente fallito il raggiungimento del marker: riproduzione deterministica da 0.8 s ha mostrato `select(fd)` che non vede la seconda riga già letta in anticipo dal TextIOWrapper. Nuovo test RED (uscita ordinaria 0 al posto di TERM), GREEN con pipe binaria non bufferizzata/lettura os.read. Nessuna estensione della deadline, retry o skip; nuova prova Docker reale passata.
- API tramite SDK pinned con locked restore e filtro `AUTH_FILTER`: 54 pass, 1 theory runtime-only skipped nell'invocazione offline; non è prova runtime. Publish e query NuGet incluse transitive: nessun package vulnerabile segnalato. La theory reale binding/pool è selezionata dal runner dipendente R00.a/CI dispatch.
- UI immagini pinned: `npm ci`, `npm run build`, `npm run build:ui01` (entrambi includono `tsc --noEmit`), audit 0 vulnerabilità. Warning bundler Ant Design `use client` preesistenti, nessuna soppressione. React/editor sorgenti e lock invariati: nessuna suite editor generale imposta come gate; shell testata con Chromium e fetch reali.
- Browser finale `r01a-final-browser.log`: **14 named checks, 0 skipped**, real Keycloak confidential code/S256 → TLS API → PostgreSQL, note SQL finali esattamente 2 e un backend applicativo con pool massimo 1; capability false/null, cross-tenant, grant/action/scope e tamper, read/write revocati alla prossima richiesta, outage503/recovery, copied cookie/logout/restart e rendering/refresh reali. Cleanup verificato: container protetti e 25 volumi invariati.
- Non si dichiara passata la full B02–B14: policy owner impact-scoped, contabilità interna/codice/test preservati. Runtime exact-head dispatch obbligatorio; skipped job non è pass.

## Chiusura R00 #40, già verificata

Readback remoto: PR #55, candidate `3aea9ffc0b69b469078f42a02defbddab75490a8`, main `7389127a53a7ea2ad0b377f6ed2b3e13bf54c15e`, tree identico. Run PR **39783474443** e dispatch **39783546725** success, browser 12 check zero skip, job migration/binding/RLS/pool realmente eseguito, TERM/cleanup success. R00.a prova ripetibilità avvio/stop/restore nello stack effimero; non richiede riavvio del bootstrap.

Il 22 ottobre 2026 eseguito **solo read-only** `sh scripts/smoke.sh http://127.0.0.1`: PASS HTML italiano, system/status, live/ready Healthy, OpenAPI. `docker inspect` bootstrap web/api entrambi healthy e avviati il 18 ottobre, ID originali. I primi probe esplorativi su `/health` e `/api/v1/status` davano 404: non sono stati usati come prova; lo smoke canonico usa le route esatte sopra. Compose/nginx bootstrap non cambiati, nessun nuovo compose up/rebuild/restart/stop necessario o autorizzato su quel target protetto. Lo smoke non dichiara il vecchio bootstrap aggiornato a R00 né autenticazione produttiva. #40 closed/Project Completato dopo readback; #41 In corso, R02–R06 Backlog.

## Limiti e rollback

Nessun nuovo ambiente persistente/manuale, deploy, dato/utente reale, chiamata ERP, acquisto, provider/MFA produttivo o readiness OPE/R06. Bootstrap/Tailscale 443→localhost:9119 e storage/backups esclusi dai runner. Nessuna implementazione IdP backchannel/global logout aggiunta: limiti R00.b restano quelli documentati.

Rollback applicativo con PR che ripristini proiezione/shell e test coerenti; nessun dato/migrazione/ledger da cancellare o downgrade SQL. Il runner rimuove solo progetto random/config esatti. Storico immutabile, Billing/Accounting e UI01 editor invariati.
