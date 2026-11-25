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
test('single association copies defaults, nullable base units and keeps company B independently read-only',async()=>{
 const h=harness({itemId:'i'});await h.settle();await h.click('catalog-company-associate');
 assert.equal(h.find(n=>n.props?.onValueChange&&find(n,c=>c.props?.id==='catalog-company-company')).props.value,'a');
 assert.equal(h.byId('catalog-company-is-sellable').props.checked,true);
 assert.equal(h.byId('catalog-company-is-purchasable').props.checked,false);
 await h.toggle('catalog-company-is-purchasable',true);await h.submit();
 const put=h.calls.find(c=>c.method==='PUT');assert.equal(put.path,'/companies/a/catalog/items/i');assert.equal(put.body.expectedVersion,0);assert.equal(put.body.values.default_sales_uom_id,null);assert.equal(put.body.values.is_purchasable,true);
 assert.equal(h.calls.some(c=>c.path.startsWith('/data/companies')),false);
 h.unmount();
});
test('company-only reader filters associated rows, never fetches organization items and cannot edit company B',async()=>{
 const h=harness({permissions:['catalog-item-companies.read'],handler:(path)=>path.startsWith('/catalog/item-companies?')?{items:[row('b')],total:1,page:1,pageSize:25}:undefined});await h.settle();
 assert.ok(h.byId('catalog-company-view-b-i'));assert.equal(h.byId('catalog-company-edit-b-i'),null);assert.equal(h.byId('catalog-company-bulk'),null);
 await h.select('company-catalog-company','b');await h.select('company-catalog-enabled','DISABLED');
 assert.ok(h.calls.some(c=>c.path.includes('companyId=b')&&c.path.includes('enabled=DISABLED')));
 assert.equal(h.calls.some(c=>c.path.startsWith('/catalog/items')||c.path.startsWith('/data/companies')),false);h.unmount();
});
test('bulk explicitly selects several items and companies, keeps selection across search/pages and sends one Cartesian command',async()=>{
 let observedPending=false;
 const storage=new Map<string,string>();const h=harness({storage,handler:(path,method)=>{if(path.startsWith('/catalog/item-companies/options'))return {items:companies.map(o=>({...o,permissions:['read','create','update']}))};if(path.startsWith('/catalog/items?'))return {items:[{...context.item,id:path.includes('page=2&')?'j':'i'}],total:26,page:path.includes('page=2&')?2:1,pageSize:25};if(method==='POST'){observedPending=[...storage.keys()].some(k=>k.endsWith(':pending'));return {created:3,unchanged:1,items:[]};}}});await h.settle();assert.equal(h.calls.some(c=>c.path.startsWith('/catalog/items?')),false);
 await h.click('catalog-company-bulk');await h.toggle('catalog-bulk-company-b',true);await h.toggle('catalog-bulk-item-i',true);await h.click('catalog-bulk-next');await h.toggle('catalog-bulk-item-j',true);await h.click('catalog-bulk-previous');assert.equal(h.byId('catalog-bulk-item-i').props.checked,true);h.byId('catalog-bulk-search').props.onChange({target:{value:'Item'}});await h.settle();assert.equal(h.byId('catalog-bulk-item-i').props.checked,true);await h.submit();
 const post=h.calls.find(c=>c.method==='POST');assert.deepEqual(JSON.parse(JSON.stringify(post.body)),{itemIds:['i','j'],companyIds:['a','b']});assert.equal(observedPending,true);assert.equal(h.calls.filter(c=>c.method==='POST').length,1);h.unmount();
});
test('company config edit uses its own baseline, while another company remains read-only',async()=>{
 const h=harness({itemId:'i',permissions:['catalog-items.read','catalog-item-companies.read','catalog-item-companies.update'],handler:path=>path.startsWith('/catalog/items/i/companies')?{items:[row(),row('b')]}:undefined});await h.settle();assert.equal(h.byId('catalog-company-edit-b-i'),null);await h.click('catalog-company-edit-a-i');await h.toggle('catalog-company-is-enabled',false);await h.submit();
 const patch=h.calls.find(c=>c.method==='PATCH');assert.equal(patch.body.expectedVersion,1);assert.equal(patch.body.values.is_enabled,false);assert.equal(h.calls.some(c=>c.method==='PUT'&&c.path==='/catalog/items/i'),false);h.unmount();
});
test('lost response survives refresh without replay and requires authoritative review then acknowledgement',async()=>{
 const storage=new Map<string,string>();let sent=0;const handler=(path:string,method:string)=>{if(method==='PUT'){sent++;throw new ApiError('network',0);}return undefined;};
 const h=harness({itemId:'i',storage,handler});await h.settle();await h.click('catalog-company-associate');await h.submit();assert.equal(sent,1);assert.ok([...storage.keys()].some(k=>k.endsWith(':pending')));h.unmount();
 const recovered=harness({itemId:'i',storage,handler});await recovered.settle();assert.ok(recovered.byId('catalog-company-review'));assert.equal(recovered.byId('catalog-company-associate').props.disabled,true);assert.equal(recovered.byId('catalog-company-acknowledge'),null);assert.equal(sent,1);
 await recovered.click('catalog-company-review');assert.ok(recovered.byId('catalog-company-acknowledge'));await recovered.click('catalog-company-acknowledge');assert.equal([...storage.keys()].some(k=>k.endsWith(':pending')),false);assert.equal(sent,1);recovered.unmount();
});
test('stale version retains edited fields and baseline across refresh rather than silently adopting new token',async()=>{
 const storage=new Map<string,string>();let version=1;const handler=(path:string,method:string)=>{if(path.startsWith('/catalog/items/i/companies'))return {items:[row()]};if(method==='PATCH'){version=2;throw new ApiError('stale_version',409);}if(path.startsWith('/companies/')&&method==='GET')return row('a',{version});};
 const h=harness({itemId:'i',storage,handler});await h.settle();await h.click('catalog-company-edit-a-i');await h.toggle('catalog-company-is-purchasable',true);await h.submit();assert.equal(h.byId('catalog-company-save').props.disabled,true);h.unmount();
 const recovered=harness({itemId:'i',storage,handler});await recovered.settle();assert.equal(recovered.byId('catalog-company-is-purchasable').props.checked,true);assert.equal(recovered.byId('catalog-company-save').props.disabled,true);const saved=JSON.parse(storage.get('catalog:v1:user:tenant:catalog-item-companies:item:i')!);assert.equal(saved.editor.version,1);recovered.unmount();
});
test('revoking organization read hides a recovered bulk chooser without fetching global items',async()=>{
 const storage=new Map<string,string>();const h=harness({storage});await h.settle();await h.click('catalog-company-bulk');h.unmount();
 const recovered=harness({storage,permissions:['catalog-item-companies.read']});await recovered.settle();assert.equal(recovered.find(n=>n.props?.['data-testid']==='catalog-company-bulk-editor'),null);assert.equal(recovered.calls.some(c=>c.path.startsWith('/catalog/items?')),false);recovered.unmount();
});
test('archived item hides new association and bulk, but permits only disabling an existing company configuration',async()=>{
 const h=harness({itemId:'i',itemStatus:'ARCHIVED',handler:path=>path.startsWith('/catalog/items/i/companies')?{items:[row('a',{item_status:'ARCHIVED'})]}:path.startsWith('/catalog/item-companies/item-options')?{...context,item:{...context.item,status:'ARCHIVED'}}:undefined});await h.settle();assert.equal(h.byId('catalog-company-associate'),null);assert.equal(h.byId('catalog-company-bulk'),null);await h.click('catalog-company-edit-a-i');assert.equal(h.byId('catalog-company-is-sellable').props.disabled,true);assert.equal(h.byId('catalog-company-save').props.disabled,true);await h.toggle('catalog-company-is-enabled',false);await h.submit();assert.equal(h.calls.find(c=>c.method==='PATCH').body.values.is_enabled,false);h.unmount();
});
test('accepted mutation with failed readback stays frozen after refresh and never replays',async()=>{
 const storage=new Map<string,string>();let accepted=false,writes=0;
 const handler=(path:string,method:string)=>{if(method==='PUT'){accepted=true;writes++;return row();}if(accepted&&path.startsWith('/companies/'))throw new ApiError('network',0);};
 const h=harness({itemId:'i',storage,handler});await h.settle();await h.click('catalog-company-associate');await h.submit();const pending=JSON.parse(storage.get('catalog:v1:user:tenant:catalog-item-companies:item:i:pending')!);assert.equal(pending.committed,true);h.unmount();
 const recovered=harness({itemId:'i',storage,handler});await recovered.settle();assert.equal(writes,1);await recovered.click('catalog-company-review');assert.equal(recovered.byId('catalog-company-acknowledge'),null);assert.ok(storage.has('catalog:v1:user:tenant:catalog-item-companies:item:i:pending'));assert.equal(writes,1);recovered.unmount();
});
test('unavailable saved unit remains visible but cannot be newly selected',async()=>{
 const configured=row('a',{default_sales_uom_id:'old-unit'});
 const h=harness({itemId:'i',handler:(path,method)=>path.startsWith('/catalog/items/i/companies')?{items:[configured]}:path.startsWith('/companies/')&&method==='GET'?configured:undefined});await h.settle();await h.click('catalog-company-edit-a-i');const option=h.find(n=>n.type?.name==='SelectItem'&&n.props?.value==='old-unit');assert.ok(option,'saved unit must remain visible');assert.equal(option.props.disabled,true);h.unmount();
});
for(const side of ['items','companies'])test(`bulk refuses more than 100 selected ${side} even below Cartesian limit`,async()=>{
 const many=Array.from({length:101},(_,i)=>'id-'+i);
 const bulk={itemIds:side==='items'?many:['i'],companyIds:side==='companies'?many:['a'],search:'',page:1};
 const storage=new Map([['catalog:v1:user:tenant:catalog-item-companies',JSON.stringify({bulk})]]);
 const h=harness({storage});await h.settle();assert.equal(h.byId('catalog-bulk-save').props.disabled,true);
 await h.submit();assert.equal(h.calls.some(c=>c.method==='POST'),false);h.unmount();
});
test('company creation controls require readback authority for the exact company before sending writes',async()=>{
 const h=harness({itemId:'i',handler:path=>path.startsWith('/catalog/item-companies/options')?{items:companies.map(o=>({...o,permissions:o.id==='a'?['create']:['read']}))}:undefined});
 await h.settle();assert.equal(h.byId('catalog-company-associate'),null);assert.equal(h.byId('catalog-company-bulk'),null);
 assert.equal(h.calls.some(c=>c.method!=='GET'),false);h.unmount();
});
export {harness,row,context,companies,ApiError};
