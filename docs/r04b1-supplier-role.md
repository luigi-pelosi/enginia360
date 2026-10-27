# R04.b.1 — Ruolo fornitore nell’anagrafica condivisa e ID fornitore Giobby in estensione societaria

Figlio di R04 #44 (Refs #45). D88 (27 ottobre 2026): fornitore = **ruolo** dell’anagrafica condivisa tenant-wide (D26/D65); ID fornitore Giobby in una **estensione societaria**, mai nell’anagrafica condivisa; richiesta d’acquisto creata a mano da una riga Part (R04.b.2); nessun approvatore separato (una azione con permesso dedicato, R04.b.2). Giobby resta l’unica autorità per stock e documenti d’acquisto (D82). Questo incremento consegna **solo** i due prerequisiti dati: nessuna richiesta d’acquisto, nessun connettore d’acquisto Giobby, nessun traffico ERP, nessuna UI.

## Contratto

Migrazione append-only `0027_supplier_role.sql` (0001–0026 byte-identiche, checksum manifest verificati). Tutto in schema `counterparties`.

**Ruolo (anagrafica condivisa).** Colonna `counterparties.counterparties."IsSupplier" boolean NOT NULL DEFAULT false`. L’applicazione ha solo SELECT: nessun UPDATE sulla colonna.

- `PUT /api/v1/counterparties/{id}/supplier-role` — corpo `{legalEntityId, isSupplier, commandId, authorityVersion, expectedRevision}`; CSRF come ogni PUT di sessione. Richiede le **stesse azioni esatte** della modifica comune già esistente: `counterparties.read` sulla società esatta **e** `counterparties.common.edit` tenant-wide. Nessun permesso nuovo né delegabile.
- Funzione SQL `counterparties.set_supplier_role` (SECURITY DEFINER, stessa lock di autorità `master-authority:<tenant>`): ricontrolla appartenenza e grant, **autorità unica R02.b** (profilo locale e versione esatta: `missing` / `stale_authority` / `external` → 409 senza scrivere), revisione ottimistica **condivisa** con la modifica comune (`expectedRevision`), idempotenza per `commandId` (replay identico → `replayed`, payload diverso → `conflict`), e storia immutabile `common_edit_history` con snapshot Before/After che includono `isSupplier`. La modifica comune esistente non azzera il ruolo e non cambia firma.
- `GET /api/v1/counterparties/{id}/edit-state` ora riporta anche `counterparty.isSupplier` (stessa serializzazione). Le liste/ricerche e `GET /{id}` restano invariate: nessun ID ERP e nessun ruolo nei contratti di selezione.

**Estensione societaria (ID Giobby).** Tabella `counterparties.giobby_vendor_identity_history`, per società (RLS forzata su `TenantId` **e** `LegalEntityId`), append-only (UPDATE/DELETE/TRUNCATE rifiutati anche per il proprietario DB), revisioni crescenti per (società, controparte). Campi dall’evidenza R05.a.4/a.5 (ID opaco del fornitore + nome esatto per la ricerca `GET /vendors?name=`), **nessun altro**: `VendorId` (1–64 caratteri ASCII stampabili senza spazi, opaco), `VendorName` (1–200, senza controlli, troncato dagli spazi), più attore, riferimento di verifica e istante.

- Scrittura **solo** dal percorso proprietario/operatore fidato: `python3 scripts/owner-supplier-vendor-identity.py <input.json>` (come `owner-master-authority.py`/`owner-stock-profile.py`: `PGSSLMODE=verify-full`, certificato radice, connessione del proprietario DB non privilegiato, attore con binding e appartenenza già fidati, readback esatto). Nessun EXECUTE né accesso diretto alla tabella per il ruolo applicativo, nessun endpoint, nessuna delega D77. Il riferimento di verifica registra un controllo esterno; **non è** verifica d’identità.
- Funzione `counterparties.establish_giobby_vendor_identity`: controparte esistente nel tenant **e con ruolo fornitore** (`not_supplier` altrimenti), società del tenant, revisione attesa esatta, un ID fornitore identifica **una** controparte per società (ultima revisione), replay identico idempotente, input malformato `invalid`.
- `GET /api/v1/counterparties/{id}/supplier-erp-identity?legalEntityId=` — `counterparties.read` sulla società esatta; risposta `{state:ready,isSupplier,vendor:{vendorId,vendorName,revision,effectiveFrom}|null}`; l’estensione è servita **solo mentre** la controparte ha il ruolo (togliere il ruolo non cancella né riscrive la storia). Un’altra società o un altro tenant non vede la mappatura.

Input proprietario (chiuso): `commandId, tenantId, legalEntityId, counterpartyId, actorMembershipId, verificationReference` (UUID canonici non nulli), `expectedRevision` (intero ≥ 0), `vendorId`, `vendorName`.

## Interpretazioni e punto aperto (gate)

Lettura dell’agente, correggibile dall’owner: D88 non dice se il ruolo/ID siano modificabili localmente o proiettati dall’ERP quando la direzione D76 è `ExternalToEnginia360`. Implementato solo il non ambiguo: il ruolo segue **la stessa regola di autorità R02.b** della modifica comune (locale = modifica ammessa; esterna/mancante = rifiuto esplicito, nessun fallback locale né cambio automatico di autorità); la mappatura è impostata dal percorso proprietario offline indipendentemente dalla direzione (non è autorità sull’anagrafica fornitori). **Nessuna proiezione D76 è implementata**: con profilo esterno il ruolo non può oggi essere impostato localmente, quindi la mappatura (che richiede il ruolo) non è impostabile finché l’owner non decide la proiezione. Ciò non è inventato né aggirato.

## Limiti

- Nessuna UI: la superficie R02.b esistente non è stata estesa; ruolo e ID sono impostabili/leggibili solo via API/percorso proprietario. Nessuna richiesta d’acquisto, azione dedicata, connettore Giobby d’acquisto, lookup/ricevimento/overlay, token, traffico live/sandbox, dati reali, deployment.
- Compatibilità live con Giobby non provata (nessun ID reale usato; valori sintetici). Un ID fornitore presente nell’ERP ma non mappato non viene dedotto per nome: l’abbinamento resta un atto esplicito del proprietario.
- La storia delle modifiche comuni precedenti non contiene `isSupplier` nei propri snapshot (`Before/After` di `edit_common` invariati per compatibilità di replay).
- R06: la nuova tabella è la voce 67 dell’inventario, eleggibilità UNDECIDED, nessuna approvazione di migrazione; `IsSupplier` è un ALTER non inventariato come CREATE.

## Prove (sintetiche, isolate)

`scripts/test-r04b1-supplier.py` (9 test: ingresso proprietario offline + 6 SQL su PostgreSQL effimero, eseguiti da `run-r00a-tests.py`), `RuntimeMigrationPoolTests.Supplier_role_and_company_vendor_identity_do_not_leak_across_reused_real_pool` (pool 1 e 4), `MasterAuthorityEnforcementTests` (401 senza sessione), `ui01b-acceptance.cjs` (Chromium/OIDC/nginx/API/PostgreSQL con pool 4 e 1: 403 per identità senza azione e per tenant estraneo, CSRF mancante, stale/esterno, replay, readback edit-state, ID Giobby impostato dal tool proprietario su TLS e assente da lista/dettaglio/edit-state). Impatto CI: `scripts/test-r04b1-impact.py`. Il dettaglio dei comandi, esiti e job CI è nella PR dopo esecuzione reale.

## Rollback

Un revert rivisto della PR rimuove endpoint, funzioni applicative e tool; lo schema applicato resta (migrazione append-only, nessun DROP). Una versione precedente dell’applicazione ignora la colonna e la tabella e non può scriverle (nessun privilegio applicativo). Non cancellare né riscrivere la storia: correggere con una nuova revisione o con una migrazione in avanti rivista. Bootstrap, Tailscale 443 → localhost:9119, volumi e backup protetti non toccati.

## Requisiti rimanenti per R04.b.2

1. Azione/permesso dedicato unico (D88c) per creare la richiesta, non autoassegnabile né subdelegabile oltre D77, con CSRF e scope società/magazzino esatti.
2. Richiesta d’acquisto creata a mano dalla riga Part (D88a), come intento/outbox verso l’ERP, con idempotenza e storia immutabile, mai scrittore locale di acquisto o stock (D82); la quantità richiesta (es. 2 su fabbisogno 3, disponibile 1) è scelta dall’operatore.
3. Connettore d’acquisto Giobby (ordine fornitore) basato sulla mappatura `VendorId`/`VendorName` di questo incremento, con lookup per nome esatto prima di ogni riuso e hold su ambiguità (R05.a.4/a.5), e riconciliazione del residuo non autorevole (D86).
4. Decisione owner su proiezione D76 del ruolo/ID quando l’ERP possiede l’anagrafica fornitori.
5. Evidenza sandbox e idempotenza lato provider prima di qualunque effetto reale.
