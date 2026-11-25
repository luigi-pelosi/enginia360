import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,itemOptions,root} from './catalog-items-harness.ts';

test('new item selects first active type in draft and submitted payload',async()=>{
 const options={...itemOptions,types:[itemOptions.types[2],itemOptions.types[1],itemOptions.types[0]]};
 const h=itemHarness((path,method)=>method==='POST'?root({kind:'SERVICE',item_type_id:'service'}):undefined,{options});
 await h.settle();await h.click('catalog-item-new');
 assert.equal(h.state.editor!.values.item_type_id,'service');
 assert.equal(h.state.editor!.record.kind,'SERVICE');
 const trigger=h.byId('item-type');const select=h.find(n=>n.props?.onValueChange&&n.props?.value==='service');assert.ok(trigger);assert.ok(select);
 await h.edit('item-name','New');await h.select('item-category-id','category');await h.select('item-base-uom','g');await h.submit(false,true);
 assert.equal(h.calls.find(c=>c.method==='POST')?.body.values.item_type_id,'service');
});

test('empty and inactive catalogs leave the required draft unset',async()=>{
 for(const types of [[],[itemOptions.types[2]]]){const h=itemHarness(undefined,{options:{...itemOptions,types}});await h.settle();await h.click('catalog-item-new');assert.equal(h.state.editor!.values.item_type_id,null);await h.edit('item-name','New');await h.submit();assert.equal(h.calls.some(c=>c.method==='POST'),false);h.unmount();}
});

test('edit and restored new draft retain their selected type',async()=>{
 const h=itemHarness();await h.settle();h.action('Modifica Item A').props.onClick();await h.settle();assert.equal(h.state.editor!.values.item_type_id,'good');await h.click('item-cancel');await h.click('catalog-item-new');await h.select('item-type','service');const restored=itemHarness(undefined,{storage:h.storage});await restored.settle();assert.equal(restored.state.editor!.values.item_type_id,'service');h.unmount();restored.unmount();
});

test('failed options request does not open a partially initialized editor',async()=>{
 let count=0;const h=itemHarness(path=>{if(path.startsWith('/catalog/item-options')&&++count===2)throw Error('options unavailable');});await h.settle();await h.click('catalog-item-new');assert.equal(h.state.editor,null);h.unmount();
});

test('late options after unmount do not create or persist a draft',async()=>{
 let count=0,release!:(value:typeof itemOptions)=>void;const h=itemHarness(path=>path.startsWith('/catalog/item-options')&&++count===2?new Promise(resolve=>{release=resolve;}):undefined);await h.settle();const opening=h.click('catalog-item-new');await new Promise(resolve=>setImmediate(resolve));h.unmount();release(itemOptions);await opening;assert.equal(h.state.editor,null);assert.equal([...h.storage.values()].some(v=>v.includes('"item_type_id":"good"')),false);
});
