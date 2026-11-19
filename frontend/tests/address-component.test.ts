import test from 'node:test';
import assert from 'node:assert/strict';
import {addressDriver} from './address-component-harness.ts';
import {find} from './workspace-harness.ts';
const context={country_code:'IT',city:'Capua',province:'CE'}, scope=(p:string)=>p+'&tenantId=tenant';
const base={id:'field-address',field:'address',value:'Via Roma',context,scope,disabled:false,required:false,onChange(_text:string){},onSelect(_item:any){}};
const item={label:'Via Roma, Capua',address:'Via Roma',city:'Capua',province:'CE',postalCode:'81043',countryCode:'IT'};
const keyEvent=(key:string)=>({key,preventDefault(){},stopPropagation(){}});
test('manual address entry retains the consumer field length independently of lookup limits',()=>{
 const d=addressDriver(async()=>{});
 assert.equal(find(d.render({...base,maxLength:500}),n=>n.props?.role==='combobox').props.maxLength,500);d.unmount();
});
test('shared autocomplete retains field validation alongside manual-fallback feedback',async()=>{
 const d=addressDriver(async()=>{throw Error('unavailable');});
 const props={...base,'aria-invalid':true,'aria-describedby':'validation-message'};
 let tree=d.render(props);find(tree,n=>n.props?.role==='combobox').props.onFocus();d.render(props);await d.runTimers();tree=d.render(props);
 const input=find(tree,n=>n.props?.role==='combobox');
 assert.equal(input.props['aria-invalid'],true);
 assert.equal(input.props['aria-describedby'],'validation-message field-address-lookup-error');
 assert.ok(find(tree,n=>n.props?.id==='field-address-lookup-error'));d.unmount();
});
test('street selection clears an omitted postcode even in same city; partial parent selections never leave incompatible descendants',()=>{
 const d=addressDriver(async()=>{}), old={country_code:'IT',province:'CE',city:'Capua',postal_code:'OLD',address:'Old street'};
 const next=d.exports.addressSelection(old,'address',{...item,postalCode:''});
 assert.equal(next.postal_code,'');
 assert.equal(next.address,'Via Roma');
 assert.equal(d.exports.addressSelection(old,'province',{label:'Rome',countryCode:'IT',province:'RM'}).city,'');
});
test('focus + min3/debounce350, internal scoped query only, keyboard listbox selection and ignores legacy attribution',async()=>{
 const calls:any[]=[], selected:any[]=[];const d=addressDriver(async(...args)=>{calls.push(args);return {ok:true,json:async()=>({items:[item],attribution:'Powered by Geoapify | © OpenStreetMap contributors'})};});
 let props={...base,value:'Vi',onSelect:(item:any)=>selected.push(item)};
 let tree=d.render(props);assert.equal(d.timers.size,0);
 find(tree,n=>n.props?.role==='combobox').props.onFocus();d.render(props);assert.equal(d.timers.size,0);
 props={...props,value:'Via'};tree=d.render(props);
 assert.equal([...d.timers.values()][0].delay,350);assert.equal(calls.length,0);
 await d.runTimers();tree=d.render(props);
 assert.equal(calls.length,1);const url=new URL(calls[0][0],'https://app.invalid');
 assert.equal(url.pathname,'/api/addresses/autocomplete');assert.equal(url.searchParams.get('tenantId'),'tenant');assert.equal(url.searchParams.get('countryCode'),'IT');assert.equal(url.searchParams.get('language'),'en');assert.equal(url.searchParams.get('city'),'Capua');
 assert.ok(calls[0][1].signal instanceof AbortSignal);
 assert.ok(find(tree,n=>n.props?.role==='listbox'));assert.equal(find(tree,n=>n.type==='a'),undefined);
 find(tree,n=>n.props?.role==='combobox').props.onKeyDown(keyEvent('ArrowDown'));tree=d.render(props);
 assert.equal(find(tree,n=>n.props?.role==='combobox').props['aria-activedescendant'],'field-address-suggestions-0');
 find(tree,n=>n.props?.role==='combobox').props.onKeyDown(keyEvent('Enter'));tree=d.render(props);
 assert.deepEqual(selected,[item]);assert.equal(find(tree,n=>n.props?.role==='listbox'),undefined);assert.equal(d.timers.size,0);
 d.unmount();
});
test('ArrowUp from an unopened active option starts at the final suggestion',async()=>{
 const d=addressDriver(async()=>({ok:true,json:async()=>({items:[item,{...item,label:'Second'}]})}));
 let tree=d.render(base);find(tree,n=>n.props?.role==='combobox').props.onFocus();d.render(base);await d.runTimers();tree=d.render(base);
 find(tree,n=>n.props?.role==='combobox').props.onKeyDown(keyEvent('ArrowUp'));tree=d.render(base);
 assert.equal(find(tree,n=>n.props?.role==='combobox').props['aria-activedescendant'],'field-address-suggestions-1');d.unmount();
});
test('local pointer choice preserves focus and leading zeros; Enter without active option never submits a choice',async()=>{
 const selected:any[]=[],changed:string[]=[];
 const local={label:'Roma · 00100',city:'Roma',province:'RM',region:'Lazio',postalCode:'00100',countryCode:'IT'};
 const d=addressDriver(async()=>({ok:true,json:async()=>({items:[local]})}));
 const props={...base,field:'city',value:'Rom',onSelect:(item:any)=>selected.push(item),onChange:(value:string)=>changed.push(value)};
 let tree=d.render(props);find(tree,n=>n.props?.role==='combobox').props.onFocus();d.render(props);await d.runTimers();tree=d.render(props);
 let prevented=false;find(tree,n=>n.props?.role==='combobox').props.onKeyDown({key:'Enter',preventDefault(){prevented=true;}});
 assert.equal(prevented,false);assert.deepEqual(selected,[]);
 const option=find(tree,n=>n.props?.role==='option');option.props.onMouseDown({preventDefault(){prevented=true;}});assert.equal(prevented,true);
 option.props.onClick();assert.deepEqual(selected,[local]);assert.deepEqual(changed,[]);
 const draft=d.exports.addressSelection({address:'Via manuale'},'city',local);
 assert.equal(draft.address,'Via manuale');assert.equal(draft.postal_code,'00100');assert.equal(draft.region,'Lazio');
 tree=d.render(props);assert.equal(find(tree,n=>n.props?.role==='listbox'),undefined);d.unmount();
});
test('local lookup failure is localized and preserves manual entry; readonly/busy never fetch/change',async()=>{
 for(const locale of ['it','en']) {
 const changed:string[]=[];const d=addressDriver(async()=>{throw Error('private provider URL/key');},locale);
 const props={...base,onChange:(value:string)=>changed.push(value)};
 let tree=d.render(props);find(tree,n=>n.props?.role==='combobox').props.onFocus();d.render(props);await d.runTimers();tree=d.render(props);
 const message=find(tree,n=>n.props?.id==='field-address-lookup-error');assert.ok(message);assert.match(message.props.children,locale==='it'?/Puoi compilare a mano/:/manually/);
 find(tree,n=>n.props?.role==='combobox').props.onChange({target:{value:'Manual'}});assert.deepEqual(changed,['Manual']);
 tree=d.render({...props,disabled:true});const input=find(tree,n=>n.props?.role==='combobox');input.props.onChange({target:{value:'Blocked'}});input.props.onFocus();
 assert.deepEqual(changed,['Manual']);assert.equal(d.timers.size,0);d.unmount();
 }
});
test('aborted stale responses cannot replace current suggestions; Escape/blur cancel and close',async()=>{
 const pending:Array<{resolve:Function,signal:AbortSignal}>=[];const d=addressDriver((_url,options)=>new Promise(resolve=>pending.push({resolve,signal:options.signal})));
 let props={...base};let tree=d.render(props);find(tree,n=>n.props?.role==='combobox').props.onFocus();d.render(props);const first=d.runTimers();
 assert.equal(pending.length,1);
 find(tree,n=>n.props?.role==='combobox').props.onChange({target:{value:'Via Nuova'}});props={...props,value:'Via Nuova'};d.render(props);const second=d.runTimers();assert.equal(pending[0].signal.aborted,true);
 pending[1].resolve({ok:true,json:async()=>({items:[{...item,label:'New street'}]})});await second;tree=d.render(props);
 assert.ok(find(tree,n=>n.props?.role==='option'&&n.props.children==='New street'));
 pending[0].resolve({ok:true,json:async()=>({items:[{...item,label:'Stale street'}]})});await first;tree=d.render(props);
 assert.equal(find(tree,n=>n.props?.role==='option'&&n.props.children==='Stale street'),undefined);
 find(tree,n=>n.props?.role==='combobox').props.onKeyDown(keyEvent('Escape'));tree=d.render(props);assert.equal(find(tree,n=>n.props?.role==='listbox'),undefined);
 tree.props.onBlur({currentTarget:{contains:()=>false},relatedTarget:null});d.render(props);assert.equal(d.timers.size,0);d.unmount();
});
