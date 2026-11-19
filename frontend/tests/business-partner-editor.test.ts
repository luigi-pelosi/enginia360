import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError} from '../lib/api.ts';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const scope=(path:string)=>`${path}${path.includes('?')?'&':'?'}tenantId=t`;
const props={session:{...session,permissions:['business-partners.read','business-partners.create','business-partners.update']},scope,onError:(e:any)=>e.code||'error',id:null,onClose(){},onSaved(){}};
const byId=(tree:any,id:string)=>find(tree,n=>n.props?.id===id);
const action=(tree:any,text:string)=>find(tree,n=>n.props?.['data-action']===text);
const form=(tree:any)=>find(tree,n=>n.type==='form');
const apply=(tree:any)=>find(tree,n=>n.props?.['data-bp-related-form']).props.onSubmit({preventDefault(){},stopPropagation(){}});
for (const locale of ['it','en']) test(`identity editor omits the removed lifecycle hint (${locale})`,()=>{
 const h=partnerHarness('business-partner-workspace',locale);
 const html=h.render('BusinessPartnerEditor',props);
 assert.doesNotMatch(html,/La bozza può essere incompleta|Drafts may be incomplete/);
 const tree=h.tree('BusinessPartnerEditor',props);
 assert.ok(byId(tree,'bp-status'));
 assert.ok(byId(tree,'bp-legal_name'));
});
test('new partner has operator identity fields and saves one complete aggregate without numbering authority',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({id:'bp1'}));
 let tree=h.tree('BusinessPartnerEditor',props);
 assert.ok(byId(tree,'bp-kind'),'kind operator select');
 assert.ok(find(tree,n=>n.props?.value==='ACTIVE'&&n.props?.onValueChange),'active status selected by default');
 assert.ok(byId(tree,'bp-legal_name'),'legal name field');
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Officina Uno'}});
 tree=h.tree('BusinessPartnerEditor',props);
 assert.ok(form(tree),'one aggregate form');
 await form(tree).props.onSubmit({preventDefault(){}});
 assert.equal(h.calls.filter(c=>c.method!=='GET').length,1);
 assert.equal(h.calls[1].path,'/data/business-partners/bp1?tenantId=t');
 assert.equal(h.calls[0].path,'/data/business-partners/save?tenantId=t');
 assert.equal(h.calls[0].method,'POST');
 assert.deepEqual(JSON.parse(JSON.stringify(h.calls[0].body)),{values:{kind:'ORGANIZATION',legal_name:'Officina Uno',first_name:null,last_name:null,status:'ACTIVE'},taxIdentifiers:[],addresses:[],contactChannels:[]});
 assert.ok(!h.calls.some(c=>c.path.includes('numbering')));
});
test('nested tax identifiers, multiple addresses and contact channels edit locally and submit together',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({id:'bp1'}));
 let tree=h.tree('BusinessPartnerEditor',props);
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Partner'}});tree=h.tree('BusinessPartnerEditor',props);
 assert.ok(action(tree,'add-tax'),'add tax identifier action');
 action(tree,'add-tax').props.onClick();
 tree=h.tree('BusinessPartnerEditor',props);
 byId(tree,'bp-tax-0-value').props.onChange({target:{value:'12345678901'}});tree=h.tree('BusinessPartnerEditor',props);apply(tree);tree=h.tree('BusinessPartnerEditor',props);
 action(tree,'add-address').props.onClick();
 tree=h.tree('BusinessPartnerEditor',props);
 byId(tree,'bp-address-0-city').props.onChange('Roma');
 assert.equal(byId(tree,'bp-address-0-postal_code').props.required,true,'postal code required by aggregate contract');tree=h.tree('BusinessPartnerEditor',props);apply(tree);tree=h.tree('BusinessPartnerEditor',props);
 action(tree,'add-contact').props.onClick();
 tree=h.tree('BusinessPartnerEditor',props);
 byId(tree,'bp-contact-0-value').props.onChange({target:{value:'office@example.com'}});tree=h.tree('BusinessPartnerEditor',props);apply(tree);
 tree=h.tree('BusinessPartnerEditor',props);
 assert.equal(h.calls.length,0,'nested edits are draft only');
 await form(tree).props.onSubmit({preventDefault(){}});
 const payload=h.calls[0].body;
 assert.equal(payload.taxIdentifiers[0].value,'12345678901');
 assert.equal(payload.addresses[0].city,'Roma');
 assert.equal(payload.contactChannels[0].value,'office@example.com');
 assert.equal(h.calls.filter(c=>c.method!=='GET').length,1);
});
test('manual numbering server validation keeps draft and asks for code; known AUTO never submits a manual code',async()=>{
 let reject=true;
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='POST'&&reject) throw new ApiError('business_partner_code_required',400);return {id:'bp1'};});
 let tree=h.tree('BusinessPartnerEditor',props);
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Keep me'}});
 tree=h.tree('BusinessPartnerEditor',props);await form(tree).props.onSubmit({preventDefault(){}});
 tree=h.tree('BusinessPartnerEditor',props);
 assert.equal(byId(tree,'bp-code').props.required,true);
 assert.equal(byId(tree,'bp-legal_name').props.value,'Keep me');
 reject=false;byId(tree,'bp-code').props.onChange({target:{value:'MAN-1'}});
 tree=h.tree('BusinessPartnerEditor',props);await form(tree).props.onSubmit({preventDefault(){}});
 assert.equal(h.calls.filter(c=>c.method==='POST').at(-1)?.body.values.code,'MAN-1');
 const autoProps={...props,session:{...props.session,permissions:[...props.session.permissions,'business-partner-numbering.read']}};
 const auto=partnerHarness('business-partner-workspace','en',path=>path.includes('numbering')?{mode:'AUTO'}:{id:'bp2'});
 auto.tree('BusinessPartnerEditor',autoProps);await auto.flush();
 const autoTree=auto.tree('BusinessPartnerEditor',autoProps);
 assert.equal(byId(autoTree,'bp-code'),undefined);
});
test('successful create followed by a failed readback retries verification without a duplicate create',async()=>{
 let failRead=true, saved=0;
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='GET'&&failRead)throw new ApiError('network_error',0);return {id:'bp1'};});
 const p={...props,onSaved:()=>saved++};
 let tree=h.tree('BusinessPartnerEditor',p);
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Partner'}});tree=h.tree('BusinessPartnerEditor',p);
 await form(tree).props.onSubmit({preventDefault(){}});
 assert.equal(saved,0);
 failRead=false;tree=h.tree('BusinessPartnerEditor',p);
 await form(tree).props.onSubmit({preventDefault(){}});
 assert.equal(h.calls.filter(c=>c.method==='POST').length,1,'never recreate a committed partner');
 assert.equal(saved,1);
});
test('invalid contact phone and unsafe website cannot be submitted',async()=>{
 const h=partnerHarness();let tree=h.tree('BusinessPartnerEditor',props);
 action(tree,'add-contact').props.onClick();tree=h.tree('BusinessPartnerEditor',props);
 const channel=find(tree,n=>n.props?.value==='EMAIL'&&typeof n.props?.onValueChange==='function');
 channel.props.onValueChange('PHONE');tree=h.tree('BusinessPartnerEditor',props);
 byId(tree,'bp-contact-0-value').props.onChange({target:{value:'not-a-phone'}});tree=h.tree('BusinessPartnerEditor',props);
 apply(tree);tree=h.tree('BusinessPartnerEditor',props);
 assert.equal(h.calls.length,0,'invalid phone refused locally');
 const phone=find(tree,n=>n.props?.value==='PHONE'&&typeof n.props?.onValueChange==='function');phone.props.onValueChange('WEBSITE');tree=h.tree('BusinessPartnerEditor',props);
 byId(tree,'bp-contact-0-value').props.onChange({target:{value:'javascript:alert(1)'}});tree=h.tree('BusinessPartnerEditor',props);
 apply(tree);assert.equal(h.calls.length,0);
});
const record={id:'bp1',version:7,kind:'ORGANIZATION',legal_name:null,first_name:null,last_name:null,code:'BP-000001',status:'DRAFT',tax_identifiers:[],addresses:[],contact_channels:[]};
test('a fiscally and legally incomplete DRAFT can be read and saved; nullable server names normalize safely',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>record),p={...props,id:'bp1'};
 h.tree('BusinessPartnerEditor',p);await h.flush();
 const tree=h.tree('BusinessPartnerEditor',p);
 assert.equal(byId(tree,'bp-legal_name').props.value,'');
 await form(tree).props.onSubmit({preventDefault(){}});
 const write=h.calls.find(c=>c.method==='PUT');assert.ok(write);
 assert.equal(write.body.expectedVersion,7);assert.equal(write.body.values.legal_name,null);
 assert.ok(!('code' in write.body.values),'immutable existing code omitted');
});
for(const code of ['duplicate_tax_identifier','stale_version']) test(`${code} retains complete edited aggregate and original expectedVersion`,async()=>{
 const savedRecord={...record,legal_name:'Original',tax_identifiers:[{id:'tax-server',normalized_value:'12345678901',country_code:'IT',identifier_type:'VAT',value:'12345678901'}]};
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='PUT')throw new ApiError(code,409);return savedRecord;}),p={...props,id:'bp1'};
 h.tree('BusinessPartnerEditor',p);await h.flush();let tree=h.tree('BusinessPartnerEditor',p);
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Edited'}});tree=h.tree('BusinessPartnerEditor',p);
 await form(tree).props.onSubmit({preventDefault(){}});tree=h.tree('BusinessPartnerEditor',p);
 assert.equal(byId(tree,'bp-legal_name').props.value,'Edited');assert.match(h.render('BusinessPartnerEditor',p),/12345678901/);
 const write=h.calls.find(c=>c.method==='PUT')!;assert.equal(write.body.expectedVersion,7);assert.ok(!('id' in write.body.taxIdentifiers[0]));assert.ok(!('normalized_value' in write.body.taxIdentifiers[0]));
 assert.match(h.render('BusinessPartnerEditor',p),new RegExp(code));
});
test('address defaults and contact primary are exclusive only on Apply; removal sends explicit empty collections',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({id:'bp1'}));const render=()=>h.tree('BusinessPartnerEditor',props);let tree=render();
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Partner'}});tree=render();
 for(let i=0;i<2;i++) {
   action(tree,'add-address').props.onClick();tree=render();byId(tree,`bp-address-${i}-SHIPPING`).props.onCheckedChange(true);tree=render();byId(tree,`bp-address-${i}-SHIPPING-default`).props.onCheckedChange(true);tree=render();apply(tree);tree=render();
 }
 for(const [i,expected] of [[0,false],[1,true]]) {action(tree,`details-address-${i}`).props.onClick();tree=render();assert.equal(byId(tree,`bp-address-${i}-SHIPPING-default`).props.checked,expected);action(tree,'cancel-related').props.onClick();tree=render();}
 for(let i=0;i<2;i++) {action(tree,'add-contact').props.onClick();tree=render();byId(tree,`bp-contact-${i}-value`).props.onChange({target:{value:`${i}@example.com`}});tree=render();byId(tree,`bp-contact-${i}-primary`).props.onCheckedChange(true);tree=render();apply(tree);tree=render();}
 for(const [i,expected] of [[0,false],[1,true]]) {action(tree,`details-contact-${i}`).props.onClick();tree=render();assert.equal(byId(tree,`bp-contact-${i}-primary`).props.checked,expected);action(tree,'cancel-related').props.onClick();tree=render();}
 for(let i=0;i<2;i++)for(const kind of ['address','contact']){action(tree,`remove-${kind}-0`).props.onClick();tree=render();await action(tree,'confirm-remove-related').props.onClick({preventDefault(){}});tree=render();}
 await form(tree).props.onSubmit({preventDefault(){}});assert.equal(h.calls[0].body.addresses.length,0);assert.equal(h.calls[0].body.contactChannels.length,0);
});
for(const locale of ['it','en']) test(`read-only details show localized operator sections with no mutation controls (${locale})`,async()=>{
 const h=partnerHarness('business-partner-workspace',locale,()=>({...record,legal_name:'Demo'})),p={...props,id:'bp1',session:{...session,permissions:['business-partners.read']}};
 h.tree('BusinessPartnerEditor',p);await h.flush();const tree=h.tree('BusinessPartnerEditor',p);
 assert.equal(byId(tree,'bp-legal_name').props.disabled,true);assert.equal(action(tree,'add-tax'),undefined);
 await form(tree).props.onSubmit({preventDefault(){}});assert.equal(h.calls.length,1);
 const html=h.render('BusinessPartnerEditor',p);assert.match(html,locale==='it'?/Identificativi fiscali/:/Tax identifiers/);assert.match(html,locale==='it'?/Indirizzi/:/Addresses/);assert.doesNotMatch(html,/type="submit"|<textarea|JSON/);
});
test('Cancel closes a new draft without writing; ACTIVE requires identity but no fiscal data',async()=>{
 let closed=0;const p={...props,onClose:()=>closed++},h=partnerHarness('business-partner-workspace','en',()=>({id:'bp1'}));let tree=h.tree('BusinessPartnerEditor',p);
 find(tree,n=>n.props?.children==='Cancel').props.onClick();assert.equal(closed,1);assert.equal(h.calls.length,0);
 await form(tree).props.onSubmit({preventDefault(){}});assert.equal(h.calls.length,0);
 byId(tree,'bp-legal_name').props.onChange({target:{value:'Active without tax'}});tree=h.tree('BusinessPartnerEditor',p);await form(tree).props.onSubmit({preventDefault(){}});
 assert.equal(h.calls[0].body.values.status,'ACTIVE');assert.equal(h.calls[0].body.taxIdentifiers.length,0);
});
