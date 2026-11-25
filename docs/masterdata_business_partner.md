# Business Partner — modello e contratto tecnico

Documento tecnico del dominio BP: identità condivisa, numerazione, rapporti aziendali e ruoli commerciali. Per architettura generale e regole di sviluppo: [Foundation](foundation.md). Per le operazioni: [Manuale utente](manuale-utente.md#8-gestire-i-business-partner).

## 1. Perimetro e responsabilità

Un Business Partner identifica una persona o un'organizzazione una sola volta nel tenant. Cliente e fornitore sono ruoli del rapporto con una specifica azienda, non anagrafiche separate. Lo stesso BP può essere cliente e fornitore dell'azienda A e soltanto fornitore dell'azienda B.

Il modulo `backend/Modules/BusinessPartners/` gestisce anagrafica, validazione, rapporti e utilizzabilità. `Modules/Numbering/` gestisce la numerazione BP; `Modules/AccessControl/` catalogo, policy e assegnazioni aziendali dei ruoli. UI operative in **Anagrafiche → Business Partner**; numerazione in **Impostazioni → Anagrafiche → Business Partner → Numerazione**. Le gerarchie dei permessi seguono questi percorsi.

Esclusi: qualificazione `PROSPECT` del futuro CRM, valuta, listini, plafond, conti contabili, banche, configurazione FatturaPA e documenti gestionali. I default di pagamento sono gestiti separatamente per azienda e ruolo commerciale nel dominio Pagamenti. Non sono introdotti codici locali cliente/fornitore né numerazioni aziendali.

## 2. Persistenza e SQL consolidato

Unica definizione SQL del dominio: [`database/masterdata_business_partner.sql`](../database/masterdata_business_partner.sql). Crea direttamente gli oggetti definitivi, senza `ALTER` o trasferimenti successivi di schema. È inclusa una sola volta dalla baseline [`database/foundation.sql`](../database/foundation.sql), nella stessa transazione e dopo i prerequisiti condivisi. Le definizioni condivise di serie/contatori appartengono ora a [`database/foundation_numbering.sql`](../database/foundation_numbering.sql), incluso prima del frammento BP: il nucleo supporta BP e Catalogo con discriminanti separati, senza modificare il contratto BP.

| Schema | Tabella | Responsabilità |
|---|---|---|
| `masterdata` | `business_partner` | Identità, tipo, stato, codice e revisione |
| `masterdata` | `business_partner_tax_identifier` | Identificativi fiscali multipli |
| `masterdata` | `business_partner_address` | Indirizzi snapshot |
| `masterdata` | `business_partner_address_usage` | Utilizzi e predefiniti degli indirizzi |
| `masterdata` | `business_partner_contact_channel` | Recapiti e principali per tipologia |
| `masterdata` | `company_business_partner` | Rapporto autonomo BP–azienda, stato e revisione |
| `masterdata` | `company_business_partner_role` | Ruoli commerciali del rapporto |
| `foundation` | `numbering_series` | Configurazione della numerazione BP tenant-wide |
| `foundation` | `numbering_counter` | Progressivo e primo utilizzo |
| `foundation` | `role_company` | Aziende autorizzate del ruolo applicativo |

UUID, `tenant_id`, FK composte same-tenant, unicità esplicite e timestamp con fuso. I guard BP sono in `masterdata`; i trigger di aggiornamento riusano `foundation.set_updated_at`. Numerazione e assegnazioni RBAC restano in `foundation` per responsabilità, non per appartenenza all'anagrafica.

### Installazione e storia applicata

**Solo su database nuovo**, con ruolo runtime non privilegiato già predisposto, eseguire come `postgres`:

```sh
psql -X -v ON_ERROR_STOP=1 -d NOME_DATABASE_NUOVO -f database/foundation.sql
```

Conservare baseline e i cinque frammenti canonici elencati nella Foundation nella stessa directory: `psql` risolve le inclusioni relative. Il frammento BP non è un aggiornamento autonomo di un database popolato. La baseline acquisisce il lock `3607902026`, esegue in transazione e non crea tenant, BP, serie, utenti o grant impliciti; i cataloghi globali iniziali e il provisioning delle configurazioni di un nuovo tenant sono descritti nella Foundation. Il catalogo finito dei permessi è definito nella struttura RBAC condivisa e materializzato alla creazione del tenant.

Le tre migrazioni storiche, già applicate all'installazione esistente, sono conservate con checksum in [`database/migrations/archive/business_partner/`](../database/migrations/archive/business_partner/). Non costituiscono il percorso per nuove installazioni e non vanno rieseguite. Il consolidamento dei sorgenti **non modifica il database esistente**, i dati, gli OID, gli owner, le ACL o le credenziali. Non usare DROP, reset o restore sul database corrente per adottarlo.

Il runtime ha USAGE senza CREATE sugli schemi. Può leggere/inserire/aggiornare BP, rapporti e ruoli commerciali ma non eliminarli; i figli anagrafici sono sostituibili/rimovibili. `role_company` permette revoca e sostituzione delle assegnazioni. Audit applicativo e mutazione committano insieme; il fallimento dell'audit annulla la scrittura.

## 3. Anagrafica condivisa

- `ORGANIZATION`: ragione sociale obbligatoria; nome e cognome persona assenti. `PERSON`: almeno nome o cognome in Bozza, entrambi negli altri stati; ragione sociale assente. La denominazione è derivata.
- Stati `DRAFT`, `ACTIVE`, `BLOCKED`, `ARCHIVED`, scelti esplicitamente. Identificativi fiscali, indirizzi e contatti sono facoltativi anche per l'attivazione; inserire una partita IVA non attiva automaticamente il BP. Attivo non certifica l'idoneità fiscale a emettere documenti.
- Codice obbligatorio, univoco nel tenant senza distinzione maiuscole/minuscole e immutabile. Nessuna cancellazione fisica del BP: si archivia, conservando codice e unicità fiscale.
- Identificativi per paese ISO alpha-2 e tipo `VAT`, `FISCAL_CODE`, `FOREIGN_TAX_ID`. Normalizzazione in maiuscolo senza spazi, punti e trattini; unicità tenant/paese/tipo/valore normalizzato, anche tra soggetti archiviati. Nomi uguali ammessi. Per l'Italia: controllo sintattico, non esistenza, checksum o titolarità; IVA di 11 cifre senza prefisso `IT`.
- Un indirizzo richiede strada, città, CAP testuale e paese; provincia facoltativa. Etichetta, civico e informazioni aggiuntive sono facoltativi. Utilizzi `REGISTERED`, `BILLING`, `SHIPPING`, `CORRESPONDENCE`, anche multipli; al massimo un predefinito per BP/utilizzo.
- Recapiti `EMAIL`, `PHONE`, `MOBILE`, `PEC`, `WEBSITE`, scopo facoltativo e al massimo un principale per tipologia. PEC anagrafica non equivale a configurazione di fatturazione elettronica.

La geografia riusa cataloghi e controlli delle Sedi, con risorsa `business-partners` e relativi permessi create/update. Nessun provider remoto, stradario o campo `region` nel BP. I suggerimenti aggiornano soltanto l'indirizzo corrente; la compilazione manuale resta disponibile e modificare i cataloghi non riscrive gli indirizzi registrati.

## 4. Numerazione

Una serie per tenant: `scope=TENANT`, `company_id=NULL`, `entity_type=BUSINESS_PARTNER`, `reset_policy=NEVER`. Nessuna ereditarietà aziendale o numerazione documentale.

Default virtuale: `AUTO`, prefisso `BP-`, padding 6, prossimo numero 1. La sola lettura non scrive; configurazione materializzata al salvataggio esplicito o alla prima creazione BP riuscita. In `MANUAL` il codice è inserito dall'operatore.

Prefisso ASCII stampabile fino a 32 caratteri; padding 1–15; progressivo assegnabile fino a `999999999999999`, senza riuso, reset annuale o wraparound. Dopo il primo utilizzo modalità, formato e progressivo sono protetti. La revisione cambia anche all'allocazione. BP, contatore, figli e audit sono atomici sotto il lock condiviso; nessun `MAX(code)`.

## 5. Rapporti, ruoli e autorizzazioni

Il rapporto BP–azienda è unico per tenant/azienda/BP. I ruoli `CUSTOMER` e `SUPPLIER` sono unici per rapporto e possono coesistere. Relazione e ruoli hanno stato `ACTIVE`/`BLOCKED`; la relazione ha una revisione indipendente dal BP. Le modifiche preservano gli ID commerciali. Nessuna DELETE: il blocco sospende l'uso, mantenendo riferimenti e storico; la riattivazione ripristina l'operatività compatibile con gli altri stati.

I blocchi sono indipendenti: bloccare Cliente per A non blocca Fornitore per A né i rapporti con B. Bloccare il rapporto con A impedisce entrambi i ruoli in A; bloccare/archiviare il BP impedisce l'uso di tutti i suoi rapporti.

### Utilizzabilità e autorità sono verifiche distinte

`BusinessPartnerEligibility.IsEligible` risolve i record dal database e richiede tenant/azienda abilitati, BP `ACTIVE`, rapporto `ACTIVE` e ruolo `ACTIVE`. Non attribuisce autorità. L'uso richiede anche `use_customer` o `use_supplier` per la stessa azienda; `usable_roles` nelle risposte combina stato e concessioni correnti dell'operatore.

I grant derivano da ruoli attivi diretti o da gruppi attivi. **Azione e azienda devono appartenere allo stesso ruolo applicativo**: modifica su Service più sola lettura su Trading non concede modifica su Trading. Nessuna azienda assegnata significa nessun accesso aziendale, salvo Super Admin globale. L'associazione commerciale non è un grant e gli altri permessi tenant non vengono estesi implicitamente alle aziende.

| Permesso | Ambito |
|---|---|
| `business-partners.read/create/update` | Anagrafica condivisa del tenant |
| `business-partner-numbering.read/update` | Configurazione numerazione del tenant |
| `business-partner-companies.read/create/update` | Lettura, associazione e modifica per azienda |
| `business-partner-companies.use_customer/use_supplier` | Uso commerciale per azienda |
| `roles.assign_companies` | Assegnazione/revoca delle aziende nei ruoli |

Le autorizzazioni finite sono nel catalogo condiviso `PermissionCatalog`; non esistono permessi utente impliciti o concessioni incrociate tra ruoli. Leggere le aziende assegnate a un ruolo richiede `roles.read` e `companies.read`; modificarle richiede `roles.assign_companies`.

## 6. Contratti HTTP

Prefisso `/api`; per il globale `tenantId` è obbligatorio nelle operazioni tenant. L'ordinario resta vincolato al proprio tenant. Record snake_case, comandi camelCase; errori `{code,field?}` senza SQL o valori sensibili. Mutazioni protette da Origin canonico e antiforgery, incluso PATCH.

### Identità e numerazione

| Metodo e percorso | Contratto |
|---|---|
| `GET /data/business-partners` | `{items,total,page,pageSize}`; ricerca per denominazione, codice, fiscalità e recapiti |
| `GET /data/business-partners/{id}` | Dettaglio con `version`, `tax_identifiers`, `addresses` con `usages`, `contact_channels` |
| `POST /data/business-partners/save` | `{values,taxIdentifiers?,addresses?,contactChannels?}` → dettaglio 201 |
| `PUT /data/business-partners/{id}/save` | Stesso corpo più `expectedVersion` obbligatorio → dettaglio 200 |
| `GET /business-partner-numbering` | `{mode,prefix,padding,nextNumber,version}` autorevole |
| `PUT /business-partner-numbering` | Tutti i campi e revisione corrente → configurazione aggiornata |

`values` è obbligatorio; `{}` consente aggiornamenti delle sole collezioni in modifica. Insieme omesso conserva; `[]` svuota; NULL rifiutato; massimo 100 righe per insieme. Un insieme sostituito rigenera gli ID figli, non destinati a riferimenti esterni; gli insiemi omessi li conservano. Creazione senza codice in automatico, con codice in manuale. POST/PUT CRUD generici rifiutati con 405, DELETE BP con 409.

### Rapporti aziendali e assegnazioni

| Metodo e percorso | Contratto |
|---|---|
| `GET /business-partner-companies/options` | Aziende autorizzate con le azioni esatte disponibili |
| `GET /business-partner-companies` | Elenco paginato di tutti i rapporti delle sole aziende leggibili |
| `GET /data/business-partners/{bpId}/companies` | Rapporti leggibili di un BP |
| `GET /companies/{companyId}/business-partners` | Elenco paginato per una specifica azienda autorizzata |
| `GET /companies/{companyId}/business-partners/{bpId}` | Dettaglio del rapporto, anche bloccato |
| `POST /companies/{companyId}/business-partners` | `{businessPartnerId,roles?:[CUSTOMER,SUPPLIER]}` → rapporto 201; duplicato 409 |
| `PATCH /companies/{companyId}/business-partners/{bpId}` | `{status,expectedVersion}` → rapporto aggiornato |
| `PUT /companies/{companyId}/business-partners/{bpId}/roles/{roleCode}` | `{status,expectedVersion}` → assegna/aggiorna ruolo e revisione rapporto |
| `GET /companies/{companyId}/business-partners/{bpId}/eligibility/{roleCode}` | `{usable}` con lettura BP e permesso d'uso aziendale esatto |
| `GET /roles/{roleId}/companies` | `{companyIds}` |
| `PUT /roles/{roleId}/companies` | `{companyIds}`; sostituzione atomica auditata, nessun grant operativo implicito |
| `POST /data/roles/save` | `{values,links?,companyIds?}`; crea ruolo, permessi e aziende in un’unica transazione |
| `PUT /data/roles/{roleId}/save` | `{values?,links?,companyIds?}`; salva atomicamente le sole parti inviate |

Nell’editor Ruoli si usano gli endpoint `/save`: `companyIds` omesso conserva le assegnazioni, `[]` le svuota; NULL, duplicati e aziende di altri tenant sono rifiutati. Il campo richiede `roles.assign_companies`, indipendentemente dai permessi necessari per anagrafica e permessi del ruolo. Il percorso PUT separato rimane disponibile per compatibilità API, non come salvataggio autonomo nell’editor.

Gli elenchi commerciali accettano `role`, `usableOnly`, `search`, `page`, `pageSize`. Default: nessun ruolo, `usableOnly=false`, ricerca vuota, prima pagina e 25 righe. Massimo 100 righe per pagina e ricerca di 200 caratteri. Una richiesta a un'azienda vietata resta 403: non diventa lettura generale. Le risposte includono `company_name`, `roles`, `usable_roles` e revisione del rapporto; gli elenchi includono anche codice, nome e stato BP.

## 7. Persistenza UI, concorrenza ed errori

- BP nuovo: identità e figli restano locali fino al Salva generale. Un esito di creazione incerto non autorizza a ripetere automaticamente la POST.
- BP esistente: confermare aggiunta/modifica/rimozione di fiscalità, indirizzi o contatti invia la PUT aggregata con `values:{}`, sola collezione interessata ed `expectedVersion`. Persistenza immediata; figli e revisione autorevoli aggiornati senza salvare la bozza dell'identità. Annullare il padre non annulla queste scritture.
- I rapporti BP mantengono le proprie conferme contestuali. Nell’editor Ruoli, invece, aziende autorizzate, anagrafica e permessi appartengono a un’unica bozza e vengono registrati con il Salva principale nella stessa transazione. Annulla scarta tutta la bozza; selezionare aziende non scrive. Blocchi e rimozioni mantengono le conferme previste.
- Vista **Per azienda** inizialmente senza filtri: tutte le aziende leggibili, tutti i ruoli, inclusi bloccati/non utilizzabili, ricerca vuota. Colonna Azienda esplicita; filtri manuali facoltativi.
- `version` e `expectedVersion` impediscono sovrascritture obsolete. Errori e conflitti conservano i dati tentati; nessun retry di scrittura automatico. Lettura, revisione e audit restano autorevoli sul server.
- Gli errori noti indicano codice e campo/riga, ad esempio `invalid_italian_vat` con `taxIdentifiers[0].value`. Altri codici: `duplicate_tax_identifier`, `stale_version`, `business_partner_code_required`, `business_partner_code_immutable`, `company_partner_exists`, `numbering_in_use`, `numbering_exhausted`. Nessuna certificazione fiscale implicita o normalizzazione aggiunta dalla UI.

## 8. Verifiche e manutenzione

La consolidazione SQL richiede equivalenza dello schema, vincoli, funzioni, owner e ACL con la baseline precedente; installazione nuova senza dati; rollback e rifiuto di riesecuzione. Le migrazioni archiviate restano riproducibili solo nei rispettivi scenari storici isolati.

Confronto ripetibile con una copia della baseline monolitica precedente:

```sh
python3 tests/database/prove_business_partner_consolidation.py \
  --previous /percorso/baseline-precedente.sql --output /percorso/evidenze
```

La prova confronta i dump schema-only di installazione precedente, `psql -f` con inclusione e stdin espanso. Normalizza soltanto versioni pg_dump e nonce di protezione, non differenze di dominio. Verifica l'inventario di 33 tabelle vuote e i relativi privilegi/invarianti nel solo cluster effimero.

I test mirati sono in `backend/tests/`, `tests/database/`, `tests/application/` e `frontend/tests/`. Gli harness PostgreSQL/HTTP/browser usano cluster effimeri e identità sintetiche, mai dati o credenziali live. Il runner applicativo espande l'unica inclusione SQL mediante il loader di baseline prima dell'invio a `psql` via stdin; l'installazione ordinaria usa direttamente `psql -f`.

Per modifiche di dominio verificare invarianti, isolamento tenant, concessioni aziendali dello stesso ruolo, revoche, concorrenza e rollback audit. Per modifiche UI verificare conferme autonome, bozze preservate, sola lettura e percorsi IT/EN pertinenti. Se si modificano soltanto organizzazione dei file SQL e documentazione, non ricreare servizi applicativi né applicare la baseline al database esistente.
