import { afterEach, expect, test, vi } from "vitest";
import {
    act,
    cleanup,
    fireEvent,
    render,
    screen,
} from "@testing-library/react";
import MaterialOperations from "./MaterialOperations";
import { editorView, id } from "./editorFixtures";
import { parseEditor, type Editor } from "./editorContracts";
const lineId = "33333333-3333-4333-8333-333333333333",
    groupId = "44444444-4444-4444-8444-444444444444",
    warehouseId = "55555555-5555-4555-8555-555555555555";
const editor: Editor = {
    ...parseEditor(editorView, id),
    groups: [{ id: groupId, title: "Lavorazione", version: 1, sequence: 1 }],
    rows: [
        {
            id: lineId,
            kind: "Part",
            workingGroupId: groupId,
            sequence: 2,
            version: 1,
            description: null,
            line: {
                id: lineId,
                orderId: id,
                catalogItemId: id,
                catalogVersion: 8,
                catalogLabel: "Ricambio",
                kind: "Part",
                quantity: "3",
                unitPrice: "1",
                discountPercent: "0",
                netAmount: "3.000000",
                taxRate: "22",
                payerId: id,
                workingGroupId: groupId,
                configurationVersion: 9,
            },
        },
    ],
};
const state = (remaining = "3", physical = "2") => ({
    orderId: id,
    lineId,
    warehouseId,
    physical,
    available: physical,
    reserved: remaining === "3" ? "0" : "2",
    remaining,
    activeCommitted: "0",
    consumed: "0",
    canReserve: true,
    stockProfile: "local",
    reservations: [],
});
const response = (value: unknown) => new Response(JSON.stringify(value));
function api(read: () => Promise<Response>) {
    const fetch = vi.fn(async (path: string, options?: RequestInit) =>
        path.includes("/purchase-intents")
            ? new Response("{}", { status: 404 }) // independent sibling panel (R04.b.2a) does not share the material read sequence
            : path.includes("/warehouses?")
            ? response([{ id: warehouseId, name: "Magazzino" }])
            : path === "/auth/csrf"
              ? response({ requestToken: "unit-only" })
              : options?.method === "POST"
                ? response({ id: JSON.parse(options.body as string).id })
                : read(),
    );
    vi.stubGlobal("fetch", fetch);
    return fetch;
}
async function choose() {
    fireEvent.change(screen.getByLabelText("Riga ricambio"), {
        target: { value: lineId },
    });
    await screen.findByRole("option", { name: "Magazzino" });
    fireEvent.change(screen.getByLabelText("Magazzino materiali"), {
        target: { value: warehouseId },
    });
}
afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
});
test("receiving is a separate lazy panel, not an implicit purchase permission", async () => {
    const fetch = api(async () => response(state()));
    render(<MaterialOperations editor={editor} onError={() => undefined} />);
    await choose();
    expect(screen.getByRole('button', { name: 'Apri ricevimento merce' })).toBeTruthy();
    expect(fetch.mock.calls.some(call => String(call[0]).includes('receipt-sources'))).toBe(false);
});

test("dedicated receiving shows confirmed source and frozen q6 cost independently of purchasing", async () => {
    vi.stubGlobal('fetch', vi.fn(async (path: string) => {
        if (path.includes('/receipt-sources?')) return response({ state: 'ready', sources: [{ id: groupId, orderedQuantity: '3.000000', unitPurchasePrice: '12.345678', supplierName: 'Fornitore', description: 'Ricambio', externalOrderReference: 'GiobbyPurchaseOrder-301' }] });
        if (path.includes('/receipts')) return response({ state: 'ready', sourceIntentId: groupId, orderedQuantity: '3.000000', acceptedQuantity: '0.000000', uncertainQuantity: '2.000000', remainingQuantity: '1.000000', nonAuthoritative: true, erpPerOrderResidual: null, precisionDiscrepancy: 'receipt_q6_stock_report_q5_observed', linkKind: 'internal_standalone_not_erp_native', receipts: [] });
        if (path.includes('/warehouses?')) return response([{ id: warehouseId, name: 'Magazzino' }]);
        if (path.includes('/purchase-intents')) return new Response('{}', { status: 403 });
        return response(state());
    }));
    render(<MaterialOperations editor={editor} onError={() => undefined} />); await choose();
    fireEvent.click(screen.getByRole('button', { name: 'Apri ricevimento merce' }));
    await screen.findByRole('option', { name: /GiobbyPurchaseOrder-301/ });
    fireEvent.change(screen.getByLabelText('Ordine acquisto confermato'), { target: { value: groupId } });
    await screen.findByText('Capacità ricevimento disponibile: 1.000000');
    expect(screen.getByText('Costo acquisto congelato: 12.345678')).toBeTruthy();
    expect(screen.getByText(/Residuo ERP per ordine: SCONOSCIUTO/)).toBeTruthy();
    expect(screen.getByText(/limite osservato sandbox/)).toBeTruthy();
});

test("uncertain receipt freezes ancestor material context and survives a source row tombstone until exact retry", async () => {
    const posts: string[] = []; const blocked = vi.fn();
    vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
        if (path === '/auth/csrf') return response({requestToken:'x'});
        if (options?.method === 'POST') { posts.push(String(options.body)); throw new TypeError('accepted response lost'); }
        if (path.includes('/receipt-sources?')) return response({ state: 'ready', sources: [{ id: groupId, orderedQuantity: '3.000000', unitPurchasePrice: '12.345678', supplierName: 'Fornitore', description: 'Ricambio', externalOrderReference: 'GiobbyPurchaseOrder-301' }] });
        if (path.includes('/receipts')) return response({ state: 'ready', sourceIntentId: groupId, orderedQuantity: '3.000000', acceptedQuantity: '0.000000', uncertainQuantity: '0.000000', remainingQuantity: '3.000000', nonAuthoritative: true, erpPerOrderResidual: null, precisionDiscrepancy: 'receipt_q6_stock_report_q5_observed', linkKind: 'internal_standalone_not_erp_native', receipts: [] });
        if (path.includes('/warehouses?')) return response([{ id: warehouseId, name: 'Magazzino' }]);
        if (path.includes('/purchase-intents')) return new Response('{}', { status: 403 });
        return response(state());
    }));
    const view=render(<MaterialOperations editor={editor} onError={() => undefined} onContextBlocked={blocked} />); await choose();
    fireEvent.click(screen.getByRole('button',{name:'Apri ricevimento merce'}));await screen.findByRole('option',{name:/GiobbyPurchaseOrder-301/});
    fireEvent.change(screen.getByLabelText('Ordine acquisto confermato'),{target:{value:groupId}});await screen.findByText('Capacità ricevimento disponibile: 3.000000');
    fireEvent.change(screen.getByLabelText('Quantità da ricevere'),{target:{value:'2'}});fireEvent.click(screen.getByRole('button',{name:'Crea ricevimento esplicito'}));await screen.findByText(/Risposta client incerta/);
    for(const label of ['Riga ricambio','Magazzino materiali','Quantità da prenotare'])expect((screen.getByLabelText(label) as HTMLInputElement).disabled,label).toBe(true);
    expect(blocked).toHaveBeenLastCalledWith(true);
    expect((screen.getByRole('button',{name:'Chiudi ricevimento merce'}) as HTMLButtonElement).disabled).toBe(true);
    view.rerender(<MaterialOperations editor={{...editor,rows:[]}} onError={() => undefined} onContextBlocked={blocked} />);
    fireEvent.click(screen.getByRole('button',{name:'Riprova comando identico'}));await act(async()=>undefined);expect(posts).toHaveLength(2);expect(posts[1]).toBe(posts[0]);
});

test("reservation-specific explicit release is available independently from picking", async () => {
    api(async () => response(state()));
    render(<MaterialOperations editor={editor} onError={() => undefined} />);
    await choose();
    await screen.findByRole("region", { name: "Rilascio prenotazione" });
    expect(screen.getByLabelText("Prenotazione da rilasciare")).toBeTruthy();
    expect(screen.getByLabelText("Quantità da rilasciare")).toBeTruthy();
});

test("warehouse prerequisite failure retries that lookup, including repeated failure", async () => {
    let attempts = 0;
    vi.stubGlobal(
        "fetch",
        vi.fn(async (path: string) => {
            if (path.includes("/warehouses?"))
                return ++attempts < 3
                    ? new Response(null, { status: 503 })
                    : response([{ id: warehouseId, name: "Magazzino" }]);
            return response(state());
        }),
    );
    render(<MaterialOperations editor={editor} onError={() => undefined} />);
    await screen.findByText("Magazzini non disponibili.");
    expect(
        (
            screen.getByRole("button", {
                name: "Prenota quantità esplicita",
            }) as HTMLButtonElement
        ).disabled,
    ).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Riprova magazzini" }));
    await act(async () => undefined);
    expect(attempts).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: "Riprova magazzini" }));
    await screen.findByRole("option", { name: "Magazzino" });
    expect(attempts).toBe(3);
    expect(screen.queryByText("Magazzini non disponibili.")).toBeNull();
});
test.each(["missing", "external"])(
    "company stock profile %s is visible and blocks only the dependent write",
    async (profile) => {
        api(async () =>
            response({ ...state(), stockProfile: profile, canReserve: false }),
        );
        render(
            <MaterialOperations editor={editor} onError={() => undefined} />,
        );
        await choose();
        await screen.findByText("Residuo riga (tutti i magazzini): 3");
        expect(screen.getByText("Profilo stock: " + profile)).toBeTruthy();
        expect(
            (
                screen.getByRole("button", {
                    name: "Prenota quantità esplicita",
                }) as HTMLButtonElement
            ).disabled,
        ).toBe(true);
        expect(
            (
                screen.getByRole("button", {
                    name: "Rileggi materiali",
                }) as HTMLButtonElement
            ).disabled,
        ).toBe(false);
    },
);
test("older same-context read cannot overwrite the authoritative post-command reread", async () => {
    let reads = 0,
        release!: (r: Response) => void;
    api(async () =>
        ++reads === 2
            ? new Promise<Response>((r) => {
                  release = r;
              })
            : response(state(reads >= 3 ? "1" : "3")),
    );
    render(<MaterialOperations editor={editor} onError={() => undefined} />);
    await choose();
    await screen.findByText("Residuo riga (tutti i magazzini): 3");
    fireEvent.click(screen.getByRole("button", { name: "Rileggi materiali" }));
    fireEvent.change(screen.getByLabelText("Quantità da prenotare"), {
        target: { value: "2" },
    });
    fireEvent.click(
        screen.getByRole("button", { name: "Prenota quantità esplicita" }),
    );
    await screen.findByText("Residuo riga (tutti i magazzini): 1");
    await act(async () => {
        release(response(state("3")));
    });
    expect(
        screen.getByText("Residuo riga (tutti i magazzini): 1"),
    ).toBeTruthy();
});
test("aggregate q6 is not capped like an input and command micro quantity remains an exact string", async () => {
    const fetch = api(async () => response(state("3", "1234567.123456")));
    render(<MaterialOperations editor={editor} onError={() => undefined} />);
    await choose();
    await screen.findByText("Fisico magazzino: 1234567.123456");
    fireEvent.change(screen.getByLabelText("Quantità da prenotare"), {
        target: { value: "0.000001" },
    });
    fireEvent.click(
        screen.getByRole("button", { name: "Prenota quantità esplicita" }),
    );
    await screen.findByText(
        "Prenotazione registrata; stato riletto dal server.",
    );
    const call = fetch.mock.calls.find(([, o]) => o?.method === "POST")!;
    expect(JSON.parse(call[1]!.body as string).quantity).toBe("0.000001");
});
test("invalid explicit quantity focuses its input; Escape discards only the unsent draft", async () => {
    const fetch = api(async () => response(state()));
    render(<MaterialOperations editor={editor} onError={() => undefined} />);
    await choose();
    await screen.findByText("Residuo riga (tutti i magazzini): 3");
    fireEvent.change(screen.getByLabelText("Quantità da prenotare"), {
        target: { value: "1000000" },
    });
    fireEvent.click(
        screen.getByRole("button", { name: "Prenota quantità esplicita" }),
    );
    const focused =
        document.activeElement ===
        screen.getByLabelText("Quantità da prenotare");
    const unsent = fetch.mock.calls.filter(
        ([, o]) => o?.method === "POST",
    ).length;
    fireEvent.keyDown(screen.getByLabelText("Quantità da prenotare"), {
        key: "Escape",
    });
    expect({
        focused,
        unsent,
        draft: (
            screen.getByLabelText("Quantità da prenotare") as HTMLInputElement
        ).value,
    }).toEqual({ focused: true, unsent: 0, draft: "" });
});

test("uncertain new-part return stays mounted after an external row tombstone and never retargets its retry", async () => {
    const reservationId="66666666-6666-4666-8666-666666666666",pickId="77777777-7777-4777-8777-777777777777";
    const envelopes:{path:string;body:string}[]=[], blocked=vi.fn();
    vi.stubGlobal("fetch",vi.fn(async(path:string,options?:RequestInit)=>{
        if(path.includes("/warehouses?"))return response([{id:warehouseId,name:"Magazzino"}]);
        if(path==="/auth/csrf")return response({requestToken:"unit-only"});
        if(options?.method==="POST"){
            envelopes.push({path,body:options.body as string});
            if(envelopes.length===1)throw new TypeError("synthetic accepted response lost");
            return response({id:JSON.parse(options.body as string).id});
        }
        if(path.endsWith("/new-part-returns"))return response({pickId,remainingWithTechnician:"1",returned:"0",returns:[],canReturn:true,reason:"ready"});
        if(path.endsWith("/picks"))return response({reservationId,remainingToPick:"0",canPick:true,picks:[{id:pickId,quantity:"1",workingGroupId:groupId,placementLocation:null}]});
        return response({...state(),reservations:[{id:reservationId,quantity:"1"}]});
    }));
    const view=render(<MaterialOperations editor={editor} onError={()=>undefined} onContextBlocked={blocked}/>);
    await choose();await screen.findByText("Residuo riga (tutti i magazzini): 3");
    fireEvent.change(screen.getByLabelText("Prenotazione da prelevare"),{target:{value:reservationId}});
    await screen.findByLabelText("Prelievo da restituire");
    fireEvent.change(screen.getByLabelText("Prelievo da restituire"),{target:{value:pickId}});
    await screen.findByText("Residuo presso operatore: 1");
    fireEvent.change(screen.getByLabelText("Quantità da restituire"),{target:{value:"1"}});
    fireEvent.click(screen.getByRole("button",{name:"Restituisci quantità esplicita"}));
    await screen.findByText("Esito reso incerto: riprova solo il comando identico.");
    expect(blocked).toHaveBeenLastCalledWith(true);
    view.rerender(<MaterialOperations editor={{...editor,revision:editor.revision+1,rows:[]}} onError={()=>undefined} onContextBlocked={blocked}/>);
    const retry=await screen.findByRole("button",{name:"Riprova reso identico"});
    await act(async()=>{fireEvent.click(retry);});
    expect(envelopes).toHaveLength(2);expect(envelopes[1]).toEqual(envelopes[0]);
});
