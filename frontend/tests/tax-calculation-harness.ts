import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import {webcrypto} from 'node:crypto';
import React from 'react';
import ts from 'typescript';
import * as tax from '../lib/tax-rules.ts';
import * as model from '../lib/model.ts';
import {ApiError} from '../lib/api.ts';
import {uuid, identity, refs} from './tax-rules-harness.ts';

export {uuid};
export const calculationSession = {...identity, permissions:[...identity.permissions, 'tax-calculation.read', 'tax-calculation.simulate']};
export const policy = {
  policy:{code:'IT_VAT_STANDARD_V1',version:1,currency:'EUR',currencyScale:2,internalScale:12,roundingMode:'HALF_UP',roundingScope:'TAX_GROUP',residualAllocationMode:'LARGEST_REMAINDER'},
  currency:{id:uuid(40),code:'EUR',minor_units:2,version:1},permissions:['read','simulate'],
};
export function successfulScenario() {
  return {
    input:{...tax.emptyTaxDeterminationInput(),company_id:uuid(6),item_id:uuid(7),business_partner_id:uuid(8),tax_type_id:uuid(5)},
    draftVersionIds:[uuid(2)],
    output:{outcome:'SUCCESS',result:{rate:'22.000000'},isSimulation:true,trace:{}},
  };
}
export function calculationHarness(options:any = {}) {
  const slots:any[] = [], effectSlots:any[] = [], effects:(()=>void)[] = [], calls:any[] = [];
  const map:Map<string,string> = options.storage ?? new Map();
  const session = options.session ?? calculationSession;
  const key = tax.taxSimulatorRecoveryKey(session.id, session.tenantId ?? 't');
  if (options.initial && !map.has(key)) map.set(key, JSON.stringify(options.initial));
  const storage = {getItem:(k:string)=>map.get(k) ?? null,setItem:(k:string,v:string)=>map.set(k,v),removeItem:(k:string)=>map.delete(k)};
  let cursor = 0, dirty = true, tree:any;
  const ui = new Proxy({}, {get:(_,name)=>{
    const component = (props:any)=>React.createElement('div',props);
    Object.defineProperty(component,'name',{value:String(name)});
    return component;
  }});
  const hooks = {...React,
    useState:(value:any)=>{
      const i = cursor++;
      if (!(i in slots)) slots[i] = typeof value === 'function' ? value() : value;
      return [slots[i], (v:any)=>{const next = typeof v === 'function' ? v(slots[i]) : v;if(!Object.is(next,slots[i])) {slots[i]=next;dirty=true;}}];
    },
    useRef:(v:any)=>{const i=cursor++;return slots[i] ?? (slots[i]={current:v});},
    useEffect:(fn:any,deps:any[])=>{
      const i=cursor++, old=effectSlots[i];
      if(!old || deps.some((v,j)=>!Object.is(v,old.deps[j]))) effects.push(()=>{old?.cleanup?.();effectSlots[i]={deps,cleanup:fn()};});
    },
  };
  const api = async(path:string,method='GET',body?:any)=>{
    calls.push({path,method,body});
    const override = await options.handler?.(path,method,body);
    if (override !== undefined) return override;
    if(path==='/session') return options.freshSession ?? session;
    if(path.includes('/calculation-policy')) return options.policy ?? policy;
    if(path.includes('/determination-lookups')) return {countries:refs.countries,types:refs.types,companies:refs.companies,registrations:[],permissions:options.f4Permissions ?? ['read','simulate','determine']};
    throw new Error('Unexpected request '+path);
  };
  const require = createRequire(import.meta.url), cache = new Map<string,any>();
  function load(relative:string):any {
    if(cache.has(relative)) return cache.get(relative);
    const module = {exports:{} as any};
    cache.set(relative,module.exports);
    const code = ts.transpileModule(readFileSync(new URL(relative,import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
    runInNewContext(code,{module,exports:module.exports,require:resolve,sessionStorage:storage,console,AbortController,URLSearchParams,structuredClone,crypto:webcrypto,fetch:async(path:string,init:any)=>{
      calls.push({path,method:init.method,body:JSON.parse(init.body)});
      return options.fetch?.(path,init) ?? {ok:true,status:200,json:async()=>({isSimulation:true,result:{currency:'EUR',calculationPolicyCode:'IT_VAT_STANDARD_V1',calculationPolicyVersion:1,lines:[{lineId:uuid(50),netAmount:'10.00',taxAmount:'2.20',grossAmount:'12.20'}],summaries:[{priceMode:'TAX_EXCLUSIVE',netAmount:'10.00',taxAmount:'2.20',grossAmount:'12.20'}],totals:{amountPayable:'12.20'},calculationTrace:{allocations:[]}}})};
    }});
    return module.exports;
  }
  function resolve(name:string):any {
    if(name==='react') return hooks;
    if(name==='next-intl') return {useTranslations:()=>Object.assign((k:string)=>k,{has:()=>true})};
    if(name==='@/lib/tax-rules' || name==='./tax-rules.ts') return tax;
    if(name==='@/lib/model') return model;
    if(name==='@/lib/api' || name==='./api.ts') return {api,ApiError,refreshCsrf:async()=>'csrf'};
    if(name==='@/lib/tax-calculation') return load('../lib/tax-calculation.ts');
    if(name==='@/components/tax-calculation-panel') return load('../components/tax-calculation-panel.tsx');
    if(name.startsWith('@/components/ui/')) return ui;
    return require(name);
  }
  const root = load('../components/tax-simulator.tsx');
  function expand(node:any):any {
    if(Array.isArray(node)) return node.map(expand);
    if(!node || typeof node!=='object') return node;
    if(node.type?.name==='TaxCalculationPanel') return expand(node.type(node.props));
    return {...node,props:{...node.props,children:expand(node.props?.children)}};
  }
  function walk(node:any,predicate:(n:any)=>boolean):any {
    if(Array.isArray(node)) {for(const n of node) {const found=walk(n,predicate);if(found)return found;}return;}
    if(!node || typeof node!=='object') return;
    if(predicate(node)) return node;
    return walk(node.props?.children,predicate);
  }
  const scope=(path:string)=>path;
  async function settle() {
    for(let i=0;i<70;i++) {
      if(dirty) {cursor=0;dirty=false;tree=expand(root.TaxSimulator({session,tenantId:'t',scope,onError:(e:any)=>e.code ?? e.message}));}
      while(effects.length) effects.shift()!();
      await new Promise(r=>setImmediate(r));
      if(!dirty&&!effects.length)break;
    }
    return tree;
  }
  return {settle,calls,map,key,find:(p:(n:any)=>boolean)=>walk(tree,p),byId:(id:string)=>walk(tree,n=>n.props?.id===id),
    get state(){return JSON.parse(map.get(key)??'null');},
    change(id:string,value:string){const node=walk(tree,n=>n.props?.id===id);assertNode(node,id);node.props.onChange({target:{value}});},
    unmount(){for(const effect of effectSlots)effect?.cleanup?.();},
  };
}
function assertNode(node:any,id:string) {if(!node) throw new Error('Missing real component control '+id);}
