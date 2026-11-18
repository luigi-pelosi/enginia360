import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import React from 'react';
import {createTranslator} from 'next-intl';
import * as model from '../lib/model.ts';
export function addressDriver(fetcher: (...args:any[])=>any, locale='en', component='AddressAutocomplete') {
 const require=createRequire(import.meta.url), messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));
 const slots:any[]=[], dependencies:any[][]=[], cleanup:Record<number,Function>={};
 const pending:Function[]=[], timers=new Map<number,{fn:Function,delay:number}>();
 let index=0, sequence=0;
 const hooks={...React,useState:(initial:any)=>{const i=index++;if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],(v:any)=>{slots[i]=typeof v==='function'?v(slots[i]):v;}];},useRef:(current:any)=>{const i=index++;if(!(i in slots))slots[i]={current};return slots[i];},useEffect:(fn:Function,deps:any[])=>{const i=index++;if(!dependencies[i]||deps.some((v,j)=>v!==dependencies[i][j])) {dependencies[i]=deps;pending.push(()=>{cleanup[i]?.();cleanup[i]=fn();});}}};
 const module={exports:{} as any};
 const source=readFileSync(new URL(component==='SiteCountrySelect'?'../components/site-country-select.tsx':'../components/address-autocomplete.tsx',import.meta.url),'utf8');
 const code=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
 const apiModule={exports:{}};
 runInNewContext(ts.transpileModule(readFileSync(new URL('../lib/api.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText,{module:apiModule,exports:apiModule.exports,fetch:fetcher});
 runInNewContext(code,{module,exports:module.exports,require:(name:string)=>name==='react'?hooks:name==='next-intl'?{useLocale:()=>locale,useTranslations:(namespace:string)=>createTranslator({locale,messages,namespace})}:name==='@/lib/model'?model:name==='@/lib/api'?apiModule.exports:name.startsWith('@/components/ui/')?new Proxy({}, {get:(_t,key)=>Object.defineProperty(function Primitive(){},'name',{value:String(key)})}):require(name),URLSearchParams,AbortController,fetch:fetcher,setTimeout:(fn:Function,delay:number)=>{const id=++sequence;timers.set(id,{fn,delay});return id;},clearTimeout:(id:number)=>timers.delete(id),console});
 return {exports:module.exports,timers,slots,render(props:any){index=0;const tree=module.exports[component](props);while(pending.length)pending.shift()!();return tree;},async runTimers(){const batch=[...timers.values()];timers.clear();await Promise.all(batch.map(t=>t.fn()));},unmount(){Object.values(cleanup).forEach(fn=>fn?.());}};
}
