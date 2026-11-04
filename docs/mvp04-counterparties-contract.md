# MVP04 / #143 — contratto finito di implementazione

Stato corrente: VALIDAZIONE FINALE LOCALE PASSATA; CI/ARTEFATTI EXACT-HEAD REMOTI PENDENTI, consegna NON VERIFICATA.
Contratto iniziale fissato prima del codice; intero #143 prima di qualsiasi test,
build, audit, runtime o CI durante l'implementazione. Consegna e prove finali sono
distinte: [ledger di implementazione e validazione](mvp04-implementation.md).

## Fonti e minimo eseguibile

D96, baseline MVP §§1–2 e issue #143 (corpo e discussione riletti) confermano
identità e ruoli business condivisi nel tenant, indipendenti da Workshop/ERP.
D88 e il contratto pubblicato 0027 confermano il ruolo **fornitore**. Questo è
l'unico ruolo business minimo: non si inventano cliente/intestatario/conducente
come ruoli gestionali da comportamenti legacy non confermati. Nessun ruolo
business concede permessi di sicurezza; i ruoli RBAC di D97 sono oggetti distinti.

Identità: denominazione obbligatoria (1–200 scalari Unicode), identificativo
fiscale facoltativo (0–100), sede legale facoltativa (0–500). Sono gli unici campi
comuni già presenti; non si inventa obbligatorietà fiscale, partita IVA unica,
paese/tipo persona o validazione tributaria. Stringa vuota rappresenta assenza
nei vecchi contratti non-null; nessun record storico è riscritto. Il vecchio
port recipient di fatturazione conserva la forma tecnica precedente (campi
non vuoti, già garantiti da 0003): un’identità minima non è automaticamente un
recipient completo, senza validazione fiscale o nuovi requisiti anagrafici. Le vecchie API
mantengono le proprie validazioni più restrittive. Nessuna cancellazione fisica,
fusione, disattivazione o workflow nuovo. Identità omonime o con uguale dato
fiscale sono ammesse, mai auto-abbinate: cercare prima e scegliere esplicitamente.

Operazioni attive: elenco/ricerca paginata, selezione e dettaglio, creazione,
modifica dei tre campi, aggiunta/rimozione del ruolo fornitore con revisione
comune condivisa. Non c'è una semantica temporale dei ruoli inventata.

Estensioni societarie: riuso delle destinazioni già esistenti (indirizzo,
proprietario società, stato pubblicato), consultazione separata e creazione/
modifica delle sole destinazioni private della società autorizzata, con revisione
indipendente. Nessuna nuova pubblicazione, eliminazione, prezzo o dato contabile.
Le mappature Giobby restano esclusivamente nel percorso owner-offline storico:
non sono campi del form comune né un nuovo writer applicativo ERP.

## Catalogo RBAC e isolamento

Azioni tenant esatte: `counterparties.shared.read`, `counterparties.shared.create`,
`counterparties.shared.edit`, `counterparties.business-roles.write`.
Azioni società esatte: `counterparties.extensions.read`,
`counterparties.extensions.write`. Lettura condivisa esplicita richiesta anche
per scritture, letture e scritture estensioni; scrittura estensioni richiede anche
lettura della medesima società. Nessun diritto operativo implicito da SUPER ADMIN,
delega utenti/organizzazione o etichetta del ruolo.

Configurazione permessi: conservare integralmente azioni organization-context e
tripla esatta società/sede/magazzino. Per nuove azioni shared usare la tripla
esplicitamente null (tipo tenant, NON wildcard); per extensions solo società
esistente del tenant, sede/magazzino esplicitamente null. Consumer nuovi separati
non fanno confluire questi scope nelle vecchie permission company/common-edit.
Matching binding issuer/subject opaco esatto, membership corrente e Enabled
ricontrollati in transazione proprietaria; lock 777036 prima di master authority.
Modifica/revoca ruolo/permesso/assignment e disabilitazione incidono sulla sessione
già aperta e prima di un replay. Nessuna modifica alle origini legacy dei grant.

## Autorità, concorrenza e provenienza

Singola master authority tenant-wide già esistente. Setup standalone esplicito
attraverso `scripts/owner-master-authority.py` e funzione owner-only esistenti,
direzione Enginia360ToExternal (nome storico del writer locale, non prerequisito
ERP); nessun setup automatico né switch di profili esterni. Assente: 409 missing;
esterna: 409 external anche con ruolo RBAC. Versione autorità esatta sul comando.
Scritture comuni e ruolo usano la stessa sequenza `common_edit_history` e lock
master; i nuovi comandi registrano ricevuta con request tipizzata esatta e
snapshot storico immutabile, actor/binding hash/versione/provenienza minimizzata.
Estensioni hanno revisioni autonome e audit atomico, senza cambiare il comune.
UUID canonici lowercase nonzero, chiavi/tipi payload esatti; stesso commandId e
stesso payload/attore/binding => snapshot originale, non stato corrente. Cambiare
payload/target/operazione =>409. Autorizzazione corrente prima della ricevuta.
Audit fallito => rollback, nessun hard delete o mutazione dello storico.

## UI e accettazione finale (stato corrente nel ledger di implementazione)

Pagina Next italiana `/counterparties`: SSR privato no-store, query/selettore
senza UUID manuali, creazione/edit/ruolo e destinazioni societarie persistite con
rilettura. Sessione OIDC/CSRF esistenti; pending/disabled rifiutati, nessuna identità
inventata. Comando incerto congela UUID/path/bytes e tutti i form/link; retry
identico e GET autorevole prima dello sblocco. Recupero limitato alla pagina
aperta; reload forzato non recupera i bytes. SSR senza JS in lettura.

Prove finali richieste: SQL pool 1/4; cookie/JWT OIDC; tenant/user/company isolation;
role edit/revoke e disable race; revisione comune vs ruolo e destinazioni;
replay storico dopo modifica, audit rollback/immutabilità, payload negativi;
SSR noJS/header/cache/CSRF/browser; compatibilità MVP03 e vecchie origini;
selezione CI finita positiva/mista/sconosciuta. Sorgente non equivale a prova.

Migrazione append-only 0042; 0001–0041 immutabili. Classificare nuove tabelle
nell'inventario offline. Rollback: ritirare nuove route/UI e preservare audit e
schema; mai rollback distruttivo/migrazione inversa dei dati. Nessun lavoro su
Catalog MVP05, veicoli, documenti, acquisti, Workshop o connettori salvo consumer
diretti di compatibilità/sicurezza. Readiness operativa resta non provata.
