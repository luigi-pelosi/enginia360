import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import ts from 'typescript';
import * as tax from '../lib/tax-rules.ts';
import * as calculation from '../lib/tax-calculation.ts';
import * as model from '../lib/model.ts';
export const uuid=(n:number)=>`${String(n).padStart(8,'0')}-1111-4111-8111-111111111111`;
export const identity:model.Session={id:'u',username:'test',displayName:'Test',preferredLanguage:'en',tenantId:'t',isSuperAdmin:false,mustChangePassword:false,permissions:['tax-rules.read','tax-rules.create','tax-rules.update','tax-rules.validate','tax-rules.publish','tax-rules.withdraw','tax-rules.install_templates','tax-determination.read','tax-determination.simulate','tax-determination.determine','companies.read','company-tax-configurations.read','catalog-items.read','business-partners.read','tax-item-profiles.read','tax-partner-profiles.read']};
export const version:tax.TaxRuleVersion={id:uuid(2),version_number:1,status:'DRAFT',tax_code_id:uuid(3),priority:100,operation_type:'SALE',legal_reference:'Legal',valid_from:'2026-11-26',valid_to:null,conditions:[]};
export const root:tax.TaxRule={id:uuid(1),tenant_id:'t',company_id:null,country_id:uuid(4),tax_type_id:uuid(5),code:'RULE',name:'Saved name',description:null,version:4,versions:[version]};
export const refs:tax.TaxRuleLookups={...tax.emptyTaxRuleLookups,countries:[{id:uuid(4),iso_code:'IT',name:'Italy',is_enabled:true}],types:[{id:uuid(5),code:'VAT',name:'VAT',is_active:true}],companies:[{id:uuid(6),code:'C',name:'Company',permissions:['read','create','update','publish','simulate','determine','install_templates']}],codes:[{id:uuid(3),country_id:uuid(4),tax_type_id:uuid(5),code:'VAT_STANDARD',name:'Standard',is_active:true}],fields:[{key:'item.nature',type:'ENUM',operators:['EQUALS','IN'],reference:null,values:['GOOD','SERVICE'],available:true},{key:'partner.actingAsTaxablePerson',type:'BOOLEAN',operators:['EQUALS','IS_FALSE'],reference:null,values:[],available:true}],permissions:['read','create','update','validate','publish','withdraw','install_templates']};
export class ApiError extends Error{code:string;status:number;constructor(code:string,status:number){super(code);this.code=code;this.status=status;}}
export function walk(n:any,p:(n:any)=>boolean):any{if(!n||typeof n!=='object')return;if(p(n))return n;for(const child of [n.props?.children,...(n.props?.fields??[]).map((f:any)=>f.content)].flat(Infinity)){const found=walk(child,p);if(found)return found;}}
export function harness(kind:'rules'|'simulator',options:any={}){
 const slots:any[]=[],effectSlots:any[]=[],effects:(()=>void)[]=[],calls:any[]=[],map:Map<string,string>=options.storage??new Map(),busy:any[]=[];let cursor=0,dirty=true,tree:any;const session=options.session??identity,scope=(p:string)=>p;
 const key=(kind==='rules'?tax.taxRuleRecoveryKey:tax.taxSimulatorRecoveryKey)(session.id,session.tenantId??'t');
 if(options.initial&&!map.has(key))map.set(key,JSON.stringify(options.initial));
 const storage={getItem:(k:string)=>map.get(k)??null,setItem:(k:string,v:string)=>{if(options.storageFails)throw new Error('storage');map.set(k,v);},removeItem:(k:string)=>map.delete(k)};
 const ui=new Proxy({},{get:(_,name)=>{const f=(props:any)=>React.createElement('div',props);Object.defineProperty(f,'name',{value:String(name)});return f;}});
 const require=createRequire(import.meta.url),module={exports:{} as any};
 const api=async(path:string,method='GET',body?:any)=>{calls.push({path,method,body});const result=await options.handler?.(path,method,body);if(result!==undefined)return result;if(path==='/session')return session;if(path.includes('/permissions'))return {permissions:options.permissions??refs.permissions};if(path==='/tax/rule-lookups')return options.refs??refs;if(path.startsWith('/tax/rules?'))return {items:options.roots??[root],total:options.total??1,page:1,pageSize:25};if(path==='/tax/rules/'+root.id)return options.root??root;if(path.includes('/determination-lookups'))return {countries:refs.countries,types:refs.types,companies:refs.companies,registrations:[],permissions:options.simPermissions??['read','simulate','determine']};if(path.includes('/determination-options'))return {items:[{id:uuid(7),code:'SOURCE',name:'Source',tax_identifiers:[{id:uuid(8),country_code:'IT',identifier_type:'VAT'}]}],total:1,page:1,pageSize:20};if(path==='/tax/determinations/simulate')return {outcome:'INCOMPLETE_CONTEXT',result:null,trace:{missingFields:['partner.actingAsTaxablePerson'],candidates:[]},isSimulation:true};throw new Error('Unexpected '+path);};
 const resolve=(name:string):any=>{
   if(name==='react')return {...React,useState:(value:any)=>{const i=cursor++;if(!(i in slots))slots[i]=typeof value==='function'?value():value;return [slots[i],(v:any)=>{const next=typeof v==='function'?v(slots[i]):v;if(!Object.is(next,slots[i])){slots[i]=next;dirty=true;}}];},useRef:(v:any)=>{const i=cursor++;return slots[i]??(slots[i]={current:v});},useEffect:(fn:any,deps:any[])=>{const i=cursor++,old=effectSlots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))effects.push(()=>{old?.cleanup?.();effectSlots[i]={deps,cleanup:fn()};});}};
   if(name==='next-intl')return {useTranslations:(ns:string)=>Object.assign((key:string)=>key,{has:()=>true})};
   if(name==='@/lib/tax-rules')return tax;
   if(name==='@/lib/tax-calculation')return calculation;
   // Questa suite conserva il perimetro F4; l'harness F5 esegue il figlio reale.
   if(name==='@/components/tax-calculation-panel')return {
     TaxCalculationPanel: function TaxCalculationPanel(props:any){return React.createElement('div',props);}
   };
   if(name==='@/lib/model')return model;
   if(name==='@/lib/api')return {api,ApiError,refreshCsrf:async()=>'csrf'};
   if(name.startsWith('@/components/ui/'))return ui;
   return require(name);
 };
 const code=ts.transpileModule(readFileSync(new URL('../components/tax-'+(kind==='rules'?'rules':'simulator')+'.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
 runInNewContext(code,{module,exports:module.exports,require:resolve,sessionStorage:storage,console,AbortController,URLSearchParams,structuredClone,fetch:async(path:string,init:any)=>{const body=JSON.parse(init.body);calls.push({path,method:init.method,body});return options.fetch?.(path,init)??{ok:true,status:200,json:async()=>({outcome:'SUCCESS',result:{rate:'22.000000'},trace:{candidates:[]},isSimulation:false})};}});
 const onBusyChange=(v:boolean)=>busy.push(v);
 function render(){cursor=0;dirty=false;tree=(kind==='rules'?module.exports.TaxRules:module.exports.TaxSimulator)({session,tenantId:'t',scope,onError:(e:any)=>e.code??e.message,navigation:options.navigation,onBusyChange});}
 async function settle(){for(let i=0;i<60;i++){if(dirty)render();while(effects.length)effects.shift()!();await new Promise(r=>setImmediate(r));if(!dirty&&!effects.length)break;}return tree;}
 return {settle,calls,busy,map,key,byId:(id:string)=>walk(tree,n=>n.props?.id===id),find:(predicate:(n:any)=>boolean)=>walk(tree,predicate),get state(){return JSON.parse(map.get(key)??'null');},change(id:string,value:string){const n=walk(tree,n=>n.props?.id===id);if(n.props.onChange)n.props.onChange({target:{value}});else {let select:any;walk(tree,n=>{if(n.type?.name==='Select'&&walk(n,(c:any)=>c.props?.id===id))select=n;return false;});select.props.onValueChange(value);}},unmount(){for(const e of effectSlots)e?.cleanup?.();}};
}
