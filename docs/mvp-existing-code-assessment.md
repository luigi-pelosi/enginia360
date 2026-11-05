# Valutazione dell'esistente rispetto al nuovo MVP

Checkpoint storico precedente a PR172 (5 novembre 2026): valutazione originale conservata come storica. MVP07/#146 COMPLETATO via PR171, main `7d505db049880ef6fc4a2307dcd4575165c08923`, candidate `09cc3b1acddfab31879b940339fcb5af31053991`, tree equivalente `5a58e881d71e5d4b12fdb42ea1829d49790b7e0e`. Il coordinatore ha riletto CI `41945630168` (5 job/61 step) e dispatch `41945650853` (17 job/157 step), 11 ZIP head/SHA256 e 28 TRX, 380 eseguiti/passati, zero skip; issue146 chiusa/Project Completato. Non nuova CI main. Evidence `/root/.hermes/evidence/enginia360-mvp07-parent/merge-readback.json`. MVP08/#147 attivo SOURCE-ONLY/UNVERIFIED; #148/149 Backlog. Nessun deployment/readiness operativo.

## Stato corrente — precedenti verificati e acceptance integrata in preparazione

<!-- mvp09-current:start -->
**Stato corrente: MVP00–08 completati; MVP-09/#148 IN CORSO, SOURCE_COMPLETE_UNVERIFIED; MVP-10/#149 Backlog.** [Contratto finito MVP09](mvp09-integrated-acceptance-contract.md). Implementazione e acceptance preparata non sono runtime verificato. Un solo punto intero; nessuna validazione durante la fase source-only. D96 autorizza ora una sola campagna finale eccezionale `full_architecture=true` dopo completamento funzionale e sorgente, mai CI automatica ordinaria; routine PR-only/dispatch mirato `full_architecture=false`, skip non è pass.

MVP-08/#147 COMPLETATO: PR #172, merge `b00fdbafd3f91f6526caf18e75b79476ab02660f`, candidate `4169bb7ac66a841b69527bf61bd55846c6943fa2`, tree equivalente `487afd38009d71fc51185681a9ae5521a2c86d37`. Readback indipendente del parent: PR CI `42060851414` 5 job/62 step; dispatch `42060851802` 18 job/166 step; 12 ZIP fresh exact-head/SHA256, 32 TRX non vuoti, 420 eseguiti/passati, zero runtime skip. Equivalenza tree, NON nuova CI main. Ledger finale `/root/.hermes/evidence/enginia360-mvp08/final/merge-ready.json`, SHA256 `6b6bce96aa38a315848c1e6e90469503b4f18230f8f1e81656512aaf20a592a8`; readback `/root/.hermes/evidence/enginia360-mvp08-parent/merge-readback.json` e `tracking-readback.json` (#147 chiusa/Completato, #148 aperta/In corso, #149 aperta/Backlog, #37 aperta). Tutte le 46 migrazioni ora pubblicate sono immutabili. SHA256 dei readback esterni: merge `2e85e11ee4e15d9c27ad4b01c09816db0a8571a843a7b70d8ea2aaed0318afa6`, tracking `ba1c09cca4ee595bdd9e3823cb276bb94ccd1ffb0134dfe2ba667ba5190ca63d`.

D97/D98 runtimefalse nei blocchi decisionali indica soltanto i gate documentali storici, non la consegna funzionale successiva. Nessun deployment/readiness operativo; provider reale, target/accesso, recupero/RPO/RTO, privacy e manutenzione restano gate di MVP10. Cronologia e incidenti NONPASS conservati in [archivio dei checkpoint](archive/mvp08-checkpoints.md).
<!-- mvp09-current:end -->

<details><summary>Prove storiche dei predecessori (non stato corrente)</summary>

MVP-03/#142 e #166 COMPLETATI: PR #167 merged il 4 novembre 2026, main `c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb`, candidate `0f9f7d167b68778ff36d21b7b8355fecf541c72f`, tree equivalente `56f47b1cee07fe227422d9f49a3bcd703b3adf5a`. Il coordinatore ha verificato PR CI `41752991377` e dispatch `41753044926`, step richiesti e sette ZIP exact-head; evidenze `/root/.hermes/evidence/enginia360-mvp03b2b/final`. Primo binding crea membership disabilitata: abilitazione successiva e ruoli restano espliciti. Nessun deployment/readiness operativo. MVP-04/#143 COMPLETATO: PR #168, merge `03872078b2d77dcf6754700729e41fcf5567d051`, candidate `668440ae5154f076cdc308868a15846ab142095e`, tree equivalente `f7d9419348fc78463fe6e3bc5411a52d81beea8b`. Il coordinatore ha riletto CI `41780772823` (5 job/58 step), dispatch `41780819337` (14 job/130 step), otto ZIP exact-head/digest e 14 TRX non vuoti senza skip; issue #143 chiusa e Project Completato. MVP-05/#144 COMPLETATO: PR #169, merge `43a4ff836d67bf1b4f01eb27ccc318171ee45f8d`, candidate `b6a337d35826d23de2465f79e99bd4f6105da458`, tree equivalente `2d5c06ae8c83e744a88e20abdcc0c34f0066ad81`. Il coordinatore ha riletto PR CI `41833394752` (5 job/59 step), dispatch `41833450699` (15 job/139 step), nove ZIP con SHA256/head verificati, 20 TRX con 274 test eseguiti/passati e zero skip; issue #144 chiusa e Project Completato. Evidenze `/root/.hermes/evidence/enginia360-mvp05/final/merge-ready.json` e `/root/.hermes/evidence/enginia360-mvp05-parent/merge-readback.json`. Equivalenza tree, non nuova CI main. MVP-06/#145 COMPLETATO: PR #170, merge `6ca378d94435eb78ff4955128e3646cc64ef1ece`, candidate `149687265fb2f76550032333c660dca6f445d6b5`, tree equivalente `6e002f5cdce3769f8fedf1032b135f009ca33dd2`. PR CI `41881635998` (5 job/60 step), dispatch `41881398306` (16 job/148 step),10 ZIP e24 TRX328 test passati zero skip/fail verificati dal coordinatore; issue145 chiusa/Project Completato. Equivalenza tree, non nuova CI main. 

</details>

## Valutazione storica originale — non stato corrente

Data: 2 novembre 2026. Baseline codice: `34bbbb0816a63f8f62a7f81a176bc282ee297eca` (main). Carta e baseline MVP sono modifiche documentali locali non ancora pubblicate.

Riferimento: [baseline funzionale MVP](mvp-baseline.md). Stato: valutazione e raccomandazioni, non autorizzazione alla riscrittura o prova di completamento. Nessun codice applicativo modificato, nessun database/provider contattato, nessun deployment effettuato.

## 1. Conclusione

Il codice è orientato a una vertical slice officina e alle sue estensioni, non ai sette domini gestionali autonomi ora richiesti. Il nuovo MVP richiede una ricostruzione funzionale significativa, soprattutto amministrazione, frontend, documenti ed effetti inventariali. Non emerge però una ragione per cancellare indiscriminatamente tutte le fondamenta.

Raccomandazione: nuova composizione MVP, mantenendo o adattando solo componenti verificati coerenti; nuovi percorsi amministrativi e documentali espliciti. Non rinominare Workshop in Documents e non obbligare il catalogo o l'inventario a dipendere dall'officina. Conservare baseline e storia Git; non eliminare ambienti, dati o migrazioni storiche.

## 2. Matrice dei sette domini

| Dominio | Esistente osservato | Gap rispetto all'MVP | Raccomandazione |
| --- | --- | --- | --- |
| Identità, RBAC e autorizzazioni | OIDC code/PKCE, binding issuer/subject, sessione browser, verifiche permessi e concessioni operative limitate. | Nessuna autorità piattaforma SUPER ADMIN individuata; gestione utenti e ruoli amministrabili e due deleghe distinte non realizzate dal mandato attuale. Risoluzione identità legata a un solo tenant. | Mantenere/adattare autenticazione e controlli; riprogettare il contratto di amministrazione e la risoluzione attore/tenant destinatario. |
| Tenant e organizzazione | Entità tenant/società/sede/magazzino, gerarchia e lettura dei propri contesti. | Manca il percorso applicativo di creazione e gestione della struttura da SUPER ADMIN/delegato. Le note organizzative non costituiscono gestione della struttura. | Conservare principi di gerarchia e isolamento; implementare amministrazione reale con API e UI. |
| Controparti e ruoli | Ricerca, dettaglio, modifica comune revisionata, ruolo fornitore, destinazioni ed estensioni societarie. | Registrazione route senza creazione della controparte né gestione generale dei ruoli; editor corrente legato al pagante della commessa. Campi e ruoli minimi ancora da definire. | Adattare il modulo, non riscriverlo integralmente; costruire gestione autonoma autorizzata. |
| Cataloghi articoli/servizi | Identità tenant-wide con Kind, etichetta e versione; selettore officina e prezzi acquisto societari. | Nessun comando gestionale nel contratto del selettore; registrazione e consultazione dipendono dall'officina. Prezzi acquisto non equivalgono a gestione del catalogo. | Conservare la separazione identità/dati societari; disaccoppiare e realizzare la gestione autonoma. |
| Inventari | Stock per tenant/società/sede/magazzino/articolo, quantità a sei decimali, prenotazioni e consumi specialistici. | Il decremento fisico deriva dall'installazione officina, non da una conferma documentale generale. Non individuato un percorso uniforme carico/scarico/trasferimento collegato a documento e riga. | Riutilizzare selettivamente precisione, isolamento e disciplina concorrenza; costruire il percorso documentale inventariale MVP. |
| Tipologie di documento | Configurazioni societarie versionate già presenti in Workshop e Billing. | Tipologie specialistiche consultabili, non configurazione gestionale MVP dei quattro effetti sulle quantità. | Conservare principio e scope della configurazione; realizzare il contratto e la gestione delle tipologie MVP, senza sommare flag specialistici. |
| Documenti, sviluppo e raggruppamento | Testata/righe commessa, revisioni e ricevute comando; fatture tecniche e ricevimenti specialistici. | Commessa richiede veicolo/intestatario; gruppi di lavorazione non sono raggruppamento documentale. Non individuato sviluppo generale multi-sorgente con provenienze quantitative e residui per passaggio. | Nuovo modello documentale minimo indipendente dall'officina; riuso dei pattern verificabili, non degli aggregati specialistici come modello universale. |

“Mantenere” è una raccomandazione di riuso, non certificazione runtime o adozione immutata dello schema. L'assenza indicata è limitata al perimetro di sorgenti e registrazioni esaminato.

## 3. Evidenze primarie

### Identità e organizzazione

- `src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs:35`: ticket store locale e protezione dati effimera; non prova continuità delle sessioni dopo riavvio.
- `src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs:56`: rivalutazione del binding della sessione.
- `src/Enginia360.Api/BrowserAuthentication/BrowserSessionModule.cs:84`: OIDC, code flow, PKCE e validazione token.
- `src/Enginia360.Api/OrganizationAccess/OrganizationAccessDbContext.cs:21`: gerarchia organizzativa; a riga 70 unicità globale di IdentitySubject sulla membership.
- `src/Enginia360.Api/OrganizationAccess/OrganizationAccessModule.cs:114`: registrazione route per grant, contesti e note; a riga 255 risoluzione di un solo tenant dalla membership.
- `web/src/ui01/runtime/OwnContexts.tsx:7`: lettura dei propri contesti, non gestione organizzativa.

### Controparti e catalogo

- `src/Modules/Counterparties/Enginia360.Counterparties/CounterpartiesModule.cs:24`: route di consultazione, modifiche comuni/fornitore e destinazioni; nessuna creazione della controparte nella registrazione esaminata.
- `src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs:10`: registrazione WorkshopCatalog; a riga 33 lista tenant-wide, a riga 45 Find carica la lista prima di filtrare.
- `src/Enginia360.Api/Program.cs:20`: registrazione Catalog all'interno di Workshop; a riga 29 Inventory richiede Workshop; a riga 154 anche i listini Catalog sono mappati sotto Workshop.
- `web/src/ui01/runtime/WorkshopRuntime.tsx:54`: workspace corrente centrato sulla commessa; a riga 61 editor anagrafico collegato al pagante.

### Inventari e documenti

- `database/runtime/migrations/0007_inventory.sql:3`: stock organizzativamente separato, numeric(12,6) e RLS; il vincolo Physical >= 0 è comportamento esistente, non nuova policy MVP approvata.
- `src/Modules/Inventory/Enginia360.Inventory/InstallationStockEffects.cs:31`: consumo derivato dall'installazione; a riga 76 aggiornamento della quantità fisica.
- `src/Modules/Workshop/Enginia360.Workshop/WorkshopDbContext.cs:52`: configurazioni societarie; a riga 57 testata con veicolo e intestatario obbligatori; a riga 92 WorkingGroup interno alla commessa.
- `src/Modules/Billing/Enginia360.Billing/BillingDbContext.cs:28`: tipologie Billing specialistiche; a riga 47 fattura con riferimento a un solo ordine.
- `database/runtime/migrations/0033_receipt_intents.sql:87`: precedente specialistico di collegamento receipt/sorgente e gestione quantità; non modello generale multi-sorgente.

Le prove storiche conservano il proprio significato. Il nuovo MVP non autorizza automaticamente cambio di autorità dei profili storici, fiscalità implicita o migrazione dei dati.

## 4. Frontend: ricostruire le superfici gestionali

`web/package.json:7` usa Vite; a riga 15 dipende da Ant Design. `web/src/main.tsx:1` avvia React nel browser. Non è il frontend Next.js SSR/shadcn confermato.

Raccomandazione: nuova shell gestionale e pagine MVP in Next.js/shadcn, riusando ove coerenti contratti, validazioni e casi di errore. Non trasportare per default le schermate Bxx, gli UUID manuali e la navigazione centrata sull'officina. Definire trasporto della sessione, CSRF e isolamento delle cache SSR prima del collegamento autenticato.

## 5. Verifiche realmente eseguite

### Test UI selezionati: PASS, non end-to-end

Il Node host `v18.19.1` non avvia il Vitest installato: manca l'export `node:util.styleText`. Il test è stato rieseguito con l'immagine locale pin `node:24.22.0-alpine3.24`, container effimero senza rete, utente nonroot, filesystem e sorgenti read-only, capacità rimosse e cache in tmpfs `/scratch`.

Comando completo ripetibile per i due file gestionali selezionati:

```sh
docker run --rm --network none --user 65534:65534 --read-only \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 \
  --memory 1g --cpus 2 --log-opt max-size=1m --log-opt max-file=1 \
  --mount type=bind,src=/root/enginia360/web,dst=/workspace,readonly \
  --tmpfs /scratch:rw,nosuid,nodev,size=128m,mode=1777 \
  -e TMPDIR=/scratch -e HOME=/scratch -w /workspace --entrypoint node \
  node:24.22.0-alpine3.24 node_modules/vitest/vitest.mjs run \
  src/ui01/runtime/MasterAuthority.test.tsx \
  src/ui01/runtime/SupplierPurchasePrices.test.tsx \
  --configLoader runner --cache=false --fsModuleCachePath=/scratch/vitest --maxWorkers=1
```

Esito: due file, 11 test passati (5 MasterAuthority, 6 SupplierPurchasePrices). Con la stessa esecuzione isolata, selezionando `src/App.test.tsx`, sono passati i 5 test bootstrap. Totale UI selezionato: 16 test su 3 file. Questi test usano risposte mockate: non provano API/DB, SSR o nuovi scenari MVP.

Due tentativi container iniziali erano falliti prima dei test perché la cache filesystem cercava una directory read-only; `--cache=false` da solo non bastava. Il comando finale indirizza esplicitamente `--fsModuleCachePath` alla tmpfs.

### Altre verifiche

- `web/node_modules/.bin/tsc --noEmit -p web/tsconfig.json`: exit 0, typecheck del frontend esistente.
- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/test-r01b-grants.py OwnerInputTests -v`: PASS, 1 test di validazione input del precedente mandato, non nuovo provisioning.
- `dotnet` non è disponibile sul PATH host; le suite C# non sono state eseguite in questa valutazione. Non è dimostrata l'impossibilità di eseguirle in un incremento dedicato: un'immagine SDK locale esiste, ma non è stata utilizzata qui.
- Nessuna esecuzione API/DB, federazione reale, browser end-to-end, Compose acceptance, build Next.js o CI remota. Non sono risultati necessari per una valutazione statica e non sono dichiarati passati.

## 6. Decisione proposta e prossimo contratto

Una riscrittura totale non è giustificata dalle prove raccolte; una sola revisione grafica non è sufficiente. Proporre una ricostruzione mirata del prodotto, con riuso selettivo delle fondamenta.

Prima del codice:

1. Riallineare AGENTS.md e il piano operativo alla nuova baseline, preservando le protezioni di ambienti, segreti e consegna; Giobby/officina non restano prerequisiti dell'MVP.
2. Approvare un contratto finito del primo percorso: accesso SUPER ADMIN → creazione tenant → società/sede/magazzino → delega organizzativa a soggetto già anagrafato → operazione autorizzata e rifiuto cross-tenant. Specificare bootstrap del SUPER ADMIN e perimetro delle deleghe senza autoassegnazione o aggiramento RLS.
3. Fissare il confine sessione Next.js/ASP.NET e le dipendenze pin; sviluppare quel percorso con un test eseguibile fallente prima del codice.

La presente valutazione conclude la ricognizione richiesta. Non introduce un nuovo motore generico, un secondo prodotto permanente, una migrazione applicativa o l'obbligo di completare l'ERP.
