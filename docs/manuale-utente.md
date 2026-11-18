# Enginia360 — Guida rapida

Questa guida spiega le funzioni della foundation: accesso, anagrafiche, magazzini, utenti, autorizzazioni e cataloghi geografici.

Le schermate sono reali e usano un'organizzazione dimostrativa. Le voci e i pulsanti disponibili dipendono dai tuoi permessi.

## 1. Accedere

1. Apri l'indirizzo di Enginia360 ricevuto dall'amministratore.
2. Inserisci **Codice organizzazione**, **Nome utente** e **Password**.
3. Premi **Accedi**.
4. Al primo accesso, se richiesto, scegli una nuova password e confermala.

Solo il Super Admin può accedere senza codice organizzazione. Il Super Admin può anche inserirlo per entrare con l'organizzazione già selezionata.

Se l'accesso non riesce, verifica i dati indicati nel messaggio. Per una password dimenticata o un'utenza disabilitata, contatta l'amministratore.

![Schermata di accesso](assets/manuale/01-accesso.png)

## 2. Orientarsi

- **Menu a sinistra:** apre le sezioni disponibili. Su uno schermo piccolo si apre dal pulsante del menu.
- **Organizzazione:** il Super Admin seleziona l'organizzazione su cui lavorare; gli utenti ordinari operano nella propria.
- **Lingua, in alto:** permette di passare tra italiano e inglese.
- **Profilo, in alto a destra:** apre i dati personali e il comando di uscita.

Negli elenchi puoi cercare, cambiare pagina e aprire una voce. **Nuovo** crea un record; l'icona della matita lo modifica. Il cestino richiede conferma prima di eliminare.

![Menu ed elenco delle aziende](assets/manuale/02-navigazione.png)

### Salvare senza sorprese

1. Compila i campi contrassegnati con **\***.
2. Nelle selezioni puoi digitare per trovare un'opzione, poi sceglierla.
3. Premi **Salva** per registrare dati e associazioni insieme.
4. Premi **Annulla** per chiudere senza registrare la bozza.

Digitare in una ricerca non salva nulla. Se Salva non è disponibile, controlla i campi obbligatori e gli eventuali errori. Il **Codice** delle anagrafiche è normalmente facoltativo; il codice dell'organizzazione è invece obbligatorio.

## 3. Registrare aziende e sedi

Per iniziare, crea prima l'**Azienda**, poi le sue **Sedi**.

### Creare una sede

1. Apri **Sedi → Nuovo**.
2. Seleziona l'azienda e inserisci il nome della sede.
3. Compila almeno uno tra **Partita IVA** e **Codice fiscale**.
4. Inserisci la strada nel campo **Indirizzo**.
5. Scegli la **Nazione** e cerca la **Città**. Seleziona il suggerimento con il CAP corretto: città, provincia, CAP e regione vengono completati dai cataloghi locali. La strada digitata resta invariata.
6. Verifica **Indirizzo, Città, Provincia, CAP e Nazione**: sono tutti obbligatori. La Regione è facoltativa. Puoi completare manualmente i dati mancanti.
7. Scegli eventuali tipologia giuridica e funzioni, quindi premi **Salva**.

Uno stesso comune può avere più CAP: scegli quello appropriato alla sede. I suggerimenti aiutano la compilazione, ma i dati vanno sempre controllati.

![Esempio di compilazione di una sede](assets/manuale/03-nuova-sede.png)

### Organizzazioni commerciali

- **Organizzazioni di vendita:** appartengono a un'azienda.
- **Organizzazioni di acquisto:** possono coprire aziende e sedi. Seleziona prima le aziende, poi le sedi delle aziende selezionate.

Queste associazioni descrivono l'organizzazione commerciale: non concedono permessi agli utenti.

## 4. Organizzare i magazzini

Segui questo ordine:

1. **Tipi di magazzino:** crea le classificazioni necessarie.
2. **Magazzini:** crea il magazzino e collegalo a sede e tipo.
3. **Ubicazioni:** registra le posizioni interne e collegale al magazzino.

La foundation gestisce queste anagrafiche, non movimenti, giacenze o prenotazioni di merce.

## 5. Gestire utenti e autorizzazioni

Questa parte è riservata a chi possiede i permessi amministrativi.

- **Utenti:** persone che accedono all'organizzazione. Nome utente, nome, cognome ed email sono obbligatori.
- **Ruoli:** insiemi di permessi, per esempio quelli necessari a un operatore.
- **Gruppi:** raggruppano utenti e permettono di assegnare ruoli comuni.
- **Permessi:** catalogo consultabile delle operazioni disponibili; non si creano nuove voci manualmente.

### Configurare un ruolo

1. Apri **Ruoli → Nuovo** e inserisci il nome.
2. In **Permessi del ruolo**, apri i gruppi e seleziona le operazioni necessarie.
3. Usa la ricerca per trovare un permesso. Puoi selezionare un intero ramo o **Seleziona tutti**; una casella parziale indica che è selezionata solo una parte del ramo.
4. Premi **Salva**.
5. Assegna il ruolo agli utenti interessati, direttamente oppure attraverso un gruppo.

Concedi solo le operazioni necessarie. Un utente senza ruoli o permessi non ottiene automaticamente accesso alle funzioni dell'organizzazione, ma può sempre modificare il proprio profilo.

![Creazione di un ruolo e selezione dei permessi](assets/manuale/04-ruoli.png)

Per impostare o reimpostare la password di un altro utente, usa l'azione dedicata disponibile nella sezione **Utenti**. Comunica la password iniziale con un canale riservato: all'accesso sarà richiesto di sostituirla.

## 6. Consultare nazioni e città

Apri **Impostazioni**, poi scegli la tile **Nazioni** o **Città**.

I cataloghi sono condivisi da tutte le organizzazioni. Gli utenti autenticati possono consultarli; solo il **Super Admin** può modificarli.

- **Nazioni:** nome e codice paese a due lettere, per esempio `IT`.
- **Città:** nazione, nome, CAP, provincia e regione. Più CAP dello stesso comune sono voci distinte.

Per aggiungere una città di una nuova nazione, registra prima la nazione. Una nazione collegata a città non può essere eliminata finché esistono quei collegamenti. Le modifiche ai cataloghi non riscrivono gli indirizzi già salvati nelle sedi.

![Tile Nazioni e Città nella pagina Impostazioni](assets/manuale/05-impostazioni.png)

## 7. Aggiornare profilo e password

1. Premi il tuo nome in alto a destra e scegli **Profilo personale**.
2. Aggiorna nome, cognome, email, data di nascita, telefono o lingua preferita.
3. Premi **Salva**. Il nome utente non si modifica dal profilo.

Per cambiare anche la password, compila la password attuale, la nuova password e la conferma. La nuova password deve contenere da **14 a 256 caratteri**.

**Non serve cambiare la password per aggiornare i dati personali.** Lascia vuoti nuova password e conferma; un'eventuale password attuale inserita dal browser non obbliga a sostituirla.

![Profilo personale e cambio password facoltativo](assets/manuale/06-profilo.png)

Quando hai finito, apri il menu del profilo e scegli **Esci**.

## 8. Risolvere i problemi più comuni

| Situazione | Cosa fare |
|---|---|
| Non riesco ad accedere | Controlla codice organizzazione, nome utente e password. Segui il messaggio mostrato; se necessario contatta l'amministratore. |
| Non vedo una sezione o il pulsante Nuovo | Verifica l'organizzazione selezionata e chiedi all'amministratore di controllare i permessi. |
| Salva è disabilitato | Completa i campi con \*, correggi gli errori e verifica di aver modificato almeno un dato. |
| Non trovo una città o una nazione | Cerca anche per CAP; chiedi al Super Admin di verificare o aggiungere la voce. L'indirizzo può essere completato manualmente. |
| Non posso eliminare una voce | Potrebbe essere ancora collegata ad altri record. Controlla i collegamenti prima di riprovare. |
| La sessione è scaduta | Accedi di nuovo. Le modifiche non salvate non vengono registrate. |
