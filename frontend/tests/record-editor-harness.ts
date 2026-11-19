import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createTranslator} from 'next-intl';
import * as model from '../lib/model.ts';
import {ApiError} from '../lib/api.ts';
export {find,session} from './workspace-harness.ts';
export function partnerHarness(file='business-partner-workspace', locale='en', respond: (path:string, method:string, body:any)=>any=()=>({}), storage?: Storage) {
 if (!storage) {const entries=new Map<string,string>(); storage={getItem:k=>entries.get(k)??null,setItem:(k,v)=>{entries.set(k,v);},removeItem:k=>{entries.delete(k);},clear:()=>entries.clear(),key:i=>[...entries.keys()][i]??null,get length(){return entries.size;}};}
 const require=createRequire(import.meta.url), messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));
 let index=0;
 const state:any[]=[], refs:any[]=[], dependencies:any[][]=[], effects:Array<()=>any>=[], calls:Array<{path:string;method:string;body:any}>=[];
 const ui=new Proxy({}, {get:(_target,name)=>(props:any)=>{
  const tag=name==='Button'?'button':name==='Input'?'input':name==='Textarea'?'textarea':name==='Label'?'label':name==='Checkbox'?'input':'div';
  const safe=Object.fromEntries(Object.entries(props).filter(([key])=>['children','disabled','className','id','value','checked','htmlFor','type','required','pattern','readOnly','min','max'].includes(key)||key.startsWith('aria-')));
  if(tag==='input') {delete safe.children;safe.readOnly=true;}
  return React.createElement(tag,safe);
 }});
 const modules:Record<string,any>={};
 const resolve=(name:string):any=>{
  if(name==='react') return {...React,useState:(initial:any)=>{const i=index++;if(!(i in state)) state[i]=typeof initial==='function'?initial():initial;return [state[i],(next:any)=>{state[i]=typeof next==='function'?next(state[i]):next;}];},useRef:(initial:any)=>{const i=index++;return refs[i]??=( {current:initial});},useEffect:(effect:()=>any,deps:any[])=>{const i=index++;if(!dependencies[i]||deps.some((v,j)=>v!==dependencies[i][j])){dependencies[i]=deps;effects.push(effect);}},useMemo:(fn:()=>any)=>fn(),useCallback:(fn:any)=>fn};
  if(name==='next-intl') return {useLocale:()=>locale,useTranslations:(namespace:string)=>createTranslator({locale,messages,namespace})};
  if(name==='@/lib/model') return model;
  if(name==='@/lib/api') return {ApiError,api:async(path:string,method='GET',body?:any)=>{calls.push({path,method,body});return respond(path,method,body);}};
  if(name.startsWith('@/components/ui/')) return ui;
  if(name.startsWith('@/')) {
   if(modules[name]) return modules[name];
   const source=readFileSync(new URL(`../${name.slice(2)}${name.startsWith('@/components/')?'.tsx':'.ts'}`,import.meta.url),'utf8'), module={exports:{}};
   const code=ts.transpileModule(source + (name === '@/components/workspace' ? '\nexport {RecordEditor, clearRecordRecovery};' : ''),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
   runInNewContext(code,{module,exports:module.exports,require:resolve,console,setTimeout,clearTimeout,AbortController,Intl,URL,URLSearchParams,sessionStorage:storage});modules[name]=module.exports;return module.exports;
  }
  return require(name);
 };
 const components=resolve(`@/components/${file}`);
 return {calls,state,components,
  tree:(component:string,props:any)=>{index=0;return components[component](props);},
  render:(component:string,props:any)=>{index=0;return renderToStaticMarkup(React.createElement(components[component],props));},
  flush:async()=>{const pending=effects.splice(0);for(const effect of pending)effect();await new Promise(resolve=>setImmediate(resolve));}
 };
}
