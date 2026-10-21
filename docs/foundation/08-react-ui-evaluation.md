# Dossier di fondazione — 08. Valutazione UI React e composizione documento

**Stato corrente D74–D76:** UI01 (issue #5) editor autorizzato nel [piano finito](../productization-plan.md), con prototipo sintetico isolato e successiva integrazione dei comandi autorizzati dopo R00. Ant Design resta scelta UI; nessuna libreria installata da P00. Nessun go-live, dato reale o deploy; profilo di integrazione concreto al setup, non blocco generale UI/runtime. La valutazione seguente conserva motivazioni e alternative storiche, non riapre il dossier approvato D58.
**Ambito:** UI operativa di composizione del documento, interpretazione da confermare se si intende anche il layout di stampa. Non sono mockup già realizzati né una misurazione comparativa di prestazioni/accessibilità. Nessuna modifica al frontend pubblico.

## 1. Brief acquisito

Luigi Pelosi richiede componenti/layout React enterprise-oriented, eleganti e con utilizzo efficiente dello spazio disponibile. La composizione del documento deve restare verosimilmente simile all'attuale SmartData. Questo autorizza studio e proposte di UI, non copia del codice legacy o riprogettazione automatica del dominio.

**Interpretazione progettuale:** spazio di lavoro full-width/full-height, densità operativa controllata e gerarchia visiva leggibile; niente contenitore da landing page centrato con grandi margini vuoti. Non eliminare ogni spaziatura: evitare sia lo spreco di area sia controlli illeggibili. Ricerca e uso frequente delle righe devono essere provati con tastiera, tabulazione e validazioni.

## 2. Evidenza legacy di composizione

Repository `luigi-pelosi/smartdata`, commit `c5d2ec85496bc2f5f6f3a41e7913b9e82ac2b18b`, file `application/view/default/template/workshop/document.tpl`, consultato in sola lettura.

- Righe 4–19: contenuto full-width/full-height e colonna contestuale laterale di larghezza 300 nel template.
- Righe 21–69: informazioni documento, cliente, fornitore, veicolo, indirizzo e vettore nella colonna laterale.
- Righe 84–119: spazio centrale con toolbar «Lista segnalazioni» e form report/processi caricato dinamicamente.
- Righe 129–180: riepilogo inferiore con strumenti, numero righe e tempi; il resto del template/risposte dinamiche non è qui certificato come layout completo.

Sono osservazioni statiche del template, integrate dallo screenshot rappresentativo successivamente fornito e osservato: colonna contestuale sinistra, sezioni lavorazione ripetute, griglie dense e riepilogo inferiore. Lo screenshot è riferimento visuale, non fonte da cui copiare dati reali o dedurre invarianti. Non confondere il template editor con quelli di stampa/fattura.

## 3. Alternative valutate e scelta corrente

Le tre opzioni sono librerie/design system React, non una scelta obbligatoria di Next.js o di un framework full-stack. Restano React/TypeScript e il backend .NET previsti dal charter.

| Opzione | Fit proposto per Enginia360 | Attenzione |
| --- | --- | --- |
| Ant Design, con ProComponents selettivi | Prima candidata: form articolate, tabella righe, layout laterale e tema compatto; composizione enterprise vicina all'editor operativo desiderato. | Non adottare automaticamente l'intero scaffold Ant Design Pro/Umi. Provare editing di righe complesse, tastiera e compatibilità delle versioni prima della scelta. |
| Material UI + eventuale MUI X | Seconda candidata: design system personalizzabile, layout e componenti per UI enterprise con una griglia da valutare sul caso reale. | MUI X Community è MIT, Pro/Premium commerciali. Funzioni avanzate vanno confrontate con la licenza specifica; nessuna dipendenza a pagamento scelta senza costo/alternativa e approvazione. |
| Mantine | Alternativa se si privilegia un'identità visiva molto personalizzata e un layout componibile con AppShell. | La griglia dati avanzata non è un DataGrid nativo del core: valutare estensioni/community o composizione dedicata, relativa licenza e onere di manutenzione. |

**Scelta dell'agente nell'ambito della delega:** React/TypeScript/Vite esistente + Ant Design, tema chiaro compatto e layout full-width/full-height dedicato. Partire da componenti core Form/Table/Layout e CSS del progetto; non introdurre ProComponents, TanStack Table o altre griglie finché una prova non ne dimostra la necessità. Non combinare più design system per la stessa superficie. Nessun template commerciale, scaffold Ant Design Pro/Umi o cambio a Next.js. Alternative nella tabella conservate per motivazione, non come richiesta di un'altra scelta al proprietario.

**Motivazione:** la struttura osservata richiede soprattutto moduli contestuali compatti, lavorazioni ripetute e editing delle righe, non dashboard decorative. La scelta sostiene continuità visiva e costo di licenza nullo dei componenti core MIT, senza promessa di costo totale nullo: personalizzazione, manutenzione e test restano lavoro. Nessuna equivalenza automatica tra Table e una griglia tipo foglio elettronico: tastiera, focus, validazione ed editing vanno progettati e provati sul caso reale.

Licenze verificate nelle fonti ufficiali: Ant Design MIT, ProComponents MIT, Mantine MIT. Material UI è open source; MUI X distingue Community MIT e piani commerciali. Non è una consulenza legale né un inventario delle licenze transitive della futura build. Nessun costo numerico promesso: verificare prezzi e termini della versione selezionata se si considera un piano commerciale.

## 4. Layout candidato della composizione documento

```text
Barra applicativa: società / sede / ricerca / identità e contesto
Navigazione comprimibile | Documento: tipo, numero, stato, azioni
                        |--------------------------------------
                        | Contesto laterale | Lavorazioni e righe
                        | cliente/pagante   | tabella estesa
                        | veicolo           | dettagli espandibili
                        | destinazione      | stati operativi
                        |--------------------------------------
                        | Riepilogo: tempi, importi, esiti, azioni
```

- Mantenere la riconoscibilità della colonna documento/controparti/veicolo e della zona centrale report/lavorazioni, anziché trasformare l'editor in un wizard obbligatorio.
- Zona centrale elastica, colonna contestuale comprimibile e possibilmente ridimensionabile; riepilogo e azioni persistenti senza coprire le righe.
- Tabelle con descrizioni elastiche, numeri allineati, riferimenti e stati operativi leggibili; dettagli meno frequenti espandibili, non una colonna permanente per ogni campo possibile.
- Composizione delle sezioni secondo capability, permessi e customizing societario: relazione lavorazioni/righe configurabile, non una gerarchia fissa imposta dal template UI.
- Prenotato, prelevato, in preparazione, installato e carcassa rientrata mostrati distintamente; esiti esterni pendenti non rappresentati come conferme.
- Breakpoint per schermi piccoli senza promessa di offline/client nativo. Su monitor desktop privilegiare spazio operativo, non moltiplicare pannelli decorativi.

## 5. Verifica della scelta prima dell'adozione applicativa

**Proposta successiva:** un prototipo dell'editor con Ant Design e dati sintetici, separato dal runtime del DMS. Non è necessario confrontare obbligatoriamente due framework dopo la delega della scelta. La delega seleziona la base UI, non autorizza da sola un backend fittizio presentato come implementazione o il rilascio pubblico di dati aziendali.

Criteri: confronto a parità di contenuto su monitor desktop e portatile; densità/leggibilità; editing, ricerca ricambio e navigazione tastiera; gestione errori; colonna contestuale e riepilogo; italiano; comportamento con documento lungo; verifica delle funzioni/licenze necessarie alla griglia. Misurare dove pertinente, non presumere che un componente garantisca prestazioni o conformità accessibile senza prove.

Nessun prototipo è costruito o pubblicato da questo documento. Lo screenshot rappresentativo è stato successivamente fornito e osservato nella discussione: colonna contestuale sinistra, lavorazioni ripetute con griglie dense di ricambi/manodopera/note, toolbar locali e riepilogo inferiore. Non sono trascritti dati identificativi del cliente. La scelta finale va registrata nel dossier prima dell'adozione produttiva.

### Alternativa richiesta: template amministrativo React commerciale

**Alternativa storica non adottata:** dopo la valutazione dei costi/licenza Fuse React, il proprietario rinuncia all'acquisto e delega la scelta autonoma all'agente. La scelta corrente è indicata nella sezione 3. Quanto segue documenta l'alternativa esaminata, non una raccomandazione ancora aperta ad acquistare.

**Valutazione proposta:** il template può fornire shell, navigazione, tema, schermate comuni e componenti; non costituisce già l'editor documento, il customizing, l'autorizzazione backend o un DMS funzionante. La schermata SmartData è soprattutto un editor di documento denso, non una dashboard di indicatori: validare la griglia e la composizione operativa prima di scegliere in base alla homepage della demo.

**Candidati da esaminare:** Fuse React (la scheda presenta varianti NextJS/Vite), Vuexy nella variante React/Next.js basata su MUI, Mantis come ulteriore confronto commerciale nel relativo store. Mantis usa MUI con principi visivi Ant Design: non descriverlo come template costruito su Ant Design. Non sono certificati compatibilità delle versioni, contenuti esatti del pacchetto o risultati su griglie operative. Verificare TypeScript, scaffold minimo, versione Vite/React richiesta e presenza di dipendenze commerciali aggiuntive.

**Vincolo operativo proposto:** preferire pacchetto React/TypeScript/Vite per restare sulla baseline esistente; un template che richiede Next.js non è scartato a priori ma richiede valutazione architetturale esplicita, non sostituzione silenziosa del frontend/backend. Estrarre il seed e i soli componenti necessari, evitando backend demo e sistemi identity del template come decisioni di prodotto.

**Licenze:** le fonti ufficiali Envato distinguono Regular per end product gratuito agli utenti ed Extended per accesso a pagamento, con limite a un end product anche per Extended. Non assumere che una licenza Regular basti al SaaS commerciale Enginia360, che Extended sia multi-prodotto o che includa eventuali componenti MUI X Pro/Premium. Chiedere conferma scritta dell'inquadramento del SaaS multi-tenant e delle eventuali installazioni separate al licenziante, verificare il pacchetto specifico e presentare costo/alternativa open source prima dell'acquisto. Nessun prezzo numerico o parere legale definitivo è formulato qui.

**Fedeltà funzionale al riferimento:** mantenere contesto laterale, sezioni lavorazione ripetute/espandibili, editing righe e riepilogo persistente; migliorare leggibilità, tastiera, stati e gerarchia senza riprodurre necessariamente microcaratteri o tutte le icone. Prova con documento lungo e contenuto sintetico, non copie di dati reali della schermata.

Fonti aggiuntive ufficiali:
- Envato standard licenses: https://themeforest.net/licenses/standard
- Envato license FAQ: https://themeforest.net/licenses/faq
- Fuse React item: https://themeforest.net/item/fuse-react-react-redux-material-design-admin-template/21769397
- Vuexy item: https://themeforest.net/item/vuexy-vuejs-html-laravel-admin-dashboard-template/23328599
- Vuexy autore: https://themeselection.com/item/vuexy-mui-nextjs-admin-template/
- Mantis autore/store: https://mui.com/store/items/mantis-react-admin-dashboard-template/

Nessun template acquistato, scaricato, installato o pubblicato.

## 6. Fonti primarie consultate

- Ant Design Table: https://ant.design/components/table/
- Ant Design theming/compact algorithm: https://ant.design/docs/react/customize-theme/
- Ant Design license: https://github.com/ant-design/ant-design/blob/master/LICENSE
- ProComponents e licenza: https://github.com/ant-design/pro-components
- ProForm: https://procomponents.ant.design/en-US/components/form/
- Material UI overview: https://mui.com/material-ui/getting-started/
- MUI X licensing: https://mui.com/x/introduction/licensing/
- Mantine AppShell: https://mantine.dev/core/app-shell/
- Mantine grid guidance: https://help.mantine.dev/q/data-grid-i-need
- Mantine license: https://github.com/mantinedev/mantine/blob/master/LICENSE

Le fonti sostengono caratteristiche/licenze dichiarate; il fit estetico e la raccomandazione sono valutazioni progettuali dell'agente. Non sono dichiarati benchmark, compatibilità di versioni o accessibilità certificata non provati.
