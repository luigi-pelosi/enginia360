import test from 'node:test';
import assert from 'node:assert/strict';
import {find, session} from './workspace-harness.ts';
import {partnerHarness} from './record-editor-harness.ts';
import type {Resource} from '../lib/model.ts';
const names=['address','city','province','postal_code','country_code'];
const resource:Resource={key:'sites',fields:[{name:'name',type:'text',required:true},{name:'vat_number',type:'text',required:false},{name:'tax_code',type:'text',required:false},...names.map(name=>({name,type:name==='country_code'?'select' as const:'text' as const,required:true,options:name==='country_code'?['IT','US']:undefined})),{name:'is_enabled',type:'boolean',required:true}]};
const complete={name:'Site',vat_number:'VAT',tax_code:'',address:'Main street',city:'New York',province:'NY',postal_code:'10001',country_code:'US',is_enabled:false};
const props={resource,row:null,canWrite:true,session,tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:()=> 'error'};
for(const name of names) for(const invalid of [undefined,null,'','  \t ']) test(`required ${name} blocks Save and synthetic submit for ${JSON.stringify(invalid)}`,async()=>{
 const h=partnerHarness('workspace','it'); h.tree('RecordEditor',props); await h.flush(); h.state[0]={...complete,[name]:invalid}; const tree=h.tree('RecordEditor',props);
 assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,true);
 await find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.deepEqual(h.calls,[]);
});
test('complete manual foreign address accepts false boolean and metadata required markers',async()=>{
 const h=partnerHarness('workspace','en'); h.tree('RecordEditor',props); await h.flush(); h.state[0]=complete; const tree=h.tree('RecordEditor',props);
 assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,false);
 for(const name of names){
  const label=find(tree,n=>n.props?.htmlFor===`field-${name}`);assert.equal(label.props.required,true);
 }
 await find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.deepEqual(h.calls.map(call=>call.path),['/data/sites/save']);
});
