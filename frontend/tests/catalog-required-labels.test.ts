import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';

for (const [resource,required,optional] of [
 ['catalog-brands',['name'],['code','description','is_active']],
 ['catalog-categories',['name','sort_order'],['code','description','parent_id']],
 ['catalog-types',['name','kind'],['code','is_active']],
 ['catalog-units',['name','code','dimension','factor_to_base','decimal_places'],['conversion_scope','is_active']],
 ['catalog-numbering',['mode','padding','nextNumber'],['prefix']],
] as const) test(`${resource}: required labels match the editor contract`,async()=>{
 const session={...catalogSession,permissions:[...catalogSession.permissions,...['read','create','update'].map(a=>`${resource}.${a}`)]};
 const h=catalogHarness(resource,p=>p==='/session'?session:resource==='catalog-numbering'?{mode:'AUTO',padding:3,nextNumber:1,version:1}:{items:[],total:0},undefined,'it',session);
 await h.settle();
 if(resource!=='catalog-numbering'){await h.byId('catalog-new').props.onClick();await h.settle();}
 for(const name of required){const label=findCatalog(h.tree,n=>n.type?.name==='Label'&&n.props?.htmlFor===`catalog-${name}`);assert.ok(label,`${name} label`);assert.equal(label.props.required,true,`${name} must be marked required`);}
 for(const name of optional){const label=findCatalog(h.tree,n=>n.type?.name==='Label'&&n.props?.htmlFor===`catalog-${name}`);assert.ok(label,`${name} label`);assert.notEqual(label.props.required,true,`${name} must remain optional`);}
 h.unmount();
});

test('conversion labels mark target and quantity required',async()=>{
 const h=catalogHarness('catalog-units',p=>p==='/session'?catalogSession:{items:[],total:0});await h.settle();
 for(const name of ['target','quantity']){const label=findCatalog(h.tree,n=>n.type?.name==='Label'&&n.props?.htmlFor===`catalog-${name}`);assert.equal(label?.props.required,true,`${name} must be marked required`);}
 h.unmount();
});
