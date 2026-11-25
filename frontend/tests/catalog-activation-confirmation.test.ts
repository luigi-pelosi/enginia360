import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,itemSession,root} from './catalog-items-harness.ts';
const writes=(h:ReturnType<typeof itemHarness>)=>h.calls.filter(call=>call.method!=='GET');

for(const scenario of ['create','first activation'] as const)test(`ACTIVE confirmation before ${scenario}: cancel retains all drafts and confirm writes once`,async()=>{
 const existing=scenario!=='create';
 let record=root({status:'SUSPENDED',activated_at:null});
 const h=itemHarness((path,method,body)=>{if(method!=='GET'){record={...record,...body.values,status:'ACTIVE',physicalData:body.physicalData,version:existing?5:1};return record;}if(path.startsWith('/catalog/items/'))return record;},{record});
 await h.settle();if(existing){await h.action('Modifica Item A').props.onClick();await h.settle();}else{await h.click('catalog-item-new');await h.edit('item-code','NEW');await h.select('item-category-id','category');await h.select('item-base-uom','g');}
 await h.edit('item-name','Confirm this name');await h.select('item-status','ACTIVE');await h.click('item-tab-physical');await h.edit('item-net-weight','2');await h.select('item-weight-uom-id','g');await h.click('item-tab-general');
 await h.submit();assert.ok(h.byId('item-activation-confirm'));assert.equal(writes(h).length,0);assert.equal(h.pending,null);
 await h.click('item-activation-cancel');assert.equal(h.byId('item-activation-confirm'),undefined);assert.equal(writes(h).length,0);assert.equal(h.state.editor!.values.name,'Confirm this name');assert.equal(h.state.editor!.physicalDraft!.net_weight,'2');assert.equal(h.state.editor!.statusDraft,'ACTIVE');
 await h.submit();await h.click('item-activation-confirm');assert.equal(writes(h).length,1);const request=writes(h)[0];assert.equal(request.method,existing?'PUT':'POST');assert.equal(request.body.values.name,'Confirm this name');assert.equal(request.body.physicalData.net_weight,'2');assert.equal(request.body.expectedVersion,existing?4:undefined);
});

test('already ACTIVE saves directly, including a draft status roundtrip, without activate permission',async()=>{
 for(const roundtrip of [false,true]){
  let record=root({status:'ACTIVE',activated_at:'2026-11-24T09:00:00Z'});
  const h=itemHarness((path,method,body)=>{if(method==='PUT'){record={...record,...body.values,physicalData:body.physicalData,version:5};return record;}if(path.startsWith('/catalog/items/'))return record;},{record,session:{...itemSession,permissions:itemSession.permissions.filter(permission=>permission!=='catalog-items.activate')}});
  await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();await h.edit('item-name','Already active edit');
  if(roundtrip){await h.select('item-status','SUSPENDED');await h.select('item-status','ACTIVE');}
  await h.click('item-tab-physical');await h.edit('item-net-weight','2');await h.select('item-weight-uom-id','g');await h.click('item-tab-general');await h.submit();
  assert.equal(writes(h).length,1);assert.equal(h.byId('item-activation-confirm'),undefined);assert.equal(writes(h)[0].body.status,undefined);assert.equal(writes(h)[0].body.values.name,'Already active edit');assert.equal(writes(h)[0].body.physicalData.net_weight,'2');assert.equal(writes(h)[0].body.expectedVersion,4);assert.equal(record.activated_at,'2026-11-24T09:00:00Z');
 }
});

test('previous activation skips confirmation on reactivation and keeps consolidated fields locked',async()=>{
 let record=root({status:'SUSPENDED',activated_at:'2026-11-24T09:00:00Z'});
 const h=itemHarness((path,method,body)=>{if(method==='PUT'){record={...record,...body.values,status:body.status,version:5};return record;}if(path.startsWith('/catalog/items/'))return record;},{record});
 await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();assert.equal(h.byId('item-code').props.disabled,true);await assert.rejects(h.select('item-base-uom','kg'),/Disabled/);
 await h.edit('item-name','Reactivated without warning');await h.select('item-status','ACTIVE');await h.submit();
 assert.equal(writes(h).length,1);assert.equal(h.byId('item-activation-confirm'),undefined);assert.equal(writes(h)[0].body.status,'ACTIVE');assert.equal(writes(h)[0].body.expectedVersion,4);assert.equal(record.status,'ACTIVE');assert.equal(record.activated_at,'2026-11-24T09:00:00Z');
});

test('reactivation without confirmation still checks fresh activate authority',async()=>{
 let revoked=false;const h=itemHarness(path=>path==='/session'&&revoked?{...itemSession,permissions:['catalog-items.read','catalog-items.update']}:undefined,{record:root({status:'SUSPENDED',activated_at:'2026-11-24T09:00:00Z'})});
 await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();await h.select('item-status','ACTIVE');revoked=true;await h.submit();assert.equal(writes(h).length,0);assert.equal(h.byId('item-activation-confirm'),undefined);assert.equal(h.pending,null);assert.equal(h.state.editor!.statusDraft,'ACTIVE');assert.ok(h.byId('item-field-error'));
});

test('confirm ACTIVE rechecks permissions after modal opened',async()=>{
 let revoked=false;const h=itemHarness(path=>path==='/session'&&revoked?{...itemSession,permissions:['catalog-items.read','catalog-items.update']}:undefined);
 await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();await h.select('item-status','ACTIVE');await h.submit();revoked=true;await h.click('item-activation-confirm');assert.equal(writes(h).length,0);assert.equal(h.pending,null);assert.ok(h.state.editor);assert.ok(h.byId('item-activation-cancel'));
});

test('mandatory validation precedes ACTIVE confirmation',async()=>{
 const h=itemHarness();await h.settle();await h.click('catalog-item-new');await h.edit('item-name','Incomplete');await h.edit('item-code','NEW');await h.submit();assert.equal(h.byId('item-activation-confirm'),undefined);assert.equal(writes(h).length,0);assert.ok(h.byId('item-field-error'));
});

test('busy ACTIVE confirmation keeps both portals mounted and prevents a second write',async()=>{
 let release!:(value:any)=>void;const h=itemHarness((path,method)=>method==='PUT'?new Promise(resolve=>{release=resolve;}):undefined);
 await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();await h.select('item-status','ACTIVE');await h.submit();await h.click('item-activation-confirm');assert.equal(writes(h).length,1);assert.equal(h.byId('item-activation-confirm').props.disabled,true);assert.equal(h.byId('item-activation-cancel').props.disabled,true);assert.ok(h.find(n=>n.props?.['data-testid']==='catalog-item-editor').props.children);assert.ok(h.find(n=>n.props?.['data-testid']==='catalog-item-activation-confirm'));
 release(root({status:'ACTIVE',version:5,activated_at:'2026-11-24T09:00:00Z'}));await h.settle();assert.equal(writes(h).length,1);
});
