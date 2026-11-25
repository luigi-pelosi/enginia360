import test from 'node:test';
import assert from 'node:assert/strict';
import {harness,context} from './catalog-companies-interaction.test.ts';
const key='catalog:v1:user:tenant:catalog-item-companies';
const options=Array.from({length:26},(_,i)=>({id:'c'+i,name:'Company '+i,code:null,is_enabled:true,permissions:['read','create'],legal_address:i===0?{address:'Via Uno',postal_code:'00100',city:'Roma',province:'RM',country_code:'IT'}:null}));
function handler(path:string){if(path.includes('/item-companies/options'))return {items:options};if(path.startsWith('/catalog/items?')){const page=Number(new URL('http://test'+path).searchParams.get('page'));return {items:[{...context.item,id:page===1?'i':'j'}],total:26,page,pageSize:25};}}
test('bulk renders compact tables with page-local tri-state selection and legal address',async()=>{
 const h=harness({handler});await h.settle();await h.click('catalog-company-bulk');
 assert.match(h.find(n=>n.props?.['data-testid']==='catalog-company-bulk-editor').props.className,/sm:max-w-6xl/);
 assert.ok(h.byId('catalog-bulk-companies-table'));assert.ok(h.byId('catalog-bulk-items-table'));
 assert.ok(h.find(n=>n.props?.children==='Via Uno, 00100 Roma RM, Italy (IT)'));
 assert.equal(h.byId('catalog-bulk-company-all').props.checked,'indeterminate');
 await h.toggle('catalog-bulk-company-all',true);await h.click('catalog-bulk-company-next');
 assert.equal(h.byId('catalog-bulk-company-c0'),null);assert.equal(h.byId('catalog-bulk-company-all').props.checked,false);
 await h.toggle('catalog-bulk-company-all',true);await h.click('catalog-bulk-company-previous');await h.toggle('catalog-bulk-company-all',false);
 const saved=JSON.parse(h.storage.get(key)!);assert.deepEqual(saved.bulk.companyIds,['c25']);
 await h.toggle('catalog-bulk-item-all',true);await h.click('catalog-bulk-next');await h.toggle('catalog-bulk-item-all',true);await h.click('catalog-bulk-previous');await h.toggle('catalog-bulk-item-all',false);
 assert.deepEqual(JSON.parse(h.storage.get(key)!).bulk.itemIds,['j']);h.unmount();
});
test('company page restores, clamps after metadata shrink and retains off-page selections',async()=>{
 const storage=new Map([[key,JSON.stringify({bulk:{itemIds:['j'],companyIds:['c25'],search:'',page:1,companyPage:99}})]]);
 const h=harness({storage,handler});await h.settle();assert.ok(h.byId('catalog-bulk-company-c25'));assert.equal(JSON.parse(storage.get(key)!).bulk.companyPage,2);h.unmount();
 const recovered=harness({storage,handler:path=>path.includes('/item-companies/options')?{items:options.slice(0,1)}:handler(path)});await recovered.settle();assert.equal(JSON.parse(storage.get(key)!).bulk.companyPage,1);assert.deepEqual(JSON.parse(storage.get(key)!).bulk.companyIds,['c25']);recovered.unmount();
});
test('empty eligible item page disables all and page bounds',async()=>{
 const h=harness({handler:path=>path.startsWith('/catalog/items?')?{items:[{...context.item,status:'ARCHIVED'}],total:0,page:1,pageSize:25}:handler(path)});await h.settle();await h.click('catalog-company-bulk');assert.equal(h.byId('catalog-bulk-item-all').props.disabled,true);assert.equal(h.byId('catalog-bulk-previous').props.disabled,true);assert.equal(h.byId('catalog-bulk-next').props.disabled,true);h.unmount();
});

test('loading chooser freezes every bulk input and does not allow submitting stale selections',async()=>{
 let resolveItems!:(value:any)=>void;const wait=new Promise(resolve=>{resolveItems=resolve;});
 const h=harness({handler:path=>path.startsWith('/catalog/items?')?wait:handler(path)});await h.settle();await h.click('catalog-company-bulk');
 for(const id of ['catalog-bulk-company-all','catalog-bulk-company-c0','catalog-bulk-item-all','catalog-bulk-search','catalog-bulk-company-previous','catalog-bulk-company-next','catalog-bulk-previous','catalog-bulk-next','catalog-bulk-save','catalog-bulk-cancel'])assert.equal(h.byId(id).props.disabled,true,id);
 await h.submit();assert.equal(h.calls.some(c=>c.method==='POST'),false);
 resolveItems({items:[context.item],total:1,page:1,pageSize:25});await h.settle();assert.equal(h.byId('catalog-bulk-item-all').props.disabled,false);h.unmount();
});
test('search and reload retain hidden selections while page-all deselects only visible matches',async()=>{
 const storage=new Map<string,string>();const h=harness({storage,handler});await h.settle();await h.click('catalog-company-bulk');await h.toggle('catalog-bulk-item-all',true);await h.click('catalog-bulk-next');await h.toggle('catalog-bulk-item-all',true);
 h.byId('catalog-bulk-search').props.onChange({target:{value:'Item'}});await h.settle();assert.equal(h.byId('catalog-bulk-item-all').props.checked,true);h.unmount();
 const recovered=harness({storage,handler});await recovered.settle();assert.equal(recovered.byId('catalog-bulk-search').props.value,'Item');assert.equal(recovered.byId('catalog-bulk-item-all').props.checked,true);await recovered.toggle('catalog-bulk-item-all',false);assert.deepEqual(JSON.parse(storage.get(key)!).bulk.itemIds,['j']);recovered.unmount();
});
test('page-all keeps complete selection above pair limit, displays feedback and blocks Save',async()=>{
 const h=harness({handler:path=>path.startsWith('/catalog/items?')?{items:Array.from({length:25},(_,i)=>({...context.item,id:'i'+i})),total:25,page:1,pageSize:25}:handler(path)});await h.settle();await h.click('catalog-company-bulk');await h.toggle('catalog-bulk-company-all',true);await h.toggle('catalog-bulk-item-all',true);
 const saved=JSON.parse(h.storage.get(key)!);assert.equal(saved.bulk.companyIds.length,25);assert.equal(saved.bulk.itemIds.length,25);assert.equal(h.byId('catalog-bulk-save').props.disabled,true);assert.ok(h.find(n=>n.props?.role==='alert'&&n.props.children==='Maximum 100 items, 100 companies and 500 associations.'));await h.submit();assert.equal(h.calls.some(c=>c.method==='POST'),false);h.unmount();
});
for(const value of [0,-1,1.2,'2',null])test('invalid recovered company page defaults to one: '+String(value),async()=>{
 const storage=new Map([[key,JSON.stringify({bulk:{itemIds:[],companyIds:[],search:'',page:1,companyPage:value}})]]);const h=harness({storage,handler});await h.settle();assert.equal(JSON.parse(storage.get(key)!).bulk.companyPage,1);h.unmount();
});
