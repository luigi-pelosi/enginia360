import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
const base = import.meta.env.VITE_B05_HTTP_BASE as string | undefined;
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.resetModules(); });
test.skipIf(!base)("B05 real DOM/HTTP edits variable values and rereads six-decimal persisted totals after recovery", async () => {
  const realFetch=globalThis.fetch;
  const writes: Record<string, unknown>[]=[];
  let failInitialCatalog=true;
  vi.stubGlobal("fetch", (url:string, init?:RequestInit) => {
    if (url.includes('/catalog?') && failInitialCatalog) {
      failInitialCatalog=false;
      return Promise.resolve(new Response('{}',{status:503}));
    }
    if (url.endsWith("/lines") && init?.method==="POST") writes.push(JSON.parse(init.body as string));
    return realFetch(new URL(url,base).href,init);
  });
  vi.stubEnv("VITE_B05_TEST_UI","true");
  const {default:App}=await import("./App");
  render(<App/>);
  fireEvent.change(screen.getByLabelText("Utente sintetico"),{target:{value:"operatore-alfa-sintetico"}});
  fireEvent.change(screen.getByLabelText("Password sintetica"),{target:{value:"synthetic-alpha-password"}});
  fireEvent.click(screen.getByRole("button",{name:"Accedi"}));
  fireEvent.click(await screen.findByRole("button",{name:"Alfa Società Uno · Alfa Sede Nord"},{timeout:15000}));
  await screen.findByRole("option",{name:"Veicolo sintetico altra società"});
  for (const [label,value] of [["Soggetto a carico","11111111-3333-0000-0000-000000000001"],["Tipo commessa","11111111-5555-0000-0000-000000000001"],["Veicolo","11111111-4444-0000-0000-000000000001"]])
    fireEvent.change(screen.getByLabelText(label),{target:{value}});
  fireEvent.click(screen.getByRole("button",{name:"Apri commessa"}));
  await screen.findByRole("heading",{name:"Valori commerciali · caso 001"});
  const addService=await screen.findByRole("button",{name:"Aggiungi prestazione"});
  await screen.findByRole("alert");
  expect((addService as HTMLButtonElement).disabled).toBe(true);
  expect(writes).toHaveLength(0);
  fireEvent.click(screen.getByRole("button",{name:"Rileggi valori salvati"}));
  await waitFor(()=>expect((addService as HTMLButtonElement).disabled).toBe(false));
  for (const kind of ['prestazione', 'ricambio']) {
    for (const [label, value] of [['Quantità', '1.000000'], ['Prezzo unitario', '0.000001'], ['Sconto %', '50.00']])
      fireEvent.change(screen.getByLabelText(`${label} ${kind}`), {target: {value}});
  }
  fireEvent.click(addService);
  await screen.findByText("Imponibile: 0.000001 EUR");
  fireEvent.click(screen.getByRole("button",{name:"Aggiungi ricambio"}));
  await screen.findByText("Totale: 0.000002 EUR");
  expect(screen.getByText("Imposta aggregata: 0.000000 EUR")).toBeTruthy();
  expect(screen.getByText("Imponibile: 0.000002 EUR")).toBeTruthy();
  expect(screen.getByText(/Manodopera meccanica · 1 × 0.000001/)).toBeTruthy();
  expect(screen.getByText(/Filtro olio · 1 × 0.000001/)).toBeTruthy();
  expect(writes).toHaveLength(2);
  expect(writes[0].quantity).toBe("1.000000");
  expect(writes[1].unitPrice).toBe("0.000001");
  expect(writes.every(x=>!('total' in x) && !('payerId' in x) && !('tenantId' in x))).toBe(true);
  fireEvent.click(screen.getByRole("button",{name:"Rileggi valori salvati"}));
  await waitFor(()=>expect(screen.getByText("Totale: 0.000002 EUR")).toBeTruthy());
},30000);
