import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import ts from 'typescript';
import {createTranslator} from 'next-intl';
import * as model from '../lib/model.ts';
import * as catalog from '../lib/catalog.ts';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';
const file=new URL('../components/catalog-items-overview.tsx',import.meta.url);
const both={...catalogSession,permissions:['catalog-items.read','catalog-item-companies.read']};
function overview(storage=new Map<string,string>(),session=both,tenant='t'){
 const require=createRequire(import.meta.url),slots:any[]=[],effects:any[]=[],old:any[]=[];let cursor=0,dirty=true,tree:any,authority=session,props={session,tenantId:tenant};const calls:string[]=[];
 const ss={getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>storage.set(k,v),removeItem:(k:string)=>storage.delete(k)};
 const identity=()=>null,company=()=>null,module={exports:{} as any};
 const messages=JSON.parse(readFileSync(new URL('../messages/it.json',import.meta.url),'utf8'));
 function resolve(name:string):any{
  if(name==='react')return {...React,useState:(init:any)=>{const n=cursor++;if(!(n in slots))slots[n]=typeof init==='function'?init():init;return [slots[n],(v:any)=>{slots[n]=typeof v==='function'?v(slots[n]):v;dirty=true;}];},useRef:(v:any)=>{const n=cursor++;return slots[n]??(slots[n]={current:v});},useEffect:(fn:any,deps:any[])=>{const n=cursor++;if(!old[n]||deps.some((v,i)=>!Object.is(v,old[n].deps[i])))effects.push(()=>{old[n]?.cleanup?.();old[n]={deps,cleanup:fn()};});}};
  if(name==='next-intl')return {useTranslations:(namespace:string)=>createTranslator({locale:'it',messages,namespace})};
  if(name==='@/lib/model')return model;if(name==='@/lib/catalog')return catalog;
  if(name==='@/lib/api')return {api:async(path:string)=>{calls.push(path);return authority;}};
  if(name==='@/components/catalog-item-workspace')return {CatalogItemWorkspace:identity};
  if(name==='@/components/company-catalog-items')return {CompanyCatalogItems:company};
  if(name.startsWith('@/components/ui/'))return {Button:(p:any)=>React.createElement('button',p)};
  return require(name);
 }
 runInNewContext(ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module,exports:module.exports,require:resolve,sessionStorage:ss,console});
 async function settle(){for(let i=0;i<20;i++){if(dirty){cursor=0;dirty=false;tree=module.exports.CatalogItemsOverview({...props,scope:(p:string)=>p,onError:String,heading:React.createElement('h1',{},'Items')});}while(effects.length)effects.shift()();await new Promise(r=>setImmediate(r));if(!dirty&&!effects.length)break;}return tree;}
 const find=(fn:any)=>findCatalog(tree,fn)??findCatalog(findCatalog(tree,(n:any)=>typeof n.props?.renderToolbar==='function')?.props.renderToolbar(null),fn),button=(view:string)=>find((n:any)=>n.props?.['data-action']==='catalog-'+view+'-view');
 return {settle,find,button,calls,identity,company,storage,change:(next:any)=>{props={...props,...next};authority=props.session;dirty=true;},revoke:(s:any)=>{authority=s;},click:async(view:string)=>{await button(view).props.onClick();await settle();}};
}
test('Catalog tile and traversal unify company-only readers without changing CRUD permissions',()=>{
 const session={...both,permissions:['catalog-item-companies.read']};const w=catalogHarness().workspace({0:session,1:false,5:model.catalogRoutes.map(key=>({key,fields:[]})),6:'catalog',7:'t'});
 assert.equal(w.canOpenResource(session,'catalog-items'),true);
 assert.equal(model.can(session,'catalog-items','read'),false);
 const tree=w.default();const tile=findCatalog(tree,n=>n.type==='button'&&findCatalog(n,c=>c.type==='h2'&&c.props.children==='Articoli e servizi'));
 assert.ok(tile);assert.equal(findCatalog(tree,n=>n.type==='button'&&findCatalog(n,c=>c.type==='h2'&&c.props.children==='Catalogo aziendale')),undefined);
 assert.deepEqual(model.navigationPath('catalog-item-companies'),['catalog','catalog-items','catalog-item-companies']);
});
test('overview component exists before exercising its real hooks',()=>assert.ok(existsSync(file),'unified wrapper missing'));
test('company-only mounts only authorized child and retains two BP-style controls',async()=>{
 assert.ok(existsSync(file),'unified wrapper missing');const h=overview(new Map(),{...both,permissions:['catalog-item-companies.read']});await h.settle();
 assert.equal(h.button('identity').props.disabled,true);assert.equal(h.button('company').props['aria-pressed'],true);assert.equal(h.button('company').props.variant,'default');assert.ok(h.find((n:any)=>n.type===h.company));assert.equal(h.find((n:any)=>n.type===h.identity),undefined);assert.deepEqual(h.calls,['/session']);
});
test('selection survives refresh, isolates user/tenant, and freshly validates revocation',async()=>{
 assert.ok(existsSync(file),'unified wrapper missing');const storage=new Map<string,string>();const h=overview(storage);await h.settle();await h.click('company');assert.equal(h.button('company').props['aria-pressed'],true);
 const reload=overview(storage);await reload.settle();assert.equal(reload.button('company').props['aria-pressed'],true);
 for(const session of [{...both,id:'other'},{...both,isSuperAdmin:true}]){const other=overview(storage,session,session.isSuperAdmin?'other-tenant':'t');await other.settle();assert.equal(other.button('identity').props['aria-pressed'],true);}
 h.revoke({...both,permissions:['catalog-items.read']});await h.click('company');assert.equal(h.button('identity').props['aria-pressed'],true);assert.equal(h.find((n:any)=>n.type===h.company),undefined);assert.ok(h.calls.every(p=>p==='/session'));
 h.change({session:{...both,permissions:['catalog-item-companies.read']}});await h.settle();assert.equal(h.button('company').props['aria-pressed'],true);
});
