# Enginia360 — Foundation

Riferimento tecnico generale e regole di sviluppo della foundation. Specifiche di dominio: [Business Partner](masterdata_business_partner.md), [Catalogo](masterdata_catalog.md). Per le attività quotidiane: [Manuale utente](manuale-utente.md).

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
- Audit transazionale delle operazioni amministrative.
- Nazioni e città condivise, ricerca locale e import geografico esplicito.
- Business Partner: identità tenant condivisa, identificativi fiscali, indirizzi e recapiti; numerazione dedicata, rapporti multi-company e ruoli Cliente/Fornitore.
- Pagamenti: metodi, condizioni rateali, simulazione delle scadenze e default aziendali e per ruolo Business Partner.
- Catalogo: identità tenant-wide di articoli/servizi, unità e conversioni, categorie, tipologie, marchi, identificativi, confezioni e dati fisici; configurazioni autonome di utilizzo per azienda e quattro numerazioni sul nucleo condiviso.

Sono esclusi i processi operativi successivi: documenti, ordini, commesse, movimentazione e valorizzazione di magazzino, incassi e pagamenti effettivi, fatturazione e contabilità. Non sono introdotti identity provider esterni, intercompany, organizzazioni predefinite o dati dimostrativi automatici.

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

Il nome precede il codice nei form. I **codici anagrafici sono facoltativi**, non vengono generati e sono univoci nel rispettivo ambito quando valorizzati. Stringhe vuote/spazi diventano NULL; in modifica l'omissione conserva il valore. Eccezioni: codice tenant obbligatorio al login, codici tecnici dei permessi gestiti dal sistema e codice Business Partner obbligatorio, assegnato secondo la numerazione dedicata descritta sotto.

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

### Business Partner

Identità condivisa nel tenant, rapporti distinti per azienda e ruoli `CUSTOMER`/`SUPPLIER`, senza anagrafiche duplicate. Numerazione BP tenant-wide separata dalla configurazione commerciale. Modello, invarianti, autorizzazioni aziendali, persistenza e API sono definiti nella [specifica Business Partner](masterdata_business_partner.md).

### Catalogo

Identità e configurazioni condivise nel tenant, nello schema `masterdata`, senza azienda obbligatoria. Unità con codice/simbolo obbligatorio e significato immutabile; categorie indipendenti dalla natura; tipologie con natura economica GOOD/INTANGIBLE/SERVICE/CHARGE modificabile soltanto in assenza di articoli collegati e default non retroattivi. Solo GOOD è materiale e ammette dati fisici/gestione stock; le altre nature non introducono regole fiscali o contabili. Quantità/fattori fino a 12 decimali, conversioni esatte e arrotondamento esplicito a metà lontano da zero. Le unità UNIVERSAL hanno un fattore globale; quelle ITEM hanno rapporti solo nell'articolo, senza conversioni universali fittizie. Quattro numerazioni indipendenti sul nucleo condiviso in `foundation`, isolate dalla serie BP; GOOD e SERVICE esistenti restano invariati.

`CatalogItem` governa codice, riferimenti, identificativi, unità alternative, dati fisici dei soli beni e ciclo ACTIVE/SUSPENDED/ARCHIVED. ACTIVE è il default in creazione; ARCHIVED non è creabile e richiede conferma irreversibile al salvataggio. Natura derivata dalla tipologia, immutabile; codice e unità base bloccati dalla prima attivazione. I vecchi codici manuali restano riservati. Marchio distinto da produttore/fornitore. Nessun prezzo, stock, IVA, conto o flag operativo aziendale sul master. Modello, API e invarianti nella [specifica unica Catalogo](masterdata_catalog.md).

`CatalogItemCompany` governa abilitazione opt-in e configurazioni operative indipendenti per azienda, senza duplicare il master. Default della tipologia copiati soltanto alla prima associazione, unità predefinite tra quelle ammesse dall'articolo, disponibilità effettive calcolate e stock previsto solo per GOOD. Permessi con ambito aziendale sullo stesso ruolo; nessuna associazione automatica, movimento, prezzo o regola fiscale/contabile.

La UI riunisce le viste in **Anagrafiche → Catalogo → Articoli e servizi**, con tab **Identità** e **Per azienda**, secondo il modello Business Partner. I permessi restano distinti: il solo lettore aziendale può raggiungere il contenitore senza ottenere lettura o CRUD sul master. Tab, filtri e bozze sono isolati per utente/tenant e recuperabili al refresh; il menu resetta la schermata senza eliminare le mutazioni incerte. La vecchia rotta UI aziendale è un alias compatibile, non una voce separata; le API non cambiano.

### Valute

`foundation.currency` è un catalogo globale condiviso, esposto come `/data/currencies`: codice alfabetico e numerico a tre caratteri univoci, nome, unità minori opzionali e stato abilitato. La consultazione è disponibile agli utenti autorizzati; la modifica è riservata al Super Admin globale attivo. La baseline incorpora 178 codici distinti dalla lista corrente ISO 4217 SIX pubblicata il 17 settembre 2026: `https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml`, SHA-256 `33139b438657d1cee116ba737807ea71d19d6de4b90f799a09c56f0cc6a1b0ff`. I valori N.A. sono `NULL`, non due decimali. È uno snapshot, non un aggiornamento automatico; comprende anche codici di test e unità di conto.

Per database esistenti, `database/migrations/20261120_currency.sql` crea tabella, trigger, grant e dati in una transazione, con timeout e lock advisory. È manuale e non idempotente: va applicata una sola volta come `postgres`, dopo verifica dei prerequisiti e backup. Il seed coincide staticamente con quello della baseline; ciò non dimostra l'esito dell'upgrade o rollback su una specifica installazione. Verificare prima su copia isolata della baseline precedente, senza presumere che sia già stata applicata in produzione.

La modifica valuta della UI conserva la versione originale anche nel recupero della bozza e invia `expectedVersion`; una versione obsoleta produce conflitto, non sovrascrittura. Le bozze prive di versione affidabile non sono inviabili. Per database con la tabella già presente serve anche la migrazione manuale `database/migrations/20261120_currency_version.sql` prima della nuova API. Le chiamate legacy senza token restano non condizionali: dettagli e limiti in [currency-concurrency.md](currency-concurrency.md).

Nell'anteprima scadenze Pagamenti il server accetta soltanto codici abilitati con unità minori numeriche e verifica la precisione dell'importo; N.A., disabilitati e sconosciuti sono rifiutati. L'interfaccia propone solo valute abilitate con precisione nota e valida l'importo in base alle unità minori selezionate, usando il passo corrispondente. Non sono implementati cambi valutari o conversioni.

### Pagamenti

Metodi e condizioni appartengono all'azienda. Una condizione contiene almeno una rata e percentuali per un totale esatto del 100%; i differimenti e le regole di calendario sono espliciti. Il calcolo è indipendente dal database e assegna il residuo di arrotondamento all'ultima rata. Default aziendali e default per ruolo Business Partner sono distinti; la risoluzione considera nell'ordine valori espliciti, rapporto aziendale, azienda e selezione manuale. I riferimenti inattivi non sono proposti per nuove operazioni. L'accesso richiede permesso e azienda sullo stesso ruolo attivo.

La UI mostra metodi e condizioni in tabelle filtrabili con finestre di dettaglio/modifica; la condizione ha schede Generale e Rate, con l'anteprima scadenze contestuale nella scheda Rate. Le impostazioni aziendali restano nella pagina. Metodi, condizioni e default usano versioni attese per rilevare aggiornamenti concorrenti; un conflitto richiede rilettura e confronto, non un reinvio cieco.

Il recupero al refresh usa `sessionStorage` nella stessa scheda ed è subordinato a contesto, esistenza del record e autorizzazioni attuali; non sostituisce un salvataggio e non è garantito se lo storage è indisponibile. La navigazione da menu può chiudere l'editor e scartare la bozza. Un timeout o una risposta persa non dimostrano il fallimento del commit: il blocco prudenziale del reinvio non è idempotenza, e occorre verificare lo stato autorevole prima di procedere.

Le nuove installazioni includono `database/masterdata_payments.sql` nella baseline; per database esistenti la migrazione `database/migrations/20261119_payments.sql` è manuale e non assegna permessi ai ruoli. Il catalogo FatturaPA iniziale contiene solo i codici previsti nell'incremento. Documenti, snapshot, conti di regolamento, movimenti e contabilizzazione restano fuori dal perimetro.

### Pagina Impostazioni

È un contenitore di navigazione per configurazioni e cataloghi specifici. Non è una risorsa CRUD e non richiede permessi generici propri. Menu e rotta sono disponibili soltanto se almeno una funzione discendente è consultabile; in caso contrario anche accesso diretto, refresh e cronologia conducono alla prima pagina autorizzata, oppure a un’area neutra se non esistono pagine accessibili. Le singole funzioni mantengono le proprie autorizzazioni: numerazioni, cataloghi di sistema e default aziendali dei pagamenti rimangono separati.

## 3. Identità e autorizzazioni

### Un solo utente

`User`, `DbSet<User> Users`, tabella `foundation."user"`, risorsa API `users`. Non esistono identità parallele `account` o `app_user`.

Nome, cognome ed email sono obbligatori; email non necessariamente univoca. Username univoco nel tenant senza distinzione maiuscole/minuscole. Nascita facoltativa e non futura; telefono facoltativo, massimo 50 caratteri. Lingue `it`/`en`, default italiano. `displayName` è calcolato da nome e cognome, non persistito.

| Identità | Ambito |
|---|---|
| Utente ordinario | Un solo tenant |
| Super Admin | Globale, `tenant_id=NULL`, autorità piattaforma esplicita |

Un ruolo tenant, un'email o il primo accesso non rendono Super Admin. Il globale può preselezionare un'organizzazione al login senza cambiare identità: `selectedTenantId` è contesto rivalidato, non appartenenza o grant.

Per il Super Admin la selezione corrente della UI sopravvive al refresh nella stessa scheda: `sessionStorage` con chiave per utente `workspace-tenant:{id}`. All'avvio si carica l'elenco autorevole delle organizzazioni prima di ripristinare selezione, liste e bozze; una selezione non più disponibile diventa vuota. Anche nessuna selezione è esplicita e non ricade sull'organizzazione del login. Gli utenti ordinari ignorano la preferenza; logout la elimina e un nuovo login prevale con il proprio contesto. Nessuna modifica a cookie, identità o grant. Rilasciato il 19 novembre 2026, solo frontend `workspace-tenant-recovery`: 10 test frontend, typecheck/build e 5 percorsi browser mirati superati, con refresh di bozze nuove/esistenti e concorrenza preservata. Readback HTTPS/asset e immagine esatta verificati, backend/database/grant/Serve/mount invariati. Checkpoint privato `/root/.config/enginia360/releases/workspace-tenant-20261119T214424/`. Un tentativo browser per moduli ha incluso accidentalmente casi storici ereditati e ha superato il limite; non costituisce accettazione globale. La verifica finale usa i cinque casi espliciti nel log `workspace-tenant-recovery/browser-final-recovered.log`.

Nella CRUD utenti del tenant il globale vede anche soltanto la propria riga globale, readonly e non assegnabile a relazioni tenant; gli ordinari non vedono identità globali.

### Profilo e password

Ogni autenticato può leggere/modificare il proprio profilo anche senza grant o tenant selezionato. Campi ammessi: nome, cognome, email, nascita, telefono e lingua. Username, tenant, stato e autorizzazioni non sono modificabili dal profilo.

Un solo salvataggio può aggiornare dati e password. Il cambio password facoltativo richiede corrente e nuova; la nuova è diversa e lunga 14–256 caratteri. **La sola password corrente autocompilata non attiva il cambio.** La password corrente è trattata come valore esatto, senza trim. Il cambio iniziale obbligatorio precede le altre operazioni.

### RBAC tenant

```text
User → Role → Permission
User → Group → Role → Permission
```

Si uniscono le concessioni attive. Nessun permesso diretto utente, deny, gruppo annidato o gerarchia di ruoli. Ruoli, gruppi e catalogo permessi appartengono al tenant. Per le operazioni `business-partner-companies.*` e `catalog-item-companies.*`, l'ambito è aziendale: il ruolo che concede l'operazione deve contenere anche l'azienda in `role_company`. Gli altri permessi tenant esistenti mantengono il loro ambito; l'elenco aziende non attribuisce automaticamente diritti ad altri moduli o sedi.

Il catalogo è finito, readonly e contiene **97 operazioni**, incluse Pagamenti e Catalogo multi-company; `catalog-types.delete` abilita l'eliminazione delle sole tipologie senza articoli collegati:

| Risorse | Operazioni |
|---|---|
| `companies`, `sites`, `warehouse-types`, `warehouses`, `warehouse-locations`, `users`, `groups`, `roles`, `sales-organizations`, `purchasing-organizations` | `read`, `create`, `update`, `delete` |
| `permissions`, `countries`, `cities`, `currencies` | `read` |
| `users` | `reset_password` |
| `roles` | `assign`, `assign_permissions` |
| `roles` | `assign_companies` |
| `groups` | `assign_users` |
| `purchasing-organizations` | `assign_scope` |
| `business-partners` | `read`, `create`, `update` |
| `business-partner-numbering` | `read`, `update` |
| `business-partner-companies` | `read`, `create`, `update`, `use_customer`, `use_supplier` |
| `payment-methods`, `payment-terms` | `read`, `create`, `update` |
| `payment-settings`, `payment-partner-defaults` | `read`, `update` |
| `payment-schedule` / `payment-resolution` | `preview` / `read` |
| `catalog-units` | `read`, `create`, `update` |
| `catalog-types` | `read`, `create`, `update`, `delete` |
| `catalog-categories` | `read`, `create`, `update`, `delete` |
| `catalog-numbering` | `read`, `update` |
| `catalog-items` | `read`, `create`, `update`, `activate`, `deactivate`, `archive` |
| `catalog-brands` | `read`, `create`, `update` |
| `catalog-item-companies` | `read`, `create`, `update` |

Creare un tenant materializza il catalogo, **non ruoli o grant impliciti**. Codici sconosciuti, legacy non di sistema e vecchi `.write` non concedono autorità. `tenants` è esclusivo del globale; Nazioni/Città hanno policy globali dedicate, fuori dal catalogo tenant.

| Relazione | Lettura | Modifica |
|---|---|---|
| `user-roles`, `group-roles` | `read` del proprietario | `roles.assign` |
| `group-users` | `groups.read` | `groups.assign_users` |
| `role-permissions` | `roles.read` | `roles.assign_permissions` |
| Copertura acquisti | `purchasing-organizations.read` | `purchasing-organizations.assign_scope` |
| Aziende dei ruoli | `roles.read` e `companies.read` | `roles.assign_companies` |

Creare/modificare un record non autorizza le assegnazioni; `users.update` non autorizza il reset password. Le modifiche di sole associazioni richiedono i relativi permessi, non update/read dell'anagrafica, e restituiscono soltanto l'ID.

Policy e handler ASP.NET Core applicano default deny. Identità, stamp, stato tenant e concessioni vengono riletti a ogni richiesta; il cookie non conserva grant autorevoli. Lo scope dei riferimenti viene controllato oltre al permesso. Nessuna RLS: filtri applicativi e FK hanno responsabilità distinte.

## 4. Database e installazione

Unico ingresso di installazione: [`database/foundation.sql`](../database/foundation.sql). Le definizioni condivise Numbering appartengono a `foundation`; Business Partner e Pagamenti conservano i frammenti [`masterdata_business_partner.sql`](../database/masterdata_business_partner.sql) e [`masterdata_payments.sql`](../database/masterdata_payments.sql). Il Catalogo usa un solo frammento finale [`masterdata_catalog.sql`](../database/masterdata_catalog.sql), non una catena di parti incrementali o migrazioni obsolete. La tabella unità resta `masterdata.catalog_unit_of_measure` anche quando la sua definizione è posta fra i prerequisiti della baseline. Non applicare la baseline a dati esistenti.

| Area | Tabelle |
|---|---|
| Organizzazione | `tenant`, `company`, `site`, `sales_organization`, `purchasing_organization` |
| Copertura acquisti | `purchasing_organization_company`, `purchasing_organization_site` |
| Magazzino | `warehouse_type`, `warehouse`, `warehouse_location` |
| Identità/RBAC | `user`, `user_group`, `role`, `permission` |
| Associazioni | `user_group_member`, `user_role`, `user_group_role`, `role_permission` |
| Sicurezza | `login_limit`, `audit_event` |
| Geografia | `country`, `city` |
| Business Partner (`masterdata`) | `business_partner`, `business_partner_tax_identifier`, `business_partner_address`, `business_partner_address_usage`, `business_partner_contact_channel` |
| Rapporti BP–azienda (`masterdata`) | `company_business_partner`, `company_business_partner_role` |
| Ambito aziendale RBAC (`foundation`) | `role_company` |
| Numbering condiviso (`foundation`) | `numbering_series`, `numbering_counter` |
| Valute (`foundation`) | `currency` |
| Pagamenti (`masterdata`) | `payment_methods`, `payment_terms`, `payment_term_installments`, `company_payment_settings`, `business_partner_payment_defaults`, `fatturapa_payment_codes` |
| Catalogo (`masterdata`) | `catalog_unit_of_measure`, `catalog_category`, `catalog_item_type` |
| Articoli e servizi (`masterdata`) | `catalog_brand`, `catalog_item`, `catalog_item_code`, `catalog_item_identifier`, `catalog_item_unit`, `catalog_item_physical_data` |
| Utilizzo aziendale Catalogo (`masterdata`) | `catalog_item_company` |

**49 tabelle: 26 in `foundation`, 23 in `masterdata`.** Le altre aree della tabella sopra rimangono in `foundation`. Tenant, utenti, geografia, BP, serie, marchi, articoli e associazioni aziendali non sono precaricati dall'SQL; i cataloghi globali Valute e FatturaPA hanno i rispettivi dati iniziali. La creazione applicativa di un tenant materializza permessi senza grant e inizializza 11 unità e le tipologie Merce/Servizio, senza categorie o confezioni specifiche. Date tecniche e aggiornamento di `updated_at`, dove presenti, sono gestiti dal database; associazioni, FK, unicità e trigger fanno parte dello schema. Il runtime riceve USAGE su entrambi gli schemi senza CREATE e non ha DELETE su BP, rapporti commerciali/ruoli, unità Catalogo, articoli, marchi, configurazioni aziendali, serie o contatori; le tipologie inutilizzate sono eliminabili con permesso dedicato e il registro codici è append-only. Gli accessi aziendali `role_company` sono invece sostituibili per revocare l'autorità. I guard di dominio appartengono a `masterdata`; il trigger timestamp riusa la funzione condivisa `foundation.set_updated_at`.

### Nuova installazione

1. Predisporre PostgreSQL 18, un database nuovo dedicato e il ruolo `enginia360_app` non privilegiato e senza membership. Credenziali e CONNECT al database sono responsabilità del provisioning amministrativo, non del file SQL.
2. Eseguire come `postgres`, fuori da altre transazioni, sulla destinazione nuova esplicitamente selezionata:

   ```sh
   psql -X -v ON_ERROR_STOP=1 -d NOME_DATABASE_NUOVO -f database/foundation.sql
   ```

3. Conservare `foundation.sql` e i frammenti canonici nella stessa directory: `psql -f` risolve le inclusioni relative nella transazione della baseline. Configurare connessione applicativa e origine HTTPS, predisporre il keyring e avviare i servizi.
4. Eseguire il bootstrap esplicito del Super Admin; importare la geografia se richiesta.

Lo script usa una transazione e l'advisory lock `3607902026`. Rifiuta uno schema `foundation` già presente, un esecutore diverso da quello previsto o un ruolo runtime elevato. Non crea login/password né richiede account personali dell'installazione di sviluppo.

Il ruolo runtime riceve USAGE sullo schema e DML sulle tabelle applicative; su `audit_event` **solo INSERT**, non SELECT/UPDATE/DELETE. Non è proprietario e non può creare oggetti o assumere ruoli elevati. Eventuali accessi personali/amministrativi restano separati dal prodotto.

### Database esistente

**Non eseguire la baseline, il frammento BP, DROP o reset sul database attuale.** Il consolidamento non cambia schema, dati, OID, ACL o credenziali esistenti. Le migrazioni BP già applicate sono archiviate, senza modificarne i byte e con checksum, in [`database/migrations/archive/business_partner/`](../database/migrations/archive/business_partner/); non sono il percorso di installazione.

Non esistono `EnsureCreated`, `Migrate`, DDL automatico all'avvio o migration runner. Le evoluzioni successive richiedono nuovi interventi incrementali autorizzati e verificati.

L'installazione esistente ha già ricevuto le evoluzioni BP; non richiede alcuna applicazione SQL per questa riorganizzazione. I checkpoint dei rilasci restano privati in `/root/.config/enginia360/releases/`. Ripristinare richiede schema, dati, immagini e chiavi compatibili, valutando le scritture successive al checkpoint.

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
    BusinessPartners/                # aggregato anagrafico, validazione e API dedicate
    Numbering/                       # nucleo BP/Catalogo, discriminante serie esplicito
    Catalog/                         # configurazioni, articoli, figli, marchi e ciclo di vita
    Payments/                        # metodi, condizioni, default e simulazione
  Infrastructure/Persistence/        # AppDb, mapping, identificatori SQL
  Api/Resources/                     # metadata e CRUD/associazioni condivisi
  Shared/Validation/                 # Check e ApiException
  Verification/                      # self-test divisi per ambito
  tests/                             # contratti e struttura
```

Namespace principali: `Enginia360.Modules.Identity`, `.AccessControl`, `.Organizations`, `.Geography`; `Enginia360.Infrastructure.Persistence`; `Enginia360.Api.Resources`; `Enginia360.Shared.Validation`; `Enginia360.Verification.*`.

`Security` e `IdentityState` restano insieme nel modulo Identity perché condividono il ciclo sessione/password/bootstrap. Il catalogo e gli handler autorizzativi sono in AccessControl. La CRUD metadata-driven rimane condivisa, invece di duplicare endpoint identici in ogni modulo. Non sono aggiunti repository astratti, mediator, microservizi o framework modulari.

## 6. Contratti API

Stessa origine HTTPS, nessun CORS pubblico. Oggetti di servizio camelCase; record e campi metadata snake_case. Errori `{code:string,field?:string}`, senza SQL, stack, valori inseriti o segreti. `field` è omesso quando non noto: i consumatori delle risposte precedenti restano compatibili.

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

### API Business Partner e Numbering

Contratti di anagrafica, collezioni, numerazione, rapporti commerciali e accessi aziendali dei ruoli: [Business Partner — Contratti HTTP](masterdata_business_partner.md#6-contratti-http). Il documento descrive anche revisioni indipendenti, errori specifici, controlli aziendali e persistenza immediata delle operazioni correlate.

## 7. Sicurezza

- ASP.NET PasswordHasher, 210.000 iterazioni; password senza hash impedisce login. Password non stampate né auditate.
- Cookie Secure, HttpOnly, SameSite Strict. Sessione massima otto ore, non scorrevole. Keyring persistente `/app/keys`; conservarlo nei rilasci e nei backup.
- POST/PUT/PATCH/DELETE, inclusi login/logout, richiedono Origin canonico esatto e `X-CSRF-TOKEN`. Rigenerare il token dopo variazioni dell'autenticazione.
- Stato utente/tenant e security stamp sono rivalidati; disabilitazione o revoca invalida l'accesso. Cambio obbligatorio consente solo sessione, cambio password e logout.
- Lockout: cinque errori, quindici minuti; trenta login/minuto per IP visto dall'API. Dietro proxy il limite può essere condiviso; non fidarsi di header IP del client.
- HTTPS termina sull'ingresso privato; `App__Origin` imposta lo schema, non gli header client. API `no-store` e `nosniff`.
- Body 64 KiB, profondità JSON 32, pagina massimo 100, ricerca massimo 200 caratteri. SQL parametrico e identificatori da whitelist.
- Advisory lock `3607902026` serializza controllo autorizzazioni e mutazioni amministrative. È una scelta conservativa, non una garanzia di alto throughput.
- Risposte protette trattenute fino al commit. Audit minimizzato prima/dopo e associazioni, mai password, hash, stamp o chiavi. Fallimento audit annulla la mutazione; storia non riscritta.
- File segreti `0600`, directory private `0700`; niente environment completi, connessioni o segreti nei log, nel repository o nel bundle frontend.

## 8. Geografia e import

Nazioni e Città sono dati globali condivisi: per gli utenti ordinari la consultazione richiede rispettivamente `countries.read` e `cities.read`; Valute richiede `currencies.read`. La manutenzione di questi tre cataloghi rimane riservata al Super Admin. I nuovi permessi sono assegnabili nei ruoli tenant, non vengono concessi automaticamente. Una città è una coppia località/CAP; `istat_code` è tecnico e non editabile. Nazione ISO univoca, non modificabile se referenziata; eliminazione RESTRICT. Le città estere possono non avere provincia/regione: gli obblighi della sede rimangono separati.

La UI le presenta come tile di **Impostazioni → Sistema**, non in sidebar. Il contenitore non ha un permesso generico: è visibile soltanto con almeno una funzione discendente autorizzata. Consultazione e modifica delle singole funzioni dipendono dalle rispettive autorizzazioni.

| Endpoint | Comportamento |
|---|---|
| `GET /api/addresses/countries` | `{provider:"catalog",items:[{isoCode,name}]}`, solo nazioni abilitate |
| `GET /api/addresses/autocomplete` | `{items:[{label,address,city,province,postalCode,countryCode,region}],attribution:""}` |

Entrambi richiedono create oppure update della risorsa indicata nel tenant. `resource` facoltativo ammette soltanto `sites` (default compatibile) o `business-partners`; nessuna concessione incrociata tra le due risorse. Il catalogo nazioni accetta solo `tenantId` e `resource`. Query autocomplete ammesse: `tenantId`, `resource`, `field`, `text`, `countryCode`, `city`, `province`, `language`; campi `address/city/province/postal_code`, testo 3–200 caratteri, paese ISO valido, lingua `it/en`.

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

### Incremento Business Partner

Le verifiche di dominio sono riepilogate nella [specifica BP](masterdata_business_partner.md#8-verifiche-e-manutenzione). Per una modifica SQL eseguire installazione nuova ed equivalenza dello schema in PostgreSQL effimero. Per una modifica applicativa avviare immagini esplicite nel progetto `enginia360-business-partner-proof`, con database in tmpfs e credenziali sintetiche:

```sh
docker build -t enginia360-backend:business-partner-proof backend
docker build -t enginia360-frontend:business-partner-proof frontend
python3 tests/application/run_business_partner_proof.py \
  --backend-image enginia360-backend:business-partner-proof \
  --frontend-image enginia360-frontend:business-partner-proof --keep
# Con Playwright e Chromium predisposti: selezionare i singoli casi pertinenti.
# Non usare la discovery per modulo su classi che ereditano altre suite.
python3 tests/application/run_business_partner_proof.py --cleanup
```

Il runner usa un'origine HTTPS logica inoltrata al trasporto HTTP loopback: **non è una prova TLS**. Espande esclusivamente gli include canonici della baseline prima dell'invio via stdin, mantenendo separati Business Partner, Pagamenti e il Catalogo consolidato. I browser richiedono il Chromium dell'harness; `BP_DB_TESTS=true` abilita i test nativi esclusivamente su database isolato. Le prove HTTP usano il ruolo applicativo non privilegiato; eventuali iniezioni audit richiedono il ruolo elevato della sola fixture. Cronologie e report dei precedenti run restano nei checkpoint privati.

### Verifiche mirate Pagamenti

Dalla radice del repository, con Python 3 e Node compatibile con `--experimental-strip-types`:

```sh
python3 -m unittest discover -s tests/database -p 'test_business_partner_source.py' -v
# Solo parità statica: il caso PostgreSQL viene saltato senza PAYMENTS_TEST_CONTAINER.
python3 -m unittest discover -s tests/database -p 'test_payment_permissions.py' -v
(cd frontend && node --experimental-strip-types --test tests/payment-*.test.ts tests/payments-*.test.ts)
# Prova HTTP reale con Docker e immagini disponibili; build prima l'immagine backend:
docker build -t enginia360-backend:payments-proof backend
python3 tests/application/run_payments_proof.py --backend-image enginia360-backend:payments-proof
```

Il runner HTTP crea PostgreSQL e API effimeri, carica la baseline fresca e fallisce anche se i test HTTP sono saltati. Usa l'immagine `postgres:18.6-alpine3.24`, un'origine HTTPS logica su HTTP loopback (non TLS) e nomi fissi `enginia360-payments-http-proof*`; non eseguire due prove contemporaneamente. All'avvio e in chiusura rimuove le risorse con quei nomi e l'etichetta di scope della prova: non utilizzarle per altri scopi. Il file di credenziali sintetiche rimane nella directory di evidenza sotto `TMPDIR`.

`test_payments_schema.py` e il caso runtime di `test_payment_permissions.py` richiedono un container PostgreSQL **isolato**, con ruolo `enginia360_app` e baseline già caricata nel database `payments_test`; impostare `PAYMENTS_TEST_CONTAINER` al nome esatto prima della discovery. Non puntare mai a dati reali. Questi test non preparano né eliminano il database. Il runner HTTP non prova l'upgrade: la migrazione manuale va verificata separatamente su una copia isolata della baseline precedente, includendo rollback e assenza di nuove assegnazioni ai ruoli. Il confronto sorgente o un test statico non sostituisce tale prova.

### Foundation e regressioni mirate

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

La baseline SQL deve dimostrare: schema equivalente allo stato corrente salvo ACL personali escluse dalle nuove installazioni; assenza di tenant e dati operativi, con i soli cataloghi globali iniziali dichiarati; rifiuto di una seconda applicazione; rollback e retry; privilegi minimi; integrità e concorrenza della copertura acquisti. Non normalizzare via differenze sconosciute per ottenere un confronto positivo.

Dopo il refactoring: manifest sorgenti prima della build, publish reale, candidato esatto su copia, regressioni pertinenti e readback dopo rilascio. TLS reale distinto dai test interni; screenshot autentici. Audit vulnerabilità aggiornato richiede accesso alle fonti: un publish offline riuscito non è un audit corrente.

## 11. Regole di sviluppo

1. **Niente overengineering**, salvo richiesta espressa del proprietario.
2. **Codice standard-based, clean, snello, leggibile e manutenibile.**
3. **Naming convenzionale:** standard de facto coerenti con le tecnologie per schemi, tabelle, campi e codice.
4. **Riusabilità:** privilegiare fortemente il riuso.
5. **Verifiche locali e incrementali:** unit test, lint, test funzionali, semantici e sintattici locali, senza GitHub Actions; incrementali salvo diverse disposizioni.
6. **Rilascio automatico:** ogni implementazione include verifiche pertinenti, checkpoint di rollback, rilascio sull'installazione Enginia360 esistente e verifica dello stato pubblicato, senza richiedere una conferma separata. Interventi distruttivi o fuori perimetro richiedono autorizzazione specifica. Commit, push, PR e attivazione di pipeline CI/CD restano soggetti all'avallo del proprietario.
7. **Lingue:** UI italiano default più inglese; nomi codice/DB inglesi; commenti codice/DB e documentazione tecnica/utente italiani.
8. **Codici anagrafici:** facoltativi e secondari, dopo nome/dati principali; niente generazione per colmare assenze. Codice tenant/login obbligatorio, ma dopo Nome nel form. Codici tecnici permessi obbligatori e readonly.
   Eccezione autorizzata Business Partner: codice obbligatorio e immutabile, automatico o manuale secondo la configurazione Numbering dedicata.
   Eccezione autorizzata Catalogo: codice/simbolo obbligatorio per le unità di misura; codice articolo obbligatorio, automatico o manuale e immutabile dalla prima attivazione. Il codice articolo inserito o modificato manualmente ammette esclusivamente lettere ASCII A–Z/a–z e cifre 0–9, massimo 40 caratteri, senza spazi, accenti, simboli o normalizzazioni automatiche. Gli articoli sospesi mai attivati in modalità manuale possono cambiarlo, senza liberare i codici precedenti. Categorie, tipologie e marchi conservano il codice facoltativo.
9. **Integrazioni esterne:** segreti in impostazioni e schermate dedicate autorizzate, cifrati nel DB; non in file root/bundle, risposte API o audit/log. `integrations.` riservato ed escluso dalla CRUD generica.
10. **Select con ricerca in tempo reale**, salvo richiesta esplicita diversa; comportamento condiviso anche su cataloghi brevi, etichette localizzate e tastiera.
11. **Messaggi specifici e precisi:** avvisi, errori e informazioni indicano l'operazione o il controllo effettivo, il campo e la riga interessati quando noti, e l'azione utile. Non sostituire una causa conosciuta con un messaggio generico né esporre dettagli SQL, dati riservati o cause non verificate. Se indistinguibili, indicare tutti i campi rilevanti. Non distinguere username inesistente/password errata né rivelare stato prima della password corretta.
12. **Geografia coerente in tutti i CRUD:** ogni form con campi geografici riusa controlli e comportamento condivisi di autocompletamento e selezione nazione. Ricerca nel catalogo locale, soglia/debounce, tastiera, annullamento delle risposte obsolete e compilazione manuale sono uniformi. I permessi appartengono al CRUD chiamante, mai a un'altra anagrafica. La selezione modifica soltanto la bozza e l'indirizzo interessato; le strade rimangono manuali in assenza di stradario. I cataloghi Nazioni/Città sono la fonte dei suggerimenti, non un servizio esterno.

13. **Permessi coerenti con le rotte:** catalogo e selettore dei ruoli seguono la gerarchia completa della navigazione, usando gli stessi metadati dei percorsi. I nodi intermedi raggruppano i permessi discendenti, senza introdurre permessi impliciti o ereditarietà delle autorizzazioni. Codici e assegnazioni restano indipendenti dalla presentazione dell'albero.

14. **Persistenza delle tabelle contestuali/correlate:** sull'entità principale già salvata, le azioni confermate sulle righe sono effettive e persistono senza richiedere anche il Salva generale. Non salvano implicitamente la bozza dei dati principali. Prima della creazione del padre, le righe restano locali e vengono registrate insieme al primo salvataggio.

15. **Campi obbligatori:** ogni campo obbligatorio è contrassegnato da un asterisco visibile accanto all'etichetta, coerente con le regole effettive, comprese quelle condizionali.

16. **Selezioni obbligatorie:** nelle nuove maschere, in assenza di un valore iniziale definito dal dominio, preselezionare la prima opzione valorizzata e ammissibile. Non sostituire scelte già effettuate, bozze recuperate o valori esistenti; i campi facoltativi restano invariati.

17. **Stati delle entità:** rappresentare gli stati visualizzati tramite badge coerenti; i controlli per modificarli restano selettori o altri elementi di input appropriati.

18. **Parità creazione/modifica:** validazioni e obbligatorietà dei campi sono speculari in creazione e modifica, nella UI e nelle API, salvo diversa richiesta esplicita del proprietario. Riutilizzare le stesse regole; uno stato diverso non introduce implicitamente deroghe. Nei salvataggi parziali validare il risultato complessivo, conservando i valori omessi. Restano valide le immutabilità e le eccezioni di dominio approvate.

19. **Ordine dei filtri:** il campo di ricerca occupa sempre la prima posizione a sinistra; lo stesso ordine viene mantenuto quando i controlli si dispongono su più righe o su mobile.

20. **Filtri compatti e adattivi:** preferire una sola riga, con etichette brevi e comprensibili. Se lo spazio non basta, mantenere la ricerca e i primi filtri sulla riga principale e porre in fondo un pulsante con icona filtri che espande un accordion sottostante con gli altri controlli. Dimensionamento sulla larghezza disponibile, non su un numero fisso di campi. Nascondere un controllo non azzera né disattiva il suo filtro; niente duplicazioni dei controlli o perdita delle selezioni al ridimensionamento.

21. **Allineamento delle tabelle:** celle testuali e relative intestazioni a sinistra; valori numerici, economici e importi in valuta a destra con intestazioni centrate; badge, icone e azioni centrati nelle celle e nelle intestazioni. Usare il tipo semantico delle colonne nei componenti condivisi, senza dedurlo dal contenuto occasionale. I codici identificativi restano testi anche quando composti da cifre.

UI professionale: niente testi su agente, proprietario, prototipo, tecnologia o scelte implementative; niente help text tecnico permanente. Azioni tabellari centrate in colonna di larghezza fissa; preferire icone con nome accessibile e descrizione al passaggio del mouse. Le azioni della videata restano allineate a destra sulla barra dei tab. Un solo Salva per anagrafica e associazioni, salvo le operazioni autonome delle tabelle correlate già persistibili descritte sopra. Permessi a domini/risorse/operazioni, ricerca bilingue e checkbox parziali: filtrare o collassare non perde selezioni, la selezione di un ramo include anche foglie nascoste. Nessun dato demo persistente.
