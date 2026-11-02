# R02 / D95 — proiezione positiva offline del ruolo fornitore esterno

Refs #136, #42, #44, #45. **Candidato runtime, non merged:** prove locali isolate PostgreSQL, TLS owner CLI e Chromium/OIDC/API/UI italiana eseguite; CI exact-head e pubblicazione riportate nella PR dopo esecuzione. La policy D95 è già risolta e i documenti/guardie sono merged in PR #137. Nessuna nuova scelta di dominio o modifica AGENTS.

## Contratto limitato

`python3 scripts/owner-external-supplier-role.py <input.json>` è un percorso **owner/trusted-operator offline**, non un endpoint, un grant utenti, un mandato tenant-admin o un importatore. Richiede la connessione del proprietario DB esistente non superuser, senza BYPASSRLS/CREATEROLE/CREATEDB, TLS `PGSSLMODE=verify-full` e `PGSSLROOTCERT`. Credenziali solo nella configurazione libpq/env approvata, mai negli argomenti del tool o nei log.

L'operatore deve avere già verificato offline l'identità e il fatto esterno e avere un binding/membership corrente già trusted. Il tool **non effettua** tale verifica: i riferimenti UUID sono provenienza/audit dell'atto, non autenticazione, prova automatica Giobby o garanzia della verifica. Nessuna chiamata Giobby né provider reader inventato.

Il JSON è chiuso, massimo 4096 byte, senza chiavi duplicate. Tutti i riferimenti sono UUID canonici minuscoli non nulli, non token da riparare:

- `commandId`, `tenantId`, `legalEntityId`, `counterpartyId`, `actorMembershipId`;
- `verificationReference` (verifica offline dell'operatore/atto), `sourceFactReference` (evidenza del fatto fornitore), `sourceId`, `profileId`;
- `sourceSystem`: esattamente `Giobby`; è un descrittore di provenienza, non sostituisce l'identità tecnica;
- `authorityVersion`: intero 1–2147483647, versione **corrente** della decisione unica `master_authority_history`; il contratto esistente usa UUID source/profile e questa versione, non un enum direzione come identità;
- `expectedRevision`: intero 0–2147483647 della **stessa** sequenza `common_edit_history` degli edit comuni/ruolo;
- `isSupplier`: letterale booleano `true`, mai false/null/stringa/numero.

Campi aggiuntivi (inclusi nome comune, codice fiscale, sede, VendorId/VendorName, prezzi, scope o grant) sono rifiutati. Il tool non configura l'autorità e non crea, deduplica, abbina o cambia identità.

## Atomicità e sicurezza SQL

La migrazione append-only `0035_external_supplier_projection.sql` aggiunge soltanto la funzione Counterparties `project_external_supplier_role(jsonb)` SECURITY DEFINER e `external_supplier_projection_history`. Le migrazioni pubblicate 0001–0034 e i rispettivi checksum restano byte-identici. Nessun app EXECUTE o SELECT/DML sulla nuova storia, nessuna modifica ai privilegi ordinari del ruolo o delle estensioni.

La funzione ricontrolla il `session_user` proprietario non privilegiato (non il `current_user` del definer), il contesto tenant/società e l'intero input prima dei cast. Sotto la lock tenant `master-authority:<tenant>`, blocca le righe binding/membership già fidate e la società fino al commit, verifica **direzione esterna, sourceId, profileId e authorityVersion esatti** e società compresa nella stessa decisione tenant-wide. Un'altra sorgente/profilo con la stessa direzione non è sufficiente. Nessun override master per società né switch automatico/retroattivo D76.

Sotto la lock UUID già usata dalle modifiche comuni, blocca la controparte esistente e controlla la revisione condivisa. Scrive nella stessa transazione:

1. storia comune Before/After con solo `isSupplier` portato a true;
2. richiesta completa e snapshot immutabile nel ledger di proiezione;
3. `IsSupplier=true` sulla controparte esistente.

La storia ha FORCE tenant RLS e trigger append-only (UPDATE/DELETE/TRUNCATE rifiutati anche all'owner). Errori di inserimento, violazioni o fallimento al commit non lasciano ruolo/storie/provenienza parziali. Il massimo intero non viene incrementato: nuova osservazione a revisione esaurita → `conflict`, non overflow.

### Replay e osservazioni ripetute

UUID e payload JSON identici restituiscono `replayed` con **lo snapshot originale**, anche dopo un'altra osservazione positiva con nuova revisione; nessuna nuova storia. UUID con payload diverso → `conflict`. Collisione UUID di un altro tenant nascosto da RLS → `conflict` controllato senza snapshot o dettagli stranieri. Replay ricontrolla sempre fiducia e autorità **correnti**; revoca/cambio autorità non è aggirato da una ricevuta precedente.

Un nuovo UUID a revisione corrente, anche se il ruolo è già true, registra una nuova osservazione verificata immutabile e incrementa la revisione condivisa. Non è autosync né un no-op silenzioso. Questa semantica è esplicita e compatibile con la sequenza ottimistica esistente.

Il tool attende il commit e rilegge esattamente richiesta, snapshot, revisione comune e ruolo dal DB prima di dichiarare successo. Esito rifiutato, errore SQL/TLS/timeout o ricevuta diversa → errore generico senza stderr DB/credenziali. Un errore di readback dopo un commit non dimostra rollback: conservare l'input e riprovare solo lo stesso UUID/payload; mai inventare un nuovo comando per risolvere un esito incerto.

## Letture e separazione societaria

Nessuna nuova UI di scrittura o route. Le API `edit-state` e `supplier-erp-identity` e la checkbox italiana già approvate mostrano il ruolo positivo. Autorità esterna mantiene disabilitato il controllo; gli ordinari PUT comune/ruolo restano **409 external**, con CSRF/azioni esatte invariati.

Dopo la proiezione, il tool esistente `owner-supplier-vendor-identity.py` può effettuare il suo distinto binding VendorId/VendorName societario. Nessuna mappatura implicita/creazione combinata: ruolo e binding restano comandi separati con audit e revisioni distinti. Un'altra società ha un'estensione indipendente; nomi/ID vendor non entrano mai in nome legale, anagrafica condivisa, edit-state o selettore generale.

**Limite funzionale da non nascondere:** i contratti acquisti `counterparties.purchase_suppliers` e `organization_access.purchasing_authority` attualmente rifiutano ancora `master_external`; D95 non ne cambia silenziosamente i gate né allarga i writer prezzi D91/D92. La lettura anagrafica del ruolo e il binding owner sono provati, **non** il percorso acquisti end-to-end con master esterno. Il successivo incremento dovrà risolvere coerentemente questi consumatori con evidenze proprie; R02/R04/R05 e #42/#44/#45 restano aperti. Nessun completamento generale D76, catalogo o ingestion dichiarato.

## Prove e cronologia

Evidenza privata: `/root/.local/share/enginia360/evidence/d95-external-supplier-projection-runtime/` (directory0700/file0600).

- `red-impact.log`: path nuovi non mappati/SQL privo di editor; `green-impact.log` e `green-wiring-scope.log` verificano selezione finita, wiring e fail-closed su executable sconosciuto; `red-finite-scope.log` prova il rifiuto dell'espansione accidentale ad architettura estranea.
- `red-positive.log`: controparte/binding/società/autorità esterna validi, comando esistente restituisce `external` invece di `applied`; non errore di compilazione o fixture. `green-positive.log`: proiezione positiva, revisione condivisa, letture approvate e edit ordinario ancora rifiutato.
- `red-replay.log` → `green-replay.log`: replay dopo osservazione successiva restituisceva `conflict` invece della ricevuta originale, poi snapshot esatto/storia non duplicata e collisione straniera controllata.
- `red-closed-input.log` → `green-closed-input.log`: campi extra e riferimenti non canonici accettati prima del controllo chiuso, poi rifiuto senza scritture.
- `red-cli-contract.log` → `green-cli-contract.log`: contratto owner positivo inizialmente non supportato dal precedente tool mapping; nuovo CLI chiuso. `red-cli-tls-readback.log` conserva anche il tentativo con il vecchio tool incompatibile: **non** prova comportamentale di tutte le future verifiche TLS/readback. I test TLS/receipt/redazione successivi sono regressioni; non RED retroattivo.
- `scripts/test-d95-projection.py`: SQL reale, trust/company/source/profile/version denials, revisione massima, audit/RLS/privilegi, rollback normale e trigger fixture-only di fallimento insert/deferred commit, replay/collisioni e corse su sessioni PostgreSQL fisiche distinte. Barriere osservate via `pg_stat_activity`, entrambi gli ordinamenti authority/binding/membership/shared revision e same/new UUID. I controlli già presenti al primo GREEN restano regressioni, non nuovi RED inventati.
- `run-ui01b-tests.py`: tutte le asserzioni originali del browser e dei readback sono preservate; la prova D95 si aggiunge **dopo** gli originali conteggi esatti e usa il secondo tenant sintetico esistente. Prima ruolo false/disabilitato, owner CLI TLS write+replay+readback, binding vendor separato, poi ruolo true/disabilitato in Chromium/OIDC/API e PUT409; pool4 e pool1 eseguiti. Nessun cambiamento al componente UI.

Incidenti non-pass preservati: il primo controllo integrato della storia comune ha rilevato che una nuova FK dal ledger D95 cambiava il rifiuto TRUNCATE da append-only a vincolo FK; corretta solo 0035 ancora non pubblicata, mantenendo atomico il collegamento tramite comando e readback senza quella FK e senza cambiare l'asserzione originale. La guardia delle partizioni è estesa per un solo nuovo suite D95: l'insieme ORIGINAL, disgiunzione, suite receipts e budget restano invariati, nessuna sostituzione di test storici. Primo tentativo runtime con umask077 rendeva i certificati pubblici non leggibili al postgres nonroot (setup, non RED); esecuzione con umask normale della fixture e log privati ha passato. Primo test corse riusava il valore fixture `IdentitySubject=revoked` contro un indice univoco; corretto con suffisso UUID proprio, non modifica produzione. Timeout read-only nell'elenco immagini Docker non è un test né un pass.

## Consegna, inventario e rollback

CI ordinaria PR-only e dispatch sul candidato esatto `full_architecture=false`: security/API compile boundaries, migrazioni/RLS/pool, TLS/OIDC/editor, diretto consumatore acquisti e offline guards/inventory. Skip non è pass. Budget/asserzioni storici e guardie autorità D1–D95 non ridotti; nessuna full architecture ora.

Inventario: 35 migrazioni / 80 CREATE / 9 schemi calcolati dal verificatore; nuova storia `audit_history`, eleggibilità **UNDECIDED**, nessuna migrazione legacy approvata. Nessuna dipendenza nuova, deployment, ambiente persistente, dato reale, provider call, acquisto o accesso SmartData. Drift host storico già noto (28 volumi, container estranei sostituiti) non riparato; confronti freschi di tutti gli ID/StartedAt/mount/volumi correnti prima/dopo le prove, accesso Enginia/Tailscale invariato.

Rollback operativo: revert rivisto del codice/tool/wiring, **non** DROP o riscrittura della migrazione/storia applicata; le versioni precedenti ignorano il ledger e non ricevono nuovi privilegi. Non annullare automaticamente un ruolo proiettato, rimuovere audit o ripristinare i nomi comuni. Correzioni richiedono un percorso successivo esplicitamente approvato; la slice non offre rimozione negativa.

D89 Esercizio **OPEN/BACKLOG**, non waived; FINAL eccezionale solo dopo completamento funzionale effettivo. D86 historical raw gap OPEN_NOT_REPAIRED, ERP residual UNKNOWN, stock precision e idempotenza provider non provata restano invariati. Parent responsabile di merge/chiusure/board; questa PR usa solo Refs.
