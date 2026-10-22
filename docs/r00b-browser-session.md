# R00.b — browser OIDC e sessione locale revocabile

Stato: implementazione tecnica sintetica, D74–D76. Completa il bridge di [stage 1](r00b-identity-boundary.md); non è provisioning commerciale, scelta del provider produttivo, MFA/federazione approvata, go-live o UI01.b.

## Contratto consegnato

- Middleware ufficiale `Microsoft.AspNetCore.Authentication.OpenIdConnect` **10.0.13**, confidential client, authorization code, PKCE S256; usa PAR quando il provider lo pubblica. Scope solo `openid`, `SaveTokens=false`, nessuna chiamata user-info/refresh/offline access. ID/access/refresh token non vengono restituiti alla UI né memorizzati nel ticket applicativo.
- Firma RS256, issuer esatto, audience **client ID**, lifetime/skew zero, state/correlation/nonce del middleware. Il manager ufficiale discovery/JWKS rimane responsabile di download, chiavi e refresh; un wrapper rifiuta issuer differente e endpoint authorization/token/JWKS/PAR non HTTPS prima dello scambio credenziali. L'audience bearer API deve essere diversa dal client ID OIDC.
- Il callback risolve **dopo** le verifiche del protocollo la coppia issuer verificato + subject opaco attraverso `ExternalIdentityResolver` già consegnato. Il principal applicativo ha un solo `NameIdentifier` UUID interno; nessun ruolo, email, username, tenant/header o GUID esterno concede binding o grant.
- Binding mancante: callback 403, nessun cookie applicativo e nessun insert. Binding senza membership: sessione valida, contesti `[]`. Il limite corrente rimane una membership tenant e un binding esterno per identità interna; niente account linking o tenant switching.
- Cookie `__Host-enginia360-session`: Secure, HttpOnly, Path `/`, nessun Domain, SameSite Lax, non persistente. Contiene esclusivamente il riferimento protetto a `ITicketStore`, non il principal/token. Store di processo thread-safe, massimo **1024** ticket, chiavi casuali 256 bit, copie serializzate, scadenza assoluta massima **15 minuti**, niente sliding/renewal o resurrezione dopo remove. Capacità esaurita rifiuta la creazione, non elimina sessioni attive per ammetterne altre.
- Ogni richiesta cookie rilegge il binding nel DB e verifica che l'UUID interno corrisponda ancora. Binding rimosso/incoerente: ticket revocato e API 401. Store DB indisponibile: 503 controllato, nessuna autorizzazione da cache. Gli adapter esistenti continuano a verificare membership/capability/azione/scope per ogni operazione.
- Se è presente **qualsiasi** header `Authorization`, viene selezionato solo bearer: un bearer invalido/non utilizzabile non ricade sul cookie. Le API non effettuano challenge OIDC implicito né redirect a login HTML.

### HTTP same-origin

| Percorso | Comportamento |
|---|---|
| `GET /auth/session` | 200 `{ authenticated: boolean }`, nessun identificatore personale/token/grant; errori store 503 |
| `GET /auth/csrf` | request token antiforgery, cookie `__Host-enginia360-csrf` Secure/HttpOnly/Strict; token solo in memoria/form |
| `POST /auth/login` | antiforgery reale obbligatoria; challenge OIDC; redirect finale fisso `/`, nessun return URL o provider controllato dal chiamante |
| `GET /signin-oidc` | handler ufficiale; callback invalido 400 controllato, nessun sign-in; nessuna query OAuth nella destinazione finale |
| `POST /auth/logout` | antiforgery reale e sessione; rimozione ticket/cookie locale prima del redirect fisso `/` |
| `GET /auth/logout` | 405, nessun effetto |
| `/api/**` | comando cookie autenticato: validazione `IAntiforgery`, header `X-CSRF-TOKEN` o form token, prima di ogni endpoint |

Il guard usa namespace `/auth` e `/api` case-insensitive, non una lista fragile di soli due path: copre trailing slash e POST/PUT/PATCH/DELETE, anche endpoint futuri sotto lo stesso prefisso. Origin diverso da quello configurato e `Sec-Fetch-Site: cross-site` sono rifiutati in aggiunta al token. Un finto bearer non può ottenere contemporaneamente autenticazione cookie ed esenzione CSRF. Token mancante/alterato/di altra sessione, form semplice e Origin estranea: 400 `csrf_invalid`, zero scritture. Il callback OIDC non è un comando browser generico: usa le proprie protezioni di protocollo.

### Logout e limiti esatti

**Il logout è locale, non RP-Initiated Logout del provider. Non esiste backchannel logout implementato/promesso.** Non conserviamo ID token per un `id_token_hint` e non esponiamo un webhook che accetti JWT di logout. La sessione IdP può rimanere attiva; un nuovo accesso può quindi usare il suo SSO. Per cambiare account o terminare il suo SSO occorre uscire anche dal provider.

Dopo il completamento del logout locale, ripresentare una copia precedente dello stesso cookie o usarla in un altro tab non autorizza una nuova richiesta. Il riavvio dell'API perde store e protezioni effimere: il vecchio cookie non riprende la sessione; il recupero è un nuovo login. Nessuna garanzia HA, multi-replica, persistenza sessioni o revoca immediata globale è implicita. Una revoca solo presso l'IdP non è rilevata sincronicamente: il residuo applicativo è limitato dalla scadenza assoluta del ticket, al massimo 15 minuti. La rimozione del binding è distinta e verificata alla prossima richiesta DB.

Una richiesta o un callback validato già in volo non è una transazione globale con logout: può terminare dopo di esso. Remove/renew sullo stesso ticket non lo resuscitano; il logout di un ticket non pretende di cancellare tutti gli altri login indipendenti dell'identità. Un requisito futuro di revoca IdP globale richiede un incremento esplicito con notifica realmente firmata/JWKS, replay/tombstone/race e prova della delivery; non è soddisfatto da questa implementazione locale.

## Configurazione e trasporto

Default: `BrowserSessions:Enabled` assente/false. Nessuna route `/auth/*` o callback nuova; login development/diagnostica sono 404 salvo profilo esplicito `SyntheticLegacy` più relativo flag, disgiunto dal profilo browser. Browser e SyntheticLegacy insieme vengono rifiutati all'avvio.

Abilitazione richiede:

- `BrowserSessions:PublicOrigin`: origine HTTPS esatta, senza path/query/userinfo/fragment/trailing slash;
- `BrowserSessions:Authority`: issuer HTTPS canonico esatto, senza query/userinfo/fragment/trailing slash;
- `BrowserSessions:ClientId`, `BrowserSessions:ClientSecret` da sorgente runtime, audience API distinta;
- API HTTPS, certificato valido per nginx e CA fidata per discovery/token/JWKS, DB `VerifyFull`, schema runtime già migrato.

Il percorso R00.b usa TLS end-to-end: nginx HTTPS → API HTTPS, IdP HTTPS, PostgreSQL TLS con verifica CA/hostname. L'API non si fida di forwarding headers: verifica direttamente schema TLS e Host pubblico esatto. Nginx verifica il certificato/SNI API, rifiuta Host diverso e cancella gli header forwarding del client. Nessuna eccezione HTTP, `ignoreHTTPSErrors`, skip certificate validation o porta backend/DB pubblicata. La CA è generata per ciascuna acceptance, fidata esplicitamente da NSS Chromium, client .NET e libpq/Npgsql; non è un impianto PKI/renewal produttivo.

`no-store` sulle risposte sensibili. Referrer policy `same-origin` consente un Origin valido nei form nativi senza inviare referrer al provider; callback `no-referrer`. CSP limita script/connect a self, form a self e origine IdP esatta, vieta frame e base URI. Access log nginx disabilitato e error log limitato a criticità di processo; hosting request logs API esclusi per non registrare query code/state. Diagnostica applicativa conserva metodo/stato/durata/correlation ID, non query/token/cookie. Nessun HAR, trace o screenshot del flusso autenticato è prodotto dal runner.

## Shell runtime minima, non UI01.b

`web/runtime-access.html` + `runtime-access.js`, esposti **solo dal nuovo nginx R00.b**. Login/logout, stato sessione, lettura contesti assegnati e singola creazione/rilettura nota tramite le API organizzative esistenti. Messaggi italiani e retry ricaricano sessione, antiforgery e tutti i contesti; nessuna password raccolta dall'app, token OAuth o storage browser.

La nota viene riletta per ID nella sessione corrente; non esiste lista/storia né recupero dell'ID dopo refresh. Nessun editor commessa generico, inventario endpoint simulato o nuova API di dominio/setup è stato aggiunto. **UI01.b #5 rimane aperta**: occorre collegare l'editor solo ai comandi/letture realmente supportati, mantenendo visibili le funzioni non ancora collegate. R01 decide chi assegna/revoca binding, membership e grant; la fixture SQL privilegiata di acceptance non è un onboarding API né quella policy.

## Acceptance ripetibile, effimera

```sh
python3 scripts/test-ci-impact.py
python3 scripts/test-r00b-migration-tls.py
python3 scripts/test-r00b-lifecycle.py
python3 scripts/run-r00b-tests.py
python3 scripts/test-r00b-lifecycle.py --actual
sh scripts/run-r00a-tests.sh
```

Richiede Docker e `TMPDIR` privato. Il runner non accetta un progetto/target fornito dall'esterno: genera `enginia360-r00b-<random>`, rete interna, nessuna porta pubblicata/volume persistente. Prima applica il manifest a DB vuoto e verifica **tutte** le tabelle business vuote; solo dopo aggiunge utenti/credenziali sintetiche random e fixture SQL opt-in. Client Keycloak confidential con standard flow, S256 obbligatorio, password/direct grant e implicit/service accounts disabilitati, redirect esatto. Utenti, CA, password e secret vengono rimossi col progetto.

Prove reali selezionate:

- Chromium senza CA rifiuta il certificato; Chromium con sola CA effimera segue login IdP reale, callback del middleware e cookie. Verifica hostname negativo, Host/forwarding spoof e dinieghi edge case/trailing/descendant.
- Client secret errato rifiutato; direct grant disabilitato; codice **fresco** trattenuto solo nella fixture negativa viene presentato al token endpoint reale con verifier errato → `invalid_grant`, `PKCE verification failed`. Gli scenari positivi non usano interception/mock.
- Sessione/API/SQL: write e reread nota reali; CSRF mancante/alterato/altro contesto/Origin/form/metodi/case; azione e scope societa/sede/magazzino insufficienti con riferimenti realmente esistenti; cross-tenant; falso bearer; binding mancante e senza membership.
- Pool massimo 1: 20 alternanze concorrenti di due identità/tenant e un solo backend applicativo osservato nel DB; dipendenza R00.a prova anche pool 12, forced RLS e reset transaction-local issuer/subject/tenant.
- Binding rimosso mentre la sessione è attiva; DB realmente sospeso → 503 e recupero 200; logout con IdP sospeso e copia cookie; riavvio API e nuovo login reale. SQL finale esattamente due note autorizzate: nessun effetto dalle richieste negative.
- Stop/cleanup: verifica **tutte** le etichette progetto/config prima di agire, unpause solo di container esatti prima della rimozione, nessun discendente CLI abbandonato. La prova TERM interrompe il runner con DB sospeso e Chromium vivo e confronta inventari protetti.

Store unit tests controllano clock senza sleep lungo, capacità, copie, chiavi nuove e race remove/renew. I test dell'handler usano ID token RS256 firmati e verificano firma/issuer/audience/expiry/nbf/nonce, callback replay, discovery non sicura, assenza di fallback e store outage; non sono sostituti della prova Chromium/JWKS reali.

## RED → GREEN osservato

| Incremento | RED reale | GREEN/verifica |
|---|---|---|
| Sessione anonima/antiforgery | `/auth/session` 404 invece di 200 | session false, cookie CSRF sicuro |
| TLS/config/auth CSRF | config insicura ammessa, auth POST 404, HTTP non protetto | rifiuti TLS/config e 400 antiforgery |
| OIDC/store | login valido 404, ITicketStore non registrato | challenge code/S256/state/nonce e store revocabile |
| Callback con binding | callback firmato valido creava sign-in 302 senza resolver | DB indisponibile 503, nessun cookie; negativi firma/protocollo |
| Cookie binding | cookie noto dava session true nonostante DB down | fail-closed 503; falso bearer 401 |
| API cookie CSRF | **Chromium reale** creava nota 201 senza token | 400 e SQL senza scritture negative |
| Shell | Chromium non trovava Accedi | login e nota/rilettura tramite controlli reali |
| Edge Host | Host estraneo dava 200 | TLS HTTP 400 |
| Audience/metadata | audience uguale ammessa, metadata issuer/HTTP dava redirect 302 | startup rifiutato / 503 prima dello scambio |
| Auth trailing slash | login maiuscolo/trailing 302, logout trailing 401 senza CSRF | 400 come route canonica |
| Migrator TLS | env child perdeva PGSSLMODE/PGSSLROOTCERT | allowlist minima preserva verify-full/CA |
| Cleanup sospeso | nessun unpause del container esatto | unit guard e prova TERM reale |
| Impact CI | selettore assente e nessun opt-in full exception | selezione deterministica + mutation/unknown-path guards |

I problemi di fixture (Keycloak build optimized, profilo sintetico incompleto, Origin:null da no-referrer nei form, redirect interception e attesa logout) sono stati distinti da RED applicativi, non dichiarati bug di produzione o prove PKCE. I test di expiry/capacità/copia/race rafforzano il contratto dello store: non sono presentati come esiti di un provider/backchannel non implementato.

## Policy CI del proprietario — 22 ottobre 2026

**La suite è circoscritta all'ultima implementazione completata e alle sue dipendenze dirette, non all'architettura intera.** Questo aggiorna il precedente gate di routine architecture-wide, non elimina l'acceptance nuova.

`select-ci-impact.py` legge il diff fra SHA esatti, deduplica/ordina i path e pubblica il manifest di selezione nei log/summary. Auth, TLS/browser/fixture runner, migrazioni, lock o selettore/workflow selezionano i test auth e i contratti organizzativi, build API, typecheck/build UI/audit, acceptance Chromium e dipendenze migration/identity/RLS. Un nuovo path eseguibile non mappato fallisce chiedendo una nuova mappatura **test-first**, invece di scegliere silenziosamente zero test o l'intera architettura. Il selettore è volutamente finito per questo incremento; cambiamenti futuri di dominio/entrypoint devono estenderlo esplicitamente.

PR automatiche: impact guard + test/build/audit rappresentativi interessati. Browser e migration runtime sono manual dispatch **mirato** sul candidato esatto, obbligatorio per consegnare R00.b. Uno skip in PR non è un runtime pass. `full_architecture` è false di default anche nel dispatch; solo true abilita i vecchi job B02–B14/all-architecture come eccezione esplicita. Nessun automatic push o automatic main CI è ripristinato. Consegna: PR exact-head fast verde + dispatch mirato exact-head realmente passato, merge di quello SHA e readback dell'identità del tree merged rispetto al candidato verificato; eventuale nuova main verifica solo se necessaria e mirata, non duplicazione completa.

Billing recovery: run main **39761531418** su `7f219425edf565dc337f69be43f59acdecb58e3c` ha realmente avviato entrambi i job; `runtime-migrations` success. Il resto è stato **cancellato su direttiva del proprietario**, non è un all-architecture pass né un nuovo errore di pagamento. ID/SHA/esiti finali di questa consegna appartengono alla PR/issue dopo esecuzione remota, non sono anticipati qui.

## Rollback e confini protetti

Disabilitare il flag browser elimina la superficie nuova, non attiva automaticamente SyntheticLegacy. Per rollback del codice usare una PR; non riscrivere le 14 migrazioni congelate o la 15 già consegnata. Store e CA non hanno dati persistenti da migrare; fermare e rimuovere solo progetto/config etichettati generati dal runner. Il migrator copre con tmpfs anche il VOLUME ereditato dall'immagine PostgreSQL per non generare volumi anonimi.

Bootstrap Compose/nginx, Tailscale 443→localhost:9119, dati/config/backups e 25 volumi conservati sono esclusi dal target. Nessun provider produttivo, OPE/R06, garanzia fiscale/contabile o disponibilità single-host viene approvato dalla prova sintetica. Billing/Accounting interni restano disponibili e non sono stati modificati/deprecati; suite storiche non interessate non vengono dichiarate nuovamente passate senza esecuzione.

## Fonti primarie consultate

Documentazione Microsoft ASP.NET Core 10 OIDC web authentication, cookie `ITicketStore` e antiforgery; OpenID Connect Core e documentazione Keycloak OIDC layers. URL e hash dei contenuti HTTP 200 acquisiti durante l'esecuzione sono nel manifest tecnico scratch `r00b-stage2-primary-research.json`; le versioni runtime sono quelle pinned nei lock/Dockerfile, non una dichiarazione di provider definitivo o di versione produttiva approvata.
