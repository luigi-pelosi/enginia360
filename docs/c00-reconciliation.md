# C00 — Riconciliazione finale e pulizia tecnica post-slice

## Perimetro

C00 riconcilia lo stato pubblicato della prima vertical slice e applica soltanto pulizie documentali/CI a comportamento invariato. Non autorizza UI01, nuove capability di dominio, modifiche API/schema, fiscalità reale, produzione, pilota, ambienti persistenti o deploy.

## Evidenza remota riconciliata

- B01–B14: PR #21–#35; B02 usa la decisione #22 e l'implementazione #23.
- Issue implementative #8–#20: chiuse e Project Completato.
- Baseline finale precedente a C00: main `fa972837684e67b9e5094025acdd54848a46c62a`.
- CI main finale B14: run 39518931794, success.
- D01 #3 e B00 #6: già chiuse/Completato con evidenza PR #2 e decisione D58; la chiusura è documentale/autorizzativa, non una validazione fiscale, contabile generale o produttiva.

## Stato runtime osservato prima delle verifiche C00

- Container in esecuzione: soltanto `enginia360-web-1` e `enginia360-api-1`, entrambi healthy.
- Tailscale Serve: solo tailnet 443 verso `127.0.0.1:9119`; nessuna porta manuale 8443–8447 attiva.
- Volumi Docker conservati: 25; nessun prune, mount, lettura dati o modifica.
- I container holder/proof fermati restano protetti; C00 non li rimuove né li avvia.

## Ispezione della pulizia tecnica

Sono stati ispezionati i 351 file tracciati, i 152 percorsi toccati fra B10 e B14, i duplicati byte-identici, i runner e i controlli CI, i riferimenti agli endpoint manuali e le righe stale con `git blame`.

Esito:

- nessun artefatto generato è tracciato; `bin`, `obj`, `node_modules` e `dist` presenti localmente sono ignorati;
- una cache Python `scripts/__pycache__` prodotta dalla verifica locale è stata rimossa e `**/__pycache__/`/`*.pyc` sono ora ignorati, senza toccare output applicativi;
- i `.csproj` e lock file identici dei progetti Contracts sono confini modulari intenzionali, non duplicazione eliminabile senza cambiare struttura/build;
- i runner e i test CI B10–B14 duplicano forma ma custodiscono invarianti, fault e selezione distinti; consolidarli ridurrebbe evidenza o allargherebbe il rischio, quindi non è stato applicato;
- gli URL/overlay/probe B02–B06 appartengono a runbook storici e guardie di sicurezza, non al runtime o al CI corrente; sono stati marcati esplicitamente come storici invece di essere cancellati;
- nessuna rimozione o refactor di codice runtime è risultata SAFE/CAREFUL senza rischio di contratto, comportamento o copertura. C00 evita churn.

La possibile archiviazione/rimozione degli asset manuali è RISKY ed è differita nella issue #37, in Backlog.

## Cambi applicati

- sezioni attive dei dossier 01/04/05/07/09 riconciliate, con archivio storico esplicito;
- header B10–B14 aggiornati con PR, CI exact-head, merge, issue e CI main finali;
- runbook manuali B02–B06 marcati come storici e URL non attivi;
- `AGENTS.md` portato ai vincoli post-slice: solo C00 autorizzato, UI01 non implicita;
- aggiunto `scripts/test-c00-consistency.py`, selezionato dalla CI, per fallire su metadati attivi stale, header remoti incompleti, runbook non marcati o perdita dei runner B02–B14.

## Limiti preservati

D42/D44/D45 restano circoscritti ai riferimenti dichiarati. OPE01–OPE05 non sono approvati dalla consegna tecnica. Nessuna garanzia di produzione, fiscalità generale, SdI, RPO/RTO, ERP reale o disponibilità è dedotta. Bootstrap, Tailscale, volumi, backup, configurazioni e segreti restano fuori dal cambiamento.
