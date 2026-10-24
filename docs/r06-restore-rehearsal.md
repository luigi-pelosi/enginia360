# R06.b.1 — rehearsal di restore current-runtime (sintetico, effimero)

Refs #80, parent #46 (resta aperta). **Prova tecnica opt-in su un singolo host, dati sintetici; non è una procedura di backup di produzione, non approva migrazione, go-live, dati reali né eleggibilità di tabelle.** La classificazione R06.a.1 resta `UNDECIDED`.

## Cosa fa

`scripts/run-r06b1-tests.py` (nessun target accettato in input: progetto `enginia360-r00b-<12 hex>` casuale, compose dedicato `compose.r06b1-test.yaml`, nessuna porta host, nessun volume, container nonroot/read-only/`cap_drop: ALL`, PGDATA su tmpfs):

1. **A init-only** (solo ruoli/ACL, zero relazioni di dominio, nessun ledger) → migratore reale sul manifest esatto di *tutte* le migrazioni correnti → seconda esecuzione no-op (ledger identico incl. `applied_at`).
2. **Popolamento solo via API autorizzate** (Chromium reale, OIDC/PKCE, CA fidata): ordine/gruppi/righe/nota, tempo effettivo proprio (create + correzione + ricevute, due operatori dello stesso tenant), prenotazione/rilascio esplicito/prelievo/installazione/rientro carcassa, chiusura tecnica, snapshot Billing e giornale Accounting bilanciato, richiesta amministrativa esterna di un altro tenant.
3. **Quiescenza** (API/web fermi, zero backend applicativi, due snapshot uguali) → baseline SQL dinamica → marker *pre-dump* (nota d'ordine) → `pg_dump --format=custom` binario (0600, fuori da PGDATA, sha256 + TOC) → marker *post-dump* (deve risultare assente dopo il restore).
4. **Distruzione reale** del container PostgreSQL A (e del suo PGDATA tmpfs) → **cluster B nuovo** (`system_identifier` diverso, solo ruoli infrastrutturali, zero relazioni di dominio) → `pg_restore --exit-on-error --single-transaction` (nessun `--clean/--create/--no-owner/--no-acl`; i ruoli globali vengono dal bootstrap, non dal dump).
5. **Confronto a freddo**: conteggio + sha256 di **ogni tabella scoperta dinamicamente** (nessun numero fisso), ledger id/checksum/`applied_at`, fingerprint di catalogo (relazioni, colonne, vincoli, indici, policy RLS, ACL, owner, trigger, funzioni, sequenze, ruoli, database). Migratore su B = no-op verificato due volte.
6. **Usabilità HTTP**: riavvio API/web senza ricreare dati, **nuovo contesto browser** e login OIDC/PKCE, readback autorizzato (proiezione semantica identica, ogni ricevuta riprodotta con stesso URL/UUID/payload, isolamento own-time altro operatore/altro tenant/anonimo/CSRF, storico rilasci), `runtime_app` reale (non superuser, non BYPASSRLS) per RLS e reset del contesto su un solo backend, **pool API 4 poi 1**; nessuna riga nuova dopo readback/replay.
7. **Fallimento di una migrazione solo scratch** (manifest scratch: i file pubblicati sono copie read-only con hash identici, mai modificati): rollback, prefisso del ledger intatto, lock rilasciato, sentinella non eseguita; poi unità scratch *forward-fix* append-only, replay no-op, drift di checksum rifiutato; il dump pre-fallimento è ancora integro e il suo ledger coincide col prefisso pubblicato.

Tempi: `time.monotonic()` per fase, etichetta **«synthetic ephemeral single-host measurement»**. **Non sono evidenza di RPO, RTO, SLA, PITR, copia off-host o disaster recovery; OPE03 resta aperta.** L'IdP sintetico non fa parte del cluster perduto.

## Esecuzione e limiti

```
cd web && npm ci && npm run build:ui01-runtime    # editor runtime separato, opt-in
TMPDIR=<scratch privato> timeout 600 python3 scripts/run-r06b1-tests.py
TMPDIR=<scratch privato> timeout 420 python3 scripts/test-r06b1-lifecycle.py --actual dump|restore|browser
```

CI: automatico su PR solo `scripts/test-r06b1-impact.py` e `scripts/test-r06b1-guards.py` (offline). Il restore reale è il job `affected-r06-restore`, **solo `workflow_dispatch` su exact head** con `full_architecture=false`; un job saltato non è una prova.

Normalizzazioni documentate del confronto (trovate dal rehearsal, non perdite di dati):

- **ACL**: `pg_dump` omette un'ACL uguale al default; un'ACL esplicita `{owner=arwdDxtm/owner}` (o EXECUTE a PUBLIC per le funzioni) si ripristina come `NULL`. Si confrontano i **privilegi effettivi** (`coalesce(acl, acldefault(...))`); ACL con PUBLIC revocato o grant a ruoli restano confrontati esattamente.
- **CHECK**: PostgreSQL ri-analizza l'espressione deparsata e ne emette una forma equivalente con cast diversi; solo per i vincoli `CHECK` si confronta il testo senza cast di tipo/parentesi/spazi (identificatori, letterali e operatori restano). PK/FK/unique/exclusion restano esatti.
- Esclusi dal digest dati solo i namespace `^pg_` e `information_schema` (la regex è letterale: uno schema `pgx_*` resterebbe incluso) e le relazioni temporanee; il ledger **non** è escluso.

Limiti: singolo host; PostgreSQL e API condividono il Docker daemon; dump logico completo di un dataset minimo (non misura volumi reali); nessun WAL/PITR; dump e fixture restano nello scratch effimero e non sono artefatti; in caso di SIGKILL dell'intero orchestratore non si promette cleanup (il migratore ha la guardia parent-death, il runner Docker no). Rollback: nessuno stato persistente; `docker compose down` guardato elimina l'intero progetto; i container bootstrap `enginia360-api-1/web-1`, i 25 volumi e i backup non sono mai referenziati dal runner e il loro inventario è confrontato prima/dopo.
