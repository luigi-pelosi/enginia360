# Valutazione dell'esistente rispetto al nuovo MVP

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
