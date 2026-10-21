# UI01.a — verifica del prototipo editor (dati sintetici)

Incremento: UI01.a (issue #5). UI01.b resta dipendente da R00 e non è consegnata qui. Nessuna implementazione R00, nessun endpoint nuovo, nessun dato reale, nessun deployment o ambiente persistente.

Contratto congelato prima dell'implementazione: `docs/ui01-prototype-contract.md`, pubblicato anche come commento su #5 prima del codice di produzione.

## Dipendenza adottata

`antd` **6.6.7**, MIT. Verifiche effettive del 21 ottobre 2026:

- `npm view antd version license peerDependencies --json` → `6.6.7`, `MIT`, peer `react`/`react-dom` `>=18.0.0`.
- Documentazione ufficiale: changelog v6.6.x su `https://ant.design/docs/react/introduce/`; `https://ant.design/docs/react/migration-v6/` conferma «antd@6 requires React >= 18»; `https://ant.design/docs/react/customize-theme/` documenta `theme.compactAlgorithm`.
- Licenza letta dal tag esatto: `gh api repos/ant-design/ant-design/contents/LICENSE?ref=6.6.7` → testo MIT.
- Limite: `https://ant.design/...` non è raggiungibile in fetch diretto dalla rete di lavoro (HTTP 403); le pagine sono state verificate tramite risultati/estratti di ricerca e la licenza tramite l'API GitHub al tag. Versione e licenza del pacchetto installato provengono dal registry reale, non da memoria.
- Pin esatto in `web/package.json` (`"antd": "6.6.7"`), lock rigenerato intenzionalmente. `npm audit --audit-level=high` → `found 0 vulnerabilities` (159 pacchetti auditati).
- Nessun secondo design system, nessuna griglia aggiuntiva, nessun ProComponents/Umi/template commerciale. Icone `@ant-design/icons` non introdotte.

## Perimetro e isolamento

- Entry opt-in separata: `web/ui01.html` + `web/src/ui01/main.tsx`, build `npm run build:ui01` (config `vite.ui01.config.ts`, output `dist-ui01/`, ignorato da git).
- `web/index.html`, `web/src/App.tsx`, `web/src/main.tsx` e tutti i flag `VITE_Bxx` non sono stati modificati: il bundle pubblico di default non importa il prototipo né antd (build default 222.08 kB, invariata nella composizione; il prototipo è 489.39 kB separato).
- Guardia eseguibile `scripts/test-ui01-ci.py`: il prototipo è costruito in CI, antd resta pinnata, la entry pubblica non referenzia `ui01`, le build private Bxx restano presenti. Osservato RED prima della modifica di `ci.yml` (`AssertionError: CI must build the UI01.a prototype explicitly`), poi GREEN.
- Nessuna chiamata di rete, autenticazione, tenant context, persistenza, localStorage o effetto di magazzino. Il ricaricamento perde le bozze: è un prototipo, non uno stato autorevole.

## RED → GREEN per comportamento (un test alla volta)

| # | Comportamento | RED osservato | GREEN |
| --- | --- | --- | --- |
| 1 | Render contesto/gruppi/q6/stati senza fetch | `Unable to find an element with the text: Prototipo — dati sintetici` | 1 test |
| 2 | Modifica esplicita, focus sulla descrizione, annulla senza emettere bozze | `Unable to find a label with the text of: Descrizione service-a` | 2 test |
| 3 | Applica con stringhe q6, identità riga/gruppo stabile, riepilogo fornito immutabile e marcato non aggiornato | `Unable to find a label with the text of: Quantità part-a` | 3 test |
| 4 | Rifiuto di decimali non invarianti senza arrotondamento, errore associato/annunciato e focus | 8 fallimenti su `aria-invalid` | 11 test |
| 5 | Descrizione obbligatoria 1–500 caratteri | 3 fallimenti sul messaggio `1–500` | 14 test |
| 6 | Escape annulla, ripristina freschezza del riepilogo e focus | 1 fallimento | 15 test |
| 7 | Ricerca/selezione da catalogo locale dentro la riga attiva | 1 fallimento | 16 test |
| 8 | Veicolo e pagante indipendenti, contesto comprimibile senza perdere le selezioni | 1 fallimento | 17 test |
| 9 | Stati loading/error/vuoto come stati UI, senza contenuti inventati | 2 fallimenti (`Nessuna lavorazione fornita`) | 19 test |
| 10 | Documento lungo sintetico 100 righe, ultima riga modificabile, fixture senza dati personali | `Failed to resolve import "./syntheticFixtures"` | 22 test |

Comando: `docker run --rm -v "$PWD:/source" -w /source/web node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f npm test`.

## Esecuzioni locali effettive

- `npm test` (intera suite web, incluse le regressioni Bxx esistenti): **Test Files 13 passed | 12 skipped (25); Tests 57 passed | 12 skipped (69)**. Gli skip sono i test runtime Bxx preesistenti, condizionati a basi runtime, non disattivati da questa consegna.
- `npm run build` (default, include `tsc --noEmit`): `✓ built in 463ms`, `dist/assets/index-yPgjVR5f.js 222.08 kB`.
- `npm run build:ui01`: `✓ built in 975ms`, `dist-ui01/assets/ui01-BHN3YNAo.js 489.39 kB`. Avvisi rollup `MODULE_LEVEL_DIRECTIVE "use client"` da antd: build riuscita, nessun SSR usato dal prototipo.
- `npm audit --audit-level=high`: `found 0 vulnerabilities`.
- Guardie Python eseguite: `test-ui01-ci.py`, `test-c00-consistency.py`, `test-productization-consistency.py` (13 test OK), `test-ci-runtime.py` (3 test OK), `test-b05-ci.py`, `test-b10-ci.py`, `test-b14-ci.py`, `git diff --check`.
- Non eseguiti localmente: test di integrazione API .NET, Compose health e smoke HTTP; restano coperti dalla CI remota su questo head, che non è modificata nelle sue suite storiche.

## Prove browser reali (effimere, locali)

Server effimero: container nginx su `127.0.0.1:9321` che serve solo `dist-ui01`, rimosso al termine (`docker rm -f ui01-proto`, verificato). Nessun URL pubblico, nessuna modifica a Tailscale/bootstrap/volumi.

- Desktop 1920×1080 (`window.innerWidth/innerHeight` = 1920/1080): 100 pulsanti `Modifica` presenti, colonna contestuale 272 px, riepilogo con `bottom = 1080`.
- Scorrimento del documento (`.ui01-document` scrollTop 3171): riepilogo ancora a `bottom = 1080` e ultima riga `line-sintetica-100` raggiungibile (rect y 960). «Persistente» significa visibile durante lo scorrimento, non memorizzato.
- Tastiera/focus reali: focus sul trigger `Modifica line-sintetica-099` → click → focus su `description-line-sintetica-099`; ordine dei controlli nella riga: descrizione, ricerca catalogo, risultati, quantità, prezzo.
- Validazione reale: quantità `1,5` → `aria-invalid="true"`, focus su `quantity-line-sintetica-099`, alert «Usa un valore non negativo, punto e massimo 6 decimali (12 cifre intere).», riepilogo marcato «Riepilogo non aggiornato · modifiche locali».
- Escape: editor chiuso, focus restituito a `Modifica line-sintetica-099`, riepilogo di nuovo «Proiezione fornita · invariata».
- Portatile 1366×768: viewport misurato 1366/768, riepilogo a `bottom = 768`, editor di riga interamente visibile (rect 488–641) senza coprire le righe.
- Stati vuoto/caricamento/errore catturati a 1366×768.

Screenshot (solo dati sintetici, fuori dal repository per non versionare binari generati): `/root/.hermes/cache/scratch/ui01-evidence/01-desktop-1920x1080-long.png`, `02-desktop-1920x1080-row-edit-validation.png`, `03-desktop-1920x1080-scrolled-sticky-summary.png`, `04-laptop-1366x768-long.png`, `05-laptop-1366x768-row-editor.png`, `06-laptop-1366x768-empty.png`, `07-laptop-1366x768-loading.png`, `08-laptop-1366x768-error.png`.

## Fedeltà al riferimento legacy

Lo screenshot legacy fornito è stato osservato solo per la struttura: colonna contestuale stretta a sinistra, lavorazioni ripetute con griglie dense, toolbar locali, riepilogo inferiore persistente. Nessun dato di cliente, veicolo, documento o importo è stato copiato. La fedeltà è compositiva, non pixel-identica, e non dimostra il comportamento del sistema legacy.

## Limiti dichiarati

- Prototipo isolato con soli dati sintetici: nessuna persistenza, nessun comando backend, nessuna autorizzazione, nessun effetto su giacenze o documenti.
- Il riepilogo è una proiezione fornita: nessuna aritmetica fiscale in JavaScript. Le modifiche locali lo marcano non aggiornato; non esiste un ricalcolo simulato spacciato per risposta.
- Le validazioni di riga sono vincoli di input del prototipo, non policy fiscali, di sconto o di magazzino.
- `Received` è esplicitamente distinto da `Confirmed`; prenotato, prelevato, in preparazione, installato/consumato e carcassa restano fatti separati e di sola lettura.
- Accessibilità verificata solo sui percorsi provati (etichette, `aria-invalid`/`role=alert`, focus, Escape): nessuna conformità WCAG dichiarata. Nessuna misura di prestazioni oltre l'uso osservato con 100 righe; nessuna virtualizzazione introdotta.
- Il prototipo non dimostra alcun endpoint: `B05TestApp` resta add-only per una singola Service/Part, quindi editing multi-gruppo e modifica righe restano un gap dichiarato fino a UI01.b dopo R00.

## Rollback

Rimuovere in una PR tracciata: `web/src/ui01/`, `web/ui01.html`, `web/vite.ui01.config.ts`, gli script `build:ui01`/`dev:ui01`, la dipendenza `antd` con rigenerazione del lock, lo step CI «Opt-in UI01.a synthetic prototype build» e `scripts/test-ui01-ci.py`. Nessuna migrazione dati, nessun rollback runtime: schema, bootstrap, Tailscale e volumi conservati non sono toccati.
