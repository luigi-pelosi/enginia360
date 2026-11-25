import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,root} from './catalog-items-harness.ts';

for(const existing of [false,true])for(const status of ['ACTIVE','SUSPENDED'] as const)for(const kind of ['GOOD','SERVICE'] as const)test(`required fields and validation match: ${existing?'update':'create'} ${kind} ${status}`,async()=>{
 const h=itemHarness(undefined,{record:root({status,kind,item_type_id:kind==='GOOD'?'good':'service'})});
 await h.settle();
 if(existing){await h.action('Modifica Item A').props.onClick();await h.settle();}
 else{await h.click('catalog-item-new');await h.select('item-type',kind==='GOOD'?'good':'service');await h.select('item-status',status);await h.edit('item-name','Required fields');if(kind==='GOOD')await h.edit('item-code','REQUIRED');}
 for(const id of ['item-name','item-type','item-category-id','item-base-uom'])assert.equal(h.find(n=>n.props?.htmlFor===id).props.required,true,id);
 for(const [field,id,value] of [['category_id','item-category-id','category'],['base_uom_id','item-base-uom','g']]){
  await h.select('item-category-id','category');await h.select('item-base-uom','g');
  await h.select(id,'__none__');
  await h.submit();
  assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
  assert.equal(h.byId(id).props['aria-invalid'],true);
  assert.equal(h.pending,null);
  assert.equal(h.state.editor!.values[field],null);
  await h.select(id,value);
 }
 await h.edit('item-name','');await h.submit();assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});

test('incomplete existing suspended record stays readable but cannot save from another tab',async()=>{
 const h=itemHarness(undefined,{record:root({category_id:null})});await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();
 assert.equal(h.state.editor!.values.category_id,null);
 await h.click('item-tab-physical');await h.submit();
 assert.equal(h.state.tab,'general');assert.equal(h.byId('item-category-id').props['aria-invalid'],true);
 assert.equal(h.state.editor!.version,4);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
});
