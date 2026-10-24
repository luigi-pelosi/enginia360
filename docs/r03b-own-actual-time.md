# R03.b — consuntivo manuale del proprio tempo (primo vertical)

Stato: implementato sul branch di consegna, #72 (sottoissue di #43; #5 e #43 restano aperte). Decisione D78 già registrata: tempo effettivo manuale proprio per lavorazione (data, durata, nota, correzioni tracciate), senza ore fatturate o stock automatici. Nessuna nuova policy di business: i limiti sotto sono tecnici o di perimetro del primo profilo.

## Contratto

- Azioni esatte, non dedotte da altre: `workshop.actual-time.read-own`, `workshop.actual-time.write-own`, più `workshop.orders.read`. Capability workshop spenta: nuove scritture negate; storico proprio e replay esatto restano leggibili con grant valido.
- Attore da `NameIdentifier` verificato + membership/tenant risolti dal server, mai dal payload (campi sconosciuti rifiutati). Ogni lettura/storia/ricevuta/correzione filtra tenant + membership proprietaria: un altro operatore dello stesso tenant, anche con tutti i grant propri, riceve 404.
- `POST /api/v1/workshop/orders/{id}/actual-time/own`, `.../own/{entryId}/corrections`, `GET .../own` (cursore UUID, max 50), `GET .../own/{entryId}/history` (max 50). Durata: secondi interi 1…Int32.MaxValue (limite tecnico, non turno/giornata); data ISO `yyyy-MM-dd` 0001–9999; note ≤500 UTF-16 senza controlli. Nessun DELETE/void; correzioni = nuove versioni immutabili con attore, timestamp server, CommandId e ricevuta originale.
- Il gruppo (`WorkingGroupId`) resta quello salvato; revisione propria separata da `CommercialRevision`.
- Solo commessa aperta per nuove registrazioni e correzioni (limite del primo profilo, non divieto di business universale); lettura propria e replay esatto restano dopo la chiusura tecnica.
- Nessun effetto su righe, quantità Service, q6, stock, outbox, billed hours, snapshot Billing/Accounting/esterno.

## Persistenza (migrazione 0022, append-only)

Cinque tabelle Workshop con RLS forzata: stream, entries, versions, commands (tenant + `app.workshop_actor_membership_id`) e `actual_time_group_references` (solo tenant, nessun dato personale) che impedisce `RemoveEmptyGroup` anche quando il tempo è di un altro operatore. Trigger append-only, catena versioni/revisione e completezza differita (versione ↔ ricevuta ↔ entry ↔ riferimento). Serializzazione sul lock canonico d'ordine già usato da editor/chiusura.

## Prove

`scripts/run-r03b-tests.py` (pool 4 default, `R03B_POOL_SIZE=1`): Chromium reale, CA fidata, OIDC, nginx→API TLS, PostgreSQL; due operatori dello stesso tenant + tenant esterno; barriere SQL su connessioni fisiche distinte; risposta persa con retry byte-identico; consumer diretti (chiusura → Billing interno → Accounting; snapshot esterno senza chiamate ERP). Test unitari UI `OwnActualTime.test.tsx`; guard `scripts/test-r03b-impact.py`, `test-r03b-migration.py`, TERM `test-r03b-lifecycle.py`. CI: job `affected-r03b` solo su dispatch exact-head.

## Limiti e rollback

Non implementati: lettura di altri operatori, pianificazione, timer, assegnazioni, annullamento/DELETE, correzioni post-chiusura. Rollback: ripristino applicazione compatibile con il solo comando di scrittura disattivato (capability/grant); dati e migrazione 0022 restano, nessuna down-migration distruttiva. Nessuna verifica fiscale/legale; nessun ambiente reale.
