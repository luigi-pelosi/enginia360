import test from 'node:test';
import assert from 'node:assert/strict';
import {harness} from './catalog-companies-interaction.test.ts';

const key='catalog:v1:user:tenant:catalog-item-companies';
const values={is_enabled:true,is_sellable:false,is_purchasable:true,track_stock:false,default_sales_uom_id:null,default_purchase_uom_id:null};
const editor={itemId:'i',companyId:'a',version:1,values,readonly:false};
const bulk={itemIds:['i'],companyIds:['a'],search:'chooser draft',page:2};
const pending={path:'/companies/a/catalog/items/i',method:'PATCH',body:{values,expectedVersion:1},itemIds:['i'],companyIds:['a'],committed:true};

test('legacy implicit ALL migrates once to ENABLED page one without losing drafts or pending identity',async()=>{
 const storage=new Map([[key,JSON.stringify({companyId:'a',search:'needle',kind:'SERVICE',enabled:'ALL',page:4,editor,bulk})],[key+':pending',JSON.stringify(pending)]]);
 const h=harness({storage});await h.settle();
 assert.equal(selected(h),'ENABLED');assert.match(query(h),/companyId=a&page=1&.*search=needle&enabled=ENABLED&canSell=ALL&canPurchase=ALL&canTrackStock=ALL/);
 const saved=JSON.parse(storage.get(key)!);assert.equal(saved.filterVersion,2);assert.equal('kind' in saved,false);assert.equal(saved.page,1);assert.deepEqual(saved.editor,editor);assert.deepEqual(saved.bulk,bulk);assert.deepEqual(JSON.parse(storage.get(key+':pending')!),pending);
 assert.ok(h.byId('catalog-company-review'));assert.equal(h.calls.some(c=>c.method!=='GET'),false);h.unmount();
 const refreshed=harness({storage});await refreshed.settle();assert.equal(selected(refreshed),'ENABLED');assert.deepEqual(JSON.parse(storage.get(key)!).editor,editor);
 await refreshed.select('company-catalog-enabled','ALL');refreshed.unmount();
 const explicit=harness({storage});await explicit.settle();assert.equal(selected(explicit),'ALL');assert.deepEqual(JSON.parse(storage.get(key+':pending')!),pending);explicit.unmount();
});

for(const enabled of ['ALL','DISABLED'])test(`current explicit ${enabled} survives refresh, while fresh menu reset returns ENABLED`,async()=>{
 const storage=new Map([[key,JSON.stringify({filterVersion:2,enabled,page:3})]]);
 const h=harness({storage});await h.settle();assert.equal(selected(h),enabled);assert.match(query(h),new RegExp(`page=3&.*enabled=${enabled}&`));
 await h.click('catalog-company-refresh');assert.equal(selected(h),enabled);
 await h.select('company-catalog-enabled',enabled);h.unmount();
 const refreshed=harness({storage});await refreshed.settle();assert.equal(selected(refreshed),enabled);refreshed.unmount();
 storage.delete(key);const reset=harness({storage});await reset.settle();assert.equal(selected(reset),'ENABLED');assert.match(query(reset),/page=1&.*enabled=ENABLED&/);reset.unmount();
});

test('item configurations tab stays unfiltered and exact-company metadata remains authoritative',async()=>{
 const h=harness({itemId:'i'});await h.settle();assert.equal(h.byId('company-catalog-enabled'),null);assert.ok(h.calls.some(c=>c.path==='/catalog/items/i/companies'));assert.equal(query(h),undefined);h.unmount();
 const storage=new Map([[key,JSON.stringify({filterVersion:1,companyId:'b',enabled:'ALL',page:2})]]);
 const denied=harness({storage,permissions:['catalog-item-companies.read'],handler:path=>path==='/catalog/item-companies/options'?{items:[{id:'b',name:'B',code:'B',is_enabled:true,permissions:['update']}]}:undefined});
 await denied.settle();assert.equal(selected(denied,'company-catalog-company'),'ALL');assert.equal(selected(denied),'ALL');assert.equal(denied.calls.some(c=>c.path.includes('companyId=b')),false);assert.equal(denied.byId('catalog-company-bulk'),null);denied.unmount();
});
const selected=(h:ReturnType<typeof harness>,id='company-catalog-enabled')=>h.find(n=>n.props?.onValueChange&&contains(n,id))?.props.value;
function contains(n:any,id:string):boolean{return Array.isArray(n)?n.some(c=>contains(c,id)):!!n&&typeof n==='object'&&(n.props?.id===id||contains(n.props?.children,id));}
const query=(h:ReturnType<typeof harness>)=>h.calls.filter(c=>c.path.startsWith('/catalog/item-companies?')).at(-1)?.path;

test('fresh company association list selects ENABLED and sends the same initial API filter',async()=>{
 const h=harness({permissions:['catalog-item-companies.read']});await h.settle();
 assert.equal(selected(h),'ENABLED');assert.match(query(h),/enabled=ENABLED&/);assert.match(query(h),/page=1&/);
 assert.equal(h.calls.some(c=>c.path.startsWith('/catalog/items')),false);h.unmount();
});
