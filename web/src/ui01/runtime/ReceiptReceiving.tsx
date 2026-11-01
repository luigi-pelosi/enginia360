import { useEffect, useRef, useState } from 'react';
import { ApiError, request } from './workshopApi';
import { check, record, uuid } from './contracts';

type Source = { id: string; orderedQuantity: string; unitPurchasePrice: string; externalOrderReference: string; supplierName: string; description: string };
type Receipt = { id: string; snapshot: { quantity: string; unitPrice: string }; status: string; externalReference: string | null; delivery: { state: string; lastError: string | null; knownDocumentId: number | null } };
type State = { orderedQuantity: string; acceptedQuantity: string; uncertainQuantity: string; remainingQuantity: string; receipts: Receipt[] };
function deliveryText(r: Receipt): string {
    if (r.status === 'Confirmed' && r.delivery.state === 'Completed' && r.delivery.knownDocumentId && r.externalReference === 'GiobbyReceipt-' + r.delivery.knownDocumentId) return 'Confermato dopo readback esatto · ' + r.externalReference;
    if (r.delivery.state === 'Queued') return 'In coda · non confermato';
    if (r.delivery.state === 'Completed') return 'HOLD · conferma business non ancora registrata';
    return r.delivery.knownDocumentId ? 'HOLD · ACK noto: attesa di verifica esatta Giobby' : 'HOLD · ACK sconosciuto: nessun reinvio, quota impegnata';
}
const q6 = (v: unknown): v is string => typeof v === 'string' && /^\d{1,6}\.\d{6}$/.test(v);
const quantityPattern = /^\d{1,6}(?:\.\d{1,6})?$/;
const micros = (v: string) => { const [whole, fraction = ''] = v.split('.'); return BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0')); };
const format = (v: bigint) => (v / 1000000n).toString() + '.' + (v % 1000000n).toString().padStart(6, '0');

// Receiving discovery is separately authorized: never reuse purchase-only history or list prices.
export default function ReceiptReceiving({ url, warehouseId, onError, blocked = false, closed = false, onBlocked }: Readonly<{ url: string; warehouseId: string; onError: (e: unknown) => void; blocked?: boolean; closed?: boolean; onBlocked?: (blocked: boolean) => void }>) {
    const [sources, setSources] = useState<Source[]>(), [sourceId, setSourceId] = useState(''), [state, setState] = useState<State>();
    const [message, setMessage] = useState('Seleziona un ordine acquisto confermato.');
    const [quantity, setQuantity] = useState(''), [busy, setBusy] = useState(false), [pending, setPending] = useState(false), [retryable, setRetryable] = useState(false);
    const frozen = useRef<{ path: string; body: string } | undefined>(undefined);
    const input = useRef<HTMLInputElement>(null);
    useEffect(() => { onBlocked?.(busy || pending); }, [busy, pending, onBlocked]);
    useEffect(() => () => onBlocked?.(false), [onBlocked]);
    const generation = useRef(0);
    const source = sources?.find(s => s.id === sourceId);
    const path = '/api/v1/inventory/purchase-intents/' + sourceId + '/receipts';
    async function loadSources() {
        const r = record(await request(url + '/receipt-sources?warehouseId=' + encodeURIComponent(warehouseId)));
        check(r.state === 'ready' && Array.isArray(r.sources));
        for (const value of r.sources) {
            const s = record(value);
            check(uuid(s.id) && q6(s.orderedQuantity) && q6(s.unitPurchasePrice) && typeof s.externalOrderReference === 'string' && /^GiobbyPurchaseOrder-[1-9]\d*$/.test(s.externalOrderReference) && typeof s.supplierName === 'string' && typeof s.description === 'string');
        }
        return r.sources as Source[];
    }
    async function read() {
        const r = record(await request(path));
        check(r.state === 'ready' && r.sourceIntentId === sourceId && r.nonAuthoritative === true && r.erpPerOrderResidual === null && r.linkKind === 'internal_standalone_not_erp_native' && r.precisionDiscrepancy === 'receipt_q6_stock_report_q5_observed');
        for (const k of ['orderedQuantity', 'acceptedQuantity', 'uncertainQuantity', 'remainingQuantity']) check(q6(r[k]));
        check(Array.isArray(r.receipts));
        for (const value of r.receipts) {
            const receipt = record(value), snapshot = record(receipt.snapshot), delivery = record(receipt.delivery);
            check(uuid(receipt.id) && q6(snapshot.quantity) && q6(snapshot.unitPrice));
            check(receipt.status === 'PendingUnconfirmed' || receipt.status === 'Confirmed');
            check(delivery.state === 'Queued' || delivery.state === 'Uncertain' || delivery.state === 'Completed');
            check(delivery.knownDocumentId === null || Number.isSafeInteger(delivery.knownDocumentId) && Number(delivery.knownDocumentId) > 0);
            check(delivery.lastError === null || typeof delivery.lastError === 'string');
            check(receipt.externalReference === null || typeof receipt.externalReference === 'string' && /^GiobbyReceipt-[1-9]\d*$/.test(receipt.externalReference));
        }
        return r as State;
    }
    function failed(e: unknown) {
        setState(undefined);
        if (e instanceof ApiError && (e.status === 403 || e.status === 404)) { setSources(undefined); setMessage('Ricevimento non autorizzato o sorgente non accessibile: serve il grant dedicato inventory.receipts.create su società, sede e magazzino.'); }
        else setMessage('Lettura ricevimento non disponibile. Rileggi.');
        onError(e);
    }
    useEffect(() => {
        let active = true;
        void loadSources().then(s => { if (active) setSources(s); }).catch(e => { if (active) failed(e); });
        return () => { active = false; };
    }, [url, warehouseId]);
    useEffect(() => {
        const gen = ++generation.current; setState(undefined);
        if (source) void read().then(s => { if (gen === generation.current) setState(s); }).catch(e => { if (gen === generation.current) failed(e); });
        return () => { generation.current++; };
    }, [sourceId]);
    async function refresh() {
        if (busy || blocked) return;
        ++generation.current;
        setBusy(true);
        try {
            const available = await loadSources();
            setSources(available);
            if (sourceId) {
                const next = await read();
                if (frozen.current && !next.receipts.some(r => r.id === JSON.parse(frozen.current!.body).id)) {
                    setState(next); setMessage('Comando non ancora presente nello storico: conserva il comando originale.'); return;
                }
                setState(next); frozen.current = undefined; setPending(false); setRetryable(false);
                setMessage('Ricevimenti riletti dal server.');
            }
        } catch (e) { failed(e); }
        finally { setBusy(false); }
    }
    async function create() {
        if (busy || blocked) return;
        if (!frozen.current) {
            if (!source || !state || closed) return;
            if (!quantityPattern.test(quantity) || micros(quantity) <= 0n || micros(quantity) > micros(state.remainingQuantity)) {
                setMessage('Quantità positiva q6, non oltre la capacità disponibile. Il server verifica il limite cumulativo.'); input.current?.focus(); return;
            }
            frozen.current = { path, body: JSON.stringify({ id: crypto.randomUUID(), quantity }) };
        }
        const command = frozen.current;
        ++generation.current;
        setBusy(true); setPending(true);
        try {
            await request(command.path, JSON.parse(command.body));
            setRetryable(false); setState(undefined);
            try {
                const next = await read();
                check(next.receipts.some(r => r.id === JSON.parse(command.body).id));
                setState(next); frozen.current = undefined; setPending(false); setQuantity(''); setMessage('Ricevimento registrato e riletto dal server.');
            } catch (e) {
                if (e instanceof ApiError && (e.status === 403 || e.status === 404)) failed(e);
                else { setMessage('Comando registrato; rilettura autorevole ancora necessaria. Nessun nuovo comando.'); onError(e); }
            }
        } catch (e) {
            if (e instanceof ApiError && e.status < 500 && !retryable) {
                frozen.current = undefined; setPending(false); failed(e);
            } else if (e instanceof ApiError && (e.status === 403 || e.status === 404)) { failed(e); }
            else { setRetryable(true); setMessage('Risposta client incerta: riprova solo il comando identico, non un nuovo ricevimento.'); }
        } finally { setBusy(false); }
    }
    const locked = busy || pending || blocked;
    return <section aria-label="Ricevimento merce">
        <h3>Ricevimento merce · azione dedicata</h3><p role="status">{message}</p>
        <label>Ordine acquisto confermato<select disabled={locked} value={sourceId} onChange={e => setSourceId(e.target.value)}><option value="">Seleziona ordine</option>{sources?.map(s => <option key={s.id} value={s.id}>{s.externalOrderReference} · {s.supplierName} · {s.description}</option>)}</select></label>
        {source && state && <>
            <p>Costo acquisto congelato: {source.unitPurchasePrice}</p>
            <p>Quantità ordinata: {state.orderedQuantity}</p><p>Ricevuto confermato cumulativo: {state.acceptedQuantity}</p><p>Quantità impegnata non confermata (include coda e HOLD): {state.uncertainQuantity}</p><p>Capacità ricevimento disponibile: {state.remainingQuantity}</p>
            <p>Residuo interno non autorevole (ordinato meno soli ricevimenti confermati): {format(micros(state.orderedQuantity) - micros(state.acceptedQuantity))}. La quota incerta resta impegnata e non si libera per timeout.</p>
            <p>Giobby è l'unica autorità per stock e documenti. Residuo ERP per ordine: SCONOSCIUTO, non ricavato dallo stock aggregato. Collegamento solo interno all'ordine congelato; collegamento nativo ERP non provato. Nessuna modifica all'ordine sorgente da questa azione.</p>
            <p>Discrepanza precisione: receipt q6 / report stock 5 decimali, limite osservato sandbox R05.a.9; non è una lettura stock live. Ordine sorgente osservato invariato nel sandbox, non una verifica corrente. Nessuna correzione stock automatica o riprezzatura. Gap storico raw/ledger non riparato.</p>
        </>}
        {source && state?.receipts.map(r => <article key={r.id} aria-label={'Ricevimento ' + r.id}><p>Ricevimento {r.id} · quantità {r.snapshot.quantity} · costo congelato {r.snapshot.unitPrice}</p><p>{deliveryText(r)}</p></article>)}
        {state && quantity && <p role="status">{quantityPattern.test(quantity) && micros(quantity) > 0n && micros(quantity) <= micros(state.remainingQuantity)
            ? 'Anteprima quantità: ' + format(micros(quantity)) + ' · capacità dopo comando: ' + format(micros(state.remainingQuantity) - micros(quantity)) + ' (da verificare dal server)'
            : 'Anteprima non valida: quantità positiva q6 entro la capacità disponibile.'}</p>}
        <form onSubmit={e => { e.preventDefault(); void create(); }}><label>Quantità da ricevere<input ref={input} value={quantity} disabled={locked} onChange={e => setQuantity(e.target.value)} /></label><button disabled={locked || closed || !state || !source}>Crea ricevimento esplicito</button></form>
        <button disabled={busy || blocked} onClick={() => void refresh()}>Rileggi ricevimenti</button>
        {pending && retryable && <button disabled={busy || blocked} onClick={() => void create()}>Riprova comando identico</button>}
    </section>;
}
