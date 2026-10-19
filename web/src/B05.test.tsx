import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
const order = { id: "11111111-1111-1111-1111-111111111111", legalEntityId: "company", siteId: "site" };
vi.mock("./B04TestApp", () => ({ default: ({commercial}: {commercial: (context: {id: string; legalEntityId: string; siteId: string}, token: string) => ReactNode}) => commercial(order, "synthetic-token") }));
import B05TestApp from "./B05TestApp";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
test.each([true, false])("initial catalog failure followed by reread: catalog recovery %s", async (recovers) => {
  let catalogReads = 0;
  let posts = 0;
  const empty = { orderId: order.id, payerId: order.id, revision: 0, lines: [], netAmount: "0.00", taxAmount: "0.00", total: "0.00", currency: "EUR", policy: "Case001" };
  const item = { id: "22222222-2222-2222-2222-222222222222", kind: "Service", label: "Prestazione sintetica", version: 1 };
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes("/catalog?")) {
      catalogReads++;
      return new Response(JSON.stringify([item]), { status: catalogReads > 1 && recovers ? 200 : 503 });
    }
    if (init?.method === "POST") {
      posts++;
      expect(JSON.parse(init.body as string)).toMatchObject({quantity: '2.123456', unitPrice: '10.000001', discountPercent: '10.25'});
      return new Response("{}", {status: 201});
    }
    return new Response(JSON.stringify(posts ? {...empty, revision: 1, lines: [{...item, catalogItemId: item.id, catalogLabel: item.label, quantity: "1.5", unitPrice: "55", discountPercent: "10", netAmount: "74.25", workingGroupId: order.id, payerId: order.id}], netAmount: "74.25", taxAmount: "16.34", total: "90.59"} : empty));
  }));
  render(<B05TestApp/>);
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", {name: "Rileggi valori salvati"}));
  await waitFor(() => expect(catalogReads).toBe(2));
  const add = screen.getByRole("button", {name: "Aggiungi prestazione"}) as HTMLButtonElement;
  if (recovers) {
    await waitFor(() => expect(add.disabled).toBe(false));
    fireEvent.change(screen.getByLabelText("Quantità prestazione"), {target: {value: "2.123456"}});
    fireEvent.change(screen.getByLabelText("Prezzo unitario prestazione"), {target: {value: "10.000001"}});
    fireEvent.change(screen.getByLabelText("Sconto % prestazione"), {target: {value: "10.25"}});
    fireEvent.click(add);
    await screen.findByText("Imponibile: 74.25 EUR");
    expect(posts).toBe(1);
    expect(screen.queryByRole("alert")).toBeNull();
  } else {
    await waitFor(() => expect((screen.getByRole("button", {name: "Rileggi valori salvati"}) as HTMLButtonElement).disabled).toBe(false));
    expect(add.disabled).toBe(true);
    expect(screen.getByRole("alert").textContent).toMatch(/Rileggi/);
    fireEvent.click(add);
    expect(posts).toBe(0);
  }
});
