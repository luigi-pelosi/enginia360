# Enginia360 — Foundation

Riferimento tecnico unico per la foundation. Per le attività quotidiane: [Manuale utente](manuale-utente.md).

## Indice

1. [Prodotto e perimetro](#1-prodotto-e-perimetro)
2. [Dominio e regole](#2-dominio-e-regole)
3. [Identità e autorizzazioni](#3-identità-e-autorizzazioni)
4. [Database e installazione](#4-database-e-installazione)
5. [Moduli backend](#5-moduli-backend)
6. [Contratti API](#6-contratti-api)
7. [Sicurezza](#7-sicurezza)
8. [Geografia e import](#8-geografia-e-import)
9. [Esecuzione e manutenzione](#9-esecuzione-e-manutenzione)
10. [Verifiche locali](#10-verifiche-locali)
11. [Regole di sviluppo](#11-regole-di-sviluppo)

## 1. Prodotto e perimetro

**Enginia360 è un DMS SaaS multi-tenant** per automotive, service e aftermarket, di Luigi Pelosi. Il repository di riferimento è `luigi-pelosi/enginia360`.

L'obiettivo è governare in modo unificato processi operativi, amministrativi e gestionali: officina, commesse e post-vendita; logistica, magazzino e acquisti; fatturazione, contabilità e controllo di gestione. Questa è la visione del prodotto, **non l'elenco delle funzionalità già implementate**.

La progettazione segue DDD pragmatico, API-first, modularità, riuso e interoperabilità. Si procede per incrementi autorizzati dal proprietario; non sono richiesti microservizi o livelli architetturali aggiuntivi in assenza di un'esigenza concreta.

### Cosa comprende la foundation

- Autenticazione locale, Super Admin globale, profilo e password.
- Organizzazioni tenant, aziende, sedi e organizzazioni commerciali.
- Anagrafiche di magazzino, non movimenti o giacenze.
- Utenti, gruppi, ruoli e permessi tenant.
- Impostazioni con ambito esplicito e audit transazionale.
- Nazioni e città condivise, ricerca locale e import geografico esplicito.

Sono esclusi i processi operativi successivi: documenti, ordini, commesse, clienti/fornitori, movimentazione e valorizzazione di magazzino, pagamenti, fatturazione e contabilità. Non sono introdotti identity provider esterni, intercompany, organizzazioni predefinite o dati dimostrativi automatici.

## 2. Dominio e regole

### Struttura organizzativa

```text
tenant
  └─ company
      └─ site
          └─ warehouse → warehouse_type
              └─ warehouse_location
```

Ogni elemento appartiene a un solo proprietario del livello superiore. Il tipo di magazzino appartiene al tenant. UUID e FK composte impediscono riferimenti tra tenant diversi; le associazioni non ammettono duplicati. Le cancellazioni di elementi referenziati sono bloccate.

Il nome precede il codice nei form. I **codici anagrafici sono facoltativi**, non vengono generati e sono univoci nel rispettivo ambito quando valorizzati. Stringhe vuote/spazi diventano NULL; in modifica l'omissione conserva il valore. Eccezioni: codice tenant obbligatorio al login e codici tecnici dei permessi gestiti dal sistema.

### Sedi

- `site_type`: una scelta facoltativa tra `LEGAL`, `LOCAL_UNIT`, `SECONDARY`, senza default.
- `functions`: insieme indipendente, inizialmente vuoto: `OPERATIONAL`, `ADMINISTRATIVE`, `COMMERCIAL`, `PRODUCTION`, `LOGISTICS`, `WAREHOUSE`, `TECHNICAL_SERVICE`, `MANAGEMENT`, `RETAIL`.
- Almeno uno tra `vat_number` e `tax_code` deve essere non vuoto. I dati fiscali rimangono sulla sede; non si deduce la futura sede fiscale dei documenti.
- `address`, `city`, `province`, `postal_code`, `country_code` obbligatori; `region` facoltativa. CAP testuale; paese ISO 3166-1 alpha-2.
- L'indirizzo è uno snapshot: modificare un catalogo non riscrive le sedi. Nessun backfill inventato o FK retroattiva.

Tipologia e funzioni non creano magazzini, organizzazioni commerciali o permessi. In modifica, omissione conserva; `site_type:null` rimuove la scelta; `functions:[]` svuota. NULL, duplicati o codici sconosciuti nelle funzioni sono invalidi.

### Organizzazioni commerciali

**Vendita:** un'organizzazione appartiene a un'azienda; un'azienda può averne diverse. Nome obbligatorio, codice/descrizione facoltativi, stato. Nessun legame rigido a sede o magazzino.

**Acquisto:** appartiene al tenant e copre aziende con una modalità per azienda:

| Modalità | Copertura |
|---|---|
| `all_sites` | Tutte le sedi attuali e future; nessun elenco esplicito |
| `selected_sites` | Un insieme esplicito non vuoto; nuove sedi escluse |

Azienda e sedi devono appartenere allo stesso tenant e alla stessa catena. Elenco vuoto non significa tutte; non si possono mescolare le due modalità. Un'organizzazione senza aziende può esistere, ma non è applicabile ad alcuna sede.

La copertura è un aggregato: viene salvata atomicamente e verificata anche al commit, con protezione delle scritture concorrenti. Disabilitare conserva la composizione; cambiare copertura non riscrive la storia. L'applicabilità richiede tenant, organizzazione, azienda e sede attivi.

**La copertura commerciale è eleggibilità, non autorizzazione utente.** Non cambia l'azienda titolare delle future transazioni, non abilita intercompany e non stabilisce prevalenze automatiche tra organizzazioni applicabili.

### Impostazioni

Ambiti ammessi: tenant; tenant+azienda; tenant+azienda+sede. La sede richiede la propria azienda. Unicità della chiave anche con NULL, JSONB come valore, riferimenti coerenti con il tenant.

Non esistono ereditarietà, precedenze o fallback impliciti. Le chiavi `integrations.*` sono escluse dalla CRUD generica: eventuali segreti futuri richiedono percorsi dedicati autorizzati.

## 3. Identità e autorizzazioni

### Un solo utente

`User`, `DbSet<User> Users`, tabella `foundation."user"`, risorsa API `users`. Non esistono identità parallele `account` o `app_user`.

Nome, cognome ed email sono obbligatori; email non necessariamente univoca. Username univoco nel tenant senza distinzione maiuscole/minuscole. Nascita facoltativa e non futura; telefono facoltativo, massimo 50 caratteri. Lingue `it`/`en`, default italiano. `displayName` è calcolato da nome e cognome, non persistito.

| Identità | Ambito |
|---|---|
| Utente ordinario | Un solo tenant |
| Super Admin | Globale, `tenant_id=NULL`, autorità piattaforma esplicita |

Un ruolo tenant, un'email o il primo accesso non rendono Super Admin. Il globale può preselezionare un'organizzazione al login senza cambiare identità: `selectedTenantId` è contesto rivalidato, non appartenenza o grant.

Nella CRUD utenti del tenant il globale vede anche soltanto la propria riga globale, readonly e non assegnabile a relazioni tenant; gli ordinari non vedono identità globali.

### Profilo e password

Ogni autenticato può leggere/modificare il proprio profilo anche senza grant o tenant selezionato. Campi ammessi: nome, cognome, email, nascita, telefono e lingua. Username, tenant, stato e autorizzazioni non sono modificabili dal profilo.

Un solo salvataggio può aggiornare dati e password. Il cambio password facoltativo richiede corrente e nuova; la nuova è diversa e lunga 14–256 caratteri. **La sola password corrente autocompilata non attiva il cambio.** La password corrente è trattata come valore esatto, senza trim. Il cambio iniziale obbligatorio precede le altre operazioni.

### RBAC tenant

```text
User → Role → Permission
User → Group → Role → Permission
```

Si uniscono le concessioni attive. Nessun permesso diretto utente, deny, gruppo annidato, gerarchia di ruoli o ACL per record. Ruoli, gruppi e permessi valgono per l'intero tenant, non per azienda o sede.

Il catalogo è finito, readonly e contiene **50 operazioni**:

| Risorse | Operazioni |
|---|---|
| `companies`, `sites`, `warehouse-types`, `warehouses`, `warehouse-locations`, `settings`, `users`, `groups`, `roles`, `sales-organizations`, `purchasing-organizations` | `read`, `create`, `update`, `delete` |
| `permissions` | `read` |
| `users` | `reset_password` |
| `roles` | `assign`, `assign_permissions` |
| `groups` | `assign_users` |
| `purchasing-organizations` | `assign_scope` |

Creare un tenant materializza il catalogo, **non ruoli o grant impliciti**. Codici sconosciuti, legacy non di sistema e vecchi `.write` non concedono autorità. `tenants` è esclusivo del globale; Nazioni/Città hanno policy globali dedicate, fuori dal catalogo tenant.

| Relazione | Lettura | Modifica |
|---|---|---|
| `user-roles`, `group-roles` | `read` del proprietario | `roles.assign` |
| `group-users` | `groups.read` | `groups.assign_users` |
| `role-permissions` | `roles.read` | `roles.assign_permissions` |
| Copertura acquisti | `purchasing-organizations.read` | `purchasing-organizations.assign_scope` |

Creare/modificare un record non autorizza le assegnazioni; `users.update` non autorizza il reset password. Le modifiche di sole associazioni richiedono i relativi permessi, non update/read dell'anagrafica, e restituiscono soltanto l'ID.

Policy e handler ASP.NET Core applicano default deny. Identità, stamp, stato tenant e concessioni vengono riletti a ogni richiesta; il cookie non conserva grant autorevoli. Lo scope dei riferimenti viene controllato oltre al permesso. Nessuna RLS: filtri applicativi e FK hanno responsabilità distinte.

## 4. Database e installazione

Unico schema iniziale: [`database/foundation.sql`](../database/foundation.sql). Contiene direttamente lo stato finale, non una concatenazione delle evoluzioni storiche.

| Area | Tabelle |
|---|---|
| Organizzazione | `tenant`, `company`, `site`, `sales_organization`, `purchasing_organization` |
| Copertura acquisti | `purchasing_organization_company`, `purchasing_organization_site` |
| Magazzino | `warehouse_type`, `warehouse`, `warehouse_location` |
| Configurazione | `setting` |
| Identità/RBAC | `user`, `user_group`, `role`, `permission` |
| Associazioni | `user_group_member`, `user_role`, `user_group_role`, `role_permission` |
| Sicurezza | `login_limit`, `audit_event` |
| Geografia | `country`, `city` |

**23 tabelle, nessun dato iniziale.** Tenant, utenti, permessi e geografia non sono precaricati dall'SQL. Date tecniche e aggiornamento di `updated_at` sono gestiti dal database; associazioni, FK, unicità e trigger fanno parte dello schema.

### Nuova installazione

1. Predisporre PostgreSQL 18, un database nuovo dedicato e il ruolo `enginia360_app` non privilegiato e senza membership. Credenziali e CONNECT al database sono responsabilità del provisioning amministrativo, non del file SQL.
2. Eseguire come `postgres`, fuori da altre transazioni, sulla destinazione nuova esplicitamente selezionata:

   ```sh
   psql -X -v ON_ERROR_STOP=1 -d NOME_DATABASE_NUOVO -f database/foundation.sql
   ```

3. Configurare connessione applicativa e origine HTTPS, predisporre il keyring e avviare i servizi.
4. Eseguire il bootstrap esplicito del Super Admin; importare la geografia se richiesta.

Lo script usa una transazione e l'advisory lock `3607902026`. Rifiuta uno schema `foundation` già presente, un esecutore diverso da quello previsto o un ruolo runtime elevato. Non crea login/password né richiede account personali dell'installazione di sviluppo.

Il ruolo runtime riceve USAGE sullo schema e DML sulle tabelle applicative; su `audit_event` **solo INSERT**, non SELECT/UPDATE/DELETE. Non è proprietario e non può creare oggetti o assumere ruoli elevati. Eventuali accessi personali/amministrativi restano separati dal prodotto.

### Database esistente

**Non eseguire `foundation.sql`, DROP o reset sul database attuale.** Il consolidamento non cambia schema, dati, OID, ACL o credenziali esistenti. Le vecchie migrazioni sono archiviate fuori dal repository con checksum; non sono più il percorso di installazione.

Non esistono `EnsureCreated`, `Migrate`, DDL automatico all'avvio o migration runner. Le evoluzioni successive richiedono nuovi interventi incrementali autorizzati e verificati.

## 5. Moduli backend

Un solo assembly .NET; namespace coerenti con le cartelle, import espliciti e nessuna nuova dipendenza.

```text
backend/
  Program.cs                         # composition root, pipeline e routing
  Modules/
    Identity/                        # User, autenticazione, sessione, profilo, bootstrap
    AccessControl/                   # catalogo e policy ASP.NET Core
    Organizations/                   # applicabilità e copertura acquisti
    Geography/                       # cataloghi, ricerca locale, import, ISO
  Infrastructure/Persistence/        # AppDb, mapping, identificatori SQL
  Api/Resources/                     # metadata e CRUD/associazioni condivisi
  Shared/Validation/                 # Check e ApiException
  Verification/                      # self-test divisi per ambito
  tests/                             # contratti e struttura
```

Namespace principali: `Enginia360.Modules.Identity`, `.AccessControl`, `.Organizations`, `.Geography`; `Enginia360.Infrastructure.Persistence`; `Enginia360.Api.Resources`; `Enginia360.Shared.Validation`; `Enginia360.Verification.*`.

`Security` e `IdentityState` restano insieme nel modulo Identity perché condividono il ciclo sessione/password/bootstrap. Il catalogo e gli handler autorizzativi sono in AccessControl. La CRUD metadata-driven rimane condivisa, invece di duplicare endpoint identici in ogni modulo. Non sono aggiunti repository astratti, mediator, microservizi o framework modulari.

## 6. Contratti API

Stessa origine HTTPS, nessun CORS pubblico. Oggetti di servizio camelCase; record e campi metadata snake_case. Errori `{code:string}`, senza SQL, stack o segreti.

### Accesso e profilo

| Metodo/percorso | Dati e risposta |
|---|---|
| `GET /api/health` | `{status:"ok"}`, controlla il DB |
| `GET /api/auth/csrf` | `{token}` e cookie antiforgery |
| `POST /api/auth/login` | `{username,password,tenantCode?}` → sessione |
| `GET /api/session` | Sessione o 401 |
| `POST /api/auth/logout` | 204 |
| `PUT /api/auth/password` | `{currentPassword,newPassword}` → 204 |
| `GET /api/profile` | Profilo dell'utente corrente |
| `PUT /api/profile` | `{values?:{first_name?,last_name?,email?,date_of_birth?,phone_number?,preferred_language?},currentPassword?,newPassword?}` → profilo |

Sessione: `{id,username,displayName,preferredLanguage,isSuperAdmin,tenantId,selectedTenantId,mustChangePassword,permissions}`. Senza codice organizzazione accede solo il globale. Con codice attivo, il globale resta globale e preseleziona il tenant; l'ordinario accede soltanto al tenant indicato. Il contesto viene conservato al cambio password e rimosso al logout.

Codice organizzazione sconosciuto/disabilitato: `invalid_organization_code`. Credenziali non valide: `login_details_invalid`, senza distinguere username inesistente e password errata. `account_disabled` e `account_temporarily_locked` solo dopo password corretta. Altri errori principali: `validation_error`, `current_password_invalid`, `forbidden`, `not_found`, `conflict`, `password_change_required`, `rate_limited`, `server_error`.

Il profilo restituisce `{id,username,first_name,last_name,email,date_of_birth,phone_number,preferred_language}`. Le omissioni conservano i dati. Dati e password sono atomici; cambio password rinnova la sessione corrente, revoca le altre e conserva il tenant preselezionato.

### Risorse e relazioni

| Metodo/percorso | Contratto |
|---|---|
| `GET /api/resources` | `{key,readOnly,fields:[{name,type,required,reference?,options?,defaultValue?}]}`[] |
| `GET /api/data/{resource}?tenantId=UUID&page=1&pageSize=25&search=...` | `{items,total,page,pageSize}` |
| `POST /api/data/{resource}` | Record pubblico, 201 |
| `PUT /api/data/{resource}/{id}` | Modifica parziale, record pubblico 200 |
| `DELETE /api/data/{resource}/{id}` | 204; 409 se referenziato |
| `GET /api/links/{relation}/{ownerId}` | `{ids:string[]}` |
| `PUT /api/links/{relation}/{ownerId}` | `{ids:string[]}`, sostituzione atomica, 204 |
| `PUT /api/users/{id}/password` | `{newPassword}`, cambio obbligatorio successivo; non riabilita l'utente |

`tenantId` è richiesto al globale per le risorse tenant; l'ordinario è vincolato al proprio. Non è richiesto per `tenants`, `countries`, `cities`. Anche relazioni e reset password rispettano il contesto tenant.

Tipi metadata: `text`, `textarea`, `boolean`, `json`, `reference`, `date`, `tel`, `select`, `multiselect`. Campi server-managed, proprietà sconosciute e duplicati sono rifiutati. Proiezioni pubbliche escludono password/hash, stamp, flag globali e tentativi login; nessuna API generica per tabelle arbitrarie o audit. I campi editabili sono dichiarati in `Api/Resources/Resources.cs`, unica fonte dei metadata.

### Salvataggio unico

- Creazione: `POST /api/data/{resource}/save`, risposta 201.
- Modifica: `PUT /api/data/{resource}/{id}/save`, risposta 200.
- Corpo: `{values?:object,links?:{relation:string[]}}`; creazione richiede `values`.
- Per `purchasing-organizations`: `coverage?:[{companyId,siteScope:"all_sites"|"selected_sites",siteIds:string[]}]`.
- Lettura copertura: `GET /api/data/purchasing-organizations/{id}/coverage` → `{coverage:[...]}`.

Omissione conserva, `[]` svuota la relazione/copertura indicata; NULL e no-op vuoti non sono validi. Massimo 500 associazioni o sedi complessive. Ogni autorità viene verificata prima delle scritture. Anagrafica, relazioni, copertura e audit committano insieme; un errore tardivo annulla tutto. Per sole associazioni la risposta contiene soltanto `{id}`.

La UI mantiene una bozza e un solo Salva. Annulla non scrive; un errore conserva la bozza. Dopo commit aggiorna la sessione prima di altre letture: una revoca non deve produrre accessi illeciti o far apparire fallito un salvataggio già riuscito.

## 7. Sicurezza

- ASP.NET PasswordHasher, 210.000 iterazioni; password senza hash impedisce login. Password non stampate né auditate.
- Cookie Secure, HttpOnly, SameSite Strict. Sessione massima otto ore, non scorrevole. Keyring persistente `/app/keys`; conservarlo nei rilasci e nei backup.
- POST/PUT/DELETE, inclusi login/logout, richiedono Origin canonico esatto e `X-CSRF-TOKEN`. Rigenerare il token dopo variazioni dell'autenticazione.
- Stato utente/tenant e security stamp sono rivalidati; disabilitazione o revoca invalida l'accesso. Cambio obbligatorio consente solo sessione, cambio password e logout.
- Lockout: cinque errori, quindici minuti; trenta login/minuto per IP visto dall'API. Dietro proxy il limite può essere condiviso; non fidarsi di header IP del client.
- HTTPS termina sull'ingresso privato; `App__Origin` imposta lo schema, non gli header client. API `no-store` e `nosniff`.
- Body 64 KiB, profondità JSON 32, pagina massimo 100, ricerca massimo 200 caratteri. SQL parametrico e identificatori da whitelist.
- Advisory lock `3607902026` serializza controllo autorizzazioni e mutazioni amministrative. È una scelta conservativa, non una garanzia di alto throughput.
- Risposte protette trattenute fino al commit. Audit minimizzato prima/dopo e associazioni, mai password, hash, stamp o chiavi. Fallimento audit annulla la mutazione; storia non riscritta.
- File segreti `0600`, directory private `0700`; niente environment completi, connessioni o segreti nei log, nel repository o nel bundle frontend.

## 8. Geografia e import

Nazioni e Città sono globali: lettura per ogni autenticato, manutenzione soltanto Super Admin. Una città è una coppia località/CAP; `istat_code` è tecnico e non editabile. Nazione ISO univoca, non modificabile se referenziata; eliminazione RESTRICT. Le città estere possono non avere provincia/regione: gli obblighi della sede rimangono separati.

La UI le presenta come tile di **Impostazioni**, non in sidebar. La landing è accessibile senza `settings.read`, ma non concede lettura delle impostazioni tenant.

| Endpoint | Comportamento |
|---|---|
| `GET /api/addresses/countries` | `{provider:"catalog",items:[{isoCode,name}]}`, solo nazioni abilitate |
| `GET /api/addresses/autocomplete` | `{items:[{label,address,city,province,postalCode,countryCode,region}],attribution:""}` |

Entrambi richiedono `sites.create` oppure `sites.update` nel tenant. Query ammesse: `tenantId`, `field`, `text`, `countryCode`, `city`, `province`, `language`; campi `address/city/province/postal_code`, testo 3–200 caratteri, paese ISO valido, lingua `it/en`.

Ricerca locale limitata e accent-insensitive, debounce e cancellazione delle risposte obsolete. Selezionare completa geografia ma conserva la strada manuale; una provincia precedente non blocca una nuova città. Nessuno stradario, geocoding remoto o caricamento integrale delle città nel browser.

**Geoapify è dismesso:** nessun endpoint/configurazione, trasporto, cache applicativa, CLI o rete dedicata. La cancellazione locale non attesta revoca della chiave presso il fornitore.

Import esplicito per operatore fidato, con connessione configurata e payload montato nel runtime:

```sh
dotnet Enginia360.Api.dll import-geography /percorso/assoluto/cities.json
```

Valida il payload, acquisisce il lock e salva nazione, città e audit atomicamente. È idempotente e non sovrascrive manutenzioni manuali. Non viene eseguito all'avvio o periodicamente.

Dataset Italia: 7.894 comuni e 8.458 coppie comune/CAP. Provenienza, licenze, checksum e rigenerazione sono nel [README del dataset](../database/seeds/italy/README.md), da conservare insieme agli archivi. I CAP non sono una certificazione postale.

## 9. Esecuzione e manutenzione

### Stack e servizi

Stack fissato nei manifest: .NET 10/ASP.NET Core, EF Core 10.0.14, Npgsql 10.0.3; PostgreSQL 18.6; Node 24.22.0, Next.js 16.4.5, React 19.3.1, TypeScript 5.9.3, next-intl 4.14.9; shadcn/ui New York, Radix e Tailwind. Digest e dipendenze complete sono nei Dockerfile, Compose e lockfile; non si aggiornano implicitamente.

Tre container Linux: PostgreSQL, backend .NET e frontend Next standalone. SSR non sposta dominio o autorizzazioni sul frontend. Il backend non pubblica porte host.

| Risorsa | Configurazione |
|---|---|
| Database | `enginia360-foundation-db`, volume `enginia360-foundation-db-data` su `/var/lib/postgresql` |
| Keyring | Volume `enginia360-application-keys` su `/app/keys` |
| Frontend | `127.0.0.1:18080` verso proxy, Node interno 3000 |
| Backend | Porta interna 8080, rete `application` interna |
| Configurazione privata | `/root/.config/enginia360/foundation-db.env` e `backend.env` |

`backend.env` contiene `ConnectionStrings__Database` del ruolo runtime e `App__Origin` HTTPS senza slash finale. Il Compose dichiara PostgreSQL su loopback `127.0.0.1:5432`; gli eventuali accessi amministrativi privati dell'installazione esistente non sono prerequisiti della baseline.

Origine privata dell'installazione attuale: `https://vmi3659251.tailfcced0.ts.net:8080`, Tailscale Serve, non Funnel. Non esporre pubblicamente il database né reimpostare ingressi estranei. Container applicativi non root, capability rimosse, `no-new-privileges`, risorse limitate e log ruotati.

Comandi operativi, dopo il provisioning:

```sh
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
# Arresto applicativo senza eliminare dati o chiavi:
docker compose stop frontend backend
```

Non stampare Compose risolto o environment privati. Non usare `down -v`, reset ingressi, DROP o prune globali. Un rilascio deve ricreare soltanto i servizi interessati e verificare immagini, mount e stato effettivi.

### Bootstrap del Super Admin

```sh
dotnet Enginia360.Api.dll bootstrap /percorso/privato.json
```

File privato massimo 8192 byte con `username`, `firstName`, `lastName`, `email`, `password`; password almeno 14 caratteri, nessun `displayName`. Il file deve essere leggibile dal comando, non da gruppo/altri, e va rimosso dopo la consegna autorizzata.

Bootstrap e audit sono atomici. È creata una sola identità globale con tenant NULL e cambio password obbligatorio; l'operazione rifiuta un globale già presente. Nessuna creazione di tenant fittizi o bootstrap automatico all'avvio web.

### Backup e ripristino

Prima di interventi rischiosi: dump coerente, keyring, immagini e inventario di dati/credenziali/grant/schema da preservare, in directory private durevoli. Checksum e prove di restore su un cluster isolato; nessun dato sintetico sul principale.

Ripristinare significa allineare **schema, dati, immagini e chiavi compatibili**. Non sovrascrivere dati successivi al checkpoint né considerare il solo rollback dell'immagine sufficiente dopo modifiche di schema. Verificare autenticazione, autorizzazioni, audit e contratti interessati.

Backup locali e rehearsal non definiscono una politica di disaster recovery. Destinazione esterna, frequenza, retention, responsabilità e RPO/RTO restano da concordare e verificare. Gli originali SQL e documentali di questo consolidamento sono archiviati privatamente in `/root/.config/enginia360/foundation-close/history/`, con manifest SHA-256; non sostituiscono i backup del database.

## 10. Verifiche locali

Test proporzionati alle modifiche e alle dipendenze dirette; nessuna suite globale di routine. Per questo refactoring sono interessati i namespace di tutto il backend, quindi le verifiche includono contratti, self-test e flussi di autenticazione/RBAC/CRUD.

```sh
# Backend, dalla directory backend:
dotnet restore --locked-mode --disable-parallel
dotnet build -c Release --no-restore /p:UseSharedCompilation=false /m:1
# Dalla directory del publish, con connessione di configurazione:
dotnet Enginia360.Api.dll self-test
dotnet Enginia360.Api.dll self-test-site-addresses
dotnet Enginia360.Api.dll self-test-geography

# SQL: cluster effimero; l'oracolo è un dump schema-only acquisito in sola lettura:
python3 tests/database/prove_foundation.py --oracle /percorso/schema.sql --output /percorso/prove

# Frontend: selezionare soltanto file modificati e consumer diretti:
node --experimental-strip-types --test tests/NOME.test.ts
npm run typecheck
```

`RBAC_DB_TESTS=true` e `LOGIN_PRESELECTION_DB_TESTS=true` abilitano prove native con scritture: **solo su database isolato**, mai sul principale. Gli harness HTTP/browser sotto `tests/application/` richiedono destinazione e credenziali sintetiche esplicite. Nei test che preparano o leggono l'audit può essere necessario un ruolo di fixture elevato; non è il ruolo runtime e non prova da solo i suoi privilegi.

La baseline SQL deve dimostrare: schema equivalente allo stato corrente salvo ACL personali escluse dalle nuove installazioni; zero dati; rifiuto di una seconda applicazione; rollback e retry; privilegi minimi; integrità e concorrenza della copertura acquisti. Non normalizzare via differenze sconosciute per ottenere un confronto positivo.

Dopo il refactoring: manifest sorgenti prima della build, publish reale, candidato esatto su copia, regressioni pertinenti e readback dopo rilascio. TLS reale distinto dai test interni; screenshot autentici. Audit vulnerabilità aggiornato richiede accesso alle fonti: un publish offline riuscito non è un audit corrente.

## 11. Regole di sviluppo

1. **Niente overengineering**, salvo richiesta espressa del proprietario.
2. **Codice standard-based, clean, snello, leggibile e manutenibile.**
3. **Naming convenzionale:** standard de facto coerenti con le tecnologie per schemi, tabelle, campi e codice.
4. **Riusabilità:** privilegiare fortemente il riuso.
5. **Verifiche locali e incrementali:** unit test, lint, test funzionali, semantici e sintattici locali, senza GitHub Actions; incrementali salvo diverse disposizioni.
6. **Consegna soggetta ad approvazione:** commit, push, PR e CI/CD richiedono avallo del proprietario.
7. **Lingue:** UI italiano default più inglese; nomi codice/DB inglesi; commenti codice/DB e documentazione tecnica/utente italiani.
8. **Codici anagrafici:** facoltativi e secondari, dopo nome/dati principali; niente generazione per colmare assenze. Codice tenant/login obbligatorio, ma dopo Nome nel form. Codici tecnici permessi obbligatori e readonly.
9. **Integrazioni esterne:** segreti in impostazioni e schermate dedicate autorizzate, cifrati nel DB; non in file root/bundle, risposte API o audit/log. `integrations.` riservato ed escluso dalla CRUD generica.
10. **Select con ricerca in tempo reale**, salvo richiesta esplicita diversa; comportamento condiviso anche su cataloghi brevi, etichette localizzate e tastiera.
11. **Errori pertinenti:** indicare il controllo realmente fallito e l'azione utile, non cause non verificate. Se indistinguibili, indicare tutti i campi rilevanti. Non distinguere username inesistente/password errata né rivelare stato prima della password corretta.

UI professionale: niente testi su agente, proprietario, prototipo, tecnologia o scelte implementative; niente help text tecnico permanente. Un solo Salva per anagrafica e associazioni. Permessi a domini/risorse/operazioni, ricerca bilingue e checkbox parziali: filtrare o collassare non perde selezioni, la selezione di un ramo include anche foglie nascoste. Nessun dato demo persistente.
