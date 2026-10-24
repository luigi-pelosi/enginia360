const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");
const fixture = JSON.parse(fs.readFileSync("/run/fixture.json", "utf8"));
const origin = "https://app.r00.test:8443";
const checks = [];
const aSeeded = [];
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
async function rawPost(page, path, text, contentType) {
    const token = (await get(page, "/auth/csrf")).value.requestToken;
    return page.evaluate(async ({ path, text, contentType, token }) => {
        const headers = { "X-CSRF-TOKEN": token };
        if (contentType) headers["Content-Type"] = contentType;
        const r = await fetch(path, { method: "POST", headers, body: text });
        return { status: r.status };
    }, { path, text, contentType, token });
}
const controlled4xx = (status, label) => assert(status >= 400 && status < 500, label + " must be a controlled 4xx, got " + status);
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
        await control("stock-profile-local");
        const base = `/api/v1/inventory/orders/${order}/lines/${lines[0]}`;
        const reservationId = crypto.randomUUID(), releaseId = crypto.randomUUID();
        assert.equal((await post(page, base + "/reservations", {id:reservationId,warehouseId:ctx.warehouseId,quantity:"2",catalogVersion:8})).status,201);
        const before = (await get(page, base+`?warehouseId=${ctx.warehouseId}`)).value;
        assert.equal(before.activeCommitted,"2");
        const r = await post(page, base+`/reservations/${reservationId}/releases`,{id:releaseId,quantity:"1"});
        assert.equal(r.status,201,"explicit release1 must be accepted (404 demonstrates route absence only)");
        const after = (await get(page, base+`?warehouseId=${ctx.warehouseId}`)).value;
        assert.equal(after.physical,before.physical);
        assert.equal(after.activeCommitted,"1");
        assert.equal(after.available,"1");
        assert.equal(after.remaining,"2");
        pass("owner reserve2 release1 persisted compensation readback");
        const historyUrl=base+`/reservations/${reservationId}/releases`;
        const history=await get(page,historyUrl);
        assert.equal(history.status,200,"reservation-specific immutable release history endpoint");
        assert.equal(history.value.released,"1");
        assert.equal(history.value.remainingReleasable,"1");
        assert.equal(history.value.canRelease,true);
        assert.equal(history.value.releases[0].id,releaseId);
        const receipt=history.value.releases[0];
        assert.deepEqual((await post(page,historyUrl,{id:releaseId,quantity:"1.000000"})).value,receipt,"normalized q6 replay returns immutable original actor date provenance");
        assert.equal((await post(page,historyUrl,{id:releaseId,quantity:"0.1"})).status,409);
        for(const quantity of ["0","-1","1.0000001","1000000","1e0","NaN"," 1","1,0"])
            assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity})).status,400,quantity);
        assert.equal((await post(page,historyUrl,{id:"00000000-0000-0000-0000-000000000000",quantity:"1"})).status,400);
        assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity:"1",tenantId:ctx.tenantId})).status,400,"tenant is server-owned and unknown payload fields rejected");
        assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity:"2"})).status,409);
        await control("capability-off");
        assert.equal((await get(page,historyUrl)).value.canRelease,false);
        assert.deepEqual((await post(page,historyUrl,{id:releaseId,quantity:"1"})).value,receipt,"accepted receipt replay survives capability off");
        assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity:"1"})).status,403);
        await control("capability-on");
        const csrfDenied=await page.evaluate(async ({historyUrl})=>(await fetch(historyUrl,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:crypto.randomUUID(),quantity:"1"})})).status,{historyUrl});
        assert.equal(csrfDenied,400);
        const anonymous=await browser.newPage();await anonymous.goto(origin+"/");assert.equal((await get(anonymous,historyUrl)).status,401);await anonymous.close();
        const reader=await browser.newPage();await reader.goto(origin+"/");await reader.getByRole("button",{name:"Accedi",exact:true}).click();
        await reader.locator("#username").fill(fixture.users[5].username);await reader.locator("#password").fill(fixture.users[5].password);
        await Promise.all([reader.waitForURL(u=>u.hostname==="app.r00.test"),reader.locator("#kc-login").click()]);
        for(const scope of ["read","common","site","warehouse"]){await control("target-stock:"+scope);assert.equal((await get(reader,historyUrl)).value.canRelease,false);assert.equal((await post(reader,historyUrl,{id:crypto.randomUUID(),quantity:"0.1"})).status,403,scope);}
        await control("target-stock:exact");assert.equal((await get(reader,historyUrl)).value.canRelease,true);
        for(const axis of ["company","site","warehouse"]){
            await control("target-release:"+axis);
            const h=await get(reader,historyUrl);
            assert.equal(h.status,200,"read stays available with wrong "+axis);assert.equal(h.value.canRelease,false,"wrong "+axis);
            assert.equal((await post(reader,historyUrl,{id:crypto.randomUUID(),quantity:"0.1"})).status,403,"release grant on wrong "+axis+" alone must not authorize");
        }
        await control("target-stock:revoke");assert.equal((await post(reader,historyUrl,{id:crypto.randomUUID(),quantity:"0.1"})).status,403);
        await reader.close();
        {
            const stateUrl=base+`?warehouseId=${ctx.warehouseId}`;
            const beforeHistory=(await get(page,historyUrl)).value, beforeStock=(await get(page,stateUrl)).value;
            const bad=[["remaining overflow",{id:crypto.randomUUID(),quantity:"999999.999999"},409],["remaining+1 micro",{id:crypto.randomUUID(),quantity:"1.000001"},409],
                ["zero q6",{id:crypto.randomUUID(),quantity:"0.000000"},400],["negative",{id:crypto.randomUUID(),quantity:"-0.5"},400],
                ["7 decimals",{id:crypto.randomUUID(),quantity:"0.1234567"},400],["7 integer digits",{id:crypto.randomUUID(),quantity:"1000000.5"},400],
                ["14 chars",{id:crypto.randomUUID(),quantity:"00000000000001"},400],["leading plus",{id:crypto.randomUUID(),quantity:"+1"},400],
                ["trailing dot",{id:crypto.randomUUID(),quantity:"1."},400],["leading dot",{id:crypto.randomUUID(),quantity:".5"},400],
                ["null quantity",{id:crypto.randomUUID(),quantity:null},400],["numeric quantity",{id:crypto.randomUUID(),quantity:1},400],
                ["bad uuid",{id:"not-a-guid",quantity:"1"},400],["missing id",{quantity:"1"},400],["int64 overflow digits",{id:crypto.randomUUID(),quantity:"9223372036854775807"},400]];
            for(const [label,body,expected] of bad) assert.equal((await post(page,historyUrl,body)).status,expected,label);
            for(const [label,text,type] of [["empty body","","application/json"],["array","[]","application/json"],["json null","null","application/json"],["truncated json","{\"id\":","application/json"],["plain text","x","text/plain"]])
                controlled4xx((await rawPost(page,historyUrl,text,type)).status,label);
            controlled4xx((await post(page,base+`/reservations/${crypto.randomUUID()}/releases`,{id:crypto.randomUUID(),quantity:"1"})).status,"unknown reservation");
            assert.deepEqual((await get(page,historyUrl)).value,beforeHistory,"rejected inputs leave no partial release row");
            assert.deepEqual((await get(page,stateUrl)).value,beforeStock,"rejected inputs leave stock and reservation state unchanged");
        }
        pass("strict q6/input UUID/payload replay, capability-off history/receipt, CSRF, exact independent read/common/site/warehouse scopes and revocation");
        const picksUrl=base+`/reservations/${reservationId}/picks`;
        assert.equal((await get(page,picksUrl)).value.remainingToPick,"1","release leaves exactly1 pickable");
        assert.equal((await post(page,picksUrl,{id:crypto.randomUUID(),quantity:"2"})).status,409,"cannot pick released quota");
        const reReservationId=crypto.randomUUID();
        assert.equal((await post(page,base+"/reservations",{id:reReservationId,warehouseId:ctx.warehouseId,quantity:"1",catalogVersion:8})).status,201,"released pool quota must be re-reservable");
        const secondWarehouse=fixture.deniedContexts.find(c=>c.legalEntityId===ctx.legalEntityId && c.siteId===ctx.siteId).warehouseId;
        assert.equal((await post(page,base+"/reservations",{id:crypto.randomUUID(),warehouseId:secondWarehouse,quantity:"1",catalogVersion:8})).status,201,"released line capacity spans warehouses");
        assert.equal((await post(page,base+"/reservations",{id:crypto.randomUUID(),warehouseId:secondWarehouse,quantity:"0.000001",catalogVersion:8})).status,409,"cumulative line bound cannot be exceeded");
        const primaryPickId=crypto.randomUUID();
        {
            await control("hold-line:"+lines[0]);
            const pickPromise=post(page,picksUrl,{id:primaryPickId,quantity:"1"});
            await control("wait-lock:1");
            await control("release-lock");
            assert.equal((await pickPromise).status,201);
            assert.equal((await post(page,base+`/reservations/${reservationId}/releases`,{id:crypto.randomUUID(),quantity:"0.000001"})).status,409,"bounded release rejects ANY picked reservation even unpicked remainder");
        }
        await post(page,base+`/reservations/${reReservationId}/releases`,{id:crypto.randomUUID(),quantity:"1"});
        const freeBase=`/api/v1/inventory/orders/${order}/lines/${lines[1]}`;
        const freed=crypto.randomUUID();
        assert.equal((await post(page,freeBase+"/reservations",{id:freed,warehouseId:ctx.warehouseId,quantity:"1",catalogVersion:8})).status,201);
        await page.goto(origin+"/ui01-runtime.html#order="+order);
        await page.getByLabel("Workspace commessa").waitFor();
        await page.getByText("Operazioni materiali",{exact:true}).click();
        const materialPanel=page.getByRole("region",{name:"Operazioni materiali"});
        await materialPanel.getByLabel("Riga ricambio").selectOption(lines[1]);
        await materialPanel.getByLabel("Magazzino materiali").selectOption(ctx.warehouseId);
        const releasePanel=page.getByRole("region",{name:"Rilascio prenotazione"});
        await releasePanel.getByLabel("Prenotazione da rilasciare").selectOption(freed);
        await releasePanel.getByText("Residuo mai prelevato rilasciabile: 1").waitFor();
        {
            const panelsOpen=async()=>page.locator(".ui01-panels > details[open]").count();
            for(const name of ["Tempo effettivo mio","Chiusura e attesa amministrativa"]) await page.locator("summary",{hasText:name}).click();
            assert.equal(await panelsOpen(),3,"all three material panels expanded");
            const focused=(locator)=>locator.evaluate(e=>e===document.activeElement);
            const select=releasePanel.getByLabel("Prenotazione da rilasciare"), input=releasePanel.getByLabel("Quantità da rilasciare");
            const submit=releasePanel.getByRole("button",{name:"Rilascia quantità esplicita",exact:true}), reread=releasePanel.getByRole("button",{name:"Rileggi rilasci",exact:true});
            for(const [width,height] of [[1920,1080],[1366,768]]){
                await page.setViewportSize({width,height});
                assert.equal(await panelsOpen(),3);
                assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),"no horizontal page overflow at "+width);
                const footerBox=await page.locator("footer").boundingBox();
                assert(footerBox&&footerBox.y>=0&&footerBox.y+footerBox.height<=height+1,"sticky footer visible at "+width);
                for(const [name,control] of [["select",select],["quantity",input],["release",submit],["reread",reread]]){
                    await control.scrollIntoViewIfNeeded();
                    const box=await control.boundingBox();
                    assert(box&&box.x>=0&&box.x+box.width<=width&&box.y>=0&&box.y+box.height<=footerBox.y+1,"release "+name+" reachable above sticky footer at "+width+JSON.stringify([box,footerBox]));
                }
                const editorControl=page.locator(".ui01-group").first();
                await editorControl.scrollIntoViewIfNeeded();
                const editorBox=await editorControl.boundingBox();
                assert(editorBox&&editorBox.y>=0&&editorBox.y<footerBox.y,"editor group reachable at "+width);
                await select.focus();
                await page.keyboard.press("Tab");assert(await focused(input),"Tab from reservation goes to quantity at "+width);
                await page.keyboard.press("Tab");assert(await focused(submit),"Tab from quantity goes to release at "+width);
                await page.keyboard.press("Tab");assert(await focused(reread),"Tab from release goes to reread at "+width);
                await input.fill("0");await input.press("Enter");
                await releasePanel.getByText("Quantità positiva con massimo 6 decimali.").waitFor();
                assert(await focused(input),"invalid quantity returns focus to the field at "+width);
                await page.screenshot({path:"/run/control/release-"+width+".png"});
            }
            await page.setViewportSize({width:1920,height:1080});
            for(const name of ["Tempo effettivo mio","Chiusura e attesa amministrativa"]) await page.locator("summary",{hasText:name}).click();
            assert.equal(await panelsOpen(),1);
            pass("real release panel keyboard order, error focus, three panels expanded, editor/sticky footer reachable at 1920x1080 and 1366x768");
        }
        await releasePanel.getByLabel("Quantità da rilasciare").fill("1");
        const envelopes=[];
        let dropped=false;
        await page.route("**/reservations/"+freed+"/releases",async route=>{
            if(route.request().method()!=="POST") return route.continue();
            envelopes.push({url:route.request().url(),body:route.request().postData()});
            if(!dropped){dropped=true;const response=await route.fetch();assert.equal(response.status(),201);return route.abort("connectionfailed");}
            return route.continue();
        });
        await releasePanel.getByRole("button",{name:"Rilascia quantità esplicita",exact:true}).click();
        await releasePanel.getByText("Esito rilascio incerto: riprova solo il comando identico.").waitFor();
        assert(await materialPanel.getByLabel("Riga ricambio").isDisabled());
        assert(await materialPanel.getByLabel("Magazzino materiali").isDisabled());
        assert(await releasePanel.getByLabel("Prenotazione da rilasciare").isDisabled());
        await releasePanel.getByRole("button",{name:"Riprova rilascio identico"}).click();
        await releasePanel.getByText("Rilascio registrato e riletto; fisico e riga commerciale invariati.").waitFor();
        assert.equal(envelopes.length,2);assert.deepEqual(envelopes[0],envelopes[1]);
        const uiReceipt=JSON.parse(envelopes[0].body).id;
        assert.equal((await get(page,freeBase+`/reservations/${freed}/releases`)).value.releases.filter(r=>r.id===uiReceipt).length,1);
        pass("real release UI accepted-response loss freezes URL UUID body and ancestors; immutable retry one effect");
        const freeHistoryUrl=freeBase+`/reservations/${freed}/releases`;
        const uiReceiptRow=(await get(page,freeHistoryUrl)).value.releases.find(r=>r.id===uiReceipt);
        assert(uiReceiptRow);
        const removed=await post(page,`/api/v1/workshop/orders/${order}/editor/commands`,{type:"RemoveLine",commandId:crypto.randomUUID(),expectedRevision:revision,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,lineId:lines[1]});
        assert.equal(removed.status,200,"fully compensated never-picked Part removal must preserve history without false commitment fence: "+JSON.stringify(removed));
        {
            const replay=await post(page,freeHistoryUrl,{id:uiReceipt,quantity:"1.000000"});
            assert.equal(replay.status,200);assert.deepEqual(replay.value,uiReceiptRow,"post-P2 replay returns the original immutable receipt");
            assert.equal((await post(page,freeHistoryUrl,{id:uiReceipt,quantity:"0.5"})).status,409,"changed quantity for an accepted UUID conflicts");
            assert.equal((await post(page,historyUrl,{id:uiReceipt,quantity:"1"})).status,409,"same UUID cannot be retargeted to another reservation");
            assert([404,409].includes((await post(page,freeBase+`/reservations/${reservationId}/releases`,{id:uiReceipt,quantity:"1"})).status),"mismatched line/reservation path cannot retarget");
            const after=(await get(page,freeHistoryUrl));
            assert.equal(after.status,200);assert.deepEqual(after.value.releases,[uiReceiptRow]);assert.equal(after.value.remainingReleasable,"0");assert.equal(after.value.canRelease,false);
            assert(!(await get(page,historyUrl)).value.releases.some(r=>r.id===uiReceipt),"no retargeted row under another reservation");
            const stale=removed.value.appliedRevision;
            for(const [label,expected] of [["max int32",2147483647],["int32 overflow",2147483648],["int64 max",9223372036854775807n],["negative",-1]]){
                const r=await rawPost(page,`/api/v1/workshop/orders/${order}/editor/commands`,'{"type":"AddGroup","commandId":"'+crypto.randomUUID()+'","expectedRevision":'+expected+',"expectedLinePolicyVersion":9,"expectedStructurePolicyVersion":1,"groupId":"'+crypto.randomUUID()+'","title":"SYNTHETIC revision bound"}',"application/json");
                controlled4xx(r.status,label);
            }
            assert.equal((await get(page,`/api/v1/workshop/orders/${order}/editor`)).value.revision,stale,"bad revisions leave the document unchanged");
            pass("post-P2 old release UUID replays original receipt; changed/retargeted payload conflicts; max-revision overflow is controlled with no write");
        }
        {
            const aOrder=crypto.randomUUID(),aLine=crypto.randomUUID(),aGroup=crypto.randomUUID(),aRes=crypto.randomUUID(),aRel=crypto.randomUUID();
            const aUrl=`/api/v1/inventory/orders/${aOrder}/lines/${aLine}/reservations/${aRes}/releases`;
            await control(`authority-seed:${aOrder}:${aLine}:${aGroup}:${aRes}:${aRel}`);
            for(const mode of ["missing","external"]){
                if(mode==="external") await control("authority-external");
                const h=await get(page,aUrl);
                assert.equal(h.status,200,mode+" authority keeps release history readable");assert.equal(h.value.canRelease,false,mode);
                assert.equal(h.value.releases.length,1);assert.equal(h.value.released,"0.25");assert.equal(h.value.remainingReleasable,"0.75");
                const denied=await post(page,aUrl,{id:crypto.randomUUID(),quantity:"0.1"});
                assert.equal(denied.status,409,mode+" authority refuses release writes");assert.equal(denied.value.code,"stock_profile_"+mode);
                const replay=await post(page,aUrl,{id:aRel,quantity:"0.25"});
                assert.equal(replay.status,200);assert.deepEqual(replay.value,h.value.releases[0],mode+" exact replay of an accepted receipt stays readable");
                assert.equal((await post(page,aUrl,{id:aRel,quantity:"0.1"})).status,409);
                assert.deepEqual((await get(page,aUrl)).value,h.value,mode+" refusals wrote no ledger row");
            }
            pass("missing and external company stock authority refuse release writes while history and exact replay stay readable");
            aSeeded.push(aRes);
        }
        if(process.env.RELEASE_POOL==="4") {
            async function ordered(first,second){
                await control("hold-line:"+lines[0]);
                const a=first();await control("wait-lock:1");
                const b=second();await control("wait-lock:2");
                await control("release-lock");return [(await a).status,(await b).status];
            }
            async function reserveOne(){const id=crypto.randomUUID();assert.equal((await post(page,base+"/reservations",{id,warehouseId:ctx.warehouseId,quantity:"1",catalogVersion:8})).status,201);return id;}
            await control("hold-order:"+order);
            const orderReserve=reserveOne();await control("wait-lock:1");await control("release-lock");
            const orderReservation=await orderReserve;
            assert.equal((await post(page,base+`/reservations/${orderReservation}/releases`,{id:crypto.randomUUID(),quantity:"1"})).status,201);
            const revokedReservation=await reserveOne();
            await control("hold-line:"+lines[0]);
            const revokedCommand=post(page,base+`/reservations/${revokedReservation}/releases`,{id:crypto.randomUUID(),quantity:"1"});
            await control("wait-lock:1");await control("release-owner-revoke");await control("release-lock");
            assert.equal((await revokedCommand).status,403,"revocation committed while waiting must be observed before release write");
            await control("release-owner-restore");
            assert.equal((await post(page,base+`/reservations/${revokedReservation}/releases`,{id:crypto.randomUUID(),quantity:"1"})).status,201);
            const rp=await reserveOne();
            const releasePath=base+`/reservations/${rp}/releases`, pickPath=base+`/reservations/${rp}/picks`;
            assert.deepEqual(await ordered(()=>post(page,releasePath,{id:crypto.randomUUID(),quantity:"1"}),()=>post(page,pickPath,{id:crypto.randomUUID(),quantity:"1"})),[201,409],"release first prevents picking released quota");
            const rr=await reserveOne();const rrPath=base+`/reservations/${rr}/releases`;
            assert.deepEqual(await ordered(()=>post(page,rrPath,{id:crypto.randomUUID(),quantity:"1"}),()=>post(page,rrPath,{id:crypto.randomUUID(),quantity:"1"})),[201,409],"two distinct releases cannot overcompensate");
            const same=await reserveOne();const samePath=base+`/reservations/${same}/releases`, sameId=crypto.randomUUID();
            assert.deepEqual(await ordered(()=>post(page,samePath,{id:sameId,quantity:"1"}),()=>post(page,samePath,{id:sameId,quantity:"1.000000"})),[201,200],"simultaneous identical UUID yields immutable receipt once");
            const pr=await reserveOne();
            assert.deepEqual(await ordered(()=>post(page,base+`/reservations/${pr}/picks`,{id:crypto.randomUUID(),quantity:"0.5"}),()=>post(page,base+`/reservations/${pr}/releases`,{id:crypto.randomUUID(),quantity:"0.5"})),[201,409],"pick first refuses release even unpicked remainder for bounded scope");
            pass("separate physical-connection SQL barriers release/pick BOTH orders and release/release distinct+same UUID");
        }
        const remainingBeforeConsume=(await get(page,base+`?warehouseId=${ctx.warehouseId}`)).value.remaining;
        const installId=crypto.randomUUID(), installationPath=`/api/v1/workshop/orders/${order}/lines/${lines[0]}/picks/${primaryPickId}/installations`;
        const installBody={id:installId,quantity:"1"};
        const installed=await post(page,installationPath,installBody);assert.equal(installed.status,201,JSON.stringify(installed));assert.equal(installed.value.stockEffect,"Consumed");
        assert.deepEqual((await post(page,installationPath,installBody)).value,installed.value);
        const afterConsume=(await get(page,base+`?warehouseId=${ctx.warehouseId}`)).value;
        assert.equal(afterConsume.remaining,remainingBeforeConsume,"consumption must NOT reopen reservable line capacity");
        assert.equal((await post(page,base+"/reservations",{id:crypto.randomUUID(),warehouseId:ctx.warehouseId,quantity:"3",catalogVersion:8})).value.code,"exceeds_remaining");
        const carcassId=crypto.randomUUID(),carcassBody={id:carcassId,warehouseId:ctx.warehouseId,quantity:"1",description:"SYNTHETIC replaced component after explicit release"};
        const carcass=await post(page,base+"/carcass-returns",carcassBody);assert.equal(carcass.status,201,JSON.stringify(carcass));assert.equal(carcass.value.workingGroupId,groups[0]);
        assert.deepEqual((await post(page,base+"/carcass-returns",carcassBody)).value,carcass.value);
        const editor=(await get(page,`/api/v1/workshop/orders/${order}/editor`)).value;
        assert.equal(editor.revision,removed.value.appliedRevision);
        assert.equal(editor.summary.total,"3.660000");assert.equal(editor.summary.netAmount,"3.000000");assert.equal(editor.summary.taxAmount,"0.660000");
        const closed=await post(page,`/api/v1/workshop/orders/${order}/technical-closure`,{id:crypto.randomUUID(),expectedRevision:editor.revision});assert.equal(closed.status,201,JSON.stringify(closed));
        assert.deepEqual((await post(page,historyUrl,{id:releaseId,quantity:"1"})).value,receipt,"historical accepted receipt remains exact after closure");
        assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity:"1"})).status,409,"no new release after closure");
        assert.equal((await get(page,historyUrl)).value.canRelease,false);
        const invoiceId=crypto.randomUUID(),invoiceBody={id:invoiceId,orderId:order,documentTypeId:data.invoiceTypeId,configurationVersion:6,documentDate:"2026-10-24",currency:"EUR",reference:"SYNTHETIC-R04C1"};
        const invoice=await post(page,"/api/v1/billing/workshop-invoices",invoiceBody);assert.equal(invoice.status,201,JSON.stringify(invoice));assert.deepEqual(invoice.value.summary,editor.summary);
        assert.deepEqual((await post(page,"/api/v1/billing/workshop-invoices",invoiceBody)).value,invoice.value);
        const confirmationBody={id:crypto.randomUUID(),configurationVersion:6};const confirmationPath=`/api/v1/billing/workshop-invoices/${invoiceId}/confirmation`;
        const confirmed=await post(page,confirmationPath,confirmationBody);assert.equal(confirmed.status,201,JSON.stringify(confirmed));assert.deepEqual((await post(page,confirmationPath,confirmationBody)).value,confirmed.value);
        const journalId=crypto.randomUUID(),journalBody={id:journalId,invoiceId,chartVersion:5};
        const journal=await post(page,"/api/v1/accounting/invoice-journal-entries",journalBody);assert.equal(journal.status,201,JSON.stringify(journal));
        assert.equal(journal.value.balanced,true);assert.equal(journal.value.totalDebit,"3.660000");assert.equal(journal.value.totalCredit,"3.660000");assert.equal(journal.value.difference,"0.000000");
        assert.deepEqual((await post(page,"/api/v1/accounting/invoice-journal-entries",journalBody)).value,journal.value);
        pass("after release/re-reserve: real pick/install/consume/carcass/technical closure/internal Billing/Accounting balanced q6 immutable commercial snapshot and idempotence");
        const foreign=await browser.newPage();await foreign.goto(origin+"/");await foreign.getByRole("button",{name:"Accedi",exact:true}).click();
        await foreign.locator("#username").fill(fixture.users[1].username);await foreign.locator("#password").fill(fixture.users[1].password);
        await Promise.all([foreign.waitForURL(u=>u.hostname==="app.r00.test"),foreign.locator("#kc-login").click()]);
        assert.equal((await get(foreign,historyUrl)).status,404);assert.equal((await post(foreign,historyUrl,{id:crypto.randomUUID(),quantity:"1"})).status,404);
        const fc=fixture.contexts[1],fd=fixture.workshop[1],fo=crypto.randomUUID(),fg=crypto.randomUUID(),fl=crypto.randomUUID();
        await control("external-local-setup");
        assert.equal((await post(foreign,"/api/v1/workshop/orders",{id:fo,legalEntityId:fc.legalEntityId,siteId:fc.siteId,documentTypeId:fd.documentTypeId,configurationVersion:7,payerId:fd.payerId,vehicleId:fd.vehicleId})).status,201);
        async function fcmd(type,rev,fields){const r=await post(foreign,`/api/v1/workshop/orders/${fo}/editor/commands`,{type,commandId:crypto.randomUUID(),expectedRevision:rev,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,...fields});assert.equal(r.status,201,JSON.stringify(r));}
        await fcmd("AddGroup",0,{groupId:fg,title:"SYNTHETIC external release source"});
        await fcmd("AddCommercialLine",1,{groupId:fg,lineId:fl,catalogItemId:fd.partId,catalogVersion:8,quantity:"2",unitPrice:"1.123456",discountPercent:"0"});
        const fr=crypto.randomUUID(), fbase=`/api/v1/inventory/orders/${fo}/lines/${fl}`;
        assert.equal((await post(foreign,fbase+"/reservations",{id:fr,warehouseId:fc.warehouseId,quantity:"2",catalogVersion:8})).status,201);
        const fpath=fbase+`/reservations/${fr}/releases`;
        assert.equal((await post(foreign,fpath,{id:releaseId,quantity:"1"})).status,409,"RLS-hidden UUID collision is controlled without exposing foreign receipt");
        assert.equal((await get(foreign,fpath)).value.releases.length,0);
        assert.equal((await post(foreign,fpath,{id:crypto.randomUUID(),quantity:"1"})).status,201);
        const fre=crypto.randomUUID();assert.equal((await post(foreign,fbase+"/reservations",{id:fre,warehouseId:fc.warehouseId,quantity:"1",catalogVersion:8})).status,201);
        const fp=crypto.randomUUID();assert.equal((await post(foreign,fbase+`/reservations/${fre}/picks`,{id:fp,quantity:"1"})).status,201);
        const fi=crypto.randomUUID();assert.equal((await post(foreign,`/api/v1/workshop/orders/${fo}/lines/${fl}/picks/${fp}/installations`,{id:fi,quantity:"1"})).value.stockEffect,"Consumed");
        assert.equal((await post(foreign,fbase+"/carcass-returns",{id:crypto.randomUUID(),warehouseId:fc.warehouseId,quantity:"1",description:"SYNTHETIC external carcass"})).status,201);
        const fsnapshot=(await get(foreign,`/api/v1/workshop/orders/${fo}/editor`)).value.summary;
        assert.equal((await post(foreign,`/api/v1/workshop/orders/${fo}/technical-closure`,{id:crypto.randomUUID(),expectedRevision:2})).status,201);
        const externalId=crypto.randomUUID(),externalBody={id:externalId,expectedRevision:2};
        assert.equal((await post(foreign,`/api/v1/workshop/orders/${fo}/administrative-requests`,externalBody)).status,201);
        assert.equal((await post(foreign,`/api/v1/workshop/orders/${fo}/administrative-requests`,externalBody)).status,200);
        let externalState;
        for(let i=0;i<100;i++){externalState=(await get(foreign,`/api/v1/workshop/orders/${fo}/administrative-requests`)).value;if(JSON.stringify(externalState).includes('Completed'))break;await new Promise(r=>setTimeout(r,100));}
        assert(JSON.stringify(externalState).includes('Completed'),"actual isolated simulator must acknowledge pinned administrative snapshot after release flow");
        pass("cross-tenant invisibility/RLS-hidden UUID collision, external release consumer and actual simulator pinned snapshot");
        await foreign.close();
        fs.writeFileSync("/run/control/result.json", JSON.stringify({authorityReservations:aSeeded,order,groups,lines,reservationId,releaseId,primaryPickId,installId,carcassId,invoiceId,journalId,externalId,fo,fsnapshot,checks}));
    } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
