# MVP05 / #144 — FINAL LOCAL VALIDATION COMPLETE; REMOTE DELIVERY PENDING AT COMMIT

Fase finale autorizzata dopo il completamento dell'intero punto. Il queue seriale
corretto ha concluso 21/21 stage con EXIT=0: catalogo pool4/pool1, controparti,
onboarding, membership, ruoli, organizzazione UI/API, autorità, foundation,
browser comune/lifecycle e fixture nonroot. I 20 TRX runtime contengono 274 test
eseguiti e riusciti, zero non-eseguiti/skip. Per ciascun pool catalogo: 21 SQL
catalogo, 23 SQL prezzi storici e 27 API, con browser OIDC/JWT, SSR/noJS e nove
screenshot. L'ispezione degli artefatti verifica snapshot Part/Service, prezzi
societari invariati, rilettura IWorkshopCatalog dopo edit, retry esatti e hydration.

Evidenze progressive in `/root/.hermes/evidence/enginia360-mvp05/final/`:
`local-final-proof.json`, `runtime-progress.json`, `executed-ledger.json` e gli
inspection JSON per pool. Ogni stage conserva comando, manifest SHA256 dei
sorgenti, START/EXIT/END, log e contatori effettivi. Le esecuzioni finali condividono
source hash `e73d00611b2a3cba7ec861998205f1f3a9e818cc65276c3580d11eb51d102067`;
la successiva modifica di questo riepilogo è solo documentale. I NONPASS precedenti
restano conservati e non sono convertiti in pass. I 17 skip opt-in del fast API
sono esplicitamente non-evidenza runtime.

Rilettura finale: i tre ID/StartedAt/Mounts protetti originari invariati; 18 project
osservati del queue assenti dopo cleanup esatto. Nessun cleanup del vecchio project
PostgreSQL protetto o di altri prodotti. Le 42 migrazioni pubblicate, i 95 record
inventario precedenti e i 20 lockfile sono preservati; 0043 resta la sola aggiunta.

Al momento del commit la consegna remota deve ancora essere verificata: PR con
Refs #144, CI PR-only ed exact-head dispatch full_architecture=false, tutti i job e
step richiesti realmente eseguiti, ZIP/digest/ispezione di ogni artefatto. Gli ID
run/head/tree e la rilettura finale vengono aggiunti alla PR e al ledger esterno
senza un inutile commit successivo. Nessun merge, deployment o readiness operativo
è dichiarato; il coordinatore conserva merge e aggiornamenti issue/Project.

Incidenti e correzioni finali osservati:
- Ripristinato il riferimento storico al contratto MVP04 nei riepiloghi correnti,
  conservando i marker completi verificati e tutte le mutazioni negative D97/D98.
- `CatalogModule.cs` è un producer condiviso: conserva i consumer legacy se cambiato
  da solo; la composizione finita completa resta mirata. Nessun producer ignoto ignorato.
- Browser pool4 iniziale NONPASS: `getByLabel('Tipo', exact)` includeva il testo delle
  option. Probe Chromium pinned: label esatta 0, combobox con nome esatto 1.
  Corretto soltanto il locator esatto; nessun timeout o controllo di sicurezza ridotto.
- Aggiunte prove reali del CLI owner per entrambi i domini: applied/replayed,
  TLS rifiutato e diniego corrente anche con riga storica esatta ancora presente.
- Aggiunte regressioni esplicite per snapshot commerciali persistiti Part/Service,
  rilettura della porta storica dopo edit e ordinamento inverso revoca/effetto.
  Le aggiunte non sono presentate come RED originale; il ledger registra l'esecuzione.
- Due suite hanno conservato NONPASS per deriva di container di un altro progetto:
  tutti gli assertion SQL/browser erano riusciti ma i vecchi confronti globali o
  l'inspect di un ID esterno rimosso fallivano. Il guard comune ora verifica ID,
  StartedAt e Mounts di ogni container Enginia360 preesistente, esporta la deriva
  globale separatamente e non legge Config/Env di altri prodotti. Invariati volumi
  e cleanup esatto project/config. Fixture MVP correnti, foundation e browser sono
  i soli consumer modificati; i producer standalone/misti restano selezionati.
  Probe Docker sintetico reale e negativi unit verificano rimozione esterna ammessa
  e rifiuto di perdita/restart/mount alterati protetti. Manifest corrente: 52 path,
  inclusi i 45 originali, sei runner condivisi e il probe lifecycle espliciti nel selettore.
  Rimossi i vecchi prefix catch-all run-r00/test-r00: restano nove file noti esatti,
  i near-prefix ignoti rifiutati e i consumer originari per modifiche standalone/miste.
- I payload CSRF negativi sono validi: token assente e alterato devono restituire
  esattamente csrf_invalid senza righe. Artefatti registrano route/metodo, byte dei
  tre retry, hash e readback SQL prima/dopo di prezzi e snapshot legacy, non dati inventati.
- Guarded catalog pool4 NONPASS conservato: 21 SQL catalogo, 23 SQL prezzi e
  27 API senza skip riusciti, poi il browser ha inviato il form SSR come GET prima
  dell'hydration (`/catalog?label=...`). Riprodotto con un nuovo assertion SSR
  effettivamente fallito; corretto soltanto il gating dei comandi fino a hydration,
  lasciando ricerca/selezione native disponibili. Unit/build/typecheck pinned:
  31 test riusciti. Il browser finale ritarda il vero chunk catalogo e verifica
  form disabilitato prima, abilitato dopo hydration; entrambe le esecuzioni runtime finali riuscite.
- Il solo smoke read-only del deployment protetto si è fermato sul marker lang=it
  della pagina iniziale; NONPASS conservato, nessuna diagnosi o modifica del servizio.
  Non è una prova del candidato isolato né readiness operativa.

## Dipendenze e limiti di sicurezza del framework

Lock e image pin restano quelli della baseline. La verifica pinned senza cache ha
eseguito npm ci, audit con soglia low (zero vulnerabilità), 30 unit test, build e
typecheck; anche i due audit NuGet source/test risultano privi di advisory riportati.
Questo non equivale a clearance generale. Il [rilascio Next del 3 novembre 2026](https://nextjs.org/blog/november-2026-security-release)
annuncia 16.4.5. La valutazione finita del candidato 16.4.4 osserva assenti i prerequisiti
segnalati: Cache Components/use-cache/unstable_cache, Edge cookie setter, route che
inoltrano Response inalterate, immagini/upload o sorgenti remote consentite. Le route
correnti sono dinamiche/private-no-store; nessun asset pubblico immagine è presente.
Evidenza e inventario: `next-security-applicability.md` nella directory finale esterna.
Rivalutare e aggiornare prima di abilitare quei modi o di un'esposizione operativa;
nessuna readiness o rinuncia agli audit è dichiarata.

## Checkpoint storico del writer sorgenti — SOURCE COMPLETE, UNEXECUTED

Nessun test, build, typecheck, audit, installazione npm, migrazione, servizio,
smoke o CI eseguito da questo writer. Nessun commit/push/PR, scrittura issue/Project,
merge o deployment. Non è una consegna verificata né una dichiarazione di readiness.
I diagnostici automatici del tool di editing non sono esecuzioni di acceptance:
segnalano moduli frontend non installati nel worktree e helper dinamici nei test Python.

Base: `03872078b2d77dcf6754700729e41fcf5567d051`; branch `feat/mvp-catalog-management`.
Il [contratto finito](mvp05-catalog-contract.md) è stato scritto prima del codice.
Il checkpoint progressivo esterno è `/root/.hermes/evidence/enginia360-mvp05/source-checkpoint.json`.

## Criteri implementati nei sorgenti (non prove eseguite)

| Criterio | Implementazione / sorgenti delle prove finali |
| --- | --- |
| Articolo e servizio senza Workshop/ERP | `Catalog:Enabled`, `AddCatalog`, management endpoints; `CatalogManagementTests` disabilita Workshop/Counterparties e usa bearer firmato. Runner Next usa `Workshop__Enabled=false`. |
| Identità unica tenant-wide | Riuso `catalog.items`, `Id` e `Version`. Contratti tipizzati `Article|Service`; mapping esplicito `Article↔Part` soltanto alla frontiera. Porta storica `IWorkshopCatalog` mantenuta e riletta nel test API. Nessun duplicato canonico. |
| Lista, ricerca, selezione, dettaglio, creazione e modifica | SQL read/command, `/catalog` SSR privato e workspace italiano; entrambi i kind in test SQL/API/browser OIDC e JWT. Solo label; tipo esplicito in creazione e non riclassificato in edit. Nessun UUID manuale nei form. |
| Prezzi/stock/customizing separati | Nessun writer nuovo di prezzi/quantità; test SQL mantiene intatte due storie prezzo societarie dopo edit canonico, rilegge versioni correnti e snapshot storici; runner esegue anche `PriceSqlTests`, `SupplierPurchasePriceTests`, `BusinessMembershipFenceTests`. |
| RBAC configurabile reale | Tre azioni `catalog.shared.read/create/edit` in catalogo ed editor D97; scope tenant esplicito null/null/null non wildcard. Algoritmo role precedente preservato salvo whitelist; test confronta la funzione esatta e mantiene i precedenti branch warehouse/company. |
| Revoca corrente / no TOCTOU | SQL owning transaction 777036, binding issuer/subject/internal ID esatto, membership enabled, assegnazioni/ruoli/permessi attuali prima del replay; witness RR già presente su role objects mantenuto. Test revoche aperte OIDC/JWT, race permission/assignment/role/binding/membership e vecchio snapshot RR. |
| Autorità singola ed esplicita | Nessuna inferenza dal setup counterparties. `catalog.authority_history` separata perché il vecchio CHECK/unique/funzioni supportano solo counterparties: non alterare quella storia per attribuirle semantica nuova. CLI owner esistente con domain catalog esplicito, TLS verify-full, owner nonprivilegiato, binding/membership enabled bloccati e witness corrente. Missing/external/stale rifiutano. Fonte/profile/versione verificati anche prima del replay. |
| Audit, revisioni, retry | Audit privato immutabile atomico, payload JSON tipizzato esatto, snapshot prima/dopo, membership/binding hash minimizzati. Optimistic Version condivisa, niente merge automatico. SQL insert/deferred-commit rollback di create/edit per entrambi i kind; concorrenza e max revision controlled-conflict. |
| CSRF / SSR / cache / incertezza | Cookie corrente soltanto a HTTPS backend fisso; force-dynamic/no-store, ingress privato anche su rifiuto API. CSRF prima del POST, frozen route/UUID/body e navigazione, replay storico seguito da GET autorevole. Browser: risposta persa → CSRF rifiutato → replay/GET fallito → retry byte-identico; noJS ricerca/selezione/dettaglio e screenshots responsive per entrambi i kind. |
| Migrazioni e inventario | Solo nuova 0043; manifest e due nuove classificazioni authority/security evidence, eligibility UNDECIDED. Guard finale confronta tutti i 42 byte stream pubblicati, prefix manifest e record inventario precedenti; classificazione runtime SD/ACL/RLS e privati nel runner. |
| CI finita | Nuovo output/job `catalog_management`, due pool mirati con scratch privato e artefatti exact-head. Mapping finito, mixed producer conserva consumer originari, unknown/near-prefix rifiutati. I runner precedenti ammettono esattamente i due nuovi SD user-derived, senza ampliare gli envelope worker. |
| Stato predecessore | Header/carta/baseline/piano/backlog/assessment riconciliati con PR168 e prove del coordinatore; D97/D98 documentali e cronologia conservati. Nessuna nuova verifica remota è attribuita a questo writer. |

## Confini e rischi noti

- Stato storico del writer: tutti i sorgenti e harness dovevano ancora compilare ed essere eseguiti. Questo punto è superato dalle prove finali effettive riportate all'inizio; resta conservato, non è un limite corrente.
- Setup owner esplicito catalogo richiesto prima di scrivere. La prima società esplicitamente scelta nella decisione resta la provenienza RegisteredCompanyId, non uno scope di visibilità o di prezzi. Non importare o cambiare automaticamente ambienti storici.
- Un vecchio readback immutabile non basta per il successo del CLI: ora sono richiesti esito applied/replayed e readback esatto anche sul percorso counterparties già supportato; i normali payload/SQL di quel dominio non cambiano.
- Recupero dell'esito incerto soltanto nella pagina aperta; reload forzato/login/chiusura non conservano il comando. Nessuna cancellazione, disattivazione, tassonomia, variante, riclassificazione, listino, costo, fiscalità o motore documentale/stock aggiunti.
- La suite prezzi storica è un test di compatibilità dei consumer già esistenti, non consegna di nuovi prezzi, acquisti o integrazioni ERP. Feature operative esterne e gate di produzione rimangono separati.
- Nessun lock/image pin modificato. Servizi, volumi e Tailscale443→9119 protetti non toccati.

## Comandi della fase finale — preparati, NON ESEGUITI

Eseguire dal worktree esclusivo; evidenza fuori repository e TMPDIR sotto scratch.
Questo checkpoint conclude l'intera implementazione #144: il coordinatore prosegue
con la fase finale autorizzata, senza una nuova approvazione ordinaria del perimetro.
Non sovrapporre runner con snapshot dei container preesistenti; ogni runner possiede
soltanto il proprio progetto effimero e ripulisce in finally.

```sh
export TMPDIR=/root/.hermes/cache/scratch
export EVIDENCE=/root/.hermes/evidence/enginia360-mvp05/final
mkdir -p "$EVIDENCE"
python3 -I scripts/test-mvp05-contract.py
python3 -I scripts/test-mvp05-impact.py
python3 -I scripts/test-mvp04-impact.py
python3 -I scripts/test-d97-policy.py
python3 -I scripts/test-d98-policy.py
python3 -I scripts/test-mvp-baseline.py
python3 -I scripts/run-mvp01-tests.py --build-only --evidence-dir "$EVIDENCE/frontend"
MVP05_POOL_SIZE=4 timeout 1500 python3 -I scripts/run-mvp05-tests.py --evidence-dir "$EVIDENCE/pool4"
MVP05_POOL_SIZE=1 timeout 1500 python3 -I scripts/run-mvp05-tests.py --evidence-dir "$EVIDENCE/pool1"
```

La selezione esatta dei path cambiati (tracked + untracked prima del commit) deve
ancora essere eseguita con `scripts/select-ci-impact.py --paths-json` e salvata nel
ledger finale. Eseguire inoltre tutti i consumer selezionati: build/test/audit API
con filtro prodotto dal selettore, shell SSR/Chromium e runner counterparty,
tenant-role, membership, onboarding, authenticated organization e foundation
pertinenti secondo `.github/workflows/ci.yml`. Non usare `full_architecture=true`.
La nuova suite SQL/API/browser non sostituisce quei consumer né passa da uno skip.
I comandi canonici, pin e budget sono quelli del workflow, non una campagna ERP indiscriminata.

Dopo risultati finali corretti: soltanto il parent gestisce commit/PR, CI PR-only,
dispatch sullo stesso head, download/inspection artefatti, merge e issue/Project.
Non dichiarare verificata la consegna basandosi su questa lista o sulla sola exit aggregate.

## Manifest completo dei file repository creati/modificati

- `.github/workflows/ci.yml`
- `AGENTS.md`
- `PROJECT_CHARTER.md`
- `database/runtime/manifest.json`
- `database/runtime/migrations/0043_catalog_management.sql`
- `docs/mvp-backlog.json`
- `docs/mvp-baseline.md`
- `docs/mvp-delivery-plan.md`
- `docs/mvp-existing-code-assessment.md`
- `docs/mvp04-counterparties-contract.md`
- `docs/mvp04-implementation.md`
- `docs/mvp05-catalog-contract.md`
- `docs/mvp05-implementation.md`
- `docs/r06-migration-inventory.json`
- `docs/r06-migration-inventory.md`
- `frontend/app/catalog/page.tsx`
- `frontend/app/domains/[domain]/page.tsx`
- `frontend/components/catalog-workspace.tsx`
- `frontend/components/shell.tsx`
- `frontend/components/tenant-role-workspace.tsx`
- `frontend/lib/catalog.ts`
- `frontend/lib/private-backend.ts`
- `frontend/next.config.ts`
- `frontend/tests/acceptance.spec.ts`
- `frontend/tests/catalog.test.tsx`
- `frontend/tests/shell.test.tsx`
- `scripts/owner-master-authority.py`
- `scripts/run-mvp02a-tests.py`
- `scripts/run-mvp02b-tests.py`
- `scripts/run-mvp02c-tests.py`
- `scripts/run-mvp03b1-tests.py`
- `scripts/run-r00a-tests.py`
- `scripts/run-r00b-tests.py`
- `scripts/test-r00b-lifecycle.py`
- `scripts/run-mvp03b2a-tests.py`
- `scripts/run-mvp03b2b-tests.py`
- `scripts/run-mvp04-tests.py`
- `scripts/run-mvp05-tests.py`
- `scripts/select-ci-impact.py`
- `scripts/test-mvp03b1-roles.py`
- `scripts/test-mvp04-impact.py`
- `scripts/test-mvp05-catalog.py`
- `scripts/test-mvp05-contract.py`
- `scripts/test-mvp05-impact.py`
- `src/Enginia360.Api/Program.cs`
- `src/Modules/Catalog/Enginia360.Catalog.Contracts/ManagementContracts.cs`
- `src/Modules/Catalog/Enginia360.Catalog/CatalogModule.cs`
- `src/Modules/Catalog/Enginia360.Catalog/ManagementEndpoints.cs`
- `tests/Enginia360.Api.Tests/CatalogManagementTests.cs`
- `tests/browser/mvp04-counterparties.cjs`
- `tests/browser/mvp05-catalog.cjs`
- `tests/fixtures/nginx.mvp02c.conf`
