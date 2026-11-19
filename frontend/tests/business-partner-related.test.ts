import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const p={session:{...session,permissions:['business-partners.create','business-partners.read','business-partners.update']},scope:(s:string)=>s,onError:(e:any)=>e.code,id:null,onClose(){},onSaved(){}};
const action=(tree:any,s:string)=>find(tree,n=>n.props?.['data-action']===s);
const field=(tree:any,s:string)=>find(tree,n=>n.props?.id===s);
const event={preventDefault(){},stopPropagation(){}};
const base={id:'bp1',version:3,kind:'ORGANIZATION',status:'DRAFT',code:'BP-1',legal_name:'Demo',tax_identifiers:[{country_code:'IT',identifier_type:'VAT',value:'12345678901'}],addresses:[{label:'Office',street:'Via Uno',street_number:'1',postal_code:'00100',city:'Roma',province:'RM',country_code:'IT',additional_info:'Keep me',usages:[{usage:'SHIPPING',is_default:true}]}],contact_channels:[{channel_type:'EMAIL',value:'a@example.com',purpose:'Office',is_primary:true}]};
for(const locale of ['it','en'])test(`cancelled defaults and primary changes never alter the staged aggregate (${locale})`,async()=>{
 const h=partnerHarness('business-partner-workspace',locale,()=>base),props={...p,id:'bp1'};const render=()=>h.tree('BusinessPartnerEditor',props);
 h.tree('BusinessPartnerEditor',props);await h.flush();let tree=render();
 for(const kind of ['address','contact']) {
  action(tree,`add-${kind}`).props.onClick();tree=render();
  if(kind==='address') {field(tree,'bp-address-1-SHIPPING').props.onCheckedChange(true);tree=render();field(tree,'bp-address-1-SHIPPING-default').props.onCheckedChange(true);}
  else field(tree,'bp-contact-1-primary').props.onCheckedChange(true);
  tree=render();action(tree,'cancel-related').props.onClick();tree=render();assert.equal(action(tree,`details-${kind}-1`),undefined);
  action(tree,`edit-${kind}-0`).props.onClick();tree=render();
  if(kind==='address')field(tree,'bp-address-0-SHIPPING-default').props.onCheckedChange(false);else field(tree,'bp-contact-0-primary').props.onCheckedChange(false);
  tree=render();action(tree,'cancel-related').props.onClick();tree=render();
 }
 await find(tree,n=>n.type==='form').props.onSubmit(event);
 const body=h.calls.find(c=>c.method==='PUT')!.body;assert.equal(body.addresses.length,1);assert.equal(body.addresses[0].usages[0].is_default,true);assert.equal(body.addresses[0].additional_info,'Keep me');assert.equal(body.contactChannels[0].is_primary,true);
});
for(const locale of ['it','en'])test(`readonly row Details are available with no mutators and safe close (${locale})`,async()=>{
 const h=partnerHarness('business-partner-workspace',locale,()=>base),props={...p,id:'bp1',session:{...session,permissions:['business-partners.read']}};const render=()=>h.tree('BusinessPartnerEditor',props);
 render();await h.flush();let tree=render();
 for(const kind of ['tax','address','contact']) {
  assert.ok(action(tree,`details-${kind}-0`));for(const operation of ['add','edit','remove'])assert.equal(action(tree,operation==='add'?`add-${kind}`:`${operation}-${kind}-0`),undefined);
  action(tree,`details-${kind}-0`).props.onClick();tree=render();assert.ok(find(tree,n=>n.props?.['data-bp-related-editor']===kind));assert.equal(action(tree,'apply-related'),undefined);
  const key=kind==='tax'?'value':kind==='address'?'city':'value';assert.equal(field(tree,`bp-${kind}-0-${key}`).props.disabled,true);
  assert.match(h.render('BusinessPartnerEditor',props),locale==='it'?/Conferma con Salva/:/Confirm with Save/);
  action(tree,'cancel-related').props.onClick();tree=render();
 }
 await find(tree,n=>n.type==='form').props.onSubmit(event);assert.equal(h.calls.length,1);
});
test('child submission stops bubbling and aggregate Save is refused while a child is pending',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({id:'bp1'}));const render=()=>h.tree('BusinessPartnerEditor',p);let tree=render();action(tree,'add-tax').props.onClick();tree=render();
 await find(tree,n=>n.type==='form').props.onSubmit(event);assert.equal(h.calls.length,0);
 field(tree,'bp-tax-0-value').props.onChange({target:{value:'12345678901'}});tree=render();let stopped=0,prevented=0;
 find(tree,n=>n.props?.['data-bp-related-form']).props.onSubmit({preventDefault(){prevented++;},stopPropagation(){stopped++;}});assert.equal(stopped,1);assert.equal(prevented,1);assert.equal(h.calls.length,0);
});
test('compact tables stage a child only on Apply and Cancel discards changes',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({id:'bp1'}));const render=()=>h.tree('BusinessPartnerEditor',p);let tree=render();
 field(tree,'bp-legal_name').props.onChange({target:{value:'Partner'}});tree=render();
 for(const kind of ['tax','address','contact'])assert.ok(find(tree,n=>n.props?.['data-bp-related-table']===kind));
 action(tree,'add-tax').props.onClick();tree=render();assert.ok(find(tree,n=>n.props?.['data-bp-related-editor']==='tax'));
 assert.equal(find(tree,n=>n.props?.type==='submit'&&!n.props?.['data-action'])?.props.disabled,true);
 field(tree,'bp-tax-0-value').props.onChange({target:{value:'12345678901'}});tree=render();
 action(tree,'cancel-related').props.onClick();tree=render();assert.equal(action(tree,'edit-tax-0'),undefined);
 action(tree,'add-tax').props.onClick();tree=render();assert.equal(field(tree,'bp-tax-0-value').props.value,'');
 field(tree,'bp-tax-0-value').props.onChange({target:{value:'12345678901'}});tree=render();
 find(tree,n=>n.type==='form'&&n.props['data-bp-related-form']).props.onSubmit(event);tree=render();
 assert.ok(action(tree,'details-tax-0'));assert.equal(field(tree,'bp-tax-0-value'),undefined);assert.equal(h.calls.length,0);
 action(tree,'edit-tax-0').props.onClick();tree=render();field(tree,'bp-tax-0-value').props.onChange({target:{value:'discard'}});tree=render();
 find(tree,n=>n.props?.open===true&&n.props?.onOpenChange).props.onOpenChange(false);tree=render();
 action(tree,'remove-tax-0').props.onClick();tree=render();assert.ok(action(tree,'confirm-remove-related'));assert.ok(action(tree,'details-tax-0'));
 action(tree,'cancel-remove-related').props.onClick();tree=render();assert.ok(action(tree,'details-tax-0'));
 await find(tree,n=>n.type==='form').props.onSubmit(event);assert.equal(h.calls[0].body.taxIdentifiers[0].value,'12345678901');
});
