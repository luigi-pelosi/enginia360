import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import {createTranslator} from 'next-intl';
import ts from 'typescript';
import * as model from '../lib/model.ts';
import * as catalog from '../lib/catalog.ts';
const companies=[{id:'a',name:'Company A',code:'A',is_enabled:true,permissions:['read','create','update']},{id:'b',name:'Company B',code:'B',is_enabled:true,permissions:['read']}];
const context={item:{id:'i',code:'I',name:'Item',status:'SUSPENDED',kind:'GOOD',base_uom_id:'kg'},defaults:{is_sellable:true,is_purchasable:false,track_stock:true},units:[{id:'kg',name:'Kilogram',code:'KG',is_active:true},{id:'box',name:'Box',code:'BOX',is_active:true}]};
const row=(company_id='a',other={})=>({id:'rel-'+company_id,company_id,item_id:'i',company_name:'Company '+company_id,company_is_enabled:true,item_code:'I',item_name:'Item',item_status:'SUSPENDED',kind:'GOOD',base_uom_id:'kg',is_enabled:true,is_sellable:true,is_purchasable:false,track_stock:true,default_sales_uom_id:null,default_purchase_uom_id:null,effective_sales_uom_id:'kg',effective_purchase_uom_id:'kg',canSell:false,canPurchase:false,canTrackStock:false,version:1,...other});
class ApiError extends Error{code:string;status:number;constructor(code:string,status:number){super(code);this.code=code;this.status=status;}}
function find(tree:any,predicate:(n:any)=>boolean):any{if(!tree)return null;if(Array.isArray(tree)){for(const n of tree){const found=find(n,predicate);if(found)return found;}return null;}if(typeof tree!=='object')return null;if(predicate(tree))return tree;return find([tree.props?.children,...(tree.props?.fields??[]).map((field:any)=>field.content)],predicate);}
function harness(config:{itemId?:string;itemStatus?:string;storage?:Map<string,string>;permissions?:string[];handler?:(path:string,method:string,body:any)=>any}={}){
 const require=createRequire(import.meta.url),storage=config.storage??new Map(),calls:any[]=[],slots:any[]=[],es:any[]=[],effects:any[]=[];let cursor=0,dirty=true,tree:any;
 const session={id:'user',tenantId:'tenant',isSuperAdmin:false,mustChangePassword:false,permissions:config.permissions??['catalog-items.read',...['read','create','update'].map(a=>'catalog-item-companies.'+a)]};
 const sessionStorage={getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>storage.set(k,v),removeItem:(k:string)=>storage.delete(k)};
 const source=new URL('../components/catalog-item-companies.tsx',import.meta.url);
 function resolve(name:string):any{
  if(name==='react')return {...React,useState:(initial:any)=>{const n=cursor++;if(!(n in slots))slots[n]=typeof initial==='function'?initial():initial;return [slots[n],(next:any)=>{const v=typeof next==='function'?next(slots[n]):next;if(!Object.is(v,slots[n])){slots[n]=v;dirty=true;}}];},useRef:(v:any)=>{const n=cursor++;return slots[n]??(slots[n]={current:v});},useEffect:(fn:any,deps:any[])=>{const n=cursor++,old=es[n];if(!old||deps.some((v,i)=>!Object.is(v,old.deps[i])))effects.push(()=>{old?.cleanup?.();es[n]={deps,cleanup:fn()};});}};
  if(name==='next-intl')return {useLocale:()=> 'en',useTranslations:(namespace:string)=>createTranslator({locale:'en',messages:JSON.parse(readFileSync(new URL('../messages/en.json',import.meta.url),'utf8')),namespace,onError:(e:any)=>{throw e;}})};
  if(name==='@/lib/model')return model;if(name==='@/lib/catalog')return catalog;
  if(name==='@/lib/catalog-companies'){const m={exports:{}};runInNewContext(ts.transpileModule(readFileSync(new URL('../lib/catalog-companies.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:m,exports:m.exports,require:resolve,structuredClone});return m.exports;}
  if(name==='@/lib/api')return {ApiError,api:async(path:string,method='GET',body:any)=>{calls.push({path,method,body});const result=await config.handler?.(path,method,body);if(result!==undefined)return result;if(path==='/session')return session;if(path==='/catalog/item-options')return {types:[],categories:[],units:[],brands:[],numbering:{}};if(path.startsWith('/catalog/item-companies/options'))return {items:companies};if(path.startsWith('/catalog/item-companies/item-options/'))return context;if(path.startsWith('/catalog/items?'))return {items:[{...context.item,id:'i'},{...context.item,id:'j',name:'Other'}],total:2,page:1,pageSize:25};if(method==='GET'&&path.startsWith('/companies/'))return row();if(method==='GET')return {items:[],total:0,page:1,pageSize:25};return row();}};
  if(name.startsWith('@/components/ui/'))return new Proxy({},{get:(_,key)=>{const c=(p:any)=>React.createElement('div',p);Object.defineProperty(c,'name',{value:String(key)});return c;}});
  return require(name);
 }
 const m={exports:{} as any};
 if(existsSync(source))runInNewContext(ts.transpileModule(readFileSync(source,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module:m,exports:m.exports,require:resolve,sessionStorage,AbortController,structuredClone,console});
 else m.exports.CatalogItemCompanies=()=>null;
 const scope=(p:string)=>p,props={session,tenantId:'tenant',scope,onError:(e:any)=>e.code??e.message,itemId:config.itemId,itemStatus:config.itemStatus};
 async function settle(){for(let i=0;i<40;i++){if(dirty){cursor=0;dirty=false;tree=m.exports.CatalogItemCompanies(props);}while(effects.length)effects.shift()();await new Promise(r=>setImmediate(r));if(!dirty&&!effects.length)return tree;}throw Error('Effect render loop');}
 const byId=(id:string)=>find(tree,n=>n.props?.id===id);
 return {settle,byId,find:(p:(n:any)=>boolean)=>find(tree,p),calls,storage,async click(id:string){const n=byId(id);assert.ok(n,'Missing '+id);assert.ok(!n.props.disabled,'Disabled '+id);await n.props.onClick();return settle();},async toggle(id:string,v:boolean){const n=byId(id);assert.ok(n,'Missing '+id);assert.ok(!n.props.disabled,'Disabled '+id);n.props.onCheckedChange(v);return settle();},async select(id:string,v:string){const n=byId(id);const parent=find(tree,p=>p.props?.onValueChange&&find(p,c=>c===n));assert.ok(parent,'Missing '+id);parent.props.onValueChange(v);return settle();},async submit(){const form=find(tree,n=>n.type==='form');assert.ok(form);let stopped=false;await form.props.onSubmit({preventDefault(){},stopPropagation(){stopped=true;}});assert.equal(stopped,true);return settle();},unmount(){for(const e of es)e?.cleanup?.();}};
}

export {harness};
