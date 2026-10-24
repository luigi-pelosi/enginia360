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
        path.includes("/warehouses?")
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
