# R06.a.2 — export/import sintetico STAGING-ONLY con replay e riconciliazione

**STAGING-ONLY. NON è migrazione di prodotto/dominio.** Refs #106, parent #46 **aperta**. Nessun permesso di migrazione, nessuna readiness o go-live. Tutte le 66 voci dell'[inventario](r06-migration-inventory.md) restano **UNDECIDED**; il [registro](r06-readiness-registry.json) resta OPEN (OPE01–OPE05 invariati, nessuna evidenza o approvazione aggiunta). Nessuna tabella reale, migrazione (0001–0026 invariate, nessuna nuova), ERP, identità reale, credenziale o dato reale è toccato.

## Cosa è stato costruito

- `scripts/r06a2_transfer.py` — formato finito `R06A2_STAGING_ONLY_V1`: intestazione `source_system`/`batch_id`/`revision` sintetici (`SYNTH-INVALID-FOR-PRODUCTION-…`), `context` (authority `STAGING_PROBES_ONLY_NO_DOMAIN_AUTHORITY` + scope tenant/società/sede/magazzino/scope derivati), `counts`, `dataset` nel formato **R06.a.1 invariato** (`SYNTH_INVALID_FOR_PRODUCTION_V1`), `sha256` canonico. Validatore `parse` puro (JSON senza chiavi duplicate, ≤2 MB, ≤1000 record, campi esatti, versione, decimali stringa canonici q6, sconto scala 2 come nel contratto R06.a.1 — **limite esplicito**, nessuna estensione —, identità sintetiche, duplicati source/internal, ordine canonico, conteggi, scope, authority, checksum).
- `scripts/r06a2_storage.py` — `export_source` (legge la tabella `r06a2_staging.source` realmente memorizzata), `import_bytes` (parse **prima** del primo statement; una sola transazione PostgreSQL con lock `SHARE ROW EXCLUSIVE`), `export_target` (legge le righe importate). Comparazione con il riconciliatore esistente `r06_reconcile.compare`, Decimal, nessun float.
- Storage: **PostgreSQL effimero** (container `enginia360-r00b-<12hex>`, rete `none`, nonroot 70:70, read-only, cap-drop ALL, no-new-privileges, risorse e log limitati, PGDATA tmpfs, nessuna porta/volume), solo schema `r06a2_staging` con tabelle `source`, `configuration`, `batches`, `imported`, `audit`. Nessuna migrazione applicativa, motore migrazioni o endpoint di produzione.

## Semantica

| Caso | Esito |
| --- | --- |
| Primo import | `batches`=1, `imported`=8 (source_system, batch, revision, source_id, internal_id, batch_hash, payload), `audit`=1 |
| Replay identico (stessa chiave+hash) | accettato, nessuna riga/audit in più, snapshot identico inclusi timestamp |
| Stessa chiave, contenuto diverso | rifiutato atomicamente (eccezione transazionale), target invariato |
| Scope/authority diversi o target senza configurazione | rifiutato/«held», nessuna scrittura, **nessun cambio automatico** della configurazione |
| Versione/numeri/oversize/chiavi duplicate/checksum/conteggi | `ValueError` prima di qualsiasi statement di storage |
| Fault dopo scritture parziali (trigger solo-fixture) | rollback di batch + 8 righe, retry pulito importa 8 |

Non inferisce autorità di stock, non crea eventi stock o documenti locali, non importa identità reali. `physical_stock`/`reserved_stock` sono sonde copiate così come nel contratto R06.a.1, non saldi. Import concorrente identico: lock tabella batch, un solo set.

## Comandi e risultati effettivi (log in scratch privato, exit preservati)

| Comando | Risultato |
| --- | --- |
| `python3 -I scripts/test-r06a2-impact.py` | RED iniziale: 3 fallimenti (`extend and test direct-dependency impact mapping`, workflow privo di job); GREEN 4 test |
| `python3 -I scripts/test-r06a2-storage.py` / `python3 -I scripts/run-r06a2-tests.py` | `Ran 9 tests OK`, exit 0, DB PostgreSQL reale; source=8 imported=8 matched=8; replay audit=1; 4 import simultanei → 1/8/1; cleanup e inventario protetto invariati |
| `python3 -I scripts/test-r06a2-transfer.py` | 5 test puri OK (versione, oversize, checksum, conteggi, q6, identità, scope, authority) |
| `python3 -I scripts/test-r06a2-lifecycle.py` / `--actual` | guard offline OK; `--actual`: TERM con DB vivo → container rimosso, exit≠0 (−2), container protetti/StartedAt/25 volumi invariati |

### RED osservati prima del codice
1. impact: selettore/workflow privi di `r06a2`.
2. `test_01`: `stored-source exporter / transactional importer missing`.
3. `test_02` replay: `CalledProcessError` (duplicate key) invece di accettazione.
4. `test_03`: `ValueError not raised` (contenuto modificato ignorato silenziosamente da un naive skip).
5. pure guards: `AttributeError: no attribute 'parse'`.
6. `test_04`: `ValueError not raised` (input non validato).
7. `test_05`: `ValueError not raised` (nessuna verifica di scope/authority).
8. lifecycle: `staging runner missing`.

`test_06`–`test_09` (rollback con fault, tracciabilità, tampering via riconciliatore, concorrenza) sono **regressioni scritte dopo l'implementazione**: passavano subito, non sono RED.

## CI

PR automatica: `impact` (+ `test-r06a2-impact.py`) e `affected-r06-offline` (transfer puro e lifecycle offline; il caso TERM reale è *skipped* in quel job e non vale come pass). Runtime: solo dispatch esatto sull'head con `full_architecture=false`, job `affected-r06-staging` (`run-r06a2-tests.py`, `test-r06a2-lifecycle.py --actual`). Nessun push su main, nessuna full architecture. Un job runtime saltato non è un pass.

## Limiti stretti e rollback

- Prova **solo** su schema di staging effimero con sonde sintetiche; non è import di dominio, né idempotenza di una migrazione reale, né compatibilità Giobby/ERP, off-host, RPO/RTO o validità fiscale.
- Il formato, lo schema `r06a2_staging` e la `configuration` sono fixture di prova, **non** una scelta di autorità, mapping, eleggibilità o stock iniziale; un eventuale mapping a tabelle reali richiede decisione owner separata.
- Rollback: revert della PR (script, selettore, workflow, documenti). Nessuna migrazione, nessun dato persistente, nessun volume, bootstrap/Tailscale 443→9119/25 volumi non toccati.
