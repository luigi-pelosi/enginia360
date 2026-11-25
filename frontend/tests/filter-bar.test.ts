import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import ts from 'typescript';
function harness(controlled=false){
 const slots:any[]=[],effects:any[]=[];let cursor=0,tree:any,width=900,resize:any,external=false;
 const fields=[200,180,130,128,128,128].map((minWidth,i)=>({key:String(i),minWidth,grow:i===0,content:React.createElement('input',{id:'field-'+i,value:'saved-'+i,readOnly:true})}));
 const require=createRequire(import.meta.url),m={exports:{} as any};
 const file=new URL('../components/ui/filter-bar.tsx',import.meta.url);
 const hooks={...React,useState:(initial:any)=>{const n=cursor++;if(!(n in slots))slots[n]=typeof initial==='function'?initial():initial;return[slots[n],(v:any)=>{slots[n]=typeof v==='function'?v(slots[n]):v;}];},useRef:(v:any)=>{const n=cursor++;return slots[n]??(slots[n]={current:v});},useEffect:(fn:any,deps:any[])=>{const n=cursor++;if(!slots[n]){slots[n]=deps;effects.push(fn);}}};
 if(existsSync(file))runInNewContext(ts.transpileModule(readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText,{module:m,exports:m.exports,require:(name:string)=>name==='react'?hooks:name==='next-intl'?{useTranslations:()=>()=> 'More filters'}:require(name),ResizeObserver:class{constructor(cb:any){resize=cb;}observe(){resize([{contentRect:{width}}]);}disconnect(){}}});
 else m.exports.FilterBar=()=>null;
 function render(){cursor=0;tree=m.exports.FilterBar({id:'test-filters',fields,...(controlled?{expanded:external,onExpandedChange:(v:boolean)=>{external=v;}}:{})});if(tree?.props.ref)tree.props.ref.current={getBoundingClientRect:()=>({width})};while(effects.length)effects.shift()();cursor=0;tree=m.exports.FilterBar({id:'test-filters',fields,...(controlled?{expanded:external,onExpandedChange:(v:boolean)=>{external=v;}}:{})});return tree;}
 function all(n:any,p:(x:any)=>boolean):any[]{if(!n||typeof n!=='object')return [];if(Array.isArray(n))return n.flatMap(x=>all(x,p));return [...(p(n)?[n]:[]),...all(n.props?.children,p)];}
 return {render,resize:(w:number)=>{width=w;resize?.([{contentRect:{width:w}}]);return render();},all:(p:(x:any)=>boolean)=>all(tree,p),button:()=>all(tree,n=>n.type==='button')[0],region:()=>all(tree,n=>n.props?.role==='region')[0]};
}
test('measured overflow reserves the final toggle, keeps search first and renders each control once',()=>{
 const h=harness();h.render();assert.ok(h.button(),'overflow must expose a final filter toggle');assert.equal(h.region().props.hidden,true);
 assert.equal(h.all(n=>n.type==='input').length,6);assert.equal(h.all(n=>n.props?.['data-filter-primary'])[0].props.children[0][0].props['data-filter-key'],'0');
 h.button().props.onClick();h.render();assert.equal(h.region().props.hidden,false);
 h.resize(1054);assert.equal(h.button(),undefined);h.resize(300);assert.equal(h.region().props.hidden,false);assert.equal(h.all(n=>n.type==='input').length,6);
 h.resize(80);assert.equal(h.all(n=>n.props?.['data-filter-primary'])[0].props.children[0][0].props['data-filter-key'],'0');
});
test('controlled expansion reports preference without modifying filter values',()=>{const h=harness(true);h.render();h.button().props.onClick();h.render();assert.equal(h.button().props['aria-expanded'],true);assert.equal(h.region().props.id,h.button().props['aria-controls']);assert.equal(h.all(n=>n.type==='input'&&n.props.value==='saved-5').length,1);});
