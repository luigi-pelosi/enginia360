# MVP08 / #147 — sviluppo parziale e raggruppamento quantitativo

Stato corrente: MVP08 COMPLETATO via PR172 / main `b00fdbafd3f91f6526caf18e75b79476ab02660f`; [stato e prove parent](mvp-delivery-plan.md). MVP09/#148 è il punto corrente, non ancora verificato.

## Checkpoint storico source-only, precedente alla validazione di PR172

Il testo seguente conserva la cronologia della preparazione; UNVERIFIED/UNEXECUTED e i futuri #148/#149 descrivono quel momento, non lo stato corrente.

Stato: CONTRATTO FINITO, sorgenti dell'intero punto COMPLETI / UNVERIFIED; [mappa implementazione e prove preparate](mvp08-implementation.md). READY_FOR_FINAL_VALIDATION soltanto come completezza sorgente, non consegna verificata. Intero #147 (SQL/API/UI/test/runner/CI) prima di qualsiasi esecuzione di validazione. Nessun nuovo ambiente, deployment o scrittura remota. #148 e #149 restano futuri.

## Decisioni del proprietario (prima del codice dipendente)

<!-- d100-current:start -->
D100: «La quantità viene prenotata alla conferma della bozza». La destinazione Draft salva allocazioni proposte, senza impegnare capacità sorgente né stock. L'impegno della capacità documentale avviene soltanto atomicamente con la conferma della destinazione, rileggendo tutti i residui riga/passaggio. Bozze concorrenti possono contendere: una conferma perdente riceve 409, resta Draft, senza riduzione silenziosa o effetto parziale. Non è una prenotazione fisica. Ogni precedente proposta di prenotazione al salvataggio è SUPERATA/non scelta.
<!-- d100-current:end -->

<!-- d101-current:start -->
D101: «Usare soltanto sorgenti confermate, anche di tipi diversi se tutti abilitati verso la destinazione». Ogni sorgente deve essere Confirmed immutabile e ogni percorso societario sorgente→destinazione deve essere correntemente abilitato. Tipi sorgente differenti sono ammessi, mai tenant/società differenti. D14/D17 restano: customizing solo societario, stessa sede per default, cross-site della stessa società solo esplicitamente abilitato per ciascun percorso coinvolto.
<!-- d101-current:end -->

D100 e D101 sono i prossimi ID liberi rilevati nel registro; non riaprono D99.

## Traccia di ownership osservata (lettura sorgente, non prove eseguite)

- `document_types.definitions/versions` e `document_types.for_document/document_choices` possiedono tipi e versioni; `document_types.command/read` sono gli ingressi pubblici attuali. Estendere lo stesso modulo per i percorsi supportati, non introdurre un motore universale.
- `documents.headers/lines/versions` possiedono UUID canonici e snapshot. `documents.command` possiede l'unica transazione save/confirm, stock `balances/ledger`, audit/receipt e `snapshot_fence`; `documents.read` è il selettore pubblico. Estendere questi ingressi nello stesso owning context.
- `catalog.items` possiede ID/Version e Kind Part/Service; `catalog.document_item` traduce Part→Article al boundary. Uno sviluppo usa gli snapshot delle righe confermate, non una nuova identità e non riscrive la provenienza dopo edit del master.
- `DocumentEndpoints` imposta soltanto la tupla verificata issuer/subject/internal identity in transazione, prima di SQL. `organization_access.current_membership_access`, lock 777036, ruolo/permission scope corrente e witness MVCC precedono query, effetto e replay. Nessun adapter pooled annidato.
- D97 attuale: 14 azioni pre-documenti + 7 documentali, scope tenant condiviso (7), company (7), site (3), warehouse (4). Le due nuove azioni finite sono `documents.develop` SITE e `document-types.paths.manage` COMPANY. Richiedono anche i read esistenti pertinenti; nessun grant implicito dal ruolo amministrativo o dalla sola configurazione.

## Percorsi e identità del passaggio

Un passaggio è la tupla stabile (tenant, società, sourceTypeId, destinationTypeId), non il command UUID o la revisione di regola. Un'unica identità persistente per tupla; disabilitare e riabilitare appende versioni, non cancella/ricrea la capacità. Non esiste hard-delete pubblico; un UUID di comando nuovo non cambia il passaggio. Versioni correnti con enabled e allowCrossSite boolean espliciti, default same-site; nessun codice, formula, conversione o catena universale. Revisioni attese obsolete → 409 config_changed e rilettura esplicita, non ricalcolo silenzioso. Creazione diretta MVP07 resta ammessa indipendentemente dall'esistenza di percorsi.

## Compatibilità finita e quantità

Una destinazione ha una società, una sede e un tipo. Ogni origine è un documento Confirmed della stessa società/tenant; ogni tipo ha il proprio percorso abilitato verso il tipo destinazione. Il destinatario sceglie magazzini operativi autorizzati della sede destinazione secondo l'effetto corrente (None/Service senza magazzino, Load/Unload uno, Transfer due distinti). Non copiare i magazzini storici da sorgenti cross-site.

Una riga può raccogliere molte origini se coincidono item canonico, kind, versione e label snapshot, e un unico contesto operativo destinazione. Snapshot differenti restano righe differenti. Ogni allocazione conserva sourceDocumentId/sourceLineId, sourceQuantity immutabile, site/warehouse storici, sourceType/version applicati e path/version applicati alla conferma. Somma esatta q6 delle origini = quantità della riga; nessun float JS, positivo, numeric(24,6), massimo 999999999999999999.999999 anche per aggregati. Limiti tecnici: 200 righe, 200 allocazioni complessive, 200 origini per riga, body 262144 byte, profondità finita. Duplicate sourceLine/passaggio nella stessa riga vietate; sorgente condivisa tra righe somma sotto lo stesso cap. Nessun prezzo, valuta, unità o conversione inventata.

Capacità/residuo = quantità immutabile sourceLine meno somma delle allocazioni confermate per quello specifico passaggio. Le bozze sono intenzioni non riservate e sono mostrate separatamente. Un'altra destinazione di tipo diverso usa un altro passaggio: lo stesso quantitativo può attraversare più stadi. Un documento sviluppato e poi confermato può essere sorgente; i link immediati restano navigabili ricorsivamente con autorizzazione corrente a ogni salto, senza inventare quote transitive dopo una fusione.

## Transazione e correzioni finite

Conferma: tupla/membership/ruoli correnti e MVCC → diritti destinazione e lettura+develop di ogni sorgente → header → percorsi/origini in ordine deterministico → residui correnti aggregati → chiavi stock ordinate → allocazioni accettate + effetto MVP07 corrente + stato/versioni/audit/receipt in un'unica transazione. Una violazione o errore audit/deferred commit annulla tutto. None impegna capacità, Service non stock; replay autorizzato non duplica; UUID nuovo non riconferma un Confirmed. I fatti accettati conservano regole e quantità storiche ma le prossime operazioni usano regole correnti, non congelate per tutta la vita Draft.

Draft: aggiungere/rimuovere/correggere quantità e origini autorizzate, senza impegno capacità. Salvataggio ordinario non può spogliare una riga già backed o mutarne quantità arbitrariamente: richiede il comando di sviluppo con piano completo coerente. Rimozione esplicita via editor sviluppo è consentita, non conversione implicita a riga libera. Confermati immutabili: nessun cancel/reopen/reset, nessun rifornimento automatico di residuo o stock undo. Il principio D5–D7 di compensazione guidata/collegata resta requisito futuro; questa consegna espone impatto e link ma NON consegna un lifecycle di compensazione dei Confirmed, assente anche in MVP07. La politica esatta di riapertura residui rimane non deliberata e non viene simulata. La correzione parziale consegnata riguarda soltanto il piano Draft. Nessuna waiver tacita di un reset accettato: nessun reset è stato accettato.

## Matrice finale da preparare / tutte le esecuzioni UNEXECUTED

SQL/API: bozze contendenti entrambe salvabili, vincitore e 409 all-or-none; residuo parziale stesso passaggio e indipendente; revisione/disable/reenable senza reset; fusione multi-origin e multi-hop; due tipi verso uno e un percorso vietato annulla tutto; stesso-site default e cross-site esplicito senza copia WH; permessi revocati su ogni origine, RLS tenant/company, pool1/pool4, entrambi ordini fisici e RR stale fail-closed; audit insert/deferred rollback su quota/stock/header; retry exact e nuovo UUID; q6/overflow/Unicode/UUID/duplicati/chunked body; regressioni D99/MVP07 e consumer D97.

UI/SSR/headless Chromium: ricerca nativa e dettaglio/origini/residui noJS private-no-store; comandi disabled prima idratazione; scelta contesto destinazione; correzione piano persistito; lost ACK→CSRF rifiutata→replay con GET fallita conserva route/UUID/bytes nella pagina aperta; revoca corrente; keyboard e 26 righe ai viewport390/1366/1920. Runner e selettore CI finiti exact/mixed/unknown con consumer diretti e full_architecture=false, immagini/deadline originali preservate. Nessun risultato di queste prove è ancora dichiarato.
