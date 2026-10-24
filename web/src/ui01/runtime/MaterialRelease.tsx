import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workshopApi";
import { check, decimal, record, uuid } from "./contracts";


type Release = {id:string; quantity:string; workingGroupId:string; releasedAt:string; operatorId:string};
type Releasing = { remainingReleasable:string; released:string; canRelease:boolean; releases:Release[] };
export default function MaterialRelease({
    url,
    reservations,
    closed,
    blocked,
    onBlocked,
    onApplied,
    onError,
}: Readonly<{
    url: string;
    reservations: { id: string; quantity: string }[];
    closed: boolean;
    blocked: boolean;
    onBlocked: (blocked: boolean) => void;
    onApplied: () => Promise<void>;
    onError: (e: unknown) => void;
}>) {
    const [reservationId, setReservationId] = useState(""),
        [quantity, setQuantity] = useState("");
    const [state, setState] = useState<Releasing>(),
        [message, setMessage] = useState("Seleziona una prenotazione."),
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
    const path = url + "/reservations/" + reservationId + "/releases";
    const readSequence = useRef(0);
    async function read(gen = generation.current) {
        const serial = ++readSequence.current;
        const r = record(await request(path));
        check(
            r.reservationId === reservationId &&
                typeof r.remainingReleasable === "string" &&
                /^\d+(?:\.\d{1,6})?$/.test(r.remainingReleasable) &&
                typeof r.canRelease === "boolean" &&
                Array.isArray(r.releases),
        );
        check(typeof r.released === "string" && /^\d+(?:\.\d{1,6})?$/.test(r.released));
        for (const value of r.releases) {
            const p = record(value);
            check(
                uuid(p.id) &&
                    uuid(p.workingGroupId) &&
                    typeof p.quantity === "string" &&
                    typeof p.releasedAt === "string" && uuid(p.operatorId),
            );
        }
        if (gen === generation.current && serial === readSequence.current)
            setState(r as Releasing);
    }
    useEffect(() => {
        const gen = ++generation.current;
        setState(undefined);
        if (reservationId)
            void read(gen).catch((e) => {
                if (gen === generation.current) {
                    setMessage("Lettura rilasci non disponibile.");
                    onError(e);
                }
            });
        return () => {
            generation.current++;
        };
    }, [path]);
    async function release() {
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
                "Rilascio registrato; stato non verificato. Rileggi rilasci.",
            );
            try {
                await onApplied();
                await read(gen);
                if (gen === generation.current)
                    setMessage(
                        "Rilascio registrato e riletto; fisico e riga commerciale invariati.",
                    );
            } catch (e) {
                if (gen === generation.current) onError(e);
            }
        } catch (e) {
            if (gen !== generation.current) return;
            if (e instanceof ApiError && e.status < 500) {
                frozen.current = undefined;
                setUncertain(false);
                setMessage(
                    e.code === "picking_configuration_missing"
                        ? "Configurazione di rilascio non disponibile."
                        : e.message,
                );
                onError(e);
            } else {
                setUncertain(true);
                setMessage(
                    "Esito rilascio incerto: riprova solo il comando identico.",
                );
            }
        } finally {
            if (gen === generation.current) setBusy(false);
        }
    }
    return (
        <section aria-label="Rilascio prenotazione">
            <label>
                Prenotazione da rilasciare
                <select
                    value={reservationId}
                    disabled={
                        blocked || busy || uncertain
                    }
                    onChange={(e) => setReservationId(e.target.value)}
                >
                    <option value="">Seleziona prenotazione</option>
                    {reservations.map((r) => (
                        <option key={r.id} value={r.id}>
                            {r.id} · {r.quantity}
                        </option>
                    ))}
                </select>
            </label>
            <p role="status">{message}</p>
            {state && (
                <>
                    <p>Rilasciato: {state.released}</p>
                    <p>
                        Residuo mai prelevato rilasciabile:{" "}
                        {state.remainingReleasable}
                    </p>
                    {state.releases.map((p) => (
                        <p key={p.id}>
                            Rilascio {p.id} · {p.quantity} · Gruppo{" "}
                            {p.workingGroupId} ·{" "}
                            {p.releasedAt} · Operatore {p.operatorId}
                        </p>
                    ))}
                </>
            )}
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    void release();
                }}
            >
                <label>
                    Quantità da rilasciare
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
                        !state?.canRelease
                    }
                >
                    Rilascia quantità esplicita
                </button>
            </form>
            {uncertain && (
                <button disabled={busy} onClick={() => void release()}>
                    Riprova rilascio identico
                </button>
            )}
            <button
                disabled={
                    blocked || busy || !reservationId
                }
                onClick={() => {
                    const gen = generation.current;
                    void read(gen).then(() => {
                        if (gen === generation.current) setMessage("Stato rilascio riletto dal server.");
                    }).catch((e) => {
                        if (gen === generation.current) {
                            setMessage("Lettura rilasci non disponibile.");
                            onError(e);
                        }
                    });
                }}
            >
                Rileggi rilasci
            </button>

        </section>
    );
}
