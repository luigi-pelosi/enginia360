import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';

function setup() {
 const source=readFileSync(new URL('../components/workspace.tsx',import.meta.url),'utf8');
 const block=source.match(/\/\* profile-recovery-helpers \*\/([\s\S]*?)\/\* end-profile-recovery-helpers \*\//)?.[1] || '';
 const data=new Map<string,string>();
 const sessionStorage={get length(){return data.size},key:(i:number)=>[...data.keys()][i]??null,getItem:(k:string)=>data.get(k)??null,setItem:(k:string,v:string)=>data.set(k,v),removeItem:(k:string)=>data.delete(k)};
 const code=ts.transpileModule(`${block}\nmodule.exports={profileRecoveryKey:typeof profileRecoveryKey==='function'?profileRecoveryKey:null, clearProfileRecovery:typeof clearProfileRecovery==='function'?clearProfileRecovery:null, clearUserProfileRecoveries:typeof clearUserProfileRecoveries==='function'?clearUserProfileRecoveries:null};`,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
 const module={exports:{} as any};runInNewContext(code,{module,sessionStorage});return {helpers:module.exports,data,source};
}
test('profile recovery is scoped by authenticated user and effective tenant',()=>{
 const {helpers:h}=setup();assert.equal(typeof h.profileRecoveryKey,'function');
 assert.equal(h.profileRecoveryKey({id:'u'},'a'),'profile-open:u:a');
 assert.notEqual(h.profileRecoveryKey({id:'u'},'a'),h.profileRecoveryKey({id:'u'},'b'));
 assert.notEqual(h.profileRecoveryKey({id:'u'},'a'),h.profileRecoveryKey({id:'v'},'a'));
 assert.equal(h.profileRecoveryKey({id:'u'},''),null);
});
test('explicit close removes only the current profile draft and marker; logout removes all of that user',()=>{
 const {helpers:h,data}=setup();assert.equal(typeof h.clearProfileRecovery,'function');
 for(const key of ['profile-open:u:a','profile-draft:u:a','profile-open:u:b','profile-draft:u:b','profile-draft:v:a'])data.set(key,'x');
 h.clearProfileRecovery({id:'u'},'a');assert.equal(data.has('profile-draft:u:a'),false);assert.equal(data.has('profile-open:u:a'),false);assert.equal(data.has('profile-draft:u:b'),true);
 h.clearUserProfileRecoveries({id:'u'});assert.deepEqual([...data.keys()],['profile-draft:v:a']);
});
test('restore effect waits for session and tenant and never opens another scope',()=>{
 const {helpers:h,data,source}=setup();
 const file=ts.createSourceFile('workspace.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 let effect:ts.CallExpression|undefined;
 function visit(node:ts.Node){if(ts.isCallExpression(node)&&node.expression.getText(file)==='useEffect'&&node.getText(file).includes('profileRecoveryKey(session, tenant)'))effect=node;ts.forEachChild(node,visit)}
 visit(file);assert.ok(effect);
 const code=ts.transpileModule(effect.getText(file),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
 data.set('profile-open:u:a','1');
 function run(initial:boolean,session:any,tenant:string){let opened=false;runInNewContext(code,{initial,session,tenant,profileRecoveryKey:h.profileRecoveryKey,sessionStorage:{getItem:(key:string)=>data.get(key)??null},setProfileOpen:(value:boolean)=>{opened=value},useEffect:(fn:()=>void)=>fn()});return opened}
 assert.equal(run(true,{id:'u'},'a'),false);assert.equal(run(false,null,'a'),false);
 assert.equal(run(false,{id:'u',mustChangePassword:true},'a'),false);assert.equal(run(false,{id:'u'},''),false);
 assert.equal(run(false,{id:'v'},'a'),false);assert.equal(run(false,{id:'u'},'b'),false);assert.equal(run(false,{id:'u'},'a'),true);
});
