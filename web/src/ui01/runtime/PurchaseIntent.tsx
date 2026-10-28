import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workshopApi";
import { check, decimal, record, uuid } from "./contracts";

type Quote = { revision: number; catalogVersion: number; authorityVersion: number; sourcePresent: boolean; unitPurchasePrice: string | null };
type Supplier = { id: string; name: string; revision: number; mappingRevision: number };
type AcceptedPrice = { unitPurchasePrice: string; sourcePresent: boolean; revision: number; method: "manual" | "listed" };
type Dispatch = { state: "queued" | "uncertain" | "confirmed" | "not_sendable"; reason: "configuration_missing" | "unpriced" | null; externalReference: string | null };
type Intent = { id: string; quantity: string; supplierName: string; status: string; acceptedPrice?: AcceptedPrice | null; dispatch?: Dispatch | null };
type State = { source: { revision: number }; remaining: string; suppliers: Supplier[]; intents: Intent[] };
const q6 = /^\d+(?:\.\d{1,6})?$/;
const reference = /^[A-Za-z0-9][A-Za-z0-9-]{0,63}$/;
// Server-derived technical readout. The Giobby order status is never stock authority (D82) and no action follows from it.
function dispatchText(d: Dispatch): string {
    switch (d.state) {
        case "queued": return d.reason === "configuration_missing" ? "Non inviata · configurazione acquisti mancante: richiesta trattenuta" : "Non inviata · in coda per l'invio";
        case "uncertain": return "In verifica · esito dell'ordine incerto: nessun nuovo invio automatico" + (d.reason === "configuration_missing" ? " · configurazione acquisti da verificare" : "");
        case "confirmed": return "Confermata · riferimento ordine Giobby: " + d.externalReference;
        default: return "Non inviabile · richiesta senza prezzo: mai inviata";
    }
}
// D88/D90: manual pending intent; no vendor identifier, destination or ERP value is ever shown or sent by the browser.
export default function PurchaseIntent({ url, warehouseId, closed, blocked, onBlocked, onError }: Readonly<{
    url: string; warehouseId: string; closed: boolean; blocked: boolean; onBlocked: (blocked: boolean) => void; onError: (e: unknown) => void;
}>) {
    const [state, setState] = useState<State>(), [supplierId, setSupplierId] = useState(""), [quantity, setQuantity] = useState("");
    const [message, setMessage] = useState("Seleziona fornitore e quantità."), [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
    const frozen = useRef<{ path: string; body: string } | undefined>(undefined), generation = useRef(0), quantityInput = useRef<HTMLInputElement>(null);
    const [quoteRefresh, setQuoteRefresh] = useState(0);
    const [quote, setQuote] = useState<Quote>(), [manualPrice, setManualPrice] = useState("0.000000"), [priceEntered, setPriceEntered] = useState(false);
    const path = url + "/purchase-intents";
    useEffect(() => {
        let active = true; setQuote(undefined); setManualPrice("0.000000"); setPriceEntered(false);
        if (supplierId) void request(path + "/quote?warehouseId=" + encodeURIComponent(warehouseId) + "&supplierId=" + encodeURIComponent(supplierId)).then(value => {
            const result = record(value), q = record(result.quote);
            check(result.state === "ready" && Number.isSafeInteger(q.revision) && Number.isSafeInteger(q.catalogVersion) && Number.isSafeInteger(q.authorityVersion)
                && typeof q.sourcePresent === "boolean" && (q.sourcePresent ? typeof q.unitPurchasePrice === "string" && decimal(q.unitPurchasePrice) : q.unitPurchasePrice === null));
            if (active) setQuote(q as Quote);
        }).catch(e => { if (active) { setMessage("Quotazione acquisto non disponibile. Rileggi."); onError(e); } });
        return () => { active = false; };
    }, [path, warehouseId, supplierId, quoteRefresh]);
    useEffect(() => { onBlocked(busy || uncertain); }, [busy, uncertain, onBlocked]);
    useEffect(() => () => onBlocked(false), [onBlocked]);
    async function read(gen = generation.current) {
        const r = record(await request(path + "?warehouseId=" + encodeURIComponent(warehouseId)));
        check(r.state === "ready" && typeof r.remaining === "string" && q6.test(r.remaining) && Array.isArray(r.suppliers) && Array.isArray(r.intents));
        const source = record(r.source);
        check(Number.isSafeInteger(source.revision));
        for (const value of r.suppliers) { const s = record(value); check(uuid(s.id) && typeof s.name === "string" && Number.isSafeInteger(s.revision) && Number.isSafeInteger(s.mappingRevision)); }
        for (const value of r.intents) {
            const i = record(value); check(uuid(i.id) && typeof i.quantity === "string" && typeof i.supplierName === "string" && typeof i.status === "string");
            if (i.dispatch != null) {
                const d = record(i.dispatch);
                check((d.state === "queued" || d.state === "uncertain") && (d.reason === null || d.reason === "configuration_missing") && d.externalReference === null
                    || d.state === "confirmed" && d.reason === null && typeof d.externalReference === "string" && reference.test(d.externalReference)
                    || d.state === "not_sendable" && d.reason === "unpriced" && d.externalReference === null);
            }
            if (i.acceptedPrice != null) { const p = record(i.acceptedPrice); check(typeof p.unitPurchasePrice === "string" && decimal(p.unitPurchasePrice) && typeof p.sourcePresent === "boolean" && Number.isSafeInteger(p.revision) && (p.method === "manual" || p.method === "listed")); }
        }
        if (gen === generation.current) setState({ source: { revision: source.revision as number }, remaining: r.remaining, suppliers: r.suppliers as Supplier[], intents: r.intents as Intent[] });
    }
    useEffect(() => {
        const gen = ++generation.current; setState(undefined);
        void read(gen).catch((e) => { if (gen === generation.current) { setMessage("Lettura richieste d'acquisto non disponibile."); onError(e); } });
        return () => { generation.current++; };
    }, [path, warehouseId]);
    async function refresh() {
        if (busy || uncertain || blocked) return;
        const gen = generation.current;
        setBusy(true);
        try {
            await read(gen);
            if (gen === generation.current) {
                setMessage("Richieste rilette. Verifica la quotazione prima di confermare.");
                setQuoteRefresh(value => value + 1);
            }
        } catch (e) {
            // A refused reread means the grant or source access is gone: never keep showing the earlier readout or reference.
            if (gen === generation.current) { if (e instanceof ApiError && (e.status === 403 || e.status === 404)) setState(undefined); setMessage("Lettura richieste d'acquisto non disponibile."); onError(e); }
        } finally { if (gen === generation.current) setBusy(false); }
    }
    async function create() {
        if (busy || !state) return;
        const supplier = state.suppliers.find((s) => s.id === supplierId);
        if (!frozen.current) {
            if (!supplier) { setMessage("Seleziona un fornitore."); return; }
            if (!decimal(quantity) || !q6.test(quantity) || !/[1-9]/.test(quantity) || Number(quantity) > Number(state.remaining)) {
                setMessage("Quantità positiva, massimo 6 decimali e non oltre il residuo richiedibile."); quantityInput.current?.focus(); return;
            }
            if (!quote) { setMessage("Attendi la quotazione acquisto o rileggi."); return; }
            if (!quote.sourcePresent && (!priceEntered || !/^[0-9]{1,6}(?:\.[0-9]{1,6})?$/.test(manualPrice))) {
                setMessage("Prezzo mancante: inserisci esplicitamente il costo, anche zero."); return;
            }
            frozen.current = { path: path + "/accepted", body: JSON.stringify({ id: crypto.randomUUID(), warehouseId, supplierId, sourceRevision: state.source.revision, supplierRevision: supplier.revision, mappingRevision: supplier.mappingRevision, quantity, quoteRevision: quote.revision, catalogVersion: quote.catalogVersion, authorityVersion: quote.authorityVersion, manualUnitPurchasePrice: quote.sourcePresent ? null : manualPrice }) };
        }
        const command = frozen.current, gen = generation.current;
        setBusy(true);
        try {
            await request(command.path, JSON.parse(command.body));
            if (gen !== generation.current) return;
            frozen.current = undefined; setUncertain(false); setMessage("Richiesta registrata; stato non verificato. Rileggi.");
            try { await read(gen); if (gen === generation.current) setMessage("Richiesta registrata e riletta dal server."); } catch (e) { if (gen === generation.current) onError(e); }
        } catch (e) {
            if (gen !== generation.current) return;
            if (e instanceof ApiError && e.status < 500) { frozen.current = undefined; setUncertain(false); setMessage(e.message); onError(e); }
            else { setUncertain(true); setMessage("Esito richiesta d'acquisto incerto: riprova solo il comando identico."); }
        } finally { if (gen === generation.current) setBusy(false); }
    }
    const locked = blocked || busy || uncertain;
    return (
        <section aria-label="Richiesta d'acquisto">
            <p role="status">{message}</p>
            {state && <p>Residuo richiedibile: {Number(state.remaining)}</p>}
            {quote?.sourcePresent && <p>Costo unitario acquisto: {quote.unitPurchasePrice} · listino presente (revisione {quote.revision})</p>}
            <form onSubmit={(e) => { e.preventDefault(); void create(); }}>
                <label>Fornitore
                    <select value={supplierId} disabled={locked} onChange={(e) => setSupplierId(e.target.value)}>
                        <option value="">Seleziona fornitore</option>
                        {state?.suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                </label>
                <label>Quantità da richiedere
                    <input ref={quantityInput} value={quantity} disabled={locked} onChange={(e) => setQuantity(e.target.value)} />
                </label>
                {quote && !quote.sourcePresent && <label>Prezzo acquisto mancante
                    <input aria-label="Prezzo acquisto mancante" value={manualPrice} disabled={locked} onChange={e => { setManualPrice(e.target.value); setPriceEntered(true); }} />
                    <span>Listino assente · 0.000000 provvisorio, inserimento obbligatorio (anche zero).</span>
                </label>}
                <button disabled={locked || closed || !state || Number(state.remaining) <= 0}>Crea richiesta d'acquisto</button>
            </form>
            <button disabled={locked} onClick={() => void refresh()}>Rileggi richieste e quotazione</button>
            {uncertain && <button disabled={busy} onClick={() => void create()}>Riprova richiesta identica</button>}
            {state?.intents.map((i) => <div key={i.id}><p>Richiesta {i.id} · {Number(i.quantity)} · {i.supplierName}{i.dispatch ? "" : " · " + (i.status === "Held" ? "In attesa — connettore d'acquisto non ancora attivo" : i.status)}</p>
                {i.dispatch && <p>{dispatchText(i.dispatch)}</p>}
                {i.dispatch?.state === "confirmed" && <p>Lo stato dell'ordine non modifica le giacenze locali: il magazzino resta governato da Giobby.</p>}
                {i.acceptedPrice ? <p>Costo accettato: {i.acceptedPrice.unitPurchasePrice} · {i.acceptedPrice.sourcePresent ? "listino presente alla conferma (revisione " + i.acceptedPrice.revision + ")" : "listino assente alla conferma"} · {i.acceptedPrice.method === "manual" ? "inserimento operatore" : "prezzo di listino"}</p> : <p>Prezzo non congelato · richiesta storica bloccata, nessun invio.</p>}
            </div>)}
        </section>
    );
}
