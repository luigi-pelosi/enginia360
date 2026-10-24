const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");
const fixture = JSON.parse(fs.readFileSync("/run/fixture.json", "utf8"));
const origin = "https://app.r00.test:8443";
const checks = [];
function pass(name) {
    checks.push(name);
    console.log("PASS R04A " + name);
}
async function get(page, path) {
    return page.evaluate(async (path) => {
        const r = await fetch(path);
        return { status: r.status, value: await r.json().catch(() => null) };
    }, path);
}
async function post(page, path, body) {
    const token = (await get(page, "/auth/csrf")).value.requestToken;
    return page.evaluate(
        async ({ path, body, token }) => {
            const r = await fetch(path, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-TOKEN": token,
                },
                body: JSON.stringify(body),
            });
            return {
                status: r.status,
                value: await r.json().catch(() => null),
            };
        },
        { path, body, token },
    );
}
async function control(action) {
    fs.writeFileSync("/run/control/request.tmp", action);
    fs.renameSync("/run/control/request.tmp", "/run/control/request");
    for (let i = 0; i < 300; i++) {
        if (fs.existsSync("/run/control/ack")) {
            assert.equal(fs.readFileSync("/run/control/ack", "utf8"), action);
            fs.unlinkSync("/run/control/ack");
            return;
        }
        await new Promise((r) => setTimeout(r, 100));
    }
    assert.fail("controller acknowledgement missing");
}
(async () => {
    const browser = await chromium.launch({ headless: true });
    try {
        const page = await browser.newPage();
        let ready = false;
        for (let i = 0; i < 40; i++) {
            try {
                if (
                    (await page.goto(origin + "/auth/session")).status() === 200
                ) {
                    ready = true;
                    break;
                }
            } catch {}
            await new Promise((r) => setTimeout(r, 500));
        }
        assert(ready);
        await page.goto(origin + "/");
        await page.getByRole("button", { name: "Accedi", exact: true }).click();
        await page.locator("#username").fill(fixture.users[0].username);
        await page.locator("#password").fill(fixture.users[0].password);
        await Promise.all([
            page.waitForURL((u) => u.hostname === "app.r00.test"),
            page.locator("#kc-login").click(),
        ]);
        const ctx = fixture.contexts[0],
            data = fixture.workshop[0],
            order = crypto.randomUUID();
        assert.equal(
            (
                await post(page, "/api/v1/workshop/orders", {
                    id: order,
                    legalEntityId: ctx.legalEntityId,
                    siteId: ctx.siteId,
                    documentTypeId: data.documentTypeId,
                    configurationVersion: 7,
                    payerId: data.payerId,
                    vehicleId: data.vehicleId,
                })
            ).status,
            201,
        );
        let revision = 0;
        const groups = [],
            lines = [];
        async function command(type, fields) {
            const r = await post(
                page,
                `/api/v1/workshop/orders/${order}/editor/commands`,
                {
                    type,
                    commandId: crypto.randomUUID(),
                    expectedRevision: revision,
                    expectedLinePolicyVersion: 9,
                    expectedStructurePolicyVersion: 1,
                    groupId: null,
                    lineId: null,
                    title: null,
                    description: null,
                    catalogItemId: null,
                    catalogVersion: null,
                    quantity: null,
                    unitPrice: null,
                    discountPercent: null,
                    ...fields,
                },
            );
            assert.equal(r.status, 201, JSON.stringify(r));
            revision = r.value.appliedRevision;
        }
        for (let i = 0; i < 2; i++) {
            groups.push(crypto.randomUUID());
            lines.push(crypto.randomUUID());
            await command("AddGroup", {
                groupId: groups[i],
                title: "Materiali " + i,
            });
            await command("AddCommercialLine", {
                lineId: lines[i],
                groupId: groups[i],
                catalogItemId: data.partId,
                catalogVersion: 8,
                quantity: "3",
                unitPrice: "1",
                discountPercent: "0",
            });
        }
        const profileProbe = await post(
            page,
            `/api/v1/inventory/orders/${order}/lines/${lines[0]}/reservations`,
            {
                id: crypto.randomUUID(),
                warehouseId: ctx.warehouseId,
                quantity: "1",
                catalogVersion: 8,
            },
        );
        const missingRead = await get(
            page,
            `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
        );
        assert.deepEqual(
            {
                status: profileProbe.status,
                canReserve: missingRead.value.canReserve,
                profile: missingRead.value.stockProfile,
            },
            { status: 409, canReserve: false, profile: "missing" },
            "D76 missing company profile blocks dependent writes and advice, not reads",
        );
        assert.equal(profileProbe.value.code, "stock_profile_missing");
        await control("stock-profile-local");
        const initial = await get(
            page,
            `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
        );
        assert.equal(initial.status, 200);
        assert.equal(
            initial.value.canReserve,
            true,
            "owning stock read must supply exact-action advisory, independently from editor grants",
        );
        await page.goto(origin + "/ui01-runtime.html#order=" + order);
        await page.getByLabel("Workspace commessa").waitFor();
    await page.getByText("Operazioni materiali", { exact: true }).click();
    await page.getByRole("region", { name: "Operazioni materiali" }).waitFor();
        assert.equal(
            await page
                .getByRole("region", { name: "Operazioni materiali" })
                .count(),
            1,
            "real authenticated workspace must expose MaterialOperations, not disconnected logistics",
        );
        const panel = page.getByRole("region", {
            name: "Operazioni materiali",
        });
        await panel.getByLabel("Riga ricambio").selectOption(lines[0]);
        await panel
            .getByLabel("Magazzino materiali")
            .selectOption(ctx.warehouseId);
        await panel.getByText("Fisico magazzino: 2").waitFor();
        await panel.getByLabel("Quantità da prenotare").fill("3");
        await panel
            .getByRole("button", {
                name: "Prenota quantità esplicita",
                exact: true,
            })
            .click();
        await panel.getByText(/Disponibilità insufficiente/).waitFor();
        assert.equal(
            (
                await get(
                    page,
                    `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
                )
            ).value.reservations.length,
            0,
        );
        const reservePath = `/api/v1/inventory/orders/${order}/lines/${lines[0]}/reservations`;
        const commercialSummary = await page.locator("footer").textContent();
        let lost = false,
            readLost = false;
        const attempts = [];
        await page.route("**" + reservePath, async (route) => {
            attempts.push(route.request().postData());
            if (!lost) {
                const response = await route.fetch();
                assert.equal(response.status(), 201);
                lost = true;
                await route.abort("failed");
            } else await route.continue();
        });
        await panel.getByLabel("Quantità da prenotare").fill("2");
        await panel
            .getByRole("button", {
                name: "Prenota quantità esplicita",
                exact: true,
            })
            .click();
        await panel
            .getByText(/Esito incerto: riprova il comando identico/)
            .waitFor();
        assert.equal(
            await panel.getByLabel("Quantità da prenotare").isDisabled(),
            true,
        );
        assert.equal(
            await panel.getByLabel("Riga ricambio").isDisabled(),
            true,
        );
        await page.route(
            "**/api/v1/inventory/orders/" + order + "/lines/" + lines[0] + "?*",
            async (route) => {
                if (!readLost) {
                    readLost = true;
                    await route.abort("failed");
                } else await route.continue();
            },
        );
        await panel
            .getByRole("button", {
                name: "Riprova prenotazione identica",
                exact: true,
            })
            .click();
        await panel
            .getByText(
                "Registrato; stato aggiornato non verificato. Rileggi materiali.",
            )
            .waitFor();
        assert.equal(
            await page.locator("footer").textContent(),
            commercialSummary,
            "optional material error cannot discard independent saved commercial summary",
        );
        assert.equal(attempts.length, 2);
        assert.equal(
            attempts[0],
            attempts[1],
            "accepted lost response replay freezes complete URL/UUID/payload",
        );
        await panel
            .getByRole("button", { name: "Rileggi materiali", exact: true })
            .click();
        await panel.getByText("Residuo riga (tutti i magazzini): 1").waitFor();
        const state = (
            await get(
                page,
                `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
            )
        ).value;
        assert.deepEqual(
            [state.physical, state.available, state.reserved, state.remaining],
            ["2", "0", "2", "1"],
        );
        assert.equal(state.reservations.length, 1);
        pass("real TLS OIDC UI explicit reserve 3 denied / 2 accepted");
        const reservationId = state.reservations[0].id;
        const pickingPath = `/api/v1/inventory/orders/${order}/lines/${lines[0]}/reservations/${reservationId}/picks`;
        const picking = (await get(page, pickingPath)).value;
        assert.equal(
            await panel.getByLabel("Prenotazione da prelevare").count(),
            1,
            "specific reservation selector must be operable",
        );
        assert.equal(
            picking.canPick,
            true,
            "specific reservation read must expose exact pick advisory",
        );
        await panel
            .getByLabel("Prenotazione da prelevare")
            .selectOption(reservationId);
        let lostPick = false;
        const pickAttempts = [];
        await page.route("**" + pickingPath, async (route) => {
            if (route.request().method() !== "POST") return route.continue();
            pickAttempts.push(route.request().postData());
            if (!lostPick) {
                const r = await route.fetch();
                assert.equal(r.status(), 201);
                lostPick = true;
                await route.abort("failed");
            } else await route.continue();
        });
        await panel.getByLabel("Quantità da prelevare").fill("1");
        await panel
            .getByRole("button", {
                name: "Preleva quantità esplicita",
                exact: true,
            })
            .click();
        await panel
            .getByText(
                "Esito prelievo incerto: riprova solo il comando identico.",
            )
            .waitFor();
        assert.deepEqual(
            [
                await panel.getByLabel("Riga ricambio").isDisabled(),
                await panel.getByLabel("Magazzino materiali").isDisabled(),
                await panel
                    .getByRole("button", {
                        name: "Rileggi materiali",
                        exact: true,
                    })
                    .isDisabled(),
            ],
            [true, true, true],
            "uncertain descendant command must freeze ancestor context/reread, not lose original envelope",
        );
        await panel
            .getByRole("button", {
                name: "Riprova prelievo identico",
                exact: true,
            })
            .click();
        await panel.getByText("Residuo prenotazione da prelevare: 1").waitFor();
        assert.equal(pickAttempts.length, 2);
        assert.equal(pickAttempts[0], pickAttempts[1]);
        const picked = (await get(page, pickingPath)).value;
        assert.equal(picked.picks.length, 1);
        assert.equal(picked.picks[0].quantity, "1");
        assert.equal(picked.picks[0].placementLocation, "Preparazione A");
        assert.equal(picked.picks[0].workingGroupId, groups[0]);
        const afterPicking = (
            await get(
                page,
                `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
            )
        ).value;
        assert.deepEqual(
            [
                afterPicking.physical,
                afterPicking.available,
                afterPicking.activeCommitted,
            ],
            ["2", "0", "2"],
            "picking/staging is not a stock decrement",
        );
        pass("real UI partial picking/staging without fake stock effect");
        const pickId = picked.picks[0].id;
        const installPath = `/api/v1/workshop/orders/${order}/lines/${lines[0]}/picks/${pickId}/installations`;
        const installState = (await get(page, installPath)).value;
        assert.deepEqual(
            {
                control: await panel
                    .getByLabel("Prelievo da installare")
                    .count(),
                canInstall: installState.canInstall,
            },
            { control: 1, canInstall: true },
            "installation requires real specific-pick controls and owning action advisory",
        );
        await panel.getByLabel("Prelievo da installare").selectOption(pickId);
        await panel.getByLabel("Quantità da installare").fill("0.5");
        await panel
            .getByRole("button", {
                name: "Installa quantità esplicita",
                exact: true,
            })
            .click();
        await panel.getByText("Residuo prelievo da installare: 0.5").waitFor();
        const installed = (await get(page, installPath)).value;
        assert.equal(installed.installations.length, 1);
        assert.equal(installed.installations[0].stockEffect, "Consumed");
        assert.equal(
            (
                await get(
                    page,
                    `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
                )
            ).value.physical,
            "1.5",
        );
        assert.equal(
            await panel
                .getByText("Fisico magazzino: 1.5", { exact: true })
                .count(),
            1,
            "accepted installation must refresh owning stock, not leave pre-installation UI snapshot",
        );
        pass("real UI partial installation and actual consumption");
        await control("consume-fault-on");
        await panel.getByLabel("Quantità da installare").fill("0.5");
        await panel
            .getByRole("button", {
                name: "Installa quantità esplicita",
                exact: true,
            })
            .click();
        await panel
            .getByText(
                "Installazione accettata; consumo Pending da recuperare.",
            )
            .waitFor();
        const pendingState = (await get(page, installPath)).value;
        const pending = pendingState.installations.find(
            (i) => i.stockEffect === "Pending",
        );
        assert(pending);
        assert.equal(
            (
                await get(
                    page,
                    `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
                )
            ).value.physical,
            "1.5",
        );
        await page.reload();
        await page.getByLabel("Workspace commessa").waitFor();
    await page.getByText("Operazioni materiali", { exact: true }).click();
    await page.getByRole("region", { name: "Operazioni materiali" }).waitFor();
        await panel.getByLabel("Riga ricambio").selectOption(lines[0]);
        await panel
            .getByLabel("Magazzino materiali")
            .selectOption(ctx.warehouseId);
        await panel
            .getByLabel("Prenotazione da prelevare")
            .selectOption(reservationId);
        await panel.getByLabel("Prelievo da installare").selectOption(pickId);
        await panel
            .getByText(new RegExp(pending.installation.id + ".*Pending"))
            .waitFor();
        assert.deepEqual(
            {
                control: await panel
                    .getByRole("button", {
                        name: "Recupera consumo " + pending.installation.id,
                        exact: true,
                    })
                    .count(),
                canRecover: pendingState.canRecoverConsumption,
            },
            { control: 1, canRecover: true },
            "reload must recover original accepted fact, not generate a new installation",
        );
        await control("consume-fault-off");
        const recoveredResponse = page.waitForResponse(
            (r) =>
                r.url().endsWith(installPath) &&
                r.request().method() === "POST",
        );
        await panel
            .getByRole("button", {
                name: "Recupera consumo " + pending.installation.id,
                exact: true,
            })
            .click();
        const replay = await recoveredResponse;
        assert.deepEqual(replay.request().postDataJSON(), {
            id: pending.installation.id,
            quantity: "0.5",
        });
        await panel
            .getByText(new RegExp(pending.installation.id + ".*Consumed"))
            .waitFor();
        assert.equal(
            (await get(page, installPath)).value.installations.length,
            2,
        );
        pass(
            "Pending accepted durable fact, reload and original UUID recovery",
        );
        const carcassPath = `/api/v1/inventory/orders/${order}/lines/${lines[0]}/carcass-returns`;
        const carcassState = (
            await get(page, carcassPath + "?warehouseId=" + ctx.warehouseId)
        ).value;
        assert.deepEqual(
            {
                control: await panel
                    .getByRole("button", {
                        name: "Ricevi intero residuo carcassa",
                        exact: true,
                    })
                    .count(),
                canReceive: carcassState.canReceiveCarcass,
            },
            { control: 1, canReceive: true },
            "whole-residual carcass requires real controls and owning action advisory",
        );
        await panel
            .getByRole("button", { name: "Rileggi carcasse", exact: true })
            .click();
        await panel.getByText("Residuo carcassa (tutta la riga): 1").waitFor();
        await panel.getByLabel("Quantità carcassa").fill("0.5");
        await panel
            .getByLabel("Descrizione carcassa")
            .fill("Synthetic replaced component");
        await panel
            .getByRole("button", {
                name: "Ricevi intero residuo carcassa",
                exact: true,
            })
            .click();
        await panel.getByText(/coprire esattamente tutto il residuo/).waitFor();
        assert.equal(
            (await get(page, carcassPath + "?warehouseId=" + ctx.warehouseId))
                .value.returns.length,
            0,
        );
        await panel.getByLabel("Quantità carcassa").fill("1");
        await panel
            .getByRole("button", {
                name: "Ricevi intero residuo carcassa",
                exact: true,
            })
            .click();
        await panel.getByText("Residuo carcassa (tutta la riga): 0").waitFor();
        const carcass = (
            await get(page, carcassPath + "?warehouseId=" + ctx.warehouseId)
        ).value;
        assert.equal(carcass.returns.length, 1);
        assert.equal(carcass.returns[0].installations.length, 2);
        assert.equal(carcass.returns[0].location, "Dedicated carcass");
        assert.deepEqual(
            carcass.returns[0].installations
                .map((i) => i.installationId)
                .sort(),
            pendingState.installations.map((i) => i.installation.id).sort(),
        );
        assert.equal(
            (
                await get(
                    page,
                    `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
                )
            ).value.physical,
            "1",
        );
        pass(
            "real UI whole residual carcass, exact installation coverage, no new stock",
        );
        await control("picking-off");
        const unstaged = await post(page, pickingPath, {
            id: crypto.randomUUID(),
            quantity: "0.5",
        });
        assert.equal(unstaged.status, 201);
        assert.equal(unstaged.value.placementLocation, null);
        assert.equal(unstaged.value.configurationVersion, 2);
        assert.equal(
            (
                await get(
                    page,
                    `/api/v1/inventory/orders/${order}/lines/${lines[0]}?warehouseId=${ctx.warehouseId}`,
                )
            ).value.physical,
            "1",
        );
        await panel
            .getByRole("button", { name: "Rileggi prelievi", exact: true })
            .click();
        await panel
            .getByLabel("Prelievo da installare")
            .selectOption(unstaged.value.id);
        await panel.getByLabel("Quantità da installare").fill("0.25");
        await panel
            .getByRole("button", {
                name: "Installa quantità esplicita",
                exact: true,
            })
            .click();
        await panel.getByText("Residuo prelievo da installare: 0.25").waitFor();
        await panel
            .getByRole("button", { name: "Rileggi carcasse", exact: true })
            .click();
        await panel
            .getByText("Residuo carcassa (tutta la riga): 0.25")
            .waitFor();
        const nextResidual = (
            await get(page, carcassPath + "?warehouseId=" + ctx.warehouseId)
        ).value;
        assert.equal(nextResidual.returns.length, 1);
        assert.equal(nextResidual.returns[0].id, carcass.returns[0].id);
        assert.equal(nextResidual.returns[0].quantity, "1");
        assert.equal(nextResidual.outstanding, "0.25");
        await control("picking-missing");
        const missingPick = await post(page, pickingPath, {
            id: crypto.randomUUID(),
            quantity: "0.25",
        });
        assert.equal(missingPick.status, 409);
        assert.equal(missingPick.value.code, "picking_configuration_missing");
        await control("picking-restore");
        pass(
            "preparation disabled snapshots null, missing configuration refuses, later installation creates new carcass residual without rewriting covered history",
        );
        const externalPage = await browser.newPage();
        await externalPage.goto(origin + "/");
        await externalPage
            .getByRole("button", { name: "Accedi", exact: true })
            .click();
        await externalPage.locator("#username").fill(fixture.users[1].username);
        await externalPage.locator("#password").fill(fixture.users[1].password);
        await Promise.all([
            externalPage.waitForURL((u) => u.hostname === "app.r00.test"),
            externalPage.locator("#kc-login").click(),
        ]);
        const ec = fixture.contexts[1],
            ed = fixture.workshop[1],
            eo = crypto.randomUUID(),
            el = crypto.randomUUID(),
            eg = crypto.randomUUID(),
            er = crypto.randomUUID(),
            ep = crypto.randomUUID(),
            ei = crypto.randomUUID();
        assert.equal(
            (
                await post(externalPage, "/api/v1/workshop/orders", {
                    id: eo,
                    legalEntityId: ec.legalEntityId,
                    siteId: ec.siteId,
                    documentTypeId: ed.documentTypeId,
                    configurationVersion: 7,
                    payerId: ed.payerId,
                    vehicleId: ed.vehicleId,
                })
            ).status,
            201,
        );
        const envelope = (type, revision, fields) => ({
            type,
            commandId: crypto.randomUUID(),
            expectedRevision: revision,
            expectedLinePolicyVersion: 9,
            expectedStructurePolicyVersion: 1,
            groupId: null,
            lineId: null,
            title: null,
            description: null,
            catalogItemId: null,
            catalogVersion: null,
            quantity: null,
            unitPrice: null,
            discountPercent: null,
            ...fields,
        });
        assert.equal(
            (
                await post(
                    externalPage,
                    `/api/v1/workshop/orders/${eo}/editor/commands`,
                    envelope("AddGroup", 0, {
                        groupId: eg,
                        title: "External history",
                    }),
                )
            ).status,
            201,
        );
        assert.equal(
            (
                await post(
                    externalPage,
                    `/api/v1/workshop/orders/${eo}/editor/commands`,
                    envelope("AddCommercialLine", 1, {
                        lineId: el,
                        groupId: eg,
                        catalogItemId: ed.partId,
                        catalogVersion: 8,
                        quantity: "3",
                        unitPrice: "1",
                        discountPercent: "0",
                    }),
                )
            ).status,
            201,
        );
        await control(`external-history:${eo}:${el}:${eg}:${er}:${ep}:${ei}`);
        const exbase = `/api/v1/inventory/orders/${eo}/lines/${el}`,
            exinstall = `/api/v1/workshop/orders/${eo}/lines/${el}/picks/${ep}/installations`;
        const exread = await get(
            externalPage,
            exbase + "?warehouseId=" + ec.warehouseId,
        );
        assert.equal(exread.status, 200);
        assert.equal(exread.value.stockProfile, "external");
        assert.equal(exread.value.canReserve, false);
        const exPick = await post(
            externalPage,
            exbase + `/reservations/${er}/picks`,
            { id: crypto.randomUUID(), quantity: "0.25" },
        );
        const exInstall = await post(externalPage, exinstall, {
            id: crypto.randomUUID(),
            quantity: "0.25",
        });
        const exRecovery = await post(externalPage, exinstall, {
            id: ei,
            quantity: "0.25",
        });
        const exCarcass = await post(
            externalPage,
            exbase + "/carcass-returns",
            {
                id: crypto.randomUUID(),
                warehouseId: ec.warehouseId,
                quantity: "0.5",
                description: "Synthetic external history",
            },
        );
        assert.deepEqual(
            [
                exPick.status,
                exPick.value?.code,
                exInstall.status,
                exRecovery.status,
                exCarcass.status,
                exCarcass.value?.code,
            ],
            [
                409,
                "stock_profile_external",
                404,
                404,
                409,
                "stock_profile_external",
            ],
            "external stock profile forbids all dependent local writes, including recovery without captured local authority",
        );
        assert.equal(
            (await get(externalPage, exbase + `/reservations/${er}/picks`))
                .status,
            200,
        );
        assert.equal((await get(externalPage, exinstall)).status, 200);
        pass(
            "external profile blocks local pick/install/recovery/carcass; history stays readable",
        );
        const primary = `/api/v1/inventory/orders/${order}/lines/${lines[0]}`;
        assert.equal(
            (
                await get(
                    externalPage,
                    primary + "?warehouseId=" + ctx.warehouseId,
                )
            ).status,
            404,
            "cross tenant read does not leak existence",
        );
        assert.equal(
            (
                await post(externalPage, primary + "/reservations", {
                    id: crypto.randomUUID(),
                    warehouseId: ctx.warehouseId,
                    quantity: "0.1",
                    catalogVersion: 8,
                })
            ).status,
            404,
        );
        const anonymous = await browser.newPage();
        await anonymous.goto(origin + "/");
        assert.equal(
            (await get(anonymous, primary + "?warehouseId=" + ctx.warehouseId))
                .status,
            401,
        );
        await anonymous.close();
        const noCsrf = await page.evaluate(
            async ({ primary, warehouseId }) => {
                const r = await fetch(primary + "/reservations", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        id: crypto.randomUUID(),
                        warehouseId,
                        quantity: "0.1",
                        catalogVersion: 8,
                    }),
                });
                return r.status;
            },
            { primary, warehouseId: ctx.warehouseId },
        );
        assert.equal(noCsrf, 400);
        const reader = await browser.newPage();
        await reader.goto(origin + "/");
        await reader
            .getByRole("button", { name: "Accedi", exact: true })
            .click();
        await reader.locator("#username").fill(fixture.users[5].username);
        await reader.locator("#password").fill(fixture.users[5].password);
        await Promise.all([
            reader.waitForURL((u) => u.hostname === "app.r00.test"),
            reader.locator("#kc-login").click(),
        ]);
        const protectedBody = {
            id: crypto.randomUUID(),
            warehouseId: ctx.warehouseId,
            quantity: "0.1",
            catalogVersion: 8,
        };
        for (const scope of ["read", "common", "site", "warehouse"]) {
            await control("target-stock:" + scope);
            const read = await get(
                reader,
                primary + "?warehouseId=" + ctx.warehouseId,
            );
            assert.equal(read.status, 200);
            assert.equal(
                read.value.canReserve,
                false,
                scope + " does not grant stock create",
            );
            assert.equal(
                (await post(reader, primary + "/reservations", protectedBody))
                    .status,
                403,
            );
        }
        await control("target-stock:exact");
        assert.equal(
            (await get(reader, primary + "?warehouseId=" + ctx.warehouseId))
                .value.canReserve,
            true,
        );
        await control("target-stock:revoke");
        assert.equal(
            (await post(reader, primary + "/reservations", protectedBody))
                .status,
            403,
            "revocation after advice must revalidate",
        );
        await control("capability-off");
        for (const [path, flag] of [
            [primary + "?warehouseId=" + ctx.warehouseId, "canReserve"],
            [pickingPath, "canPick"],
            [installPath, "canInstall"],
            [
                carcassPath + "?warehouseId=" + ctx.warehouseId,
                "canReceiveCarcass",
            ],
        ]) {
            const r = await get(page, path);
            assert.equal(r.status, 200);
            assert.equal(
                r.value[flag],
                false,
                "disabled capability keeps history but disables " + flag,
            );
        }
        assert.equal(
            (await post(page, primary + "/reservations", protectedBody)).status,
            403,
        );
        assert.equal(
            (
                await post(page, pickingPath, {
                    id: crypto.randomUUID(),
                    quantity: "0.1",
                })
            ).status,
            403,
        );
        assert.equal(
            (
                await post(page, installPath, {
                    id: pending.installation.id,
                    quantity: "0.5",
                })
            ).status,
            404,
        );
        await control("capability-on");
        pass(
            "anonymous, cross-tenant, CSRF, exact action/scope, common/site/warehouse insufficiency, revoke and capability-off history",
        );
        let currentVersion = 8;
        async function raceLine(quantity) {
            const o = crypto.randomUUID(),
                g = crypto.randomUUID(),
                l = crypto.randomUUID();
            assert.equal(
                (
                    await post(page, "/api/v1/workshop/orders", {
                        id: o,
                        legalEntityId: ctx.legalEntityId,
                        siteId: ctx.siteId,
                        documentTypeId: data.documentTypeId,
                        configurationVersion: 7,
                        payerId: data.payerId,
                        vehicleId: data.vehicleId,
                    })
                ).status,
                201,
            );
            assert.equal(
                (
                    await post(
                        page,
                        `/api/v1/workshop/orders/${o}/editor/commands`,
                        envelope("AddGroup", 0, {
                            groupId: g,
                            title: "Pool race",
                        }),
                    )
                ).status,
                201,
            );
            assert.equal(
                (
                    await post(
                        page,
                        `/api/v1/workshop/orders/${o}/editor/commands`,
                        envelope("AddCommercialLine", 1, {
                            lineId: l,
                            groupId: g,
                            catalogItemId: data.partId,
                            catalogVersion: currentVersion,
                            quantity,
                            unitPrice: "1",
                            discountPercent: "0",
                        }),
                    )
                ).status,
                201,
            );
            return {
                o,
                g,
                l,
                path: `/api/v1/inventory/orders/${o}/lines/${l}`,
            };
        }
        await control("race-stock");
        const a = await raceLine("2");
        await control("catalog-next");
        currentVersion = 9;
        const b = await raceLine("2");
        const reserveA = {
                id: crypto.randomUUID(),
                warehouseId: ctx.warehouseId,
                quantity: "2",
                catalogVersion: 8,
            },
            reserveB = {
                ...reserveA,
                id: crypto.randomUUID(),
                catalogVersion: currentVersion,
            };
        if (fixture.poolSize >= 4) await control("hold-stock");
        const ra = post(page, a.path + "/reservations", reserveA);
        if (fixture.poolSize === 1) await ra;
        const rb = post(page, b.path + "/reservations", reserveB);
        if (fixture.poolSize >= 4) {
            await control("wait-lock:2");
            await control("release-lock");
        }
        const competition = await Promise.all([ra, rb]);
        assert.deepEqual(competition.map((r) => r.status).sort(), [201, 409]);
        assert.equal(
            competition.find((r) => r.status === 409).value.code,
            "insufficient_available",
        );
        pass(
            fixture.poolSize >= 4
                ? "real shared physical pool barrier across orders/non-order groups/catalog versions"
                : "pool1 shared stock sequential safety",
        );
        await control("race-stock");
        const across = await raceLine("3");
        const secondWarehouse = fixture.deniedContexts.find(
            (c) =>
                c.legalEntityId === ctx.legalEntityId &&
                c.siteId === ctx.siteId,
        ).warehouseId;
        if (fixture.poolSize >= 4) await control("hold-line:" + across.l);
        const wa = post(page, across.path + "/reservations", {
            id: crypto.randomUUID(),
            warehouseId: ctx.warehouseId,
            quantity: "2",
            catalogVersion: currentVersion,
        });
        if (fixture.poolSize === 1) await wa;
        const wb = post(page, across.path + "/reservations", {
            id: crypto.randomUUID(),
            warehouseId: secondWarehouse,
            quantity: "2",
            catalogVersion: currentVersion,
        });
        if (fixture.poolSize >= 4) {
            await control("wait-lock:2");
            await control("release-lock");
        }
        const warehouseRace = await Promise.all([wa, wb]);
        assert.deepEqual(warehouseRace.map((r) => r.status).sort(), [201, 409]);
        assert.equal(
            warehouseRace.find((r) => r.status === 409).value.code,
            "exceeds_remaining",
        );
        const cumulative = (
            await get(page, across.path + "?warehouseId=" + secondWarehouse)
        ).value;
        assert.equal(cumulative.reserved, "2");
        assert.equal(cumulative.remaining, "1");
        pass(
            fixture.poolSize >= 4
                ? "real line barrier across authorized warehouses preserves cumulative residual"
                : "pool1 cumulative warehouse residual",
        );
        await control("race-stock");
        const consumerOrder = await raceLine("2");
        if (fixture.poolSize >= 4) await control("hold-stock");
        const consuming = post(
            page,
            `/api/v1/workshop/orders/${order}/lines/${lines[0]}/picks/${unstaged.value.id}/installations`,
            { id: crypto.randomUUID(), quantity: "0.125" },
        );
        if (fixture.poolSize === 1) await consuming;
        const besideConsumption = post(
            page,
            consumerOrder.path + "/reservations",
            {
                id: crypto.randomUUID(),
                warehouseId: ctx.warehouseId,
                quantity: "2",
                catalogVersion: currentVersion,
            },
        );
        if (fixture.poolSize >= 4) {
            await control("wait-lock:2");
            await control("release-lock");
        }
        const stockAndConsumption = await Promise.all([
            consuming,
            besideConsumption,
        ]);
        assert.deepEqual(
            stockAndConsumption.map((r) => r.status),
            [201, 201],
        );
        assert.equal(stockAndConsumption[0].value.stockEffect, "Consumed");
        assert.equal(
            (
                await get(
                    page,
                    consumerOrder.path + "?warehouseId=" + ctx.warehouseId,
                )
            ).value.available,
            "0",
        );
        pass(
            fixture.poolSize >= 4
                ? "real reserve versus consumption stock-row barrier, no artificial availability release"
                : "pool1 reserve and consumption completion without nested connections",
        );
        await control("database-outage");
        const unavailable = page.waitForResponse(
            (r) =>
                r.url().includes(primary + "?warehouseId=") &&
                r.status() === 503,
        );
        await panel
            .getByRole("button", { name: "Rileggi materiali", exact: true })
            .click();
        await unavailable;
        await panel.getByText("Lettura materiali non disponibile.").waitFor();
        assert.equal(
            await page.locator("footer").textContent(),
            commercialSummary,
        );
        await control("database-recover");
        await panel
            .getByRole("button", { name: "Rileggi materiali", exact: true })
            .click();
        const recoveredStock = (
            await get(page, primary + "?warehouseId=" + ctx.warehouseId)
        ).value;
        await panel
            .getByText("Fisico magazzino: " + recoveredStock.physical, {
                exact: true,
            })
            .waitFor();
        pass(
            "real paused PostgreSQL503, authoritative retry, independent commercial summary preserved",
        );
        for (const [width, height] of [
            [1366, 768],
            [1920, 1080],
        ]) {
            await page.setViewportSize({ width, height });
            const last = panel.getByRole("button", {
                name: "Ricevi intero residuo carcassa",
                exact: true,
            });
            await last.scrollIntoViewIfNeeded();
            const box = await last.boundingBox(),
                footer = await page.locator("footer").boundingBox();
            assert(box && footer);
            assert(
                box.x >= 0 &&
                    box.x + box.width <= width &&
                    box.y >= 0 &&
                    box.y + box.height <= footer.y,
                "last material control reachable above sticky summary",
            );
            const input = panel.getByLabel("Quantità da prenotare");
            await input.scrollIntoViewIfNeeded();
            await input.fill("1.123456");
            await input.press("Escape");
            assert.equal(await input.inputValue(), "");
            await input.fill("0");
            await input.press("Enter");
            await panel
                .getByText(
                    "Quantità positiva con massimo 6 interi e 6 decimali.",
                )
                .waitFor();
            assert.equal(
                await input.evaluate((e) => e === document.activeElement),
                true,
            );
            await input.press("Tab");
            assert.equal(
                await panel
                    .getByRole("button", {
                        name: "Prenota quantità esplicita",
                        exact: true,
                    })
                    .evaluate((e) => e === document.activeElement),
                true,
            );
            await page.screenshot({
                path: "/run/control/materials-" + width + ".png",
            });
        }
        pass(
            "real keyboard Enter/Escape/Tab focus and reachable controls above summary at both viewport sizes",
        );
        await control("binding-revoke");
        await panel
            .getByRole("button", { name: "Rileggi materiali", exact: true })
            .click();
        await page
            .getByText("Sessione terminata. Accedi nuovamente.")
            .waitFor();
        assert.equal(
            await page
                .getByRole("region", { name: "Operazioni materiali" })
                .count(),
            0,
        );
        assert.equal(
            await page.locator("footer").textContent(),
            "Riepilogo non verificato",
        );
        pass(
            "real binding revocation401 clears material state and saved document",
        );
        fs.writeFileSync(
            "/run/control/result.json",
            JSON.stringify({
                order,
                groups,
                lines,
                reservationId,
                pickId,
                installationIds: pendingState.installations.map(
                    (i) => i.installation.id,
                ),
                carcassId: carcass.returns[0].id,
                externalOrder: eo,
                checks,
            }),
        );
    } finally {
        await browser.close();
    }
})().catch((e) => {
    console.error(e);
    process.exit(1);
});
