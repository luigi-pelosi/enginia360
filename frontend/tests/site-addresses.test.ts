import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {harness, find, session, workspace} from './workspace-harness.ts';
import {partnerHarness} from './record-editor-harness.ts';
import type {Resource} from '../lib/model.ts';
const codes = JSON.parse(readFileSync(new URL('./country-codes.json', import.meta.url),'utf8')) as string[];
const resource: Resource = {key:'sites',fields:[{name:'name',type:'text',required:true},{name:'code',type:'text',required:false},{name:'vat_number',type:'text',required:false},{name:'tax_code',type:'text',required:false},{name:'country_code',type:'select',required:false,options:codes}]};
const props = {resource,row:null,canWrite:true,session,scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:()=> 'error'};
test('backend fiscal rejection has concise IT/EN feedback',()=>{
 for(const locale of ['it','en']) {
  const messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));
  assert.equal(messages.errors.tax_identity_required,messages.app.taxIdentityRequired);
 }
});
test('fiscal alternatives block blank/whitespace submission without top message or orphan description',async()=>{
 const p={...props,tenant:'t'}; const h=partnerHarness('workspace','it'); h.tree('RecordEditor',p); await h.flush(); h.state[0]={name:'Sede',code:'',vat_number:'  ',tax_code:'',country_code:''};
 const tree=h.tree('RecordEditor',p);
 assert.equal(find(tree,n=>n.props?.id==='tax-identity-requirement'),undefined);
 for(const name of ['vat_number','tax_code']) assert.equal(find(tree,n=>n.props?.id===`field-${name}`).props['aria-describedby'],undefined);
 assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,true);
 assert.equal(find(tree,n=>n.props?.id==='field-vat_number').props.required,true);
 assert.equal(find(tree,n=>n.props?.id==='field-tax_code').props.required,true);
 await find(tree,n=>n.props?.id==='record-form').props.onSubmit({preventDefault(){}});
 assert.deepEqual(h.calls,[]);
 const vh=partnerHarness('workspace','en'); vh.tree('RecordEditor',p); await vh.flush(); vh.state[0]={name:'Site',vat_number:'VAT',tax_code:'',country_code:''}; const valid=vh.tree('RecordEditor',p);
 assert.equal(find(valid,n=>n.props?.id==='field-tax_code').props.required,false);
 assert.equal(find(valid,n=>n.props?.form==='record-form').props.disabled,false);
 assert.equal(find(valid,n=>n.props?.id==='tax-identity-requirement'),undefined,'nessun messaggio di compilazione dopo un identificativo fiscale valido');
});
for(const locale of ['it','en']) test(`site country provider control and table localize (${locale}), no default`,()=>{
 const h=harness(locale); const tree=h.components.RecordEditor(props);
 const select=find(tree,n=>n.type?.name==='SiteCountrySelect');
 assert.equal(select.props.value,'');
 assert.equal(codes.length,249);
 assert.equal(select.props.scope,props.scope);
 const html=workspace(resource,['sites.read'],{id:'s',name:'Sede',country_code:'IT'},locale);
 assert.ok(html.includes(locale==='it'?'Italia (IT)':'Italy (IT)'));
});
