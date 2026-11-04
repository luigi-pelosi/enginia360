import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { OnboardingAdministration, PendingOnboardingWorkspace } from "../components/onboarding-workspace";
import { privateRead } from "../lib/private-backend";
const id="aaaaaaaa-0000-0000-0000-000000000001";
test("pending SSR displays only own status and never protected approval directory",()=>{
  const html=renderToStaticMarkup(<PendingOnboardingWorkspace status={200} invitation={null} initial={{requestId:id,tenantId:id,expiresAt:"2026-11-03T12:00:00Z",revision:1,approved:false}}/>);
  assert.match(html,/In attesa di approvazione/);assert.match(html,new RegExp(id));assert.doesNotMatch(html,/Soggetto opaco verificato|Crea invito privato|Approva associazione/);
});
test("approved SSR describes distinct disabled state and explicit reauthentication without implicit grant",()=>{
  const html=renderToStaticMarkup(<PendingOnboardingWorkspace status={200} invitation={null} initial={{requestId:id,tenantId:id,expiresAt:"2026-11-03T12:00:00Z",revision:2,approved:true}}/>);
  assert.match(html,/accesso disabilitato e senza ruoli o deleghe/);assert.match(html,/Accedi dopo l’approvazione/);
});
test("delegate SSR exposes exact current request, not a customer directory or role grant",()=>{
  const html=renderToStaticMarkup(<OnboardingAdministration initial={{status:200,tenants:[],data:{state:"ok",mode:"delegate",tenantId:id,invitations:[],requests:[{requestId:id,invitationId:id,revision:1,issuer:"https://issuer.test",subject:"opaque<&subject",expiresAt:"2026-11-03T12:00:00Z",approved:false,available:true,membershipId:null,internalIdentityId:null}]}}}/>);
  assert.match(html,/Soggetto opaco verificato/);assert.match(html,/opaque&lt;&amp;subject/);assert.match(html,/senza abilitare o assegnare ruoli/);assert.doesNotMatch(html,/Tenant destinatario|Concedi gestione utenti/);
});
test("anonymous SSR cannot initiate without an invitation or see approvals",()=>{
 const html=renderToStaticMarkup(<PendingOnboardingWorkspace status={401} invitation={null} initial={null}/>);
 assert.match(html,/Non è disponibile un elenco pubblico dei clienti/);assert.doesNotMatch(html,/Autenticati per richiedere accesso|Approva associazione/);
});
test("finite SSR pending forwarding preserves only incoming cookie and private TLS/no-store",async()=>{
 for(const path of ["/auth/onboarding/status","/api/v1/platform/tenant-roles/onboarding/workspace","/api/v1/platform/tenant-roles/"+id+"/onboarding"]){
  const get:typeof fetch=async(url,init)=>{assert.equal(String(url),"https://backend.test"+path);assert.deepEqual(init?.headers,{Cookie:"pending-cookie",Host:"public.test"});assert.equal(init?.cache,"no-store");return Response.json({state:"ok"})};
  assert.equal((await privateRead(path,"pending-cookie",get,{origin:"https://backend.test",host:"public.test"})).status,200);
 }
 for(const path of ["/auth/onboarding/status?tenant="+id,"/auth/onboarding/unknown","/api/v1/platform/tenant-roles/"+id+"/onboarding/unknown"])
  await assert.rejects(privateRead(path,""),/Nonfinite backend read/);
});
