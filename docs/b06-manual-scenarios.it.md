# Prova privata B06 — guida del proprietario

> **STORICO — ambiente rimosso.** Il runtime privato descritto sotto non è in esecuzione e l'URL citato non è un endpoint attivo. Il documento resta come evidenza/runbook; non ripristinare o creare un ambiente persistente senza nuova autorizzazione. Il bootstrap e Tailscale 443 → 9119 restano invariati.

**Esito corrente:** il proprietario ha risposto «Funziona. Procediamo»: accettazione manuale positiva e consegna Git/PR/CI/merge autorizzata per la sola B06. Review indipendenti core/lifecycle e artefatti manuali PASS comunicate dal parent. I riferimenti sotto ad accettazione/review pendenti sono storici della preparazione. Non è una nuova prova browser autenticata dell’agente; limiti UI e perimetro D69 restano quelli descritti. Non ripetere il caso assumendo disponibilità iniziale ancora 2 dopo le scritture del proprietario; nessun reset autorizzato. B07–B14 restano bloccati.

19 ottobre 2026. Ambiente preparato e verificato tecnicamente; accettazione manuale e review indipendente degli artefatti manuali ancora pendenti. Nessun commit, push o merge autorizzato da questa preparazione. B07 e successivi invariati.

URL: https://vmi3659251.tailfcced0.ts.net:8447/ — solo dispositivi autorizzati nella tailnet, HTTPS verificato, nessun Funnel. Non inserire dati reali o personali. L'intestazione della pagina riporta ancora «B05» e «caso 001»: è un limite di etichettatura noto del candidato, non il perimetro effettivo. La sezione «Prenotazione ricambio» sulla riga Ricambio è B06.

## 1. Accesso e nuova commessa

Solo account di fixture, NON credenziali del database:

- Alfa: `operatore-alfa-sintetico` / `synthetic-alpha-password`.
- Beta: `operatore-beta-sintetico` / `synthetic-beta-password`.
- Senza membership: `operatore-senza-membership` / `synthetic-no-membership`.
- Alfa senza lettura: `operatore-alfa-senza-lettura` / `synthetic-no-read`.

Accedere con Alfa. Scegliere «Alfa Società Uno · Alfa Sede Nord», pagante sintetico, veicolo sintetico e tipo «Commessa diretta sintetica». Aprire una nuova commessa e annotarne l'ID. Intestatario del veicolo e pagante restano distinti. Aggiungere il Ricambio «Filtro olio», quantità `3`, prezzo `95`, sconto `5`. Si possono inserire valori commerciali variabili, non solo il caso 001. La prenotazione è disponibile solo per una riga Ricambio salvata, non per una Prestazione.

## 2. Insufficienza senza riduzione automatica

Nella sezione «Prenotazione ricambio», selezionare il magazzino originale «Alfa Nord Magazzino A» con ID finale `100101`, NON quelli con nome «B06 probe ...». Lo stock originale è stato lasciato intatto per la prova: fisico `2`, disponibile `2`, prenotato sulla nuova riga `0`, residuo `3`. Verificare questi valori prima di proseguire: la disponibilità è condivisa tra commesse, non si rigenera aprendo una nuova commessa.

Inserire quantità da prenotare `3`; premere «Prenota quantità esplicita». Atteso: «Disponibilità insufficiente. Nessuna prenotazione eseguita.». Premere «Rileggi prenotazioni»: fisico `2`, disponibile `2`, prenotato `0`, residuo `3`. Nessun autotrim a `2`, nessun blocco automatico della commessa.

## 3. Parziale esplicito 2 su 3

Sulla stessa riga e magazzino inserire `2`, poi «Prenota quantità esplicita». Atteso: fisico `2` invariato, disponibile `0`, prenotato sulla riga `2`, residuo `1`. Premere «Rileggi prenotazioni»: stessi valori salvati. La prenotazione non è un prelievo, consumo, scarico o rilascio.

Opzionale: sulla stessa riga scegliere «Alfa Nord Magazzino senza scope», ID finale `100102` (etichetta storica B02: in B06 l'account Alfa ha ora i permessi esatti; non confondere il nome con i grant effettivi), inizialmente fisico/disponibile `2`. Prenotare esplicitamente `1`: prenotato globale riga `3`, residuo `0`, fisico di B `2`, disponibile di B `1`. Un'ulteriore quantità positiva viene rifiutata per residuo superato. Il residuo è globale alla riga, non ricomincia cambiando magazzino. Non è stato aggiunto alcun endpoint di rifornimento; non chiedere reset di stock per ripetere i casi.

## 4. Quantità, retry e rilettura

Quantità positiva, punto decimale, massimo sei decimali; niente virgole, esponenti, zero o valori negativi. Esempio valido `0.000001`, non `0.0000001`. Ogni richiesta è limitata sia dal residuo della riga sia dalla disponibilità del magazzino coerente con società/sede della testata e permessi esatti.

In caso di rete incerta, premere «Rileggi prenotazioni» prima di ripetere. Se il comando è ancora pendente, il retry identico riusa il suo ID e non duplica l'impegno. Dopo conferma e rilettura, un nuovo clic è un NUOVO parziale: non usarlo per simulare lo stesso retry già confermato. Il probe API ha verificato identico retry 200 senza duplicazione e conflitto a payload modificato. Non è una promessa di recovery della sessione dopo refresh.

## 5. Persistenza, accessi e limiti

Non fare refresh completo durante la prova: sessione, commessa e selezione locali si perdono. Non esiste ancora lista storico né campo GUI per riaprire una commessa per ID. I dati restano nel database e sono leggibili via API autorizzata: questo limite GUI NON è perdita dati. La persistenza è stata provata ricreando soltanto PostgreSQL B06 e rileggendo identici ordine, riga/snapshot, prenotazione e totali stock.

Beta non può leggere dati Alfa; senza membership e Alfa senza lettura non possono completare il flusso. Lettura e creazione Inventory richiedono permessi separati sull'esatto magazzino. I test API hanno provato read-only, create-only e diniego dei dettagli storici non autorizzati. Non cambiare capability, permessi o master per provare lo storico qui; quei casi distruttivi restano nella suite isolata.

I magazzini «B06 probe ...» sono fixture tecniche dedicate, già utilizzate dai probe: non selezionarli per la prova guidata. Nessuna cancellazione, rilascio, annullamento, scadenza, prelievo, consumo, acquisto o ricevimento è implementato in B06. Il database B06 è separato da B02–B05. Identity sintetica H2 volatile: un riavvio identity reimporta gli account ma non conserva le sessioni. Nessuna garanzia produzione/backup, IAM definitivo, fiscale o contabile.

## 6. Esito da comunicare

Annotare ID commessa/riga, magazzino, quantità richiesta, fisico/disponibile/prenotato/residuo prima e dopo, messaggi o correlation ID. Confermare esplicitamente se insufficienza senza effetti, parziale 2/3, rilettura e limiti GUI sono accettati. La preparazione non equivale ad accettazione del proprietario. Login renderizzato in browser reale; nessuna sessione browser autenticata è stata eseguita dall'agente, poiché il Vault non aveva login salvati. I controlli autenticati dichiarati sono HTTP/API, non E2E browser.
