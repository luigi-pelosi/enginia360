# B03 — guida alla verifica manuale privata

> **STORICO — ambiente rimosso.** Il runtime privato descritto sotto non è in esecuzione e l'URL citato non è un endpoint attivo. Il documento resta come evidenza/runbook; non ripristinare o creare un ambiente persistente senza nuova autorizzazione. Il bootstrap e Tailscale 443 → 9119 restano invariati.

Aprire https://vmi3659251.tailfcced0.ts.net:8444/ con Tailscale connesso. Solo dati inventati, nessun dato personale o fiscale reale. La porta 8443 resta B02: non usarla per questa prova.

## Identità sacrificabili di fixture

Queste password appartengono esclusivamente alle fixture sintetiche già versionate, non al database né a persone reali.

| Utente | Password sintetica | Permessi effettivi B03 |
| --- | --- | --- |
| operatore-alfa-sintetico | synthetic-alpha-password | Tenant Alfa; lettura società A e B; creazione destinazione soltanto B; pubblicazione societaria A/B; nessun edit comune |
| operatore-alfa-senza-lettura | synthetic-no-read | Nome storico B02: in B03 legge soltanto B e modifica i tre campi comuni. Pubblicazione limitata a sede/magazzino: insufficiente. Nessuna creazione destinazioni |
| operatore-beta-sintetico | synthetic-beta-password | Altro tenant Beta, società C: legge soltanto la propria controparte |
| operatore-senza-membership | synthetic-no-membership | Nessuna società autorizzata |

A e B sono società dello **stesso tenant Alfa**; Beta è un altro tenant, non la società B. La UI mostra i nomi societari delle fixture. ID società: A termina `1101`, B termina `1102`, C termina `2201`. Non esistono utenti separati A/B: il primo account seleziona entrambe le società.

## Scenari e risultati attesi

1. Accedere come `operatore-alfa-sintetico`. Selezionare A, annotare identità comune e tre campi; selezionare B. Stesso UUID e stessi campi: non sono due anagrafiche. I test tecnici hanno già cambiato il nome in «Modifica comune sintetica»; non attendersi necessariamente il nome iniziale.
2. In B premere **Destinazioni**, inserire un indirizzo univoco inventato (es. «Prova manuale 01») e **Aggiungi destinazione privata**. Deve apparire «Riservata alla società proprietaria». Ricaricare, accedere nuovamente e verificare che sia persistita in B.
3. Selezionare A e riaprire Destinazioni: quell'indirizzo non deve apparire. Tornare in B: deve esserci. Le destinazioni lasciate dalle verifiche tecniche sono sintetiche; identificarne una nuova propria.
4. In B, sulla propria nuova destinazione, **Condividi nel tenant**. Diventa «Condivisa nel tenant». In A ora compare la stessa destinazione. Nessuna revoca/cancellazione/modifica indirizzo è prevista in B03.
5. Come primo account provare **Modifica campi comuni** e salvare valori inventati: rifiuto. Il permesso di pubblicazione non concede edit comune.
6. Ricaricare la pagina per cambiare identità (token soltanto in memoria; nessun logout dedicato). Accedere come `operatore-alfa-senza-lettura`: deve essere disponibile soltanto B. Modificare e salvare i tre campi comuni; con il primo account verificarli anche in A, stesso UUID.
7. Con l'editor aprire una destinazione privata B rimasta dai test e provare **Condividi nel tenant**: rifiuto, perché edit comune e grant sede/magazzino non bastano. Provare una nuova destinazione: rifiuto. Pulsanti visibili non equivalgono a permesso.
8. Con account Beta verificare soltanto C e la sua controparte distinta, senza indirizzi Alfa, anche dopo la pubblicazione. Con l'account senza membership nessuna società. Le prove tecniche verificano anche accessi diretti con ID manipolati, non solo la UI.
9. Password errata: accesso rifiutato. Campi vuoti/lunghi non devono essere salvati. Non inserire token negli URL o nelle chat.

## Accettazione

Comunicare per ciascun punto: superato/non superato, società/identità sintetica, azione ed errore visibile; niente token/password nei report. L'ambiente persiste, ma non è produzione: singolo host, nessun backup/ripristino validato, Keycloak sintetico reimportato dopo riavvio. Non sono presenti anagrafica generale, amministrazione utenti, deduplicazione, controlli fiscali o B04+. Il 18 ottobre 2026 il proprietario ha comunicato «Ho fatto la prova privata: funziona tutto. Possiamo procedere»: accettazione manuale privata positiva e autorizzazione alla consegna finale B03. È un'attestazione del proprietario, non un nuovo test browser eseguito dall'agente né un verbale dettagliato per ciascun punto. Prima della consegna restano la review indipendente della configurazione manuale più recente e la CI remota sul commit esatto; B04–B14 non autorizzati.
