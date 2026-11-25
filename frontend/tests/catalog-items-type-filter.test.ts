import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,itemSession,findCatalog} from './catalog-items-harness.ts';
import {catalogKey} from '../lib/catalog.ts';
const key=catalogKey(itemSession.id,itemSession.tenantId!,'catalog-items');
test('tenant item types including inactive are selectable, encoded and survive refresh',async()=>{
 const storage=new Map<string,string>();const h=itemHarness(()=>undefined,{storage});await h.settle();
 const trigger=h.byId('catalog-item-filter-itemTypeId');assert.ok(trigger);
 const select=h.find(n=>n.props?.onValueChange&&findCatalog(n,c=>c===trigger));
 const options:any[]=[];function visit(n:any){if(!n||typeof n!=='object')return;if(n.type?.name==='SelectItem')options.push([n.props.value,n.props.children]);for(const c of [n.props?.children].flat(Infinity))visit(c);}visit(select);
 assert.deepEqual(options,[['ALL','Tutti'],['good','Goods type'],['service','Service type'],['old','Old type']]);
 await h.select('catalog-item-filter-itemTypeId','old');h.unmount();const r=itemHarness(()=>undefined,{storage});await r.settle();assert.equal(r.state.itemTypeId,'old');const q=new URLSearchParams(r.calls.find(c=>c.path.startsWith('/catalog/items?'))!.path.split('?')[1]);assert.equal(q.get('itemTypeId'),'old');assert.equal(q.has('kind'),false);
});
test('legacy nature filter migrates to all and resets page while retaining draft',async()=>{
 const storage=new Map([[key,JSON.stringify({filterVersion:1,status:'SUSPENDED',kind:'SERVICE',page:4,search:'abc'})]]);const h=itemHarness(()=>undefined,{storage});await h.settle();assert.equal(h.state.itemTypeId,'ALL');assert.equal(h.state.page,1);assert.equal(h.state.status,'SUSPENDED');assert.equal(h.state.search,'abc');
});
