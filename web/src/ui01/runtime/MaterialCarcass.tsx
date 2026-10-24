import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workshopApi";
import { check, decimal, record, uuid } from "./contracts";
type State = {
    outstanding: string;
    canReceiveCarcass: boolean;
    returns: {
        id: string;
        quantity: string;
        location: string;
        installations: { installationId: string; quantity: string }[];
    }[];
};
export default function MaterialCarcass({
    url,
    warehouseId,
    closed,
    blocked,
    onBlocked,
    onApplied,
    onError,
}: Readonly<{
    url: string;
    warehouseId: string;
    closed: boolean;
    blocked: boolean;
    onBlocked: (blocked: boolean) => void;
    onApplied: () => Promise<void>;
    onError: (e: unknown) => void;
}>) {
    const [state, setState] = useState<State>(),
        [quantity, setQuantity] = useState(""),
        [description, setDescription] = useState("");
    const [message, setMessage] = useState(
            "Rileggi il residuo prima di ricevere la carcassa.",
        ),
        [busy, setBusy] = useState(false),
        [uncertain, setUncertain] = useState(false);
    useEffect(() => {
        onBlocked(busy || uncertain);
    }, [busy, uncertain, onBlocked]);
    useEffect(() => () => onBlocked(false), [onBlocked]);
    const generation = useRef(0),
        frozen = useRef<
            | {
                  url: string;
                  body: {
                      id: string;
                      warehouseId: string;
                      quantity: string;
                      description: string;
                  };
              }
            | undefined
        >(undefined);
    const path = url + "/carcass-returns";
    useEffect(
        () => () => {
            generation.current++;
        },
        [],
    );
    const readSequence = useRef(0);
    async function read(gen = generation.current) {
        const serial = ++readSequence.current;
        const r = record(await request(path + "?warehouseId=" + warehouseId));
        check(
            typeof r.outstanding === "string" &&
                /^\d+(?:\.\d{1,6})?$/.test(r.outstanding) &&
                typeof r.canReceiveCarcass === "boolean" &&
                Array.isArray(r.returns),
        );
        for (const value of r.returns) {
            const c = record(value);
            check(
                uuid(c.id) &&
                    typeof c.quantity === "string" &&
                    typeof c.location === "string" &&
                    Array.isArray(c.installations),
            );
            for (const item of c.installations)
                check(uuid(record(item).installationId));
        }
        if (gen === generation.current && serial === readSequence.current)
            setState(r as State);
    }
    async function receive() {
        if (busy) return;
        if (
            !frozen.current &&
            (!decimal(quantity) ||
                !/[1-9]/.test(quantity) ||
                !description.trim() ||
                description !== description.trim() ||
                description.length > 200 ||
                /[\x00-\x1f\x7f]/.test(description))
        ) {
            setMessage(
                "Quantità positiva q6 e descrizione da 1 a 200 caratteri senza controlli.",
            );
            return;
        }
        const command = frozen.current ?? {
            url: path,
            body: {
                id: crypto.randomUUID(),
                warehouseId,
                quantity,
                description,
            },
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
                "Carcassa registrata; stato non verificato. Rileggi carcasse.",
            );
            try {
                await onApplied();
                await read(gen);
                if (gen === generation.current)
                    setMessage(
                        "Carcassa registrata e riletta; nessun reintegro dello stock nuovo.",
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
                    e.code === "must_cover_outstanding"
                        ? "Il rientro deve coprire esattamente tutto il residuo carcassa."
                        : e.message,
                );
                onError(e);
            } else {
                setUncertain(true);
                setMessage(
                    "Esito carcassa incerto: riprova solo il comando identico.",
                );
            }
        } finally {
            if (gen === generation.current) setBusy(false);
        }
    }
    return (
        <section aria-label="Rientro carcassa">
            <h3>Carcassa · ubicazione dedicata non vendibile</h3>
            <p role="status">{message}</p>
            <button
                disabled={busy}
                onClick={() =>
                    void read().catch((e) => {
                        setMessage("Lettura carcasse non disponibile.");
                        onError(e);
                    })
                }
            >
                Rileggi carcasse
            </button>
            {state && (
                <>
                    <p>Residuo carcassa (tutta la riga): {state.outstanding}</p>
                    {state.returns.map((c) => (
                        <div key={c.id}>
                            <p>
                                Carcassa {c.id} · {c.quantity} · {c.location}
                            </p>
                            {c.installations.map((i) => (
                                <p key={i.installationId}>
                                    Copertura installazione {i.installationId} ·{" "}
                                    {i.quantity}
                                </p>
                            ))}
                        </div>
                    ))}
                </>
            )}
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    void receive();
                }}
            >
                <label>
                    Quantità carcassa
                    <input
                        value={quantity}
                        disabled={blocked || busy || uncertain}
                        onChange={(e) => setQuantity(e.target.value)}
                    />
                </label>
                <label>
                    Descrizione carcassa
                    <input
                        value={description}
                        maxLength={200}
                        disabled={blocked || busy || uncertain}
                        onChange={(e) => setDescription(e.target.value)}
                    />
                </label>
                <button
                    disabled={
                        blocked ||
                        busy ||
                        uncertain ||
                        closed ||
                        !state?.canReceiveCarcass
                    }
                >
                    Ricevi intero residuo carcassa
                </button>
            </form>
            {uncertain && (
                <button disabled={busy} onClick={() => void receive()}>
                    Riprova carcassa identica
                </button>
            )}
        </section>
    );
}
