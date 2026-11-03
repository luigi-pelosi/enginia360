# Piano corrente di consegna MVP — D96

Data: 2 novembre 2026. Stato: sviluppo autonomo autorizzato; MVP non ancora pronto all'utilizzo.

## Mandato attivo

D96 nella [carta](../PROJECT_CHARTER.md) autorizza riallineamento GitHub e istruzioni, implementazione autonoma dei sette domini, pulizia motivata, commit/PR/CI/merge e pubblicazione del software quando verificato. La [baseline](mvp-baseline.md) descrive i requisiti e la [valutazione dell'esistente](mvp-existing-code-assessment.md) distingue il riuso dalle lacune.

Questo piano e [mvp-backlog.json](mvp-backlog.json) sostituiscono come roadmap operativa P00/UI01/R00–R06. [Il piano precedente](productization-plan.md) e le sue prove sono archivio storico: non richiedono completamento Giobby o ciclo officina prima del nuovo MVP. La contabilità interna non viene dichiarata deprecata o eliminata.

## Sette capability necessarie

1. Identity federation, RBAC e autorizzazioni.
2. Tenant, società, sedi e magazzini.
3. Controparti e ruoli.
4. Cataloghi articoli e servizi.
5. Inventari: gestione continuativa delle quantità.
6. Tipologie documentali configurabili per società.
7. Documenti: testate, righe, sviluppo parziale e raggruppamento con provenienza quantitativa e residui per passaggio.

Next.js SSR/shadcn/ui è il frontend, ASP.NET Core il backend, PostgreSQL la persistenza. Il nuovo inventario è documentale e locale senza prerequisito ERP; nessuno switch implicito degli ambienti storici.

## Ordine di consegna

| ID | Risultato | Dipendenza |
| --- | --- | --- |
| MVP-00 | Riallineamento verificato di carta, agenti, backlog e GitHub | Nessuna |
| MVP-01 | Shell Next.js SSR/shadcn con percorso di verifica isolato | MVP-00 |
| MVP-02 | Accesso federato, SUPER ADMIN e amministrazione organizzativa reale | MVP-01 |
| MVP-03 | Deleghe separate: struttura organizzativa e gestione utenti/ruoli | MVP-02 |
| MVP-04 | Controparti e ruoli gestibili autonomamente | MVP-03 |
| MVP-05 | Articoli e servizi gestibili senza Workshop | MVP-04 |
| MVP-06 | Configurazione societaria delle tipologie documentali | MVP-05 |
| MVP-07 | Testate/righe/conferma e carico/scarico/trasferimento tracciati | MVP-06 |
| MVP-08 | Sviluppo parziale e raggruppamento multi-sorgente | MVP-07 |
| MVP-09 | Pulizia dei percorsi sostituiti e acceptance finale integrata | MVP-08 |
| MVP-10 | Release verificata e valutazione di utilizzabilità operativa | MVP-09 |

Gli ID sono risultati, non obblighi di una sola PR: suddividere in sottoincrementi testabili senza restringere silenziosamente la capability. WIP 1: una sola implementazione attiva, ricerche indipendenti in parallelo. Nessuna promessa di date. L'autorizzazione copre l'intera sequenza, senza approvazioni ordinarie ripetute; i dettagli di dominio realmente mancanti si chiudono nel relativo contratto.

## Regole del primo percorso amministrativo

Il SUPER ADMIN è Luigi Pelosi, non il primo utente che si autentica. Il bootstrap dell'autorità globale deve essere esplicito, verificabile e auditato; nessuna inferenza da email, registrazione o correlation token. Non pubblicare identità o credenziali personali nelle fixture.

Il contesto di destinazione è verificato per ogni operazione globale. La delega è attribuita dal SUPER ADMIN a un soggetto già anagrafato nel singolo tenant. Gestione struttura e invito/abilitazione/ruoli sono facoltà distinte; nessuna estensione implicita ad altri tenant o al ruolo SUPER ADMIN. La facoltà di nominare ulteriori amministratori o subdelegare non è stata confermata: non implementarla come effetto collaterale.

Prima dell'implementazione dipendente definire campi minimi, revoca e assegnabilità finita. Le decisioni tecniche senza impatto di dominio sono responsabilità dell'agente. L'assenza di un dettaglio non blocca shell, letture e altro lavoro indipendente.

## Pulizia controllata

- Ripulire subito roadmap, stati attivi e istruzioni obsolete; mantenere cronologia ed evidenze con etichette storiche.
- Rimuovere UI/endpoint obsoleti solo dopo sostituzione, tracciamento degli utilizzi e verifiche pertinenti; non ricopiare tutto il vecchio frontend nel nuovo.
- Non cancellare interi moduli riusabili solo perché fuori MVP; togliere dal percorso attivo le dipendenze non necessarie, decidendo la rimozione per componente.
- Conservare migrazioni pubblicate, contratti/evidenze storici e rollback. Non riscrivere storia Git né eseguire prune Docker/volumi.
- Bootstrap, Tailscale 443 → localhost:9119, volumi, backup e configurazioni conservati restano protetti.

## Verifiche e consegna

Per ogni incremento: contratto finito → test eseguibile RED → GREEN → regressioni d'impatto → commit → PR → CI exact-head → dispatch runtime mirato quando applicabile → merge controllato → equivalenza del tree o nuova prova mirata se il tree cambia → rilettura issue e Project.

CI automatica solo pull_request; niente automatismi push main. Gli incrementi di routine usano full_architecture=false. Full architecture non è il default: una campagna finale esplicita dopo il completamento funzionale. Skip non è pass. Incrementi documentali usano guardie offline, non runtime storico indiscriminato. Test tenant/RLS/CSRF, autorizzazione, concorrenza, retry, audit, API/UI/build/dependency audit e health/smoke rimangono necessari secondo l'impatto.

## Pubblicazione e utilizzabilità

La release del software non coincide con un deployment o con l'accettazione operativa. MVP-10 deve distinguere artefatti verificati, readiness tecnica, target operativo e limiti residui.

Non presumere approvati dati reali, accesso pubblico, acquisti, nuovi ambienti persistenti o sostituzione dei servizi protetti. Prima di un uso operativo devono essere dimostrati identità/revoca, recupero/backup, privacy, manutenzione e gli altri gate applicabili; non dichiararli passati per il solo esito dei test sintetici. Se target o accesso non sono definiti, preparare il contratto operativo e chiedere solo quella decisione, senza fermare lo sviluppo isolato.

## Tracking GitHub

Riutilizzare il Project esistente, rinominandolo per il MVP e preservando gli item storici. Creare issue idempotenti con marker `enginia360-mvp:MVP-xx`; assegnare i nuovi item al backlog corrente. Gli item della vecchia roadmap ancora aperti vanno distinti come sostituiti, mai dichiarati completati. Il dettaglio storico rimane nei corpi/commenti e nella Git history. Numero issue e stato del Project sono sempre verificati con readback, non dedotti dal successo di una scrittura.

### Riorganizzazione riletta il 2 novembre 2026

Project privato esistente n. 3 rinominato **Enginia360 · MVP**, senza creare un Project duplicato. Create e rilette 11 issue #139–#149 per MVP-00–MVP-10; ogni item ha Backlog ID, ordine e stato verificati. MVP-00/#139 e' completato dopo PR #150 e CI `41536452707` (impact e guardie MVP offline, 32 step effettivi; tree `f583cb382ed78505cc727317129a98a0a3856e66`, evidenze verificate dal coordinatore). Checkpoint successivo: MVP-01/#140 completato (PR #151, head `e3102e41a34dddff63faf033b7c0c56935297635`; PR CI `41541966173`, dispatch `41541963004`, tree `1009876b5368aa30fa6ace3d20c1e226e57abbf2`, verificati dal coordinatore). MVP-02/#141 e' In corso; MVP-03–MVP-10 restano Backlog. I 66 item precedenti sono archiviati reversibilmente nel Project, non cancellati; le issue conservano storia e discussioni. Le sei vecchie capability #5/#42/#43/#44/#45/#46 sono state chiuse come sostituite (`not_planned`), non completate, dopo il merge verificato del riallineamento. #37 resta aperta e differita: nessuna archiviazione fisica di storage e' stata eseguita.

Il checkpoint MVP-01 introduce soltanto la [shell tecnica verificabile](mvp01-frontend.md) in `frontend/`; non anticipa identity federation o capability operative. MVP-01 e' consegnato; MVP-02.a/#152 e' consegnato via PR #153, main `185682700d621edcb547d0291167aec248c50bfe` (tree equivalente al candidato `a38a4274df901454b59892bc133f91c6a12d2df4`); PR CI `41553422654` e dispatch `41553418829` verificati dal coordinatore. [Autorita globale esplicita](mvp02a-platform-authority.md), bootstrap/revoca owner-offline e readout minimo non sono organizzazione CRUD o frontend autenticato. MVP-02.b/#154 e' consegnato via PR #155, main `1913c7393362d30193e79ebd7cc1f1a5f521f218` (tree `f4fbe62f00c59b427c57b6b00b88b371c6c37129` identico al candidato `a7c018e5eadfbef7653ea66ba0840c653605bbbc`); PR CI `41564892938` e dispatch `41564891812` verificati dal coordinatore. Il sottoincremento attivo MVP-02.c/#156 definisce il [percorso Next autenticato](mvp02c-authenticated-organization.md) sulle API di [amministrazione organizzativa persistita](mvp02b-organization-administration.md); parent #141 resta aperto e In corso fino alla verifica completa della UI autenticata. Issue/Project e merge restano gestiti dal coordinatore. Il nuovo percorso CI per frontend e' esplicito, isolato dal runtime ERP storico e usa `full_architecture=false`.

Correzione tecnica di esecuzione: il vecchio gh CLI non accettava il valore numerico zero per Ordine; e' stato usato ordinamento 1–11, mantenendo invariati gli ID MVP-00–MVP-10. La creazione issue e' stata ripresa tramite marker, senza duplicazioni. Nessuna di queste operazioni dimostra una capability applicativa completata.
