import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';

function setup(blocked = false) {
 const source = readFileSync(new URL('../components/workspace.tsx', import.meta.url), 'utf8');
 const block = source.match(/\/\* workspace-navigation-helpers \*\/([\s\S]*?)\/\* end-workspace-navigation-helpers \*\//)?.[1] || '';
 const data = new Map<string,string>();
 const sessionStorage = {getItem:(key:string)=>{if(blocked)throw new Error('unavailable');return data.get(key)??null;},setItem:(key:string,value:string)=>{if(blocked)throw new Error('unavailable');data.set(key,value);}};
 const code = ts.transpileModule(`${block}\nmodule.exports={workspaceTenant:typeof workspaceTenant==='function'?workspaceTenant:null,rememberWorkspaceTenant:typeof rememberWorkspaceTenant==='function'?rememberWorkspaceTenant:null};`,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
 const module = {exports:{} as any};runInNewContext(code,{module,sessionStorage,URLSearchParams});
 return {...module.exports,data};
}
const admin = {id:'admin',isSuperAdmin:true,tenantId:null,selectedTenantId:'a'};
const tenants = [{id:'a'},{id:'b'}];
test('selected organization survives refresh instead of reverting to login preselection',()=>{
 const h=setup();assert.equal(typeof h.rememberWorkspaceTenant,'function');
 h.rememberWorkspaceTenant(admin,'b');assert.equal(h.workspaceTenant(admin,tenants),'b');
});
test('explicit no selection persists without falling back to the login organization',()=>{
 const h=setup();assert.equal(typeof h.workspaceTenant,'function');
 h.rememberWorkspaceTenant(admin,'');assert.equal(h.workspaceTenant(admin,tenants),'');
});
test('restored selection is user scoped and validated against current organizations',()=>{
 const h=setup();assert.equal(typeof h.workspaceTenant,'function');
 h.rememberWorkspaceTenant(admin,'b');assert.equal(h.workspaceTenant({...admin,id:'other'},tenants),'a');
 assert.equal(h.workspaceTenant(admin,[{id:'a'}]),'');
 assert.equal(h.workspaceTenant({...admin,isSuperAdmin:false,tenantId:'a'},tenants),'a');
});
test('missing or unavailable browser storage preserves a valid server preselection',()=>{
 for(const blocked of [false,true]){const h=setup(blocked);assert.equal(typeof h.workspaceTenant,'function');assert.equal(h.workspaceTenant(admin,tenants),'a');assert.equal(h.workspaceTenant(admin,[]),'');assert.doesNotThrow(()=>h.rememberWorkspaceTenant(admin,'b'));}
});
