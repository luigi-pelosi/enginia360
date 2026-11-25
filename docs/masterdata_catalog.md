# Enginia360 — Catalogo

Riferimento tecnico unico del Catalogo. Le [regole Foundation §11](foundation.md#11-regole-di-sviluppo) sono normative; i percorsi operativi sono nel [manuale utente](manuale-utente.md#9-configurare-il-catalogo).

## 1. Perimetro e proprietà

Catalogo governa identità tenant-wide di articoli e servizi, classificazioni, unità, conversioni e configurazioni d'utilizzo per azienda. La condivisione non concede accesso: servono i permessi correnti.
Non comprende prezzi/costi, listini, disponibilità, movimenti, valorizzazione, documenti, acquisti/vendite operativi, IVA/contabilità, distinte, lotti/seriali o integrazioni esterne. `track_stock` esprime soltanto una configurazione, non implementa Inventory.

## 2. Modello e invarianti

Il dominio comprende **10 tabelle**, tutte nello schema `masterdata`; `tenant_id` identifica l'organizzazione, senza un parallelo `organization_id`:

| Tabella | Responsabilità |
|---|---|
| `catalog_unit_of_measure` | Unità universali o specifiche per articolo |
| `catalog_category` | Classificazione gerarchica |
| `catalog_item_type` | Natura economica e default operativi |
| `catalog_brand` | Marchio, distinto da produttore/fornitore |
| `catalog_item` | Identità, codice corrente, riferimenti e ciclo di vita |
| `catalog_item_code` | Registro append-only dei codici assegnati |
| `catalog_item_identifier` | Identificativi e unità associata |
| `catalog_item_unit` | Unità alternative e rapporti verso la base articolo |
| `catalog_item_physical_data` | Dati fisici facoltativi 1:1 |
| `catalog_item_company` | Configurazione autonoma per azienda e articolo |

UUID e FK composite proteggono i riferimenti same-tenant; filtri applicativi e autorizzazioni proteggono le letture, senza RLS implicita. Identità e proprietà non cambiano. Versioni ottimistiche e timestamp riguardano le entità revisionate; il registro codici non è un secondo aggregato editabile.
Le mutazioni acquisiscono il lock Catalogo per tenant nella transazione della pipeline esistente. Scritture e audit minimizzato in `foundation.audit_event` committano insieme; un fallimento audit annulla tutto. Nessuna storia parallela `created_by`/`updated_by`.

### Classificazioni

Categorie ad adjacency list, senza auto-riferimenti o cicli anche concorrenti. Cambiare padre sposta il ramo; disattivare non modifica i discendenti. Eliminazione soltanto senza figli o riferimenti, con permesso dedicato; albero HTTP piatto, senza profondità funzionale fissa.
Tipologie con quattro nature: `GOOD` (bene materiale), `INTANGIBLE` (bene immateriale), `SERVICE` (servizio), `CHARGE` (onere accessorio, non sconto). `GOOD` resta singolare. Solo GOOD ammette dati fisici e default di gestione stock.
La natura della tipologia cambia soltanto senza articoli collegati, inclusi sospesi e archiviati; gli altri campi restano modificabili. `canChangeKind` è metadato calcolato, non input. Eliminazione esplicita senza cascata, previo controllo dei collegamenti e nuova verifica atomica al comando.
Codice facoltativo per categorie, tipologie e marchi, obbligatorio per le unità; unicità case-insensitive nell'ambito previsto quando valorizzato. Marchi disattivabili, senza DELETE esposto.

### Articolo e ciclo di vita

Nome, tipologia, categoria e unità base sono obbligatori in creazione e modifica in ogni stato; marchio e descrizione facoltativi. Omissione in PUT conserva, null è ammesso solo dove previsto. Dati storici incompleti restano leggibili e vanno completati al prossimo Salva generale, senza backfill inventati.
Tre stati: `ACTIVE` predefinito in creazione, `SUSPENDED`, `ARCHIVED`. Creazione solo ACTIVE/SUSPENDED; ACTIVE↔SUSPENDED, da entrambi ad ARCHIVED, senza ritorno. L'archivio è readonly e sostituisce l'eliminazione del master.
La natura deriva dalla tipologia e non cambia sostituendo la tipologia dell'articolo. Nuovi riferimenti richiedono voci attive; riferimenti poi disattivati possono essere conservati. L'attivazione rivalida riferimenti e figli applicabili.
`activated_at` registra una sola volta la prima attivazione, anche nel POST ACTIVE. Da allora codice e unità base sono immutabili. Prima dell'attivazione, cambiare base richiede assenza di alternative, identificativi e dati fisici; le configurazioni aziendali non possono essere invalidate.
Codice articolo unico case-insensitive nel tenant fra tutte le nature, anche per archiviati e codici precedenti. Nuovo codice manuale o modifica: esclusivamente `[A-Za-z0-9]{1,40}`, senza trim, normalizzazioni, spazi, accenti o simboli. Modifica solo in modalità MANUAL su articolo SUSPENDED mai attivato. Codici automatici e storici non modificati restano intatti; nessun codice riservato torna disponibile.
La UI conferma soltanto la prima attivazione, non la riattivazione già consolidata; conferma sempre l'archiviazione irreversibile. Annullare conserva la bozza senza scrivere. `update` non concede transizioni: servono activate/deactivate/archive; POST ACTIVE richiede create e activate, POST SUSPENDED solo create, senza ripiego implicito.

### Identificativi e dati fisici

Tipi finiti GTIN/OEM/MPN/BARCODE/LEGACY, un principale per tipo/articolo e nessun duplicato identico sull'articolo. GTIN validato per lunghezza/check digit e confrontato a 14 cifre; GTIN e BARCODE univoci nel tenant, OEM/MPN/LEGACY condivisibili fra articoli. Non si deduce il produttore dal marchio né si certifica la titolarità commerciale del GTIN.
`uom_id:null` indica la base articolo; un valore esplicito deve essere la base o un'alternativa associata. Nuove associazioni attive; rimozioni/disattivazioni non possono lasciare identificativi incoerenti.
Dati fisici solo GOOD, facoltativi e non negativi, riferiti alla base articolo: pesi con unità UNIVERSAL MASS, dimensioni con UNIVERSAL LENGTH, lordo ≥ netto quando entrambi presenti. Rimozione esplicita revisionata.

## 3. Unità e conversioni

Dimensioni finite COUNT/MASS/LENGTH/VOLUME/TIME/AREA. `conversion_scope` immutabile: UNIVERSAL con fattore globale positivo; ITEM senza fattore globale e senza ruolo di base di dimensione (es. CF/PLT). Dimensione, fattore e ruolo di base immutabili dalla creazione.
Per dimensione/tenant al massimo una base UNIVERSAL, fattore 1; quando esistono unità universali attive occorre la base attiva, verificata anche al commit. Non disattivare la base con dipendenti attivi. Le unità non si eliminano.
La base articolo deve essere UNIVERSAL, ma può essere G anche se la base della dimensione è KG. Rapporto implicito 1:1, non duplicato nelle alternative. Alternative uniche per articolo: UNIVERSAL con stessa dimensione e rapporto coerente con i fattori; ITEM con numeratore/denominatore specifici dell'articolo.
Quantità e fattori trasportati come stringhe decimali invarianti, PostgreSQL `numeric`, massimo 12 decimali e magnitudine assoluta < `10^16`; fattori/numeratori/denominatori positivi. Precisione destinazione 0–12. Overflow o scala non ammessa sono rifiutati, non corretti.
Conversione universale `q × fattore origine ÷ fattore destinazione`, soltanto fra UNIVERSAL attive della stessa dimensione/tenant. Conversione articolo soltanto fra base e alternative attive associate, comprese ITEM.
Calcolo razionale `BigInteger`, senza float o arrotondamenti intermedi; unico arrotondamento finale a metà lontano da zero. Risposta `{quantity,unroundedQuantity,rounded,decimalPlaces}`: anteprima periodica troncata a 40 decimali, risultato e flag dalla frazione esatta. Nessuna modifica all'input o registrazione di stock.

## 4. Numerazione condivisa

`backend/Modules/Numbering/NumberingKernel.cs` usa `foundation.numbering_series` e `foundation.numbering_counter`, mai duplicati in `masterdata`. Cinque discriminanti: BUSINESS_PARTNER e CATALOG_GOOD/INTANGIBLE/SERVICE/CHARGE; scope TENANT, `company_id IS NULL`, reset NEVER, discriminante immutabile.
Quattro serie Catalogo indipendenti, separate da BP: default virtuali AUTO, prefissi ART-/IMM-/SRV-/ONR-, padding 6, prossimo numero 1. GET non materializza; Salva esplicito o allocazione riuscita crea la configurazione. Configurazioni esistenti non vengono sovrascritte.
Dopo l'uso modalità/formato bloccati, contatore non riavvolgibile. Versioni/progressivi rispettano i limiti esatti del trasporto. Numerazione, codice riservato, articolo, figli, aziende richieste e audit sono atomici; nessun endpoint pubblico alloca un numero Catalogo senza articolo. L'unicità trasversale è garantita anche dal registro codici, non dalle sole serie.

## 5. Utilizzo per azienda

Una sola configurazione `(tenant_id,company_id,item_id)`, con versione indipendente dal master. Nessuna associazione automatica creando un articolo o un'azienda. All'associazione i default vendibile/acquistabile/stock della tipologia sono copiati una volta, poi restano indipendenti; solo GOOD consente `track_stock`.
Campi editabili: `is_enabled`, `is_sellable`, `is_purchasable`, `track_stock`, `default_sales_uom_id`, `default_purchase_uom_id`. Unità default facoltative: null usa la base corrente; scelta esplicita fra base o alternative attive dell'articolo, con unità attiva. Compatibilità dimensionale da sola insufficiente; nessuna conversione creata automaticamente.
Rimozione/disattivazione di alternative usate e cambio base non possono invalidare configurazioni esistenti. Disabilitare preserva identità, flag e unità; nessun DELETE. SUSPENDED blocca l'uso effettivo senza disabilitare le associazioni.
Archiviare disabilita atomicamente tutte le associazioni ancora abilitate, con una revisione/audit per ciascuna modificata, senza permessi aziendali aggiuntivi; quelle già disabilitate restano invariate. Un archivio non si riabilita; su azienda disabilitata è consentita soltanto la disabilitazione delle associazioni.
`canSell`/`canPurchase`/`canTrackStock` sono proiezioni: articolo ACTIVE, azienda e associazione abilitate, relativo flag; stock inoltre GOOD. Il gate verifica il tenant attivo. Non sono input o colonne operative Inventory.
Bulk: massimo 100 itemIds, 100 companyIds e 500 coppie; tutti i target validi/autorizzati o rollback totale. Crea solo associazioni mancanti; esistenti, anche disabilitate, intatte. Risposta `{created,unchanged,items}`, ordine stabile e protezione dai duplicati concorrenti.

## 6. API e autorizzazioni

Endpoint dedicati, esclusi dalla CRUD generica. Envelope camelCase, record snake_case, decimali stringa; tenant dalla sessione, `tenantId` per il contesto esplicito del globale. Tenant attivo, Origin/CSRF sulle mutazioni comprese le conversioni, nessun grant implicito.
Liste `{items,total,page,pageSize}`, pagina predefinita 25/massimo 100 e ricerca massimo 200 caratteri. Filtri applicati prima di conteggio/paginazione, senza duplicare articoli tramite identificativi.

| Famiglia (prefisso `/api`) | Contratto e autorità |
|---|---|
| `GET/POST /catalog/{units,categories,types,brands}`; `GET/PUT .../{id}` | POST `{values}`, PUT `{values,expectedVersion}`; permesso read/create/update della risorsa |
| `GET /catalog/categories/tree`; `DELETE /catalog/categories/{id}` | Albero piatto, `parentId` facoltativo; delete con versione query e permesso dedicato |
| `GET /catalog/types/{id}/deletion-check`; `DELETE .../{id}` | `{canDelete}`, poi versione query; `catalog-types.delete`, senza obbligo di leggere articoli |
| `POST /catalog/units/{id}/convert` | `{targetUnitId,quantity}`; `catalog-units.read` |
| `GET/PUT /catalog/numbering?kind=...` | Una delle quattro nature; `{mode,prefix,padding,nextNumber,version}` e versione attesa in modifica; read/update dedicati |
| `GET/POST /catalog/items`; `GET/PUT .../{id}` | Master e aggregato; `catalog-items.read/create/update`, più azione richiesta dallo stato |
| `PUT /catalog/items/{id}/status` | `{status,expectedVersion}`; activate/deactivate/archive secondo transizione |
| `POST /catalog/items/{id}/{identifiers,units}`; `PUT/DELETE .../{childId}` | `{values,expectedVersion}`, DELETE versione query; update articolo, risposta aggregato 200 |
| `PUT /catalog/items/{id}/physical-data`; `POST .../convert` | `{values:object\|null,expectedVersion}` con update; `{sourceUnitId,targetUnitId,quantity}` con read |
| `GET /catalog/item-options` | Proiezioni minime riferimenti e modalità delle quattro serie sotto autorità articolo, non amministrazione dei cataloghi |
| `GET /catalog/item-companies/options`; `GET .../item-options/{itemId}` | Aziende/azioni autorizzate e contesto minimo articolo; nessun CRUD aziende implicito |
| `GET /catalog/items/{itemId}/companies` | Configurazioni visibili con read master e read delle precise aziende |
| `GET /catalog/item-companies`; `GET /companies/{companyId}/catalog/items[/{itemId}]` | Sole associazioni nell'ambito leggibile, senza richiedere consultazione completa del master |
| `PUT/PATCH /companies/{companyId}/catalog/items/{itemId}` | `{values,expectedVersion}`; PUT crea con versione 0 o aggiorna, PATCH solo esistente; create/update aziendale |
| `POST /catalog/item-companies/bulk-enable`; `POST /companies/{companyId}/catalog/items/bulk-enable` | `{itemIds,companyIds}` oppure `{itemIds}`; create su tutte le aziende |

Permessi finiti: units read/create/update; categories e types read/create/update/delete; numbering read/update; items read/create/update/activate/deactivate/archive; brands e item-companies read/create/update, tutti con prefisso `catalog-` appropriato.
L'autorità aziendale richiede operazione e azienda in `foundation.role_company` sullo **stesso ruolo attivo**, diretto o via gruppo attivo: niente prodotto fra permessi di ruoli diversi. Revoche e scope rivalidati sulla sessione aperta. Globale con tenant esplicito; nessuna dipendenza da Pagamenti/BP.
Filtri master: search/status/itemTypeId, kind compatibile API. Liste aziendali: companyId/search/enabled/kind e canSell/canPurchase/canTrackStock con ALL/YES/NO; valori o duplicati non ammessi rifiutati. `kind` non è proposto nella UI aziendale.

## 7. Transazioni, versioni e recupero

Come da §11.14, POST articolo `{values,status?,identifiers?,units?,physicalData?,companies?}` registra insieme bozza, figli e massimo 100 aziende distinte `{company_id,values}`. Qualsiasi errore annulla anche progressivo, riserva codici e audit. Omettere companies non crea associazioni.
PUT generale `{values,expectedVersion,status?,physicalData?}` non accetta companies né collezioni figli; omissione conserva, `physicalData:null` rimuove. Salva generale UI registra anche stato/dati fisici in una transazione. Articolo/marchio creati: 201; mutazioni figli: aggregato aggiornato 200.
Su articolo esistente, confermare identificativo/unità persiste subito solo la riga e incrementa la versione articolo; non salva la bozza generale. Si adotta la nuova versione solo dopo la mutazione che ha verificato quella precedente, conservando bozza e baseline originali. Una rilettura non autorizza a sostituire alla cieca il token obsoleto.
Configurazioni aziendali già persistite sono autonome: non cambiano versione articolo e non salvano la sua bozza. PUT aziendale senza variazioni conserva la revisione ma controlla comunque la versione. Conflitti 409 `stale_version`, senza sovrascrittura.
`sessionStorage` recupera nella stessa scheda filtri/tab/editor, per utente/tenant/contesto e con nuova verifica di permessi/record. Non garantisce recupero se storage o accesso mancano. Menu resetta la vista, non il presidio di una mutazione dall'esito incerto.
Timeout/risposta persa non dimostrano rollback: nessun replay automatico. Occorrono lettura autorevole e riconoscimento esplicito prima di sbloccare; non è idempotenza server-side né protezione fra schede.

## 8. Interfaccia

**Anagrafiche → Catalogo → Articoli e servizi** riunisce **Identità** e **Per azienda**. Il lettore solo aziendale non carica il master; `catalog-item-companies` resta alias URL. Altri accessi: Catalogo → Categorie/Marchi; Impostazioni → Anagrafiche → Catalogo → Tipologie articolo/Numerazione; Impostazioni → Sistema → Unità di misura.
Identità parte da Attivi; Per azienda da Abilitate, con Tutte/Disabilitate selezionabili. Tab e filtri espliciti persistono al refresh; menu ripristina i default autorizzati. Scheda articolo: Generale, Identificativi, Unità, Dati fisici solo GOOD, Aziende.
Sette colonne articolo: Codice, Nome, Tipologia, Categoria, Unità di misura base, Marchio, Stato; azioni master separate. Bulk in dialog largo con le stesse sette colonne, senza azioni di riga, più checkbox; tabella aziende con Azienda e Indirizzo legale.
Checkbox intestazione solo pagina corrente, stato parziale e selezioni conservate fra pagine/ricerche. Aziende: 25 per pagina sui metadati autorizzati; articoli: ricerca/paginazione server a 25. Indirizzo della prima sede LEGAL attiva per created_at/id, nessun ripiego operativo e cella vuota se assente. Nessun troncamento implicito dei limiti bulk.
Cerca sempre per primo; filtri compatti, accordion quando lo spazio manca, filtri nascosti ancora applicati. Testi a sinistra, numeri a destra/intestazioni centrate, stati/icone/azioni centrati tramite tipo semantico. Badge di stato, select ricercabili, azioni accessibili, dialog condivisi trascinabili/ridimensionabili, IT/EN; azioni vista a destra dei tab e disposizione adattiva su mobile.

## 9. Installazione e manutenzione

Ingresso fresh install: [`database/foundation.sql`](../database/foundation.sql); definizioni Catalogo finali in un solo [`database/masterdata_catalog.sql`](../database/masterdata_catalog.sql). Numbering condiviso appartiene a foundation; Business Partner e Pagamenti conservano frammenti separati. La tabella delle unità resta `masterdata.catalog_unit_of_measure` anche se la definizione è collocata fra i prerequisiti condivisi.
La composizione fresh install non riproduce una sequenza di migrazioni Catalogo. Parti incrementali obsolete non sono il percorso attivo; nessuna applicazione di baseline/DDL su dati conservati, nessun migration runner all'avvio. Installazione solo su database nuovo, con psql e struttura relativa preservata; loader stdin limitato agli include canonici.
Seed tenant idempotente: 11 unità standard (PZ, KG, G, M, CM, L, ML, MIN, H, M2, CM2) e tipologie Merce GOOD/Servizio SERVICE; nessuna categoria, marchio, articolo, confezione ITEM, associazione o grant. Non sovrascrive personalizzazioni né riattiva basi. Baseline senza tenant: nessun dato Catalogo operativo o serie materializzata.
Verifiche mirate: test source/runtime Catalogo in `tests/database/`, contratti e self-test `backend/Verification/Catalog/`, test frontend `frontend/tests/catalog-*.test.ts`, runner HTTP/browser `tests/application/run_catalog*_proof.py`. SQL e mutazioni di prova solo in fixture isolate, mai sul principale; trasporto HTTPS logico non prova TLS. Risultati, immagini e stato di rilascio richiedono evidenze proprie, non sono dedotti da questo documento.
