import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
const path = new URL('../lib/catalog.ts', import.meta.url);
const load = () => {assert.ok(existsSync(path),'catalog state helpers are implemented'); const require=createRequire(import.meta.url); const ts=require('typescript'); const m={exports:{} as any}; runInNewContext(ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module:m,exports:m.exports});return m.exports;};
test('scoped recovery keeps the original version and pending guard on reset',()=>{
 const c=load(); const map=new Map(); const storage={getItem:(k:string)=>map.get(k)??null,setItem:(k:string,v:string)=>map.set(k,v),removeItem:(k:string)=>map.delete(k)};
 const key=c.catalogKey('u','t','catalog-types');
 c.storeCatalog(storage,key,{search:'x',page:2,editor:{id:'r',version:4,values:{name:'draft'}}});
 c.storeCatalog(storage,key+':pending',{method:'PUT',id:'r'});
 c.resetCatalog(storage,key);
 assert.equal(c.readCatalog(storage,key).editor.version,4);
 assert.ok(c.readCatalog(storage,key+':pending'));
 assert.equal(c.readCatalog(storage,c.catalogKey('u','other','catalog-types')),null);
 storage.removeItem(key+':pending'); c.resetCatalog(storage,key); assert.equal(c.readCatalog(storage,key),null);
});
test('parent options exclude the whole moving subtree, without recursion limits',()=>{
 const c=load(); const rows=[{id:'a',parent_id:null,name:'A'},{id:'b',parent_id:'a',name:'B'},{id:'c',parent_id:'b',name:'C'},{id:'d',parent_id:null,name:'D'}];
 assert.deepEqual(Array.from(c.categoryParents(rows,'a'),(r:any)=>r.id),['d']);
 assert.equal(c.categoryPath(rows,'c'),'A / B / C');
});
test('mutation values are allowlisted and immutable values omitted on edit',()=>{
 const c=load();const v={name:'Metre',code:'M',dimension:'LENGTH',factor_to_base:'1',decimal_places:3,is_base:true,is_active:true,tenant_id:'foreign',version:900};
 const out=c.catalogValues('catalog-units',v,true);
 assert.equal(out.dimension,undefined);assert.equal(out.factor_to_base,undefined);assert.equal(out.is_base,undefined);assert.equal(out.tenant_id,undefined);assert.equal(out.decimal_places,3);
 assert.equal(c.catalogValues('catalog-types',{name:'s',kind:'SERVICE',default_track_stock:true},false).default_track_stock,false);
});
