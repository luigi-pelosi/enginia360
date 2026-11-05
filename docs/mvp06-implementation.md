# MVP06 / #145 — CONSEGNATO PR170

Stato corrente verificato dal coordinatore: MVP06/#145 COMPLETATO con PR170, merge `6ca378d94435eb78ff4955128e3646cc64ef1ece`, candidato `149687265fb2f76550032333c660dca6f445d6b5`, tree equivalente `6e002f5cdce3769f8fedf1032b135f009ca33dd2`; PR CI41881635998 (5job/60step), dispatch41881398306 (16job/148step),10ZIP SHA256/head e24TRX328eseguiti/passati zero skip/fail riletti dal parent. Non nuova CI main. Issue145 chiusa/Project Completato. MVP07/#146 consegnato PR171; MVP08/#147 SOURCE-ONLY UNVERIFIED;–149 Backlog. Incidente storico dispatch41873815332: overflow native-noJS pool1 inizialmente fallito, causa non provata; diagnostica soltanto, nessuna asserzione/CSS/attesa/deadline indebolita; successivi pass non provano una causa/fix. Smoke HTML lang=it protetto NONPASS non attribuibile al candidato, nessuna investigazione/restart. Valutazione sicurezza framework limitata alle modalità già documentate, non clearance operativa.

## Checkpoint storico SOURCE-ONLY MVP06 — non stato corrente


Intero punto implementato nei sorgenti prima della validazione. Nessun test,
build, typecheck, audit, npm ci, migrazione, runtime/container, smoke o CI avviato
in questa fase. Nessun commit/push/PR, scrittura issue/Project, merge o deployment.
I diagnostici automatici dell'editor non sono acceptance: nel worktree mancano
le dipendenze frontend installate; gli helper dinamici dei test SQL non sono
risolvibili staticamente. Tutti i risultati applicativi rimangono UNVERIFIED.

Base `43a4ff836d67bf1b4f01eb27ccc318171ee45f8d`, branch
`feat/mvp-document-types`, worktree esclusivo
`/root/.hermes/cache/scratch/enginia360-mvp-document-types`.
[Contratto finito e tracciamento ownership](mvp06-document-types-contract.md)
scritti prima dei sorgenti produttivi. Checkpoint progressivo con manifest
tracked + untracked e SHA256:
`/root/.hermes/evidence/enginia360-mvp06/source-checkpoint.json`.

## Criteri dell'intero #145 nei sorgenti, non prove eseguite

| Criterio | Percorso implementato / accettazione preparata |
| --- | --- |
| Ogni società gestisce le proprie tipologie autorizzate | Nuovo modulo di dominio DocumentTypes, schema company-owned, chooser derivato dalle reali permission read; nessun organization.read o directory get-all richiesto. `/document-types` SSR italiana: selezione società, ricerca, paginazione, dettaglio, creazione e modifica. SQL e browser due società dello stesso cliente, tenant diverso, grant corrente/revoca. |
| Quattro comportamenti supportati | Enum tipizzato `Load`, `Unload`, `Transfer`, `None`, label minimo; SQL vincola anche gli ingressi diretti. UI espone Carico/Scarico/Trasferimento/Nessun effetto e persiste ogni valore. SQL, bearer API e browser coprono tutti e quattro. Configurare non crea documenti o stock. |
| Nessuna formula/codice o bypass | Campi chiusi e tipi/limiti ricontrollati in API e SQL, UUID canonici/nonvuoti, duplicate key/NUL/surrogati/numeri/corpo ostili, nessun tenant accettato. Nuove permission D97 read/create/edit COMPANY esatta, null site/warehouse espliciti. Preservato l'intero algoritmo precedente salvo whitelist dei tre nuovi consumer. Nessun potere business da amministrazione; nessun owner/master/ERP setup per questa configurazione societaria. |
| Versioni e audit senza riscrittura | Identità stabile, puntatore tecnico corrente e versioni immutabili. Ogni modifica inserisce una nuova versione e audit prima/dopo atomico. UI rilegge corrente e mostra la versione storica scelta con data. Replay storico originale anche dopo edit; autorità corrente prima di lookup; collisione UUID cross-company/tenant/attore/payload fail-closed. Nessun nuovo fatto documentale parallelo. |

## Fonti e proprietà

- `0044_document_types.sql`: definitions/versions/command_audit, FORCE RLS,
  policy owner-private; application senza DML/SELECT diretti, due soli ingressi
  finiti EXECUTE. Owner definer nonprivilegiato e search_path fissato. Ogni read e
  comando detiene 777036, binding/membership attuali, witness MVCC e righe attuali
  di role/permission/assignment/società nella transazione proprietaria.
- Le migrazioni 0001–0043 non vengono modificate. Manifest append-only e inventario
  aggiungono soltanto le tre nuove tabelle; tutte le classificazioni precedenti
  restano intatte, eleggibilità legacy UNDECIDED. Nessun seed commerciale.
- `DocumentTypes:Enabled` è attivato soltanto nella composizione di acceptance
  effimera; non viene cambiato alcun ambiente o `.env` persistente. Nuovi progetti
  riusano gli stessi package/versioni/hash dei lock preesistenti; soltanto i due
  lock di composizione ricevono gli edge Project aggiuntivi. Nessuna dipendenza
  esterna o immagine nuova.
- Workshop/Billing/Inventory/Integrations e i loro fatti restano invariati.
  Le famiglie documentali storiche non limitano le tipologie MVP. Nessun modulo
  dipende da un nuovo motore o da un resolver ipotetico. L'endpoint di storico è
  già consumato da UI/readback, non inventato per un futuro engine.
- SSR force-dynamic/revalidate0, private/no-store, cookie per richiesta al backend
  HTTPS finito. Comandi disabilitati prima hydration e nascosti senza JS; letture
  native disponibili. Retry conserva route/UUID/byte/società dopo ACK perso,
  CSRF refusal e GET fallito. Stato incerto nasconde dati/chooser obsoleti e blocca
  navigazione ordinaria. Recupero solo nella pagina viva.

## Harness completo preparato

- `scripts/test-mvp06-document-types.py`: PostgreSQL reale, quattro effetti,
  versioni storiche, isolamento società/tenant, replay e collisioni, campi e
  scope/null esatti, insert/deferred-commit audit rollback per create/edit e
  tutti gli effetti, immutabilità/ACL/RLS, pagina lista e storico, revisione max,
  concorrenza, permesso/ruolo/assegnazione/binding/disable in entrambi gli ordini,
  snapshot RR vecchio fail-closed.
- `DocumentTypeManagementTests.cs`: bearer realmente firmato, composizione senza
  Workshop/Catalog/Counterparties, pool1/4, ogni effetto, chooser minimo, storico
  e replay, input JSON ostili e query duplicate, no-store, revoca sessione.
- `tests/browser/mvp06-document-types.cjs`: OIDC e JWT IdP reali, permessi societari
  creati tramite editor D97 italiano, grant reale e consumer effettivo; due società,
  ricerca/dettaglio/create/edit/storico per quattro effetti, SSR noJS e screenshot,
  chunk client effettivamente ritardato, CSRF assente/alterato con payload valido,
  tre POST identici dopo esito perso/CSRF refusal/reread failure, revoca scope di
  una società conservando l'altra, ruolo/assignment/binding/disable aperti.
- `scripts/run-mvp06-tests.py`: runner isolato riusando pin, CA/TLS e rete interna;
  pool4/1, SQL + API + browser e readback diretto delle versioni/audit, nessun
  nuovo master-setup. Runtime catalog reale SD/ACL/RLS con tutti gli ingressi
  storici e soltanto due nuovi endpoint eseguibili; private snapshot/helper non
  eseguibili. Classifica l'outbox reader storico esatto senza nuovi bypass.
  Controlla hardening anche del browser one-shot mentre è vivo. Preserva
  ID/start/mount dei servizi preesistenti, volumi e cleanup esatto project/config;
  deriva esterna separata, nessun inspect Config/Env non pertinente.
- Frontend test usa il componente reale, chooser e snapshot storico, quattro
  effetti, no invented fields, hydration-disabled, trasporto cookie/no-store e
  allowlist finita. Acceptance shell aggiornata soltanto per il nuovo percorso.
- Guardie `test-mvp06-contract.py` e `test-mvp06-impact.py`: byte pubblicati e
  inventario precedente, lock package invariati, algoritmo D97 esatto,
  D97/D98 letterali, negativi sugli stati correnti, ingressi SD esatti e selezione
  CI finita/direct/mixed/unknown. Nessuna guardia eseguita durante implementazione.
- CI: output `document_types`, nuovo job dispatch exact-head, pool4 e pool1,
  TMPDIR privato e artefatto `mvp06-${github.sha}`. Automatico PR-only invariato,
  routine full_architecture=false. Vecchi consumer e unknown/mixed-path refusal
  preservati; classificatori runtime precedenti ammettono esattamente i due
  nuovi ingressi. Il catalogo azioni corrente resta una lista esatta, non subset.

## Riconciliazione del predecessore

AGENTS, carta, baseline, piano, backlog e assessment indicano #144 completato da
PR169 e #145 in implementazione non verificata. Evidenze fornite dal coordinatore:
merge `43a4ff836d67bf1b4f01eb27ccc318171ee45f8d`, candidato
`b6a337d35826d23de2465f79e99bd4f6105da458`, tree equivalente
`2d5c06ae8c83e744a88e20abdcc0c34f0066ad81`, PR CI `41833394752`, dispatch
`41833450699`, nove ZIP verificati e 20 TRX con 274 eseguiti/passati, zero skip.
Non è una nuova esecuzione main. Contratto/implementation MVP05 conservano i
checkpoint cronologici sotto una testata corrente verificata. D97/D98 letterali
restano intatti e storici dei rispettivi gate documentali. #146–#149 Backlog.
Nessun readback remoto o riscrittura tracking attribuito a questo writer.

## Confini ancora aperti, non blocchi di #145

#146 definirà documenti/conferma/stock e riferimento esatto alla versione applicata
per ciascuna operazione, non necessariamente congelata alla creazione per tutta
la vita del documento. #147 definirà sviluppo/grouping/compatibilità/residui.
Non vengono decisi lifecycle/delete/published/approver/numbering/fiscalità,
quantità insufficienti, negative-stock o workflow non confermati. Nessuna readiness
operativa, IdP reale, dati reali, accesso pubblico o deployment implicito.
Il NONPASS storico dello smoke del servizio protetto non è prova del candidato;
nessuna investigazione, restart o correzione del deployment protetto eseguita.
La valutazione Next16.4.4 rimane limitata ai modi già documentati in MVP05, non
una security clearance: nessuna superficie Cache Components/Edge/image/upstream
Response pass-through introdotta; rivalutazione/audit nella fase finale.

## Comandi finali preparati — NON ESEGUITI

Il coordinatore può avviare la validazione dell'intero punto senza riconfermare
il dominio. Conservare log, exit, hash sorgenti, incidenti NONPASS e correzioni;
mai sostituire output mancante con dati plausibili. Non sovrapporre runner con
snapshot dei container preesistenti.

```sh
export TMPDIR=/root/.hermes/cache/scratch
export EVIDENCE=/root/.hermes/evidence/enginia360-mvp06/final
mkdir -p "$EVIDENCE"
python3 -I scripts/test-mvp06-contract.py
python3 -I scripts/test-mvp06-impact.py
python3 -I scripts/test-mvp05-contract.py
python3 -I scripts/test-mvp05-impact.py
python3 -I scripts/test-d97-policy.py
python3 -I scripts/test-d98-policy.py
python3 -I scripts/test-mvp-baseline.py
python3 -I scripts/run-mvp01-tests.py --build-only --evidence-dir "$EVIDENCE/frontend"
MVP06_POOL_SIZE=4 timeout 1500 python3 -I scripts/run-mvp06-tests.py --evidence-dir "$EVIDENCE/pool4"
MVP06_POOL_SIZE=1 timeout 1500 python3 -I scripts/run-mvp06-tests.py --evidence-dir "$EVIDENCE/pool1"
```

Prima di dichiarare completamento verificato: eseguire la selezione esatta dei
path tracked+untracked con `select-ci-impact.py --paths-json`, conservarla nel
ledger; eseguire tutti i consumer selezionati secondo il workflow, inclusi build,
test e audit API/frontend pinned e runner catalog/counterparty/roles/membership/
onboarding/authenticated organization/foundation/browser pertinenti. Le prove
preparate nuove non sostituiscono i vecchi consumer né trasformano skip in pass.
Dopo correzioni e validazione finale effettiva, parent gestisce commit/push/PR,
CI PR-only e dispatch sullo stesso head, download/inspection artefatti, merge e
rilettura issue/Project. Nessuna full architecture di routine o release operativa.
