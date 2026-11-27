import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import ts from 'typescript';
import {createTranslator} from 'next-intl';
import * as model from '../lib/model.ts';
import * as tax from '../lib/tax.ts';
import * as classifications from '../lib/tax-classifications.ts';
import * as companyTax from '../lib/company-tax.ts';
class ErrorResponse extends Error {code:string;status:number;constructor(code:string,status:number){super(code);this.code=code;this.status=status;}}
const version={...tax.blankTaxVersion(),valid_from:'2026-01-01'};
const record:tax.TaxCode={id:'r',tenant_id:'t',tax_type_id:'vat',country_id:'it',country_iso_code:'IT',code:'VAT22',name:'IVA',description:null,is_active:true,version:4,created_at:'2026-01-01',updated_at:'2026-01-01',versions:[version]};
const session:model.Session={id:'u',username:'ada',displayName:'Ada',preferredLanguage:'it',isSuperAdmin:false,tenantId:'t',mustChangePassword:false,permissions:['tax-codes.read','tax-codes.create','tax-codes.update','tax-codes.schedule','tax-codes.deactivate','tax-codes.reactivate','tax-codes.install_templates']};
function find(node:any,predicate:(node:any)=>boolean):any {if(!node||typeof node!=='object')return;if(predicate(node))return node;for(const child of [node.props?.children,...(node.props?.fields??[]).map((x:any)=>x.content)].flat(Infinity)){const result=find(child,predicate);if(result)return result;}}
export function harness(saved:Partial<tax.TaxState>={},handler:(path:string,method:string,body:any)=>any=()=>undefined,identity=session,storage=new Map<string,string>()) {
 const key=tax.taxKey(identity.id,'t');if(Object.keys(saved).length)storage.set(key,JSON.stringify({...tax.taxDefaults(),...saved}));
 const slots:any[]=[],effectSlots:any[]=[],effects:any[]=[],calls:{path:string;method:string;body:any}[]=[];
 let cursor=0,dirty=true,tree:any;
 const messages=JSON.parse(readFileSync(new URL('../messages/it.json',import.meta.url),'utf8'));
 const require=createRequire(import.meta.url);
 const module={exports:{} as any};
 const scope=(path:string)=>path+(path.includes('?')?'&':'?')+'tenantId=t';
 const ui=new Proxy({},{get:(_,name)=>{const fn=(props:any)=>React.createElement('div',props);Object.defineProperty(fn,'name',{value:String(name)});return fn;}});
 const resolve=(name:string):any=>{
  if(name==='react')return {...React,useState:(initial:any)=>{const index=cursor++;if(!(index in slots))slots[index]=typeof initial==='function'?initial():initial;return [slots[index],(next:any)=>{const value=typeof next==='function'?next(slots[index]):next;if(!Object.is(slots[index],value)){slots[index]=value;dirty=true;}}];},useRef:(initial:any)=>{const i=cursor++;return slots[i]??(slots[i]={current:initial});},useEffect:(fn:any,deps:any[])=>{const i=cursor++,old=effectSlots[i];if(!old||deps.some((v,j)=>!Object.is(v,old.deps[j])))effects.push(()=>{old?.cleanup?.();effectSlots[i]={deps,cleanup:fn()};});}};
  if(name==='next-intl')return {useTranslations:(namespace:string)=>createTranslator({locale:'it',messages,namespace})};
  if(name==='@/lib/model')return model;if(name==='@/lib/tax')return tax;
  if(name==='@/lib/tax-classifications')return classifications;
  if(name==='@/components/tax-classifications')return {TaxClassifications:()=>null};
  if(name==='@/components/tax-regimes')return {TaxRegimes:()=>null};
  if(name==='@/components/tax-rules')return {TaxRules:function TaxRules(){return null;}};
  if(name==='@/components/tax-simulator')return {TaxSimulator:function TaxSimulator(){return null;}};
  if(name==='@/lib/tax-rules')return {resetTaxRuleRecovery:()=>{},resetTaxSimulatorRecovery:()=>{}};
  if(name==='@/lib/company-tax')return companyTax;
  if(name.startsWith('@/components/ui/'))return ui;
  if(name==='@/lib/api')return {ApiError:ErrorResponse,api:async(path:string,method='GET',body:any)=>{
   calls.push({path,method,body});const custom=await handler(path,method,body);if(custom!==undefined)return custom;
   if(path==='/session')return identity;
   if(path.startsWith('/tax/lookups'))return {countries:[{id:'it',iso_code:'IT',name:'Italia'}],types:[{id:'vat',code:'VAT',name:'IVA',is_active:true}],natureCodes:[{id:'n4',country_id:'it',code:'N4',description:'Esenti'}]};
   if(path.startsWith('/tax/countries'))return {items:[{id:'it',iso_code:'IT',name:'Italia'}]};
   if(path.startsWith('/tax/types'))return {items:[{id:'vat',code:'VAT',name:'IVA',is_active:true}],total:1};
   if(path.startsWith('/tax/nature-codes'))return {items:[{id:'n4',country_id:'it',code:'N4',description:'Esenti'}],total:1};
   if(path.startsWith('/tax/codes/r/audit'))return {items:[],total:0};
   if(path.startsWith('/tax/codes/r'))return record;
   if(path.startsWith('/tax/codes'))return {items:[record],total:1};
   throw new Error('Unexpected '+path);
  }};
  return require(name);
 };
 const code=ts.transpileModule(readFileSync(new URL('../components/tax-workspace.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
 runInNewContext(code,{module,exports:module.exports,require:resolve,sessionStorage:{getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>storage.set(k,v),removeItem:(k:string)=>storage.delete(k)},console,AbortController,URLSearchParams});
 function render(){cursor=0;dirty=false;tree=module.exports.TaxManagement({session:identity,tenantId:'t',scope,onError:(e:any)=>e.code||e.message,heading:'Tasse e imposte'});}
 async function settle(){for(let i=0;i<40;i++){if(dirty)render();while(effects.length)effects.shift()();await new Promise(resolve=>setImmediate(resolve));if(!dirty&&!effects.length)break;}return tree;}
 return {settle,calls,storage,key,byId:(id:string)=>find(tree,n=>n.props?.id===id),byTest:(id:string)=>find(tree,n=>n.props?.['data-testid']===id),find:(p:any)=>find(tree,p),get state(){return slots[0] as tax.TaxState;},get tree(){return tree;},unmount(){for(const effect of effectSlots)effect?.cleanup?.();}};
}
test('code-only reader loads contextual options without requesting catalog authority',async()=>{
 const h=harness({},(path)=>{if(/^\/tax\/(types|nature-codes|countries)(?:[?]|$)/.test(path))throw new ErrorResponse('forbidden',403);}, {...session,permissions:['tax-codes.read']});
 await h.settle();assert.equal(h.calls.filter(c=>c.path.startsWith('/tax/lookups')).length,1);
 assert.equal(h.calls.some(c=>/^\/tax\/(types|nature-codes|countries)(?:[?]|$)/.test(c.path)),false);
 assert.equal(h.byId('tax-new'),undefined);
 const firstList=h.calls.find(c=>c.path.startsWith('/tax/codes?'));assert.ok(firstList);
 assert.equal(new URL(firstList.path,'http://fixture').searchParams.get('date'),tax.taxDefaults().date);
 h.byId('tax-date').props.onChange({target:{value:'2030-04-30'}});await h.settle();
 assert.equal(new URL(h.calls.filter(c=>c.path.startsWith('/tax/codes?')).at(-1)!.path,'http://fixture').searchParams.get('date'),'2030-04-30');
 h.byId('tax-date').props.onChange({target:{value:''}});await h.settle();
 assert.equal(new URL(h.calls.filter(c=>c.path.startsWith('/tax/codes?')).at(-1)!.path,'http://fixture').searchParams.has('date'),false);
 h.unmount();const recovered=harness({},()=>undefined,{...session,permissions:['tax-codes.read']},h.storage);await recovered.settle();
 assert.equal(recovered.byId('tax-date').props.value,'');recovered.unmount();
});
test('new code is staged with the first eligible references, not posted until main Save',async()=>{
 const h=harness();await h.settle();assert.equal(h.byId('tax-new').props.disabled,false);await h.byId('tax-new').props.onClick();await h.settle();
 assert.equal(h.state.editor?.values.country_id,'it');assert.equal(h.state.editor?.values.tax_type_id,'vat');
 h.byId('tax-name').props.onChange({target:{value:'IVA test'}});await h.settle();h.byId('tax-code').props.onChange({target:{value:'VATTEST'}});await h.settle();
 h.byTest('tax-editor-versions').props.onClick();await h.settle();h.byId('tax-add-version').props.onClick();await h.settle();
 h.byId('tax-valid_from').props.onChange({target:{value:'2026-01-01'}});await h.settle();
 const form=h.find((n:any)=>n.type==='form'&&n.props.id!=='tax-editor-form');form.props.onSubmit({preventDefault(){},stopPropagation(){}});await h.settle();
 assert.equal(h.state.editor?.versions.length,1);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);h.unmount();
});
test('scheduling writes immediately, leaves metadata draft intact and advances its own token',async()=>{
 let persisted={...record};const draft:tax.TaxEditor={id:'r',expectedVersion:4,original:record,values:{name:'Bozza locale',code:'VAT22',description:'non salvare',tax_type_id:'vat',country_id:'it'},versions:[version],readonly:false};
 const h=harness({editor:draft,tab:'versions'},(path,method,body)=>{if(method==='POST'){persisted={...record,version:5,versions:[{...version,valid_to:'2026-12-31'},body.values]};return persisted;}if(path.startsWith('/tax/codes/r?'))return persisted;});
 await h.settle();h.byId('tax-add-version').props.onClick();await h.settle();h.byId('tax-valid_from').props.onChange({target:{value:'2027-01-01'}});await h.settle();
 h.find((n:any)=>n.type==='form'&&n.props.id!=='tax-editor-form').props.onSubmit({preventDefault(){},stopPropagation(){}});await h.settle();
 const posts=h.calls.filter(c=>c.method==='POST');assert.equal(posts.length,1);assert.equal(posts[0].body.expectedVersion,4);assert.equal(posts[0].body.values.name,undefined);assert.equal(h.state.editor?.values.name,'Bozza locale');assert.equal(h.state.editor?.expectedVersion,5);assert.equal(h.state.editor?.versions.length,2);assert.equal(h.storage.has(h.key+':pending'),false);h.unmount();
});
test('readonly recovered details allow read-plus-schedule without update, retaining modal during write',async()=>{
 const identity={...session,permissions:['tax-codes.read','tax-codes.schedule']};
 const draft:tax.TaxEditor={id:'r',expectedVersion:4,original:record,values:{name:record.name,code:record.code,description:'',tax_type_id:'vat',country_id:'it'},versions:[version],readonly:true};
 let persisted={...record},release:(value:tax.TaxCode)=>void=()=>{};
 const h=harness({editor:draft,tab:'versions'},(path,method,body)=>{
  if(method==='POST')return new Promise<tax.TaxCode>(resolve=>{release=()=>{persisted={...record,version:5,versions:[{...version,valid_to:'2026-12-31'},body.values]};resolve(persisted);};});
  if(path.startsWith('/tax/codes/r?'))return persisted;
 },identity);
 await h.settle();assert.equal(h.state.editor?.readonly,true);
 assert.equal(h.find((n:any)=>n.props?.form==='tax-editor-form'),undefined);
 assert.equal(h.byId('tax-add-version').props.disabled,false);
 h.byId('tax-add-version').props.onClick();await h.settle();
 assert.equal(h.byId('tax-legal_reference').props.maxLength,255);
 h.byId('tax-valid_from').props.onChange({target:{value:'2027-01-01'}});await h.settle();
 h.find((n:any)=>n.type==='form'&&n.props.id!=='tax-editor-form').props.onSubmit({preventDefault(){},stopPropagation(){}});await h.settle();
 assert.ok(h.byId('tax-editor'),'normal busy state must not unmount details');
 assert.ok(h.byId('tax-valid_from'),'normal busy state must not unmount the version dialog');
 assert.equal(h.byId('tax-add-version').props.disabled,true);
 release(persisted);await h.settle();
 assert.equal(h.calls.filter(c=>c.method==='POST').length,1);
 assert.equal(h.calls.find(c=>c.method==='POST')?.body.expectedVersion,4);
 assert.equal(h.state.editor?.readonly,true);assert.equal(h.state.editor?.expectedVersion,5);
 assert.equal(h.state.versionDraft,null);assert.equal(h.storage.has(h.key+':pending'),false);h.unmount();
});
test('a stale recovered draft never adopts the server revision or sends a write',async()=>{
 const h=harness({editor:{id:'r',expectedVersion:3,original:{...record,version:3},values:{name:'Bozza',code:'VAT22',description:'',tax_type_id:'vat',country_id:'it'},versions:[version],readonly:false}});await h.settle();
 assert.equal(h.state.editor?.expectedVersion,3);const save=h.find((n:any)=>n.props?.form==='tax-editor-form');assert.equal(save.props.disabled,true);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);h.unmount();
});
test('uncertain mutation survives menu reset and refresh and cannot be blindly resubmitted',async()=>{
 const draft:tax.TaxEditor={id:'r',expectedVersion:4,original:record,values:{name:'Nuovo nome',code:'VAT22',description:'',tax_type_id:'vat',country_id:'it'},versions:[version],readonly:false};
 const h=harness({editor:draft},(_,method)=>{if(method==='PUT')throw new ErrorResponse('network_error',0);});await h.settle();h.byId('tax-editor-form').props.onSubmit({preventDefault(){}});await h.settle();
 assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);assert.ok(h.storage.has(h.key+':pending'));assert.equal(h.byId('tax-editor'),undefined);
 tax.resetTaxState({getItem:(k:string)=>h.storage.get(k)??null,removeItem:(k:string)=>{h.storage.delete(k);}},h.key);h.unmount();
 const recovered=harness({},()=>undefined,session,h.storage);await recovered.settle();assert.equal(recovered.byId('tax-new'),undefined);assert.equal(recovered.byId('tax-editor'),undefined);assert.equal(recovered.calls.filter(c=>c.method!=='GET').length,0);recovered.unmount();
});
test('types-only readers do not fetch codes or code-only lookup catalogs',async()=>{
 const h=harness({},()=>undefined,{...session,permissions:['tax-types.read']});await h.settle();assert.equal(h.byTest('tax-tab-types').props['aria-selected'],true);assert.equal(h.byId('tax-new'),undefined);assert.equal(h.calls.some(c=>c.path.startsWith('/tax/lookups')||c.path.startsWith('/tax/countries')||c.path.startsWith('/tax/codes')||c.path.startsWith('/tax/nature-codes')),false);h.unmount();
});
