import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
import {ApiError} from '../lib/api.ts';
const initial={mode:'AUTO',prefix:'BP-',padding:6,nextNumber:1,version:0};
const props={session:{...session,permissions:['business-partner-numbering.read','business-partner-numbering.update']},scope:(p:string)=>p+'?tenantId=t',onError:(e:any)=>e.code||'error'};
const byId=(tree:any,id:string)=>find(tree,n=>n.props?.id===id);
const form=(tree:any)=>find(tree,n=>n.type==='form');
for(const locale of ['it','en']) test(`numbering loads persisted configuration and saves exact version with verification (${locale})`,async()=>{
 let current={...initial};
 const h=partnerHarness('business-partner-numbering',locale,(_path,method,body)=>{if(method==='PUT')current={...body,version:1};return current;});
 h.tree('BusinessPartnerNumbering',props);await h.flush();
 let tree=h.tree('BusinessPartnerNumbering',props);
 assert.equal(byId(tree,'bp-numbering-prefix').props.value,'BP-');
 byId(tree,'bp-numbering-prefix').props.onChange({target:{value:'PART-'}});
 tree=h.tree('BusinessPartnerNumbering',props);await form(tree).props.onSubmit({preventDefault(){}});
 assert.deepEqual(JSON.parse(JSON.stringify(h.calls[1])),{path:'/business-partner-numbering?tenantId=t',method:'PUT',body:{...initial,prefix:'PART-'}});
 assert.equal(h.calls[2].method,'GET');
 assert.match(h.render('BusinessPartnerNumbering',props),locale==='it'?/Modifiche salvate/:/Changes saved/);
});
test('numbering read-only and absent permissions never infer write or data authority',async()=>{
 const readonly={...props,session:{...session,permissions:['business-partner-numbering.read']}};
 const h=partnerHarness('business-partner-numbering','en',()=>initial);h.tree('BusinessPartnerNumbering',readonly);await h.flush();
 let tree=h.tree('BusinessPartnerNumbering',readonly);
 assert.equal(byId(tree,'bp-numbering-prefix').props.disabled,true);
 await form(tree).props.onSubmit({preventDefault(){}});assert.equal(h.calls.length,1);
 const no=partnerHarness('business-partner-numbering'),none={...props,session:{...session,permissions:['settings.update']}};
 no.tree('BusinessPartnerNumbering',none);await no.flush();assert.equal(no.calls.length,0);
});
for(const code of ['stale_version','numbering_in_use']) test(`numbering ${code} retains entered draft without reporting success`,async()=>{
 const h=partnerHarness('business-partner-numbering','en',(_path,method)=>{if(method==='PUT')throw new ApiError(code,409);return initial;});
 h.tree('BusinessPartnerNumbering',props);await h.flush();let tree=h.tree('BusinessPartnerNumbering',props);
 byId(tree,'bp-numbering-prefix').props.onChange({target:{value:'KEEP-'}});tree=h.tree('BusinessPartnerNumbering',props);
 await form(tree).props.onSubmit({preventDefault(){}});tree=h.tree('BusinessPartnerNumbering',props);
 assert.equal(byId(tree,'bp-numbering-prefix').props.value,'KEEP-');
 const html=h.render('BusinessPartnerNumbering',props);assert.match(html,new RegExp(code));assert.doesNotMatch(html,/Changes saved/);
 if(code==='numbering_in_use')assert.equal(byId(tree,'bp-numbering-prefix').props.disabled,true);
});
test('numbering Cancel restores the last persisted configuration without a write',async()=>{
 const h=partnerHarness('business-partner-numbering','en',()=>initial);h.tree('BusinessPartnerNumbering',props);await h.flush();
 let tree=h.tree('BusinessPartnerNumbering',props);byId(tree,'bp-numbering-prefix').props.onChange({target:{value:'UNSAVED-'}});
 tree=h.tree('BusinessPartnerNumbering',props);find(tree,n=>n.props?.children==='Cancel').props.onClick();
 tree=h.tree('BusinessPartnerNumbering',props);assert.equal(byId(tree,'bp-numbering-prefix').props.value,'BP-');assert.equal(h.calls.length,1);
});
