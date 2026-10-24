# R06.b.1 — rehearsal di restore current-runtime (sintetico, effimero)

**Stato corrente R06.b.2:** prova tecnica R06.b.1 consegnata (PR #81); [registro OPE OPEN](r06-readiness-registry.json) e [runbook/limiti correnti](r06-recovery-runbook.md). Parent #46 aperta; nessuna readiness operativa. Le sezioni sotto conservano l'evidenza storica e il contratto della prova.

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
- **CHECK**: entrambe le definizioni (origine e restore) sono ri-analizzate **dallo stesso PostgreSQL**, come nel restore logico, tramite una funzione `pg_temp` e una tabella temporanea vuota `LIKE` la tabella originale (stessi nomi, tipi e collation). Si confronta il nuovo `pg_get_constraintdef` **integrale**. Nessuna regex, parser SQL applicativo o dipendenza nuova; parentesi, spazi/byte nei letterali e identificatori quotati e cast significativi non vengono eliminati. Funzione/tabella sono solo temporanee e l'intera normalizzazione termina con `ROLLBACK`; nessun oggetto sorgente o migrazione pubblicata viene riscritto. PK/FK/unique/exclusion usano ancora la definizione originale esatta.
- Esclusi dal digest dati solo i namespace `^pg_` e `information_schema` (la regex è letterale: uno schema `pgx_*` resterebbe incluso) e le relazioni temporanee; il ledger **non** è escluso.

## Integrità dopo il readback (nessuna eccezione ai dati)

Il confronto a freddo rimane rigoroso su tutte le tabelle. Anche dopo readback/replay, **tutti i conteggi e gli hash di tutte le colonne di tutte le righe devono essere identici**, inclusa `integrations.administrative_dispatches`: nessuna allowlist di tabelle o colonne, neppure per timestamp/contatori di retry.

Per rendere deterministico questo secondo confronto, solo nel cluster B effimero e dopo la verifica cold/no-op, prima di avviare API/web si revoca temporaneamente **solo INSERT** sulla tabella dispatcher a `runtime_app`. Il percorso corrente `AdministrativeDispatcher.Claim` esegue sempre prima `INSERT ... ON CONFLICT DO NOTHING`, anche per richieste esistenti, prima di qualunque UPDATE di lease/retry. PostgreSQL verifica INSERT anche se il conflitto produrrebbe un no-op: il worker fallisce prima di modificare lo stato; SELECT e i permessi UPDATE per colonna restano intatti. Si verificano il privilegio effettivo negato e un INSERT reale rifiutato; pool 4 e 1 eseguono normalmente il readback. Dopo lo stop di API/web, il `finally` ripristina INSERT e verifica l'**ACL esatta precedente**. Nessuna configurazione di prodotto o migrazione cambia. Se questo percorso del dispatcher cambia, la guardia che ne traccia l'INSERT iniziale deve essere aggiornata: non allargare le eccezioni al contenuto.

## Regressioni ed evidenze della correzione

`python3 scripts/test-r06b1-guards.py --actual` avvia PostgreSQL della stessa immagine pinned in un container separato, nonroot/read-only, rete `none`, tmpfs, nessuna porta/volume; rimuove solo il proprio container verificato per label. Il runner completo lo esegue prima del rehearsal, quindi il dispatch exact-head esegue anche queste regressioni reali. Le prove TERM non duplicano le regressioni già eseguite dal rehearsal.

- RED prima delle correzioni: collisioni CHECK reali per raggruppamento booleano (`false` contro `true` con `a=true,b=false,c=false`), whitespace e testo cast-like nei letterali, cast text/bpchar significativi; mutazioni reali di identità, tenant, payload, provenienza e retry non venivano rilevate dal readback.
- GREEN: fingerprint distinti per tutte le espressioni non equivalenti e identificatori quotati; reparse stabile; grant/revoke PUBLIC rilevati; mutazioni SQL di ogni categoria, aggiunta e rimozione righe rifiutate dal confronto effettivo del runner. Il payload/provenienza sintetico aggiunto alla tabella di prova dimostra che anche colonne non conosciute al comparatore rimangono incluse.
- Evidenze locali private: `r06b1-logs/23-check-collisions-red.log`, `26-dispatcher-integrity-red.log`, `27-guards-green.log`, `30-runtime-guards-red.log`; i successivi log conservano rehearsal, guardie e tre prove TERM bounded. Il log 29 è interrotto dal limite del tool a 420 secondi (non un pass); cleanup mirato e inventario protetto sono stati riverificati prima di rieseguire con lo stesso limite del comando di 600 secondi.
- Correzione riferimento storico: il dispatch precedente verificato per `8a1a8c99df2df7775f6c5a1c7de1d50e52450ee2` è **40097103714**, non 40097224642. PR CI precedente: 40097097340. Non valgono per il nuovo head: il report finale registra separatamente i nuovi ID/URL letti tramite API e i job realmente eseguiti con `full_architecture=false`.

Limiti: singolo host; PostgreSQL e API condividono il Docker daemon; dump logico completo di un dataset minimo (non misura volumi reali); nessun WAL/PITR; dump e fixture restano nello scratch effimero e non sono artefatti; in caso di SIGKILL dell'intero orchestratore non si promette cleanup (il migratore ha la guardia parent-death, il runner Docker no). Rollback: nessuno stato persistente; `docker compose down` guardato elimina l'intero progetto; i container bootstrap `enginia360-api-1/web-1`, i 25 volumi e i backup non sono mai referenziati dal runner e il loro inventario è confrontato prima/dopo.
