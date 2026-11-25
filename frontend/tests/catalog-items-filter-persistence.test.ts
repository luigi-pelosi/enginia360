import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,itemSession} from './catalog-items-harness.ts';
import {catalogKey} from '../lib/catalog.ts';
const key=catalogKey(itemSession.id,itemSession.tenantId!,'catalog-items');
for(const status of ['ALL','ACTIVE','SUSPENDED','ARCHIVED']) test(`explicit ${status} survives refresh with matching query`,async()=>{
 const storage=new Map<string,string>();const h=itemHarness(()=>undefined,{storage});await h.settle();await h.select('catalog-item-filter-status',status);h.unmount();const r=itemHarness(()=>undefined,{storage});await r.settle();assert.equal(r.state.status,status);const query=r.calls.find(c=>c.path.startsWith('/catalog/items?'))!.path;assert.equal(new URLSearchParams(query.split('?')[1]).get('status'),status==='ALL'?'':status);
});
