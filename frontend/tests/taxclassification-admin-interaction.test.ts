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
import * as companyTax from '../lib/company-tax.ts';
class ErrorResponse extends Error {code:string;status:number;constructor(code:string,status:number){super(code);this.code=code;this.status=status;}}
const version={...tax.blankTaxVersion(),valid_from:'2026-01-01'};
const record:tax.TaxCode={id:'r',tenant_id:'t',tax_type_id:'vat',country_id:'it',country_iso_code:'IT',code:'VAT22',name:'IVA',description:null,is_active:true,version:4,created_at:'2026-01-01',updated_at:'2026-01-01',versions:[version]};
const session:model.Session={id:'u',username:'ada',displayName:'Ada',preferredLanguage:'it',isSuperAdmin:false,tenantId:'t',mustChangePassword:false,permissions:['tax-item-classifications.read','tax-item-classifications.create','tax-item-classifications.update','tax-item-classifications.deactivate','tax-item-classifications.reactivate','tax-item-classifications.install_templates']};
function find(node:any,predicate:(node:any)=>boolean):any {if(!node||typeof node!=='object')return;if(predicate(node))return node;for(const child of [node.props?.children,...(node.props?.fields??[]).map((x:any)=>x.content)].flat(Infinity)){const result=find(child,predicate);if(result)return result;}}
function harness(saved:any={},handler:(path:string,method:string,body:any)=>any=()=>undefined,identity=session,storage=new Map<string,string>(),kind:'item'|'partner'='item',workspace=false) {
 const key=tax.taxKey(identity.id,'t')+':classifications:'+kind;if(Object.keys(saved).length)storage.set(key,JSON.stringify(saved));
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
  if(name==='@/components/tax-regimes')return {TaxRegimes:()=>null};
  if(name==='@/components/tax-rules')return {TaxRules:()=>null};
  if(name==='@/components/tax-simulator')return {TaxSimulator:()=>null};
  if(name==='@/lib/tax-rules')return {resetTaxRuleRecovery:()=>{},resetTaxSimulatorRecovery:()=>{}};
  if(name==='@/lib/company-tax')return companyTax;
  if(name==='@/components/tax-classifications'){const m={exports:{} as any};runInNewContext(ts.transpileModule(readFileSync(new URL('../components/tax-classifications.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module:m,exports:m.exports,require:resolve,sessionStorage:{getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>storage.set(k,v),removeItem:(k:string)=>storage.delete(k)},console,AbortController,URLSearchParams});return m.exports;}
  if(name==='@/lib/tax-classifications'){const m={exports:{}};runInNewContext(ts.transpileModule(readFileSync(new URL('../lib/tax-classifications.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText,{module:m,exports:m.exports,require:resolve});return m.exports;}
  if(name.startsWith('@/components/ui/'))return ui;
  if(name==='@/lib/api')return {ApiError:ErrorResponse,api:async(path:string,method='GET',body:any)=>{
   calls.push({path,method,body});const custom=await handler(path,method,body);if(custom!==undefined)return custom;
   if(path==='/session')return identity;
   if(path.startsWith('/tax/classification-lookups'))return {countries:[{id:'it',iso_code:'IT',name:'Italia'}],types:[{id:'bad',code:'OTHER',is_active:true},{id:'off',code:'VAT',is_active:false},{id:'vat',code:'VAT',name:'IVA',is_active:true}],classifications:[record]};
   if(path.startsWith('/tax/'+kind+'-classifications/r'))return record;
   if(path.startsWith('/tax/'+kind+'-classifications'))return {items:[record],total:1,page:1,pageSize:25};
   throw new Error('Unexpected '+path);
  }};
  return require(name);
 };
 const code=ts.transpileModule(readFileSync(new URL(workspace?'../components/tax-workspace.tsx':'../components/tax-classifications.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
 runInNewContext(code,{module,exports:module.exports,require:resolve,sessionStorage:{getItem:(k:string)=>storage.get(k)??null,setItem:(k:string,v:string)=>storage.set(k,v),removeItem:(k:string)=>storage.delete(k)},console,AbortController,URLSearchParams});
 function render(){cursor=0;dirty=false;const props={kind,session:identity,tenantId:'t',scope,onError:(e:any)=>e.code||e.message,navigation:'tabs',heading:'Tasse e imposte'};tree=workspace?module.exports.TaxManagement(props):module.exports.TaxClassifications(props);if(workspace){const child=find(tree,(n:any)=>n.type?.name==='TaxClassifications');if(child){const content=child.type(child.props);tree=React.createElement('div',{},tree,content);}}}
 async function settle(){for(let i=0;i<40;i++){if(dirty)render();while(effects.length)effects.shift()();await new Promise(resolve=>setImmediate(resolve));if(!dirty&&!effects.length)break;}return tree;}
 return {settle,calls,storage,key,byId:(id:string)=>find(tree,n=>n.props?.id===id),byTest:(id:string)=>find(tree,n=>n.props?.['data-testid']===id),find:(p:any)=>find(tree,p),get state(){return slots[0] as any;},get tree(){return tree;},unmount(){for(const effect of effectSlots)effect?.cleanup?.();}};
}
test('classification-only reader uses own contextual lookups and list without phase-one grants',async()=>{
 const h=harness({},()=>undefined,{...session,permissions:['tax-item-classifications.read']});await h.settle();
 assert.ok(h.byId('taxclass-table'));assert.ok(h.calls.some(c=>c.path.startsWith('/tax/classification-lookups?kind=item')));
 assert.equal(h.calls.some(c=>/^\/tax\/(codes|types|nature-codes|countries|lookups)(?:[?]|$)/.test(c.path)),false);
 assert.equal(h.byId('taxclass-new'),undefined);assert.equal(h.byId('taxclassinstall'),undefined);h.unmount();
});
test('creation defaults to active VAT, name first, immutable metadata update, no rates or dates',async()=>{
 let saved:any=null;const h=harness({},(path,method,body)=>{if(method==='POST'){saved={...record,...body.values,version:1};return saved;}if(saved&&path.startsWith('/tax/item-classifications/r'))return saved;});
 await h.settle();await h.byId('taxclass-new').props.onClick();await h.settle();
 assert.equal(h.state.editor.values.tax_type_id,'vat');assert.equal(h.state.editor.values.country_id,'it');
 h.byId('taxclass-name').props.onChange({target:{value:'Beni'}});await h.settle();h.byId('taxclass-code').props.onChange({target:{value:'GOODS'}});await h.settle();
 h.byId('taxclass-editor-form').props.onSubmit({preventDefault(){}});await h.settle();
 const post=h.calls.find(c=>c.method==='POST')!;assert.deepEqual(Object.keys(post.body).sort(),['values']);assert.deepEqual(JSON.parse(JSON.stringify(post.body.values)),{name:'Beni',code:'GOODS',description:null,country_id:'it',tax_type_id:'vat'});assert.equal(h.storage.has(h.key+':pending'),false);h.unmount();
});

const draft=()=>({id:'r',expectedVersion:4,original:record,values:{name:'Bozza locale',code:'VAT22',description:'Descrizione',country_id:'it',tax_type_id:'vat'},readonly:false});
test('update never sends identity scope, uses frozen original token and exact update authority',async()=>{
 let persisted={...record};const h=harness({editor:draft()},(path,method,body)=>{if(method==='PUT'){persisted={...record,...body.values,version:5};return persisted;}if(path.startsWith('/tax/item-classifications/r'))return persisted;});await h.settle();
 assert.equal(h.byId('taxclass-code').props.disabled,true);assert.ok(h.byId('taxclass-country_id'));
 h.byId('taxclass-editor-form').props.onSubmit({preventDefault(){}});await h.settle();
 assert.deepEqual(JSON.parse(JSON.stringify(h.calls.find(c=>c.method==='PUT')?.body)),{values:{name:'Bozza locale',description:'Descrizione'},expectedVersion:4});assert.equal(h.state.editor,null);h.unmount();
});
test('server classification stale-version conflict preserves original, draft and blocks resubmit',async()=>{
 let conflict=false;const h=harness({editor:draft()},(path,method)=>{if(method==='PUT'){conflict=true;throw new ErrorResponse('tax_classification_stale_version',409);}if(conflict&&path.startsWith('/tax/item-classifications/r'))return {...record,version:5,name:'Server corrente'};});await h.settle();
 h.byId('taxclass-editor-form').props.onSubmit({preventDefault(){}});await h.settle();
 assert.equal(h.state.editor.expectedVersion,4);assert.equal(h.state.editor.original.version,4);assert.equal(h.state.editor.values.name,'Bozza locale');
 assert.equal(h.find((n:any)=>n.props?.form==='taxclass-editor-form').props.disabled,true);assert.ok(h.find((n:any)=>n.type==='pre'&&String(n.props.children).includes('Server corrente')));
 h.byId('taxclass-editor-form').props.onSubmit({preventDefault(){}});await h.settle();assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);h.unmount();
});
test('uncertain accepted write stays blocked through remount; explicit readback and acknowledgment never replay it',async()=>{
 const h=harness({editor:draft()},(_,method)=>{if(method==='PUT')throw new ErrorResponse('network_error',0);});await h.settle();h.byId('taxclass-editor-form').props.onSubmit({preventDefault(){}});await h.settle();assert.ok(h.storage.has(h.key+':pending'));assert.equal(h.byId('taxclass-editor'),undefined);h.unmount();
 const recovered=harness({},()=>undefined,session,h.storage);await recovered.settle();assert.equal(recovered.byId('taxclass-new'),undefined);assert.equal(recovered.calls.some(c=>c.method!=='GET'),false);
 const review=recovered.find((n:any)=>n.props?.onClick&&n.props.children==='Leggi lo stato corrente del server');await review.props.onClick();await recovered.settle();assert.equal(recovered.calls.some(c=>c.method!=='GET'),false);
 recovered.find((n:any)=>n.props?.onClick&&n.props.children==='Verificato — chiudi comando recuperato').props.onClick();await recovered.settle();assert.equal(recovered.storage.has(recovered.key+':pending'),false);assert.equal(recovered.state.editor,null);recovered.unmount();
});
test('a changed fresh session denies writes, does not borrow phase-one or partner authority',async()=>{
 const unrelated={...session,permissions:['tax-item-classifications.read','tax-codes.update','tax-partner-classifications.update']};let checks=0;
 const h=harness({editor:draft()},path=>{if(path==='/session'&&++checks>1)return unrelated;});await h.settle();h.byId('taxclass-editor-form').props.onSubmit({preventDefault(){}});await h.settle();assert.equal(h.calls.some(c=>c.method!=='GET'),false);assert.equal(h.state.editor.values.name,'Bozza locale');h.unmount();
});
test('filters are search-first and send country, VAT type, active status, never a date',async()=>{
 const h=harness({country:'it',type:'vat',status:'false',search:'special',filtersExpanded:true});await h.settle();const list=h.calls.find(c=>c.path.startsWith('/tax/item-classifications?'))!;const query=new URL(list.path,'http://fixture').searchParams;
 assert.equal(query.get('country_id'),'it');assert.equal(query.get('tax_type_id'),'vat');assert.equal(query.get('is_active'),'false');assert.equal(query.get('search'),'special');assert.equal(query.has('date'),false);assert.equal(h.byId('taxclass-filters').props.fields[0].key,'search');h.unmount();
});

test('template installation is not declared successful if authoritative scoped template readback is incomplete',async()=>{
 const h=harness({},(_,method)=>{if(method==='POST')return {installed:10,skipped:0};});await h.settle();h.byId('taxclassinstall').props.onClick();await h.settle();h.byId('taxclass-install-form').props.onSubmit({preventDefault(){}});await h.settle();
 assert.deepEqual(JSON.parse(JSON.stringify(h.calls.find(c=>c.method==='POST')?.body)),{country_id:'it',tax_type_id:'vat'});assert.ok(h.storage.has(h.key+':pending'));assert.equal(h.calls.filter(c=>c.method==='POST').length,1);h.unmount();
});

test('partner reader uses only its own list and bounded lookup kind',async()=>{
 const h=harness({},()=>undefined,{...session,permissions:['tax-partner-classifications.read']},new Map(),'partner');await h.settle();assert.ok(h.byId('taxclass-table'));assert.ok(h.calls.some(c=>c.path.startsWith('/tax/partner-classifications?')));assert.ok(h.calls.some(c=>c.path.startsWith('/tax/classification-lookups?kind=partner')));assert.equal(h.calls.some(c=>c.path.startsWith('/tax/item-classifications')),false);assert.equal(h.byId('taxclass-new'),undefined);h.unmount();
});
test('readonly details stay readonly and transitions require their separate action',async()=>{
 const h=harness({},()=>undefined,{...session,permissions:['tax-item-classifications.read','tax-item-classifications.update']});await h.settle();const details=h.find((n:any)=>n.props?.['aria-label']==='Dettagli IVA');assert.ok(details);await details.props.onClick();await h.settle();assert.equal(h.state.editor.readonly,true);assert.equal(h.byId('taxclass-name').props.disabled,true);assert.equal(h.find((n:any)=>n.props?.form==='taxclass-editor-form'),undefined);assert.equal(h.find((n:any)=>String(n.props?.['aria-label']).startsWith('Disattiva ')),undefined);h.unmount();
});
test('deactivation confirmation posts only original revision and verifies active-state readback',async()=>{
 let persisted={...record};const h=harness({},(path,method)=>{if(method==='POST'){persisted={...record,is_active:false,version:5};return persisted;}if(path.startsWith('/tax/item-classifications/r'))return persisted;},{...session,permissions:['tax-item-classifications.read','tax-item-classifications.deactivate']});await h.settle();h.find((n:any)=>n.props?.['aria-label']==='Disattiva IVA').props.onClick();await h.settle();assert.equal(h.calls.some(c=>c.method==='POST'),false);h.find((n:any)=>n.props?.onClick&&n.props.children==='Disattiva').props.onClick();await h.settle();const post=h.calls.find(c=>c.method==='POST')!;assert.ok(post.path.startsWith('/tax/item-classifications/r/deactivate?'));assert.deepEqual(JSON.parse(JSON.stringify(post.body)),{expectedVersion:4});assert.equal(h.storage.has(h.key+':pending'),false);h.unmount();
});
test('server canonical text is verified against the accepted mutation response, not rejected as uncertain',async()=>{
 let persisted={...record};const h=harness({editor:{...draft(),values:{...draft().values,name:' Beni ',description:' Descrizione '}}},(path,method,body)=>{if(method==='PUT'){persisted={...record,...body.values,name:body.values.name.trim(),description:body.values.description.trim(),version:5};return persisted;}if(path.startsWith('/tax/item-classifications/r'))return persisted;});await h.settle();h.byId('taxclass-editor-form').props.onSubmit({preventDefault(){}});await h.settle();assert.equal(h.storage.has(h.key+':pending'),false);assert.equal(h.state.editor,null);h.unmount();
});

test('same existing TaxManagement route mounts real classifications for either child-only reader with no phase-one requests',async()=>{
 for(const kind of ['item','partner'] as const){const resource='tax-'+kind+'-classifications';const identity={...session,permissions:[resource+'.read']};const h=harness({},()=>undefined,identity,new Map(),kind,true);await h.settle();assert.ok(h.byId('taxclass-table'));assert.equal(h.byTest('tax-tab-'+kind+'-classifications').props['aria-selected'],true);assert.equal(h.calls.some(c=>/^\/tax\/(codes|types|nature-codes|lookups|countries)(?:[?]|$)/.test(c.path)),false);assert.equal(h.byId('tax-new'),undefined);h.unmount();}
});

test('a transition conflict keeps its original revision and shows the authoritative record',async()=>{
 let conflict=false;const h=harness({},(path,method)=>{if(method==='POST'){conflict=true;throw new ErrorResponse('tax_classification_stale_version',409);}if(conflict&&path.startsWith('/tax/item-classifications/r'))return {...record,version:5,name:'Stato corrente'};});await h.settle();h.find((n:any)=>n.props?.['aria-label']==='Disattiva IVA').props.onClick();await h.settle();h.find((n:any)=>n.props?.onClick&&n.props.children==='Disattiva').props.onClick();await h.settle();assert.equal(h.state.transition.version,4);assert.ok(h.find((n:any)=>n.type==='pre'&&String(n.props.children).includes('Stato corrente')));h.unmount();
});

test('explicitly closing a stale draft permits a new authoritative edit without silently advancing the old one',async()=>{
 const h=harness({editor:{...draft(),expectedVersion:3,original:{...record,version:3}}});await h.settle();assert.equal(h.state.editor.expectedVersion,3);assert.equal(h.find((n:any)=>n.props?.form==='taxclass-editor-form').props.disabled,true);h.find((n:any)=>n.props?.onClick&&n.props.children==='Annulla').props.onClick();await h.settle();const edit=h.find((n:any)=>n.props?.['aria-label']==='Modifica IVA');assert.equal(edit.props.disabled,false);await edit.props.onClick();await h.settle();assert.equal(h.state.editor.expectedVersion,4);assert.equal(h.state.editor.values.name,'IVA');h.unmount();
});

test('both template families install explicitly, verify scoped codes, report installed and skipped without validity dates',async()=>{
 const codes={item:['GENERAL_GOODS','GENERAL_SERVICES','FOOD','BOOKS','MEDICAL_GOODS','DIGITAL_SERVICES','REPAIR_SERVICES','TRANSPORT_SERVICES','INTELLECTUAL_PROPERTY','ANCILLARY_CHARGES'],partner:['TAXABLE_PERSON','NON_TAXABLE_PERSON','UNKNOWN']};
 for(const kind of ['item','partner'] as const){let installed=false;const h=harness({},(path,method)=>{if(method==='POST'){installed=true;return {installed:codes[kind].length-1,skipped:1};}if(installed&&path.startsWith('/tax/classification-lookups'))return {countries:[{id:'it',iso_code:'IT',name:'Italia'}],types:[{id:'vat',code:'VAT',name:'IVA',is_active:true}],classifications:codes[kind].map((code,i)=>({...record,id:'template-'+i,code}))};},{...session,permissions:['tax-'+kind+'-classifications.read','tax-'+kind+'-classifications.install_templates']},new Map(),kind);await h.settle();h.byId('taxclassinstall').props.onClick();await h.settle();assert.equal(h.calls.some(c=>c.method!=='GET'),false);h.byId('taxclass-install-form').props.onSubmit({preventDefault(){}});await h.settle();assert.deepEqual(JSON.parse(JSON.stringify(h.calls.find(c=>c.method==='POST')!.body)),{country_id:'it',tax_type_id:'vat'});assert.equal(h.storage.has(h.key+':pending'),false);assert.equal(h.state.install,null);assert.ok(h.find((n:any)=>n.props?.role==='status'&&String(n.props.children).includes('Ignorati: 1')));h.unmount();}
});
test('reactivation requires reactivation authority and its own expected revision',async()=>{
 let persisted={...record,is_active:false};const h=harness({},(path,method)=>{if(method==='POST'){persisted={...record,is_active:true,version:5};return persisted;}if(path.startsWith('/tax/item-classifications'))return path.startsWith('/tax/item-classifications/r')?persisted:{items:[persisted],total:1};},{...session,permissions:['tax-item-classifications.read','tax-item-classifications.reactivate']});await h.settle();assert.equal(h.find((n:any)=>n.props?.['aria-label']==='Disattiva IVA'),undefined);h.find((n:any)=>n.props?.['aria-label']==='Riattiva IVA').props.onClick();await h.settle();h.find((n:any)=>n.props?.onClick&&n.props.children==='Riattiva').props.onClick();await h.settle();const post=h.calls.find(c=>c.method==='POST')!;assert.ok(post.path.startsWith('/tax/item-classifications/r/reactivate?'));assert.deepEqual(JSON.parse(JSON.stringify(post.body)),{expectedVersion:4});assert.equal(h.storage.has(h.key+':pending'),false);h.unmount();
});
