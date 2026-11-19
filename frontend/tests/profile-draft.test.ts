import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import React from 'react';
import {createTranslator} from 'next-intl';
import {find, session} from './workspace-harness.ts';
export {find, session};
const require = createRequire(import.meta.url);
export const ownProfile = {id:'u',username:'ada',first_name:'Ada',last_name:'Lovelace',email:'ada@example.test',date_of_birth:null,phone_number:'123',preferred_language:'it'};
const data = new Map<string,string>();
const sessionStorage = {getItem:(k:string)=>data.get(k)??null, setItem:(k:string,v:string)=>data.set(k,v), removeItem:(k:string)=>data.delete(k)};
export function driver(respond: (path:string,method?:string,body?:any)=>any = (path) => path==='/session' ? session : ownProfile, locale='it') {
 const state:any[]=[]; const refs:any[]=[]; const deps:any[]=[]; let cursor=0; const effects:Array<()=>void>=[];
 const calls:Array<{path:string,method?:string,body?:any}>=[]; const events:string[]=[]; const document={cookie:''};
 const ui=new Proxy({}, {get:(_target,name)=>function Primitive(props:any){ return React.createElement(name==='Input'?'input':name==='Button'?'button':'div',props); }});
 const module={exports:{} as any};
 const resolve=(name:string):any=>{
  if(name==='react') return {...React,useState:(initial:any)=>{const i=cursor++;if(!(i in state))state[i]=typeof initial==='function'?initial():initial;return [state[i],(next:any)=>{state[i]=typeof next==='function'?next(state[i]):next}]},useRef:(initial:any)=>{const i=cursor++;return refs[i]??(refs[i]={current:initial})},useEffect:(fn:()=>any,next:any[])=>{const i=cursor++; if(!deps[i]||next.some((d,j)=>d!==deps[i][j])){deps[i]=next;effects.push(fn)}},useCallback:(fn:any)=>fn};
  if(name==='next-intl')return {useLocale:()=>locale,useTranslations:(namespace:string)=>createTranslator({locale,messages:JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8')),namespace})};
  if(name==='@/lib/api')return {api:async(path:string,method?:string,body?:any)=>{calls.push({path,method,body});events.push(path);return respond(path,method,body)},refreshCsrf:async()=>{events.push('csrf')}};
  if(name.startsWith('@/components/ui/'))return ui;
  if(name==='@/lib/password')return load('../lib/password.ts');
  return require(name);
 };
 function load(path:string){const m={exports:{}}; const text=readFileSync(new URL(path,import.meta.url),'utf8');runInNewContext(ts.transpileModule(text,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{module:m,exports:m.exports,require:resolve});return m.exports;}
 const path=new URL('../components/profile-dialog.tsx',import.meta.url);
 if(existsSync(path)) runInNewContext(ts.transpileModule(readFileSync(path,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}}).outputText,{module,exports:module.exports,require:resolve,document,sessionStorage,location:{reload(){events.push('reload')}}});
 const props={session:{id:'u',selectedTenantId:'tenant-a'},onClose(){events.push('close')},onSaved(value:any){events.push('saved');return value},onError(error:any){return error.message||'error'}};
 const render=()=>{cursor=0;return module.exports.ProfileDialog?.(props)};
 return {render,calls,events,document,props,state,async load(){const initial=render();assertComponent(initial);for(const effect of effects.splice(0)) effect();await new Promise(resolve=>setTimeout(resolve,0));return render()},change(tree:any,id:string,value:string){const node=find(tree,(n:any)=>n.props?.id===id);if(!node)throw Error(`Missing ${id}`);(node.props.onChange??node.props.onValueChange)(node.props.onChange?{target:{value}}:value)},submit(tree:any){return find(tree,(n:any)=>n.type==='form').props.onSubmit({preventDefault(){}})}};
}
function assertComponent(value:any){if(!value)throw new Error('ProfileDialog must render a dedicated personal profile form');}

 test('restores whitelisted personal draft only after authorized profile read, scoped by user and tenant',async()=>{
 data.clear(); const h=driver(); let tree=await h.load();h.change(tree,'profile-first_name','Grace');h.change(h.render(),'profile-password-current','secret');
 assert.ok([...data.values()].some(v=>v.includes('Grace')));assert.ok(!JSON.stringify([...data]).includes('secret'));
 const restored=driver();tree=await restored.load();assert.equal(find(tree,n=>n.props?.id==='profile-first_name').props.value,'Grace');assert.equal(find(tree,n=>n.props?.id==='profile-password-current').props.value,'');
 const other=driver();other.props.session.selectedTenantId='tenant-b';tree=await other.load();assert.equal(find(tree,n=>n.props?.id==='profile-first_name').props.value,'Ada');
 const denied=driver(()=>{throw Error('forbidden')});tree=await denied.load();assert.equal(find(tree,n=>n.props?.id==='profile-first_name'),undefined);
 });
