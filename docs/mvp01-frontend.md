# MVP-01 — shell frontend Next.js isolata

Data di verifica: 2 novembre 2026. Refs #140. Solo abilitatore tecnico: **nessun dominio operativo completato e nessun rilascio operativo**.

## Contratto consegnato

`frontend/` è il percorso canonico del nuovo frontend, separato da `web/`, conservato senza modifiche come percorso storico. App Router Next.js con React/TypeScript, SSR dinamico effettivo, navigazione italiana dei sette domini, pagina di panoramica e pagine di indisponibilità reali. Nessun dato dimostrativo aziendale, selettore di identità, login finto, utente predefinito, sessione o collegamento API/DB/ERP. Il menu descrive il perimetro del prodotto, **non** concede permessi.

La navigazione è disponibile senza JavaScript tramite link SSR e fallback mobile `noscript`; con JavaScript il pulsante shadcn apre/chiude il menu responsive, `Escape` lo chiude e restituisce il focus. Skip link, focus visibile, `aria-current`, `aria-controls` e `aria-expanded`, layout desktop/laptop/mobile. Le pagine sconosciute rispondono 404. Le funzioni non consegnate dichiarano esplicitamente l'indisponibilità, senza pulsanti operativi ingannevoli.

Tutto il rendering è `force-dynamic`: le risposte HTML provate sono `private, no-cache, no-store, max-age=0, must-revalidate`. La shell non interpreta cookie, header tenant, query di identità o ruoli, non emette cookie e non carica dati riservati. Le prove con cookie/header non attendibili verificano che non vengano riflessi né diventino contesto. Non è una prova di isolamento di una futura sessione: trasporto sessione, CSRF, revoca, autorizzazione API e cache dati richiedono il contratto MVP-02 prima di introdurre letture autenticate. ASP.NET Core resta proprietario di dominio/autorizzazioni; nessun accesso PostgreSQL da Next.js.

## Dipendenze e fonti primarie

Pacchetti diretti con versioni esatte e lock npm v3 con integrità delle transitive:

| Dipendenza | Pin | Motivazione |
| --- | --- | --- |
| Next.js | 16.4.4 | Stable npm verificata; Node richiesto >=20.9, React 19 ammesso dai peer |
| React / react-dom | 19.3.1 | Stable npm verificata, versioni allineate |
| TypeScript | 5.9.3 | Linea compatibile effettivamente compilata; non adozione automatica della major 7.0.2 attuale |
| Tailwind / @tailwindcss/postcss | 4.3.4 | Stili compilati localmente, nessun CDN/font remoto |
| @radix-ui/react-slot | 1.5.0 | Primitive del Button shadcn |
| class-variance-authority / clsx / tailwind-merge | 0.7.1 / 2.1.1 / 3.7.0 | Varianti, composizione classi e merge shadcn |
| @playwright/test | 1.58.2 | Allineato alla versione del browser container già pin nel repository, non dichiarato latest |
| tsx | 4.23.15 | Esecuzione del test React SSR con node:test senza mock del componente |

Tipi esatti: @types/node 24.10.0, @types/react e @types/react-dom 19.3.0. Next/React/shadcn e utility MIT; TypeScript/Playwright Apache-2.0 (licenze verificate nei metadata npm). Nessun servizio commerciale o Vercel richiesto: l'output standalone esegue realmente `node server.js` in container Node, come previsto dalla documentazione self-hosting. L'immagine non è un export HTML statico.

Fonti consultate e scaricate il 2 novembre 2026:

- Next installazione/requisiti: <https://nextjs.org/docs/app/getting-started/installation>.
- Next self-hosting: <https://nextjs.org/docs/app/guides/self-hosting>.
- Next advisory ufficiali: <https://github.com/vercel/next.js/security/advisories> (API: `gh api 'repos/vercel/next.js/security-advisories?per_page=100'`, 72 record restituiti).
- shadcn Next e Button: <https://ui.shadcn.com/docs/installation/next>, <https://ui.shadcn.com/docs/components/button>.
- Metadata esatti: `https://registry.npmjs.org/<package>/<version>`; peer/engines controllati, non versioni inventate da memoria.

`components/ui/button.tsx`, `card.tsx`, `badge.tsx` sono **sorgenti reali** dal registry ufficiale `https://ui.shadcn.com/r/styles/new-york/{button,card,badge}.json`, non componenti etichettati shadcn senza derivazione. Sola modifica ai file originali: import utility relativo; CSS token Tailwind v4 nel progetto. `components.json` conserva convenzioni di generazione; `shadcn-LICENSE.txt` conserva MIT. Hash SHA-256 delle risposte JSON originali:

- button: `4d8f39c3bd25e630b5962667722e8707e7b18122ad6842a5c22acf8a3ff9f93a`
- card: `e6b5055ff2e674007d65df1b1e13f7e18eaba86efda60641c02ee6abaec337ce`
- badge: `ce3f01e6d6785477a7fee003bd7144d7d11e7c5e8e31b3373de15138349361e6`

### Sicurezza dipendenze: risultato e limiti

`npm audit --audit-level=low` su dipendenze incluse dev: **0 vulnerabilità riportate**, exit 0; anche `npm ci` del Dockerfile esegue l'audit senza soppressioni. Questo non significa assenza assoluta di vulnerabilità. Gli advisory ufficiali del 14 ottobre GHSA-2464-fhr4-w9xw, GHSA-673q-mjm6-r5xr e GHSA-p3m5-59mp-jv5r indicano patch Next 16.4.1; il pin 16.4.4 è successivo.

Il feed ufficiale contiene inoltre record con metadata patch incompleti (`16.3.?`, `15.5.?`) e range larghi: non sono stati occultati né trasformati in attestazioni di sicurezza. I casi GHSA-39w2-rjm5-chcv (solo `next dev`), GHSA-4jqv-mc3x-m676 (Pages Router SSG/ISR) e GHSA-mcj8-r9mp-w47p (root catch-all con SSG/ISR) non corrispondono a questa shell di produzione App Router dinamica senza catch-all, SSG/ISR, Server Actions o funzioni `use cache`. La prova non avvia `next dev`. Prima di introdurre quei meccanismi o pubblicare un ambiente occorre riesaminare gli advisory correnti e i loro range, anche quando npm audit è verde. Nessuna deroga ai gate operativi o promessa di esposizione sicura è implicita.

## RED → GREEN e prove locali

Evidenze integrali conservate fuori Git in `/root/.hermes/cache/scratch/mvp01-evidence/`; non sono output inventati o versioni ricostruite dopo l'implementazione.

1. Prima dei sorgenti applicativi: `npm test` nel container Node 24, un test del rendering React SSR. Il baseline esplicito rende `null` solo se il modulo shell non esiste; il test non fallisce per un errore d'importazione. RED: assertion `SSR must expose usable domain navigation`, actual stringa vuota, exit 1. Dopo implementazione lo stesso test importa/rende il vero componente: 1 test PASS, exit 0.
2. Selettore nuovo: `python3 -I scripts/test-mvp01-impact.py` RED perché i percorsi frontend non avevano mapping (2 errori di contratto attesi), poi GREEN 4 test. Mapping finito, mix con produttori storici conserva i consumer, percorsi eseguibili non mappati falliscono chiusi.
3. Prima acceptance Chromium: HTTP/SSR passava, ma la ricerca di un heading di indisponibilità falliva perché CardTitle shadcn rende un div. Corretto il markup applicativo aggiungendo un vero h2, senza indebolire il test. Acceptance successiva: **4 test PASS** in 14.4s: HTTP su panoramica e sette pagine, no-JS, stato assente/404, keyboard/skip link/menu/Escape e layout 1440×900, 1366×768, 390×844; nessun errore pageerror o overflow orizzontale rilevato. Screenshot desktop/laptop/mobile riletti visivamente.
4. `npm run build`: PASS, route `/`, `/_not-found`, `/domains/[domain]` dinamiche SSR; `npm run typecheck`: PASS; dependency audit: PASS come sopra.
5. Tutti i 21 comandi di guardia dell'impact job eseguiti localmente, inclusi i relativi comandi concatenati: PASS. Guardie MVP baseline 3 test + reset impact 5 test + frontend impact iniziali 4 test (poi 5 con regressione del wiring CI): PASS. Non sono state modificate le suite storiche per farle passare.

Log e SHA-256:

| File | SHA-256 |
| --- | --- |
| `red-shell.log` | `17f892a633f5d46e0db852a2c82798462b259db4c014f8c0b61f515bb44eb325` |
| `green-shell.log` | `333b1f51433cc2aa7fa9c88a79d159f79eba1bb8d4d0aba9cfbc5d6b218edc52` |
| `red-impact.log` | `ec86e739017e96db0f2b88a274a926395168f7cf07cf72320b07d259c577a3ca` |
| `green-impact.log` | `6bbfa003c3e16da4dd463534a1510855b4d6bf8d516d3670f5b342cc5d1135fe` |
| `red-browser-heading.log` | `9eb0ef0c087ce6521f23b13a0294cff0ff43f77e5ffef37b1252b91d0d8d7cd8` |
| `runtime-green.log` | `30f7e4507fd01e57e8c30894b49bb7446288e5a64f5d888e5c28407eace8735c` |

I primi tentativi d'installazione hanno incontrato cache npm tmpfs insufficiente (256 MiB) e ownership non allineata: non sono stati contati come RED comportamentale. Installazione riuscita con cache effimera 1 GiB e utente nonroot; il runner finale installa in image build, non nel repository host.

## Runner, isolamento e CI

Dalla radice del checkout:

```sh
python3 -I scripts/test-mvp01-impact.py
python3 -I scripts/run-mvp01-tests.py --build-only --evidence-dir "$SCRATCH/mvp01-build"
python3 -I scripts/run-mvp01-tests.py --evidence-dir "$SCRATCH/mvp01-runtime"
```

`$SCRATCH` deve essere una directory temporanea privata già scelta dall'operatore, non `/tmp`, configurazioni o servizi conservati. Il Dockerfile usa immagini Node 24.22.0-alpine3.24 e Playwright v1.58.2-noble con digest esatti. Build/install nonroot; runtime app e Chromium nonroot, rootfs read-only, cap-drop ALL, no-new-privileges, pids 256, memoria 1 GiB, 2 CPU, log 2 MiB × 1, tmpfs `/scratch`, rete effimera `--internal`, **nessuna porta host**, volume o credenziale. Solo l'output sintetico ha mount scrivibile. Nessun backend/database viene avviato. Hardening e healthcheck riletti in `runtime-green/container-inspect.json`; health `healthy`. Rimozione esatta dei due container, rete e tag temporanei verificata sia dopo failure browser sia dopo successo; niente prune globale.

CI automatica resta solo `pull_request`. Con questo insieme finito: `impact`, `affected-mvp-offline`, `affected-frontend`; `affected-frontend-runtime` richiede dispatch esplicito. Gli altri job runtime storici non sono selezionati. Check/frontend su head PR esplicito; dispatch su commit del ref con `comparison_base` SHA esatto e `full_architecture=false`. Il job runtime non è dichiarato provato da uno skip. Il suo artefatto `mvp01-<head SHA>` conserva screenshot, inspect, log browser/app e risultati/tracce disponibili per sette giorni. Le prove exact-head remote e gli URL sono registrati nel report della PR dopo esecuzione, non anticipati qui.

## Limiti e rollback

Nessuna API/dato/identity federation, nessuna autorizzazione o dominio gestionale implementato; menu pubblico descrittivo, non menu autorizzato operativo. Chromium e viewport campionati non sono certificazione WCAG né prova Safari/Firefox/touch; nessuna prova di sessione multiutente o uso reale. Nessun CSP autenticato, session bridge o login collegato prima del relativo contratto. Nessun deploy, acquisto, dato reale o modifica a backend/vecchio web, bootstrap, Tailscale 443→9119, database, migrazioni e volumi conservati.

Rollback del solo incremento software: revert della PR e rimozione dei suoi soli artefatti effimeri. Non cambia la composizione attiva dei servizi e non richiede rollback dati/migrazioni. Checkpoint successivo verificato dal coordinatore: MVP-01/#140 completato con PR #151, head `e3102e41a34dddff63faf033b7c0c56935297635`, PR CI `41541966173` (3 job/38 step) e dispatch `41541963004` (4 job/44 step), tree candidato/main `1009876b5368aa30fa6ace3d20c1e226e57abbf2`. Artefatto `13186713984`, quattro test browser PASS riletti dal coordinatore. MVP-02/#141 ora in corso, non completato dalla shell. Le aspettative storiche e le evidenze sopra rimangono invariate.
