import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness} from './catalog-items-harness.ts';

function required(h:ReturnType<typeof itemHarness>,id:string){
 const label=h.find(n=>n.props?.htmlFor===id);
 assert.ok(label,`missing label for ${id}`);
 return label.props.required===true;
}

test('item labels reflect manual versus automatic numbering',async()=>{
 const h=itemHarness();await h.settle();await h.click('catalog-item-new');
 assert.equal(required(h,'item-name'),true);
 assert.equal(required(h,'item-type'),true);
 assert.equal(required(h,'item-code'),true);
 assert.equal(required(h,'item-base-uom'),true);
 assert.equal(required(h,'item-category-id'),true);
 await h.select('item-type','service');
 assert.equal(h.byId('item-code'),undefined);
 await h.select('item-type','good');
 assert.equal(required(h,'item-code'),true);
});

test('child labels mark only required identifier and unit fields',async()=>{
 const h=itemHarness();await h.settle();await h.click('catalog-item-new');
 await h.select('item-base-uom','g');await h.click('item-tab-identifiers');await h.click('item-add-identifiers');
 assert.equal(required(h,'item-identifier-type'),true);assert.equal(required(h,'item-value'),true);assert.equal(required(h,'item-uom-id'),false);
 await h.click('item-row-cancel');await h.click('item-tab-units');await h.click('item-add-units');
 for(const id of ['item-uom-id','item-conversion-numerator','item-conversion-denominator'])assert.equal(required(h,id),true);
 await h.select('item-uom-id','kg');
 assert.equal(h.byId('item-conversion-numerator').props.disabled,true);
 assert.equal(required(h,'item-conversion-numerator'),true);
});

test('physical data fields remain optional',async()=>{
 const h=itemHarness();await h.settle();await h.click('catalog-item-new');await h.click('item-tab-physical');
 for(const id of ['item-net-weight','item-gross-weight','item-weight-uom-id','item-length','item-width','item-height','item-dimension-uom-id'])assert.equal(required(h,id),false);
});
