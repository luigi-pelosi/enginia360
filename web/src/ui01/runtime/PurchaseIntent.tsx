import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workshopApi";
import { check, decimal, record, uuid } from "./contracts";

type Supplier = { id: string; name: string; revision: number; mappingRevision: number };
type Intent = { id: string; quantity: string; supplierName: string; status: string };
type State = { source: { revision: number }; remaining: string; suppliers: Supplier[]; intents: Intent[] };
const q6 = /^\d+(?:\.\d{1,6})?$/;
// D88/D90: manual pending intent; no vendor identifier, destination or ERP value is ever shown or sent by the browser.
export default function PurchaseIntent({ url, warehouseId, closed, blocked, onBlocked, onError }: Readonly<{
    url: string; warehouseId: string; closed: boolean; blocked: boolean; onBlocked: (blocked: boolean) => void; onError: (e: unknown) => void;
}>) {
    const [state, setState] = useState<State>(), [supplierId, setSupplierId] = useState(""), [quantity, setQuantity] = useState("");
    const [message, setMessage] = useState("Seleziona fornitore e quantità."), [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false);
    const frozen = useRef<{ path: string; body: string } | undefined>(undefined), generation = useRef(0), quantityInput = useRef<HTMLInputElement>(null);
    const path = url + "/purchase-intents";
    useEffect(() => { onBlocked(busy || uncertain); }, [busy, uncertain, onBlocked]);
    useEffect(() => () => onBlocked(false), [onBlocked]);
    async function read(gen = generation.current) {
        const r = record(await request(path + "?warehouseId=" + encodeURIComponent(warehouseId)));
        check(r.state === "ready" && typeof r.remaining === "string" && q6.test(r.remaining) && Array.isArray(r.suppliers) && Array.isArray(r.intents));
        const source = record(r.source);
        check(Number.isSafeInteger(source.revision));
        for (const value of r.suppliers) { const s = record(value); check(uuid(s.id) && typeof s.name === "string" && Number.isSafeInteger(s.revision) && Number.isSafeInteger(s.mappingRevision)); }
        for (const value of r.intents) { const i = record(value); check(uuid(i.id) && typeof i.quantity === "string" && typeof i.supplierName === "string" && typeof i.status === "string"); }
        if (gen === generation.current) setState({ source: { revision: source.revision as number }, remaining: r.remaining, suppliers: r.suppliers as Supplier[], intents: r.intents as Intent[] });
    }
    useEffect(() => {
        const gen = ++generation.current; setState(undefined);
        void read(gen).catch((e) => { if (gen === generation.current) { setMessage("Lettura richieste d'acquisto non disponibile."); onError(e); } });
        return () => { generation.current++; };
    }, [path, warehouseId]);
    async function create() {
        if (busy || !state) return;
        const supplier = state.suppliers.find((s) => s.id === supplierId);
        if (!frozen.current) {
            if (!supplier) { setMessage("Seleziona un fornitore."); return; }
            if (!decimal(quantity) || !q6.test(quantity) || !/[1-9]/.test(quantity) || Number(quantity) > Number(state.remaining)) {
                setMessage("Quantità positiva, massimo 6 decimali e non oltre il residuo richiedibile."); quantityInput.current?.focus(); return;
            }
            frozen.current = { path, body: JSON.stringify({ id: crypto.randomUUID(), warehouseId, supplierId, sourceRevision: state.source.revision, supplierRevision: supplier.revision, mappingRevision: supplier.mappingRevision, quantity }) };
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
                <button disabled={locked || closed || !state || Number(state.remaining) <= 0}>Crea richiesta d'acquisto</button>
            </form>
            {uncertain && <button disabled={busy} onClick={() => void create()}>Riprova richiesta identica</button>}
            {state?.intents.map((i) => <p key={i.id}>Richiesta {i.id} · {Number(i.quantity)} · {i.supplierName} · {i.status === "Held" ? "In attesa — connettore d'acquisto non ancora attivo" : i.status}</p>)}
        </section>
    );
}
