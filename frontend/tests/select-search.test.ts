import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {selectDriver,all,keyEvent} from './select-harness.ts';
function fixture(locale='it',overrides:any={}){
 const d=selectDriver(locale), c=d.components,changes:string[]=[];
 const props={defaultValue:'IT',defaultOpen:true,name:'country',onValueChange:(v:string)=>changes.push(v),...overrides};
 const children=[React.createElement(c.SelectTrigger,{'aria-label':'Country',id:'country'},React.createElement(c.SelectValue,{placeholder:'—'})),React.createElement(c.SelectContent,{},[
  React.createElement(c.SelectItem,{key:'none',value:'__none__'},'—'),React.createElement(c.SelectGroup,{key:'countries'},[
   React.createElement(c.SelectItem,{key:'IT',value:'IT'},'Itàlia'),React.createElement(c.SelectItem,{key:'US',value:'US'},'United States'),React.createElement(c.SelectItem,{key:'FR',value:'FR',disabled:true},'France')])])];
 return {render:()=>d.render(props,children),changes,props};
}
const search=(tree:any)=>all(tree,n=>n.type==='input'&&n.props['aria-label'])[0];
const options=(tree:any)=>all(tree,n=>n.props?.role==='option');
test('required missing sentinel displays placeholder without changing value',()=>{
 const d=selectDriver(),c=d.components,changes:string[]=[];
 const children=[React.createElement(c.SelectTrigger,{},React.createElement(c.SelectValue,{placeholder:'Seleziona'})),React.createElement(c.SelectContent,{},React.createElement(c.SelectItem,{value:'__none__'},'—'))];
 const tree=d.render({required:true,value:'__none__',onValueChange:(v:string)=>changes.push(v)},children);
 assert.equal(all(tree,n=>n.props?.['data-slot']==='select-value')[0].props.children,'Seleziona');
 assert.deepEqual(changes,[]);
});
for(const locale of ['it','en'])test(`empty required uncontrolled sentinel uses localized empty state (${locale})`,()=>{
 const d=selectDriver(locale),c=d.components,changes:string[]=[];
 const children=[React.createElement(c.SelectTrigger,{},React.createElement(c.SelectValue)),React.createElement(c.SelectContent,{})];
 const tree=d.render({required:true,defaultValue:'__none__',onValueChange:(v:string)=>changes.push(v)},children);
 assert.equal(all(tree,n=>n.props?.['data-slot']==='select-value')[0].props.children,locale==='it'?'Nessun risultato':'No results');
 assert.deepEqual(changes,[]);
});
test('optional sentinel label and missing historical value remain visible',()=>{
 for(const [props,expected] of [[{value:'__none__'},'—'],[{required:true,value:'historical-id'},'historical-id']] as const){
  const f=fixture('it',props),tree=f.render();
  assert.equal(all(tree,n=>n.props?.['data-slot']==='select-value')[0].props.children,expected);
  assert.deepEqual(f.changes,[]);
 }
});
for(const locale of ['it','en'])test(`default shared search filters label/value with accents and preserves selected label (${locale})`,()=>{
 const f=fixture(locale);let tree=f.render();const input=search(tree);assert.ok(input,'search input exists by default');assert.equal(input.props['data-slot'],'select-search');assert.equal(input.props['aria-label'],locale==='it'?'Cerca':'Search');
 input.props.onChange({target:{value:'uS'}});tree=f.render();assert.deepEqual(options(tree).map(n=>n.props['data-value']),['US']);
 assert.match(JSON.stringify(all(tree,n=>n.props?.role==='combobox')[0].props.children),/Itàlia/);
 search(tree).props.onChange({target:{value:'ITALIA'}});tree=f.render();assert.deepEqual(options(tree).map(n=>n.props['data-value']),['IT']);
 search(tree).props.onChange({target:{value:'not-found'}});tree=f.render();assert.equal(options(tree).length,0);assert.ok(all(tree,n=>n.props?.role==='status'&&n.props['data-slot']==='select-empty'&&n.props.children===(locale==='it'?'Nessun risultato':'No results')).length);
 assert.deepEqual(f.changes,[],'search never mutates value');
});
test('keyboard has no implicit first choice, skips disabled, Enter commits once and Escape only closes select',()=>{
 const f=fixture();let tree=f.render();const enter=keyEvent('Enter');search(tree).props.onKeyDown(enter);assert.equal(enter.prevented,true);assert.deepEqual(f.changes,[]);
 search(tree).props.onKeyDown(keyEvent('ArrowUp'));tree=f.render();assert.equal(search(tree).props['aria-activedescendant'],options(tree).find(n=>n.props['data-value']==='US').props.id);
 search(tree).props.onKeyDown(keyEvent('Enter'));tree=f.render();assert.deepEqual(f.changes,['US']);assert.equal(search(tree),undefined);
 const root=all(tree,n=>n.type==='primitive-root')[0];root.props.onOpenChange(true);tree=f.render();assert.equal(search(tree).props.value,'');
 const escape=keyEvent('Escape');search(tree).props.onKeyDown(escape);tree=f.render();assert.equal(escape.stopped,true);assert.equal(search(tree),undefined);
});
test('required native form proxy has complete options, no clear; disabled/same value cannot mutate',()=>{
 const f=fixture('en',{required:true,name:'country',form:'record'});let tree=f.render();assert.equal(options(tree).some(n=>n.props['data-value']==='__none__'),false);
 const native=all(tree,n=>n.type==='select')[0];assert.ok(native);assert.equal(native.props.required,true);assert.equal(native.props.form,'record');assert.equal(all(native,n=>n.type==='option').length,4);
 options(tree).find(n=>n.props['data-value']==='IT').props.onClick(keyEvent(''));assert.deepEqual(f.changes,[]);
 const disabled=fixture('it',{disabled:true});tree=disabled.render();assert.equal(all(tree,n=>n.props?.role==='combobox')[0].props.disabled,true);all(tree,n=>n.type==='select')[0].props.onChange({target:{value:'US'}});assert.deepEqual(disabled.changes,[]);
});
test('optional explicit clear and ordinary searchable=false fallback preserve compound API',()=>{
 const f=fixture();let tree=f.render();options(tree).find(n=>n.props['data-value']==='__none__').props.onClick(keyEvent(''));assert.deepEqual(f.changes,['__none__']);
 const ordinary=fixture('it',{searchable:false});tree=ordinary.render();assert.equal(search(tree),undefined);assert.ok(all(tree,n=>n.type==='primitive-item').length);
});
test('native required validation focuses trigger rather than hidden proxy',()=>{
 const f=fixture('it',{required:true,value:''});const tree=f.render();let focused=0;
 all(tree,n=>n.props?.role==='combobox')[0].props.ref({focus(){focused++;}});
 const event=keyEvent('invalid');all(tree,n=>n.type==='select')[0].props.onInvalid(event);
 assert.equal(event.prevented,true);assert.equal(focused,1);
});
test('popup is presentation not dialog; closing restores trigger focus and Tab closes without submit',()=>{
 const f=fixture();let tree=f.render();let focused=0;all(tree,n=>n.props?.role==='combobox')[0].props.ref({focus(){focused++;}});
 const popup=all(tree,n=>n.type==='primitive-content')[0];assert.equal(popup.props.role,'presentation');
 const close=keyEvent('close');popup.props.onCloseAutoFocus(close);assert.equal(close.prevented,true);assert.equal(focused,1);
 const tab=keyEvent('Tab');search(tree).props.onKeyDown(tab);tree=f.render();assert.equal(search(tree),undefined);assert.deepEqual(f.changes,[]);
});
test('controlled value/open, reset on close, disabled options and preserved native full collection',()=>{
 const f=fixture('en',{value:'IT',open:true});let tree=f.render();search(tree).props.onChange({target:{value:'France'}});tree=f.render();
 assert.equal(options(tree).length,1);options(tree)[0].props.onClick(keyEvent(''));assert.deepEqual(f.changes,[]);
 assert.equal(all(tree,n=>n.type==='option').length,5,'filter never changes native form collection');
 f.props.open=false;f.render();f.props.open=true;tree=f.render();assert.equal(search(tree).props.value,'');
 options(tree).find(n=>n.props['data-value']==='US').props.onClick(keyEvent(''));tree=f.render();assert.deepEqual(f.changes,['US']);assert.match(JSON.stringify(all(tree,n=>n.props?.role==='combobox')[0].props.children),/Itàlia/,'owner controls selected value');
});

for(const locale of ['it','en'])test(`required invalid feedback is visible and described (${locale})`,()=>{
 const d=selectDriver(locale),c=d.components;
 const children=React.createElement(c.SelectTrigger,{'aria-describedby':'existing'},React.createElement(c.SelectValue));
 let tree=d.render({required:true,value:''},children);
 const native=all(tree,n=>n.type==='select')[0];
 native.props.onInvalid({...keyEvent('invalid'),currentTarget:{form:null}});
 tree=d.render({required:true,value:''},children);
 const trigger=all(tree,n=>n.props?.role==='combobox')[0], error=all(tree,n=>n.props?.['data-slot']==='select-error')[0];
 assert.ok(error);assert.equal(error.props.children,locale==='it'?'Compila questo campo obbligatorio.':'Complete this required field.');
 assert.equal(trigger.props['aria-invalid'],true);assert.match(trigger.props['aria-describedby'],/existing/);assert.ok(trigger.props['aria-describedby'].includes(error.props.id));
});

test('multiple invalid controls focus only the first and each exposes an error',()=>{
 const a=fixture('it',{required:true,value:''}),b=fixture('it',{required:true,value:''});
 let ta=a.render(),tb=b.render(),focused:string[]=[];
 all(ta,n=>n.props?.role==='combobox')[0].props.ref({focus(){focused.push('a')}});
 all(tb,n=>n.props?.role==='combobox')[0].props.ref({focus(){focused.push('b')}});
 const first:any={willValidate:true,validity:{valid:false}}, second:any={willValidate:true,validity:{valid:false}};
 const form={elements:[first,second]};first.form=form;second.form=form;
 all(ta,n=>n.type==='select')[0].props.onInvalid({...keyEvent('invalid'),currentTarget:first});
 all(tb,n=>n.type==='select')[0].props.onInvalid({...keyEvent('invalid'),currentTarget:second});
 assert.deepEqual(focused,['a']);
 assert.equal(all(a.render(),n=>n.props?.['data-slot']==='select-error').length,1);
 assert.equal(all(b.render(),n=>n.props?.['data-slot']==='select-error').length,1);
});
test('selection or a changed controlled value clears validation feedback',()=>{
 const f=fixture('it',{required:true,defaultValue:''});let tree=f.render();
 all(tree,n=>n.type==='select')[0].props.onInvalid(keyEvent('invalid'));tree=f.render();
 assert.equal(all(tree,n=>n.props?.['data-slot']==='select-error').length,1);
 options(tree).find(n=>n.props['data-value']==='US').props.onClick(keyEvent(''));tree=f.render();
 assert.equal(all(tree,n=>n.props?.['data-slot']==='select-error').length,0);
 const controlled=fixture('it',{required:true,value:''});tree=controlled.render();
 all(tree,n=>n.type==='select')[0].props.onInvalid(keyEvent('invalid'));assert.equal(all(controlled.render(),n=>n.props?.['data-slot']==='select-error').length,1);
 controlled.props.value='IT';tree=controlled.render();assert.equal(all(tree,n=>n.props?.['data-slot']==='select-error').length,0);
 controlled.props.value='';tree=controlled.render();assert.equal(all(tree,n=>n.props?.['data-slot']==='select-error').length,0);
});
test('unknown required historical value is retained in native form collection',()=>{
 const f=fixture('it',{required:true,value:'historical-id'}),tree=f.render();
 assert.ok(all(tree,n=>n.type==='option'&&n.props.value==='historical-id').length);
});

test('form reset clears the inline error',()=>{
 const f=fixture('it',{required:true,value:'',form:'first'});let tree=f.render();
 let reset:()=>void=()=>{};const form={addEventListener:(name:string,fn:()=>void)=>{if(name==='reset')reset=fn},removeEventListener:()=>{}};
 all(tree,n=>n.type==='select')[0].props.ref.current={form};
 f.props.form='second';tree=f.render();
 all(tree,n=>n.type==='select')[0].props.onInvalid(keyEvent('invalid'));
 assert.equal(all(f.render(),n=>n.props?.['data-slot']==='select-error').length,1);
 reset();assert.equal(all(f.render(),n=>n.props?.['data-slot']==='select-error').length,0);
});
