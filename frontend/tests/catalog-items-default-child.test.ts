import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,itemOptions,root,findCatalog} from './catalog-items-harness.ts';

async function open(h:ReturnType<typeof itemHarness>){await h.settle();h.action('Modifica Item A').props.onClick();await h.settle();}
test('new unit selects first admissible active option and derives universal ratio in payload',async()=>{
 const h=itemHarness((path,method,body)=>method==='POST'?root({version:5,units:[{...body.values,id:'new'}]}):undefined);await open(h);await h.click('item-tab-units');await h.click('item-add-units');
 assert.equal(h.state.rowEditor!.values.uom_id,'kg');assert.equal(h.state.rowEditor!.values.conversion_numerator,'1');assert.equal(h.state.rowEditor!.values.conversion_denominator,'0.001');await h.submit(true);assert.equal(h.calls.find(c=>c.method==='POST')?.body.values.uom_id,'kg');
});
test('conversion selects first active associated destination distinct from base and submits it',async()=>{
 const record=root({units:[{id:'u',uom_id:'cf',conversion_numerator:'12',conversion_denominator:'1',is_active:true}]});const h=itemHarness((path,method)=>method==='POST'?{quantity:'1',unroundedQuantity:'1',rounded:false,decimalPlaces:0}:undefined,{record});await open(h);await h.click('item-tab-units');h.action('Converti').props.onClick();await h.settle();assert.equal(h.state.conversion!.sourceUnitId,'g');assert.equal(h.state.conversion!.targetUnitId,'cf');const form=h.find(n=>n.type==='form'&&findCatalog(n,c=>c.props?.id==='item-source-unit'));form.props.onSubmit({preventDefault(){},stopPropagation(){}});await h.settle();assert.equal(h.calls.find(c=>c.method==='POST')?.body.targetUnitId,'cf');
});

test('unit default skips inactive, incompatible and already associated options; explicit choice survives recovery',async()=>{
 const units=[{...itemOptions.units[0],is_active:false},itemOptions.units[3],itemOptions.units[0],itemOptions.units[2],itemOptions.units[1]];
 const record=root({units:[{id:'u',uom_id:'kg',conversion_numerator:'1',conversion_denominator:'0.001',is_active:true}]});
 const h=itemHarness(undefined,{options:{...itemOptions,units},record});await open(h);await h.click('item-tab-units');await h.click('item-add-units');assert.equal(h.state.rowEditor!.values.uom_id,'cf');await h.select('item-uom-id','__none__');const again=itemHarness(undefined,{options:{...itemOptions,units},record,storage:h.storage});await again.settle();assert.equal(again.state.rowEditor!.values.uom_id,null);h.unmount();again.unmount();
});
test('no eligible unit remains unset and existing unit is preserved',async()=>{
 const record=root({units:[{id:'u',uom_id:'kg',conversion_numerator:'1',conversion_denominator:'0.001',is_active:true}]});const options={...itemOptions,units:[itemOptions.units[0],itemOptions.units[1],{...itemOptions.units[2],is_active:false},itemOptions.units[3]]};const h=itemHarness(undefined,{record,options});await open(h);await h.click('item-tab-units');await h.click('item-add-units');assert.equal(h.state.rowEditor!.values.uom_id,null);await h.submit(true);assert.equal(h.calls.some(c=>c.method==='POST'),false);await h.click('item-row-cancel');h.action('Modifica Kilogram').props.onClick();await h.settle();assert.equal(h.state.rowEditor!.values.uom_id,'kg');
});
test('conversion does not default inactive or unassociated destination',async()=>{
 const options={...itemOptions,units:itemOptions.units.map(u=>u.id==='cf'?{...u,is_active:false}:u)};const record=root({units:[{id:'u',uom_id:'cf',conversion_numerator:'12',conversion_denominator:'1',is_active:true}]});const h=itemHarness(undefined,{record,options});await open(h);await h.click('item-tab-units');h.action('Converti').props.onClick();await h.settle();assert.equal(h.state.conversion!.targetUnitId,'');assert.equal(h.calls.some(c=>c.method==='POST'),false);
});
test('identifier keeps semantic GTIN default and optional unit remains empty',async()=>{
 const h=itemHarness();await open(h);await h.click('item-tab-identifiers');await h.click('item-add-identifiers');assert.equal(h.state.rowEditor!.values.identifier_type,'GTIN');assert.equal(h.state.rowEditor!.values.uom_id,null);
});
