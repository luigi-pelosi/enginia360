import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workshopApi";
import { check, decimal, record, uuid } from "./contracts";


type NewReturn = {id:string; quantity:string; workingGroupId:string; returnedAt:string; operatorId:string};
type Returning = { remainingWithTechnician:string; returned:string; canReturn:boolean; reason:string; returns:NewReturn[] };
export default function MaterialNewReturn({
    url,
    picks,
    closed,
    blocked,
    onBlocked,
    onApplied,
    onError,
}: Readonly<{
    url: string;
    picks: { id: string; quantity: string }[];
    closed: boolean;
    blocked: boolean;
    onBlocked: (blocked: boolean) => void;
    onApplied: () => Promise<void>;
    onError: (e: unknown) => void;
}>) {
    const [pickId, setPickId] = useState(""),
        [quantity, setQuantity] = useState("");
    const [state, setState] = useState<Returning>(),
        [message, setMessage] = useState("Seleziona un prelievo: solo nuovo integro mai installato."),
        [busy, setBusy] = useState(false),
        [uncertain, setUncertain] = useState(false);
    const quantityInput=useRef<HTMLInputElement>(null);
    useEffect(() => {
        onBlocked(busy || uncertain);
    }, [busy, uncertain, onBlocked]);
    useEffect(() => () => onBlocked(false), [onBlocked]);
    const generation = useRef(0),
        frozen = useRef<
            { url: string; body: { id: string; quantity: string } } | undefined
        >(undefined);
    const path = url + "/" + pickId + "/new-part-returns";
    const readSequence = useRef(0);
    async function read(gen = generation.current) {
        const serial = ++readSequence.current;
        const r = record(await request(path));
        check(
            r.pickId === pickId &&
                typeof r.remainingWithTechnician === "string" &&
                /^\d+(?:\.\d{1,6})?$/.test(r.remainingWithTechnician) &&
                typeof r.canReturn === "boolean" && typeof r.reason === "string" &&
                Array.isArray(r.returns),
        );
        check(typeof r.returned === "string" && /^\d+(?:\.\d{1,6})?$/.test(r.returned));
        for (const value of r.returns) {
            const p = record(value);
            check(
                uuid(p.id) &&
                    uuid(p.workingGroupId) &&
                    typeof p.quantity === "string" &&
                    typeof p.returnedAt === "string" && uuid(p.operatorId),
            );
        }
        if (gen === generation.current && serial === readSequence.current)
            setState(r as Returning);
    }
    useEffect(() => {
        const gen = ++generation.current;
        setState(undefined);
        if (pickId)
            void read(gen).catch((e) => {
                if (gen === generation.current) {
                    setMessage("Lettura resi non disponibile.");
                    onError(e);
                }
            });
        return () => {
            generation.current++;
        };
    }, [path]);
    async function returnPart() {
        if (busy) return;
        if (
            !frozen.current &&
            (!decimal(quantity) || !/[1-9]/.test(quantity))
        ) {
            setMessage("Quantità positiva con massimo 6 decimali.");
            quantityInput.current?.focus();
            return;
        }
        const command = frozen.current ?? {
            url: path,
            body: { id: crypto.randomUUID(), quantity },
        };
        frozen.current = command;
        readSequence.current++;
        const gen = generation.current;
        setBusy(true);
        try {
            await request(command.url, command.body);
            if (gen !== generation.current) return;
            frozen.current = undefined;
            setUncertain(false);
            setState(undefined);
            setMessage(
                "Reso registrato; stato non verificato. Rileggi resi.",
            );
            try {
                await onApplied();
                await read(gen);
                if (gen === generation.current)
                    setMessage(
                        "Reso registrato e riletto; fisico e riga commerciale invariati.",
                    );
            } catch (e) {
                if (gen === generation.current) onError(e);
            }
        } catch (e) {
            if (gen !== generation.current) return;
            if (e instanceof ApiError && e.status < 500) {
                setState(undefined);
                if (e.status === 401) setQuantity("");
                frozen.current = undefined;
                setUncertain(false);
                setMessage(
                    e.code === "picking_configuration_missing"
                        ? "Configurazione di reso non disponibile."
                        : e.message,
                );
                onError(e);
            } else {
                setUncertain(true);
                setMessage(
                    "Esito reso incerto: riprova solo il comando identico.",
                );
            }
        } finally {
            if (gen === generation.current) setBusy(false);
        }
    }
    return (
        <section aria-label="Reso nuovo integro mai installato">
            <label>
                Prelievo da restituire
                <select
                    value={pickId}
                    disabled={
                        blocked || busy || uncertain
                    }
                    onChange={(e) => setPickId(e.target.value)}
                >
                    <option value="">Seleziona prelievo</option>
                    {picks.map((r) => (
                        <option key={r.id} value={r.id}>
                            {r.id} · {r.quantity}
                        </option>
                    ))}
                </select>
            </label>
            <p role="status">{message}</p>
            {state && (
                <>
                    <p>Restituito: {state.returned}</p>
                    <p>{({ready:"Reso esplicito consentito: conferma nuovo integro mai installato.",pick_has_installations:"Prelievo con installazione registrata, anche Pending: reso non consentito.",order_or_line_not_open:"Commessa chiusa o riga rimossa: solo storico.",no_remaining:"Nessun residuo restituibile.",stock_profile_missing:"Profilo stock mancante: solo storico.",stock_profile_external:"Stock esterno: solo storico.",permission_or_capability:"Permesso specifico o capability non disponibili."} as Record<string,string>)[state.reason] ?? "Stato non riconosciuto: rileggi prima di operare."}</p>
                    <p>
                        Residuo presso operatore:{" "}
                        {state.remainingWithTechnician}
                    </p>
                    {state.returns.map((p) => (
                        <p key={p.id}>
                            Reso {p.id} · {p.quantity} · Gruppo{" "}
                            {p.workingGroupId} ·{" "}
                            {p.returnedAt} · Operatore {p.operatorId}
                        </p>
                    ))}
                </>
            )}
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    void returnPart();
                }}
            >
                <label>
                    Quantità da restituire
                    <input
                        ref={quantityInput}
                        value={quantity}
                        disabled={
                            blocked || busy || uncertain
                        }
                        onChange={(e) => setQuantity(e.target.value)}
                    />
                </label>
                <button
                    disabled={
                        blocked ||
                        busy ||
                        uncertain ||
                        closed ||
                        !state?.canReturn
                    }
                >
                    Restituisci quantità esplicita
                </button>
            </form>
            {uncertain && (
                <button disabled={busy} onClick={() => void returnPart()}>
                    Riprova reso identico
                </button>
            )}
            <button
                disabled={
                    blocked || busy || !pickId
                }
                onClick={() => {
                    const gen = generation.current;
                    void read(gen).then(() => {
                        if (gen === generation.current) setMessage("Stato reso riletto dal server.");
                    }).catch((e) => {
                        if (gen === generation.current) {
                            setMessage("Lettura resi non disponibile.");
                            onError(e);
                        }
                    });
                }}
            >
                Rileggi resi
            </button>

        </section>
    );
}
