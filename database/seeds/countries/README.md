# Seed mondiale Nazioni

`../countries.sql` è il seed canonico delle **249 nazioni e territori ISO 3166-1 alpha-2** già ammessi da `backend/Modules/Geography/CountryCodes.cs` (`All`). L'insieme è stato confrontato esattamente con `/usr/share/iso-codes/json/iso_3166-1.json`; non si estende la whitelist applicativa o SQL.

## Provenienza e licenza

I nomi italiani sono i valori predefiniti, senza varianti `-alt-*`, di Unicode CLDR, snapshot `cldr-json` al commit **7d2b9cb11cec08f4d333ad73209deb3df0711c3b**:

`https://raw.githubusercontent.com/unicode-org/cldr-json/7d2b9cb11cec08f4d333ad73209deb3df0711c3b/cldr-json/cldr-localenames-full/main/it/territories.json`

- `cldr-territories-it.json`: copia sorgente integrale, immutabile, per verificare i nomi offline.
- `countries.json`: trasformazione selezionata per le sole 249 chiavi ISO esistenti, ordinata per `iso_code`, campi `name` e `iso_code`. Macroregioni, varianti, XK, AC, DG, EU e ZZ non entrano nel dataset.
- `sources.json`: provenienza, commit, trasformazione e autorità dei codici.
- `UNICODE-LICENSE.txt`: avviso upstream e licenza **Unicode-3.0**, da conservare con i dati derivati.
- `SHA256SUMS.json`: SHA-256 dei dati, sorgente, licenza, provenienza, generatore e SQL canonico. Il percorso `../countries.sql` nel manifest è relativo a questa directory.

## Riproduzione offline

Dalla root del repository, solo Python standard, nessuna rete o nuova dipendenza:

```sh
python3 database/seeds/countries/generate_sql.py
python3 database/seeds/countries/generate_sql.py --check
python3 database/seeds/countries/generate_sql.py --output /percorso/di/lavoro/countries.sql
```

Il generatore legge `countries.json`, verifica unicità e appartenenza alla whitelist C# esistente, ordina i codici e raddoppia gli apostrofi nei letterali SQL. Non accede al database. Lo snapshot CLDR archiviato e i test verificano la derivazione dei nomi.

## Integrazione e conservazione dei dati

`database/foundation.sql` include `\ir seeds/countries.sql` **dopo** gli include Business Partner, Payments, Catalog, TaxManagement e TaxManagement Classification, nella transazione esistente, immediatamente prima di `COMMIT`. Il loader stdin `database/sql_source.py` accetta solo questa sequenza canonica esatta e continua a rifiutare direttive arbitrarie o annidate. Le città non sono precaricate.

Lo statement è soltanto `INSERT INTO foundation.country (name, iso_code) ... ON CONFLICT (iso_code) DO NOTHING`: i record già presenti conservano integralmente ID, nome, note, stato e timestamp; non si eseguono aggiornamenti, riattivazioni o concessioni automatiche di permessi. I nuovi record usano i default della tabella. I trigger fiscali già presenti possono inizializzare i rispettivi riferimenti italiani quando viene inserita Italia; non sono aggiunti trigger o grant dal seed.

Il dataset storico `../italy/countries.json` resta una fixture **solo Italia** dell'importatore comuni, superata da questo seed per la copertura mondiale. Non vengono sostituiti né ricopiati i dati mondiali negli archivi, nelle licenze o nei checksum Garda/ISTAT.
