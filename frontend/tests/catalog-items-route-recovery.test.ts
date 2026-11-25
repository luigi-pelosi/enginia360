import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import {harness,session,find} from './workspace-harness.ts';
import {catalogKey} from '../lib/catalog.ts';
import {can,catalogRoutes} from '../lib/model.ts';
test('legacy company route resolves to canonical root and company selection without granting identity',()=>{
 const source=readFileSync(new URL('../components/workspace.tsx',import.meta.url),'utf8');const fn=source.slice(source.indexOf('function workspaceRoute('),source.indexOf('function workspaceTenantKey('));
 const storage=new Map<string,string>();const module={exports:{} as any};const ss={setItem:(k:string,v:string)=>storage.set(k,v)};
 runInNewContext(ts.transpileModule(fn+'\nmodule.exports=workspaceRoute;',{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{module,exports:module.exports,URLSearchParams,catalogKey,can,sessionStorage:ss});
 const user={...session,permissions:['catalog-item-companies.read']};assert.equal(module.exports('?view=catalog-item-companies',['catalog-items','catalog-item-companies'],user,'t'),'catalog-items');
 assert.equal(storage.get(catalogKey('u','t','catalog-items-view')),JSON.stringify('company'));
 assert.equal(module.exports('?view=catalog-item-companies',['catalog-items'],{...user,permissions:['catalog-items.read']},'t'),'catalog-items');
});
for(const root of ['catalog','catalog-items'])test(`actual ${root} menu resets both child recoveries while preserving pending markers`,()=>{
 const user={...session,permissions:['catalog-items.read','catalog-item-companies.read']};const storage=new Map<string,string>();
 const identity=catalogKey('u','t','catalog-items'),company=catalogKey('u','t','catalog-item-companies'),view=catalogKey('u','t','catalog-items-view');
 for(const key of [identity,company,company+':item:a',view])storage.set(key,'{}');storage.set(company+':item:pending-record','{}');storage.set(company+':item:pending-record:pending','{}');storage.set(identity+':pending','{}');
 const h=harness('en',{0:user,1:false,5:catalogRoutes.map(key=>({key,fields:[]})),6:'catalog-items',7:'t'},undefined,storage);
 const tree=h.components.default();if(root==='catalog'){const nav=find(tree,n=>n.type?.name==='WorkspaceNavigation');nav.props.navigate(root);}else{const h2=harness('en',{0:user,1:false,5:catalogRoutes.map(key=>({key,fields:[]})),6:'catalog',7:'t'},undefined,storage);const tile=find(h2.components.default(),n=>n.type==='button'&&find(n,c=>c.type==='h2'&&c.props.children==='Items and services'));assert.ok(tile);tile.props.onClick();}
 assert.equal(storage.has(company),false);assert.equal(storage.has(company+':item:a'),false);assert.equal(storage.has(view),false);assert.equal(storage.has(identity),true);assert.equal(storage.has(identity+':pending'),true);assert.equal(storage.has(company+':item:pending-record'),true);assert.equal(storage.has(company+':item:pending-record:pending'),true);
});
