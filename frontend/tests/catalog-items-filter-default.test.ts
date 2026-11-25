import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,itemSession,root} from './catalog-items-harness.ts';
import {catalogKey} from '../lib/catalog.ts';
const key=catalogKey(itemSession.id,itemSession.tenantId!,'catalog-items');
test('fresh list defaults to active and all types',async()=>{
 const h=itemHarness();await h.settle();assert.equal(h.state.status,'ACTIVE');assert.equal(h.state.itemTypeId,'ALL');assert.match(h.calls.find(c=>c.path.startsWith('/catalog/items?'))!.path,/status=ACTIVE&itemTypeId=/);
});
test('legacy implicit all migrates without losing editor or pending and explicit all survives refresh',async()=>{
 const editor={id:'item-a',record:root(),values:{name:'draft'},original:{name:'original'},version:4,readonly:false};
 const pending={marker:'keep'};const storage=new Map([[key,JSON.stringify({status:'ALL',kind:'SERVICE',page:3,search:'abc',editor})],[key+':pending',JSON.stringify(pending)]]);
 const h=itemHarness(()=>undefined,{storage});await h.settle();assert.equal(h.state.status,'ACTIVE');assert.equal(h.state.itemTypeId,'ALL');assert.equal(h.state.search,'abc');assert.equal(h.state.editor?.values.name,'draft');assert.equal((h.pending as any).marker,'keep');
 await h.select('catalog-item-filter-status','ALL');h.unmount();const refreshed=itemHarness(()=>undefined,{storage});await refreshed.settle();assert.equal(refreshed.state.status,'ALL');assert.equal(refreshed.state.itemTypeId,'ALL');
});
