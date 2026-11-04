import React from "react";
import assert from "node:assert/strict";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { DocumentTypesWorkspace } from "../components/document-types-workspace";
import { documentTypesPath, documentTypesReadPath, finiteDocumentTypesRead, type DocumentTypesData, type QuantityEffect } from "../lib/document-types";
const id="aaaaaaaa-0000-0000-0000-000000000001";
const company="bbbbbbbb-0000-0000-0000-000000000001";
const data: DocumentTypesData={state:"ready",companies:[{id:company,name:"Synthetic company"}],selectedCompanyId:company,canCreate:true,canEdit:true,items:[],detail:null,history:[],selectedVersion:null};
test("anonymous revoked pending failure states do not serialize private type data",()=>{
 for(const status of [401,403,503]){
  const html=renderToStaticMarkup(<DocumentTypesWorkspace initial={{status,data:null,query:{}}}/>);
  assert.match(html,/Tipologie documentali/);assert.doesNotMatch(html,/Salva nuova versione|Synthetic/);
 }
});
test("company chooser is the actual minimal permission result, not a tenant UUID form",()=>{
 const html=renderToStaticMarkup(<DocumentTypesWorkspace initial={{status:200,data:{...data,selectedCompanyId:null},query:{}}}/>);
 assert.match(html,/Società autorizzata/);assert.match(html,/Synthetic company/);assert.doesNotMatch(html,/Nuova tipologia|name="tenantId"|name="companyId"/);
});
test("four effects and selected historical version render real component, current edit distinct",()=>{
 for(const effect of ["Load","Unload","Transfer","None"] as QuantityEffect[]){
  const selectedVersion={id,legalEntityId:company,label:"Historical "+effect,effect,revision:1,occurredAt:"2026-11-04T00:00:00Z"};
  const detail={...selectedVersion,label:"Current "+effect,revision:2,effect:"None" as const};
  const html=renderToStaticMarkup(<DocumentTypesWorkspace initial={{status:200,data:{...data,detail,selectedVersion,history:[detail,selectedVersion],items:[detail]},query:{legalEntityId:company,id,revision:"1"}}}/>);
  assert.match(html,/Historical/);assert.match(html,/Current/);assert.match(html,/Versione selezionata: 1/);assert.match(html,/Versione corrente/);assert.match(html,/Salva nuova versione/);
  assert.doesNotMatch(html,/maxLength|name="(?:formula|code|taxRate|price|tenantId|documentTypeId)"/);
 }
});
test("SSR mutation form disabled before hydration, native GET company/search available",()=>{
 const detail={id,legalEntityId:company,label:"Synthetic",effect:"None" as const,revision:1,occurredAt:"2026-11-04T00:00:00Z"};
 const html=renderToStaticMarkup(<DocumentTypesWorkspace initial={{status:200,data:{...data,detail,items:[detail],selectedVersion:detail},query:{legalEntityId:company,id}}}/>);
 assert.match(html,/<form class="document-type-command"[^>]*><fieldset disabled=""/);assert.match(html,/<button[^>]*disabled=""[^>]*>Nuova tipologia<\/button>/);assert.match(html,/<form[^>]*method="get"[^>]*><fieldset>/);
});
test("finite read paths preserve company and history and reject duplicate/untrusted keys",()=>{
 assert.equal(finiteDocumentTypesRead(documentTypesPath),true);
 assert.equal(finiteDocumentTypesRead(documentTypesReadPath({legalEntityId:company,id,revision:"1",search:"Società 😀 & figli"})),true);
 for(const suffix of ["?id="+id,"?legalEntityId=","?legalEntityId="+company+"&legalEntityId="+company,"?legalEntityId="+company+"&tenantId="+company,"?legalEntityId="+company+"&revision=1","?legalEntityId="+company+"&id="+id+"&revision=0","?legalEntityId="+company+"&id="+id+"&revision=2147483648","?legalEntityId="+company+"&search=%00","?legalEntityId="+company.toUpperCase()])assert.equal(finiteDocumentTypesRead(documentTypesPath+suffix),false,suffix);
 assert.equal(finiteDocumentTypesRead(documentTypesPath+"/commands"),false);
});
test("private SSR transport uses only incoming cookie fixed host no-store",async()=>{
 const {privateRead}=await import("../lib/private-backend");const path=documentTypesReadPath({legalEntityId:company,id,revision:"1"});
 const result=await privateRead(path,"synthetic-cookie",async(url,init)=>{assert.equal(String(url),"https://backend.test"+path);assert.deepEqual(init?.headers,{Cookie:"synthetic-cookie",Host:"public.test"});assert.equal(init?.cache,"no-store");return Response.json(data);},{origin:"https://backend.test",host:"public.test"});assert.equal(result.status,200);
});
