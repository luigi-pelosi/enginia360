import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import {createTranslator} from 'next-intl';
import ts from 'typescript';
import * as model from '../lib/model.ts';
export class CatalogApiError extends Error {code:string;status:number;field?:string;constructor(code:string,status:number,field?:string){super(code);this.code=code;this.status=status;this.field=field;}}
export const catalogSession:model.Session={id:'u',username:'ada',displayName:'Ada',preferredLanguage:'it',tenantId:'t',isSuperAdmin:false,mustChangePassword:false,permissions:['catalog-units','catalog-categories','catalog-types','catalog-numbering'].flatMap(r=>['read','create','update','delete'].map(a=>r+'.'+a))};
export function findCatalog(node:any,predicate:(n:any)=>boolean):any {
 if(!node||typeof node!=='object')return undefined;if(predicate(node))return node;
 for(const child of [node.props?.children,...(node.props?.fields??[]).map((field:any)=>field.content)].flat(Infinity)){const found=findCatalog(child,predicate);if(found)return found;}
}
export function catalogHarness(resource='catalog-types',handler:(path:string,method:string,body:any)=>any=()=>({items:[],total:0}),storage=new Map<string,string>(),locale='it',session=catalogSession){
 const require=createRequire(import.meta.url), slots:any[]=[], effectSlots:any[]=[], calls:{path:string;method:string;body:any}[]=[], effects:Array<()=>void>=[];
 let cursor=0, tree:any, dirty=true;
 let props:{session:model.Session;tenantId:string;resource:string}={session,tenantId:'t',resource};
 const messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));
 const sessionStorage={getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>{storage.set(k,v);},removeItem:(k:string)=>{storage.delete(k);}};
 const load=(path:string,extra='')=>{const module={exports:{} as any};const source=readFileSync(new URL(path,import.meta.url),'utf8');runInNewContext(ts.transpileModule(source+extra,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module,exports:module.exports,require:resolve,sessionStorage,AbortController,console,setTimeout,clearTimeout});return module.exports;};
 let helpers:any;
 function resolve(name:string):any {
  if(name==='react')return {...React,useState:(initial:any)=>{const n=cursor++;if(!(n in slots))slots[n]=typeof initial==='function'?initial():initial;return[slots[n],(next:any)=>{const value=typeof next==='function'?next(slots[n]):next;if(!Object.is(value,slots[n])){slots[n]=value;dirty=true;}}];},useRef:(initial:any)=>{const n=cursor++;return slots[n]??(slots[n]={current:initial});},useEffect:(fn:any,deps:any[])=>{const n=cursor++;const old=effectSlots[n];if(!old||deps.some((v,i)=>!Object.is(v,old.deps[i]))){effects.push(()=>{old?.cleanup?.();effectSlots[n]={deps,cleanup:fn()};});}},useCallback:(fn:any)=>fn,useMemo:(fn:any)=>fn()};
  if(name==='next-intl')return{useTranslations:(namespace:string)=>createTranslator({locale,messages,namespace}),useLocale:()=>locale};
  if(name==='@/lib/model')return model;
  if(name==='@/lib/catalog')return helpers;
  if(name==='@/lib/api')return{ApiError:CatalogApiError,api:async(path:string,method='GET',body:any)=>{calls.push({path,method,body});if(path==='/session')return handler(path,method,body)??session;return handler(path,method,body);}};
  if(name.startsWith('@/components/ui/'))return new Proxy({},{get:(_,key)=>{const component=(props:any)=>React.createElement('div',props);Object.defineProperty(component,'name',{value:String(key)});return component;}});
  if(name==='@/components/catalog-workspace')return component;
  if(name==='@/components/payments-workspace')return {PaymentsWorkspace:()=>null};
  if(name==='@/lib/password')return {passwordValidation:()=>null};
  if(name.startsWith('@/components/'))return new Proxy({},{get:()=>()=>null});
  return require(name);
 }
 helpers=load('../lib/catalog.ts');
 const component=load('../components/catalog-workspace.tsx');
 const scope=(path:string)=>path+(path.includes('?')?'&':'?')+'tenantId='+encodeURIComponent(props.session.isSuperAdmin?props.tenantId:props.session.tenantId||'');const onError=(e:any)=>e.code||e.message;
 function render(){cursor=0;dirty=false;tree=component.CatalogWorkspace({...props,scope,onError,heading:React.createElement('h1',{},props.resource)});return tree;}
 async function settle(){for(let i=0;i<30;i++){if(dirty||!tree)render();while(effects.length)effects.shift()!();await new Promise(resolve=>setImmediate(resolve));if(!dirty&&!effects.length)break;}return tree;}
 const byId=(id:string)=>findCatalog(tree,n=>n.props?.id===id);
 const action=(label:string)=>findCatalog(tree,n=>n.props?.['aria-label']===label);
 const submit=()=>{const form=findCatalog(tree,n=>n.type==='form');form.props.onSubmit({preventDefault(){},stopPropagation(){}});};
 return {settle,render,rerender:(next:Partial<typeof props>)=>{props={...props,...next};dirty=true;return render();},byId,action,submit,calls,storage,helpers,get tree(){return tree;},get state(){return slots[0];},unmount(){for(const effect of effectSlots)effect?.cleanup?.();},workspace:(states:Record<number,unknown>)=>{const workspace=load('../components/workspace.tsx','\nexport {canOpenResource,WorkspaceNavigation};');for(const [k,v]of Object.entries(states))slots[Number(k)]=v;cursor=0;return workspace;}};
}
