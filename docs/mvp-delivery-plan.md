# Piano corrente di consegna MVP — D96

Data: 2 novembre 2026. Stato: sviluppo autonomo autorizzato; MVP non ancora pronto all'utilizzo.

## Mandato attivo

D96 nella [carta](../PROJECT_CHARTER.md) autorizza riallineamento GitHub e istruzioni, implementazione autonoma dei sette domini, pulizia motivata, commit/PR/CI/merge e pubblicazione del software quando verificato. La [baseline](mvp-baseline.md) descrive i requisiti e la [valutazione dell'esistente](mvp-existing-code-assessment.md) distingue il riuso dalle lacune.

Questo piano e [mvp-backlog.json](mvp-backlog.json) sostituiscono come roadmap operativa P00/UI01/R00–R06. [Il piano precedente](productization-plan.md) e le sue prove sono archivio storico: non richiedono completamento Giobby o ciclo officina prima del nuovo MVP. La contabilità interna non viene dichiarata deprecata o eliminata.

## Sette capability necessarie

1. Identity federation, RBAC e autorizzazioni.
2. Tenant, società, sedi e magazzini.
3. Controparti e ruoli.
4. Cataloghi articoli e servizi.
5. Inventari: gestione continuativa delle quantità.
6. Tipologie documentali configurabili per società.
7. Documenti: testate, righe, sviluppo parziale e raggruppamento con provenienza quantitativa e residui per passaggio.

Next.js SSR/shadcn/ui è il frontend, ASP.NET Core il backend, PostgreSQL la persistenza. Il nuovo inventario è documentale e locale senza prerequisito ERP; nessuno switch implicito degli ambienti storici.

## Ordine di consegna

| ID | Risultato | Dipendenza |
| --- | --- | --- |
| MVP-00 | Riallineamento verificato di carta, agenti, backlog e GitHub | Nessuna |
| MVP-01 | Shell Next.js SSR/shadcn con percorso di verifica isolato | MVP-00 |
| MVP-02 | Accesso federato, SUPER ADMIN e amministrazione organizzativa reale | MVP-01 |
| MVP-03 | Deleghe separate: struttura organizzativa e gestione utenti/ruoli | MVP-02 |
| MVP-04 | Controparti e ruoli gestibili autonomamente | MVP-03 |
| MVP-05 | Articoli e servizi gestibili senza Workshop | MVP-04 |
| MVP-06 | Configurazione societaria delle tipologie documentali | MVP-05 |
| MVP-07 | Testate/righe/conferma e carico/scarico/trasferimento tracciati | MVP-06 |
| MVP-08 | Sviluppo parziale e raggruppamento multi-sorgente | MVP-07 |
| MVP-09 | Pulizia dei percorsi sostituiti e acceptance finale integrata | MVP-08 |
| MVP-10 | Release verificata e valutazione di utilizzabilità operativa | MVP-09 |

Gli ID sono risultati, non obblighi di una sola PR: suddividere in sottoincrementi testabili senza restringere silenziosamente la capability. WIP 1: una sola implementazione attiva, ricerche indipendenti in parallelo. Nessuna promessa di date. L'autorizzazione copre l'intera sequenza, senza approvazioni ordinarie ripetute; i dettagli di dominio realmente mancanti si chiudono nel relativo contratto.

## Regole del primo percorso amministrativo

Il SUPER ADMIN è Luigi Pelosi, non il primo utente che si autentica. Il bootstrap dell'autorità globale deve essere esplicito, verificabile e auditato; nessuna inferenza da email, registrazione o correlation token. Non pubblicare identità o credenziali personali nelle fixture.

Il contesto di destinazione è verificato per ogni operazione globale. La delega è attribuita dal SUPER ADMIN a un soggetto già anagrafato nel singolo tenant. Gestione struttura e invito/abilitazione/ruoli sono facoltà distinte; D97 approva anche creazione e modifica di ruoli e permessi con audit obbligatorio, non soltanto assegnazione di ruoli predefiniti. Nessuna estensione implicita ad altri tenant, control-plane o al ruolo SUPER ADMIN. Nessuna nomina di ulteriori amministratori o subdelega come effetto collaterale.

<!-- d97-current:start -->
D97: creare e modificare ruoli e permessi con audit immutabile e tracciabile obbligatorio, solo nel proprio tenant; gestione utenti distinta dalla delega organizzativa; nessun SUPER ADMIN, nessun potere cross-tenant o control-plane, nessuna subdelega o nomina implicita; non solo ruoli definiti dal proprietario; nessun runtime consegnato qui. [Decisione e contratto finito MVP03.b](mvp03b-user-administration.md), con interpretazione tecnica minima correggibile sulle azioni/scope eseguibili supportati, non un nuovo tetto ai ruoli.
<!-- d97-current:end -->

<!-- d98-current:start -->
D98: prima associazione binding + membership di un soggetto federato autenticato approvabile dal delegato alla gestione utenti solo nel proprio tenant; autenticazione e audit obbligatori; nessun ruolo o potere amministrativo automatico; nessun tetto owner-only; runtime D98 non consegnato. [Contratto finito MVP03.b.2](mvp03b2-user-onboarding.md).
<!-- d98-current:end -->

<!-- d99-current:start -->
D99: «Configurabile per società, con blocco predefinito». Nel nuovo inventario documentale MVP la società può consentire stock negativo soltanto mediante configurazione esplicita autorizzata, versionata e con audit immutabile; default blocca quantità insufficienti. Nessun grant amministrativo implicito, writer autonomo o switch dei profili ERP storici. La regola vale anche sulla gamba uscente dei trasferimenti (interpretazione tecnica minima correggibile); D34 sulle prenotazioni officina resta storico e non aveva risolto questa domanda.
<!-- d99-current:end -->

<!-- d100-current:start -->
D100: «La quantità viene prenotata alla conferma della bozza». La destinazione Draft salva allocazioni proposte, senza impegnare capacità sorgente né stock. L'impegno della capacità documentale avviene soltanto atomicamente con la conferma della destinazione, rileggendo tutti i residui riga/passaggio. Bozze concorrenti possono contendere: una conferma perdente riceve 409, resta Draft, senza riduzione silenziosa o effetto parziale. Non è una prenotazione fisica. Ogni precedente proposta di prenotazione al salvataggio è SUPERATA/non scelta.
<!-- d100-current:end -->

<!-- d101-current:start -->
D101: «Usare soltanto sorgenti confermate, anche di tipi diversi se tutti abilitati verso la destinazione». Ogni sorgente deve essere Confirmed immutabile e ogni percorso societario sorgente→destinazione deve essere correntemente abilitato. Tipi sorgente differenti sono ammessi, mai tenant/società differenti. D14/D17 restano: customizing solo societario, stessa sede per default, cross-site della stessa società solo esplicitamente abilitato per ciascun percorso coinvolto.
<!-- d101-current:end -->



MVP-03/#142 e #166 COMPLETATI: PR #167 merged il 4 novembre 2026, main `c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb`, candidate `0f9f7d167b68778ff36d21b7b8355fecf541c72f`, tree equivalente `56f47b1cee07fe227422d9f49a3bcd703b3adf5a`. Il coordinatore ha verificato PR CI `41752991377` e dispatch `41753044926`, step richiesti e sette ZIP exact-head; evidenze `/root/.hermes/evidence/enginia360-mvp03b2b/final`. Primo binding crea membership disabilitata: abilitazione successiva e ruoli restano espliciti. Nessun deployment/readiness operativo. Contratto storico MVP04: `docs/mvp04-counterparties-contract.md`. MVP-04/#143 COMPLETATO: PR #168, merge `03872078b2d77dcf6754700729e41fcf5567d051`, candidate `668440ae5154f076cdc308868a15846ab142095e`, tree equivalente `f7d9419348fc78463fe6e3bc5411a52d81beea8b`. Il coordinatore ha riletto CI `41780772823` (5 job/58 step), dispatch `41780819337` (14 job/130 step), otto ZIP exact-head/digest e 14 TRX non vuoti senza skip; issue #143 chiusa e Project Completato. MVP-05/#144 COMPLETATO: PR #169, merge `43a4ff836d67bf1b4f01eb27ccc318171ee45f8d`, candidate `b6a337d35826d23de2465f79e99bd4f6105da458`, tree equivalente `2d5c06ae8c83e744a88e20abdcc0c34f0066ad81`. Il coordinatore ha riletto PR CI `41833394752` (5 job/59 step), dispatch `41833450699` (15 job/139 step), nove ZIP con SHA256/head verificati, 20 TRX con 274 test eseguiti/passati e zero skip; issue #144 chiusa e Project Completato. Evidenze `/root/.hermes/evidence/enginia360-mvp05/final/merge-ready.json` e `/root/.hermes/evidence/enginia360-mvp05-parent/merge-readback.json`. Equivalenza tree, non nuova CI main. MVP-06/#145 COMPLETATO: PR #170, merge `6ca378d94435eb78ff4955128e3646cc64ef1ece`, candidate `149687265fb2f76550032333c660dca6f445d6b5`, tree equivalente `6e002f5cdce3769f8fedf1032b135f009ca33dd2`. Il coordinatore ha riletto PR CI `41881635998` (5 job/60 step), dispatch `41881398306` (16 job/148 step), 10 ZIP exact-head/SHA256 e 24 TRX con328 test eseguiti/passati, zero skip/fail. Issue #145 chiusa e Project Completato; equivalenza tree, non nuova CI main. MVP-07/#146 COMPLETATO: PR #171, main `7d505db049880ef6fc4a2307dcd4575165c08923`, candidate `09cc3b1acddfab31879b940339fcb5af31053991`, tree equivalente `5a58e881d71e5d4b12fdb42ea1829d49790b7e0e`. Il coordinatore ha riletto PR CI `41945630168` (5 job/61 step), dispatch `41945650853` (17 job/157 step), 11 ZIP exact-head/SHA256 e 28 TRX, 380 eseguiti/passati, zero skip; issue #146 chiusa, Project Completato. Equivalenza tree, non nuova CI main. Evidenze `/root/.hermes/evidence/enginia360-mvp07-parent/merge-readback.json`. MVP-08/#147 IN CORSO SOURCE-ONLY, UNVERIFIED; contratto `docs/mvp08-document-development-contract.md`. #148–#149 Backlog. Nessun deployment/readiness operativo. I riepiloghi D97/D98 sono storici dei gate documentali (runtimeDelivered=false solo del gate), non negano la consegna funzionale successiva.


Stato corrente: MVP-03/#142 e #166 COMPLETATI: PR #167 merged il 4 novembre 2026, main `c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb`, candidate `0f9f7d167b68778ff36d21b7b8355fecf541c72f`, tree equivalente `56f47b1cee07fe227422d9f49a3bcd703b3adf5a`. Il coordinatore ha verificato PR CI `41752991377` e dispatch `41753044926`, step richiesti e sette ZIP exact-head; evidenze `/root/.hermes/evidence/enginia360-mvp03b2b/final`. Primo binding crea membership disabilitata: abilitazione successiva e ruoli restano espliciti. Nessun deployment/readiness operativo. Contratto storico MVP04: `docs/mvp04-counterparties-contract.md`. MVP-04/#143 COMPLETATO: PR #168, merge `03872078b2d77dcf6754700729e41fcf5567d051`, candidate `668440ae5154f076cdc308868a15846ab142095e`, tree equivalente `f7d9419348fc78463fe6e3bc5411a52d81beea8b`. Il coordinatore ha riletto CI `41780772823` (5 job/58 step), dispatch `41780819337` (14 job/130 step), otto ZIP exact-head/digest e 14 TRX non vuoti senza skip; issue #143 chiusa e Project Completato. MVP-05/#144 COMPLETATO: PR #169, merge `43a4ff836d67bf1b4f01eb27ccc318171ee45f8d`, candidate `b6a337d35826d23de2465f79e99bd4f6105da458`, tree equivalente `2d5c06ae8c83e744a88e20abdcc0c34f0066ad81`. Il coordinatore ha riletto PR CI `41833394752` (5 job/59 step), dispatch `41833450699` (15 job/139 step), nove ZIP con SHA256/head verificati, 20 TRX con 274 test eseguiti/passati e zero skip; issue #144 chiusa e Project Completato. Evidenze `/root/.hermes/evidence/enginia360-mvp05/final/merge-ready.json` e `/root/.hermes/evidence/enginia360-mvp05-parent/merge-readback.json`. Equivalenza tree, non nuova CI main. MVP-06/#145 COMPLETATO: PR #170, merge `6ca378d94435eb78ff4955128e3646cc64ef1ece`, candidate `149687265fb2f76550032333c660dca6f445d6b5`, tree equivalente `6e002f5cdce3769f8fedf1032b135f009ca33dd2`. Il coordinatore ha riletto PR CI `41881635998` (5 job/60 step), dispatch `41881398306` (16 job/148 step), 10 ZIP exact-head/SHA256 e 24 TRX con328 test eseguiti/passati, zero skip/fail. Issue #145 chiusa e Project Completato; equivalenza tree, non nuova CI main. MVP-07/#146 COMPLETATO: PR #171, main `7d505db049880ef6fc4a2307dcd4575165c08923`, candidate `09cc3b1acddfab31879b940339fcb5af31053991`, tree equivalente `5a58e881d71e5d4b12fdb42ea1829d49790b7e0e`. Il coordinatore ha riletto PR CI `41945630168` (5 job/61 step), dispatch `41945650853` (17 job/157 step), 11 ZIP exact-head/SHA256 e 28 TRX, 380 eseguiti/passati, zero skip; issue #146 chiusa, Project Completato. Equivalenza tree, non nuova CI main. Evidenze `/root/.hermes/evidence/enginia360-mvp07-parent/merge-readback.json`. MVP-08/#147 IN CORSO SOURCE-ONLY, UNVERIFIED; contratto `docs/mvp08-document-development-contract.md`. #148–#149 Backlog. Nessun deployment/readiness operativo. I riepiloghi D97/D98 sono storici dei gate documentali (runtimeDelivered=false solo del gate), non negano la consegna funzionale successiva.

## Pulizia controllata

- Ripulire subito roadmap, stati attivi e istruzioni obsolete; mantenere cronologia ed evidenze con etichette storiche.
- Rimuovere UI/endpoint obsoleti solo dopo sostituzione, tracciamento degli utilizzi e verifiche pertinenti; non ricopiare tutto il vecchio frontend nel nuovo.
- Non cancellare interi moduli riusabili solo perché fuori MVP; togliere dal percorso attivo le dipendenze non necessarie, decidendo la rimozione per componente.
- Conservare migrazioni pubblicate, contratti/evidenze storici e rollback. Non riscrivere storia Git né eseguire prune Docker/volumi.
- Bootstrap, Tailscale 443 → localhost:9119, volumi, backup e configurazioni conservati restano protetti.

## Verifiche e consegna

Disposizione corrente del proprietario: unit test, test CI, pipeline, ogni validazione/testing e distribuzione avvengono a fine implementazione dei punti di sviluppo. La precedente sequenza test-first/RED → GREEN è superata ove incompatibile; le prove già raccolte restano evidenza storica.

Per ogni punto di sviluppo concordato: contratto finito → implementazione completa del punto → validazione finale locale d'impatto (unit/integration/security/runtime, build e audit pertinenti) → correzioni e ripetizione delle verifiche interessate se necessarie → commit/PR di consegna → CI exact-head → dispatch runtime mirato quando applicabile → merge controllato → equivalenza del tree o nuova prova mirata se il tree cambia → rilettura issue e Project → eventuale distribuzione soltanto se autorizzata. Non usare sotto-passi artificiali per anticipare campagne di validazione. Non aprire PR o eseguire pipeline durante l'implementazione; non disabilitare i controlli esistenti. Implementazione terminata non equivale a consegna verificata.

CI automatica solo pull_request; niente automatismi push main. Gli incrementi di routine usano full_architecture=false. Full architecture non è il default: una campagna finale esplicita dopo il completamento funzionale. Skip non è pass. Incrementi documentali usano guardie offline, non runtime storico indiscriminato. Test tenant/RLS/CSRF, autorizzazione, concorrenza, retry, audit, API/UI/build/dependency audit e health/smoke rimangono necessari secondo l'impatto.

## Pubblicazione e utilizzabilità

La release del software non coincide con un deployment o con l'accettazione operativa. MVP-10 deve distinguere artefatti verificati, readiness tecnica, target operativo e limiti residui.

Non presumere approvati dati reali, accesso pubblico, acquisti, nuovi ambienti persistenti o sostituzione dei servizi protetti. Prima di un uso operativo devono essere dimostrati identità/revoca, recupero/backup, privacy, manutenzione e gli altri gate applicabili; non dichiararli passati per il solo esito dei test sintetici. Se target o accesso non sono definiti, preparare il contratto operativo e chiedere solo quella decisione, senza fermare lo sviluppo isolato.

## Tracking GitHub

Riutilizzare il Project esistente, rinominandolo per il MVP e preservando gli item storici. Creare issue idempotenti con marker `enginia360-mvp:MVP-xx`; assegnare i nuovi item al backlog corrente. Gli item della vecchia roadmap ancora aperti vanno distinti come sostituiti, mai dichiarati completati. Il dettaglio storico rimane nei corpi/commenti e nella Git history. Numero issue e stato del Project sono sempre verificati con readback, non dedotti dal successo di una scrittura.

## Checkpoint corrente PR171 / MVP08 SOURCE-ONLY

MVP-03/#142 e #166 COMPLETATI: PR #167 merged il 4 novembre 2026, main `c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb`, candidate `0f9f7d167b68778ff36d21b7b8355fecf541c72f`, tree equivalente `56f47b1cee07fe227422d9f49a3bcd703b3adf5a`. Il coordinatore ha verificato PR CI `41752991377` e dispatch `41753044926`, step richiesti e sette ZIP exact-head; evidenze `/root/.hermes/evidence/enginia360-mvp03b2b/final`. Primo binding crea membership disabilitata: abilitazione successiva e ruoli restano espliciti. Nessun deployment/readiness operativo. Contratto storico MVP04: `docs/mvp04-counterparties-contract.md`. MVP-04/#143 COMPLETATO: PR #168, merge `03872078b2d77dcf6754700729e41fcf5567d051`, candidate `668440ae5154f076cdc308868a15846ab142095e`, tree equivalente `f7d9419348fc78463fe6e3bc5411a52d81beea8b`. Il coordinatore ha riletto CI `41780772823` (5 job/58 step), dispatch `41780819337` (14 job/130 step), otto ZIP exact-head/digest e 14 TRX non vuoti senza skip; issue #143 chiusa e Project Completato. MVP-05/#144 COMPLETATO: PR #169, merge `43a4ff836d67bf1b4f01eb27ccc318171ee45f8d`, candidate `b6a337d35826d23de2465f79e99bd4f6105da458`, tree equivalente `2d5c06ae8c83e744a88e20abdcc0c34f0066ad81`. Il coordinatore ha riletto PR CI `41833394752` (5 job/59 step), dispatch `41833450699` (15 job/139 step), nove ZIP con SHA256/head verificati, 20 TRX con 274 test eseguiti/passati e zero skip; issue #144 chiusa e Project Completato. Evidenze `/root/.hermes/evidence/enginia360-mvp05/final/merge-ready.json` e `/root/.hermes/evidence/enginia360-mvp05-parent/merge-readback.json`. Equivalenza tree, non nuova CI main. MVP-06/#145 COMPLETATO: PR #170, merge `6ca378d94435eb78ff4955128e3646cc64ef1ece`, candidate `149687265fb2f76550032333c660dca6f445d6b5`, tree equivalente `6e002f5cdce3769f8fedf1032b135f009ca33dd2`. Il coordinatore ha riletto PR CI `41881635998` (5 job/60 step), dispatch `41881398306` (16 job/148 step), 10 ZIP exact-head/SHA256 e 24 TRX con328 test eseguiti/passati, zero skip/fail. Issue #145 chiusa e Project Completato; equivalenza tree, non nuova CI main. MVP-07/#146 COMPLETATO: PR #171, main `7d505db049880ef6fc4a2307dcd4575165c08923`, candidate `09cc3b1acddfab31879b940339fcb5af31053991`, tree equivalente `5a58e881d71e5d4b12fdb42ea1829d49790b7e0e`. Il coordinatore ha riletto PR CI `41945630168` (5 job/61 step), dispatch `41945650853` (17 job/157 step), 11 ZIP exact-head/SHA256 e 28 TRX, 380 eseguiti/passati, zero skip; issue #146 chiusa, Project Completato. Equivalenza tree, non nuova CI main. Evidenze `/root/.hermes/evidence/enginia360-mvp07-parent/merge-readback.json`. MVP-08/#147 IN CORSO SOURCE-ONLY, UNVERIFIED; contratto `docs/mvp08-document-development-contract.md`. #148–#149 Backlog. Nessun deployment/readiness operativo. I riepiloghi D97/D98 sono storici dei gate documentali (runtimeDelivered=false solo del gate), non negano la consegna funzionale successiva.

### Checkpoint storico — 3 novembre 2026 (superato dal checkpoint PR167)

MVP-02/#141 completato dopo PR #157, main `095abca4656bffa626e259f7f4aa8237d6afdf26`, tree equivalente al candidato `53704fe326545be0ccd514f63bcd43671e8960b8`; PR CI `41585054855` e dispatch `41585054020` con artefatti verificati dal coordinatore. MVP-03/#142 e' In corso. [MVP03.a/#158](mvp03a-organization-delegation.md) e' consegnato via PR #159, main `097680690d479bbfbd498fa4fd3d6c4bd5a99db8`, candidato `cbf359c559fe8ff1cafdbd34ab4f2aa70933d5cd`, tree equivalente `54889c8a5563946082145ba383289c59f93ff7d4`; PR CI `41607621063` e dispatch `41607614693` verificati dal coordinatore. Aggiunge soltanto la delega organizzativa, non amministrazione utenti/ruoli. Il [checkpoint di esecuzione](mvp03a-progress.md) conserva le prove. Il parent #142 rimane aperto: [MVP03.b.1](mvp03b1-tenant-role-contract.md) è consegnato via PR #162 (main `4d3aeabe3d3d6fec3135ce31ad0e8da43cb54eea`, candidato `8c60f2f84cb075ffbb47c9c04c40b5bfe2fe01d7`, tree `2da30752115ca9460c0fa82cc8ef20ee7b2b1076`); PR CI `41638706451` e dispatch `41638698110` verificati dal coordinatore con artefatti, entrambi i pool e consumer reali. [D98/MVP03.b.2](mvp03b2-user-onboarding.md) chiude la policy per prima associazione federata approvata dal delegato utenti: invito/abilitazione ed enforcement trasversale restano runtime da eseguire. Nessuna readiness operativa implicita.

### Riorganizzazione storica riletta il 2 novembre 2026

Project privato esistente n. 3 rinominato **Enginia360 · MVP**, senza creare un Project duplicato. Create e rilette 11 issue #139–#149 per MVP-00–MVP-10; ogni item ha Backlog ID, ordine e stato verificati. MVP-00/#139 e' completato dopo PR #150 e CI `41536452707` (impact e guardie MVP offline, 32 step effettivi; tree `f583cb382ed78505cc727317129a98a0a3856e66`, evidenze verificate dal coordinatore). Checkpoint successivo: MVP-01/#140 completato (PR #151, head `e3102e41a34dddff63faf033b7c0c56935297635`; PR CI `41541966173`, dispatch `41541963004`, tree `1009876b5368aa30fa6ace3d20c1e226e57abbf2`, verificati dal coordinatore). MVP-02/#141 e' In corso; MVP-03–MVP-10 restano Backlog. I 66 item precedenti sono archiviati reversibilmente nel Project, non cancellati; le issue conservano storia e discussioni. Le sei vecchie capability #5/#42/#43/#44/#45/#46 sono state chiuse come sostituite (`not_planned`), non completate, dopo il merge verificato del riallineamento. #37 resta aperta e differita: nessuna archiviazione fisica di storage e' stata eseguita.

Il checkpoint MVP-01 introduce soltanto la [shell tecnica verificabile](mvp01-frontend.md) in `frontend/`; non anticipa identity federation o capability operative. MVP-01 e' consegnato; MVP-02.a/#152 e' consegnato via PR #153, main `185682700d621edcb547d0291167aec248c50bfe` (tree equivalente al candidato `a38a4274df901454b59892bc133f91c6a12d2df4`); PR CI `41553422654` e dispatch `41553418829` verificati dal coordinatore. [Autorita globale esplicita](mvp02a-platform-authority.md), bootstrap/revoca owner-offline e readout minimo non sono organizzazione CRUD o frontend autenticato. MVP-02.b/#154 e' consegnato via PR #155, main `1913c7393362d30193e79ebd7cc1f1a5f521f218` (tree `f4fbe62f00c59b427c57b6b00b88b371c6c37129` identico al candidato `a7c018e5eadfbef7653ea66ba0840c653605bbbc`); PR CI `41564892938` e dispatch `41564891812` verificati dal coordinatore. Il sottoincremento attivo MVP-02.c/#156 definisce il [percorso Next autenticato](mvp02c-authenticated-organization.md) sulle API di [amministrazione organizzativa persistita](mvp02b-organization-administration.md); parent #141 resta aperto e In corso fino alla verifica completa della UI autenticata. Issue/Project e merge restano gestiti dal coordinatore. Il nuovo percorso CI per frontend e' esplicito, isolato dal runtime ERP storico e usa `full_architecture=false`.

Correzione tecnica di esecuzione: il vecchio gh CLI non accettava il valore numerico zero per Ordine; e' stato usato ordinamento 1–11, mantenendo invariati gli ID MVP-00–MVP-10. La creazione issue e' stata ripresa tramite marker, senza duplicazioni. Nessuna di queste operazioni dimostra una capability applicativa completata.

### Stato storico dopo PR165 — superato da PR167

MVP03.b.2a/#164 consegnato da PR #165, main
`c2e94d7a91b5e641aaf1a169e878795b8612d071`, tree
`90c21640f0657f60850527a6e7355b81697de346` equivalente al candidate
`e044acbea33156ebde868cfc7385f035c6ca2d43`.
Il coordinatore ha riletto PR CI `41731554031` (7job/69step), dispatch
`41731544819` (30job/279step), step richiesti e sei artefatti: prove di #164,
non una nuova esecuzione #166. [Ledger storico](mvp03b2a-final-validation.md).
#164 chiusa; #142 resta aperta. #166 è il punto corrente: [primo ingresso
federato/invito minimo/approvazione atomica](mvp03b2b-federated-onboarding.md),
sorgente completa e prove locali finali eseguite. Consegna NON VERIFICATA sino a
CI exact-head e chiusura del coordinatore; nessun deployment.
runtimeDelivered dell'intero MVP03.b resta false fino alla chiusura finale di #166.
