const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");
const fixture = JSON.parse(fs.readFileSync("/run/fixture.json", "utf8"));
const origin = "https://app.r00.test:8443";
const checks = [];
const aSeeded = [];
function pass(name) {
    checks.push(name);
    console.log("PASS R04C2 " + name);
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
        const reservationId=crypto.randomUUID(),pickId=crypto.randomUUID(),returnId=crypto.randomUUID();
        assert.notEqual(groups[0],order);
        assert.equal((await post(page,base+"/reservations",{id:reservationId,warehouseId:ctx.warehouseId,quantity:"2",catalogVersion:8})).status,201);
        const pickPath=base+`/reservations/${reservationId}/picks`;
        assert.equal((await post(page,pickPath,{id:pickId,quantity:"2"})).status,201);
        const before=(await get(page,base+`?warehouseId=${ctx.warehouseId}`)).value;
        const editorBefore=(await get(page,`/api/v1/workshop/orders/${order}/editor`)).value;
        const returnPath=base+`/reservations/${reservationId}/picks/${pickId}/new-part-returns`;
        const returned=await post(page,returnPath,{id:returnId,quantity:"1"});
        assert.equal(returned.status,201,"D81 explicit return1 of intact never-installed pick2 must be accepted; route absence is only first tracer signal");
        const after=(await get(page,base+`?warehouseId=${ctx.warehouseId}`)).value;
        assert.equal(after.physical,before.physical,"return must not increment physical");
        assert.equal(after.activeCommitted,"1","return compensates exactly one active commitment");
        assert.equal(after.available,"1","returned quota becomes available");
        assert.equal(after.remaining,"2","returned quota becomes re-reservable cumulatively");
        const state=await get(page,returnPath);assert.equal(state.status,200);
        assert.equal(state.value.remainingWithTechnician,"1");
        assert.equal(state.value.reason,"ready","return advisory supplies current authoritative reason");
        assert.deepEqual((await get(page,`/api/v1/workshop/orders/${order}/editor`)).value,editorBefore,"return never changes commercial line or revision");
        await control(`verify-return:${order}:${lines[0]}:${groups[0]}:${reservationId}:${pickId}:${returnId}`);
        pass("owner reserve2 pick2 return1 SQL original warehouse physical unchanged active1 available+1 technician1 commercial+revision unchanged");
        await control(`verify-return-provenance:${pickId}`);
        await control(`verify-install-bound:${pickId}`);
        if(process.env.RELEASE_POOL==="4") {
            await control("hold-line:"+lines[0]);
            const revoked=post(page,returnPath,{id:crypto.randomUUID(),quantity:"0.1"});
            await control("wait-lock:1");await control("return-owner-revoke");await control("release-lock");
            assert.equal((await revoked).status,403,"exact grant revocation committed while waiting must be reread under canonical lock");await control("return-owner-restore");
            pass("revocation under held SQL line lock refuses return after initial authorization");
        }
        const receipt=state.value.returns[0];
        const historyUrl=returnPath,history=state;
        assert.deepEqual((await post(page,historyUrl,{id:returnId,quantity:"1.000000"})).value,receipt,"normalized q6 replay returns immutable original actor date provenance");
        assert.equal((await post(page,historyUrl,{id:returnId,quantity:"0.1"})).status,409);
        for(const quantity of ["0","-1","1.0000001","1000000","1e0","NaN"," 1","1,0"])
            assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity})).status,400,quantity);
        assert.equal((await post(page,historyUrl,{id:"00000000-0000-0000-0000-000000000000",quantity:"1"})).status,400);
        assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity:"1",tenantId:ctx.tenantId})).status,400,"tenant is server-owned and unknown payload fields rejected");
        assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity:"2"})).status,409);
        await control("capability-off");
        assert.equal((await get(page,historyUrl)).value.canReturn,false);
        assert.deepEqual((await post(page,historyUrl,{id:returnId,quantity:"1"})).value,receipt,"accepted receipt replay survives capability off");
        assert.equal((await post(page,historyUrl,{id:crypto.randomUUID(),quantity:"1"})).status,403);
        await control("capability-on");
        const csrfDenied=await page.evaluate(async ({historyUrl})=>(await fetch(historyUrl,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:crypto.randomUUID(),quantity:"1"})})).status,{historyUrl});
        assert.equal(csrfDenied,400);
        const anonymous=await browser.newPage();await anonymous.goto(origin+"/");assert.equal((await get(anonymous,historyUrl)).status,401);await anonymous.close();
        const reader=await browser.newPage();await reader.goto(origin+"/");await reader.getByRole("button",{name:"Accedi",exact:true}).click();
        await reader.locator("#username").fill(fixture.users[5].username);await reader.locator("#password").fill(fixture.users[5].password);
        await Promise.all([reader.waitForURL(u=>u.hostname==="app.r00.test"),reader.locator("#kc-login").click()]);
        for(const scope of ["read","common","site","warehouse"]){await control("target-return-scope:"+scope);assert.equal((await get(reader,historyUrl)).value.canReturn,false);assert.equal((await post(reader,historyUrl,{id:crypto.randomUUID(),quantity:"0.1"})).status,403,scope);assert.equal((await post(reader,historyUrl,{id:returnId,quantity:"1"})).status,403,"historical replay still requires exact current action: "+scope);}
        await control("target-return-scope:exact");assert.equal((await get(reader,historyUrl)).value.canReturn,true);assert.deepEqual((await post(reader,historyUrl,{id:returnId,quantity:"1.000000"})).value,receipt,"another authorized membership replays original actor/membership/time, never reattributes receipt");
        for(const axis of ["company","site","warehouse"]){
            await control("target-return:"+axis);
            const h=await get(reader,historyUrl);
            assert.equal(h.status,200,"read stays available with wrong "+axis);assert.equal(h.value.canReturn,false,"wrong "+axis);
            assert.equal((await post(reader,historyUrl,{id:crypto.randomUUID(),quantity:"0.1"})).status,403,"return grant on wrong "+axis+" alone must not authorize");
        }
        await control("target-return-scope:revoke");assert.equal((await post(reader,historyUrl,{id:crypto.randomUUID(),quantity:"0.1"})).status,403);
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
            controlled4xx((await post(page,base+`/reservations/${crypto.randomUUID()}/returns`,{id:crypto.randomUUID(),quantity:"1"})).status,"unknown reservation");
            assert.deepEqual((await get(page,historyUrl)).value,beforeHistory,"rejected inputs leave no partial release row");
            assert.deepEqual((await get(page,stateUrl)).value,beforeStock,"rejected inputs leave stock and reservation state unchanged");
        }
        pass("strict q6/input UUID/payload replay, capability-off history/receipt, CSRF, exact independent read/common/site/warehouse scopes and revocation");
        assert.equal((await post(page,returnPath,{id:crypto.randomUUID(),quantity:"0.1",warehouseId:fixture.deniedContexts[2].warehouseId})).status,400,"actual attempt to supply a different destination strictly refused");
        const installPath=`/api/v1/workshop/orders/${order}/lines/${lines[0]}/picks/${pickId}/installations`;
        assert.equal((await post(page,installPath,{id:crypto.randomUUID(),quantity:"2"})).status,409,"returned quota cannot be installed from original pick");
        assert.equal((await get(page,installPath)).value.remainingToInstall,"1","installation advisory subtracts returned quota");
        pass("returned quota excluded from installation allowance authoritative GET and command");
        await control("consume-fault-on");
        const pendingId=crypto.randomUUID(),pendingBody={id:pendingId,quantity:"0.5"};
        const pending=await post(page,installPath,pendingBody);assert.equal(pending.status,202);assert.equal(pending.value.stockEffect,"Pending");
        assert.equal((await post(page,returnPath,{id:crypto.randomUUID(),quantity:"0.1"})).status,409,"ANY persisted installation including Pending forbids further return from selected pick, not just consumed quota");
        assert.equal((await get(page,returnPath)).value.canReturn,false,"Pending installation return advisory must refuse");
        assert.equal((await get(page,returnPath)).value.remainingWithTechnician,"0.5","current technician remainder excludes persisted installation even Pending");
        await control(`verify-return-pending:${pickId}`);
        await control("consume-fault-off");
        const recovered=await post(page,installPath,pendingBody);assert.equal(recovered.status,200);assert.equal(recovered.value.stockEffect,"Consumed");
        assert.equal((await post(page,returnPath,{id:crypto.randomUUID(),quantity:"0.1"})).status,409,"partly installed pick is outside bounded D81 even with uninstalled remainder");
        pass("remaining picked quota may install; Pending and Consumed persisted facts both prohibit any subsequent return");
        assert.equal((await get(page,pickPath)).value.remainingToPick,"0","return must never reopen original reservation historical picked quota");
        assert.equal((await post(page,pickPath,{id:crypto.randomUUID(),quantity:"0.000001"})).status,409);
        assert.equal((await post(page,base+`/reservations/${reservationId}/releases`,{id:crypto.randomUUID(),quantity:"0.1"})).status,409,"D80 remains never-picked only after return");
        const freshReservation=crypto.randomUUID();
        assert.equal((await post(page,base+"/reservations",{id:freshReservation,warehouseId:ctx.warehouseId,quantity:"1",catalogVersion:8})).status,201,"returned pool commitment is re-reservable only through NEW reservation");
        const secondWarehouse=fixture.deniedContexts.find(c=>c.legalEntityId===ctx.legalEntityId && c.siteId===ctx.siteId).warehouseId;
        assert.equal((await post(page,base+"/reservations",{id:crypto.randomUUID(),warehouseId:secondWarehouse,quantity:"1",catalogVersion:8})).status,201,"returned quota restores cross-warehouse cumulative line capacity");
        assert.equal((await post(page,base+"/reservations",{id:crypto.randomUUID(),warehouseId:secondWarehouse,quantity:"0.000001",catalogVersion:8})).status,409,"consumption never restores cumulative reservable capacity");
        pass("return compensation coherently restores shared pool and cumulative cross-warehouse reserve but not original picking/D80 or consumption capacity");
        assert.equal((await post(page,base+`/reservations/${freshReservation}/releases`,{id:crypto.randomUUID(),quantity:"1"})).status,201);
        const freeBase=`/api/v1/inventory/orders/${order}/lines/${lines[1]}`, freeRes=crypto.randomUUID(),freePick=crypto.randomUUID();
        assert.equal((await post(page,freeBase+"/reservations",{id:freeRes,warehouseId:ctx.warehouseId,quantity:"1",catalogVersion:8})).status,201);
        assert.equal((await post(page,freeBase+`/reservations/${freeRes}/picks`,{id:freePick,quantity:"1"})).status,201);
        const freePath=freeBase+`/reservations/${freeRes}/picks/${freePick}/new-part-returns`, freeReturn=crypto.randomUUID();
        assert.equal((await post(page,freePath,{id:freeReturn,quantity:"0.5"})).status,201);
        async function editFree(type,fields={}){return post(page,`/api/v1/workshop/orders/${order}/editor/commands`,{type,commandId:crypto.randomUUID(),expectedRevision:revision,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,lineId:lines[1],...fields});}
        assert.equal((await editFree("RemoveLine")).status,409,"partially returned pick remains fenced");
        await page.goto(origin+"/ui01-runtime.html#order="+order);
        await page.getByLabel("Workspace commessa").waitFor();
        await page.getByText("Operazioni materiali",{exact:true}).click();
        const materialPanel=page.getByRole("region",{name:"Operazioni materiali"});
        await materialPanel.getByLabel("Riga ricambio").selectOption(lines[1]);
        await materialPanel.getByLabel("Magazzino materiali").selectOption(ctx.warehouseId);
        await materialPanel.getByLabel("Prenotazione da prelevare").selectOption(freeRes);
        const returnPanel=page.getByRole("region",{name:"Reso nuovo integro mai installato"});
        await returnPanel.getByLabel("Prelievo da restituire").selectOption(freePick,{timeout:5000});
        await returnPanel.getByText("Residuo presso operatore: 0.5").waitFor();
        {
            const panelsOpen=async()=>page.locator(".ui01-panels > details[open]").count();
            for(const name of ["Tempo effettivo mio","Chiusura e attesa amministrativa"]) await page.locator("summary",{hasText:name}).click();
            assert.equal(await panelsOpen(),3,"all three material panels expanded");
            const focused=(locator)=>locator.evaluate(e=>e===document.activeElement);
            const select=returnPanel.getByLabel("Prelievo da restituire"), input=returnPanel.getByLabel("Quantità da restituire");
            const submit=returnPanel.getByRole("button",{name:"Restituisci quantità esplicita",exact:true}), reread=returnPanel.getByRole("button",{name:"Rileggi resi",exact:true});
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
                await returnPanel.getByText("Quantità positiva con massimo 6 decimali.").waitFor();
                assert(await focused(input),"invalid quantity returns focus to the field at "+width);
                await page.screenshot({path:"/run/control/return-"+width+".png"});
            }
            await page.setViewportSize({width:1920,height:1080});
            for(const name of ["Tempo effettivo mio","Chiusura e attesa amministrativa"]) await page.locator("summary",{hasText:name}).click();
            assert.equal(await panelsOpen(),1);
            pass("real return panel keyboard order, error focus, three panels expanded, editor/sticky footer reachable at 1920x1080 and 1366x768");
        }
        const envelopes=[];let dropped=false;
        await page.route("**/reservations/"+freeRes+"/picks/"+freePick+"/new-part-returns",async route=>{
            if(route.request().method()!=="POST")return route.continue();
            envelopes.push({url:route.request().url(),body:route.request().postData()});
            if(!dropped){dropped=true;const accepted=await route.fetch();assert.equal(accepted.status(),201);return route.abort("connectionfailed");}return route.continue();
        });
        await returnPanel.getByLabel("Quantità da restituire").fill("0.5");
        await returnPanel.getByRole("button",{name:"Restituisci quantità esplicita",exact:true}).click();
        await returnPanel.getByText("Esito reso incerto: riprova solo il comando identico.").waitFor();
        for(const label of ["Riga ricambio","Magazzino materiali","Prenotazione da prelevare"])assert(await materialPanel.getByLabel(label).isDisabled(),"frozen ancestor "+label);
        assert(await returnPanel.getByLabel("Prelievo da restituire").isDisabled());
        assert(await page.getByLabel("UUID commessa",{exact:true}).isDisabled(),"unknown accepted return must freeze the owning order selector, not just material descendants");
        assert(await page.getByRole("button",{name:"Rileggi commessa",exact:true}).isDisabled());
        assert(await page.getByRole("button",{name:"Riprova sessione",exact:true}).isDisabled());
        assert(await page.getByLabel("Contesto elenco",{exact:true}).isDisabled());
        assert(await page.locator("#new-group-title").isDisabled(),"P2/editor commands cannot unmount a pending return");
        const materialSummary=page.locator("summary",{hasText:"Operazioni materiali"});await materialSummary.focus();await page.keyboard.press("Enter");
        assert(await materialSummary.evaluate(e=>e.parentElement.open),"pending return panel cannot be dismissed and lose its original envelope");
        for(const [width,height] of [[1920,1080],[1366,768]]){
            await page.setViewportSize({width,height});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),"pending root fence has no horizontal overflow at "+width);
            const retry=returnPanel.getByRole("button",{name:"Riprova reso identico"});await retry.scrollIntoViewIfNeeded();
            const box=await retry.boundingBox(),footer=await page.locator("footer").boundingBox();
            assert(box&&footer&&box.y>=0&&box.y+box.height<=footer.y+1&&footer.y+footer.height<=height+1,"pending retry and sticky footer reachable at "+width);
        }
        await page.setViewportSize({width:1920,height:1080});


        assert(await materialPanel.getByLabel("Prelievo da installare").isDisabled());
        await returnPanel.getByRole("button",{name:"Riprova reso identico"}).click();
        await returnPanel.getByText("Reso registrato e riletto; fisico e riga commerciale invariati.").waitFor();
        assert.equal(envelopes.length,2);assert.deepEqual(envelopes[0],envelopes[1],"lost accepted response retries byte-identical URL UUID/payload");
        await page.waitForFunction(()=>document.querySelector(".ui01-workspace > form input")?.disabled===false);
        assert(!(await page.getByLabel("Contesto elenco",{exact:true}).isDisabled()),"resolved receipt releases context fence");
        assert(!(await page.locator("#new-group-title").isDisabled()),"editor reenabled after immutable retry and authoritative readback");

        const uiReturnId=JSON.parse(envelopes[0].body).id;
        assert.equal((await get(page,freePath)).value.returns.filter(x=>x.id===uiReturnId).length,1);
        pass("actual browser accepted-response loss freezes child and every ancestor, byte-identical retry, authoritative GET one immutable effect");
        pass("Italian reservation/pick-specific actual browser controls perform explicit partial return to original warehouse");
        assert.equal((await post(page,freePath,{id:crypto.randomUUID(),quantity:"0.000001"})).status,409,"fully returned pick cannot be returned again");
        assert.equal((await post(page,freeBase+`/reservations/${freeRes}/releases`,{id:crypto.randomUUID(),quantity:"0.000001"})).status,409,"full return never requalifies historical picking for D80 release");
        const corrected=await editFree("EditCommercialLine",{quantity:"2",groupId:groups[1],catalogItemId:data.partId,catalogVersion:8});
        assert.equal(corrected.status,200,"fully returned material without other active effects permits P2 structural correction: "+JSON.stringify(corrected));revision=corrected.value.appliedRevision;
        const protect=crypto.randomUUID();assert.equal((await post(page,freeBase+"/reservations",{id:protect,warehouseId:ctx.warehouseId,quantity:"0.5",catalogVersion:8})).status,201);
        assert.equal((await editFree("RemoveLine")).status,409,"fresh reserve restores P2 fence");
        assert.equal((await post(page,freeBase+`/reservations/${protect}/releases`,{id:crypto.randomUUID(),quantity:"0.5"})).status,201);
        const removed=await editFree("RemoveLine");assert.equal(removed.status,200);revision=removed.value.appliedRevision;
        assert.equal((await get(page,freePath)).value.returns.length,2,"P2 tombstone preserves new return history");
        const freeReceipt=(await get(page,freePath)).value.returns.find(r=>r.id===freeReturn);
        assert.deepEqual((await post(page,freePath,{id:freeReturn,quantity:"0.500000"})).value,freeReceipt,"old UUID immutable after full return and P2 removal");
        assert.equal((await post(page,freePath,{id:freeReturn,quantity:"0.4"})).status,409);
        assert.equal((await post(page,returnPath,{id:freeReturn,quantity:"0.5"})).status,409,"old UUID cannot retarget another pick");
        pass("partial return fences P2; full compensation permits structure/remove with preserved history; NEW reserve reprotects; old UUID receipt remains immutable after removal");
        {
            const ao=crypto.randomUUID(),al=crypto.randomUUID(),ag=crypto.randomUUID(),ar=crypto.randomUUID(),ap=crypto.randomUUID(),ax=crypto.randomUUID();
            await control(`authority-return-seed:${ao}:${al}:${ag}:${ar}:${ap}:${ax}`);
            const authorityPath=`/api/v1/inventory/orders/${ao}/lines/${al}/reservations/${ar}/picks/${ap}/new-part-returns`;
            for(const mode of ["missing","external"]){
                if(mode==="external")await control("authority-external");
                const history=await get(page,authorityPath);assert.equal(history.status,200);assert.equal(history.value.canReturn,false);assert.equal(history.value.returned,"0.25");assert.equal(history.value.returns.length,1);
                const refused=await post(page,authorityPath,{id:crypto.randomUUID(),quantity:"0.1"});assert.equal(refused.status,409);assert.equal(refused.value.code,"stock_profile_"+mode);
                assert.deepEqual((await post(page,authorityPath,{id:ax,quantity:"0.250000"})).value,history.value.returns[0],"accepted history replay with "+mode+" authority");
                assert.deepEqual((await get(page,authorityPath)).value,history.value,"refused local write leaves no partial return");
            }
            pass("missing/external stock authority refuses new returns without blocking authorized history or exact immutable replay");
        }
        if(process.env.RELEASE_POOL==="4") {
            async function fresh({lineQuantity="1",quantity="1",pick=true}={}) {
                await control("race-stock");
                const o=crypto.randomUUID(),g=crypto.randomUUID(),l=crypto.randomUUID(),r=crypto.randomUUID(),p=crypto.randomUUID();
                assert.equal((await post(page,"/api/v1/workshop/orders",{id:o,legalEntityId:ctx.legalEntityId,siteId:ctx.siteId,documentTypeId:data.documentTypeId,configurationVersion:7,payerId:data.payerId,vehicleId:data.vehicleId})).status,201);
                const cp=`/api/v1/workshop/orders/${o}/editor/commands`;
                for(const [type,rev,fields] of [["AddGroup",0,{groupId:g,title:"SYNTHETIC D81 barrier"}],["AddCommercialLine",1,{groupId:g,lineId:l,catalogItemId:data.partId,catalogVersion:8,quantity:lineQuantity,unitPrice:"1",discountPercent:"0"}]])
                    assert.equal((await post(page,cp,{type,commandId:crypto.randomUUID(),expectedRevision:rev,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,...fields})).status,201);
                const b=`/api/v1/inventory/orders/${o}/lines/${l}`;
                if(quantity!=="0")assert.equal((await post(page,b+"/reservations",{id:r,warehouseId:ctx.warehouseId,quantity,catalogVersion:8})).status,201);
                if(pick) assert.equal((await post(page,b+`/reservations/${r}/picks`,{id:p,quantity})).status,201);
                return {o,g,l,r,p,b,cp,rp:b+`/reservations/${r}/picks/${p}/new-part-returns`,ip:`/api/v1/workshop/orders/${o}/lines/${l}/picks/${p}/installations`};
            }
            async function ordered(f,a,b,lock="order") {
                await control(lock==="stock"?"hold-stock":"hold-order:"+f.o);
                const first=a();await control("wait-lock:1");const second=b();await control("wait-lock:2");await control("release-lock");
                return [await first,await second];
            }
            const statuses=r=>r.map(x=>x.status);
            const ret=(f,q="1",id=crypto.randomUUID())=>()=>post(page,f.rp,{id,quantity:q});
            const install=(f,q="1")=>()=>post(page,f.ip,{id:crypto.randomUUID(),quantity:q});
            for(const reverse of [false,true]) {
                const f=await fresh();const a=ret(f),b=ret(f);assert.deepEqual(statuses(await ordered(f,reverse?b:a,reverse?a:b)),[201,409],"distinct return IDs serialized, both arrival orders");
                const same=await fresh(),id=crypto.randomUUID();const results=await ordered(same,ret(same,"1",id),ret(same,"1.000000",id));assert.deepEqual(statuses(results),[201,200]);assert.deepEqual(results[0].value,results[1].value,"same UUID returns same immutable receipt");
                const ri=await fresh();const rr=await ordered(ri,...(reverse?[install(ri,"0.5"),ret(ri,"0.5")]:[ret(ri,"0.5"),install(ri)]));assert.deepEqual(statuses(rr),[201,409],"return/install both orderings cannot install returned or return installed quota");
                await control("consume-fault-on");const pi=await fresh();
                const pr=await ordered(pi,...(reverse?[install(pi,"0.5"),ret(pi,"0.5")]:[ret(pi,"0.5"),install(pi,"0.5")]));
                assert.deepEqual(statuses(pr),reverse?[202,409]:[201,202],"Pending fact fences later return; remaining unreturned quota may become Pending");await control("consume-fault-off");
                const release=await fresh();const rel=()=>post(page,release.b+`/reservations/${release.r}/releases`,{id:crypto.randomUUID(),quantity:"1"});
                assert.deepEqual(statuses(await ordered(release,...(reverse?[rel,ret(release)]:[ret(release),rel]))),reverse?[409,201]:[201,409],"D80 never broadens after picked return");
                const reserve=await fresh();const res=()=>post(page,reserve.b+"/reservations",{id:crypto.randomUUID(),warehouseId:ctx.warehouseId,quantity:"1",catalogVersion:8});
                assert.deepEqual(statuses(await ordered(reserve,...(reverse?[res,ret(reserve)]:[ret(reserve),res]))),reverse?[409,201]:[201,201],"return/reserve rereads cumulative capacity after canonical lock");
                for(const structural of ["RemoveLine","EditCommercialLine"]) {
                    const edit=await fresh();const change=()=>post(page,edit.cp,{type:structural,commandId:crypto.randomUUID(),expectedRevision:2,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,lineId:edit.l,...(structural==="EditCommercialLine"?{quantity:"2"}:{})});
                    assert.deepEqual(statuses(await ordered(edit,...(reverse?[change,ret(edit)]:[ret(edit),change]))),reverse?[409,201]:[201,200],"full return/"+structural+" both serializations");
                }
                const closure=await fresh();const close=()=>post(page,`/api/v1/workshop/orders/${closure.o}/technical-closure`,{id:crypto.randomUUID(),expectedRevision:2});
                assert.deepEqual(statuses(await ordered(closure,...(reverse?[close,ret(closure)]:[ret(closure),close]))),reverse?[201,409]:[201,201],"return/technical closure both serializations");
                if(reverse) await control(`verify-return-closed:${closure.p}`);
                const shared=await fresh(),other=await fresh({quantity:"0",pick:false});
                await control("tight-stock:0");
                const otherReserve=()=>post(page,other.b+"/reservations",{id:crypto.randomUUID(),warehouseId:ctx.warehouseId,quantity:"1",catalogVersion:8});
                assert.deepEqual(statuses(await ordered(shared,...(reverse?[otherReserve,ret(shared)]:[ret(shared),otherReserve]),"stock")),reverse?[409,201]:[201,201],"shared physical stock pool across OTHER orders, both arrivals");
            }
            {
                const readCase=await fresh({lineQuantity:"2",quantity:"2"});
                await control("hold-return-read");const inFlight=get(page,readCase.ip);await control("wait-lock:1");
                assert.equal((await ret(readCase,"1")()).status,201);assert.equal((await install(readCase,"1")()).status,201);
                await control("release-lock");const projected=await inFlight;assert.equal(projected.status,200);
                assert([["0","2"],["1","0"]].some(([installed,remaining])=>projected.value.installed===installed&&projected.value.remainingToInstall===remaining),"installation GET must not mix an old returned quota with later installations: "+JSON.stringify(projected));
                await control("restore-return-read");
                pass("owning installation GET uses one coherent snapshot while return and installation commit between its source queries");
            }
            pass("real separate physical SQL barriers BOTH serializations return/return/sameUUID/install+Pending/release/reserve/shared-pool-other-order/P2/remove/technicalclosure");
        }
        await control("race-stock");
        const downstreamRes=crypto.randomUUID(),downstreamPick=crypto.randomUUID(),downstreamInstall=crypto.randomUUID();
        assert.equal((await post(page,base+"/reservations",{id:downstreamRes,warehouseId:ctx.warehouseId,quantity:"1",catalogVersion:8})).status,201);
        assert.equal((await post(page,base+`/reservations/${downstreamRes}/picks`,{id:downstreamPick,quantity:"1"})).status,201);
        const downstreamPath=`/api/v1/workshop/orders/${order}/lines/${lines[0]}/picks/${downstreamPick}/installations`,downstreamBody={id:downstreamInstall,quantity:"1"};
        const dInstall=await post(page,downstreamPath,downstreamBody);assert.equal(dInstall.status,201);assert.equal(dInstall.value.stockEffect,"Consumed");assert.deepEqual((await post(page,downstreamPath,downstreamBody)).value,dInstall.value);
        const carcassId=crypto.randomUUID(),carcassBody={id:carcassId,warehouseId:ctx.warehouseId,quantity:"1.5",description:"SYNTHETIC carcass distinct from intact new-part return"};
        const carcass=await post(page,base+"/carcass-returns",carcassBody);assert.equal(carcass.status,201,JSON.stringify(carcass));assert.deepEqual((await post(page,base+"/carcass-returns",carcassBody)).value,carcass.value);
        const editor=(await get(page,`/api/v1/workshop/orders/${order}/editor`)).value;
        assert.equal(editor.summary.netAmount,"3.000000");assert.equal(editor.summary.taxAmount,"0.660000");assert.equal(editor.summary.total,"3.660000");
        const closureBody={id:crypto.randomUUID(),expectedRevision:editor.revision};
        const closed=await post(page,`/api/v1/workshop/orders/${order}/technical-closure`,closureBody);assert.equal(closed.status,201,JSON.stringify(closed));
        assert.deepEqual((await post(page,returnPath,{id:returnId,quantity:"1"})).value,receipt,"old exact return receipt replays after closure despite persisted installations");
        assert.equal((await post(page,returnPath,{id:crypto.randomUUID(),quantity:"0.1"})).status,409);
        const invoiceId=crypto.randomUUID(),invoiceBody={id:invoiceId,orderId:order,documentTypeId:data.invoiceTypeId,configurationVersion:6,documentDate:"2026-10-24",currency:"EUR",reference:"SYNTHETIC-R04C2"};
        const invoice=await post(page,"/api/v1/billing/workshop-invoices",invoiceBody);assert.equal(invoice.status,201,JSON.stringify(invoice));assert.deepEqual(invoice.value.summary,editor.summary);assert.deepEqual((await post(page,"/api/v1/billing/workshop-invoices",invoiceBody)).value,invoice.value);
        const confirmationBody={id:crypto.randomUUID(),configurationVersion:6},confirmationPath=`/api/v1/billing/workshop-invoices/${invoiceId}/confirmation`;
        const confirmed=await post(page,confirmationPath,confirmationBody);assert.equal(confirmed.status,201);assert.deepEqual((await post(page,confirmationPath,confirmationBody)).value,confirmed.value);
        const journalId=crypto.randomUUID(),journalBody={id:journalId,invoiceId,chartVersion:5};
        const journal=await post(page,"/api/v1/accounting/invoice-journal-entries",journalBody);assert.equal(journal.status,201);assert.equal(journal.value.balanced,true);assert.equal(journal.value.totalDebit,"3.660000");assert.equal(journal.value.totalCredit,"3.660000");assert.equal(journal.value.difference,"0.000000");assert.deepEqual((await post(page,"/api/v1/accounting/invoice-journal-entries",journalBody)).value,journal.value);
        pass("returned then NEW reserve pick install carcass technicalclosure internal Billing Accounting balanced q6/idempotent unchanged commercial snapshot");
        const foreign=await browser.newPage();await foreign.goto(origin+"/");await foreign.getByRole("button",{name:"Accedi",exact:true}).click();
        await foreign.locator("#username").fill(fixture.users[1].username);await foreign.locator("#password").fill(fixture.users[1].password);
        await Promise.all([foreign.waitForURL(u=>u.hostname==="app.r00.test"),foreign.locator("#kc-login").click()]);
        assert.equal((await get(foreign,returnPath)).status,404);assert.equal((await post(foreign,returnPath,{id:crypto.randomUUID(),quantity:"1"})).status,404);
        const fc=fixture.contexts[1],fd=fixture.workshop[1],fo=crypto.randomUUID(),fg=crypto.randomUUID(),fl=crypto.randomUUID();
        await control("external-local-setup");
        assert.equal((await post(foreign,"/api/v1/workshop/orders",{id:fo,legalEntityId:fc.legalEntityId,siteId:fc.siteId,documentTypeId:fd.documentTypeId,configurationVersion:7,payerId:fd.payerId,vehicleId:fd.vehicleId})).status,201);
        async function fcmd(type,rev,fields){const r=await post(foreign,`/api/v1/workshop/orders/${fo}/editor/commands`,{type,commandId:crypto.randomUUID(),expectedRevision:rev,expectedLinePolicyVersion:9,expectedStructurePolicyVersion:1,...fields});assert.equal(r.status,201,JSON.stringify(r));}
        await fcmd("AddGroup",0,{groupId:fg,title:"SYNTHETIC external return source"});
        await fcmd("AddCommercialLine",1,{groupId:fg,lineId:fl,catalogItemId:fd.partId,catalogVersion:8,quantity:"2",unitPrice:"1.123456",discountPercent:"0"});
        const fr=crypto.randomUUID(), fbase=`/api/v1/inventory/orders/${fo}/lines/${fl}`;
        assert.equal((await post(foreign,fbase+"/reservations",{id:fr,warehouseId:fc.warehouseId,quantity:"2",catalogVersion:8})).status,201);
        const originalForeignPick=crypto.randomUUID();assert.equal((await post(foreign,fbase+`/reservations/${fr}/picks`,{id:originalForeignPick,quantity:"2"})).status,201);
        const fpath=fbase+`/reservations/${fr}/picks/${originalForeignPick}/new-part-returns`;
        assert.equal((await post(foreign,fpath,{id:returnId,quantity:"1"})).status,409,"RLS-hidden UUID collision is controlled without exposing foreign receipt");
        assert.equal((await get(foreign,fpath)).value.returns.length,0);
        assert.equal((await post(foreign,fpath,{id:crypto.randomUUID(),quantity:"1"})).status,201);
        const fre=crypto.randomUUID();assert.equal((await post(foreign,fbase+"/reservations",{id:fre,warehouseId:fc.warehouseId,quantity:"1",catalogVersion:8})).status,201);
        const fp=crypto.randomUUID();assert.equal((await post(foreign,fbase+`/reservations/${fre}/picks`,{id:fp,quantity:"1"})).status,201);
        const fi=crypto.randomUUID();assert.equal((await post(foreign,`/api/v1/workshop/orders/${fo}/lines/${fl}/picks/${fp}/installations`,{id:fi,quantity:"1"})).value.stockEffect,"Consumed");
        assert.equal((await post(foreign,fbase+"/carcass-returns",{id:crypto.randomUUID(),warehouseId:fc.warehouseId,quantity:"1",description:"SYNTHETIC external carcass distinct from intact return"})).status,201);
        const fsnapshot=(await get(foreign,`/api/v1/workshop/orders/${fo}/editor`)).value.summary;
        assert.equal((await post(foreign,`/api/v1/workshop/orders/${fo}/technical-closure`,{id:crypto.randomUUID(),expectedRevision:2})).status,201);
        const externalId=crypto.randomUUID(),externalBody={id:externalId,expectedRevision:2};
        assert.equal((await post(foreign,`/api/v1/workshop/orders/${fo}/administrative-requests`,externalBody)).status,201);
        assert.equal((await post(foreign,`/api/v1/workshop/orders/${fo}/administrative-requests`,externalBody)).status,200);
        let externalState;
        for(let i=0;i<100;i++){externalState=(await get(foreign,`/api/v1/workshop/orders/${fo}/administrative-requests`)).value;if(JSON.stringify(externalState).includes('Completed'))break;await new Promise(r=>setTimeout(r,100));}
        assert(JSON.stringify(externalState).includes('Completed'),"actual isolated simulator must acknowledge pinned administrative snapshot after new-part return flow");
        pass("cross-tenant invisibility/RLS-hidden UUID collision, external return consumer and actual simulator pinned snapshot");
        for(let i=0;i<12;i++){
            const [own,other]=await Promise.all([get(page,returnPath),get(foreign,returnPath)]);
            assert.equal(own.status,200);assert.equal(other.status,404,"pooled tenant context must never leak across authenticated readers");
        }
        assert.equal(await page.evaluate(()=>localStorage.length),0,"return state never persists in localStorage");
        await foreign.close();
        for(const rev of [2147483647,2147483648,9223372036854775807n,-1]){
            controlled4xx((await rawPost(page,`/api/v1/workshop/orders/${order}/editor/commands`,'{"type":"AddGroup","commandId":"'+crypto.randomUUID()+'","expectedRevision":'+rev+',"expectedLinePolicyVersion":9,"expectedStructurePolicyVersion":1,"groupId":"'+crypto.randomUUID()+'","title":"SYNTHETIC overflow"}',"application/json")).status,"max revision "+rev);
        }
        assert.equal((await get(page,`/api/v1/workshop/orders/${order}/editor`)).value.revision,revision);
        await page.goto(origin+"/ui01-runtime.html#order="+order);await page.reload();await page.getByLabel("Workspace commessa").waitFor();
        if(await page.getByRole("region",{name:"Operazioni materiali"}).count()===0) await page.getByText("Operazioni materiali",{exact:true}).click();
        const finalMaterials=page.getByRole("region",{name:"Operazioni materiali"});
        await finalMaterials.getByLabel("Riga ricambio").selectOption(lines[0]);await finalMaterials.getByLabel("Magazzino materiali").selectOption(ctx.warehouseId);
        await finalMaterials.getByLabel("Prenotazione da prelevare").selectOption(reservationId);
        const finalReturn=page.getByRole("region",{name:"Reso nuovo integro mai installato"});await finalReturn.getByLabel("Prelievo da restituire").selectOption(pickId);
        await finalReturn.getByText("Residuo presso operatore: 0.5").waitFor();
        await control("binding-revoke");await finalReturn.getByRole("button",{name:"Rileggi resi"}).click();
        await page.getByText("Sessione terminata. Accedi nuovamente.",{exact:true}).waitFor();
        assert.equal(await page.getByLabel("Workspace commessa").count(),0,"401 clears order/editor/material/return state rather than retargeting another identity");
        pass("pool1+4 authenticated tenant context reset, revision overflow/no writes, no localStorage and actual identity revocation 401 clears complete UI");

        fs.writeFileSync("/run/control/result.json",JSON.stringify({order,groups,lines,reservationId,pickId,returnId,downstreamRes,downstreamPick,downstreamInstall,pendingId,carcassId,invoiceId,journalId,externalId,fo,fsnapshot,revision,checks}));
    } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
