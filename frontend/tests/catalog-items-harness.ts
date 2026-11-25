import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import {createTranslator} from 'next-intl';
import ts from 'typescript';
import * as model from '../lib/model.ts';
import * as catalog from '../lib/catalog.ts';
import * as items from '../lib/catalog-items.ts';
import {CatalogApiError,findCatalog} from './catalog-harness.ts';
export {CatalogApiError,findCatalog};
export const itemSession:model.Session={id:'user-items',username:'ada',displayName:'Ada',preferredLanguage:'it',tenantId:'tenant-items',isSuperAdmin:false,mustChangePassword:false,permissions:['read','create','update','activate','deactivate','archive'].map(a=>'catalog-items.'+a)};
export const itemOptions:items.ItemOptions={types:[{id:'good',name:'Goods type',code:'G',kind:'GOOD',is_active:true},{id:'service',name:'Service type',kind:'SERVICE',is_active:true},{id:'old',name:'Old type',kind:'GOOD',is_active:false}],categories:[{id:'category',name:'Category',parent_id:null,is_active:true}],brands:[{id:'brand',name:'Brand',code:'B',is_active:true}],units:[{id:'kg',name:'Kilogram',code:'KG',dimension:'MASS',conversion_scope:'UNIVERSAL',factor_to_base:'1',decimal_places:3,is_base:true,is_active:true},{id:'g',name:'Gram',code:'G',dimension:'MASS',conversion_scope:'UNIVERSAL',factor_to_base:'0.001',decimal_places:0,is_base:false,is_active:true},{id:'cf',name:'Carton',code:'CF',dimension:'COUNT',conversion_scope:'ITEM',factor_to_base:null,decimal_places:0,is_base:false,is_active:true},{id:'m',name:'Metre',code:'M',dimension:'LENGTH',conversion_scope:'UNIVERSAL',factor_to_base:'1',decimal_places:2,is_base:true,is_active:true}],numbering:{GOOD:{mode:'MANUAL'},SERVICE:{mode:'AUTO'}}};
export function root(overrides:Partial<items.ItemRecord>={}):items.ItemRecord{return {...items.itemInitial(),id:'item-a',name:'Item A',code:'A-1',kind:'GOOD',status:'SUSPENDED',version:4,activated_at:null,item_type_id:'good',base_uom_id:'g',category_id:'category',brand_id:'brand',identifiers:[],units:[],physicalData:null,...overrides};}
export function itemHarness(handler:(path:string,method:string,body:any)=>any=()=>undefined,config:{storage?:Map<string,string>;locale?:string;session?:model.Session;tenant?:string;options?:items.ItemOptions;record?:items.ItemRecord}={}){
 const require=createRequire(import.meta.url),storage=config.storage??new Map<string,string>(),locale=config.locale??'it',session=config.session??itemSession,tenant=config.tenant??session.tenantId??'tenant-items';
 const slots:any[]=[],effectSlots:any[]=[],effects:Array<()=>void>=[],calls:{path:string;method:string;body:any}[]=[];let cursor=0,tree:any,dirty=true;
 const messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));
 const sessionStorage={getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>{storage.set(k,v);},removeItem:(k:string)=>{storage.delete(k);}};
 const module={exports:{} as any};
 function resolve(name:string):any{
  if(name==='react')return {...React,useState:(initial:any)=>{const n=cursor++;if(!(n in slots))slots[n]=typeof initial==='function'?initial():initial;return [slots[n],(next:any)=>{const value=typeof next==='function'?next(slots[n]):next;if(!Object.is(value,slots[n])){slots[n]=value;dirty=true;}}];},useRef:(initial:any)=>{const n=cursor++;return slots[n]??(slots[n]={current:initial});},useEffect:(fn:any,deps:any[])=>{const n=cursor++,old=effectSlots[n];if(!old||deps.some((v,i)=>!Object.is(v,old.deps[i])))effects.push(()=>{old?.cleanup?.();effectSlots[n]={deps,cleanup:fn()};});}};
  if(name==='next-intl')return {useTranslations:(namespace:string)=>createTranslator({locale,messages,namespace,onError:(e:any)=>{throw e;}})};
  if(name==='@/lib/model')return model;if(name==='@/lib/catalog')return catalog;if(name==='@/lib/catalog-items')return items;
  if(name==='@/lib/api')return {ApiError:CatalogApiError,api:async(path:string,method='GET',body:any)=>{calls.push({path,method,body});const result=await handler(path,method,body);if(result!==undefined)return structuredClone(result);if(path==='/session')return session;if(path.startsWith('/catalog/item-options'))return config.options??itemOptions;if(method==='GET'&&path.startsWith('/catalog/items/'))return config.record??root();if(method==='GET'&&path.startsWith('/catalog/items?'))return {items:[config.record??root()],total:1,page:1,pageSize:25};throw Error('Unhandled '+method+' '+path);}};
  if(name.startsWith('@/components/ui/'))return new Proxy({},{get:(_,key)=>{const component=(props:any)=>React.createElement('div',props);Object.defineProperty(component,'name',{value:String(key)});return component;}});
  return require(name);
 }
 const source=readFileSync(new URL('../components/catalog-item-workspace.tsx',import.meta.url),'utf8');
 runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module,exports:module.exports,require:resolve,sessionStorage,AbortController,structuredClone,console});
 const scope=(path:string)=>path+(path.includes('?')?'&':'?')+'tenantId='+tenant;
 function render(){cursor=0;dirty=false;tree=module.exports.CatalogItemWorkspace({session,tenantId:tenant,scope,onError:(e:any)=>e.code??e.message,heading:React.createElement('h1',{},messages.catalogItems.title)});return tree;}
 async function settle(){for(let i=0;i<40;i++){if(dirty||!tree)render();while(effects.length)effects.shift()!();await new Promise(resolve=>setImmediate(resolve));if(!dirty&&!effects.length)break;}return tree;}
 const byId=(id:string)=>findCatalog(tree,n=>n.props?.id===id);
 const find=(predicate:(n:any)=>boolean)=>findCatalog(tree,predicate);
 const action=(label:string)=>find(n=>n.props?.['aria-label']===label);
 async function click(id:string){const node=byId(id);if(!node)throw Error('Missing '+id);if(node.props.disabled)throw Error('Disabled '+id);await node.props.onClick();return settle();}
 async function edit(id:string,value:any){const node=byId(id);if(!node)throw Error('Missing '+id);node.props.onChange({target:{value}});return settle();}
 async function select(id:string,value:any){const trigger=byId(id);if(!trigger)throw Error('Missing '+id);const parent=find(n=>n.props?.onValueChange&&findCatalog(n,c=>c===trigger));if(parent.props.disabled)throw Error('Disabled '+id);parent.props.onValueChange(value);return settle();}
 async function submit(child=false,confirmActivation=false){const content=child?find(n=>n.props?.['data-testid']==='catalog-item-row-editor'):find(n=>n.props?.['data-testid']==='catalog-item-editor');const form=findCatalog(content,n=>n.type==='form');form.props.onSubmit({preventDefault(){},stopPropagation(){}});await settle();if(!child&&confirmActivation)return click('item-activation-confirm');return tree;}
 return {settle,render,byId,action,find,click,edit,select,submit,calls,storage,get tree(){return tree;},get state(){return slots[0] as items.ItemState;},get pending(){return slots[1] as items.ItemPending|null;},unmount(){for(const effect of effectSlots)effect?.cleanup?.();}};
}
