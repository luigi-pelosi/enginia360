import { afterEach, expect, test, vi } from "vitest";
import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/react";

afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.resetModules();
});

const context = {
    tenantId: "11111111-1111-1111-1111-111111111111",
    tenantName: "Tenant Alfa sintetico",
    legalEntityId: "11111111-1111-1111-1111-111111111101",
    legalEntityName: "Alfa Società Uno",
    siteId: "11111111-1111-1111-1111-111111110101",
    siteName: "Alfa Sede Nord",
    warehouseId: "11111111-1111-1111-1111-111111100101",
    warehouseName: "Alfa Nord Magazzino A",
    capabilityEnabled: true,
};

async function renderApp(b02TestUi = false) {
    vi.stubEnv("VITE_B02_TEST_UI", b02TestUi ? "true" : "");
    const { default: App } = await import("./App");
    render(<App />);
}

async function login(fetchMock: ReturnType<typeof vi.fn>) {
    vi.stubGlobal("fetch", fetchMock);
    await renderApp(true);
    fireEvent.change(screen.getByLabelText("Utente sintetico"), {
        target: { value: "operatore-alfa-sintetico" },
    });
    fireEvent.change(screen.getByLabelText("Password sintetica"), {
        target: { value: "password-effimera" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Accedi" }));
}

test("default production UI renders safe bootstrap status and no synthetic login controls", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
            product: "Enginia360",
            stage: "bootstrap",
            foundationDossierApproved: false,
            businessCapabilitiesAvailable: false,
        }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await renderApp();

    expect(screen.getByText("BOOTSTRAP TECNICO")).toBeTruthy();
    expect(screen.queryByLabelText("Utente sintetico")).toBeNull();
    expect(screen.queryByLabelText("Password sintetica")).toBeNull();
    expect(screen.queryByRole("button", { name: "Accedi" })).toBeNull();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/system/status");
});

test("B02 test UI login is backend mediated and lists only returned authorized contexts", async () => {
    const fetchMock = vi
        .fn()
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({ accessToken: "safe-test-token" }),
        })
        .mockResolvedValueOnce({ ok: true, json: async () => [context] });
    await login(fetchMock);

    expect(await screen.findByText("Alfa Società Uno")).toBeTruthy();
    expect(fetchMock).toHaveBeenNthCalledWith(
        1,
        "/api/v1/development/login",
        expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        "/api/v1/organization/contexts",
        expect.objectContaining({
            headers: { Authorization: "Bearer safe-test-token" },
        }),
    );
    expect(screen.queryByText("Beta Società Uno")).toBeNull();
});

test("B02 test UI selects an enabled context then creates and durably retrieves its note", async () => {
    const note = {
        id: "99999999-9999-9999-9999-999999999999",
        ...context,
        message: "Nota sintetica",
    };
    const fetchMock = vi
        .fn()
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({ accessToken: "safe-test-token" }),
        })
        .mockResolvedValueOnce({ ok: true, json: async () => [context] })
        .mockResolvedValueOnce({ ok: true, json: async () => note })
        .mockResolvedValueOnce({ ok: true, json: async () => note });
    await login(fetchMock);

    await screen.findByText("Alfa Società Uno");
    fireEvent.click(screen.getByLabelText(/Alfa Società Uno/));
    fireEvent.change(screen.getByLabelText("Nota"), {
        target: { value: "Nota sintetica" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salva nota" }));

    expect(await screen.findByText("Nota sintetica")).toBeTruthy();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(fetchMock.mock.calls[3][0]).toBe(
        "/api/v1/organization/context-notes/99999999-9999-9999-9999-999999999999",
    );
});

test("B02 test UI keeps disabled contexts visible but not selectable", async () => {
    const disabled = {
        ...context,
        legalEntityId: "11111111-1111-1111-1111-111111111102",
        legalEntityName: "Alfa Società Due",
        capabilityEnabled: false,
    };
    const fetchMock = vi
        .fn()
        .mockResolvedValueOnce({
            ok: true,
            json: async () => ({ accessToken: "safe-test-token" }),
        })
        .mockResolvedValueOnce({ ok: true, json: async () => [disabled] });
    await login(fetchMock);

    const option = await screen.findByLabelText(/Alfa Società Due/);
    expect(option).toHaveProperty("disabled", true);
    expect(screen.getByText("Capability disabilitata")).toBeTruthy();
});

test("B02 test UI does not expose Keycloak URLs in browser requests", async () => {
    const fetchMock = vi
        .fn()
        .mockResolvedValue({ ok: false, json: async () => ({}) });
    await login(fetchMock);

    await screen.findByRole("alert");
    expect(
        fetchMock.mock.calls.every((call) =>
            String(call[0]).startsWith("/api/"),
        ),
    ).toBe(true);
});
