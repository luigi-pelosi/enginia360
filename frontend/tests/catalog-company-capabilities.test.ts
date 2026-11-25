import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {harness,row} from './catalog-companies-interaction.test.ts';
const key='catalog:v1:user:tenant:catalog-item-companies';
const names=['canSell','canPurchase','canTrackStock'];
function nodes(tree:any,p:(n:any)=>boolean):any[]{if(!tree)return [];if(Array.isArray(tree))return tree.flatMap(n=>nodes(n,p));if(typeof tree!=='object')return [];return [...(p(tree)?[tree]:[]),...nodes([tree.props?.children,...(tree.props?.fields??[]).map((field:any)=>field.content)],p)];}
const query=(h:ReturnType<typeof harness>)=>new URL(h.calls.filter(c=>c.path.startsWith('/catalog/item-companies?')).at(-1)!.path,'https://test').searchParams;
const selected=(h:ReturnType<typeof harness>,id:string)=>h.find(n=>n.props?.onValueChange&&nodes(n,c=>c.props?.id===id).length)?.props.value;
test('search is first, six filters, atomic effective headers and accessible Check/X cells in list and item tab',async()=>{
 for(const itemId of [undefined,'i']){
  const h=harness({itemId,handler:path=>(path.startsWith('/catalog/item-companies?')||path==='/catalog/items/i/companies')?{items:[row('a',{is_sellable:true,is_purchasable:false,track_stock:true,canSell:false,canPurchase:true,canTrackStock:false})],total:1,page:1,pageSize:25}:undefined});const tree=await h.settle();
  const filterIds=['company-catalog-search','company-catalog-company','company-catalog-enabled',...names.map(n=>'company-catalog-'+n)];
  const fields=nodes(tree,n=>filterIds.includes(n.props?.id)).map(n=>n.props.id);
  assert.deepEqual(fields,itemId?[]:['company-catalog-search','company-catalog-company','company-catalog-enabled',...names.map(n=>'company-catalog-'+n)]);
  const heads=nodes(tree,n=>n.type?.name==='TableHead').map(n=>n.props.children);
  assert.deepEqual(heads,itemId?['Company','Association status','Can sell','Can purchase','Can track stock','Actions']:['Company','Item','Item status','Association status','Can sell','Can purchase','Can track stock','Actions']);
  const cells=nodes(tree,n=>n.props?.['data-capability']);assert.deepEqual(cells.map(n=>n.props['data-capability']),names);
  for(const [i,cell] of cells.entries()){
   const icon=nodes(cell,n=>n.props?.role==='img')[0];assert.ok(icon);assert.equal(icon.props['aria-label'],i===1?'Yes':'No');assert.equal(icon.props.title,i===1?'Yes':'No');
   const html=renderToStaticMarkup(React.createElement(React.Fragment,{},icon));assert.match(html,/aria-hidden="true"/);assert.match(html,i===1?/lucide-check/:/lucide-x/);assert.match(html,i===1?/text-green-600/:/text-red-600/);
  }
  h.unmount();
 }
});

test('capability selects send tri-state query, remove kind and reset page on every filter change; refresh retains filters',async()=>{
 const storage=new Map([[key,JSON.stringify({filterVersion:2,page:4,enabled:'ALL',canSell:'ALL',canPurchase:'ALL',canTrackStock:'ALL'})]]);const h=harness({storage});await h.settle();
 assert.equal(query(h).has('kind'),false);for(const name of names)assert.equal(query(h).get(name),'ALL');
 for(const name of names){await h.select('company-catalog-'+name,'YES');assert.equal(query(h).get(name),'YES');assert.equal(query(h).get('page'),'1');await h.select('company-catalog-'+name,'NO');assert.equal(query(h).get(name),'NO');}
 h.byId('company-catalog-search').props.onChange({target:{value:'needle & value'}});await h.settle();assert.equal(query(h).get('search'),'needle & value');
 await h.click('catalog-company-refresh');h.unmount();const recovered=harness({storage});await recovered.settle();for(const name of names)assert.equal(selected(recovered,'company-catalog-'+name),'NO');assert.equal(query(recovered).get('search'),'needle & value');recovered.unmount();
});

test('v1 migration preserves explicit enabled, editor, bulk and pending but removes kind and resets old pages; v2 invalid capabilities become ALL',async()=>{
 for(const enabled of ['ALL','DISABLED','ENABLED']){
  const editor={itemId:'i',companyId:'a',version:1,values:row(),readonly:true};const bulk={itemIds:['i'],companyIds:['a'],search:'draft',page:2};const pending={path:'/companies/a/catalog/items/i',method:'PATCH',body:{},itemIds:['i'],companyIds:['a']};
  const storage=new Map([[key,JSON.stringify({filterVersion:1,enabled,kind:'SERVICE',page:7,editor,bulk})],[key+':pending',JSON.stringify(pending)]]);const h=harness({storage});await h.settle();const saved=JSON.parse(storage.get(key)!);assert.equal(saved.filterVersion,2);assert.equal(saved.page,1);assert.equal(saved.enabled,enabled);assert.equal('kind' in saved,false);assert.deepEqual(saved.editor,editor);assert.deepEqual(saved.bulk,bulk);assert.deepEqual(JSON.parse(storage.get(key+':pending')!),pending);h.unmount();
 }
 const h=harness({storage:new Map([[key,JSON.stringify({filterVersion:2,enabled:'ALL',page:5,canSell:'YES',canPurchase:'bogus',canTrackStock:null})]])});await h.settle();assert.equal(query(h).get('page'),'5');assert.equal(query(h).get('canSell'),'YES');assert.equal(query(h).get('canPurchase'),'ALL');assert.equal(query(h).get('canTrackStock'),'ALL');h.unmount();
});
