import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { CatalogWorkspace } from "../components/catalog-workspace";
import { catalogReadPath, finiteCatalogRead, type CatalogData, type CatalogKind } from "../lib/catalog";
const id="aaaaaaaa-0000-0000-0000-000000000001";
const data: CatalogData={state:"ready",tenantId:id,authority:{state:"local",version:1},canCreate:true,canEdit:true,items:[],detail:null};
test("anonymous disabled pending and unavailable SSR do not serialize catalog data",()=>{
 for(const status of [401,403,503]) {
  const html=renderToStaticMarkup(<CatalogWorkspace initial={{status,data:null,query:{}}}/>);
  assert.match(html,/Articoli e servizi/);assert.doesNotMatch(html,/Salva identità|Synthetic/);
 }
});
test("both typed identities render actual read detail and revisioned editor, no invented business fields",()=>{
 for(const kind of ["Article","Service"] as CatalogKind[]) {
  const detail={id,kind,label:"Synthetic "+kind,revision:7};
  const html=renderToStaticMarkup(<CatalogWorkspace initial={{status:200,data:{...data,items:[detail],detail},query:{id}}}/>);
  assert.match(html,/Synthetic/);assert.match(html,/Salva identità catalogo/);assert.match(html,/disponibili senza JavaScript/);
  assert.doesNotMatch(html,/name="(?:unitPrice|cost|taxRate|warehouseId|vehicleId|code)"/);
  assert.doesNotMatch(html,/maxLength|name="tenantId"/);assert.match(html,/Revisione condivisa/);
 }
});
test("SSR mutation controls stay disabled until hydration while native search remains available",()=>{
 const detail={id,kind:"Article" as const,label:"Synthetic hydration boundary",revision:1};
 const html=renderToStaticMarkup(<CatalogWorkspace initial={{status:200,data:{...data,items:[detail],detail},query:{id}}}/>);
 assert.match(html,/<button[^>]*disabled=""[^>]*>Nuovo articolo o servizio<\/button>/);
 assert.match(html,/<form class="catalog-command"[^>]*><fieldset disabled=""/);
 assert.match(html,/<form[^>]*method="get"[^>]*><fieldset>/);
});
test("missing or external authority keeps reads but disables mutation controls",()=>{
 for(const state of ["external","missing"]) {
  const detail={id,kind:"Article" as const,label:"External synthetic",revision:1};
  const html=renderToStaticMarkup(<CatalogWorkspace initial={{status:200,data:{...data,authority:{state,version:1},items:[detail],detail},query:{id}}}/>);
  assert.match(html,/External synthetic/);assert.match(html,/<fieldset disabled=""/);
 }
});
test("finite catalog paths preserve encoded search and refuse unknown traversal duplicate keys and noncanonical values",()=>{
 assert.equal(finiteCatalogRead(catalogReadPath({id,search:"Società & figli",kind:"Article"})),true);
 for(const path of ["/api/v1/catalog/management/commands","/api/v1/catalog/management?tenant="+id,"/api/v1/catalog/management?id="+id+"&id="+id,"/api/v1/catalog/management?id="+id.toUpperCase(),"/api/v1/catalog/management?search=%00","/api/v1/catalog/management?kind=Part","/api/v1/catalog/management?kind=Article&kind=Service"])
  assert.equal(finiteCatalogRead(path),false,path);
});
test("real server transport supplies only current cookie fixed Host and no-store for catalog",async()=>{
 const {privateRead}=await import("../lib/private-backend");
 const reply=await privateRead(catalogReadPath({id}),"synthetic-cookie",async(url,init)=>{
  assert.equal(String(url),"https://backend.test"+catalogReadPath({id}));assert.deepEqual(init?.headers,{Cookie:"synthetic-cookie",Host:"public.test"});assert.equal(init?.cache,"no-store");return Response.json(data);
 },{origin:"https://backend.test",host:"public.test"});assert.equal(reply.status,200);
});
