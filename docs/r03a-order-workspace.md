# R03.a.1 — persisted order workspace (contract)

23 ottobre 2026. Sottoincremento #66 di R03 #43. Nessun go-live, dato reale, acquisto o ambiente persistente. D67 invariato.

## Decisioni del proprietario applicate

- **P1** Ogni riga Service/Part appartiene a **una sola** lavorazione obbligatoria; ogni lavorazione può avere più righe; nessuna riga condivisa. La lavorazione è un raggruppamento operativo, **non** un gruppo fiscale: l'imposta resta calcolata sull'aggregato fiscale (pagante + aliquota) della commessa.
- **P2** Prima della chiusura tecnica: correzioni tracciate; prezzo, sconto e descrizione sempre modificabili; quantità/articolo/lavorazione/rimozione di un ricambio **solo senza impegni logistici attivi**. Storia sempre conservata, nessuna cancellazione fisica.

## Stato corrente R03.a.2

Il limite R03.a.1 sotto è storico. R03.a.2 #68 implementa la fence già concordata, correzione strutturale/rimozione Part senza impegni e prove runtime reali dei consumer diretti: [contratto ed evidenze](r03a2-safe-material-corrections.md). Nessuna chiusura di #43/#5 o autorizzazione R03.b implicita.

## Stato storico R03.a.1 della parte strutturale dei ricambi (limite esplicito)

Questo incremento **non** consegna la modifica strutturale/rimozione dei ricambi, nemmeno prima della prima prenotazione. Il server risponde `409 material_structure_edit_not_supported` e un trigger PostgreSQL impedisce che un ricambio cambi quantità o venga rimosso. Motivo: `Inventory.Reserve` legge la riga Workshop *prima* della propria transazione e prende il lock `inventory:line:{tenant}:{line}`, non il lock ordine Workshop; una lettura "nessuna prenotazione" seguita da modifica è un check-then-act e non una fence. Contratto residuo esatto per l'incremento successivo (R03.a.2):

1. Inventory pubblica una funzione SQL owner-local `inventory.line_has_commitments(tenant, line)` (lettura fresca READ COMMITTED) e Workshop pubblica `workshop.reservation_line(tenant, order, line)` (quantità, catalogo, gruppo, stato correnti). Nessuna delle due moduli interroga le tabelle dell'altro.
2. Il comando strutturale prende, nella **stessa** transazione e connessione Workshop: lock ordine → lock `inventory:line:{tenant}:{line}` (chiave pubblicata nei contratti) → `line_has_commitments` → applica e incrementa versione struttura riga.
3. `Reserve` dopo aver preso il lock di riga rilegge la riga con `workshop.reservation_line` nella propria transazione (stessa connessione, quindi pool=1 senza annidamento) e usa quei valori, non quelli pre-transazione.
4. Ordine dei lock: Workshop-ordine → inventory-riga per le modifiche; comando → inventory-riga per Reserve; nessun ciclo. Prova richiesta: barriera PostgreSQL e pool≥4 con Reserve in volo vs modifica, entrambe le serializzazioni, più pool=1.

## Letture e scritture pubbliche

- `GET /api/v1/workshop/orders/{id}/line-policy` — `workshop.orders.read` (storico senza capability). Versione documento, `currentLinePolicyVersion`, `calculationPolicy`, `multipleWorkingGroups`, `structurePolicyVersion` (versione del contratto workspace, costante del server), limiti. Policy assente: `state=line_policy_missing`, versione `null`, scritture rifiutate (`409 line_policy_missing`), **mai** versione 1 di ripiego.
- `GET /api/v1/workshop/orders/{id}/editor` — un'unica snapshot RepeatableRead: ordine, revisione, policy, lavorazioni, righe/note attive, riepilogo, capacità informative (mai grant fidati).
- `GET /api/v1/workshop/orders?legalEntityId=&siteId=&limit=&after=` — `workshop.orders.read` esatto sul contesto; `limit` 1–50 (default 20); cursore UUID esclusivo; nessuna directory di tenant.
- `POST /api/v1/workshop/orders/{id}/editor/commands` — comandi chiusi `AddGroup | RenameGroup | RemoveEmptyGroup | AddCommercialLine | AddNote | EditCommercialLine | EditNote | RemoveLine`; campi extra → 400. Azioni distinte: `workshop.lines.add`, `workshop.lines.edit`, `workshop.lines.remove`, `workshop.notes.write` (anche rimozione Note), `workshop.groups.write`. `orders.create`/amministratore non le implicano.
- Ricevuta `WorkshopEditReceipt(CommandId, OrderId, AppliedRevision, ResultKind, TargetId)`; 201 alla prima creazione, 200 per modifiche/rimozioni e replay esatto. Il replay (stesso ID e payload numericamente equivalente) restituisce la ricevuta originale anche dopo modifiche successive e dopo la chiusura; membership e scope sono rivalutati prima.

## Revisione, errori, atomicità

`workshop.orders."CommercialRevision"` è persistita, monotona (trigger), incrementata una volta per comando applicato (anche add legacy); sostituisce `COUNT(lines)` in aggiunta, chiusura tecnica e sorgente billing. Backfill = numero storico di righe: i numeri di chiusura già salvati restano validi. Errori 409: `revision_changed`, `line_policy_changed`, `structure_policy_changed`, `line_policy_missing`, `order_technically_closed`, `group_not_empty`, `no_change` (nessuna revisione consumata), `material_structure_edit_not_supported`, `commercial_summary_limit`, `workspace_limit`, `multiple_groups_not_enabled`. 404 `group_not_found`/`line_not_found`. Tutto in una transazione Workshop sotto il lock ordine esistente; rifiuto = nessun effetto parziale.

Limiti tecnici (non massimi commerciali): 1000 righe attive, 100 lavorazioni, 1000 Note, descrizione 500 UTF-16. `commercial_summary_limit`: imponibile, imposta e totale devono stare in `numeric(18,6)` (≤ 999999999999.999999) come richiesta amministrativa e snapshot fattura; verificato su Decimal esatto con confine 819672131147.540983 (ammesso) / …984 (rifiutato).

## Persistenza

Migrazioni append-only `0018_workshop_order_workspace` e `0019_inventory_working_group_provenance`; nessun seed aziendale; RLS forzata su tutte le tabelle nuove; nessun DELETE/TRUNCATE al ruolo web; `workspace_history` ed `editor_commands` solo INSERT con trigger anti UPDATE/DELETE; righe/gruppi/Note con tombstone permanente. La policy ottiene l'attributo `MultipleWorkingGroups` (default `false`: nessun profilo esistente diventa multigruppo). Provenienza: prenotazione → prelievo → installazione → carcassa portano il `WorkingGroupId` reale tramite `ReservationLine.WorkingGroupId` (contratto pubblico Workshop); backfill `WorkingGroupId=OrderId` dove la baseline lo garantiva.

Rollback: nessun rollback automatico dei dati; fermare solo gli ingressi del target effimero e conservare gli originali. Un binario precedente non è compatibile con commesse multi-riga; forward-fix o restore verificato dell'esatto backup. Nessun ambiente con dati reali è autorizzato.

## Non incluso

Nel solo R03.a.1 storico: modifica strutturale/rimozione ricambi (superata dal contratto R03.a.2). Restano esclusi: cambio testata/pagante/veicolo, drag/drop, ripartizioni, appuntamenti/autorizzazioni/tempi/riconsegna, ERP, nuove aliquote. R03.b e R03.c mantengono i propri gate; #43 e #5 restano aperte.
