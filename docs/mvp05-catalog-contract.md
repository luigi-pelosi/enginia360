# MVP05 / #144 — catalogo autonomo articoli e servizi

## Stato corrente — consegna verificata dal coordinatore

MVP-05/#144 COMPLETATO: PR #169, merge `43a4ff836d67bf1b4f01eb27ccc318171ee45f8d`, candidate `b6a337d35826d23de2465f79e99bd4f6105da458`, tree equivalente `2d5c06ae8c83e744a88e20abdcc0c34f0066ad81`. Il coordinatore ha riletto PR CI `41833394752` (5 job/59 step), dispatch `41833450699` (15 job/139 step), nove ZIP con SHA256/head verificati, 20 TRX con 274 test eseguiti/passati e zero skip; issue #144 chiusa e Project Completato. Evidenze `/root/.hermes/evidence/enginia360-mvp05/final/merge-ready.json` e `/root/.hermes/evidence/enginia360-mvp05-parent/merge-readback.json`. Equivalenza tree, non nuova CI main. MVP-06/#145 SORGENTI COMPLETI, NON VERIFICATO; contratto `docs/mvp06-document-types-contract.md`. #146–#149 restano Backlog. Nessun deployment o readiness operativa. I paragrafi seguenti conservano il checkpoint storico del candidato PR169; non descrivono un blocco corrente.

## Checkpoint storico del candidato PR169

Stato: SORGENTI COMPLETI, VALIDAZIONE FINALE IN CORSO. Intero punto #144 implementato prima di qualsiasi validazione; [manifest, criteri, incidenti e comandi finali](mvp05-implementation.md). Il checkpoint UNEXECUTED del writer è storico. Nessuna dichiarazione di consegna o readiness. D96, D97 e baseline MVP-A03; nessun prerequisito Workshop, ERP o fixture seed.

## Contratto minimo fissato prima del codice

Confermato: identità condivise tenant-wide; gestione autonoma di articoli e servizi; prezzi, condizioni, stock e customizing appartengono separatamente alle società. Visibilità non concede modifica. Nessuna gestione documentale o inventariale in #144.

Osservato nel codice Enginia360 a main `03872078b2d77dcf6754700729e41fcf5567d051` (non nuove politiche di dominio):
- `0006_catalog_lines.sql`, `CatalogModule.cs`, `Catalog.Contracts/Contracts.cs`: unica identità `catalog.items`, UUID, TenantId, RegisteredCompanyId, Kind `Part|Service`, Label 1–100 scalari, Version positivo. RegisteredCompanyId è provenienza storica, non scope di visibilità.
- `IWorkshopCatalog` e `CommercialEndpoints`: selezione della stessa identità/versione; le righe congelano CatalogItemId/CatalogVersion/CatalogLabel/Kind. Prezzi/quantità/IVA sono dati delle righe, non del catalogo.
- `WorkshopReservationLines`, Inventory: le quantità dipendono da CatalogItemId della riga; nessun nuovo writer di stock.
- `PurchasePriceEndpoints`, migrazioni 0029/0030: prezzi acquisto per società/fornitore/item e revisioni congelate; non una seconda identità catalogo. Nessuna riscrittura prezzi, repricing o prezzo zero implicito.
- `0017_master_authority_profile.sql`, `owner-master-authority.py`: autorità esplicita **counterparties**, non prova di autorità catalogo. Il suo setup non autorizza scritture catalogo.

Default tecnici nuovi, delimitati e correggibili: API kind tipizzato inglese `Article|Service`; conversione unica esplicita `Article <-> Part`, `Service <-> Service` verso lo storage/porta storica, senza rinominare o duplicare le identità. Solo etichetta obbligatoria (1–100 scalari, non vuota, senza controlli); nessun codice univoco, unità, IVA, costo, marca, variante, veicolo, tassonomia, lifecycle o cancellazione. Kind scelto alla creazione e conservato nelle modifiche; riclassificare identità già referenziate non è un workflow approvato. Etichette duplicate ammesse senza auto-match/merge. UUID generato server, non digitato dall'operatore; command UUID generato browser.

## API / input / letture

`GET /api/v1/catalog/management`: query finite `search` (<=200 scalari), `after`/`id` UUID canonici non vuoti, `kind=Article|Service` facoltativo. Ricerca case-insensitive letterale; ordine UUID, 20 elementi + sentinella, dettaglio riletto indipendente dal filtro. Elenco/ricerca/selezione/dettaglio SSR anche senza JavaScript.

`POST /api/v1/catalog/management/commands`: oggetto JSON esatto, niente chiavi extra/duplicate, numeri interi tipizzati, corpo <=8192 byte:
`{commandId,operation:create|edit,itemId:null|uuid,expectedRevision,authorityVersion,kind:Article|Service,label}`.
Creazione richiede itemId=null e expectedRevision=0; modifica richiede identità esistente/revisione corrente, stesso kind. `revision` API mappa a Version storico, senza stream concorrente. Snapshot immutabile `{id,kind,label,revision}`. Risultati ready/applied/replayed, invalid, forbidden, not_found, conflict, missing/external/stale_authority, store_unavailable. Audit privato atomico prima/dopo/request esatto, membership e binding hash (non issuer/subject raw), authorityVersion. Replay restituisce snapshot storico, poi UI rilegge autoritativamente lo stato corrente.

## Autorità e sicurezza

Riutilizzare il percorso owner offline TLS verificato/nonprivileged DB owner con domain esplicito `catalog`, mantenendo il percorso counterparties invariato. La decisione catalogo blocca binding/membership esistenti e enabled con 777036 e witness RR fino al commit; un riferimento di verifica non è autenticazione. Il CLI richiede esito applied/replayed **e** readback esatto: una vecchia riga di audit non può trasformare un rifiuto corrente in successo. Storia catalogo separata tenant-wide, una sola source/profile/version e insieme esplicito di società; nessun default automatico al locale, nessun fallback se setup manca/esterno/stale. RegisteredCompanyId di nuove identità è la prima società della decisione esplicita, solo provenienza. Nessun ingest/backfill/authority switch silenzioso o nuovi permessi di setup. Letture indipendenti dal setup. Identità, prezzi/profili e consumer storici non cambiano autorità.

Azioni finite D97 `catalog.shared.read`, `catalog.shared.create`, `catalog.shared.edit`, scope tenant esatto con legalEntityId/siteId/warehouseId tutti null (non wildcard). Read richiesto anche per create/edit. Nessun grant implicito SUPERADMIN, gestore utenti o organizzazione. Consumer SQL controlla tuple issuer/subject/internalIdentity corrente, membership enabled, assegnazioni/ruoli/permessi attuali nella stessa transazione 777036 del dato e audit, prima di ogni replay. La fence RR esistente su tenant_role_objects è mantenuta; nessun nuovo consumer di scope legacy null.

## UI e trasporto

Route `/catalog`, menu italiano, Next SSR dinamico, private/no-store, backend HTTPS fisso e solo Cookie in ingresso. API cookie CSRF e JWT reali esistenti. Utente pending/disabilitato/tenant estraneo rifiutato. Comandi: CSRF browser immediatamente prima del POST; primo 400/409 certo libera il form; esito incerto conserva route/UUID/byte esatti e congela navigazione/form; replay seguito da GET corrente. Recupero limitato alla pagina aperta, non reload/login. Nessun markup fittizio come prova SSR.

## Accettazione finale richiesta — risultati nel ledger, nessun pass implicito

SQL pool1/4: entrambe le tipologie create/edit/read, duplicati, filtro/paginazione, isolamento, input esatto, revisioni/race, replay dopo edit e revoca, rollback audit insert/deferred, immutabilità/ACL/RLS, autorità missing/external/stale e owner setup. API: attivazione catalogo senza Workshop/ERP; tuple reale/JWT/cookie, CSRF, no-store. D97 editor: create/edit action tenant con scope null esatto, ruolo/assignment e revoche applicate alle sessioni aperte, membership/binding disable e RR stale witness. Browser OIDC reale: articoli E servizi, ricerca/selezione/dettaglio, noJS, errore certo e retry byte congelati, authoritative reread failure, screenshots responsive. Compatibilità: stessa identità porta storica, snapshot righe invariati, prezzi per società invariati, nessun stock/quantità creato. CI: selezione finita mixed/unknown negativa, runner isolato pool1/4 e controlli consumer interessati; nessuna esecuzione durante implementazione.

Migrazione append-only 0043; tutte le 42 migrazioni pubblicate e relativi record inventario preservati. Nuove tabelle soltanto authority_evidence e security_evidence, eligibility UNDECIDED. Lockfile/immagini/protected services invariati. Nessun commit/push/PR/issue/Project/deploy da questo writer.
