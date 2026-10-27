# R06.b.2 — registro evidenze e runbook di recupero limitato

Refs #82, parent #46 **aperta**. Artefatto offline documentale/eseguibile, non completamento R06, procedura di produzione approvata o autorizzazione al pilota. Fonte dei gate: [costi e operazioni §7, D57](foundation/12-costs-and-operations.md); definizioni originali riprodotte senza riduzione in [r06-readiness-registry.json](r06-readiness-registry.json).

<!-- r06b2-summary:start -->
**Readiness attuale R06.b.2:** OPE01=OPEN; OPE02=OPEN; OPE03=OPEN; OPE04=OPEN; OPE05=OPEN; #46 OPEN; R06 NON COMPLETA; nessuna readiness operativa.
<!-- r06b2-summary:end -->

## 1. Contratto del registro (nessuna nuova approvazione)

Il JSON distingue `requirements` (testo OPE01–OPE05 identico alla fonte), `gates` (stato operativo), `evidence` (fatti tecnici sintetici verificati), `approvals` (vuoto) e `summary` (derivata dagli stati). `target`/`scope` null e `proof_ids`/`approval_ids` vuoti significano **mancanza di prova operativa**, non approvazione condizionata. Le relazioni conoscitive sono: R06.a.1 → inventario/riconciliazione futura R06.a; R06.b.1 → prerequisito tecnico OPE02/OPE03/OPE05, **non** loro soddisfacimento. Non mettere questi link nei `proof_ids`.

Il validatore stdlib `scripts/r06_readiness.py` restituisce **0 = registro coerente**, **2 = rifiutato**, mai «pilota pronto». Rifiuta ID mancanti/duplicati/sconosciuti, JSON ambiguo/oltre 1 MiB/campi estranei, approvazioni auto-dichiarate, riferimenti sconosciuti e riepiloghi attivi obsoleti. Non legge rete, DB, segreti o dati aziendali. Nessuna dipendenza nuova.

Per `SATISFIED` occorrono tutte le categorie tipizzate sotto, prova `target_specific` verificata su **stesso target e scope**, artefatto con URL e SHA-256, e decisione esplicita del proprietario che riferisce esattamente ID e digest delle prove. Un generico `reviewer/date/evidence_id` non basta. Il catalogo fidato di prove e approvazioni operative nel codice è **vuoto**: aggiungere una riga JSON o un URL non crea fiducia. Il futuro aggiornamento richiede acquisizione/verifica dei documenti originali, scope e competenze pertinenti, revisione tracciata del catalogo e nuova CI, non una scelta dell'agente. Una validazione fiscale/legale richiede lo specialista pertinente, non il solo owner né il successo del validatore.

`VALIDATION_ONLY` esiste solo per la fixture approvata **fittizia** dei test, con target/scope `VALIDATION-ONLY-*` e provenienza `example.invalid`; verifica la forma completa e le sue mutazioni. Non è un'approvazione acquisita, non è ammessa nel registro reale (guardia della CLI predefinita/test), non muta gate/board e l'output dichiara esplicitamente lo scopo. Un digest conferma coerenza dei byte, non autenticità o competenza del firmatario. Il validatore offline controlla il **readback storico fissato**, non interroga lo stato live di #46; eventuali nuove decisioni richiedono una revisione, mai un pass automatico.

| Gate OPEN | Categorie minime tipizzate del validatore | Decisione residua / prima di |
| --- | --- | --- |
| OPE01 | `name_extension_registrar`, `initial_renewal_tax_extras`, `purchase_authorization`, `dns_control` | Proprietario: eventuale nome/registrar, costi iniziali/rinnovi/IVA-extra e autorizzazione prima dell'acquisto; controllo DNS prima dell'accesso pubblico via dominio. Nessun acquisto imposto per prova locale o canale privato Tailscale. |
| OPE02 | `implementation_scope`, `identity_resources_transport`, `protocols_mfa`, `revocation_recovery`, `identity_maintenance` | Responsabile tecnico/proprietario: adozione e configurazione target, risorse, MFA/federazione, revoca/recupero e manutenzione. Le prove B01/R00 sintetiche non adottano un IdP di produzione; nessun login reale sul bootstrap HTTP anonimo. |
| OPE03 | `destination_quotas`, `encryption_key_recovery`, `daily_checkpoint_transfer`, `retention_failure_monitoring`, `offhost_failure_independence`, `end_to_end_restore` | Proprietario assegna controllo backup e decide risorsa D48, quote, chiavi, retention, checkpoint/trasferimento, guasti e scenario; prova end-to-end target prima dello stato persistente pertinente/pilota, senza spacciare la consegna tecnica B14 per chiusura OPE03. |
| OPE04 | `coverage_timezone_holidays`, `rto_boundaries`, `smtp_received`, `backup_patch_identity_roles` | Proprietario assegna ruoli residui, fuso/festività/fine fascia, estremi misura RTO e verifica ricezione allarme SMTP prima della messa in servizio. D50 non assegna patch/backup/IdP implicitamente. |
| OPE05 | `target_country_contracts`, `data_destinations`, `actual_costs_quotas_capacity`, `recovery_resources_tests` | Proprietario con provider/competenze pertinenti: target UE effettivo e destinazioni dati/contratti, costi/quote/capacità e recupero prima del pilota; D54 non deroga al charter. |

Le categorie sono indicizzazione tecnica delle condizioni D57, non nuovi valori di retention, periodicità, provider, importi, SLA o politica legale. Eventuale non-applicabilità contestuale (es. nessun acquisto/dominio pubblico) richiede decisione esplicita motivata nello scope; non è un bypass automatico per soddisfare l'intero gate.

## 2. Evidenze tecniche storiche verificate e limiti

Il JSON contiene gli URL reali di PR/commit/run, head, merge e tree, gli eventi e **solo** i job effettivamente conclusi `success`. Il guard li confronta con fatti immutabili fissati nel codice, non con se stesso. I job skipped non sono pass; tree identico non è una nuova esecuzione CI.

- **R06.a.1, PR #77:** head `03bed79af6ffd9a6495c09dbeaafc1ae185a9a9c`, merge `fe6ea5c1403056b4069f57ecd8050cb7f65c80a9`, tree `d03cf6b58ef951d5f80fc00cbdfa8a8c504cc4b7`; CI `40075451477`, impact + affected-r06-offline. Fonte di consegna: #46 commento `6381666054`. Inventario di quel commit: 22 migrazioni/63 CREATE. Stato dell'inventario corrente: dinamico, 23 migrazioni/64 CREATE nel baseline PR #81; il DB del rehearsal include anche il ledger (65 tabelle). Matching in memoria **non** prova import/export applicativo o idempotenza di import.
- **R06.b.1, PR #81:** head `da332f36985b37bd0d5396e214815e2f8bdcd792`, merge `1761688f4710c373179f5d6087999d13744a3f26`, tree `bc7b9d606e51cd54f9af810b34a4300c96922dab`; PR CI `40099590231` (4 job), dispatch `40099603224` (8 job, `full_architecture=false`, compresi restore e tre passi TERM realmente eseguiti). Fonte: #46 commento `6385112475`. Dump custom hash/TOC, A distrutto/B fresco, marker prima/dopo dump, tutti i conteggi/hash e ledger/catalogo confrontati, no-op due volte, browser OIDC pool4/pool1, failure scratch/forward-fix, cleanup guardato.

Il secondo fatto è **single-host sintetico**: IdP sopravvive alla perdita del cluster DB; INSERT dispatcher temporaneamente negato solo su B effimero prima del readback, ACL esatta ripristinata dopo lo stop. Nessuna esenzione di tabella/colonna dai digest, CHECK ri-analizzati dallo stesso PostgreSQL senza stripping. Non prova recupero con dispatcher normalmente attivo, off-host, perdita IdP/chiavi, PITR, RPO/RTO/SLA, validità fiscale o cleanup dopo SIGKILL dell'orchestratore. Il guard rifiuta esplicitamente queste promozioni e coppie commit/CI non corrispondenti. Archivio e fixture non sono artefatti da pubblicare; niente dump, credenziali, PII o chiavi nel registro/log di consegna.

## 3. Rehearsal opt-in corrente (non avviato da R06.b.2)

Prerequisiti: checkout verificato, Docker e immagini pinned già previste, spazio scratch privato fuori repository, nessun dato reale. La build dell'editor è separata. Dalla root, **non** sul progetto bootstrap:

```sh
(cd web && npm ci && npm run build:ui01-runtime)
TMPDIR="$HOME/.hermes/cache/scratch" timeout 600 python3 scripts/run-r06b1-tests.py
TMPDIR="$HOME/.hermes/cache/scratch" timeout 420 python3 scripts/test-r06b1-lifecycle.py --actual dump
TMPDIR="$HOME/.hermes/cache/scratch" timeout 420 python3 scripts/test-r06b1-lifecycle.py --actual restore
TMPDIR="$HOME/.hermes/cache/scratch" timeout 420 python3 scripts/test-r06b1-lifecycle.py --actual browser
```

Comandi verificati leggendo `run-r06b1-tests.py`/`test-r06b1-lifecycle.py` e il wiring CI; gli esiti di esecuzione citati sono quelli **storici** sopra, non nuove prove di questa PR. Il runner non accetta un target del chiamante: genera `enginia360-r00b-<12 hex>`, compose esatto `compose.r06b1-test.yaml`, PGDATA tmpfs, nessuna porta host/volume, nonroot/read-only, rete interna, risorse bounded. `TMPDIR/r06b1-evidence/report.json` è output locale 0600; dump/segreti restano nello scratch temporaneo e vengono eliminati. Conservare solo rapporto minimizzato e metadati necessari, non esfiltrare contenuti. Non esiste uno scheduler di backup di produzione creato automaticamente da questi comandi.

### Diagnosi e classe di fallimento

| Classe / segnale | Verifica e azione limitata |
| --- | --- |
| Prerequisito/build/timeout prima del punto probe | Distinguere mancata build/dist, risorse o immagine da fallimento di integrità; conservare exit e fase. Timeout/interruzione non sono pass. Nessun retry che nasconda il primo esito. |
| Migrazione/manifest/checksum/prefisso ledger | Arrestare il candidato; confrontare manifest esatto e ledger `id/checksum/applied_at`. Non riscrivere migrazioni pubblicate, checksum o ledger per renderli verdi. Vedi §4. |
| Dump/TOC/hash/marker | Rifiutare archivio vuoto/corrotto/troncato o senza tabella attesa; non riparare il dump. Il marker post-dump **deve mancare** nel restore, quello pre-dump deve esserci. |
| Restore non vuoto/ruoli/ACL/catalogo/dati | Rifiutare target non vuoto; usare solo B fresco generato dal runner. Nessun `--clean`, `--no-owner`, `--no-acl` o eccezione ai digest per superare il confronto. |
| HTTP/OIDC/RLS/receipts/pool/dispatcher | Separare DB caricato da servizio usabile; verificare autorizzazione, scope, reset contesto e ricevute identiche. L'IdP non è stato ripristinato; non estendere il risultato a IdP DR. Non allargare il gate INSERT scratch al prodotto. |
| TERM/cleanup o inventario protetto divergente | Fallire la prova e fermare nuovi avvii. Confrontare ID/StartedAt/RestartCount bootstrap, tutti i container e i 25 volumi; mai compensare differenze cancellando risorse non riconosciute. |

### Cleanup esatto effimero

Percorso normale/fallimento/TERM: `finally` del runner ignora nuovi segnali durante cleanup, termina e attende **solo** i propri child (kill bounded solo dei child non terminati), poi `r00.cleanup(command, project)` con CONFIG riassegnato al compose R06.b.1. La helper rifiuta project fuori regex e label/config non corrispondenti; unpause dei soli container riconosciuti, rimozione dei soli ID etichettati, `down --volumes --remove-orphans` **solo per il progetto casuale e il compose esatto**, poi inventario container/network/volume del medesimo project vuoto. Non usare quel suffisso su bootstrap, né prune, wildcard o down globale.

Dopo **SIGKILL dell'intero orchestratore** non c'è garanzia di cleanup: non rilanciare alla cieca. Un operatore autorizzato deve prima identificare dalla precedente esecuzione il project casuale e la directory scratch/`runtime.env`, accertare che runner/child non siano più attivi, leggere `docker inspect` degli ID esatti, verificare label project + `com.docker.compose.project.config_files` assoluto, nonroot/read-only/no host port/no volume con `assert_exact_targets(..., protected_ids=...)`, e confrontare l'inventario protetto salvato. Solo con tali corrispondenze invocare la stessa helper `r00.cleanup` con il vettore originale `['docker','compose','--env-file', str(state/'runtime.env'),'-p',project,'-f',str(CONFIG)]`. La helper è coperta dai test offline `test-r06b1-lifecycle.py`; non è un nuovo comando di restore produzione. Se envfile/label/provenienza/inventario mancano, **stop e intervento tracciato**, non bypassare le guardie e non indovinare target. Verificare infine assenza dei soli oggetti esatti e integrità degli oggetti protetti; gestire separatamente eventuale scratch segreto residuo dopo averne provato l'ownership, senza comandi di cancellazione generica.

## 4. Tre operazioni diverse, mai un downgrade silenzioso

1. **Rollback del codice/documenti:** PR di revert tracciata della revisione errata, con verifica delle dipendenze e CI sul nuovo head. Non fa tornare indietro dati/schema e non autorizza un deployment. Per questo incremento basta revert di registry/guard/docs/wiring; nessun SQL/deployment modificato.
2. **Fallimento migrazione e forward-fix:** il motore transazionale annulla l'unità fallita, conserva il prefisso ledger pubblicato e rilascia lock; sentinella successiva non deve eseguire. Una correzione futura è **nuova unità append-only**, dopo diagnosi e test. Il rehearsal usa esclusivamente manifest scratch con copie read-only/hash dei file pubblicati invariati; la migrazione fallita mai applicata non è un fatto pubblicato da riscrivere. Id/checksum/applied_at del prefisso, ordine e lock vanno controllati prima e dopo; drift resta errore, non si «riallinea» il ledger.
3. **Restore dei dati:** perde quanto confermato dopo il checkpoint dell'archivio (marker post-dump assente apposta). Non è un revert del codice o prova di idempotenza d'import. Prima di un eventuale incarico reale occorrono decisione esplicita sul punto/perdita accettata e autorizzazione/scope, copia integra hash/TOC, chiavi/ruoli/config protetti, target fresco, compatibilità applicazione-schema e ledger dell'archivio uguale al prefisso pubblicato atteso. Dopo: confronto integrale dati/catalogo/ACL/RLS/ledger e verifiche servizio usabile. Il rehearsal applica `pg_restore --exit-on-error --single-transaction`, rifiuta B non vuoto e confronta il migratore no-op due volte. Nessun comando distruttivo di produzione è fornito o autorizzato.

Fatti fiscali/contabili/stock confermati e audit non si correggono cancellando righe o riscrivendo lo storico: correzioni tracciate/compensazioni del modulo proprietario, D37/D40/D67 e charter §9; nessun restore come bypass dell'immutabilità o cambio retroattivo di autorità D26/D65/D76. Il modulo interno Billing/Accounting resta preservato.

## 5. Responsabilità, obiettivi e decisioni finite aperte

**Già confermato (non chiedere di nuovo):** D47 VPS nel budget, importo non comunicato/nessuna nuova macchina approvata; D48 proprietario fornirà risorse esterne di backup, non già accessibili né compute failover; D49 RPO «fino al giorno precedente», RTO massimo **1 ora** nella fase iniziale, obiettivi non SLA. Non convertire RPO in 24 ore mobili, non misurare RTO dalla sola presa in carico o dal solo pg_restore. Includere rilevazione, risposta, disponibilità/reprovision nodo, chiavi/config, trasferimento, DB e servizio utilizzabile. Guasto DB e perdita VPS sono scenari distinti; nessun tempo provider già dimostrato.

D50 Luigi Pelosi riceve allarmi e gestisce interventi di ripristino iniziali. D51 **lunedì–sabato 09:00–18:00**, non 24/7 né domenica; fuso/festività/fine fascia aperti, nessuna sospensione implicita del cronometro RTO. D52 sola e-mail; D53 SMTP disponibile candidato, non consegna verificata o servizio identity approvato. D54 Germania dichiarata per VPS attuale, non target pilota vincolato o verifica contrattuale; requisito UE invariato. D55 Keycloak candidato prova, non adozione definitiva; D56 disponibilità a valutare dominio, non ordine né necessità per canale privato. D57 mantiene OPE01–OPE05. D77 primo binding/membership/mandato owner/trusted offline verificato e tracciato, nessun provisioning/self-grant/subdelega/default-first-user.

| Blocco finito | Chi deve decidere/produrre evidenza (non assegnazione inventata) | Esito richiesto; fatto già noto separato |
| --- | --- | --- |
| OPE01 / costo accesso | Proprietario; registrar/provider solo se scelti | Scelta eventuale nome/costi/rinnovi/IVA-extra e autorizzazione, controllo DNS se pubblico. Tailscale privato 443 → localhost:9119 preservato, non endpoint pubblico né acquisto obbligatorio. |
| OPE02 / D77 | Proprietario + referente tecnico da confermare | Target IdP/adozione, manutenzione/recupero/chiavi, binding e identità pilota verificati nello scope. Policy D77 già confermata, identità reali non create qui. |
| OPE03 / D48–D49 | Proprietario assegna operatore controllo backup; risorsa/provider da identificare | Destinazione indipendente/paese/quote, chiavi e recupero, checkpoint/trasferimento, retention e guasti, prova end-to-end sul target. Non scegliere valori/proprietario di servizio mancanti. |
| OPE04 / D50–D53 | Proprietario assegna ruoli residui; referente SMTP quando noto | Fuso/festività/escalation/fine fascia e assenza copertura, inizio/fine RTO, invio protetto e ricezione, controllo backup/patch host-container/IdP. D50 non assegna automaticamente queste funzioni né sostituto. |
| OPE05 / D54 | Proprietario + provider/competenze protezione dati pertinenti | Target UE e destinazioni dati/contratti/costi/quote/capacità/recupero verificati; totale ancora indeterminato, AWS/HA solo futuro, nessun acquisto. |
| R04 #44 / D82 | Provider ERP + proprietario/referente per evidenze di integrazione, non nuova domanda sulla parzialità | Stesso ERP autorevole per stock e catena acquisti nel pilota; proiezione/integrazione ERP supportata da evidenze provider necessaria. R04.b ERP BLOCKED: contratto ufficiale assente su stock/ordine/ricevimento, effetti/esiti/idempotenza/lookup da provare; nessuna risposta stock/ordine/ricevimento inventata o carico locale sostitutivo. Ricevimento parziale 3 ordinati / 2 ricevuti già approvato e condizionato all’autorità. D80/D81 consegnate nei limiti locali sintetici, prove non ritirate né riassegnate al pilota ERP; carcassa distinta, ulteriori varianti separate. |
| R05 #45 | Provider Giobby e proprietario | D79 «bozza fattura vendita» superata da D85 come artefatto; D87: ordine cliente accettato come documento del pilota, riserva stock senza scarico, rilascio/annullo riserva e conversione ordine→fattura non provati; D86 residuo ricevimento non autorevole; schema/effetti, business ACK distinto da trasporto, idempotenza e lookup dopo timeout da provare. Nessuna chiamata o risposta inventata compatibile. |
| R06.a / #46 | Proprietario sul perimetro dati; implementazione successiva autorizzata solo nei confini | D87: migrazione legacy fuori perimetro per ora (scoping, non divieto né approvazione); R06.a completa per i soli strumenti sintetici consegnati. Eleggibilità/storico/stock iniziale/topologia pilota restano non decisi. Vero roundtrip import/export via comandi, mapping/reconciliation e replay senza duplicati ancora da costruire: matching offline e restore non lo provano. |
| Fiscalità/contabilità | Proprietario con commercialista/specialisti competenti | Validazione dei casi/supporto oltre D42/D44/D45 e configurazioni/piano conti pertinenti, SdI/conservazione se in scope separato. Nessuna validità generale, retention legale o provider scelti dall'agente. |

Questa è la lista finita dei residui per la consegna; non un questionario da ripetere né un blocco allo sviluppo indipendente. Decisioni ad alto impatto non ricevute restano **BLOCKED/OPEN**, senza default dall'handoff. #43/#44/#45/#5/#46 non vengono chiuse da questo artefatto.

## 6. Verifica offline e consegna

```sh
python3 -I scripts/r06_readiness.py
python3 -I scripts/test-r06b2-impact.py
python3 -I scripts/test-r06-readiness.py
python3 -I scripts/test-r06-impact.py
python3 -I scripts/test-r06-inventory.py
python3 -I scripts/test-r06-reconcile.py
python3 scripts/test-c00-consistency.py
python3 scripts/test-productization-consistency.py
git diff --check
```

Le mutazioni chiamano davvero la CLI con registro valido (exit 0) e ogni input negativo (exit 2 controllato), più guardia documentale su copie scratch: unknown/duplicate/missing OPE, soddisfatto senza prove/approvazione, categorie/target/scope/digest/provenienza incoerenti, sintetico promosso a offhost/IdP DR/RPO, commit/tree/CI non corrispondenti e summary passato con gate aperti. La fixture approvata completa dimostra solo validazione, non passa il registro operativo.

CI automatico **solo PR**: `impact` e `affected-r06-offline`, con nuovi test/CLI integrati nel job leggero esistente. Percorsi eseguibili non mappati falliscono chiuso; cambi runtime misti mantengono selezioni security/runtime. Questa PR non richiede Docker/API/UI/build runtime/audit nuovi (nessun runtime o dipendenza cambia), dispatch o full architecture. Le prove storiche non vengono rieseguite né rinominate. Head/tree/PR/run di questa consegna saranno nei thread/report solo dopo esecuzione; non anticipare SHA futuro nel JSON. Parent mantiene merge/chiusure/Completato; rollback tracciato dei soli artefatti/wiring. Nessun go-live, dato reale, acquisto, ambiente persistente, deployment, import SDK o chiamata esterna.
