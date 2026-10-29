# R06.a.1 — inventario offline e riconciliazione sintetica

**Stato corrente R06.b.2:** tool R06.a.1 consegnato (PR #77), inventario aggiornato dai successivi incrementi; [registro OPE OPEN](r06-readiness-registry.json), [runbook/limiti correnti](r06-recovery-runbook.md). Il roundtrip sintetico STAGING-ONLY con replay è in [R06.a.2](r06a2-synthetic-import-export.md); import di dominio, tabelle reali e replay d'import reale restano non provati e UNDECIDED; parent #46 aperta. Le prove sotto non sono approvazione della migrazione.

**Perimetro 27 ottobre 2026 (D87, scoping owner):** migrazione legacy fuori perimetro per ora — «Per ora non è prevista nessuna attività di migrazione dal sistema legacy.» Non è un divieto permanente né un’approvazione. R06.a completa per i soli strumenti sintetici staging-only consegnati (#76/#77, #106/#107); 66 voci UNDECIDED (eleggibilità invariata, registro OPEN); restore di fatti già legittimi e onboarding D77 non toccati; OPE01–OPE05 invariati OPEN; #46 aperta.

**PROPOSTA tecnica di inventario, NON approvazione della migrazione.** Refs #76, parent #46 aperta. Baseline letta: `6ca042e66a826a1f45e0f7f72a004f1ecc58ade0` (R03.c); non il baseline ormai storico dell'handoff. Questo incremento implementa strumenti offline Python stdlib, non l'intera R06.a né R06.b. Non cambia applicazione, SQL, checksum, manifest, dipendenze o deployment.

## Inventario verificabile, non schema ipotizzato

`r06-migration-inventory.json` contiene una voce per ogni `CREATE TABLE` dei soli SQL pubblicati scelti da `database/runtime/manifest.json`. `scripts/r06_inventory.py` riusa **solo il caricatore/validatore** del manifest: nessuna chiamata ad `apply_migrations`, PostgreSQL, API o repository legacy. Ordine, percorso allowlistato e checksum sono verificati prima dell'estrazione. I file esclusi dal manifest non entrano nel conteggio. Commenti, stringhe e corpi dollar-quoted sono ignorati; grammatica CREATE non supportata, definizioni duplicate/incomplete e nuove tabelle non inventariate falliscono chiuso.

Risultato calcolato sul baseline R05.b.1: **26 migrazioni, 66 definizioni CREATE, 9 schemi**. La 0026 estende soltanto il CHECK Kind del binding a GiobbyV1: nessun nuovo CREATE, nessuna ricostruzione dello schema ALTER nel JSON; le 66 voci restano identiche e UNDECIDED. La nuova `workshop.administrative_bindings` è classificata `integration_evidence`, con eligibilità **UNDECIDED** e `NO_LEGACY_IMPORT_APPROVED`; il binding tecnico sintetico non approva import, Giobby o readiness. Non sono costanti nel verificatore: il test aggiunge una migrazione scratch con una tabella nuova e richiede il rifiuto per copertura mancante. Il ledger `runtime_migrations.applied` e le tabelle temporanee del motore non sono CREATE dei file del manifest e quindi sono esplicitamente fuori da questo inventario. Non si dichiara di aver interrogato un database.

**Aggiornamento R04.b.1 (D88):** la migrazione append-only 0027 porta il conteggio a **27 migrazioni, 67 definizioni CREATE, 9 schemi**; la nuova voce `counterparties.giobby_vendor_identity_history` (estensione societaria, storia immutabile dell’ID fornitore Giobby) è UNDECIDED come le altre, nessuna approvazione di migrazione. La colonna `IsSupplier` è un ALTER e non è una definizione CREATE inventariata.

**Aggiornamento R04.b.2a (D88/D90):** la migrazione append-only 0028 porta il conteggio a **28 migrazioni, 69 definizioni CREATE, 9 schemi**; `inventory.purchase_intents` (`operational_fact`) e `inventory.purchase_intent_outbox` (`integration_evidence`) sono UNDECIDED come le altre, `NO_LEGACY_IMPORT_APPROVED`, nessuna approvazione di migrazione o readiness.

**Aggiornamento R04.b.2b.1 (D91):** la migrazione append-only 0029 porta il conteggio a **29 migrazioni, 71 definizioni CREATE, 9 schemi**; `catalog.supplier_purchase_price_history` (`company_extension`) e `organization_access.purchase_price_grant_history` (`security_evidence`) sono UNDECIDED come le altre, `NO_LEGACY_IMPORT_APPROVED`, nessuna approvazione di migrazione o readiness.

**Aggiornamento R04.b.2b.2 (D91/D92):** migrazione append-only 0030, 30 migrazioni, 72 definizioni CREATE, 9 schemi. `inventory.purchase_intent_prices` (`operational_fact`) registra soltanto il prezzo accettato/provenienza dell’intento, UNDECIDED e NO_LEGACY_IMPORT_APPROVED; nessuna approvazione di migrazione o readiness.

**Aggiornamento R04.b.2b.3:** migrazione append-only 0031, **31 migrazioni, 74 definizioni CREATE, 9 schemi**. `inventory.purchase_intent_outcomes` e `integrations.purchase_dispatches` sono `integration_evidence`, entrambe UNDECIDED / NO_LEGACY_IMPORT_APPROVED. Le 72 voci precedenti restano identiche; esito immutabile e stato tecnico non sono documento acquisti/stock locale né autorizzazione di migrazione.

**Aggiornamento R04.b.2b.3 PR2:** migrazione append-only 0032 (solo `CREATE OR REPLACE FUNCTION inventory.purchase_intent_state`, nessuna tabella): **32 migrazioni, 74 definizioni CREATE, 9 schemi**; le 74 voci restano identiche, nessuna approvazione di migrazione o readiness.

Ogni voce registra:

- `table`, `owner`: nome qualificato e modulo/schema proprietario osservato, non una nuova ownership di business;
- `definition`: migrazione, percorso, SHA-256 del file, testo CREATE esatto, colonne e chiave primaria di quella definizione;
- `category`: classificazione tecnica proposta, non decisione fiscale o di migrabilità;
- `reconcile_keys`: PK e colonne di scope disponibili nel CREATE; quando un figlio eredita scope da riferimenti, il confronto reale richiederà il join autorizzato del modulo, non un tenant inventato;
- `available_command`: registrazione di un comando operativo esistente con percorso sorgente verificato, **non** autorizzazione/import API. Sono evidenziate 20 associazioni tabella/comando; `null` nelle altre 46 significa «nessun comando diretto identificato in questo inventario», non assenza di ogni writer o prova runtime del comando;
- `migration_eligibility`: **UNDECIDED per tutte le 66 voci**;
- `handling_constraint`: D77 `RESTORE_ONBOARDING_ONLY` per i sette binding/accessi di sicurezza, altrimenti `NO_LEGACY_IMPORT_APPROVED` (nessuna approvazione acquisita, NON divieto permanente dello storico).

Le definizioni CREATE non ricostruiscono ALTER successivi, RLS, indici, trigger o lo stato corrente del DB. I checksum dei file pubblicati coprono anche quelle istruzioni; questa è una fotografia delle definizioni CREATE pubblicate, non un motore SQL generale né un piano di import.

| Categoria tecnica proposta | Tabelle |
| --- | ---: |
| organization_structure | 4 |
| security_binding | 7 |
| security_evidence | 2 |
| shared_master | 3 |
| company_extension | 1 |
| business_configuration | 11 |
| authority_evidence | 2 |
| operational_fact | 23 |
| stock_state | 1 |
| integration_evidence | 6 |
| audit_history | 2 |
| derived_projection | 1 |
| technical_ledger | 3 |

`operational_fact` non significa che ogni colonna sia immutabile; è una categoria di responsabilità tecnica. Le policy dei moduli e i fatti/versioni già pubblicati restano invariati. Il restore di fatti applicativi già legittimi **non equivale** a importare fatti legacy. I binding, membership e mandati D77 non diventano importabili riclassificandoli come master; restore e onboarding owner/trusted con verifica offline e tracciamento restano distinti. Il tool non esegue né l'uno né l'altro.

## Dataset esplicitamente non reale

`scripts/r06_synthetic.py --seed 7` genera otto **probe offline**, quattro Service e quattro Part, in due tenant e quattro società sintetiche. Ogni coppia appartiene a un documento; pagante e intestatario sono distinti. Sono dimensioni di prova, **non il perimetro pilota approvato**. Tutti gli identificativi, incluso quello fiscale, iniziano con `SYNTH-INVALID-FOR-PRODUCTION-`; non sono UUID, CF o P.IVA validi. Seed limitato a intero unsigned32, nessun nome/indirizzo reale e nessuna lettura di dati esterni. Lo stesso seed produce gli stessi byte JSON canonici e SHA-256; seed diversi cambiano gli identificativi.

Le probe accostano snapshot commerciali e una coppia indipendente di quantità fisico/impegnato per chiave sorgente: **non sono righe runtime o un modello che assegna stock alle prestazioni**. Nessun saldo iniziale/zero stock, causale di ricevimento, import stock o policy di negativo è introdotto. Le quantità non realistiche servono a distinguere fisico e riservato anche al sesto decimale.

Aritmetica: contratti già documentati in [B05/D67](b05-verification.md), sezione «Artefatto attuale», e in `CommercialEndpoints.cs`/`EditorEndpoints.cs`: quantità/prezzo fino a sei decimali e relativo bound tecnico, sconto fino a due e [0,100], netto **per riga HALF_UP6**, somma netti per pagante/aliquota nello stesso documento, imposta **per gruppo HALF_UP6**, totale somma. Tutto `Decimal`, nessun float o arrotondamento monetario implicito a due. Normalizzazione delle rappresentazioni numeriche valide senza mutare gli input. Il solo profilo IVA sintetico supportato è 22%; non è un nuovo motore fiscale o una policy per altri trattamenti. I gruppi restano separati per tenant/società/documento.

Casi: imposta aggregata su due netti `0.000002` = `0.000001` (non zero per somma di imposte per riga); metà micro arrotondato per riga; quantità `2.123456`, prezzo `10.000001`, sconto `10.25`; riferimento tecnico 164.500000 / 36.190000 / 200.690000. Nessuna riduzione della precisione interna Billing/Accounting.

## Contratto del riconciliatore

`scripts/r06_reconcile.py SOURCE.json TARGET.json` accetta solo il formato `SYNTH_INVALID_FOR_PRODUCTION_V1`, campi esatti, ID sintetici, enum ammessi e decimali invarianti validi. Rifiuta dati reali/non marcati, JSON ambiguo con chiavi duplicate, file oltre 10 MB e oltre 10000 probe (limiti tecnici offline, non scala commerciale).

- `counts`: record sorgente/target e conteggi per kind; `matched` conta chiavi sorgente comuni non duplicate, **non** migrazioni riuscite o record privi di differenze;
- `missing`, `unexpected`: confronto delle chiavi sorgente, non solo dei conteggi;
- `duplicate`: chiave sorgente o identità interna ripetuta, su **entrambi** i lati; input duplicati identici restano errore;
- `provenance_mismatch`: source_id → internal_id cambiato/scambiato anche a conteggi e somme invariati;
- `amount_delta`, `physical_stock_delta`, `reserved_stock_delta`: differenze per probe, target meno sorgente, sei decimali; delta opposti non si annullano nascondendosi nel totale;
- `scope_mismatch`, `role_mismatch`, `field_mismatch`: tenant/società/sede/magazzino/scope esatto, pagante e intestatario indipendenti, altri riferimenti/valori preservati;
- `amount_groups`: basi/imposte/totali separati sorgente/target. Usa i netti forniti come snapshot; non li corregge ricalcolandoli dal catalogo o inventando un import;
- `ok`: solo contenuto equivalente normalizzato e assenza di duplicati. Exit **0** = confronto coerente, **1** = differenze, **2** = input/configurazione rifiutati (nessun contenuto input nei messaggi di errore).

Una seconda comparazione deterministica in memoria prova **solo lo strumento**: `OFFLINE_TOOL_ONLY_NOT_MIGRATION_IDEMPOTENCE`. Non è un secondo import, non dimostra idempotenza/concorrenza della migrazione né compatibilità Giobby. Nessuna risposta API, import riuscito o conferma ERP viene simulata come evidenza reale.

## Comandi ripetibili

Dalla root del repository; directory output scratch privata già esistente, mai un database:

```sh
python3 -I scripts/r06_inventory.py
python3 -I scripts/r06_synthetic.py --seed 7 --summary
python3 -I scripts/r06_synthetic.py --seed 7 > "$TMPDIR/r06-source.json"
python3 -I scripts/r06_reconcile.py "$TMPDIR/r06-source.json" "$TMPDIR/r06-source.json"
python3 -I scripts/test-r06-impact.py
python3 -I scripts/test-r06-inventory.py
python3 -I scripts/test-r06-reconcile.py
python3 scripts/test-c00-consistency.py
python3 scripts/test-productization-consistency.py
git diff --check
```

I test invocano davvero le CLI, mutano comparazioni e manifest copiati in scratch e verificano exit/report; nessuna scrittura SQL. RED→GREEN registrati per mapping prima del codice, copertura, enum/classificazione/sicurezza, generazione, Decimal, input, matching, popolazioni/duplicati, provenienza, tre delta separati, scope, ruoli, CLI e normalizzazione. Evidenze locali e check exact-head sono riportati nella PR collegata all'issue #76 tramite il numero PR effettivamente creato; questo documento non anticipa uno SHA/test remoto futuro.

## CI, confini e rollback

Il selettore ha un allowlist finito dei nuovi file offline. Solo questi file più le modifiche mirate di wiring (selettore, workflow e guard changed-path R03.a) selezionano `affected-r06-offline` e le guardie leggere di impact, **non** API/UI, Docker, dispatch runtime o full architecture. Percorsi eseguibili sconosciuti falliscono chiuso. Modifiche miste/runtime mantengono le selezioni security/runtime esistenti; manifest/motore/registrazioni comandi sono anche dipendenze dirette dell'inventario e selezionano la sua guardia leggera. Il workflow esegue i tre test offline e ne verifica la presenza con mutation test. Trigger automatico solo PR; full architecture resta eccezione esplicita, nessun main-push automatico. Gli skip runtime non sono pass: qui non serve dispatch perché nessun runtime cambia.

R05 live resta bloccata dal contratto effettivo; **OPE01–OPE05 non superati**, nessuna readiness o go-live. Restano aperti strategia/mapping/eligibilità di migrazione legacy, identità e cardinalità pilota, stock iniziale, retention/off-host, provider identity/SdI, piano dei conti e validazioni oltre i casi approvati. I default proposti nell'handoff non sono decisioni. Autorità condivisa D26/D65/D76 unica tenant-wide e setup concreto prima dei writer dipendenti restano invariati, nessun profilo concreto scelto dal dataset.

Non eseguiti in questa consegna: import/export applicativo, restore, rehearsal cross-host, API/UI/DB/Docker, ERP live, benchmark, RPO/RTO o validazione fiscale generale. Bootstrap, Tailscale443→9119, volumi/backups/configurazioni e branch protetti non sono modificati. Non sono introdotte dipendenze; lockfile invariati. Rollback: revert tracciato dei soli strumenti/data/docs e wiring CI di questa PR, preservando cronologia. Nessun downgrade SQL, cancellazione di fatti o rollback/deployment runtime necessario. Parent #46 rimane aperta; merge/chiusura/completamento board spettano al parent orchestrator.

## Rehearsal di restore (R06.b.1)

Il runner effimero e il compose dedicato (`scripts/run-r06b1-tests.py`, `compose.r06b1-test.yaml`) scoprono le tabelle dal catalogo (nessun conteggio fisso) e le confrontano con questo inventario più il ledger; **non** approvano l'eleggibilità di alcuna tabella. Vedi [r06-restore-rehearsal.md](r06-restore-rehearsal.md).
