import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import React from 'react';
const require=createRequire(import.meta.url);
export function selectDriver(locale='it') {
 const states=new Map<string,any[]>(), contexts=new Map<any,any>();let path='',index=0;const effects:Function[]=[];
 const hooks={...React,useState(initial:any){const key=path,i=index++;let slots=states.get(key);if(!slots)states.set(key,slots=[]);if(!(i in slots))slots[i]=typeof initial==='function'?initial():initial;return [slots[i],(v:any)=>slots![i]=typeof v==='function'?v(slots![i]):v];},useRef(initial:any){const [ref]=hooks.useState(()=>({current:initial}));return ref;},useId(){return 'id-'+path.replace(/[^a-z0-9]/gi,'-');},useContext(context:any){return contexts.get(context)??context._currentValue;},useMemo(fn:Function){return fn();},useCallback(fn:Function){return fn;},useEffect(fn:Function){effects.push(fn);}};
 const primitive=new Proxy({}, {get:(_t,key)=> (props:any)=>React.createElement('primitive-'+String(key).toLowerCase(),props)});
 const module={exports:{} as any};
 const resolve=(name:string):any=>{
  if(name==='react')return hooks;
  if(name==='next-intl')return {useTranslations:()=> (key:string)=>({search:locale==='it'?'Cerca':'Search',empty:locale==='it'?'Nessun risultato':'No results'})[key]};
  if(name==='radix-ui')return {Select:primitive,Popover:primitive};
  if(name==='@/lib/utils')return {cn:(...v:any[])=>v.filter(Boolean).join(' ')};
  if(name.startsWith('./select-ordinary')){const child={exports:{}};runInNewContext(ts.transpileModule(readFileSync(new URL('../components/ui/select-ordinary.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module:child,exports:child.exports,require:resolve});return child.exports;}
  return require(name);
 };
 runInNewContext(ts.transpileModule(readFileSync(new URL('../components/ui/select.tsx',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module,exports:module.exports,require:resolve});
 function expand(node:any,key='root'):any {
  if(Array.isArray(node))return node.map((n,i)=>expand(n,key+'.'+(n?.key??i)));
  if(!React.isValidElement(node))return node;
  const el=node as any;
  if(el.type===React.Fragment)return expand(el.props.children,key+'.fragment');
  if(el.type?.$$typeof===Symbol.for('react.context')){const old=contexts.get(el.type);contexts.set(el.type,el.props.value);const result=expand(el.props.children,key+'.provider');contexts.set(el.type,old);return result;}
  if(typeof el.type==='function'){const oldPath=path,oldIndex=index;path=key;index=0;const result=expand(el.type(el.props),key+'.'+el.type.name);path=oldPath;index=oldIndex;return result;}
  return {...el,props:{...el.props,children:expand(el.props.children,key+'.children')}};
 }
 return {components:module.exports,render:(props:any,children:any)=>{effects.length=0;const tree=expand(React.createElement(module.exports.Select,props,children));for(const fn of effects)fn();return tree;}};
}
export function all(node:any,predicate:(n:any)=>boolean):any[]{if(!node||typeof node!=='object')return [];if(Array.isArray(node))return Array.from(node).flatMap(n=>all(n,predicate));return [...(predicate(node)?[node]:[]),...all(node.props?.children,predicate)];}
export function keyEvent(key:string){return {key,prevented:false,stopped:false,preventDefault(){this.prevented=true;},stopPropagation(){this.stopped=true;}};}
