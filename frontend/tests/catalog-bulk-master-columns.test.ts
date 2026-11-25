import test from 'node:test';
import assert from 'node:assert/strict';
import * as catalog from '../lib/catalog.ts';
import {harness,context} from './catalog-companies-interaction.test.ts';
const columns=['code','name','item_type_id','category_id','base_uom_id','brand_id','status'];
const refs={types:[{id:'ty',name:'Historic type',is_active:false}],categories:[{id:'root',name:'Parent',parent_id:null},{id:'cat',name:'Child',parent_id:'root'}],units:[{id:'kg',name:'Kilogram'}],brands:[{id:'brand',name:'Historic brand',is_active:false}],numbering:{}};
const row={...context.item,id:'i',item_type_id:'ty',category_id:'cat',base_uom_id:'kg',brand_id:'brand'};
function nodes(tree:any,name:string):any[]{if(!tree||typeof tree!=='object')return [];if(Array.isArray(tree))return tree.flatMap(n=>nodes(n,name));return [...(tree.type?.name===name?[tree]:[]),...nodes(tree.props?.children,name)];}
test('master and bulk share the exact item data projection and missing references never expose IDs',()=>{
 assert.deepEqual(catalog.catalogItemColumns,columns);
 assert.deepEqual(columns.map(c=>catalog.catalogItemText(row,c,refs)),['I','Item','Historic type','Parent / Child','Kilogram','Historic brand','SUSPENDED']);
 assert.equal(catalog.catalogItemText({...row,brand_id:'unavailable'},'brand_id',refs),'—');
});
test('bulk displays all master data columns without row actions and fetches authorized references once per page, not per row',async()=>{
 const h=harness({handler:path=>path==='/catalog/item-options'?refs:path.startsWith('/catalog/items?')?{items:[row],total:1,page:1,pageSize:25}:undefined});await h.settle();await h.click('catalog-company-bulk');
 const table=h.byId('catalog-bulk-items-table');assert.equal(nodes(table,'TableHead').length,8);assert.deepEqual(nodes(table,'TableHead').slice(1).map(n=>n.props.children),['Code','Name','Item type','Category','Base unit of measure','Brand','Status']);
 const cells=nodes(table,'TableCell');assert.deepEqual(cells.slice(1,7).map(n=>n.props.children),['I','Item','Historic type','Parent / Child','Kilogram','Historic brand']);assert.equal(cells.at(-1).props.kind,'status');assert.equal(nodes(table,'TableHead').some(n=>n.props.kind==='actions'),false);
 assert.equal(h.calls.filter(c=>c.path==='/catalog/item-options').length,1);assert.equal(h.calls.some(c=>/\/catalog\/(types|brands|categories|units)\//.test(c.path)),false);h.unmount();
});
