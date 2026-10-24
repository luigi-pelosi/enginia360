import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workshopApi";
import { check, decimal, record, uuid } from "./contracts";
import MaterialInstallation from "./MaterialInstallation";

type Pick = {
    id: string;
    quantity: string;
    placementLocation: string | null;
    workingGroupId: string;
};
type Picking = { remainingToPick: string; canPick: boolean; picks: Pick[] };
export default function MaterialPicking({
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
    const [state, setState] = useState<Picking>(),
        [message, setMessage] = useState("Seleziona una prenotazione."),
        [busy, setBusy] = useState(false),
        [uncertain, setUncertain] = useState(false);
    const [installationBlocked, setInstallationBlocked] = useState(false);
    useEffect(() => {
        onBlocked(busy || uncertain || installationBlocked);
    }, [busy, uncertain, installationBlocked, onBlocked]);
    useEffect(() => () => onBlocked(false), [onBlocked]);
    const generation = useRef(0),
        frozen = useRef<
            { url: string; body: { id: string; quantity: string } } | undefined
        >(undefined);
    const path = url + "/reservations/" + reservationId + "/picks";
    const readSequence = useRef(0);
    async function read(gen = generation.current) {
        const serial = ++readSequence.current;
        const r = record(await request(path));
        check(
            r.reservationId === reservationId &&
                typeof r.remainingToPick === "string" &&
                /^\d+(?:\.\d{1,6})?$/.test(r.remainingToPick) &&
                typeof r.canPick === "boolean" &&
                Array.isArray(r.picks),
        );
        for (const value of r.picks) {
            const p = record(value);
            check(
                uuid(p.id) &&
                    uuid(p.workingGroupId) &&
                    typeof p.quantity === "string" &&
                    (p.placementLocation === null ||
                        typeof p.placementLocation === "string"),
            );
        }
        if (gen === generation.current && serial === readSequence.current)
            setState(r as Picking);
    }
    useEffect(() => {
        const gen = ++generation.current;
        setState(undefined);
        if (reservationId)
            void read(gen).catch((e) => {
                if (gen === generation.current) {
                    setMessage("Lettura prelievi non disponibile.");
                    onError(e);
                }
            });
        return () => {
            generation.current++;
        };
    }, [path]);
    async function pick() {
        if (busy) return;
        if (
            !frozen.current &&
            (!decimal(quantity) || !/[1-9]/.test(quantity))
        ) {
            setMessage("Quantità positiva con massimo 6 decimali.");
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
                "Prelievo registrato; stato non verificato. Rileggi prelievi.",
            );
            try {
                await onApplied();
                await read(gen);
                if (gen === generation.current)
                    setMessage(
                        "Prelievo registrato e riletto; nessuno scarico stock.",
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
                        ? "Configurazione di prelievo non disponibile."
                        : e.message,
                );
                onError(e);
            } else {
                setUncertain(true);
                setMessage(
                    "Esito prelievo incerto: riprova solo il comando identico.",
                );
            }
        } finally {
            if (gen === generation.current) setBusy(false);
        }
    }
    return (
        <section aria-label="Prelievo prenotazione">
            <label>
                Prenotazione da prelevare
                <select
                    value={reservationId}
                    disabled={
                        blocked || busy || uncertain || installationBlocked
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
                    <p>
                        Residuo prenotazione da prelevare:{" "}
                        {state.remainingToPick}
                    </p>
                    {state.picks.map((p) => (
                        <p key={p.id}>
                            Prelievo {p.id} · {p.quantity} · Gruppo{" "}
                            {p.workingGroupId} ·{" "}
                            {p.placementLocation === null
                                ? "Preparazione disabilitata: nessuna collocazione fittizia"
                                : "Preparazione: " + p.placementLocation}
                        </p>
                    ))}
                </>
            )}
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    void pick();
                }}
            >
                <label>
                    Quantità da prelevare
                    <input
                        value={quantity}
                        disabled={
                            blocked || busy || uncertain || installationBlocked
                        }
                        onChange={(e) => setQuantity(e.target.value)}
                    />
                </label>
                <button
                    disabled={
                        blocked ||
                        busy ||
                        uncertain ||
                        installationBlocked ||
                        closed ||
                        !state?.canPick
                    }
                >
                    Preleva quantità esplicita
                </button>
            </form>
            {uncertain && (
                <button disabled={busy} onClick={() => void pick()}>
                    Riprova prelievo identico
                </button>
            )}
            <button
                disabled={
                    blocked || busy || installationBlocked || !reservationId
                }
                onClick={() =>
                    void read().catch((e) => {
                        setMessage("Lettura prelievi non disponibile.");
                        onError(e);
                    })
                }
            >
                Rileggi prelievi
            </button>
            {state && (
                <MaterialInstallation
                    key={path}
                    url={url}
                    picks={state.picks}
                    closed={closed}
                    blocked={blocked || busy || uncertain}
                    onBlocked={setInstallationBlocked}
                    onApplied={async () => {
                        await onApplied();
                        await read();
                    }}
                    onError={onError}
                />
            )}
        </section>
    );
}
