# R04.c.1 — rilascio parziale esplicito di prenotazione mai prelevata

Stato: implementazione sintetica D80, issue #78, `Refs #44`. Non approva reso fisico del nuovo, rilascio del prelevato, undo installazione/consumo, ricevimento, scadenze/automatismi, azioni post-chiusura o nuove deleghe D77. Nessun ERP, dato reale, deployment o ambiente persistente.

## Contratto

- Route Inventory: `POST/GET /api/v1/inventory/orders/{order}/lines/{line}/reservations/{reservation}/releases`; azione esatta `inventory.reservations.release` (tupla società/sede/magazzino), distinta da reserve/pick e **non** aggiunta alla allowlist D77 né concessa dall'applicazione.
- Prenotazione originale immutata. Compensazione append-only in `inventory.reservation_releases` (migrazione append-only 0023; 0001–0022 invariate): UUID stabile, q6 positiva entro residuo rilasciabile, riferimenti reservation/order/line/gruppo/magazzino/catalogo, attore e data server. Nessuna DELETE/UPDATE/quantità negativa, nessun movimento fisico, nessuna revisione/riga commerciale automatica.
- Primo scope: commessa aperta e prenotazione mai prelevata; dopo qualsiasi pick, nuove release sono rifiutate anche sul residuo non prelevato. Non è un divieto universale di dominio. Dopo chiusura tecnica nessuna nuova scrittura; replay di ricevuta accettata resta leggibile con autorizzazione corrente anche con capability disattivata/chiusura.
- Solo profilo stock societario locale; missing/external bloccano le scritture, non lo storico.

## Calcoli coerenti

attivo = prenotato − rilasciato − consumato; disponibile = fisico − attivo; residuo riga = quantità − (prenotato − rilasciato). Il consumo non riapre la capacità prenotabile. Il picking usa residuo prenotazione − rilasciato − prelevato. `inventory.line_has_commitments` considera una prenotazione interamente compensata senza pick/consumo non attiva (P2 correzione/rimozione), una parziale resta bloccante.

## Concorrenza

Ordine: UUID comando → ordine → riga (cumulativa tra magazzini) → stock → reservation; Reserve, Pick e Release usano lo stesso ordine; trigger SQL replica fatti freschi. Grant/capability vengono riletti con `organization_access.inventory_release_authorized` sulla stessa connessione e transazione (nessuna connessione annidata). Revoca durante attesa del lock viene osservata prima della scrittura.

## UI e prove

Pannello Italiano “Rilascio prenotazione”: prenotazione specifica, quantità esplicita, storia, advisory server, comando congelato (URL/UUID/body) dopo esito incerto, ricevuta accettata distinta da rilettura non verificata. Prove: `python3 scripts/run-r04c1-tests.py` (pool4) e `R04A_POOL_SIZE=1`, `scripts/test-r04c1-lifecycle.py`, selettore `affected-r04c1` su dispatch (non full architecture). Il nuovo table è inventario R06 con eligibilità UNDECIDED, nessuna approvazione di migrazione.

Rollback: ripristino tracciato del commit; per database effimeri ricreazione. In un ambiente con fatti 0023 un downgrade distruttivo non è previsto: i fatti compensativi vanno preservati.
