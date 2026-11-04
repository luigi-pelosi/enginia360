# MVP03.b — Gestione utenti, ruoli e permessi: gate di policy D97

<!-- mvp03-delivery-current:start -->
MVP-03/#142 e #166 COMPLETATI: PR #167 merged il 4 novembre 2026, main `c4d46c03d80f7122f1172a5a6bd96ab0f8fa2edb`, candidate `0f9f7d167b68778ff36d21b7b8355fecf541c72f`, tree equivalente `56f47b1cee07fe227422d9f49a3bcd703b3adf5a`. Il coordinatore ha verificato PR CI `41752991377` e dispatch `41753044926`, step richiesti e sette ZIP exact-head; evidenze `/root/.hermes/evidence/enginia360-mvp03b2b/final`. Primo binding crea membership disabilitata: abilitazione successiva e ruoli restano espliciti. Nessun deployment/readiness operativo. MVP-04/#143 IN IMPLEMENTAZIONE, NON VERIFICATO; contratto `docs/mvp04-counterparties-contract.md`. I riepiloghi D97/D98 sono storici dei gate documentali (runtimeDelivered=false solo del gate), non negano la consegna funzionale successiva. #164 rimane consegnato da PR #165.
<!-- mvp03-delivery-current:end -->

## Documento e checkpoint storici seguenti — superati per lo stato corrente

Stato corrente — 3 novembre 2026. Refs #142. MVP03.b.1 consegnato via PR #162: delega utenti distinta, ruoli/permessi configurabili, audit atomico immutabile ed enforcement effettivo sul catalogo iniziale `organization-context.read/write`. I domini futuri devono integrare i propri consumer reali. MVP03.b non completato: invito/abilitazione e primo ingresso federato restano da eseguire. «nessun runtime consegnato qui» si riferisce al gate di policy D97, non nega la successiva consegna MVP03.b.1; il runtimeDelivered=false di quel gate e dell’intero MVP03.b resta distinto dal sottoincremento consegnato. [Decisione D98 e prossimo contratto finito](mvp03b2-user-onboarding.md). D96 autorizza il seguito autonomo.

<!-- d97-history:start -->
## Archivio del gate D97 e del suo contratto precedente

Il testo seguente è la registrazione documentale originaria: «questa PR», «prima del runtime» e «prossimo incremento» si riferiscono al gate D97/PR #160, non allo stato successivo a PR #162. Decisione/alternative/quote e assertion originali restano intatte.

Data: 3 novembre 2026. Refs #142. Stato: decisione confermata; questa PR contiene soltanto documentazione, test offline e selezione CI. Merge di questo gate **prima del runtime** dipendente; nessuna amministrazione utenti o enforcement audit dichiarati consegnati. D96 autorizza il proseguimento autonomo, non occorre una nuova conferma ordinaria.

## Decisione e alternative

### D97 — Creazione e modifica delegata di ruoli e permessi con audit

Fonte: risposta diretta di Luigi Pelosi nella conversazione corrente. Prima dell'assegnazione, ricerca `git grep -n D97` su tutti i file tracciati alla base `097680690d479bbfbd498fa4fd3d6c4bd5a99db8`: nessuna occorrenza. Nessuna collisione; D96 rimane l'autorizzazione autonoma nella carta, D1–D95 e i blocchi storici rimangono invariati. Il registro di questa nuova decisione è questa sezione, collegata dalla carta §8.1.

Domanda precedente (contesto conservato nel passaggio di consegna): «Il delegato alla gestione utenti puo soltanto assegnare ruoli definiti dal SUPER ADMIN oppure anche creare/modificare ruoli e relativi permessi nel proprio tenant?»

- **Alternativa A (raccomandata, NON SCELTA):** soltanto assegnare ruoli definiti dal SUPER ADMIN. La raccomandazione restrittiva dell'agente non è stata scelta e non è il default approvato.
- **Alternativa B (SCELTA):** anche creare/modificare ruoli e relativi permessi nel proprio tenant; l'owner aggiunge l'audit obbligatorio.

Risposta esatta dell'owner:

> Può anche creare e modificare ruoli e permessi sempre auditando il tutto

<!-- d97-current:start -->
D97: creare e modificare ruoli e permessi con audit immutabile e tracciabile obbligatorio, solo nel proprio tenant; gestione utenti distinta dalla delega organizzativa; nessun SUPER ADMIN, nessun potere cross-tenant o control-plane, nessuna subdelega o nomina implicita; non solo ruoli definiti dal proprietario; nessun runtime consegnato qui.
<!-- d97-current:end -->

Il SUPER ADMIN conferisce la distinta delega a un soggetto già anagrafato nel tenant. L'anagrafazione non è un grant. D97 risolve in generale creazione/modifica dei ruoli e permessi e supera soltanto la precedente proposta restrittiva, non le barriere tenant o la separazione tra autorità di piattaforma e gestione utenti. La delega organizzativa consegnata da [MVP03.a](mvp03a-organization-delegation.md) non concede gestione utenti; la nuova delega non concede automaticamente la prima. Le decisioni storiche D77 e i profili ERP non vengono riscritti o migrati per implicazione.

## Interpretazione tecnica minima, non nuovo limite di dominio

I permessi sono configurazione su **azioni e scope eseguibili supportati** dal sistema, non codice arbitrario né bypass delle autorizzazioni API. È un’**interpretazione tecnica minima dell’agente, correggibile** dal proprietario, **non un nuovo tetto ai ruoli** e non un ritorno all'alternativa A. Il delegato può creare/modificare definizioni di permesso e composizioni di ruoli tenant-scoped sopra le operazioni realmente implementate; il catalogo di azioni del sistema non coincide con le etichette dei ruoli configurate dal cliente. Non inventare ruoli professionali, amministrativi o altri ruoli di dominio per chiudere questa policy.

Cambiare etichette dei ruoli o chiamare un ruolo «SUPER ADMIN» non crea autorità globale: promozione globale automatica vietata. L'editing di un ruolo non può nominare un altro delegato, concedere subdelega, cambiare bootstrap o autorità di piattaforma, creare tenant o invadere altri clienti. Nessun grant nasce dal primo login, da claim non verificati, dalla registrazione o dal token di correlazione. Non imporre qui un requisito ulteriore del tipo «solo i permessi già posseduti dal delegato»: il matching azione/scope e la traduzione esatta della delega sono lavoro tecnico del prossimo contratto eseguibile, non una riduzione della decisione approvata.

## Contratto finito del prossimo incremento, ancora da eseguire

MVP03.b non è completato da questo gate. Il prossimo esecutore deve ispezionare l'attuale catalogo di azioni, resolver, binding/membership, grant, sessioni e API/UI; definire payload minimi, revisioni e matching azione/scope prima del codice dipendente, senza tornare a chiedere se il delegato possa creare/modificare ruoli e permessi.

1. **Delega distinta:** grant/lettura/revoca da SUPER ADMIN per una membership esistente nel solo tenant destinatario, separata dalla delega organizzativa. Server deriva identità e tenant verificati e rivaluta autorità corrente per ogni operazione; nessuna fiducia nel tenant del browser. Revoca o disabilitazione impediscono nuove scritture anche con sessione già aperta.
2. **Ruoli e permessi configurabili:** creazione, modifica e rilettura persistita nel tenant; definizioni di permesso collegate alle azioni/scope supportati, assegnazione a utenti entro confini verificati. Diniego esplicito per azioni inesistenti o non applicabili, scope estranei, richieste cross-tenant/control-plane e tentativi di cambiare autorità globale. Nessun tetto owner-defined-only reintrodotto.
3. **Audit obbligatorio:** ogni mutazione amministrativa ammessa (delega, revoca, ruolo, permesso, assegnazione, abilitazione nel relativo percorso) deve avere registrazione immutabile e tracciabile, atomica alla modifica: attore verificato, autorità/delega usata, tenant, azione, destinatario, revisione e differenza prima/dopo minimizzata, timestamp, esito e correlazione tecnica. Fallimento della persistenza audit = nessun effetto amministrativo, fail-closed. Vietate modifica/cancellazione dell'audit da parte del delegato. Dinieghi tracciati senza rivelare dati di altri tenant; audit non contiene segreti o token. La retention e i requisiti operativi non sono inventati qui; il progetto non dichiara un archivio operativo già verificato.
4. **Revoca, replay e concorrenza:** testare revoca corrente durante mutazioni e assegnazioni, aggiornamenti concorrenti e revisioni stale, replay identico senza duplicati e payload diverso con stessa chiave rifiutato. Una modifica successiva non riscrive la provenienza di un evento audit precedente. Nessuna perdita o duplicazione silenziosa della coppia effetto/audit.
5. **Percorso completo:** API ASP.NET Core, PostgreSQL/RLS e Next.js SSR italiano autenticato; UI condizionata dall'azione corrente, nessun dato privato in cache condivisa. Provare anonimo, membership semplice, solo delega struttura, solo delega utenti, entrambe, revocato e altro tenant. L'UI non sostituisce mai l'autorizzazione backend. Dati soltanto sintetici e fixture isolate.
6. **Utenti, inviti e abilitazione:** restano parte del risultato MVP03.b approvato da D96. Prima del percorso relativo documentare il meccanismo effettivo di binding/identità e i contratti di sicurezza; non inventare qui link/token, durata, consegna email, auto-verifica o accesso da una semplice email. Lavoro indipendente su ruoli/permessi non richiede di riaprire D97; una decisione realmente mancante si isola al comportamento dipendente.

Le prove vanno implementate RED → GREEN e devono verificare audit SQL effettivo, isolamento con connessioni riutilizzate/pool 1 e 4, autenticazione e revoca OIDC/HTTP, CSRF, SSR/cache, input e autorizzazione. Distinguere test della policy documentale da enforcement eseguito. Le 37 prove SQL precedenti per pool di MVP03.a e le migrazioni pubblicate restano evidenza storica intatta, non prova di D97.

## Consegna di questo gate e vincoli

Guardie eseguibili: `python3 -I scripts/test-d97-policy.py` e `python3 -I scripts/test-d97-impact.py`. Prima delle modifiche documentali: policy RED per assenza del blocco D97; selector/job RED per assenza di mapping ed esecuzione delle guardie. GREEN deve includere CLI valida completa, mutazioni di ogni confine, quote/alternative, audit e divieto di falsa consegna, più regressioni dei selettori esistenti. I log RED/GREEN e i metadati PR exact-head vengono conservati nel passaggio di consegna del coordinatore, non inventati come runtime.

Eccezione CI finita soltanto per questo documento, le due nuove guardie e i cinque riepiloghi correnti, con selector/workflow condivisi solo in combinazione documentale ancorata. Il job offline MVP esegue anche le vecchie guardie senza indebolirle; budget e trigger invariati. Cambi misti a runtime conservano tutti i consumer precedenti; eseguibili sconosciuti falliscono chiusi. PR-only automatico e dispatch offline exact-head quando applicabile, `full_architecture=false`; nessuno stack ERP o acceptance runtime di questa policy. Dopo il merge verificato, proseguire il contratto tecnico/runtime sopra; #142 rimane aperta fino al percorso completo.

Nessun deployment, nuova dipendenza, invito reale, chiamata provider, dato reale, acquisto, ambiente persistente o modifica a segreti/storage/servizi protetti. Nessuna scrittura a issue/Project o merge da questo esecutore documentale. Storia, migrazioni, vecchie assertion e confini D96 rimangono preservati.

<!-- d97-history:end -->
