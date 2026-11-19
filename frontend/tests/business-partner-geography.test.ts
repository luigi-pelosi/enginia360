import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
import {ApiError} from '../lib/api.ts';
const props={session:{...session,permissions:['business-partners.create','business-partners.read','business-partners.update']},scope:(p:string)=>p+(p.includes('?')?'&':'?')+'tenantId=tenant',onError:()=> 'error',id:null,onClose(){},onSaved(){}};
const component=(tree:any,name:string,id:string)=>find(tree,n=>n.type?.name===name&&n.props.id===id);
const action=(tree:any,id:string)=>find(tree,n=>n.props?.['data-action']===id);
const byId=(tree:any,id:string)=>find(tree,n=>n.props?.id===id);
const apply=(tree:any)=>find(tree,n=>n.props?.['data-bp-related-form']).props.onSubmit({preventDefault(){},stopPropagation(){}});
const render=(h:any,p:any=props)=>h.tree('BusinessPartnerEditor',p);

test('geographic controls preserve indexed server validation feedback',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>{throw new ApiError('business_partner_address_required',400,'addresses[0].city');});
 let tree=render(h);byId(tree,'bp-legal_name').props.onChange({target:{value:'Partner'}});tree=render(h);action(tree,'add-address').props.onClick();tree=render(h);
 apply(tree);tree=render(h);
 await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});tree=render(h);
 const city=component(tree,'AddressAutocomplete','bp-address-0-city');
 assert.equal(city.props['aria-invalid'],true);assert.equal(city.props['aria-describedby'],'bp-address-0-city-error');
 assert.ok(byId(tree,'bp-address-0-city-error'));
});

test('BP address fields reuse site autocomplete and country controls with resource-scoped lookup',()=>{
 const h=partnerHarness();let tree=render(h);action(tree,'add-address').props.onClick();tree=render(h);
 for(const [key,field] of [['street','address'],['city','city'],['province','province'],['postal_code','postal_code']]) {
  const input=component(tree,'AddressAutocomplete',`bp-address-0-${key}`);
  assert.ok(input,`${key} must reuse shared autocomplete`);
  assert.equal(input.props.field,field);assert.equal(input.props.disabled,false);
  const url=new URL(input.props.scope('/addresses/autocomplete?field=city&text=Rom'),'https://app.invalid');
  assert.equal(url.searchParams.get('resource'),'business-partners');assert.equal(url.searchParams.get('tenantId'),'tenant');
 }
 const country=component(tree,'SiteCountrySelect','bp-address-0-country');assert.ok(country);
 const url=new URL(country.props.scope('/addresses/countries'),'https://app.invalid');
 assert.equal(url.searchParams.get('resource'),'business-partners');assert.equal(country.props.readOnly,false);
 assert.equal(h.calls.length,0,'rendering controls does not persist the draft');
});

test('selecting geography affects only one address, preserves manual street and submits one aggregate',async()=>{
 const h=partnerHarness('business-partner-workspace','it',()=>({id:'bp1'}));let tree=render(h);
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Partner'}});tree=render(h);
 action(tree,'add-address').props.onClick();tree=render(h);
 component(tree,'AddressAutocomplete','bp-address-0-street').props.onChange('Via manuale');tree=render(h);
 byId(tree,'bp-address-0-street_number').props.onChange({target:{value:'17'}});tree=render(h);
 byId(tree,'bp-address-0-label').props.onChange({target:{value:'Consegne'}});tree=render(h);
 component(tree,'AddressAutocomplete','bp-address-0-city').props.onSelect({label:'Roma · 00100',city:'Roma',province:'RM',postalCode:'00100',countryCode:'IT',region:'Lazio',address:''});tree=render(h);
 assert.equal(component(tree,'AddressAutocomplete','bp-address-0-street').props.value,'Via manuale');
 assert.equal(component(tree,'AddressAutocomplete','bp-address-0-postal_code').props.value,'00100');
 assert.equal(component(tree,'AddressAutocomplete','bp-address-0-province').props.value,'RM');
 apply(tree);tree=render(h);action(tree,'add-address').props.onClick();tree=render(h);
 assert.equal(component(tree,'AddressAutocomplete','bp-address-1-city').props.value,'');apply(tree);tree=render(h);
 assert.equal(h.calls.length,0);
 await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 const writes=h.calls.filter((c:any)=>c.method!=='GET');assert.equal(writes.length,1);
 const address=writes[0].body.addresses[0];assert.equal(address.street,'Via manuale');assert.equal(address.street_number,'17');assert.equal(address.label,'Consegne');assert.equal(address.postal_code,'00100');
 assert.ok(!('address' in address)&&!('region' in address),'lookup aliases must not leak into the BP contract');
});

test('readonly BP addresses retain geographic values without authorizing lookup or edits',async()=>{
 const record={id:'bp1',version:1,kind:'ORGANIZATION',status:'DRAFT',legal_name:'Partner',code:'BP-1',addresses:[{street:'Via salvata',city:'Roma',province:'RM',postal_code:'00100',country_code:'IT',usages:[]}],tax_identifiers:[],contact_channels:[]};
 const h=partnerHarness('business-partner-workspace','en',()=>record),p={...props,id:'bp1',session:{...props.session,permissions:['business-partners.read']}};
 render(h,p);await h.flush();let tree=render(h,p);action(tree,'details-address-0').props.onClick();tree=render(h,p);
 const city=component(tree,'AddressAutocomplete','bp-address-0-city');assert.ok(city);assert.equal(city.props.disabled,true);
 assert.equal(component(tree,'SiteCountrySelect','bp-address-0-country').props.readOnly,true);
 city.props.onSelect({label:'Another',city:'Changed'});city.props.onChange('Changed');tree=render(h,p);
 assert.equal(component(tree,'AddressAutocomplete','bp-address-0-city').props.value,'Roma');
 assert.equal(h.calls.length,1,'readonly details only fetch their record');
});
