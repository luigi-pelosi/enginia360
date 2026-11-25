import assert from 'node:assert/strict';
import test from 'node:test';
import {catalogHarness,findCatalog} from './catalog-harness.ts';
import {itemHarness,root} from './catalog-items-harness.ts';

function nodes(tree:any,name:string):any[]{const out:any[]=[];function walk(n:any){if(!n||typeof n!=='object')return;if(n.type?.name===name)out.push(n);for(const c of [n.props?.children].flat(Infinity))walk(c);}walk(tree);return out;}
test('item list exposes status and action semantics and persists compact filter expansion',async()=>{
 const h=itemHarness();await h.settle();
 const table=h.byId('catalog-item-table');
 assert.deepEqual(nodes(table,'TableHead').map(n=>n.props.kind??'text'),['text','text','text','text','text','text','status','actions']);
 assert.deepEqual(nodes(table,'TableCell').map(n=>n.props.kind??'text'),['text','text','text','text','text','text','status','actions']);
 const bar=h.find(n=>n.type?.name==='FilterBar');assert.ok(bar,'shared compact FilterBar');
 assert.deepEqual(Array.from(bar.props.fields,(f:any)=>[f.key,f.minWidth,!!f.grow]),[['search',200,true],['status',130,false],['itemTypeId',180,false]]);
 assert.equal(bar.props.expanded,false);bar.props.onExpandedChange(true);await h.settle();assert.equal(h.state.filtersExpanded,true);
 const restored=itemHarness(undefined,{storage:h.storage});await restored.settle();assert.equal(restored.find(n=>n.type?.name==='FilterBar').props.expanded,true);
 assert.equal(h.state.filterVersion,2);assert.equal(h.state.status,'ACTIVE');assert.equal(h.pending,null);
});
test('item child tables classify primary flags and unit ratios',async()=>{
 const h=itemHarness(undefined,{record:root({identifiers:[{id:'i',identifier_type:'OEM',value:'001',uom_id:null,is_primary:true}],units:[{id:'u',uom_id:'cf',conversion_numerator:'2',conversion_denominator:'1',is_active:true}]})});await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();
 for(const [tab,kinds] of [['identifiers',['text','text','text','status','actions']],['units',['text','number','number','status','actions']]] as const){await h.click('item-tab-'+tab);assert.deepEqual(nodes(h.byId('item-'+tab+'-table'),'TableHead').map(n=>n.props.kind??'text'),kinds);assert.deepEqual(nodes(h.byId('item-'+tab+'-table'),'TableCell').map(n=>n.props.kind??'text'),kinds);}
});
test('configuration filters and numeric/status columns share the compact contract',async()=>{
 for(const resource of ['catalog-types','catalog-units','catalog-numbering']){
  const h=catalogHarness(resource,(path)=>path==='/session'?undefined:resource==='catalog-numbering'?{mode:'AUTO',prefix:'A',nextNumber:2,version:1}:{items:[{id:'r',name:'R',code:'001',kind:'GOOD',dimension:'MASS',conversion_scope:'UNIVERSAL',decimal_places:3,is_active:true}],total:1});await h.settle();
  const bar=findCatalog(h.tree,n=>n.type?.name==='FilterBar');assert.ok(bar,'shared compact FilterBar for '+resource);assert.deepEqual(Array.from(bar.props.fields,(f:any)=>f.key),resource==='catalog-numbering'||resource==='catalog-types'?['search','kind']:['search']);assert.equal(bar.props.expanded,false);bar.props.onExpandedChange(true);await h.settle();assert.equal(h.state.filtersExpanded,true);
  const heads=nodes(h.byId('catalog-table'),'TableHead');assert.equal(heads.at(-1).props.kind,'actions');
  if(resource==='catalog-units')assert.deepEqual(heads.map(n=>n.props.kind??'text'),['text','text','text','text','number','status','actions']);
  if(resource==='catalog-numbering')assert.equal(heads.at(-2).props.kind,'number');
 }
});
