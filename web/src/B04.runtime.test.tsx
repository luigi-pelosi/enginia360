import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
const base = import.meta.env.VITE_B04_HTTP_BASE as string | undefined;
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});
// Real fetch, private nginx -> API -> Keycloak/PostgreSQL; not an authenticated browser claim.
test.skipIf(!base)(
  "B04 DOM creates and rereads a direct order without changing payer on vehicle selection",
  async () => {
    const realFetch = globalThis.fetch;
    const calls: { url: string; body: unknown }[] = [];
    vi.stubGlobal("fetch", (url: string, init?: RequestInit) => {
      if (init?.method === "POST" && url.endsWith("/orders"))
        calls.push({ url, body: JSON.parse(init.body as string) });
      return realFetch(new URL(url, base).href, init);
    });
    vi.stubEnv("VITE_B04_TEST_UI", "true");
    const { default: App } = await import("./App");
    render(<App />);
    fireEvent.change(screen.getByLabelText("Utente sintetico"), {
      target: { value: "operatore-alfa-sintetico" },
    });
    fireEvent.change(screen.getByLabelText("Password sintetica"), {
      target: { value: "synthetic-alpha-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Accedi" }));
    fireEvent.click(
      await screen.findByRole(
        "button",
        { name: "Alfa Società Uno · Alfa Sede Nord" },
        { timeout: 15000 },
      ),
    );
    await screen.findByRole("option", {
      name: "Veicolo sintetico altra società",
    });
    const payer = (await screen.findByLabelText(
      "Soggetto a carico",
    )) as HTMLSelectElement;
    fireEvent.change(payer, {
      target: { value: "11111111-3333-0000-0000-000000000001" },
    });
    fireEvent.change(screen.getByLabelText("Tipo commessa"), {
      target: { value: "11111111-5555-0000-0000-000000000001" },
    });
    fireEvent.change(screen.getByLabelText("Veicolo"), {
      target: { value: "11111111-4444-0000-0000-000000000001" },
    });
    expect(payer.value).toBe("11111111-3333-0000-0000-000000000001");
    fireEvent.click(screen.getByRole("button", { name: "Apri commessa" }));
    const result = await screen.findByRole("status");
    expect(result.textContent).toContain("Commessa · ordine cliente");
    expect(result.textContent).toContain(
      "11111111-3333-0000-0000-000000000001",
    );
    expect(result.textContent).toContain(
      "11111111-3333-0000-0000-000000000002",
    );
    expect(calls).toHaveLength(1);
    expect(
      (calls[0].body as { configurationVersion: unknown }).configurationVersion,
    ).toBe(1);
  },
  30000,
);
