import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "./workshopApi";
import { check, decimal, record, uuid } from "./contracts";
import type { Editor } from "./editorContracts";
import MaterialPicking from "./MaterialPicking";
import MaterialCarcass from "./MaterialCarcass";

type Warehouse = { id: string; name: string };
type Stock = {
    physical: string;
    available: string;
    reserved: string;
    remaining: string;
    activeCommitted: string;
    consumed: string;
    canReserve: boolean;
    stockProfile: "local" | "external" | "missing";
    reservations: { id: string; quantity: string }[];
};
// Aggregates are not command inputs: do not impose the six-integer-digit command limit.
const aggregate = (v: unknown): v is string =>
    typeof v === "string" && /^-?\d+(?:\.\d{1,6})?$/.test(v);
export default function MaterialOperations({
    editor,
    onError,
}: Readonly<{ editor: Editor; onError: (error: unknown) => void }>) {
    const { order } = editor;
    const [lineId, setLineId] = useState(""),
        [warehouseId, setWarehouseId] = useState("");
    const [warehouses, setWarehouses] = useState<Warehouse[]>([]),
        [stock, setStock] = useState<Stock>();
    const [quantity, setQuantity] = useState(""),
        [message, setMessage] = useState(
            "Seleziona riga ricambio e magazzino.",
        ),
        [busy, setBusy] = useState(false);
    const frozen = useRef<
        | {
              url: string;
              body: {
                  id: string;
                  warehouseId: string;
                  quantity: string;
                  catalogVersion: number;
              };
          }
        | undefined
    >(undefined);
    const [uncertain, setUncertain] = useState(false);
    const [pickingBlocked, setPickingBlocked] = useState(false),
        [carcassBlocked, setCarcassBlocked] = useState(false);
    const [choices, setChoices] = useState<{
        key: string;
        items: { id: string; quantity: string }[];
    }>();
    const locked = busy || uncertain || pickingBlocked || carcassBlocked;
    const generation = useRef(0),
        quantityInput = useRef<HTMLInputElement>(null);
    const rows = editor.rows.filter((r) => r.kind === "Part");
    const row = rows.find((r) => r.id === lineId);
    const url = "/api/v1/inventory/orders/" + order.id + "/lines/" + lineId;
    const warehouseGeneration = useRef(0);
    async function loadWarehouses() {
        const gen = ++warehouseGeneration.current;
        try {
            const value = await request(
                "/api/v1/inventory/warehouses?legalEntityId=" +
                    order.legalEntityId +
                    "&siteId=" +
                    order.siteId,
            );
            check(Array.isArray(value));
            const choices = value.map((v) => {
                const r = record(v);
                check(uuid(r.id) && typeof r.name === "string");
                return { id: r.id as string, name: r.name as string };
            });
            if (gen === warehouseGeneration.current) {
                setWarehouses(choices);
                setMessage(
                    "Magazzini riletti; seleziona riga ricambio e magazzino.",
                );
            }
        } catch (e) {
            if (gen === warehouseGeneration.current) {
                setMessage("Magazzini non disponibili.");
                onError(e);
            }
        }
    }
    useEffect(() => {
        void loadWarehouses();
        return () => {
            warehouseGeneration.current++;
            generation.current++;
        };
    }, [order.id, order.legalEntityId, order.siteId]);
    const readSequence = useRef(0);
    async function read(gen = generation.current) {
        const serial = ++readSequence.current;
        const value = record(
            await request(url + "?warehouseId=" + warehouseId),
        );
        check(
            value.orderId === order.id &&
                value.lineId === lineId &&
                value.warehouseId === warehouseId,
        );
        for (const key of [
            "physical",
            "available",
            "reserved",
            "remaining",
            "activeCommitted",
            "consumed",
        ])
            check(aggregate(value[key]));
        check(typeof value.canReserve === "boolean");
        check(
            value.stockProfile === "local" ||
                value.stockProfile === "external" ||
                value.stockProfile === "missing",
        );
        check(Array.isArray(value.reservations));
        for (const reservation of value.reservations) {
            const r = record(reservation);
            check(uuid(r.id) && aggregate(r.quantity));
        }
        if (gen === generation.current && serial === readSequence.current) {
            setStock(value as Stock);
            setChoices({
                key: url + warehouseId,
                items: (value as Stock).reservations,
            });
        }
    }
    useEffect(() => {
        const gen = ++generation.current;
        setStock(undefined);
        if (row && warehouseId)
            void read(gen).catch((e) => {
                if (gen === generation.current) {
                    setMessage("Lettura materiali non disponibile.");
                    onError(e);
                }
            });
        return () => {
            generation.current++;
        };
    }, [lineId, warehouseId, editor.revision]);
    async function reserve() {
        if (busy || !row?.line) return;
        if (
            !frozen.current &&
            (!decimal(quantity) || !/[1-9]/.test(quantity))
        ) {
            setMessage("Quantità positiva con massimo 6 interi e 6 decimali.");
            quantityInput.current?.focus();
            return;
        }
        const command = frozen.current ?? {
            url: url + "/reservations",
            body: {
                id: crypto.randomUUID(),
                warehouseId,
                quantity,
                catalogVersion: row.line.catalogVersion,
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
            setStock(undefined);
            setMessage(
                "Registrato; stato aggiornato non verificato. Rileggi materiali.",
            );
            try {
                await read(gen);
                if (gen === generation.current)
                    setMessage(
                        "Prenotazione registrata; stato riletto dal server.",
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
                    e.code === "insufficient_available"
                        ? "Disponibilità insufficiente: nessuna prenotazione eseguita."
                        : e.message,
                );
                onError(e);
            } else {
                setUncertain(true);
                setMessage(
                    "Esito incerto: riprova il comando identico, senza modificare quantità o destinazione.",
                );
            }
        } finally {
            if (gen === generation.current) setBusy(false);
        }
    }
    return (
        <section aria-label="Operazioni materiali">
            <h2>Materiali · prenotazione esplicita</h2>
            <p>
                Stock societario; nessuna chiamata ERP. Prelievo, consumo e
                carcassa non sono una prenotazione.
            </p>
            <label>
                Riga ricambio
                <select
                    value={lineId}
                    disabled={locked}
                    onChange={(e) => setLineId(e.target.value)}
                >
                    <option value="">Seleziona riga</option>
                    {rows.map((r) => (
                        <option key={r.id} value={r.id}>
                            {
                                editor.groups.find(
                                    (g) => g.id === r.workingGroupId,
                                )?.title
                            }{" "}
                            · {r.line!.catalogLabel} · {r.id}
                        </option>
                    ))}
                </select>
            </label>
            <label>
                Magazzino materiali
                <select
                    value={warehouseId}
                    disabled={locked}
                    onChange={(e) => setWarehouseId(e.target.value)}
                >
                    <option value="">Seleziona magazzino</option>
                    {warehouses.map((w) => (
                        <option key={w.id} value={w.id}>
                            {w.name}
                        </option>
                    ))}
                </select>
            </label>
            <button disabled={locked} onClick={() => void loadWarehouses()}>
                Riprova magazzini
            </button>
            <p role="status">{message}</p>
            {stock && (
                <>
                    <p>Profilo stock: {stock.stockProfile}</p>
                    {stock.stockProfile !== "local" && (
                        <p>
                            Scritture locali non disponibili: serve il profilo
                            stock societario esplicito del proprietario. Nessun
                            fallback locale o chiamata ERP.
                        </p>
                    )}
                </>
            )}
            {stock && (
                <dl>
                    <dt>Fisico magazzino: {stock.physical}</dt>
                    <dt>Disponibile magazzino: {stock.available}</dt>
                    <dt>Impegno attivo magazzino: {stock.activeCommitted}</dt>
                    <dt>Consumato magazzino: {stock.consumed}</dt>
                    <dt>
                        Prenotato riga (tutti i magazzini): {stock.reserved}
                    </dt>
                    <dt>Residuo riga (tutti i magazzini): {stock.remaining}</dt>
                </dl>
            )}
            <form
                onSubmit={(e) => {
                    e.preventDefault();
                    void reserve();
                }}
            >
                <label>
                    Quantità da prenotare
                    <input
                        ref={quantityInput}
                        onKeyDown={(e) => {
                            if (e.key === "Escape" && !locked) {
                                setQuantity("");
                                setMessage(
                                    "Bozza quantità non inviata rimossa.",
                                );
                            }
                        }}
                        value={quantity}
                        disabled={locked}
                        onChange={(e) => setQuantity(e.target.value)}
                    />
                </label>
                <button
                    disabled={
                        locked ||
                        !stock?.canReserve ||
                        editor.capabilities.closed
                    }
                >
                    Prenota quantità esplicita
                </button>
            </form>
            {uncertain && (
                <button disabled={busy} onClick={() => void reserve()}>
                    Riprova prenotazione identica
                </button>
            )}
            <button
                disabled={
                    !row ||
                    !warehouseId ||
                    busy ||
                    pickingBlocked ||
                    carcassBlocked
                }
                onClick={() =>
                    void read().catch((e) => {
                        setMessage("Lettura materiali non disponibile.");
                        onError(e);
                    })
                }
            >
                Rileggi materiali
            </button>
            {row && warehouseId && (
                <MaterialPicking
                    key={url + warehouseId}
                    url={url}
                    reservations={
                        choices?.key === url + warehouseId ? choices.items : []
                    }
                    closed={editor.capabilities.closed}
                    blocked={busy || uncertain || carcassBlocked}
                    onBlocked={setPickingBlocked}
                    onApplied={async () => {
                        setStock(undefined);
                        await read();
                    }}
                    onError={onError}
                />
            )}
            {row && warehouseId && (
                <MaterialCarcass
                    key={"carcass:" + url + warehouseId}
                    url={url}
                    warehouseId={warehouseId}
                    closed={editor.capabilities.closed}
                    blocked={busy || uncertain || pickingBlocked}
                    onBlocked={setCarcassBlocked}
                    onApplied={async () => {
                        setStock(undefined);
                        await read();
                    }}
                    onError={onError}
                />
            )}
        </section>
    );
}
