import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,itemOptions,root,findCatalog} from './catalog-items-harness.ts';
import {catalogKey} from '../lib/catalog.ts';
import type {ItemOptions} from '../lib/catalog-items.ts';
const kinds=['GOOD','INTANGIBLE','SERVICE','CHARGE'] as const;
const options:ItemOptions={...itemOptions,types:kinds.map(kind=>({id:kind,name:kind,kind,is_active:true})),numbering:{GOOD:{mode:'AUTO'},INTANGIBLE:{mode:'AUTO'},SERVICE:{mode:'AUTO'},CHARGE:{mode:'AUTO'}}};
test('item filter offers every nature',async()=>{const h=itemHarness(undefined,{options});await h.settle();const filter=h.find(n=>n.props?.onValueChange&&findCatalog(n,c=>c.props?.id==='catalog-item-filter-itemTypeId'));for(const kind of kinds)assert.ok(findCatalog(filter,n=>n.props?.value===kind));h.unmount();});
for(const kind of ['INTANGIBLE','CHARGE'] as const){
 test(`${kind} first valid type initializes kind, excludes physical tab and submits after confirmation`,async()=>{
 const refs={...options,types:[options.types.find(r=>r.kind===kind)!,...options.types]};const h=itemHarness((p,m,b)=>m==='POST'?root({kind,item_type_id:kind}):undefined,{options:refs});await h.settle();await h.click('catalog-item-new');assert.equal(h.state.editor!.record.kind,kind);assert.equal(h.state.editor!.values.item_type_id,kind);assert.equal(h.byId('item-tab-physical'),undefined);assert.ok(h.byId('item-tab-units'));await h.edit('item-name','New');await h.select('item-category-id','category');await h.select('item-base-uom','g');await h.submit();assert.equal(h.calls.some(c=>c.method==='POST'),false);assert.ok(h.byId('item-activation-confirm'));await h.click('item-activation-confirm');const body=h.calls.find(c=>c.method==='POST')!.body;assert.equal(body.values.item_type_id,kind);assert.equal(body.physicalData,undefined);h.unmount();
 });
 test(`${kind} switch refuses populated physical draft, then permits empty draft`,async()=>{
 const h=itemHarness(undefined,{options});await h.settle();await h.click('catalog-item-new');await h.click('item-tab-physical');await h.edit('item-net-weight','0');await h.click('item-tab-general');await h.select('item-type',kind);assert.equal(h.state.editor!.record.kind,'GOOD');assert.equal(h.state.editor!.physicalDraft!.net_weight,'0');await h.click('item-tab-physical');await h.edit('item-net-weight','');await h.click('item-tab-general');await h.select('item-type',kind);assert.equal(h.state.editor!.record.kind,kind);assert.equal(h.byId('item-tab-physical'),undefined);h.unmount();
 });
 test(`${kind} filter, search and page recover without writes`,async()=>{
 const h=itemHarness(undefined,{options});await h.settle();await h.select('catalog-item-filter-itemTypeId',kind);await h.edit('catalog-item-search','needle');h.unmount();const recovered=itemHarness(undefined,{options,storage:h.storage});await recovered.settle();assert.equal(recovered.state.itemTypeId,kind);assert.equal(recovered.state.search,'needle');assert.ok(recovered.calls.some(c=>c.path.includes('itemTypeId='+kind)&&c.path.includes('search=needle')));assert.equal(recovered.calls.some(c=>c.method!=='GET'),false);recovered.unmount();
 });
 test(`${kind} pending review labels nature without physical data and never retries`,async()=>{
 const storage=new Map<string,string>();const key=catalogKey('user-items','tenant-items','catalog-items');storage.set(key+':pending',JSON.stringify({id:'item-a',path:'/catalog/items',method:'POST',body:{},version:0}));const h=itemHarness(undefined,{options,storage,record:root({kind,item_type_id:kind})});await h.settle();await h.click('item-review');const summary=h.find(n=>n.type==='dl');assert.ok(summary);assert.ok(findCatalog(summary,n=>n.type==='dd'&&n.props.children===(kind==='INTANGIBLE'?'Bene immateriale':'Onere accessorio')));assert.equal(findCatalog(summary,n=>n.type==='dt'&&n.props.children==='Dati fisici'),undefined);assert.equal(h.calls.some(c=>c.method!=='GET'),false);h.unmount();
 });
 test(`${kind} missing legacy numbering metadata cannot authorize a write`,async()=>{
 const legacy={...options,types:options.types.filter(r=>r.kind===kind),numbering:itemOptions.numbering};const h=itemHarness(undefined,{options:legacy});await h.settle();await h.click('catalog-item-new');assert.equal(h.state.editor!.record.kind,kind);await h.edit('item-name','New');await h.select('item-category-id','category');await h.select('item-base-uom','g');await h.submit();assert.equal(h.byId('item-activation-confirm'),undefined);assert.equal(h.calls.some(c=>c.method!=='GET'),false);h.unmount();
 });
}
for(const kind of kinds)test(`${kind} existing item only offers same-nature alternatives and rejects cross-nature change`,async()=>{
 const record=root({kind,item_type_id:kind});const h=itemHarness(undefined,{options:{...options,types:[...options.types,{id:'same',name:'Same',kind,is_active:true}]},record});await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();const choice=h.find(n=>n.props?.onValueChange&&findCatalog(n,c=>c.props?.id==='item-type'));assert.ok(findCatalog(choice,n=>n.props?.value==='same'));for(const other of kinds.filter(k=>k!==kind))assert.equal(findCatalog(choice,n=>n.props?.value===other),undefined);await h.select('item-type',kind==='GOOD'?'CHARGE':'GOOD');assert.equal(h.state.editor!.record.kind,kind);assert.equal(h.state.editor!.values.item_type_id,kind);assert.equal(!!h.byId('item-tab-physical'),kind==='GOOD');h.unmount();
});
