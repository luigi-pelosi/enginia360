# R04.c.2 — reso esplicito del nuovo (D81)

Stato: D81 approvata; implementazione UI/API/SQL e acceptance sintetica locale eseguite. Refs #84, parent #44/#5 aperte. Merge/chiusura/completamento Project spettano al parent dopo CI exact-head; i readback remoti sono nella PR, non anticipati qui.

<!-- enginia360-backlog:R04.c.2 -->
Refs #44, #5; entrambi restano aperti per ricevimento e altri residui.

## D81 — approvazione precisa, 24 ottobre 2026
Owner «Approvo A»: due ricambi prelevati entrambi INTEGRI e MAI INSTALLATI; reso esplicito di uno al magazzino originale, altro al tecnico. Fisico e commerciale/revisione invariati; impegno -1, disponibile/riprenotabile +1. Nessuna installazione persistita sul pick selezionato, Pending inclusa. Non D80 (solo mai prelevato), non carcassa, undo, danni/quarantena, altro magazzino, fornitore/ricevimento, post-chiusura, automatismi o nuove deleghe D77.

## Accettazione finita
- [ ] Prima vertical RED reale autenticata reserve2/pick2/group diverso ordine/return1, SQL append-only e quantità/commerciale invariati.
- [ ] Inventory ledger positivo q6/receipt/provenienza completa/attore membership verificata/tempo server; migrazione 0024 append-only, precedenti immutate.
- [ ] Contratti pubblici owning Workshop/Inventory, lock canonici ordine/riga/pool, nessun SQL privato cross-module/nested pool; nessuna installazione Pending o Consumed preesistente sul pick.
- [ ] Math impegno/capacità cumulativa/installabile/fence P2 coerente; ritorno non riapre pick originale né D80; full return senza altri effetti permette P2/remove, nuova reserve riprotegge.
- [ ] UUID/URL/payload replay immutabile q6, collisioni nascoste/input/overflow controllati, replay dopo P2/closure/capability-off; autorità missing/external conserva history.
- [ ] Esatta nuova azione, read-only/admin non impliciti, ogni asse tenant/company/site/warehouse, revoca, CSRF, RLS/grants/no update-delete-truncate/provenienza/context reset pool1+4.
- [ ] UI italiana specifica reservation/pick con quantità/history/advisory, retry byte-identico congelato, accettato vs readback ignoto, GET, 401/stale/late scope, niente localStorage; browser 1920/1366 focus/tab/error/scroll/footer e tutti pannelli.
- [ ] TLS/OIDC Chromium UI/API/SQL pool4+1, tentativo magazzino differente rifiutato; barriere fisiche SQL entrambi ordini return/return/sameUUID/install Pending/release/reserve/pool altri ordini/P2/remove/closure.
- [ ] Return→NUOVA reserve/pick/install/carcassa/chiusura/Billing Accounting interni bilanciati q6/idempotenti; simulatore esterno pinned, non Giobby.
- [ ] Migrazione fixture-free, inventario R06 nuova tabella UNDECIDED conteggi computati, OPE tutti OPEN.
- [ ] Impact/direct-selector RED prima produzione CI; dispatch-only affected-r04c2; mutazioni guard job/pool1/TERM/classificazione; PR-only, exact-head full_architecture=false e job effettivi verdi.
- [ ] Locked build/typecheck/audit/tests/review; lifecycle TERM Chromium+SQL lock e protezioni bootstrap/25 volumi/Tailscale invariati; PR Refs, parent merge/close/board completion.

Solo sintetico effimero random TLS Compose senza host port o volumi persistenti. Nessun deploy/ERP reale/acquisto/utente reale. Nessuna riapprovazione della policy richiesta.

## Rollback
Disabilitare nuove scritture senza nascondere storico autorizzato. Non invertire il ledger o decrementare fisico. Migration forward-only: nessuna modifica 0001–0023. Nessun deployment incluso.

## Contratto eseguibile

- Inventory possiede `new_part_returns` e ricevuta positiva q6. Azione nuova esatta `inventory.new-part-returns.create`, non implicita in reserve/pick/release/admin e non aggiunta alla delega D77. Grant iniziali solo nelle fixture isolate trusted.
- `POST` / `GET /api/v1/inventory/orders/{order}/lines/{line}/reservations/{reservation}/picks/{pick}/new-part-returns`. Body esclusivo `{ "id": "UUID non vuoto", "quantity": "q6 positiva" }`; campo `warehouseId`/attore/tenant e altri sconosciuti rifiutati. Il server deriva originale magazzino, catalogo/versione, prenotazione, ordine/lavorazione/riga dal pick immutabile; membership e attore da identità verificata, timestamp server normalizzato a microsecondi.
- Ricevuta immutabile: ID, prenotazione/pick/membership, ordine/riga/lavorazione, magazzino/catalogo/versione, quantità, data/attore. Replay normalizzato q6 stesso UUID e URL restituisce gli stessi valori originali, anche dopo full return+P2 tombstone, chiusura o capability-off; payload/URL cambiato è conflitto. Collisione UUID RLS-hidden non espone la ricevuta esterna.
- Nuovi comandi richiedono ordine/riga aperti, profilo stock **locale esplicito**, grant esatto e capability correnti. Sul pick selezionato non deve esistere **alcuna** installazione persistita: anche una sola quota Pending rende tutto il pick fuori da D81. Restituire prima parte del pick non impedisce una successiva installazione della sola quota ancora non restituita; impedisce ulteriori resi dopo quell'installazione.
- GET storico richiede lettura commessa + prenotazione sullo scope originale, non capability attiva o autorità locale. Il motivo advisory corrente è distinto dalla ricevuta immutabile; autorizzazione e fatti sono rivalutati al POST.

### Quantità e fence

Tutte le somme includono solo tenant/linea o pool societario/sede/magazzino/articolo pertinenti:

- impegno pool = Σ prenotato − Σ rilasci D80 − Σ resi D81 − Σ consumato;
- disponibile = fisico − impegno pool; il reso **non** aumenta il fisico;
- capacità residua riga cumulativa fra magazzini = quantità commerciale − Σ prenotato + Σ rilasci + Σ resi; **mai** aggiungere il consumo;
- pick residuo della prenotazione originale = quantità originale − Σ rilasci − Σ pick storici: il reso non riapre il pick;
- installabile = pick originale − Σ resi del pick − Σ installazioni persistite, Pending incluse;
- residuo presso operatore nel GET = pick − resi − installazioni; un residuo positivo non autorizza il reso di un pick parzialmente installato;
- P2: solo compensazione completa e assenza di altri effetti attivi libera modifica strutturale/rimozione. Nuova reserve torna a proteggere la riga. Fatti e versioni originali non sono riscritti.

D80 continua a rifiutare qualsiasi prenotazione che abbia avuto un pick, anche se quel pick è stato interamente reso. Carcassa del sostituito e reso del nuovo sono fatti distinti: nessuna disponibilità vendibile dalla carcassa.

### Transazioni e ownership

Ordine canonico del reso: UUID comando → commessa → riga cumulativa → grant/capability riletti e bloccati → pool stock. L'installazione condivide commessa/riga e rilegge la capacità dopo i lock: il fatto Pending precede l'effetto stock e non può sfuggire al reso. Workshop espone `pick_has_installations` / `pick_installed_quantity`; Inventory espone `pick_returned` / `pick_installation_capacity` / fence P2. Invoker + forced RLS e grant EXECUTE minimi; solo la stretta autorizzazione OrganizationAccess è SECURITY DEFINER con search_path fissato. Nessun SQL di tabelle private cross-module o connessione pool annidata.

Migrazione **0024**: append-only; prefix manifest 0001–0023 e byte SQL precedenti verificati contro digest pubblicato. Trigger di provenienza, attore, stato aperto/autorità, assenza installazioni e bound aggregato, oltre a immutabilità UPDATE/DELETE/TRUNCATE. La nuova tabella R06 è `operational_fact`, **UNDECIDED**, non eleggibile per import: conteggio calcolato 24 migrazioni/65 CREATE/9 schemi. OPE01–OPE05 OPEN invariati.

## UI e recupero

Pannello italiano specifico per prenotazione e pick sotto il prelievo; quantità esplicita, history e motivi correnti. Nessuna scelta di destinazione. Risposta POST persa: URL/UUID/body restano congelati in memoria e tutti gli antenati/operazioni concorrenti sono bloccati; retry byte-identico, poi GET autorevole. Risposta accettata con GET fallito: messaggio «registrato; stato non verificato», nessun secondo POST automatico, rilettura esplicita. 4xx invalidano advisory; 401 cancella quantità/stato e il runtime smonta commessa e pannelli. Generation/sequence scartano risposte vecchie; niente localStorage né retarget automatico.

Limite dichiarato: l'envelope incerto resta solo nella sessione del pannello montato; non si promette ripristino del retry dopo refresh/logout. Il GET storico consente la riconciliazione dei fatti accettati senza inventare una nuova scrittura. Layout/focus/tab/error/scroll esercitati realmente a 1920×1080 e 1366×768, tutti i tre pannelli aperti, gruppo editor e footer raggiungibili; screenshot conservati come evidenza scratch, non dati business.

## Evidenze locali e test-first

Comando verticale comune: `python3 scripts/run-r04c2-tests.py` (pool4); `R04A_POOL_SIZE=1 python3 scripts/run-r04c2-tests.py` (pool1). Credenziali sintetiche random, CA trusted, OIDC Chromium → API → PostgreSQL, nessun bypass TLS. Barriere reali su connessioni fisiche distinte con PID controller/waiter e `pg_blocking_pids`; entrambi gli arrivi per reso/reso, stesso UUID, installazione (anche Pending), D80, nuova reserve, altro ordine sul pool, P2/remove e chiusura. Gli altri casi aggiunti già verdi sono regressioni, **non** RED retroattivi.

Log durevoli in scratch `r04c2-logs/`:

| Comportamento nuovo | RED | GREEN/evidenza successiva |
| --- | --- | --- |
| Prima verticale reserve2→pick2→reso1, gruppo != ordine | 01 (404: sola assenza route, non prova delle altre semantiche) | 03 e successive: SQL/fisico/impegno/disponibile/tecnico/commerciale |
| Quota resa non installabile | 04: 201 invece di 409 | 05 |
| Qualsiasi installazione Pending/Consumed impedisce nuovo reso | 06: 201 invece di 409 | 07 |
| Nuova reserve recupera quota resa (pool e linea) | 08: 409 invece di 201 | 09 |
| P2 dopo compensazione completa | 10: fence residua 409 | 11 |
| Provenienza SQL/originale magazzino | 13: INSERT indebito accettato | 14 |
| Bound aggregato SQL | 16: over-return accettato | 17 |
| SQL include Pending nel divieto | 18: INSERT indebito accettato | 19 |
| SQL impedisce installazione della quota resa | 20: INSERT indebito accettato | 21 |
| Pannello UI reale | 23: controllo inesistente | 25 (24: difetto mapping corretto) |
| Motivo advisory corrente | 26: campo assente | 27 |
| SQL rifiuta reso post-chiusura | 29: INSERT indebito accettato | 30 |
| UI401/403 scarta advisory autorizzante vecchio | 39: pulsante rimasto abilitato | 41 e successive |
| Residuo tecnico sottrae anche installazione Pending | 40: 1 invece di 0.5 | 45/47 |
| Audit tecnico indica ricevuta committed | 43: ID ricevuta assente | 45/47 |
| GET installazioni non mescola resi vecchi e installazioni nuove | 54: installed1/remaining1 incoerenti dopo return1+install1 | 55: snapshot unico RepeatableRead, barriera SQL fisica |

12 e 15 erano **errori di fixture**, non RED; riparati prima dei validi 13/16. 44 era errore del test nel riaprire il pannello (toggle same-document già aperto), non difetto del comando; corretto con reload autorevole. Impact RED 02 contiene sia rifiuti fail-closed/mancanza selection-job, sia file non ancora presenti: non è prova della feature business. Mutation guard: rimozione job/output/pool1/TERM, dispatch boundary, mapping migration, tabella/classificazione/eleggibilità/ownership devono fallire; control non mutato verde. Il guard D81 conserva unico registro D1–D81.

Prove latest locali: pool4 55 (16 named browser checks) e pool1 50 (13), readback SQL anche dei downstream interni/esterni; lifecycle TERM 48 con Chromium e lock SQL vivi; migrazioni fixture-free/restart/hardening/RLS/pool 49 (34 Python + 13 .NET, zero skip); build/typecheck/UI affected/audit 51 (141 pass) e API affected/publish/NuGet audit 52 (113 pass, 13 runtime skip: non contati come pass; job runtime espliciti obbligatori). Warning Vite di direttive dependency preesistenti conservati, npm audit zero vulnerabilità. Il simulatore è isolato e confronta summary persistito: non è Giobby né compatibilità API provider.

## Gate di consegna e limiti

CI automatica solo PR, runtime pertinente solo dispatch exact-head `full_architecture=false`, incluso job dedicato `affected-r04c2` pool4+1+TERM; tutti i consumer/material/editor/auth/fence/migration/offline/restore selezionati dall'impatto devono **eseguire** e passare. Skip non è pass; nessuna full architecture come gate di routine. Commit convenzionali e PR **Refs** #84/#44/#5; merge, issue closure e Project completion riservati al parent. Head/tree/run/job finali nella PR e nel risultato checkpoint dopo letture remote.

Solo synthetic/ephemeral. Nessun provisioning reale, ERP, acquisto, certificazione fiscale o operativa, readiness, deployment, host port o nuovo volume persistente. Bootstrap container ID/StartedAt, Tailscale443→localhost9119, 25 volumi/backups/configurazioni e branch protetto non toccati. Nessun nuovo gate di policy: D81 non va richiesta di nuovo.
