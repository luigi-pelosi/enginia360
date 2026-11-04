import { test, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";
const domains = [
    "identity",
    "organization",
    "counterparties",
    "catalog",
    "inventory",
    "document-types",
    "documents",
];

test("HTTP returns real uncached Italian SSR with all seven domain pages and no inferred context", async ({
    request,
    browser,
}) => {
    for (const suffix of ["", ...domains.map((id) => `/domains/${id}`)]) {
        const response = await request.get(suffix || "/", {
            headers: {
                cookie: "tenantId=untrusted; role=SUPER_ADMIN",
                "x-tenant-id": "untrusted",
            },
        });
        expect(response.status()).toBe(200);
        expect(response.headers()["cache-control"]).toMatch(
            /private.*no-store/,
        );
        expect(response.headers()["set-cookie"]).toBeUndefined();
        expect(response.headers()["x-content-type-options"]).toBe("nosniff");
        expect(response.headers()["x-frame-options"]).toBe("DENY");
        const html = await response.text();
        if (!suffix) {
            await writeFile("/evidence/ssr-home.html", html);
            await writeFile(
                "/evidence/ssr-response-headers.json",
                JSON.stringify(response.headers(), null, 2),
            );
        }
        expect(html).toContain('<html lang="it"');
        expect(html).toContain("Navigazione principale");
        expect(html).toContain("Nessun contesto aziendale attivo");
        expect(html).not.toContain("untrusted");
        expect(html).not.toContain("SUPER_ADMIN");
        expect(html).not.toMatch(/<form|type="password"/);
        if (suffix === "/domains/counterparties") {
            expect(html).toContain("Controparti e ruoli aziendali");
            expect(html).not.toContain("Salva dati comuni");
        } else if (suffix === "/domains/catalog") {
            expect(html).toContain("Articoli e servizi");
            expect(html).not.toContain("Salva identità catalogo");
        } else if (suffix) expect(html).toContain("Area non ancora implementata");
    }
    expect((await request.get("/domains/not-a-domain")).status()).toBe(404);
    // JavaScript disabled: content and ordinary navigation really are server rendered.
    const context = await browser.newContext({
        javaScriptEnabled: false,
        viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage();
    await page.goto(process.env.MVP01_BASE_URL!);
    await expect(
        page.getByRole("heading", { name: "Uno spazio per il tuo lavoro." }),
    ).toBeVisible();
    await page
        .getByRole("navigation")
        .getByRole("link", { name: "Documenti", exact: true })
        .click();
    await expect(
        page.getByRole("heading", { name: "Area non ancora implementata" }),
    ).toBeVisible();
    await context.close();
});

for (const viewport of [
    { width: 1440, height: 900 },
    { width: 1366, height: 768 },
    { width: 390, height: 844 },
]) {
    test(`keyboard navigation, visible layout and honest unavailable area ${viewport.width}x${viewport.height}`, async ({
        page,
    }) => {
        const errors: string[] = [];
        page.on("pageerror", (error) => errors.push(error.message));
        await page.setViewportSize(viewport);
        await page.goto("/");
        await expect(
            page.getByRole("heading", {
                name: "Uno spazio per il tuo lavoro.",
            }),
        ).toBeVisible();
        await page.keyboard.press("Tab");
        await expect(
            page.getByRole("link", { name: "Vai al contenuto" }),
        ).toBeFocused();
        await page.keyboard.press("Enter");
        await expect(page.locator("main")).toBeFocused();
        const menu = page.getByRole("button", { name: "Menu domini" });
        if (viewport.width < 1024) {
            await menu.focus();
            await page.keyboard.press("Enter");
            await expect(menu).toHaveAttribute("aria-expanded", "true");
            await page.screenshot({
                path: `/evidence/menu-open-${viewport.width}.png`,
                fullPage: true,
            });
            await page.keyboard.press("Tab");
            await expect(
                page
                    .getByRole("navigation")
                    .getByRole("link", { name: "Panoramica" }),
            ).toBeFocused();
            await page.keyboard.press("Escape");
            await expect(menu).toBeFocused();
            await expect(menu).toHaveAttribute("aria-expanded", "false");
            await page.keyboard.press("Enter");
        } else {
            await expect(menu).toBeHidden();
        }
        const documents = page
            .getByRole("navigation")
            .getByRole("link", { name: "Documenti", exact: true });
        await documents.focus();
        await page.keyboard.press("Enter");
        await expect(page).toHaveURL(/\/domains\/documents$/);
        await expect(
            page.getByRole("heading", { name: "Documenti", exact: true }),
        ).toBeVisible();
        await expect(
            page.getByRole("heading", { name: "Area non ancora implementata" }),
        ).toBeVisible();
        if (viewport.width >= 1024)
            await expect(documents).toHaveAttribute("aria-current", "page");
        else await expect(menu).toHaveAttribute("aria-expanded", "false");
        expect(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= innerWidth,
            ),
        ).toBe(true);
        await page.getByRole("link", { name: "Torna alla panoramica" }).focus();
        await page.keyboard.press("Enter");
        await expect(page).toHaveURL(/\/$/);
        await page.screenshot({
            path: `/evidence/shell-${viewport.width}x${viewport.height}.png`,
            fullPage: true,
        });
        expect(errors).toEqual([]);
    });
}
