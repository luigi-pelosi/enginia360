import test from 'node:test';
import assert from 'node:assert/strict';
import {renderToStaticMarkup} from 'react-dom/server';
import {ApiError} from '../lib/api.ts';
import {taxProfileKey,type TaxProfileDraft} from '../lib/tax-profiles.ts';
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
 const messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));messages.taxProfiles??={title:'Fiscalità'};
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

function partnerHarness(file='business-partner-workspace', locale='en', respond: (path:string, method:string, body:any)=>any=()=>({}), storage?: Storage) {
 if (!storage) {const entries=new Map<string,string>(); storage={getItem:k=>entries.get(k)??null,setItem:(k,v)=>{entries.set(k,v);},removeItem:k=>{entries.delete(k);},clear:()=>entries.clear(),key:i=>[...entries.keys()][i]??null,get length(){return entries.size;}};}
 const require=createRequire(import.meta.url), messages={...JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8')),taxProfiles:{title:'Fiscalità'}};
 let index=0;
 const state:any[]=[], refs:any[]=[], dependencies:any[][]=[], effects:Array<()=>any>=[], calls:Array<{path:string;method:string;body:any}>=[];
 const uiComponents=new Map<PropertyKey,any>();
 const ui=new Proxy({}, {get:(_target,name)=>{if(uiComponents.has(name))return uiComponents.get(name);const component=(props:any)=>{
  const tag=name==='Button'?'button':name==='Input'?'input':name==='Textarea'?'textarea':name==='Label'?'label':name==='Checkbox'?'input':'div';
  const safe=Object.fromEntries(Object.entries(props).filter(([key])=>['children','disabled','className','id','value','checked','htmlFor','type','required','pattern','readOnly','min','max'].includes(key)||key.startsWith('aria-')));
  if(tag==='input') {delete safe.children;safe.readOnly=true;}
  return React.createElement(tag,safe,name==='FilterBar'?props.fields.map((field:any)=>React.createElement(React.Fragment,{key:field.key},field.content)):safe.children);
 };uiComponents.set(name,component);return component;}});
 const modules:Record<string,any>={};
 const resolve=(name:string):any=>{
  if(name==='react') return {...React,useState:(initial:any)=>{const i=index++;if(!(i in state)) state[i]=typeof initial==='function'?initial():initial;return [state[i],(next:any)=>{state[i]=typeof next==='function'?next(state[i]):next;}];},useRef:(initial:any)=>{const i=index++;return refs[i]??=( {current:initial});},useEffect:(effect:()=>any,deps:any[])=>{const i=index++;if(!dependencies[i]||deps.some((v,j)=>v!==dependencies[i][j])){dependencies[i]=deps;effects.push(effect);}},useMemo:(fn:()=>any)=>fn(),useCallback:(fn:any)=>fn};
  if(name==='next-intl') return {useLocale:()=>locale,useTranslations:(namespace:string)=>createTranslator({locale,messages,namespace})};
  if(name==='@/lib/model') return model;
  if(name==='@/lib/api') return {ApiError,api:async(path:string,method='GET',body?:any)=>{calls.push({path,method,body});return respond(path,method,body);}};
  if(name.startsWith('@/components/ui/')) return ui;
  if(name.startsWith('@/')) {
   if(modules[name]) return modules[name];
   const source=readFileSync(new URL(`../${name.slice(2)}${name.startsWith('@/components/')?'.tsx':'.ts'}`,import.meta.url),'utf8'), module={exports:{}};
   const code=ts.transpileModule(source+(name==='@/components/workspace'?'\nexport {RecordEditor};':''),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
   runInNewContext(code,{module,exports:module.exports,require:resolve,console,setTimeout,clearTimeout,AbortController,Intl,URL,URLSearchParams,sessionStorage:storage});modules[name]=module.exports;return module.exports;
  }
  return require(name);
 };
 const components=resolve(`@/components/${file}`);
 return {calls,state,components,
  tree:(component:string,props:any)=>{index=0;return components[component](props);},
  render:(component:string,props:any)=>{index=0;return renderToStaticMarkup(React.createElement(components[component],props));},
  flush:async()=>{const pending=effects.splice(0);for(const effect of pending)effect();await new Promise(resolve=>setImmediate(resolve));}
 };
}

const profileDraft:TaxProfileDraft={country_id:'it',tax_type_id:'vat',item_tax_classification_id:'std',valid_from:'2026-01-01',valid_to:null};
const profileNode=(tree:any)=>findCatalog(tree,n=>n.props?.kind&&'subjectId' in n.props&&typeof n.props?.onStagedChange==='function');
test('item read-only details allow independent tax profile actions without base update',async()=>{
 const h=itemHarness(undefined,{session:{...itemSession,permissions:['catalog-items.read','tax-item-profiles.read','tax-item-profiles.assign']}});await h.settle();await h.action('Dettagli Item A').props.onClick();await h.settle();assert.ok(h.byId('item-tab-taxation'));await h.click('item-tab-taxation');
 const child=profileNode(h.tree);assert.equal(h.state.editor!.readonly,true);assert.equal(child.props.disabled,false);assert.equal(child.props.subjectId,'item-a');assert.equal(h.calls.some(c=>c.method==='POST'),false);h.unmount();
});
test('new item stages tax profiles in parent recovery and sends them only in first POST',async()=>{
 const record=root({id:'created-item',version:1});
 const h=itemHarness((path,method)=>method==='POST'||path.startsWith('/catalog/items/created-item')?record:undefined,{session:{...itemSession,permissions:[...itemSession.permissions,'tax-item-profiles.assign']}});await h.settle();await h.click('catalog-item-new');await h.click('item-tab-taxation');profileNode(h.tree).props.onStagedChange([profileDraft]);await h.settle();
 assert.deepEqual(h.state.editor!.taxProfiles,[profileDraft]);const restored=itemHarness(undefined,{storage:h.storage,session:{...itemSession,permissions:[...itemSession.permissions,'tax-item-profiles.assign']}});await restored.settle();assert.deepEqual(restored.state.editor!.taxProfiles,[profileDraft]);assert.equal(restored.state.tab,'taxation');restored.unmount();
 await h.click('item-tab-general');await h.edit('item-name','New item');await h.edit('item-code','NEW1');await h.select('item-category-id','category');await h.select('item-base-uom','kg');await h.select('item-status','SUSPENDED');
 const childKey=taxProfileKey(itemSession.id,itemSession.tenantId!,'item','new');h.storage.set(childKey,JSON.stringify({editor:{values:profileDraft},pending:null}));await h.submit();
 const posts=h.calls.filter(c=>c.method==='POST');assert.equal(posts.length,1);assert.deepEqual(posts[0].body.taxProfiles,[profileDraft]);assert.equal(h.storage.has(childKey),false);h.unmount();
});
test('item general PUT excludes any profile drafts even if recovered state contains them',async()=>{
 const h=itemHarness((path,method)=>method==='PUT'?root({version:5}):undefined);await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();h.state.editor!.taxProfiles=[profileDraft];await h.edit('item-name','Changed');await h.submit();
 const write=h.calls.find(c=>c.method==='PUT')!;assert.ok(write);assert.equal('taxProfiles' in write.body,false);assert.equal(write.body.expectedVersion,4);h.unmount();
});
const partnerIdentity={id:'u',username:'ada',displayName:'Ada',preferredLanguage:'it',tenantId:'t',isSuperAdmin:false,mustChangePassword:false,permissions:['business-partners.read','business-partners.create','tax-partner-profiles.assign']};
const partnerProps={session:partnerIdentity,tenantId:'t',id:null as string|null,scope:(path:string)=>path+(path.includes('?')?'&':'?')+'tenantId=t',onError:(e:any)=>e.code||e.message,onClose(){},onSaved(){}};
const findId=(tree:any,id:string)=>findCatalog(tree,n=>n.props?.id===id);
test('partner new staging is included atomically in first aggregate POST with assign but no profile read',async()=>{
 const h=partnerHarness('business-partner-workspace','it',()=>({id:'created-partner'}));let tree=h.tree('BusinessPartnerEditor',partnerProps);findId(tree,'bp-legal_name').props.onChange({target:{value:'Partner'}});tree=h.tree('BusinessPartnerEditor',partnerProps);findId(tree,'bp-tab-taxation').props.onClick();tree=h.tree('BusinessPartnerEditor',partnerProps);
 const draft={country_id:'it',tax_type_id:'vat',partner_tax_classification_id:'partner-standard',valid_from:'2026-01-01',valid_to:null};profileNode(tree).props.onStagedChange([draft]);tree=h.tree('BusinessPartnerEditor',partnerProps);await tree.props.onSubmit({preventDefault(){}});assert.equal(h.calls.filter(c=>c.method==='POST').length,1);assert.deepEqual(h.calls.find(c=>c.method==='POST')!.body.taxProfiles,[draft]);
});
test('partner read-only details expose enabled independent profile actions and no metadata writes',async()=>{
 const props={...partnerProps,id:'partner-a',session:{...partnerIdentity,permissions:['business-partners.read','tax-partner-profiles.read','tax-partner-profiles.schedule']}};
 const h=partnerHarness('business-partner-workspace','it',()=>({id:'partner-a',version:8,kind:'ORGANIZATION',status:'ACTIVE',legal_name:'Partner',tax_identifiers:[],addresses:[],contact_channels:[]}));h.tree('BusinessPartnerEditor',props);await h.flush();let tree=h.tree('BusinessPartnerEditor',props);findId(tree,'bp-tab-taxation').props.onClick();tree=h.tree('BusinessPartnerEditor',props);assert.equal(profileNode(tree).props.disabled,false);assert.equal(profileNode(tree).props.subjectId,'partner-a');assert.equal(h.calls.some(c=>c.method!=='GET'),false);
});
