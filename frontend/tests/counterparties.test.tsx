import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { CounterpartyWorkspace } from "../components/counterparty-workspace";
import { counterpartyReadPath, finiteCounterpartyRead, type CounterpartyData } from "../lib/counterparties";
const id="aaaaaaaa-0000-0000-0000-000000000001";
const data: CounterpartyData={state:"ready",tenantId:id,authority:{state:"local",version:1},canCreate:true,canEdit:true,canWriteRoles:true,companies:[],items:[],detail:null};
test("anonymous and disabled SSR never serializes business fields or commands",()=>{
 for(const status of [401,403,503]){
  const html=renderToStaticMarkup(<CounterpartyWorkspace initial={{status,data:null,query:{}}}/>);
  assert.match(html,/Controparti e ruoli aziendali/);assert.doesNotMatch(html,/Salva dati comuni|Salva ruolo fornitore|Synthetic/);
 }
});
test("shared detail has actual editor and business role distinct from security roles without fiscal mandatory inputs",()=>{
 const detail={id,legalName:"Synthetic identity",fiscalIdentifier:"",registeredOffice:"",revision:7,isSupplier:true};
 const html=renderToStaticMarkup(<CounterpartyWorkspace initial={{status:200,data:{...data,items:[detail],detail},query:{id}}}/>);
 assert.match(html,/Synthetic identity/);assert.match(html,/Salva dati comuni/);assert.match(html,/Salva ruolo fornitore/);assert.match(html,/facoltativo/);assert.match(html,/disponibili senza JavaScript/);
 assert.doesNotMatch(html,/Partita IVA obbligatoria|VendorId|warehouseId|vehicleId/);
});
test("external and missing authority retain historical data but refuse enabled common commands",()=>{
 for(const state of ["external","missing"]){
  const detail={id,legalName:"External synthetic",fiscalIdentifier:"",registeredOffice:"",revision:0,isSupplier:false};
  const html=renderToStaticMarkup(<CounterpartyWorkspace initial={{status:200,data:{...data,authority:{state,version:1},items:[detail],detail},query:{id}}}/>);
  assert.match(html,/External synthetic/);assert.match(html,/<fieldset disabled=""/);
 }
});
test("finite read path rejects commands traversal noncanonical identifiers and foreign query keys",()=>{
 assert.equal(finiteCounterpartyRead(counterpartyReadPath({id,search:"Società & figli"})),true);
 for(const path of ["/api/v1/counterparties/management/commands","/api/v1/counterparties/management?tenant="+id,"/api/v1/counterparties/management?id="+id+"&id="+id,"/api/v1/counterparties/management?id="+id.toUpperCase(),"/api/v1/counterparties/management?search=%00"])
  assert.equal(finiteCounterpartyRead(path),false,path);
});
test("SSR forwards only current Cookie and fixed Host to private no-store management read",async()=>{
 const {privateRead}=await import("../lib/private-backend");
 const reply=await privateRead(counterpartyReadPath({id}),"synthetic-user",async(url,init)=>{
  assert.equal(String(url),"https://backend.test"+counterpartyReadPath({id}));assert.deepEqual(init?.headers,{Cookie:"synthetic-user",Host:"public.test"});assert.equal(init?.cache,"no-store");return Response.json(data);
 },{origin:"https://backend.test",host:"public.test"});assert.equal(reply.status,200);
});
