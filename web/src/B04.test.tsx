import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import B04TestApp from "./B04TestApp";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const A = "11111111-1111-1111-1111-111111111101";
const SITE = "11111111-1111-1111-1111-111111110101";
const PAYER = "11111111-3333-0000-0000-000000000001";
const OWNER = "11111111-3333-0000-0000-000000000002";
const VEHICLE = "11111111-4444-0000-0000-000000000001";
const TYPE = "11111111-5555-0000-0000-000000000001";
const context = {
  legalEntityId: A,
  legalEntityName: "Società sintetica",
  siteId: SITE,
  siteName: "Sede sintetica",
};
const reply = (value: unknown) => ({ ok: true, json: async () => value });
async function login() {
  render(<B04TestApp />);
  fireEvent.change(screen.getByLabelText("Utente sintetico"), {
    target: { value: "synthetic-user" },
  });
  fireEvent.change(screen.getByLabelText("Password sintetica"), {
    target: { value: "synthetic-secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Accedi" }));
}
test("B04 explains empty authorized context without exposing a creation form", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(reply({ accessToken: "synthetic-token" }))
      .mockResolvedValueOnce(reply([])),
  );
  await login();
  expect(
    await screen.findByText(
      "Nessun contesto officina autorizzato. Contatta il referente degli accessi.",
    ),
  ).toBeTruthy();
  expect(screen.queryByLabelText("Veicolo")).toBeNull();
});
test("B04 rejects malformed selector response and provides a retry action", async () => {
  const responses = [
    reply({ accessToken: "synthetic-token" }),
    reply([context]),
    reply([{ id: "invalid", label: "Untrusted" }]),
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async () => responses.shift()),
  );
  await login();
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Società sintetica · Sede sintetica",
    }),
  );
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Selezione non disponibile",
  );
  expect(screen.queryByText("Untrusted")).toBeNull();
});
test("B04 retries failed reread with the same command id and numeric configuration version", async () => {
  let saved: Record<string, unknown>;
  let gets = 0;
  const posts: Record<string, unknown>[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/login"))
        return reply({ accessToken: "synthetic-token" });
      if (url.endsWith("/contexts")) return reply([context]);
      if (url.includes("/vehicles?"))
        return reply([{ id: VEHICLE, label: "Veicolo sintetico" }]);
      if (url.includes("/counterparties?"))
        return reply([{ id: PAYER, legalName: "Pagante sintetico" }]);
      if (url.includes("/document-types?"))
        return reply([
          {
            id: TYPE,
            name: "Tipo sintetico",
            version: 1,
            directCreationEnabled: true,
          },
        ]);
      if (init?.method === "POST") {
        const payload = JSON.parse(init.body as string) as Record<
          string,
          unknown
        >;
        posts.push(payload);
        saved = { ...payload, vehicleHolderId: OWNER, isCustomerOrder: true };
        return reply(saved);
      }
      return ++gets === 1 ? { ok: false } : reply(saved);
    }),
  );
  await login();
  fireEvent.click(
    await screen.findByRole("button", {
      name: "Società sintetica · Sede sintetica",
    }),
  );
  await screen.findByRole("option", { name: "Veicolo sintetico" });
  for (const [label, value] of [
    ["Tipo commessa", TYPE],
    ["Soggetto a carico", PAYER],
    ["Veicolo", VEHICLE],
  ])
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  fireEvent.click(screen.getByRole("button", { name: "Apri commessa" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Riprova senza cambiare i campi",
  );
  expect(screen.queryByRole("status")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Apri commessa" }));
  expect((await screen.findByRole("status")).textContent).toContain(OWNER);
  expect(posts).toHaveLength(2);
  expect(posts[0]).toEqual(posts[1]);
  expect(posts[0].configurationVersion).toBe(1);
  expect(posts[0].payerId).toBe(PAYER);
});
