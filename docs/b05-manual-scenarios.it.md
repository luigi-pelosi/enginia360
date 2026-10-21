# Prova privata B05 — guida del proprietario

> **STORICO — ambiente rimosso.** Il runtime privato descritto sotto non è in esecuzione e l'URL citato non è un endpoint attivo. Il documento resta come evidenza/runbook; non ripristinare o creare un ambiente persistente senza nuova autorizzazione. Il bootstrap e Tailscale 443 → 9119 restano invariati.

**Consegna B05 — 19 ottobre 2026:** accettazione manuale positiva del proprietario «Ok funziona tutto. Procediamo»; review core e quattro artefatti manuali acquisite, discrepanza documentale risolta. Autorizzata la sola consegna Git/PR/CI/merge/chiusura B05, non nuovi deploy o B06. Stato al congelamento: In verifica; esito finale remoto nella PR e issue #11. Limiti e perimetro nel report B05. Le indicazioni precedenti di accettazione/review pendenti sono storiche e superate da questa registrazione. B06–B14 restano bloccati/Backlog e non autorizzati.

URL: https://vmi3659251.tailfcced0.ts.net:8446/ (solo dispositivi autorizzati nella tailnet; HTTPS verificato). Ambiente persistente sintetico separato da B02/B03/B04. Non inserire dati personali o reali. Non è produzione, fatturazione o validazione fiscale generale.

## Accesso e apertura

Credenziali di fixture, non segreti del database:

- Alfa: `operatore-alfa-sintetico` / `synthetic-alpha-password`.
- Beta: `operatore-beta-sintetico` / `synthetic-beta-password`.
- Senza membership: `operatore-senza-membership` / `synthetic-no-membership`.
- Alfa senza lettura: `operatore-alfa-senza-lettura` / `synthetic-no-read`.

Accedere con Alfa; scegliere **Alfa Società Uno · Alfa Sede Nord**. Selezionare soggetto a carico pagante sintetico, veicolo e tipo commessa abilitato. Verificare che cambiando veicolo il pagante scelto rimanga selezionato: intestatario e pagante sono distinti. Aprire la commessa; annotare il suo identificativo. Il catalogo ha Manodopera meccanica e Filtro olio; l'identità di catalogo è del tenant, l'autorizzazione operativa resta della società/sede.

## Caso 001 esatto

Inserire i valori con punto decimale, non virgola:

| Riga | Quantità | Prezzo unitario | Sconto % | Netto salvato EUR |
|---|---:|---:|---:|---:|
| Prestazione | 1.50 | 55.00 | 10 | 74.250000 |
| Ricambio | 1 | 95.00 | 5 | 90.250000 |

Aggiungere prima la prestazione, poi il ricambio. Attesi: imponibile **164.500000**, imposta aggregata **36.190000**, totale **200.690000 EUR**. Non 200.700000: non arrotondare singolarmente le imposte ai centesimi. Una riga per tipo, un gruppo di lavoro, un solo soggetto a carico. Nessuna prenotazione/scarico magazzino, fattura o contabilità.

## Esempio variabile

Aprire una nuova commessa. Prestazione: quantità `2.123456`, prezzo `10.000001`, sconto `10.25`. Netto **19.058020**, imposta **4.192764**, totale **23.250784 EUR**. Quantità e prezzo accettano fino a sei decimali; sconto fino a due, fra 0 e 100; quantità positiva e prezzo non negativo, entrambi inferiori a 1000000. Numeri in notazione scientifica e virgole non sono ammessi.

## Mezzo micro e imposta di gruppo

Nuova commessa: per entrambe le righe quantità `1.000000`, prezzo `0.000001`, sconto `50.00`. Ogni netto esatto 0.0000005 diventa **0.000001** con HALF_UP a sei decimali; gruppo netto **0.000002**, imposta **0.000000**, totale **0.000002**.

Altra commessa, entrambe le righe quantità `1`, prezzo `0.000002`, sconto `0`: netto **0.000004**, imposta di gruppo **0.000001**, totale **0.000005**. L'imposta non viene arrotondata riga per riga. Attesi verificati con Python Decimal indipendente e API persistente.

## Rilettura, limiti e permessi

Premere **Rileggi valori salvati**: il risultato deve essere quello salvato dal server, a sei decimali, non un totale locale della GUI. In caso di errore rileggere prima di ripetere; il retry della medesima richiesta non duplica la riga. Una seconda riga dello stesso tipo non è consentita. Non alterare catalogo/configurazioni/permessi per provare lo storico in questo ambiente.

Un refresh completo perde sessione e selezione locale: non esiste ancora una lista/navigazione storico né un campo GUI per riaprire una commessa per ID. I dati restano nel database e sono rileggibili via API autorizzata; non confondere questo limite GUI con perdita dati. Le righe conservano snapshot di catalogo/configurazione; mutazioni di master e rollback sono verifiche della suite isolata, non della prova persistente.

Beta non deve leggere commesse Alfa. Senza membership l'accesso operativo è negato. Creazione/aggiunta non implicano lettura: ogni azione richiede permesso esatto e ambito società/sede; Alfa senza lettura non può usare il flusso completo. Il tenant non è un campo modificabile fidato del client. I dinieghi API sono verificati automaticamente, non tutti hanno un controllo dedicato nella GUI.

Annotare ID, valori, eventuale messaggio/correlation ID e risultato della prova. Restano necessari accettazione manuale del proprietario e review indipendente della configurazione manuale prima della consegna Git.
