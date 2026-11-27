# Dati iniziali italiani

Snapshot Garda Informatica del **6 novembre 2026**, confrontato con l'elenco ISTAT e il raccordo territoriale della Sardegna scaricati il 18 novembre 2026.

- Una nazione nella fixture storica: **Italia**, ISO 3166-1 alpha-2 **IT**. Per il seed mondiale canonico questa fixture è **superata** da `../countries.sql` e dal dataset `../countries/countries.json` (249 nazioni/territori ISO, nomi italiani CLDR). Le nuove installazioni lo caricano già da `database/foundation.sql`; questa fixture resta invariata per l'importatore dei comuni italiani, senza duplicare il dataset mondiale negli archivi o checksum Garda/ISTAT.
- **7.894 comuni** identificati dal codice ISTAT: copertura esattamente coincidente con l'elenco ufficiale archiviato.
- **8.458 coppie comune/CAP**: 43 comuni hanno più CAP; non si riducono a un CAP arbitrario e non si generano codici espandendo intervalli.
- CAP sempre stringhe di cinque cifre, inclusi gli zeri iniziali; nessun CAP nullo o `00000`.
- `province` contiene la **sigla automobilistica ISTAT**, coerente con il formato dell'anagrafica richiesta; `region` la denominazione regionale. Sono risolte tramite ISTAT le 24 sigle obsolete Garda relative al Sulcis Iglesiente. Le denominazioni estese delle province restano disponibili nei dati sorgente.

## File e provenienza

`cities.json` è il payload iniziale dell'importatore; `countries.json` descrive Italia. `garda.zip` e `istat-comuni.xlsx` sono gli originali; `istat-rows.json` è la lettura tabellare dell'XLSX usata per il confronto. `sources.json` riporta URL, date e impronte degli scaricamenti. `SHA256SUMS.json` protegge i file distribuiti.

`result.json` e `validation-details.json` conservano il rapporto **originale** della verifica sorgenti, precedente alla conversione delle province da nomi estesi a sigle. Il rapporto descrive anche l'anomalia poi risolta delle sigle sarde. Per il payload effettivo usare `import-validation.json`: copertura e CAP rimangono invariati.

## Licenze

- **Garda Informatica, MIT**: conservare `GARDA-NOTICE.txt` e `LICENSE-MIT.txt` insieme ai dati. Fonte: https://www.gardainformatica.it/database-comuni-italiani
- **Istat, CC BY 4.0**: sigle provinciali e verifica territoriale. Fonte: https://www.istat.it/classificazione/codici-dei-comuni-delle-province-e-delle-regioni/ — condizioni archiviate in `ISTAT-LICENSE.html`, https://www.istat.it/en/legal-notice/ e https://creativecommons.org/licenses/by/4.0/
- Trasformazioni: filtro sui codici comunali correnti ISTAT, un record per comune/CAP effettivamente pubblicato da Garda, sigla provinciale ISTAT, mantenimento degli zeri iniziali. Nessun CAP inventato o modificato; nessuna affiliazione o certificazione dei fornitori è implicita.

## Limiti documentati

La copertura comunale è verificata con ISTAT; **ISTAT non certifica i CAP**. I CAP sono trascritti dal dataset Garda, non confrontati integralmente con un archivio ufficiale Poste. Il controllo non costituisce una certificazione postale.

Sovizzo è conservato perché corrente nell'elenco ufficiale, nonostante un flag contraddittorio nella tabella storica Garda. La denominazione più recente «Vallecrosia al mare» proviene dal dataset e dal sito comunale. Castegnero Nanto conserva i CAP presenti nella fonte, incluso quello transitorio; non si deducono autonomamente scadenze dalle indicazioni comunali discordanti.

## Riproduzione e manutenzione

Da questa directory:

```sh
python3 prepare_dataset.py --output /percorso/di/lavoro/cities.json
```

Il comando lavora offline sugli archivi, verifica la coincidenza con il payload distribuito e non accede al database. L'importazione applicativa è esplicita, transazionale e idempotente. Non è una sincronizzazione periodica: dopo il caricamento iniziale Nazioni e Città vengono mantenute manualmente dal Super Admin. Le modifiche manuali non devono essere sovrascritte ripetendo l'importazione.
