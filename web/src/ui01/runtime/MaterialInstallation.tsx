import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workshopApi";
import { check, decimal, record, uuid } from "./contracts";

type Installation = {
    installation: { id: string; quantity: string };
    stockEffect: "Pending" | "Consumed";
};
type State = {
    remainingToInstall: string;
    canInstall: boolean;
    canRecoverConsumption: boolean;
    installations: Installation[];
};
export default function MaterialInstallation({
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
    const [state, setState] = useState<State>(),
        [message, setMessage] = useState("Seleziona un prelievo specifico."),
        [busy, setBusy] = useState(false),
        [uncertain, setUncertain] = useState(false);
    useEffect(() => {
        onBlocked(busy || uncertain);
    }, [busy, uncertain, onBlocked]);
    useEffect(() => () => onBlocked(false), [onBlocked]);
    const generation = useRef(0),
        frozen = useRef<
            { url: string; body: { id: string; quantity: string } } | undefined
        >(undefined);
    const path =
        url.replace("/inventory/", "/workshop/") +
        "/picks/" +
        pickId +
        "/installations";
    const readSequence = useRef(0);
    async function read(gen = generation.current) {
        const serial = ++readSequence.current;
        const r = record(await request(path));
        check(
            typeof r.remainingToInstall === "string" &&
                /^\d+(?:\.\d{1,6})?$/.test(r.remainingToInstall) &&
                typeof r.canInstall === "boolean" &&
                Array.isArray(r.installations),
        );
        for (const value of r.installations) {
            const p = record(value),
                i = record(p.installation);
            check(
                uuid(i.id) &&
                    typeof i.quantity === "string" &&
                    (p.stockEffect === "Pending" ||
                        p.stockEffect === "Consumed"),
            );
        }
        if (gen === generation.current && serial === readSequence.current)
            setState(r as State);
    }
    useEffect(() => {
        const gen = ++generation.current;
        setState(undefined);
        if (pickId)
            void read(gen).catch((e) => {
                if (gen === generation.current) {
                    setMessage("Lettura installazioni non disponibile.");
                    onError(e);
                }
            });
        return () => {
            generation.current++;
        };
    }, [path]);
    async function install(recovery?: Installation) {
        if (busy) return;
        if (
            !frozen.current &&
            !recovery &&
            (!decimal(quantity) || !/[1-9]/.test(quantity))
        ) {
            setMessage("Quantità positiva con massimo 6 decimali.");
            return;
        }
        const command = frozen.current ?? {
            url: path,
            body: recovery
                ? {
                      id: recovery.installation.id,
                      quantity: recovery.installation.quantity,
                  }
                : { id: crypto.randomUUID(), quantity },
        };
        frozen.current = command;
        readSequence.current++;
        const gen = generation.current;
        setBusy(true);
        try {
            const result = record(await request(command.url, command.body));
            check(
                result.stockEffect === "Pending" ||
                    result.stockEffect === "Consumed",
            );
            if (gen !== generation.current) return;
            frozen.current = undefined;
            setUncertain(false);
            setState(undefined);
            setMessage(
                "Installazione registrata; stato non verificato. Rileggi installazioni.",
            );
            try {
                await onApplied();
                await read(gen);
                if (gen === generation.current)
                    setMessage(
                        result.stockEffect === "Pending"
                            ? "Installazione accettata; consumo Pending da recuperare."
                            : "Installazione e consumo registrati e riletti.",
                    );
            } catch (e) {
                if (gen === generation.current) onError(e);
            }
        } catch (e) {
            if (gen !== generation.current) return;
            if (e instanceof ApiError && e.status < 500) {
                frozen.current = undefined;
                setUncertain(false);
                setMessage(e.message);
                onError(e);
            } else {
                setUncertain(true);
                setMessage(
                    "Esito installazione incerto: riprova solo il comando identico.",
                );
            }
        } finally {
            if (gen === generation.current) setBusy(false);
        }
    }
    return (
        <section aria-label="Installazione prelievo">
            <label>
                Prelievo da installare
                <select
                    value={pickId}
                    disabled={blocked || busy || uncertain}
                    onChange={(e) => setPickId(e.target.value)}
                >
                    <option value="">Seleziona prelievo</option>
                    {picks.map((p) => (
                        <option key={p.id} value={p.id}>
                            {p.id} · {p.quantity}
                        </option>
                    ))}
                </select>
            </label>
            <p role="status">{message}</p>
            {state && (
                <>
                    <p>
                        Residuo prelievo da installare:{" "}
                        {state.remainingToInstall}
                    </p>
                    {state.installations.map((p) => (
                        <div key={p.installation.id}>
                            <p>
                                Installazione {p.installation.id} ·{" "}
                                {p.installation.quantity} · {p.stockEffect}
                            </p>
                            {p.stockEffect === "Pending" && (
                                <button
                                    disabled={
                                        blocked ||
                                        busy ||
                                        uncertain ||
                                        !state.canRecoverConsumption
                                    }
                                    onClick={() => void install(p)}
                                >
                                    Recupera consumo {p.installation.id}
                                </button>
                            )}
                        </div>
                    ))}
                </>
            )}
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    void install();
                }}
            >
                <label>
                    Quantità da installare
                    <input
                        value={quantity}
                        disabled={blocked || busy || uncertain}
                        onChange={(e) => setQuantity(e.target.value)}
                    />
                </label>
                <button
                    disabled={
                        blocked ||
                        busy ||
                        uncertain ||
                        closed ||
                        !state?.canInstall
                    }
                >
                    Installa quantità esplicita
                </button>
            </form>
            {uncertain && (
                <button disabled={busy} onClick={() => void install()}>
                    Riprova installazione identica
                </button>
            )}
            <button
                disabled={blocked || busy || !pickId}
                onClick={() =>
                    void read().catch((e) => {
                        setMessage("Lettura installazioni non disponibile.");
                        onError(e);
                    })
                }
            >
                Rileggi installazioni
            </button>
        </section>
    );
}
