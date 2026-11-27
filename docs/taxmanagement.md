# TaxManagement — modello e contratto tecnico

Riferimento unico delle cinque fasi operative: codici, classificazioni, fiscalità aziendale, determinazione e calcolo.
Operazioni quotidiane: [Manuale utente](manuale-utente.md#10-tasse-e-imposte). Architettura e sicurezza comuni: [Foundation](foundation.md).

## 1. Confini e proprietà

TaxManagement possiede configurazioni e decisioni fiscali nello schema `taxmanagement`, nello stesso assembly backend.
L'organizzazione è il `tenant_id` esistente, non una seconda Organization; Company, Country e User riusano le identità foundation.
Catalogo e Business Partner possiedono le anagrafiche; TaxManagement ne conserva riferimenti e profili, senza aggiungere aliquote ai master.
Codice fiscale aziendale, stabilimento IVA, registrazioni e regimi appartengono alla configurazione fiscale, non a Company generale o Sede.
Determinazione e calcolo non persistono risultati. Documenti fiscali, snapshot documentali storici, XML, registri, liquidazioni e contabilità non sono implementati.

Le **16 tabelle** sono raggruppate per responsabilità:

| Gruppo | Tabelle in `taxmanagement` | Proprietà |
|---|---|---|
| Cataloghi | `tax_types`, `tax_nature_codes`, `tax_regimes` | Sistema, sola lettura |
| Codici | `tax_codes`, `tax_code_versions`, `tax_audit_events` | Tenant, radice TaxCode e proprio storico/audit |
| Classificazioni | `item_tax_classifications`, `partner_tax_classifications` | Tenant, identità descrittive per paese e imposta |
| Profili | `item_tax_profiles`, `partner_tax_profiles` | Tenant/soggetto, assegnazioni temporali alle anagrafiche |
| Fiscalità aziendale | `company_tax_configurations`, `company_tax_registrations`, `company_tax_regime_profiles` | Tenant/Company, una radice per azienda e tipo imposta |
| Regole | `tax_rules`, `tax_rule_versions`, `tax_rule_conditions` | Tenant; `company_id` nullo = condivise, valorizzato = aziendali |

Codici di trattamento/classificazione obbligatori, stabili e univoci case-insensitive per tenant/paese/tipo; nome e descrizione modificabili.
`VAT_STANDARD` non cambia identità con l'aliquota. Le regole includono lo scope Company nell'unicità, senza precedenza implicita perché aziendali.
FK composte proteggono i riferimenti same-tenant; isolamento in lettura applicativo, non RLS.
Niente DELETE di radici o storico; soltanto le condizioni Draft possono essere sostituite/eliminate sotto guardia.

## 2. Codici e classificazioni

Solo VAT è operativa. Le altre famiglie censite non abilitano nuovi utilizzi.
`rate` è `numeric(9,6)`, trasportata come stringa decimale: `22.000000` significa 22%, limite `999.999999`, niente esponenti o floating point.
Paese, tipo e codice dell'identità sono immutabili. Disattivare impedisce nuovi utilizzi, non cancella la lettura storica.

| Trattamento | Aliquota | Natura italiana |
|---|---|---|
| `TAXABLE` | Positiva | Assente |
| `EXCLUDED` / `OUT_OF_SCOPE` | Zero | N1 / N2.1–N2.2 |
| `NON_TAXABLE` / `EXEMPT` | Zero | N3.1–N3.6 / N4 |
| `MARGIN` / `REVERSE_CHARGE` / `OTHER_EU` | Zero esposta | N5 / N6.1–N6.9 / N7 |
| `ZERO_RATED` | Zero | Non ammesso per Italia |

Lo zero configurato non implementa margine, inversione contabile o imposta in altro Stato. Split payment non è un trattamento.
La natura deve appartenere al paese e coprire tutto l'intervallo della versione; N2/N3/N6 generici non sono selezionabili.
Le classificazioni sono descrittive, non aliquote o nomenclatori ufficiali. `UNKNOWN` è una scelta esplicita, non un fallback.
Il profilo associa soggetto, paese, tipo e classificazione alla data; il paese del profilo BP non prova residenza o stabilimento.
Template di codici/classificazioni solo su richiesta: aggiungono mancanti senza sovrascrivere personalizzazioni o assegnare profili.

## 3. Fiscalità aziendale

`CompanyTaxConfiguration` nasce `DRAFT`; tipo e paese di stabilimento IVA sono immutabili e non derivano dalle sedi.
Il codice fiscale facoltativo è testo fino a 500 caratteri, senza unicità o certificazione fiscale; le registrazioni IVA sono figli distinti.
Ogni nuova configurazione richiede registrazioni iniziali; **ogni nuova registrazione richiede un regime iniziale**, anche aggiunta successivamente.
Registrazione e regime committano insieme; controlli differibili verificano il risultato finale senza completare retroattivamente vecchie registrazioni.
Il supporto `ORDINARY`/VAT per IT, DE e FR parte dal **26 novembre 2026**, data tecnica dello snapshot, non introduzione normativa.
Matrice formale: `DOMESTIC` nello stesso paese dello stabilimento; `DIRECT_IDENTIFICATION` in paese diverso IT/DE/FR; `FISCAL_REPRESENTATIVE` solo in IT con stabilimento DE/FR.
Identificativi esatti: IT + 11 cifre, DE + 9 cifre, FR + 2 alfanumerici esclusi I/O + 9 cifre; niente trim, prefissi inventati o verifica VIES.
Vietata la sovrapposizione dello stesso identificativo/paese/imposta nel tenant, anche fra aziende; una sola DOMESTIC contemporanea per configurazione.
Un profilo regime è contenuto nella registrazione e nella validità del regime; nessuna sovrapposizione nella stessa registrazione.
Attivare richiede azienda abilitata e una catena supportata valida oggi, data UTC server; ogni nuovo utilizzo ricontrolla la data richiesta.
Sospendere conserva lo storico. Chiudere abbrevia registrazione e profili attraversati, rifiutando profili futuri oltre la fine o perdita dell'ultima copertura ACTIVE odierna.
Il resolver puntuale richiede registrazione e data: restituisce la catena valida o errore, mai la prima riga disponibile.

## 4. Tempo, concorrenza e audit

Date fiscali `DATE`, intervalli inclusivi `[valid_from, valid_to]`, fine nulla = aperto. Le lacune sono errori, senza ultima versione di ripiego.
Programmare chiude il predecessore coprente al giorno prima e inserisce il successore nella stessa transazione, senza altre sovrapposizioni.
Payload pubblicati immutabili salvo abbreviazioni controllate; versioni regola modificabili solo in `DRAFT`, poi `PUBLISHED` o `WITHDRAWN`.
Il ritiro vieta nuove determinazioni anche retrodatate; la lettura storica non ricostruisce un documento emesso.
Le mutazioni di aggregati esistenti usano `expectedVersion`; token obsoleto = HTTP 409, non aggiornamento silenzioso.
Profili articolo/BP: stream indipendente per tenant/soggetto, globale ai paesi/tipi; vuoto = 0, inserimento = massimo + 1, chiusura conserva la revision della riga.
I comandi fiscali Company avanzano una sola volta la revisione fiscale, non quella dei dati generali Company.
Lock di radice, advisory lock e vincoli di esclusione proteggono successione e concorrenza anche in SQL.
Sul ruleset `tax-determination:rules:{tenant:D}:{country:D}:{taxType:D}:{SALE|PURCHASE}` lettura condivisa e pubblicazione/ritiro esclusivi precedono i lock delle radici.
Le letture materializzano snapshot coerenti; il batch acquisisce l'unione delle fonti prima del loop, nello stesso ordine globale dei writer.
Cataloghi readonly senza grant UPDATE per ottenere lock. Il gate HTTP `Security.Lock` resta conservativo: nessuna promessa di throughput concorrente oltre quel gate.
Audit e mutazione atomici: `foundation.audit_event` INSERT-only al runtime; `tax_audit_events` è la sola proiezione consultabile del TaxCode, non un audit generico.

## 5. Fatti autorevoli e determinazione

L'application recupera fonti autorizzate e revisioni; il motore puro riceve snapshot tipizzati senza DB, clock o aggregati commerciali.
Autorità: configurazione Company per registrazione/regime/stabilimento; profili per classificazioni; Catalogo per natura articolo; TaxCode per trattamento/versione/aliquota; regole per selezione.
Il client dichiara fatti e provenienza, non risultato fiscale, aliquota o policy. Partita IVA, indirizzo e classificazione non provano stabilimento o VIES.
Il riferimento facoltativo all'identificativo BP usa la revisione anagrafica corrente, non una registrazione temporale; VIES resta sconosciuto.
Selezione Company esplicita; se omessa serve una sola catena DOMESTIC italiana ACTIVE/ORDINARY alla data, mai la prima di un elenco.
Perimetro dal **26 novembre 2026**: VAT italiana nazionale ordinaria, beni mobili nazionali/unionali e servizi generici, vendite B2B/B2C, acquisti da soggetto che agisce come soggetto passivo.
Servono stabilimenti rilevanti, conferma territorio IVA ordinario e assenza di trattamento speciale; per beni ubicazione/partenza/destinazione e condizione doganale; per servizi luogo e categoria.
Fatto mancante = `INCOMPLETE_CONTEXT`; fatto positivamente fuori perimetro = `UNSUPPORTED_OPERATION`. IT→IT da solo non basta.
Condizioni su whitelist finita, in AND: `EQUALS`, `NOT_EQUALS`, `IN`, `NOT_IN`, `IS_TRUE`, `IS_FALSE`; massimo 100 condizioni e 100 valori per insieme.
Matching MATCH/NO_MATCH/UNKNOWN: una falsa rende falsa la congiunzione; UNKNOWN non soddisfa automaticamente un predicato negativo.
Vince la priorità maggiore; parità applicabile = `AMBIGUOUS_RULE`; una candidata incompleta a priorità uguale/superiore blocca la scelta.
La regola seleziona TaxCode, poi risolve `TaxFiscalVersion` alla data; nessun fallback se inattivo/privo di versione (`TAX_CODE_UNAVAILABLE`) o senza regole (`NO_MATCHING_RULE`).
Risultato ordinario TAXABLE, natura assente, debitore SUPPLIER, assolvimento STANDARD. Esenzioni, reverse charge, split payment, margine e transfrontaliere non sono operative perché configurabili nei codici.
La traccia identifica fatti, fonti/revisioni, candidati e versioni; non copia credenziali o numeri IVA personali.
Simulazione: bozze esplicite, al massimo una per radice, sostituiscono la pubblicata della stessa regola; risultato marcato, senza persistenza.
Template regola = bozze esplicite, senza creazione dei prerequisiti o pubblicazione automatica; quelli con decorrenza nel 2026 terminano il **31 dicembre 2026**.

## 6. Calcolo monetario

A ogni richiesta esplicita il backend ridetermina una volta ogni riga; il core calcola poi sulle fonti affidabili senza ulteriori letture.
Policy server `IT_VAT_STANDARD_V1`, v1: EUR, scala 2, precisione interna 12, `HALF_UP`, `TAX_GROUP`, residui `LARGEST_REMAINDER`.
EUR deve essere abilitata con `minor_units=2`; identità/revisione acquisite dal catalogo senza permesso della pagina Valute.
Sono scelte tecniche, non un metodo imposto dalla legge. Aritmetica razionale BigInteger limitata; importi/quantità/percentuali come stringhe decimali.
Con `q` quantità, `p` prezzo, `r` aliquota percentuale e `B` base commerciale corrente dopo le rettifiche:

- `B0 = q × p`; per ogni sequenza `Bsuccessiva = Bcorrente − sconto + maggiorazione`, calcolati sulla base corrente.
- Prezzo escluso: `N = B`, `I = N × r / 100`; incluso: `N = B / (1 + r / 100)`, `I = B − N`.
- Rettifica comune `A`: quota esatta `Ai = A × Bi / ΣBi` sui destinatari; capienza e base omogenea incl./escl. obbligatorie. Con somma delle basi zero è ammessa solo una rettifica zero, con quote zero.
- Importi finali: `lordo = netto + IVA`; somme righe = gruppi = totali esattamente, senza tolleranze a centesimi.
- `netto = nettoPrima − scontiNetti + maggiorazioniNette + netRoundingAdjustment`; `taxRoundingAdjustment` distingue IVA allocata da IVA arrotondata individualmente.

Quote commerciali esatte fino all'allocazione monetaria. Gruppo per tipo, paese, codice/versione, aliquota, trattamento, natura, debitore, meccanismo e modalità prezzo.
Negli inclusi si alloca prima il lordo e poi il netto con capienza per riga; IVA per differenza, senza negativi da residui. Parità risolte con UUID stabile in ordine stringa, non posizione dell'array.
Massimo 100 righe, 20 rettifiche per riga e 20 comuni; ID rettifiche univoci nel batch e sequenze univoche nell'ambito.
Quantità positiva: 14 cifre intere/6 decimali; prezzo positivo: 12/8; importo fisso non negativo: 16/2; magnitudine monetaria strettamente inferiore a `10^16`, anche dopo arrotondamento.
Percentuali: sei decimali; sconti/detraibilità 0–100, maggiorazioni fino a `999.999999`; niente sconti oltre capienza o intermedi negativi.
Oneri ordinari comuni = maggiorazioni esplicite sulle operazioni principali; CHARGE non prova accessorietà o nuova casistica territoriale.
Acquisti: detraibilità assente = `null`, non 0/100; detraibile + indetraibile = IVA finale, senza cambiare debito al fornitore. Vietata sulle vendite.
`REVERSAL` applica il segno a tutti i risultati monetari/allocazioni: non emette note di credito né recupera aliquote storiche di fatture.
Niente cambi valutari, prezzi/promozioni automatici, diritto alla detrazione o riscrittura di fatture ricevute.

## 7. API e permessi

Prefisso `/api/tax`; identificativi UUID. Sessione/tenant, Origin/CSRF e transazioni riusano la Foundation.
Il globale indica `tenantId`; l'ordinario rimane nel proprio tenant. Record snake_case, envelope camelCase, errori codice/campo senza SQL o segreti.

| Gruppo | Metodi e percorsi relativi reali |
|---|---|
| Cataloghi/lookup codici | GET `types`, `nature-codes`, `countries`, `lookups` |
| Codici | GET/POST `codes`; GET/PUT `codes/{id}`; GET `codes/{id}/versions`, `/audit`, `/resolve?date=YYYY-MM-DD&forNewUse=true`; POST `codes/{id}/versions`, `/deactivate`, `/reactivate`; POST `codes/templates/install` |
| Classificazioni | GET/POST `item-classifications`, `partner-classifications`; GET/PUT `…/{id}`; POST `…/{id}/deactivate`, `/reactivate`; POST `…/templates/install`; GET `classification-lookups?kind=item|partner` |
| Profili | GET/POST `items/{subjectId}/profiles`, `partners/{subjectId}/profiles`; POST `…/schedule`; GET `…/resolve?country_id=UUID&tax_type_id=UUID&date=YYYY-MM-DD` |
| Company: contesto | GET `regimes`, `company-lookups`, `companies/{companyId}/permissions`; GET/POST `companies/{companyId}/configurations`; GET/PUT `company-configurations/{id}` |
| Company: comandi | POST `company-configurations/{id}/activate`, `/suspend`, `/registrations`, `/registrations/{registrationId}/close`, `/registrations/{registrationId}/regimes`, `/registrations/{registrationId}/regimes/schedule` |
| Company: risoluzione | GET `companies/{companyId}/registrations`; GET `companies/{companyId}/registrations/{registrationId}/resolve` con `date` e `forNewUse` |
| Regole | GET/POST `rules`; GET/PUT `rules/{id}`; GET `rules/{id}/versions`, `/permissions`, `/conflicts`; POST `rules/{id}/versions`; PUT `rules/{id}/versions/{versionId}` |
| Regole: azioni | POST `rules/{id}/versions/{versionId}/validate`, `/publish`, `/withdraw`; POST `rules/templates/install`; GET `rule-lookups` |
| Determinazione | GET `determination-lookups`, `determination-options`; POST `determinations/simulate`, `determinations` |
| Calcolo | GET `calculation-policy?company_id=UUID&currency=EUR`; POST `calculations/simulate`, `calculations` |

Creazioni padre autorizzate accettano profili iniziali; POST `/api/data/companies/save` accetta `taxConfigurations`, mai nel PUT Company.
Calcolo: `lines[].fiscal_context` e valori commerciali, non risultati/policy del browser; successo `{isSimulation,result}` con righe, riepiloghi, totali e traccia.
Contesto fallito: HTTP 422 con `outcome`, `trace` e campo della riga; input invalido indica il percorso originale. I POST effettivi rifiutano `draft_version_ids`, anche vuoto.
Body dei soli due POST calcolo fino a 1 MiB; altre API a 64 KiB.
Codici: `tax-codes.read/create/update/schedule/deactivate/reactivate/install_templates`; cataloghi: `tax-types.read`, `tax-nature-codes.read`, `tax-regimes.read`.
Classificazioni: `tax-{item|partner}-classifications.read/create/update/deactivate/reactivate/install_templates`; profili: `tax-{item|partner}-profiles.read/assign/schedule` (notazione compatta per permessi distinti, non wildcard).
Company: `company-tax-configurations.read/create/update/activate/suspend/register/close/assign_regime/schedule_regime`; nuova registrazione richiede register + assign_regime nello stesso ruolo/azienda.
Regole: `tax-rules.read/create/update/validate/publish/withdraw/install_templates`; determinazione: `tax-determination.read/simulate/determine`; calcolo: `tax-calculation.read/simulate/calculate`.
Azione e azienda nello stesso ruolo attivo per Company, regole aziendali, determinazione/calcolo; serve `companies.read`. Regole condivise con autorità tenant distinta.
Profili autonomi richiedono lettura del soggetto; determinazione/calcolo conservano i gate fonti: fiscalità Company, Catalogo/BP e relativi profili.
Lookup contestuali non concedono manutenzione/lettura generale di altri cataloghi; conflitti fuori ambito non espongono identità o payload privati.
Il catalogo completo contiene **147 permessi di sistema**: materializzarli non li assegna a ruoli/utenti, né concede aziende.

## 8. UI, bozze e recupero

Workspace **Impostazioni → Anagrafiche → Tasse e imposte**: codici, cataloghi, classificazioni, regimi, regole e simulatore secondo permessi indipendenti.
Profili in **Articolo/BP → Fiscalità**; configurazioni in **Azienda → Fiscalità**. Finestre trascinabili/ridimensionabili e tabelle compatte con ricerca iniziale.
Padre nuovo: righe locali fino al Salva atomico; padre salvato: comandi fiscali immediati e indipendenti dai metadati in bozza.
Programmare versioni/profili o salvare Draft regola non salva i dati generali. Pubblicare è distinto dal salvataggio della bozza.
Simulatore: fatti editabili, richiesta inviata, risultato e confronto locale separati. **Aggiungi al calcolo** copia lo scenario riuscito, non l'autorità del risultato.
Calcolo multi-riga/rettifiche nello stesso simulatore; dettagli e tracce annidati a tutta larghezza disponibile anche nel confronto.
Ogni **Calcola** rivaluta le fonti correnti. Modificare input segnala esito non aggiornato, non cambia lo snapshot precedente.
Refresh nella stessa scheda: recupero per utente/tenant e permessi correnti, senza POST automatiche; dipende dallo storage disponibile.
Menu: reset ordinario, non dei comandi incerti. Conflitti conservano token originale e bozza; rileggere e confrontare senza sovrascrittura.
Risposta persa ≠ commit fallito: rilettura autorevole e verifica esplicita prima di sbloccare, nessun replay automatico.

## 9. Baseline e fonti del contratto

Solo nuova installazione: [foundation.sql](../database/foundation.sql) include il solo [taxmanagement.sql](../database/taxmanagement.sql) per tutto il dominio, nella propria transazione.
Baseline finale: cinque inclusioni dirette (BP, Pagamenti, Catalogo, seed Nazioni, TaxManagement); **65 tabelle: 26 foundation, 23 masterdata, 16 taxmanagement**.
Consolidamento ≠ upgrade: non eseguire baseline/frammento sul DB esistente, non fare DROP/reset o rieseguire migrazioni ritirate.
Niente DDL, tenant seed o migration runner all'avvio. Template/grant espliciti; storia ed evidenze dei rilasci conservate privatamente fuori repository.
Contratto eseguibile in [Modules/TaxManagement](../backend/Modules/TaxManagement/): `TaxCode`/`TaxRules`, `ClassificationTimeline`, `CompanyTaxConfiguration`, motori/resolver e rispettivi `*Endpoints`/`*Input`.
Policy/equazioni: [TaxCalculationDomain.cs](../backend/Modules/TaxManagement/TaxCalculationDomain.cs), [TaxCalculationEngine.cs](../backend/Modules/TaxManagement/TaxCalculationEngine.cs), [TaxAdjustmentAllocation.cs](../backend/Modules/TaxManagement/TaxAdjustmentAllocation.cs), [TaxRoundingService.cs](../backend/Modules/TaxManagement/TaxRoundingService.cs).
Prove dominio/SQL/HTTP/browser distinte: baseline sorgente o test statico non attestano rilascio, TLS o conservazione di un DB popolato.

## 10. Riferimenti fiscali dello snapshot

Riferimenti già verificati nei rilasci fino al **27 novembre 2026**, conservati senza nuova ricognizione normativa o aggiornamento automatico.
Nature: [FatturaPA v1.4, 31 gennaio 2025](https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.4/Specifiche_tecniche_del_formato_FatturaPA_V1.4.pdf), §3.9; nomenclatore dal **1° gennaio 2021**, descrizioni snapshot, non storia completa.
Aliquote template 22/10/5/4%: [Your Europe](https://europa.eu/youreurope/business/finance-and-tax/vat/vat-rules-rates/index_it.htm); esempi configurabili, non assegnazioni a beni/operazioni.
[DPR 633/1972 al 27 novembre 2026](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1972-10-26;633!vig=2026-11-27) fino al **31 dicembre 2026**: territorialità artt. 7/7-bis/7-ter, aliquote 16, accessorietà 12, base 13, esclusioni 15, esposizione/arrotondamento 21, c.2, lett. l).
[TU allegato al D.Lgs. 10/2026](https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2026-01-19;10!vig=2026-11-27) applicabile dal **1° gennaio 2027** (art.171): corrispondenti artt. 2/15/17, 34, 31, 27, 29, 72, c.2, lett. m). Entrata in vigore formale **31 gennaio 2026**; art.170 non abroga indistintamente l'intero DPR.
La data fiscale governa i riferimenti; numerazioni delle tabelle ridotte non si trasferiscono meccanicamente. Livigno, Campione d'Italia e acque italiane del Lago di Lugano non sono territorio IVA ordinario.
Le fonti delimitano il supporto tecnico, non certificano configurazioni o detraibilità del cliente; maggiori resti e arrotondamento per gruppo sono scelte della policy.
