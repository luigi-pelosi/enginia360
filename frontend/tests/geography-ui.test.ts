import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, find, session} from './workspace-harness.ts';
import type {Resource} from '../lib/model.ts';
const scope=(p:string)=>`${p}${p.includes('?')?'&':'?'}tenantId=tenant`;
const props={row:null,canWrite:true,session,scope,load:async()=>[],onClose(){},onSaved:async()=>{},onError:()=> 'error'};
const countries:Resource={key:'countries',fields:[{name:'name',type:'text',required:true},{name:'iso_code',type:'text',required:true},{name:'notes',type:'textarea',required:false},{name:'is_enabled',type:'boolean',required:true}]};
test('global catalogs appear without tenant selection and ordinary readers cannot mutate',()=>{
 for(const locale of ['it','en']) {
  const h=harness(locale,{0:{...session,isSuperAdmin:true,tenantId:null},1:false,5:[countries],6:'countries',7:''});
  const html=h.render('default');
  assert.match(html,locale==='it'?/Torna a Sistema/:/Back to System/);
  assert.match(html,locale==='it'?/Nazioni/:/Countries/);
  assert.match(html,/table-toolbar/);
 }
 const h=harness('en',{0:{...session,permissions:['countries.read']},1:false,5:[{...countries,readOnly:true}],6:'countries',7:'tenant'});
 const html=h.render('default');assert.match(html,/Countries/);assert.doesNotMatch(html,/New</);
 const denied=harness('en',{0:session,1:false,5:[countries],6:'countries',7:'tenant'}).render('default');
 assert.match(denied,/No resources available/);assert.doesNotMatch(denied,/table-toolbar/);
});
test('country ISO input is uppercase canonical with exactly two alphabetic characters',()=>{
 const h=harness('en'), tree=h.components.RecordEditor({...props,resource:countries});
 const input=find(tree,n=>n.props?.id==='field-iso_code');
 assert.equal(input.props.maxLength,2);assert.equal(input.props.pattern,'[A-Z]{2}');
 input.props.onChange({target:{value:'it'}});
 assert.equal((h.updates[0] as Function)({}).iso_code,'IT');
});
test('site country options load through scoped server provider and region stays manual',()=>{
 const resource:Resource={key:'sites',fields:[{name:'country_code',type:'select',required:false,options:['IT','FR']},{name:'region',type:'text',required:false}]};
 const h=harness('en'), tree=h.components.RecordEditor({...props,resource});
 const select=find(tree,n=>n.type?.name==='SiteCountrySelect');
 assert.ok(select,'site options must come from server provider, not static ISO metadata');
 assert.equal(select.props.scope,scope);
 const region=find(tree,n=>n.props?.id==='field-region');assert.ok(region);assert.notEqual(region.type?.name,'AddressAutocomplete');
});
