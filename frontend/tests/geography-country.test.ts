import test from 'node:test';
import assert from 'node:assert/strict';
import {addressDriver} from './address-component-harness.ts';
import {find} from './workspace-harness.ts';
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const base={id:'field-country_code',value:'FR',scope:(p:string)=>p+'?tenantId=A',disabled:false,required:false,onChange(_value:string){}};
test('country control preserves supplied field feedback alongside lookup failure',async()=>{
 const d=addressDriver(async()=>{throw Error('unavailable');},'en','SiteCountrySelect');
 const props={...base,'aria-invalid':true,'aria-describedby':'validation-message'};
 d.render(props);await settle();const tree=d.render(props),trigger=find(tree,n=>n.props?.id===base.id);
 assert.equal(trigger.props['aria-invalid'],true);assert.equal(trigger.props['aria-describedby'],'validation-message field-country_code-lookup-error');d.unmount();
});
test('site read-only details preserve legacy country label without requesting mutation-authorized countries endpoint',async()=>{
 const calls:any[]=[],changed:string[]=[];
 const d=addressDriver(async(...args)=>{calls.push(args);throw Error('forbidden');},'it','SiteCountrySelect');
 const props={...base,disabled:true,readOnly:true,onChange:(value:string)=>changed.push(value)};
 d.render(props);await settle();const tree=d.render(props);
 assert.deepEqual(calls,[]);assert.equal(find(tree,n=>n.props?.name==='country_code').props.value,'FR');
 assert.equal(find(tree,n=>n.type?.name==='SelectItem'&&n.props.value==='FR').props.children,'Francia (FR)');
 assert.equal(find(tree,n=>n.props?.role==='status'),undefined);assert.deepEqual(changed,[]);d.unmount();
});
for(const locale of ['it','en']) test(`site catalog options preserve manual DB names and missing legacy country (${locale})`,async()=>{
 const calls:any[]=[], changed:string[]=[];
 const d=addressDriver(async(...args)=>{calls.push(args);return {ok:true,json:async()=>({items:[{isoCode:'IT',name:'Italia manuale'},{isoCode:'DE',name:'DE'}]})};},locale,'SiteCountrySelect');
 const props={...base,onChange:(value:string)=>changed.push(value)};
 d.render(props);await settle();const tree=d.render(props);
 assert.equal(calls[0][0],'/api/addresses/countries?tenantId=A');assert.equal(calls[0][1].method,'GET');assert.equal(calls[0][1].credentials,'same-origin');assert.ok(calls[0][1].signal instanceof AbortSignal);
 assert.equal(find(tree,n=>n.type?.name==='SelectItem'&&n.props.value==='IT').props.children,'Italia manuale');
 assert.match(find(tree,n=>n.type?.name==='SelectItem'&&n.props.value==='DE').props.children,locale==='it'?/Germania/:/Germany/);
 assert.match(find(tree,n=>n.type?.name==='SelectItem'&&n.props.value==='FR').props.children,locale==='it'?/Francia/:/France/);
 assert.equal(find(tree,n=>n.props?.name==='country_code').props.value,'FR');assert.deepEqual(changed,[]);assert.equal(calls.length,1);
 d.unmount();
});
for(const locale of ['it','en']) test(`country options use catalog names only, ignoring legacy response discriminator (${locale})`,async()=>{
 const d=addressDriver(async()=>({ok:true,json:async()=>({provider:'geoapify',items:[{isoCode:'IT',name:'Catalog name'}]})}),locale,'SiteCountrySelect');
 d.render({...base,value:''});await settle();const tree=d.render({...base,value:''});
 assert.equal(find(tree,n=>n.type?.name==='SelectItem'&&n.props.value==='IT').props.children,'Catalog name');
 assert.equal(find(tree,n=>n.type?.name==='SelectItem'&&n.props.value==='US'),undefined);
 d.unmount();
});
test('country context changes abort old request; late success and failure cannot replace current options or erase values; cancel has no writes',async()=>{
 const pending:any[]=[],changed:string[]=[];
 const d=addressDriver((url,options)=>new Promise((resolve,reject)=>pending.push({url,options,resolve,reject})),'en','SiteCountrySelect');
 const props={...base,onChange:(value:string)=>changed.push(value)};
 d.render(props);const next={...props,scope:(p:string)=>p+'?tenantId=B'};d.render(next);
 assert.equal(pending[0].options.signal.aborted,true);
 pending[1].resolve({ok:true,json:async()=>({items:[{isoCode:'IT',name:'Current'}]})});await settle();
 pending[0].resolve({ok:true,json:async()=>({items:[{isoCode:'US',name:'Stale'}]})});await settle();
 let tree=d.render(next);assert.ok(find(tree,n=>n.type?.name==='SelectItem'&&n.props.children==='Current'));assert.equal(find(tree,n=>n.props?.children==='Stale'),undefined);
 const third={...props,scope:(p:string)=>p+'?tenantId=C'};d.render(third);d.unmount();const snapshot=JSON.stringify(d.slots);
 pending[2].reject(Error('cancelled'));await settle();assert.equal(JSON.stringify(d.slots),snapshot);
 assert.deepEqual(changed,[]);assert.ok(pending.every(p=>p.options.method==='GET'));
});
test('failed country options retain legacy value, concise manual fallback and no mutations',async()=>{
 const changed:string[]=[];const d=addressDriver(async()=>{throw Error('private');},'en','SiteCountrySelect');const props={...base,onChange:(value:string)=>changed.push(value)};
 d.render(props);await settle();const tree=d.render(props);
 assert.equal(find(tree,n=>n.props?.name==='country_code').props.value,'FR');assert.match(find(tree,n=>n.props?.role==='status').props.children,/manually/);assert.deepEqual(changed,[]);d.unmount();
});
test('opted-in new site selects the first valid loaded country',async()=>{
 const chosen:string[]=[];const d=addressDriver(async()=>({ok:true,json:async()=>({items:[{isoCode:'',name:'invalid'},{isoCode:'IT',name:'Italy'}]})}),'en','SiteCountrySelect');
 d.render({...base,value:'',required:true,onDefault:(value:string)=>chosen.push(value)});await settle();
 assert.deepEqual(chosen,['IT']);d.unmount();
});
test('country default ignores stale, failed, empty and aborted lookups',async()=>{
 const pending:any[]=[],chosen:string[]=[];const d=addressDriver((url,options)=>new Promise((resolve,reject)=>pending.push({url,options,resolve,reject})),'en','SiteCountrySelect');
 const props={...base,value:'',required:true,onDefault:(v:string)=>chosen.push(v)};
 d.render(props);const next={...props,scope:(p:string)=>p+'?tenantId=B'};d.render(next);
 pending[0].resolve({ok:true,json:async()=>({items:[{isoCode:'US',name:'stale'}]})});pending[1].resolve({ok:true,json:async()=>({items:[]})});await settle();assert.deepEqual(chosen,[]);
 const third={...props,scope:(p:string)=>p+'?tenantId=C'};d.render(third);pending[2].reject(Error('failed'));await settle();assert.deepEqual(chosen,[]);
 const fourth={...props,scope:(p:string)=>p+'?tenantId=D'};d.render(fourth);d.unmount();pending[3].resolve({ok:true,json:async()=>({items:[{isoCode:'IT',name:'Italy'}]})});await settle();assert.deepEqual(chosen,[]);
});
