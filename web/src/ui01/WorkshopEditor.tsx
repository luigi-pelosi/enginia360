import { Fragment, useEffect, useRef, useState } from 'react';
import { Button, ConfigProvider, Input, Tag, theme } from 'antd';
import type { InputRef } from 'antd';
import itIT from 'antd/locale/it_IT';
import type { EditorDocument, EditorLine, EditorProps } from './contracts';

const stageLabels = { reserved: 'Prenotato', picked: 'Prelevato', prepared: 'In preparazione', installed: 'Installato / consumato', carcass: 'Carcassa' } as const;
const externalLabels = { Pending: 'Pending · in attesa', Received: 'Received · ricevuto, NON confermato', Confirmed: 'Confirmed · conferma business fornita', Error: 'Error · esito da riconciliare' } as const;

export default function WorkshopEditor({ document: supplied, catalog, vehicles, payers, state = 'ready', onDraftChange }: EditorProps) {
    const [document, setDocument] = useState(supplied);
    const [draft, setDraft] = useState<EditorLine | null>(null);
    const [changed, setChanged] = useState(false);
    const [message, setMessage] = useState('');
    const [collapsed, setCollapsed] = useState(false);
    const [query, setQuery] = useState('');
    const matches = catalog.filter(item => item.kind === draft?.kind && `${item.id} ${item.description}`.toLocaleLowerCase('it').includes(query.toLocaleLowerCase('it')));
    const descriptionRef = useRef<InputRef>(null);
    const quantityRef = useRef<InputRef>(null);
    const priceRef = useRef<InputRef>(null);
    const [errors, setErrors] = useState<Partial<Record<'description' | 'quantity' | 'price', string>>>({});
    const triggers = useRef(new Map<string, HTMLButtonElement | HTMLAnchorElement>());
    const previousId = useRef<string | null>(null);
    useEffect(() => {
        if (draft) { previousId.current = draft.id; descriptionRef.current?.focus(); }
        else if (previousId.current) triggers.current.get(previousId.current)?.focus();
    }, [draft?.id]);
    const original = draft ? document.groups.flatMap(group => group.lines).find(line => line.id === draft.id) : null;
    const stale = changed || (draft !== null && JSON.stringify(original) !== JSON.stringify(draft));
    function publish(next: EditorDocument) { setDocument(next); setChanged(true); onDraftChange?.(next); }
    function cancel() { setDraft(null); setErrors({}); setMessage('Modifica annullata · nessun salvataggio'); }
    function apply() {
        if (!draft) return;
        const nextErrors: typeof errors = {};
        const decimal = /^\d{1,12}(?:\.\d{1,6})?$/;
        if (!draft.description.trim() || draft.description.length > 500) nextErrors.description = 'Inserisci una descrizione di 1–500 caratteri.';
        if (draft.kind !== 'Note') {
            if (!decimal.test(draft.quantity)) nextErrors.quantity = 'Usa un valore non negativo, punto e massimo 6 decimali (12 cifre intere).';
            if (!decimal.test(draft.unitPrice)) nextErrors.price = 'Usa un valore non negativo, punto e massimo 6 decimali (12 cifre intere).';
        }
        setErrors(nextErrors);
        if (nextErrors.description || nextErrors.quantity || nextErrors.price) {
            (nextErrors.description ? descriptionRef : nextErrors.quantity ? quantityRef : priceRef).current?.focus(); return;
        }
        publish({ ...document, groups: document.groups.map(group => group.lines.some(line => line.id === draft.id)
            ? { ...group, lines: group.lines.map(line => line.id === draft.id ? draft : line) } : group) });
        setDraft(null); setMessage('Riga applicata solo alla bozza locale · non salvata');
    }
    const configuration = { locale: itIT, componentSize: 'small' as const, theme: { algorithm: theme.compactAlgorithm, token: { colorPrimary: '#176b5b', borderRadius: 3, fontSize: 14 } } };
    if (state !== 'ready') return <ConfigProvider {...configuration}><div className="ui01-workspace ui01-state">
        <header className="ui01-topbar"><strong>Enginia360 <span>/ Officina</span></strong><Tag color="gold">Prototipo — dati sintetici</Tag></header>
        {state === 'loading'
            ? <p role="status">Caricamento del documento sintetico…</p>
            : <p role="alert">Documento non disponibile · stato di errore del prototipo, nessuna policy di recupero implementata</p>}
    </div></ConfigProvider>;
    return <ConfigProvider {...configuration}>
        <div className="ui01-workspace">
            <header className="ui01-topbar"><Button aria-controls="ui01-context" aria-expanded={!collapsed} onClick={() => setCollapsed(!collapsed)}>{collapsed ? 'Espandi contesto' : 'Comprimi contesto'}</Button><strong>Enginia360 <span>/ Officina</span></strong><Tag color="gold">Prototipo — dati sintetici</Tag><span>Nessuna connessione · nessun salvataggio</span></header>
            <div className="ui01-body">
                <aside id="ui01-context" hidden={collapsed} className="ui01-context" aria-label="Contesto documento">
                    <h2>Documento</h2><strong>{document.reference}</strong><p>Commessa sintetica · bozza locale</p>
                    <h2>Cliente</h2><p>{document.customer.name}</p>
                    <h2>Pagante indipendente</h2><label htmlFor="ui01-payer">Seleziona pagante sintetico</label>
                    <select id="ui01-payer" disabled={!!draft} value={document.payer.id} onChange={event => {
                        const payer = payers.find(item => item.id === event.target.value);
                        if (payer) publish({ ...document, payer });
                    }}><option value={document.payer.id}>{document.payer.name}</option>{payers.filter(item => item.id !== document.payer.id).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
                    <h2>Veicolo</h2><label htmlFor="ui01-vehicle">Seleziona veicolo sintetico</label>
                    <select id="ui01-vehicle" disabled={!!draft} value={document.vehicle.id} onChange={event => {
                        const vehicle = vehicles.find(item => item.id === event.target.value);
                        if (vehicle) publish({ ...document, vehicle });
                    }}><option value={document.vehicle.id}>{document.vehicle.label}</option>{vehicles.filter(item => item.id !== document.vehicle.id).map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
                    <p>Intestatario: {document.vehicle.keeper}</p><p className="ui01-hint">Il veicolo non cambia il pagante. Nessuna autorità anagrafica dedotta.</p>
                </aside>
                <main className="ui01-document" aria-label="Lavorazioni">
                    <div className="ui01-document-heading"><div><p>EDITOR COMMESSA / {document.reference}</p><h1>Lavorazioni e righe</h1></div><span>{document.groups.length} gruppi forniti</span></div>
                    <section className="ui01-operations" aria-label="Proiezioni operative di sola lettura">
                        {Object.entries(stageLabels).map(([key, label]) => <div key={key}><span>{label}</span><strong>{document.operations[key as keyof typeof stageLabels]}</strong></div>)}
                        <div className="ui01-external"><span>Esito esterno</span><strong>{externalLabels[document.operations.external]}</strong></div>
                    </section>
                    {document.groups.length === 0 && <p className="ui01-empty">Nessuna lavorazione fornita</p>}
                    {document.groups.map(group => <section className="ui01-group" key={group.id} aria-labelledby={`heading-${group.id}`}>
                        <div className="ui01-group-heading"><h2 id={`heading-${group.id}`}>{group.title}</h2><Tag>{group.lines.length} righe</Tag></div>
                        <table><caption className="ui01-sr-only">Righe di {group.title}</caption><thead><tr><th>Tipo</th><th>Descrizione / catalogo</th><th>Quantità</th><th>Prezzo unitario EUR</th><th>Azione locale</th></tr></thead><tbody>
                            {group.lines.map(line => <Fragment key={line.id}>
                                <tr data-line-id={line.id} className={draft?.id === line.id ? 'ui01-active-row' : ''}>
                                    <td><Tag>{line.kind === 'Service' ? 'Prestazione' : line.kind === 'Part' ? 'Ricambio' : 'Nota'}</Tag></td>
                                    <td>{line.description}<small>{line.id}</small></td>
                                    <td className="ui01-decimal">{line.kind !== 'Note' ? line.quantity : '—'}</td><td className="ui01-decimal">{line.kind !== 'Note' ? line.unitPrice : '—'}</td>
                                    <td><Button ref={node => { if (node) triggers.current.set(line.id, node); else triggers.current.delete(line.id); }} disabled={draft !== null} onClick={() => { setDraft({ ...line }); setMessage(''); setQuery(''); setErrors({}); }} aria-label={`Modifica ${line.id}`}>Modifica</Button></td>
                                </tr>
                                {draft?.id === line.id && <tr><td colSpan={5} className="ui01-editor-cell">
                                    <form id="ui01-row-form" className="ui01-row-editor" onKeyDown={event => { if (event.key === 'Escape') { event.preventDefault(); cancel(); } }} onSubmit={event => { event.preventDefault(); apply(); }}>
                                        <div className="ui01-description-field"><label htmlFor={`description-${line.id}`}>Descrizione {line.id}</label><Input aria-invalid={!!errors.description} aria-describedby={errors.description ? 'ui01-description-error' : undefined} id={`description-${line.id}`} ref={descriptionRef} value={draft.description} onChange={event => setDraft({ ...draft, description: event.target.value })} />{errors.description && <span id="ui01-description-error" role="alert">{errors.description}</span>}</div>
                                        {draft.kind !== 'Note' && <>
                                            <div className="ui01-catalog"><label htmlFor="ui01-catalog-search">Cerca nel catalogo sintetico</label><Input id="ui01-catalog-search" value={query} onChange={event => setQuery(event.target.value)} />
                                                <ul aria-label="Risultati catalogo locale">{matches.map(item => <li key={item.id}><Button aria-label={`Seleziona ${item.description}`} onClick={() => { setDraft({ ...draft, catalogId: item.id, description: item.description, unitPrice: item.unitPrice }); descriptionRef.current?.focus(); }}>{item.description} · {item.unitPrice} EUR</Button></li>)}</ul>
                                                {matches.length === 0 && <span role="status">Nessun risultato locale</span>}
                                            </div>
                                            <div><label htmlFor={`quantity-${line.id}`}>Quantità {line.id}</label><Input ref={quantityRef} aria-invalid={!!errors.quantity} aria-describedby={errors.quantity ? 'ui01-quantity-error' : undefined} id={`quantity-${line.id}`} inputMode="decimal" value={draft.quantity} onChange={event => setDraft({ ...draft, quantity: event.target.value })} />{errors.quantity && <span id="ui01-quantity-error" role="alert">{errors.quantity}</span>}</div>
                                            <div><label htmlFor={`price-${line.id}`}>Prezzo unitario {line.id}</label><Input ref={priceRef} aria-invalid={!!errors.price} aria-describedby={errors.price ? 'ui01-price-error' : undefined} id={`price-${line.id}`} inputMode="decimal" value={draft.unitPrice} onChange={event => setDraft({ ...draft, unitPrice: event.target.value })} />{errors.price && <span id="ui01-price-error" role="alert">{errors.price}</span>}</div>
                                        </>}
                                        <p>Bozza riga locale · applica o annulla prima di cambiare riga</p>
                                    </form>
                                </td></tr>}
                            </Fragment>)}
                        </tbody></table>
                    </section>)}
                </main>
            </div>
            <footer className="ui01-summary" aria-label="Riepilogo commerciale fornito">
                <div><strong>Riepilogo fornito</strong><small>Revisione {document.summary.revision} · nessun calcolo locale</small><span role="status" className={stale ? 'ui01-stale' : ''}>{stale ? 'Riepilogo non aggiornato · modifiche locali' : 'Proiezione fornita · invariata'}</span></div>
                <dl><div><dt>Imponibile</dt><dd>{document.summary.net} EUR</dd></div><div><dt>IVA fornita</dt><dd>{document.summary.tax} EUR</dd></div><div><dt>Totale</dt><dd>{document.summary.total} EUR</dd></div></dl>
                <div className="ui01-actions"><Button disabled={!draft} onClick={cancel}>Annulla riga</Button><Button disabled={!draft} type="primary" htmlType="submit" form="ui01-row-form">Applica riga</Button><span role="status">{message}</span></div>
            </footer>
        </div>
    </ConfigProvider>;
}
