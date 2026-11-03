const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");
const fixture = JSON.parse(fs.readFileSync("/run/fixture.json", "utf8"));
const origin = "https://app.r00.test:8443";
async function control(action) {
    try {
        fs.unlinkSync("/run/control/ack");
    } catch {}
    fs.writeFileSync("/run/control/request", action);
    for (let i = 0; i < 600; i++) {
        if (
            fs.existsSync("/run/control/ack") &&
            fs.readFileSync("/run/control/ack", "utf8") === action
        )
            return;
        await new Promise((r) => setTimeout(r, 100));
    }
    throw new Error("control timeout");
}
async function login(browser, index) {
    const context = await browser.newContext();
    const page = await context.newPage();
    await page.goto(origin + "/organization");
    await page
        .getByRole("button", { name: "Accedi con identità federata" })
        .click();
    await page.waitForURL((u) => u.hostname === "idp.r00.test", {
        timeout: 20000,
        waitUntil: "domcontentloaded",
    });
    await page.locator("#username").fill(fixture.users[index].username);
    await page.locator("#password").fill(fixture.users[index].password);
    await Promise.all([
        page.waitForURL((u) => u.hostname === "app.r00.test"),
        page.locator("#kc-login").click(),
    ]);
    await page
        .getByRole("navigation")
        .getByRole("link", { name: "Organizzazione", exact: true })
        .click();
    await page
        .getByRole("link", {
            name: "Apri amministrazione organizzativa",
            exact: true,
        })
        .click();
    return { context, page };
}
(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        const page = await browser.newPage();
        for (let i = 0; i < 60; i++) {
            try {
                const ready = await page
                    .context()
                    .request.get(origin + "/auth/session");
                if (ready.status() !== 200) throw new Error("API not ready");
                await page.goto(origin + "/organization");
                break;
            } catch (e) {
                if (i === 59) throw e;
                await new Promise((r) => setTimeout(r, 500));
            }
        }
        assert.equal(
            await page
                .getByRole("heading", {
                    name: "Amministrazione organizzativa",
                    exact: true,
                })
                .count(),
            1,
            "real SSR organization workspace absent",
        );
        assert.equal(
            await page
                .getByRole("button", { name: "Accedi con identità federata" })
                .count(),
            1,
            "actual federated login entry absent",
        );
        console.log("PASS MVP02C actual anonymous SSR organization route");
        const owner = await login(browser, 4);
        await owner.page
            .getByText("Autorità amministrativa assente o revocata", {
                exact: true,
            })
            .waitFor();
        await control("grant");
        await owner.page.reload();
        await owner.page
            .getByText("Autorità globale verificata", { exact: true })
            .waitFor();
        assert.match(
            await owner.page.locator("footer").innerText(),
            /Sessione gestita dal backend/,
            "connected organization workspace must not claim federation unavailable",
        );
        await owner.page.getByLabel("Tenant destinatario").waitFor();
        assert.ok(
            (await owner.page
                .getByLabel("Tenant destinatario")
                .locator("option")
                .count()) >= 5,
            "directory includes empty synthetic tenant",
        );
        console.log(
            "PASS MVP02C real login and live eligibility/directory SSR",
        );
        const acceptedBodies = [];
        let dropAccepted = true,
            dropRead = false,
            badCsrf = false;
        await owner.page.route("**/api/v1/platform/tenants", async (route) => {
            if (route.request().method() !== "POST") {
                if (dropRead) {
                    dropRead = false;
                    return route.abort("connectionfailed");
                }
                return route.continue();
            }
            acceptedBodies.push(route.request().postData());
            if (dropAccepted) {
                dropAccepted = false;
                const response = await route.fetch();
                assert.equal(response.status(), 200);
                return route.abort("connectionfailed");
            }
            if (badCsrf) {
                badCsrf = false;
                return route.continue({
                    headers: {
                        ...route.request().headers(),
                        "x-csrf-token": "invalid",
                    },
                });
            }
            return route.continue();
        });
        await owner.page
            .getByRole("button", { name: "Nuovo tenant", exact: true })
            .click();
        await owner.page.getByLabel("Nome", { exact: true }).fill("UI tenant");
        await owner.page
            .getByRole("button", { name: "Salva", exact: true })
            .click();
        await owner.page
            .getByText("Esito incerto. Contesto e comando congelati.", {
                exact: true,
            })
            .waitFor();
        assert.equal(
            await owner.page.getByLabel("Tenant destinatario").isDisabled(),
            true,
        );
        assert.equal(
            await owner.page.getByLabel("Nome", { exact: true }).isDisabled(),
            true,
        );
        assert.equal(
            await owner.page
                .getByRole("button", { name: "Nuovo tenant", exact: true })
                .isDisabled(),
            true,
        );
        await owner.page
            .getByRole("link", { name: "Enginia360 · Panoramica", exact: true })
            .click();
        await owner.page.waitForTimeout(500);
        assert.equal(
            new URL(owner.page.url()).pathname,
            "/organization",
            "uncertain context must prevent SPA navigation losing command",
        );
        badCsrf = true;
        await owner.page
            .getByRole("button", {
                name: "Riprova lo stesso comando",
                exact: true,
            })
            .click();
        await owner.page
            .getByRole("status")
            .filter({ hasText: "CSRF non valida" })
            .waitFor();
        assert.equal(
            await owner.page.getByLabel("Nome", { exact: true }).isDisabled(),
            true,
            "CSRF refusal after lost accepted response cannot release frozen command",
        );
        dropRead = true;
        await owner.page
            .getByRole("button", {
                name: "Riprova lo stesso comando",
                exact: true,
            })
            .click();
        await owner.page
            .getByRole("status")
            .filter({ hasText: "Servizio non disponibile" })
            .waitFor();
        assert.equal(
            await owner.page.getByLabel("Nome", { exact: true }).isDisabled(),
            true,
            "accepted replay but failed reread is still uncertain",
        );
        await owner.page
            .getByRole("button", {
                name: "Riprova lo stesso comando",
                exact: true,
            })
            .click();
        await owner.page
            .getByRole("heading", { name: "UI tenant", exact: true })
            .waitFor();
        assert.equal(acceptedBodies.length, 4);
        for (const body of acceptedBodies)
            assert.equal(
                body,
                acceptedBodies[0],
                "lost accepted response must retry byte-identical UUID/payload",
            );
        await owner.page.unroute("**/api/v1/platform/tenants");
        await owner.page
            .getByRole("status")
            .filter({ hasText: "Salvato e riletto dal server" })
            .waitFor();
        await owner.page
            .getByRole("button", { name: "Rinomina tenant", exact: true })
            .click();
        await owner.page
            .getByLabel("Nome", { exact: true })
            .fill("UI tenant renamed");
        await owner.page
            .getByRole("button", { name: "Salva", exact: true })
            .click();
        await owner.page
            .getByRole("heading", { name: "UI tenant renamed", exact: true })
            .waitFor();
        console.log("PASS MVP02C UI tenant create/rename authoritative reread");
        for (const [kind, label, createLabel] of [
            ["company", "società", "Nuova società"],
            ["site", "sede", "Nuova sede"],
            ["warehouse", "magazzino", "Nuovo magazzino"],
        ]) {
            await owner.page
                .getByRole("button", { name: createLabel, exact: true })
                .click();
            await owner.page
                .getByLabel("Nome", { exact: true })
                .fill("UI " + kind);
            await owner.page
                .getByRole("button", { name: "Salva", exact: true })
                .click();
            await owner.page
                .getByRole("heading", { name: "UI " + kind, exact: true })
                .waitFor();
            await owner.page
                .getByRole("button", { name: "Rinomina " + label, exact: true })
                .click();
            await owner.page
                .getByLabel("Nome", { exact: true })
                .fill("UI " + kind + " renamed");
            await owner.page
                .getByRole("button", { name: "Salva", exact: true })
                .click();
            await owner.page
                .getByRole("heading", {
                    name: "UI " + kind + " renamed",
                    exact: true,
                })
                .waitFor();
        }
        await control("audit-readback");
        console.log(
            "PASS MVP02C complete UI hierarchy create/rename + SQL all4 kinds",
        );
        const target = await owner.page
            .getByLabel("Tenant destinatario")
            .inputValue();
        const tree = await (
            await owner.context.request.get(
                origin + "/api/v1/platform/tenants/" + target,
            )
        ).json();
        await owner.page
            .getByRole("button", { name: "Rinomina magazzino", exact: true })
            .click();
        const csrf = (
            await (
                await owner.context.request.get(origin + "/auth/csrf")
            ).json()
        ).requestToken;
        const warehouse = tree.warehouses[0];
        const concurrent = {
            commandId: require("node:crypto").randomUUID(),
            operation: "rename",
            kind: "warehouse",
            tenantId: target,
            resourceId: warehouse.id,
            parentId: warehouse.parentId,
            name: "Concurrent warehouse",
            expectedRevision: warehouse.revision,
        };
        assert.equal(
            (
                await owner.context.request.post(
                    origin + "/api/v1/platform/tenants/" + target + "/commands",
                    { headers: { "X-CSRF-TOKEN": csrf }, data: concurrent },
                )
            ).status(),
            200,
        );
        await owner.page
            .getByLabel("Nome", { exact: true })
            .fill("Stale warehouse");
        await owner.page
            .getByRole("button", { name: "Salva", exact: true })
            .click();
        await owner.page
            .getByRole("status")
            .filter({ hasText: "Conflitto:" })
            .waitFor();
        await owner.page
            .getByRole("heading", { name: "Concurrent warehouse", exact: true })
            .waitFor();
        assert.equal(
            await owner.page
                .getByRole("button", { name: "Salva", exact: true })
                .count(),
            0,
            "conflict must discard stale revision, require fresh edit",
        );
        console.log("PASS MVP02C stale revision conflict authoritative reread");
        const unicodeName = "😀".repeat(100);
        await owner.page
            .getByRole("button", { name: "Rinomina magazzino", exact: true })
            .click();
        await owner.page.getByLabel("Nome", { exact: true }).fill(unicodeName);
        await owner.page
            .getByRole("button", { name: "Salva", exact: true })
            .click();
        await owner.page
            .getByRole("heading", { name: unicodeName, exact: true })
            .waitFor();
        await owner.page
            .getByRole("button", { name: "Rinomina magazzino", exact: true })
            .click();
        await owner.page
            .getByLabel("Nome", { exact: true })
            .fill("Concurrent warehouse");
        await owner.page
            .getByRole("button", { name: "Salva", exact: true })
            .click();
        await owner.page
            .getByRole("heading", { name: "Concurrent warehouse", exact: true })
            .waitFor();
        console.log(
            "PASS MVP02C exact server Unicode100-scalar name boundary, no client UTF16 narrowing",
        );
        // Regression coverage of existing session/authority APIs and generation-isolated UI reads.
        const nojs = await browser.newContext({ javaScriptEnabled: false });
        await nojs.addCookies(await owner.context.cookies());
        const ssr = await nojs.newPage();
        const htmlResponse = await ssr.goto(
            origin + "/organization?tenant=" + target,
        );
        assert.equal(htmlResponse.status(), 200);
        assert.match(htmlResponse.headers()["cache-control"], /no-store/);
        await ssr
            .getByRole("heading", { name: "Concurrent warehouse", exact: true })
            .waitFor();
        fs.writeFileSync(
            "/evidence/authenticated-nojs.html",
            await ssr.content(),
        );
        fs.writeFileSync(
            "/evidence/ssr-headers.json",
            JSON.stringify({
                status: htmlResponse.status(),
                cacheControl: htmlResponse.headers()["cache-control"],
            }),
        );
        await nojs.close();
        const ordinary = await login(browser, 0);
        await ordinary.page
            .getByText("Autorità amministrativa assente o revocata", {
                exact: true,
            })
            .waitFor();
        assert.equal(
            await ordinary.page.getByLabel("Tenant destinatario").count(),
            0,
        );
        assert.equal(
            await ordinary.page
                .getByText("UI tenant renamed", { exact: true })
                .count(),
            0,
        );
        assert.equal(
            (
                await ordinary.context.request.get(
                    origin + "/api/v1/platform/tenants/" + target,
                )
            ).status(),
            403,
        );
        assert.equal(
            (
                await owner.context.request.post(
                    origin + "/api/v1/platform/tenants/" + target + "/commands",
                    { data: concurrent },
                )
            ).status(),
            400,
            "CSRF cannot be skipped from cookie UI",
        );
        const emptyId = await owner.page
            .getByLabel("Tenant destinatario")
            .locator("option")
            .filter({ hasText: "Empty synthetic tenant" })
            .getAttribute("value");
        let release;
        const held = new Promise((resolve) => (release = resolve));
        let enteredResolve;
        const entered = new Promise((resolve) => (enteredResolve = resolve));
        await owner.page.route(
            "**/api/v1/platform/tenants/" + target,
            async (route) => {
                const response = await route.fetch();
                enteredResolve();
                await held;
                await route.fulfill({ response });
            },
        );
        await owner.page
            .getByLabel("Tenant destinatario")
            .selectOption(emptyId);
        await owner.page
            .getByRole("heading", {
                name: "Empty synthetic tenant",
                exact: true,
            })
            .waitFor();
        await owner.page.getByLabel("Tenant destinatario").selectOption(target);
        await entered;
        await owner.page
            .getByLabel("Tenant destinatario")
            .selectOption(emptyId);
        await owner.page
            .getByRole("heading", {
                name: "Empty synthetic tenant",
                exact: true,
            })
            .waitFor();
        release();
        await owner.page.waitForTimeout(300);
        assert.equal(
            await owner.page
                .getByRole("heading", {
                    name: "UI tenant renamed",
                    exact: true,
                })
                .count(),
            0,
            "late old target response cannot replace latest selection",
        );
        await owner.page.unroute("**/api/v1/platform/tenants/" + target);
        await owner.page.getByLabel("Tenant destinatario").selectOption(target);
        await owner.page
            .getByRole("heading", { name: "Concurrent warehouse", exact: true })
            .waitFor();
        console.log(
            "PASS MVP02C authenticated noJS SSR private/no-store; ordinary denial; CSRF; latest target response wins",
        );
        const layouts = [];
        for (const viewport of [
            { width: 1440, height: 900 },
            { width: 1366, height: 768 },
            { width: 390, height: 844 },
        ]) {
            await owner.page.setViewportSize(viewport);
            const create = owner.page.getByRole("button", {
                name: "Nuovo tenant",
                exact: true,
            });
            await create.focus();
            await owner.page.keyboard.press("Enter");
            const input = owner.page.getByLabel("Nome", { exact: true });
            await input.waitFor();
            assert.equal(
                await input.evaluate((e) => e === document.activeElement),
                true,
                "keyboard create focuses name",
            );
            assert.ok(
                (await input.boundingBox()).height >= 40,
                "editable name must have usable keyboard/touch height",
            );
            await input.fill("Keyboard only, not submitted");
            await owner.page.keyboard.press("Escape");
            assert.equal(await input.count(), 0, "Escape cancels unsent edit");
            assert.equal(
                await create.evaluate((e) => e === document.activeElement),
                true,
                "cancel restores triggering focus",
            );
            const layout = await owner.page.evaluate(() => ({
                width: innerWidth,
                scrollWidth: document.documentElement.scrollWidth,
            }));
            assert.ok(
                layout.scrollWidth <= layout.width,
                "no horizontal organization overflow",
            );
            layouts.push(layout);
            await owner.page
                .getByRole("heading", {
                    name: "Concurrent warehouse",
                    exact: true,
                })
                .scrollIntoViewIfNeeded();
            await owner.page.evaluate(() => window.scrollTo(0, 0));
            await owner.page.screenshot({
                path: "/evidence/organization-" + viewport.width + ".png",
                fullPage: true,
            });
        }
        fs.writeFileSync("/evidence/layouts.json", JSON.stringify(layouts));
        console.log(
            "PASS MVP02C keyboard create/Escape/focus and responsive1440/1366/390",
        );
        await control("revoke");
        await owner.page
            .getByRole("button", { name: "Rileggi dal server", exact: true })
            .click();
        await owner.page
            .getByText("Autorità amministrativa assente o revocata", {
                exact: true,
            })
            .waitFor();
        assert.equal(
            await owner.page
                .getByRole("heading", {
                    name: "UI tenant renamed",
                    exact: true,
                })
                .count(),
            0,
        );
        assert.equal(
            (
                await (
                    await owner.context.request.get(origin + "/auth/session")
                ).json()
            ).authenticated,
            true,
        );
        await control("grant");
        await owner.page.reload();
        await owner.page
            .getByText("Autorità globale verificata", { exact: true })
            .waitFor();
        const copied = await browser.newContext();
        await copied.addCookies(await owner.context.cookies());
        assert.equal(
            (
                await copied.request.get(origin + "/api/v1/platform/tenants")
            ).status(),
            200,
        );
        const replayPage = await copied.newPage();
        await replayPage.goto(origin + "/organization?tenant=" + target);
        await replayPage
            .getByRole("heading", { name: "Concurrent warehouse", exact: true })
            .waitFor();
        await owner.page
            .getByRole("button", { name: "Esci dalla sessione", exact: true })
            .click();
        await owner.page.waitForURL(origin + "/");
        await owner.page.goto(origin + "/organization");
        await owner.page
            .getByText("Sessione assente o scaduta", { exact: true })
            .waitFor();
        assert.equal(
            (
                await copied.request.get(origin + "/api/v1/platform/tenants")
            ).status(),
            401,
            "logout invalidates copied session cookie in actual server ticket store",
        );
        await replayPage
            .getByRole("button", { name: "Rileggi dal server", exact: true })
            .click();
        await replayPage
            .getByText("Sessione assente o scaduta", { exact: true })
            .waitFor();
        assert.equal(
            await replayPage.getByLabel("Tenant destinatario").count(),
            0,
        );
        await copied.close();
        await ordinary.context.close();
        await owner.context.close();
        console.log(
            "PASS MVP02C active-session authority revoke; UI logout; copied cookie denied and session loss SSR visible",
        );
    } finally {
        await browser.close();
    }
})().catch((e) => {
    console.error(e);
    process.exit(1);
});
