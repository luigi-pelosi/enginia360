import test from 'node:test';
import assert from 'node:assert/strict';
import {addressDriver} from './address-component-harness.ts';
import {find, harness, session} from './workspace-harness.ts';
test('local explicit region copies or clears, omitted/null region preserves manual draft',()=>{
 const d=addressDriver(async()=>{}), old={country_code:'IT',city:'Roma',province:'RM',region:'Manual',postal_code:'00100',address:'Via manuale'};
 for(const region of [undefined,null]) assert.equal(d.exports.addressSelection(old,'city',{label:'Roma',city:'Roma',region}).region,'Manual');
 assert.equal(d.exports.addressSelection(old,'city',{label:'Roma',city:'Roma',region:'Lazio'}).region,'Lazio');
 assert.equal(d.exports.addressSelection(old,'city',{label:'Roma',city:'Roma',region:''}).region,'');
});
test('local city selection preserves manual street in the parent draft and only one explicit Save writes',async()=>{
 const resource={key:'sites',fields:['address','city','province','region','postal_code','country_code'].map(name=>({name,type:'text' as const,required:false}))};
 const old={address:'Via manuale 17',city:'Roma',province:'RM',region:'Lazio',postal_code:'00100',country_code:'IT'};
 const props={resource,row:null,canWrite:true,session,scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:()=> 'error'};
 const h=harness('en',{0:old}),tree=h.components.RecordEditor(props);
 find(tree,n=>n.type?.name==='AddressAutocomplete'&&n.props.field==='city').props.onSelect({label:'Capua · 81043',address:'',city:'Capua',province:'CE',region:'Campania',postalCode:'81043',countryCode:'IT'});
 const draft=(h.updates[0] as Function)(old);
 assert.equal(draft.address,'Via manuale 17');assert.equal(draft.region,'Campania');assert.equal(draft.postal_code,'81043');assert.deepEqual(h.apiCalls,[]);
 const saved=harness('en',{0:draft});const next=saved.components.RecordEditor(props);
 await find(next,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.deepEqual(saved.apiCalls,['/data/sites/save']);
 assert.equal((saved.apiPayloads[0] as any).values.address,'Via manuale 17');
});
test('local suggestions never falsely attribute Geoapify and preserve leading postal zeros',async()=>{
 const d=addressDriver(async()=>({ok:true,json:async()=>({items:[{label:'Roma · 00100',city:'Roma',postalCode:'00100',region:'Lazio'}],attribution:''})}));
 const props={id:'city',field:'city',value:'Rom',context:{country_code:'IT'},scope:(p:string)=>p,disabled:false,required:false,onChange(){},onSelect(){}};
 let tree=d.render(props);find(tree,n=>n.props?.role==='combobox').props.onFocus();d.render(props);await d.runTimers();tree=d.render(props);
 assert.ok(find(tree,n=>n.props?.role==='option'));
 assert.equal(find(tree,n=>n.type==='a'&&n.props.href.includes('geoapify')),undefined);
 assert.equal(find(tree,n=>n.type==='a'&&n.props.href.includes('openstreetmap')),undefined);
 d.unmount();
});
