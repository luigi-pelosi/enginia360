import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import {createTranslator} from 'next-intl';
import ts from 'typescript';
import * as items from '../lib/catalog-items.ts';
import {catalogKey} from '../lib/catalog.ts';
import {itemHarness,itemSession,itemOptions,root,CatalogApiError,findCatalog} from './catalog-items-harness.ts';
const metadata=[{id:'a',name:'Company A',code:null,is_enabled:true,permissions:['read','create']},{id:'b',name:'Company B',code:null,is_enabled:true,permissions:['read','create']},{id:'denied',name:'Denied',code:null,is_enabled:true,permissions:['create']}];
const session={...itemSession,permissions:[...itemSession.permissions,'catalog-item-companies.read','catalog-item-companies.create']};
const options={...itemOptions,types:itemOptions.types.map(row=>({...row,default_sellable:true,default_purchasable:false,default_track_stock:row.kind==='GOOD'}))};
function restoredEditor(overrides:Partial<items.ItemEditor>={}){
 const editor={...items.itemEditor(root({id:'',version:0,code:'A1'})),statusDraft:'SUSPENDED' as const,companyDrafts:[{company_id:'a',values:items.itemCompanyInitial(options.types[0],'GOOD')}],...overrides};
 const key=catalogKey(session.id,session.tenantId!,'catalog-items');
 return new Map([[key,JSON.stringify({...items.itemDefaults,editor})]]);
}
test('explicit GOOD to non-GOOD selection preserves association and disables its stock flag',async()=>{
 const h=itemHarness(path=>path.startsWith('/catalog/item-companies/options')?{items:metadata}:undefined,{session,options,storage:restoredEditor()});await h.settle();
 await h.select('item-type','service');assert.equal(h.state.editor!.companyDrafts![0].company_id,'a');assert.equal(h.state.editor!.companyDrafts![0].values.track_stock,false);h.unmount();
});
test('removed local unit blocks main Save with specific validation and retains company default',async()=>{
 const draft={company_id:'a',values:{...items.itemCompanyInitial(options.types[0],'GOOD'),default_sales_uom_id:'cf'}};
 const h=itemHarness(path=>path.startsWith('/catalog/item-companies/options')?{items:metadata}:undefined,{session,options,storage:restoredEditor({companyDrafts:[draft]})});await h.settle();await h.submit();
 assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);assert.equal(h.state.tab,'companies');assert.equal(h.state.editor!.companyDrafts![0].values.default_sales_uom_id,'cf');
 assert.match(JSON.stringify(h.byId('item-field-error')),/unità predefinita aziendale/);h.unmount();
});
test('removing a staged item unit does not clear company defaults and prevents root POST',async()=>{
 const draft={company_id:'a',values:{...items.itemCompanyInitial(options.types[0],'GOOD'),default_sales_uom_id:'cf'}};
 const record=root({id:'',version:0,units:[{id:'unit-local',uom_id:'cf',conversion_numerator:'12',conversion_denominator:'1',is_active:true}]});
 const h=itemHarness(path=>path.startsWith('/catalog/item-companies/options')?{items:metadata}:undefined,{session,options,storage:restoredEditor({record,companyDrafts:[draft]})});await h.settle();await h.click('item-tab-units');
 h.action('Elimina Carton').props.onClick();await h.settle();await h.submit(true);assert.equal(h.state.editor!.record.units.length,0);assert.equal(h.state.editor!.companyDrafts![0].values.default_sales_uom_id,'cf');
 await h.submit();assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);assert.equal(h.state.tab,'companies');assert.match(JSON.stringify(h.byId('item-field-error')),/unità predefinita aziendale/);h.unmount();
});
test('main Save rechecks current company authority before the root POST',async()=>{
 let revoked=false;
 const h=itemHarness(path=>path.startsWith('/catalog/item-companies/options')?{items:revoked?[]:metadata}:undefined,{session,options,storage:restoredEditor()});await h.settle();revoked=true;await h.submit();
 assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);assert.ok(h.calls.filter(c=>c.path.startsWith('/catalog/item-companies/options')).length>=2);assert.equal(h.state.editor!.companyDrafts!.length,1);assert.equal(h.pending,null);h.unmount();
});

test('main creation posts both companies once; only root Save asks for activation',async()=>{
 const companyDrafts=['a','b'].map(company_id=>({company_id,values:{...items.itemCompanyInitial(options.types[0],'GOOD'),is_purchasable:company_id==='b'}}));
 const h=itemHarness((path,method)=>path.startsWith('/catalog/item-companies/options')?{items:metadata}:method==='POST'?root():undefined,{session,options,storage:restoredEditor({companyDrafts,statusDraft:'ACTIVE'})});await h.settle();await h.submit();
 assert.ok(h.byId('item-activation-confirm'));assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
 await h.click('item-activation-confirm');
 const writes=h.calls.filter(c=>c.method!=='GET');assert.equal(writes.length,1);assert.equal(writes[0].method,'POST');assert.match(writes[0].path,/^\/catalog\/items\?/);
 assert.equal(JSON.stringify(writes[0].body.companies),JSON.stringify(companyDrafts));assert.equal(h.pending,null);assert.equal(h.state.editor,null);
 assert.ok(h.calls.some(c=>c.path.startsWith('/catalog/items/item-a')));assert.equal(h.calls.some(c=>c.path.includes('/item-options/')),false);h.unmount();
});
test('uncertain root creation restores the full companies body without replay or child requests',async()=>{
 const h=itemHarness((path,method)=>{if(path.startsWith('/catalog/item-companies/options'))return {items:metadata};if(method==='POST')throw new CatalogApiError('network_error',0);},{session,options,storage:restoredEditor()});await h.settle();await h.submit();
 assert.ok(h.pending);assert.equal((h.pending.body as any).companies[0].company_id,'a');assert.equal(h.calls.filter(c=>c.method!=='GET').length,1);
 const again=itemHarness(path=>path.startsWith('/catalog/item-companies/options')?{items:metadata}:undefined,{session,options,storage:h.storage});await again.settle();
 assert.equal(JSON.stringify(again.pending!.body),JSON.stringify(h.pending.body));assert.equal(again.calls.filter(c=>c.method!=='GET').length,0);assert.equal(again.byId('catalog-item-new').props.disabled,true);
 assert.equal(again.calls.some(c=>c.path.includes('/item-options/')),false);h.unmount();again.unmount();
});
test('revoked company create permission preserves restored drafts and blocks root submission',async()=>{
 const revoked={...session,permissions:session.permissions.filter(p=>p!=='catalog-item-companies.create')};
 const h=itemHarness(path=>path==='/session'?revoked:undefined,{session:revoked,options,storage:restoredEditor()});await h.settle();await h.submit();
 assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);assert.equal(h.state.editor!.companyDrafts![0].company_id,'a');assert.equal(h.byId('item-tab-companies'),undefined);h.unmount();
});
function childHarness(props:()=>any){
 const require=createRequire(import.meta.url),slots:any[]=[];let cursor=0,tree:any;
 const module={exports:{} as any},messages=JSON.parse(readFileSync(new URL('../messages/it.json',import.meta.url),'utf8'));
 function resolve(name:string):any {
  if(name==='react')return {...React,useState:(initial:any)=>{const n=cursor++;if(!(n in slots))slots[n]=typeof initial==='function'?initial():initial;return [slots[n],(next:any)=>{slots[n]=typeof next==='function'?next(slots[n]):next;}];}};
  if(name==='next-intl')return {useTranslations:(namespace:string)=>createTranslator({locale:'it',messages,namespace,onError:(e:any)=>{throw e;}})};
  if(name==='@/lib/catalog-items')return items;
  if(name.startsWith('@/components/ui/'))return new Proxy({},{get:(_,key)=>{const component=(props:any)=>React.createElement('div',props);Object.defineProperty(component,'name',{value:String(key)});return component;}});
  return require(name);
 }
 const source=readFileSync(new URL('../components/catalog-item-company-drafts.tsx',import.meta.url),'utf8');
 runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module,exports:module.exports,require:resolve,structuredClone,console});
 function render(){cursor=0;tree=module.exports.CatalogItemCompanyDrafts(props());return tree;}
 const find=(fn:(n:any)=>boolean)=>findCatalog(tree,fn),byId=(id:string)=>find(n=>n.props?.id===id);
 function click(id:string){const n=byId(id);assert.ok(n,'Missing '+id);assert.ok(!n.props.disabled,'Disabled '+id);n.props.onClick();render();}
 function select(id:string,value:string){const n=byId(id),parent=find(p=>p.props?.onValueChange&&findCatalog(p,c=>c===n));assert.ok(!parent.props.disabled);parent.props.onValueChange(value);render();}
 function toggle(id:string,value:boolean){const n=byId(id);assert.ok(!n.props.disabled);n.props.onCheckedChange(value);render();}
 function submit(){const form=find(n=>n.type==='form');assert.ok(form);let stopped=false;form.props.onSubmit({preventDefault(){},stopPropagation(){stopped=true;}});assert.ok(stopped);render();}
 render();return {render,byId,find,click,select,toggle,submit};
}
test('draft company table uses status semantics for flags and fixed centered actions',()=>{
 const props={companyDrafts:[{company_id:'a',values:items.itemCompanyInitial(options.types[0],'GOOD')}],companyOptions:metadata,types:options.types,units:options.units,record:root(),selectedTypeId:'good',kind:'GOOD' as const,baseId:'g',disabled:false,loading:false,onChange:()=>{}};
 const child=childHarness(()=>props),table=child.byId('catalog-company-drafts-table');
 for(const name of ['TableHead','TableCell']){const kinds:string[]=[];function walk(n:any){if(!n||typeof n!=='object')return;if(n.type?.name===name)kinds.push(n.props.kind??'text');for(const c of [n.props?.children].flat(Infinity))walk(c);}walk(table);assert.deepEqual(kinds,['text','status','status','text','text','actions']);}
});
for(const kind of ['GOOD','SERVICE','INTANGIBLE','CHARGE'] as const)test(`${kind}: local dialog uses parent nature and mandatory first eligible company`,()=>{
 const props={companyDrafts:[] as items.ItemCompanyDraft[],companyOptions:metadata,types:options.types,units:options.units,record:root({kind:'GOOD'}),selectedTypeId:'good',kind,baseId:'g',disabled:false,loading:false,onChange:(rows:items.ItemCompanyDraft[])=>{props.companyDrafts=rows;}};
 const child=childHarness(()=>props);child.click('catalog-company-draft-add');
 assert.equal(child.find(n=>n.props?.onValueChange&&findCatalog(n,c=>c.props?.id==='catalog-company-draft-company')).props.value,'a');
 assert.equal(child.find(n=>n.props?.htmlFor==='catalog-company-draft-company').props.required,true);
 const stock=child.byId('catalog-company-draft-track-stock');assert.equal(stock.props.checked,kind==='GOOD');assert.equal(stock.props.disabled,kind!=='GOOD');
 child.submit();assert.equal(props.companyDrafts[0].values.track_stock,kind==='GOOD');
});
test('local unit picker follows selected base and active local rows, keeps removed defaults invalid until explicit correction',()=>{
 const props={companyDrafts:[] as items.ItemCompanyDraft[],companyOptions:metadata,types:options.types,units:[...options.units,{id:'disabled',name:'Disabled',is_active:false}],record:root({base_uom_id:'kg',units:[{id:'local',uom_id:'cf',is_active:true},{id:'off',uom_id:'m',is_active:false}]}),selectedTypeId:'good',kind:'GOOD' as const,baseId:'g',disabled:false,loading:false,onChange:(rows:items.ItemCompanyDraft[])=>{props.companyDrafts=rows;}};
 const child=childHarness(()=>props);child.click('catalog-company-draft-add');
 const unitSelect=()=>child.find(n=>n.props?.onValueChange&&findCatalog(n,c=>c.props?.id==='catalog-company-draft-default-sales-uom-id'));
 const choices:any[]=[];function collect(n:any){if(!n||typeof n!=='object')return;if(n.type?.name==='SelectItem')choices.push(n.props);React.Children.forEach(n.props?.children,collect);}collect(unitSelect());
 assert.deepEqual(choices.map(c=>c.value),['BASE','g','cf']);
 child.select('catalog-company-draft-default-sales-uom-id','cf');props.record={...props.record,units:[]};child.render();child.submit();assert.equal(props.companyDrafts.length,0);assert.ok(child.find(n=>n.props?.role==='alert'));
 child.select('catalog-company-draft-default-sales-uom-id','BASE');child.submit();assert.equal(props.companyDrafts[0].values.default_sales_uom_id,null);
});
test('recovered non-GOOD stock draft stays visible and can be explicitly corrected without removing its company',()=>{
 const draft={company_id:'a',values:items.itemCompanyInitial(options.types[0],'GOOD')};
 const props={companyDrafts:[draft],companyOptions:metadata,types:options.types,units:options.units,record:root(),selectedTypeId:'service',kind:'SERVICE' as const,baseId:'g',disabled:false,loading:false,onChange:(rows:items.ItemCompanyDraft[])=>{props.companyDrafts=rows;}};
 const child=childHarness(()=>props);child.click('catalog-company-draft-edit-a');assert.equal(child.byId('catalog-company-draft-track-stock').props.checked,true);assert.equal(child.byId('catalog-company-draft-track-stock').props.disabled,false);
 child.toggle('catalog-company-draft-track-stock',false);child.submit();assert.equal(props.companyDrafts[0].company_id,'a');assert.equal(props.companyDrafts[0].values.track_stock,false);
});
test('unsaved company modal confirms locally with copied defaults and no HTTP mutations',async()=>{
 const h=itemHarness(path=>path.startsWith('/catalog/item-companies/options')?{items:metadata}:undefined,{session,options});await h.settle();await h.click('catalog-item-new');await h.click('item-tab-companies');
 const props=()=>h.find(n=>Array.isArray(n.props?.companyDrafts)&&typeof n.props?.onChange==='function')?.props;
 assert.ok(props(),'new root renders local company editor instead of persisted company component');
 const child=childHarness(props);child.click('catalog-company-draft-add');
 assert.ok(child.find(n=>n.props?.['data-testid']==='catalog-company-draft-editor'));
 assert.equal(child.byId('catalog-company-draft-track-stock').props.checked,true);
 child.toggle('catalog-company-draft-is-sellable',false);child.submit();await h.settle();child.render();
 assert.equal(h.state.editor!.companyDrafts!.length,1);assert.equal(h.state.editor!.companyDrafts![0].company_id,'a');
 assert.equal(h.state.editor!.companyDrafts![0].values.is_sellable,false);
 assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
 child.click('catalog-company-draft-add');child.submit();await h.settle();child.render();
 assert.deepEqual(Array.from(h.state.editor!.companyDrafts!,r=>r.company_id),['a','b']);
 assert.equal(h.state.editor!.companyDrafts![1].values.is_sellable,true);
 child.click('catalog-company-draft-edit-a');child.toggle('catalog-company-draft-is-purchasable',true);child.submit();await h.settle();child.render();
 assert.equal(h.state.editor!.companyDrafts![0].values.is_purchasable,true);
 const restored=itemHarness(path=>path.startsWith('/catalog/item-companies/options')?{items:metadata}:undefined,{session,options,storage:h.storage});await restored.settle();
 assert.equal(JSON.stringify(restored.state.editor!.companyDrafts),JSON.stringify(h.state.editor!.companyDrafts));
 assert.ok(restored.calls.some(c=>c.path.startsWith('/catalog/item-companies/options')));
 child.click('catalog-company-draft-remove-b');await h.settle();assert.equal(h.state.editor!.companyDrafts!.length,1);
 await h.click('item-cancel');assert.equal(h.state.editor,null);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
 h.unmount();restored.unmount();
});
