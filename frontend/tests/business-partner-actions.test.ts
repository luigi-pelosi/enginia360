import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const record={id:'bp',version:1,kind:'ORGANIZATION',status:'DRAFT',legal_name:'Partner',code:'BP-1',tax_identifiers:[{country_code:'IT',identifier_type:'VAT',value:'12345678901'}],addresses:[{street:'Via Roma',city:'Roma',postal_code:'00100',country_code:'IT',usages:[]}],contact_channels:[{channel_type:'EMAIL',value:'office@example.invalid',is_primary:true}]};
for(const locale of ['it','en'])test(`related table actions are fixed-width, centered and accessible icon buttons (${locale})`,async()=>{
 const props={session:{...session,permissions:['business-partners.read','business-partners.update']},scope:(p:string)=>p,onError:()=> 'error',id:'bp',onClose(){},onSaved(){}};
 const h=partnerHarness('business-partner-workspace',locale,()=>record);
 h.tree('BusinessPartnerEditor',props);await h.flush();const tree=h.tree('BusinessPartnerEditor',props);
 for(const kind of ['tax','address','contact']) {
  const table=find(tree,n=>n.props?.['data-bp-related-table']===kind);
  const header=find(table,n=>n.props?.['data-bp-actions']==='header');assert.ok(header,'fixed action header');
  assert.match(header.props.className,/w-\[120px\]/);assert.equal(header.props.kind,'actions');
  const cell=find(table,n=>n.props?.['data-bp-actions']==='cell');assert.ok(cell);
  assert.match(cell.props.className,/w-\[120px\]/);assert.equal(cell.props.kind,'actions');
  assert.ok(find(cell,n=>n.props?.className?.includes('justify-center')));
  for(const operation of ['details','edit','remove']) {
   const button=find(cell,n=>n.props?.['data-action']===`${operation}-${kind}-0`);
   assert.equal(button.props.size,'icon');assert.ok(button.props['aria-label']);assert.equal(button.props.title,button.props['aria-label']);
   assert.notEqual(typeof button.props.children,'string','no visible action text');
   assert.equal(button.props.children.props['aria-hidden'],true);
  }
 }
});
