# B04 — prova manuale privata

> **STORICO — ambiente rimosso.** Il runtime privato descritto sotto non è in esecuzione e l'URL citato non è un endpoint attivo. Il documento resta come evidenza/runbook; non ripristinare o creare un ambiente persistente senza nuova autorizzazione. Il bootstrap e Tailscale 443 → 9119 restano invariati.

URL: https://vmi3659251.tailfcced0.ts.net:8445/ — collegarsi alla tailnet con Tailscale. Le porte 8443 e 8444 sono ambienti precedenti: non usarle per questa prova. Nessun dato reale/personale/fiscale.

## Account sacrificabili delle fixture

Solo credenziali sintetiche già versionate; nessuna password del database.

| Utente | Password sintetica | Risultato |
| --- | --- | --- |
| operatore-alfa-sintetico | synthetic-alpha-password | Commessa società A, sedi autorizzate; nessuna gestione società B |
| operatore-beta-sintetico | synthetic-beta-password | Solo tenant Beta, società C |
| operatore-alfa-senza-lettura | synthetic-no-read | Nessun contesto officina autorizzato |
| operatore-senza-membership | synthetic-no-membership | Nessun contesto officina autorizzato |

A e B sono società dello stesso tenant Alfa; Beta è un tenant differente. Il veicolo Alfa è registrato presso B ma selezionabile in A senza concedere gestione B.

## Passi e risultati attesi

1. Aprire l'URL: titolo «Commessa diretta · prova privata B04». Password errata: messaggio di accesso non riuscito, nessuna commessa.
2. Accedere con Alfa e scegliere **Alfa Società Uno · Alfa Sede Nord**. Si mostrano una società e una sola sede di testata, non un magazzino. Nessun appuntamento/preventivo è richiesto.
3. Aprire **Tipo commessa**: scegliere «Commessa diretta sintetica · versione 1». «Commessa non diretta sintetica» deve essere disabilitata. La configurazione appartiene alla società, non è un tipo universale modificabile dalla schermata.
4. Selezionare **Soggetto a carico**, quindi **Veicolo sintetico altra società**. Il pagante deve restare selezionato e non essere sostituito dall'intestatario. Senza tutti i campi non si apre la commessa.
5. Premere **Apri commessa**. Attendere «Commessa · ordine cliente»: annotare l'identificativo. Pagante termina `0001`, intestatario `0002`, configurazione versione 1. È già un ordine cliente, senza righe, prezzi o fiscalità. Il salvataggio effettua anche una rilettura dal server.
6. Ripremere senza cambiare campi: stesso identificativo, nessun doppione. Per una nuova prova distinta ricaricare e accedere di nuovo. Se appare «Commessa non confermata», riprovare senza cambiare campi per recuperare lo stesso tentativo; dopo cambi di configurazione riselezionare il contesto.
7. Selezionare nuovamente un contesto: pagante, veicolo, tipo e risultato precedente si azzerano. Non deve sopravvivere una selezione del contesto precedente.
8. **Ricaricare la pagina**: si torna al login perché il token è solo in memoria. La commessa nel database NON viene cancellata; questa UI non offre elenco storico né ricerca per UUID. Non aspettarsi che il riquadro ricompaia automaticamente. Per rilettura tecnica usare il probe autorizzato descritto nelle operazioni, senza token negli URL/chat. Un nuovo login e nuovo invio dopo reload genera un nuovo comando, non il retry di quello precedente.
9. Ricaricare e accedere come Beta: solo società C e veicolo Beta; nessun contesto Alfa. Con ciascuno degli ultimi due account: «Nessun contesto officina autorizzato» e nessuna apertura possibile.
10. Le prove tecniche HTTPS verificano anche UUID di altro tenant/inesistenti, società/sede non autorizzate, configurazione disabilitata/errata, permessi insufficienti, spoofing e letture alternate: rifiuto senza rivelare la commessa altrui. Non modificare SQL/permessi per riprodurle sul persistente.

## Verbale e limiti

Riportare per punto superato/non superato, azione, errore visibile e UUID sintetico; mai token o segreti. L'agente ha verificato login/creazione/rilettura via HTTPS e DOM React con HTTP reale. Il browser ha renderizzato il login HTTPS; nessuna sessione browser autenticata è dichiarata.

Ambiente sintetico persistente su singolo host, non produzione. Keycloak reimporta fixture dopo riavvio; nessun backup/ripristino, IAM produttivo, audit durevole, RPO/RTO o fiscalità validati. Nessun B05. Resta necessaria l'accettazione manuale umana B04 e la review indipendente delle nuove operazioni prima di qualsiasi commit/push/merge.
