import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError} from '../lib/api.ts';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const event={preventDefault(){},stopPropagation(){}};
const action=(tree:any,key:string)=>find(tree,n=>n.props?.['data-action']===key);
const field=(tree:any,key:string)=>find(tree,n=>n.props?.id===key);
const childForm=(tree:any)=>find(tree,n=>n.props?.['data-bp-related-form']);
const plain=(value:any)=>JSON.parse(JSON.stringify(value));
const base={id:'bp1',version:3,kind:'ORGANIZATION',status:'DRAFT',code:'BP-1',legal_name:'Original',first_name:'',last_name:'',tax_identifiers:[{id:'tax-id',country_code:'IT',identifier_type:'VAT',value:'12345678901'}],addresses:[{id:'address-id',label:'Office',street:'Via Uno',street_number:'1',postal_code:'00100',city:'Roma',province:'RM',country_code:'IT',additional_info:'Keep',usages:[{id:'usage-id',usage:'SHIPPING',is_default:true}]}],contact_channels:[{id:'contact-id',channel_type:'EMAIL',value:'a@example.com',purpose:'Office',is_primary:true}]};
const props={session:{...session,permissions:['business-partners.read','business-partners.create','business-partners.update']},scope:(s:string)=>s,onError:(e:any)=>e.code,id:'bp1' as string|null,onClose(){},onSaved(){throw Error('child commit must not navigate');}};
const collections={tax:'taxIdentifiers',address:'addresses',contact:'contactChannels'} as const;
for(const kind of ['tax','address','contact'] as const)test(`existing ${kind} edit persists one collection before closing, preserves identity and uses latest revision`,async()=>{
 let resolve!:(record:any)=>void;
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>method==='PUT'?new Promise(r=>{resolve=r;}):base);
 const render=()=>h.tree('BusinessPartnerEditor',props);render();await h.flush();let tree=render();
 field(tree,'bp-legal_name').props.onChange({target:{value:'Pending identity'}});tree=render();
 action(tree,`edit-${kind}-0`).props.onClick();tree=render();
 const id=`bp-${kind}-0-${kind==='address'?'label':'value'}`;
 field(tree,id).props.onChange({target:{value:kind==='contact'?'edited@example.com':'Edited'}});tree=render();
 const confirmLabel=action(tree,'apply-related').props.children;
 const submit=childForm(tree).props.onSubmit;const pending=submit(event);submit(event);
 assert.equal(h.calls.filter(c=>c.method==='PUT').length,1,'row confirmation must issue one immediate PUT');
 assert.equal(confirmLabel,'Save');
 const call=h.calls.at(-1)!;assert.equal(call.path,'/data/business-partners/bp1/save');
 assert.deepEqual(Object.keys(call.body).sort(),[collections[kind],'expectedVersion','values'].sort());
 assert.deepEqual(plain(call.body.values),{});assert.equal(call.body.expectedVersion,3);assert.doesNotMatch(JSON.stringify(call.body),/"id":/);
 tree=render();assert.ok(childForm(tree));assert.equal(action(tree,'cancel-related').props.disabled,true);
 find(tree,n=>n.props?.open&&n.props?.onOpenChange).props.onOpenChange(false);action(tree,'cancel-related').props.onClick();assert.ok(childForm(render()));
 const key=kind==='tax'?'tax_identifiers':kind==='address'?'addresses':'contact_channels';
 resolve({...base,version:4,[key]:[{...base[key][0],[kind==='address'?'label':'value']:'Authoritative@example.com'}]});await pending;
 tree=render();assert.equal(childForm(tree),undefined);assert.equal(field(tree,'bp-legal_name').props.value,'Pending identity');
 const saving=find(tree,n=>n.type==='form').props.onSubmit(event);assert.equal(h.calls.at(-1)!.body.expectedVersion,4);assert.equal(h.calls.at(-1)!.body.values.legal_name,'Pending identity');
 assert.equal(h.calls.at(-1)!.body[collections[kind]][0][kind==='address'?'label':'value'],'Authoritative@example.com');resolve({...base,version:5});await saving;
});
for(const kind of ['tax','address','contact'] as const)test(`existing ${kind} removal persists immediately and main Save cannot resurrect it`,async()=>{
 let record:any=plain(base),saved=0;const p={...props,onSaved(){saved++;}};
 const h=partnerHarness('business-partner-workspace','en',(_path,method,body)=>{if(method==='PUT'){record={...record,version:record.version+1};for(const [api,key] of [['taxIdentifiers','tax_identifiers'],['addresses','addresses'],['contactChannels','contact_channels']])if(api in body)record[key]=body[api];}return record;});
 const render=()=>h.tree('BusinessPartnerEditor',p);render();await h.flush();let tree=render();field(tree,'bp-legal_name').props.onChange({target:{value:'Pending'}});tree=render();
 action(tree,`remove-${kind}-0`).props.onClick();tree=render();await action(tree,'confirm-remove-related').props.onClick(event);tree=render();
 const call=h.calls.find(c=>c.method==='PUT');assert.ok(call,'removal confirmation must issue PUT');assert.deepEqual(plain(call.body),{values:{},[collections[kind]]:[],expectedVersion:3});
 assert.equal(saved,0);assert.equal(action(tree,`details-${kind}-0`),undefined);assert.equal(field(tree,'bp-legal_name').props.value,'Pending');
 await find(tree,n=>n.type==='form').props.onSubmit(event);assert.equal(h.calls.at(-2)!.body.expectedVersion,4);assert.deepEqual(plain(h.calls.at(-2)!.body[collections[kind]]),[]);assert.equal(saved,1);
});
for(const mode of ['edit','add'] as const)for(const code of ['invalid_italian_vat','stale_version'])test(`${mode} failure ${code} preserves exact failed row without retry`,async()=>{
 const failure=new ApiError(code,code==='stale_version'?409:400,`taxIdentifiers[${mode==='add'?1:0}].value`);
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>{if(method==='PUT')throw failure;return base;});const render=()=>h.tree('BusinessPartnerEditor',props);render();await h.flush();let tree=render();
 action(tree,mode==='add'?'add-tax':'edit-tax-0').props.onClick();tree=render();const id=`bp-tax-${mode==='add'?1:0}-value`;field(tree,id).props.onChange({target:{value:'Rejected draft'}});tree=render();await childForm(tree).props.onSubmit(event);tree=render();
 assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);assert.equal(field(tree,id)?.props.value,'Rejected draft');assert.equal(field(tree,id)?.props['aria-invalid'],true);assert.equal(field(tree,id)?.props['aria-describedby'],`${id}-error`);assert.equal(action(tree,'cancel-related').props.disabled,false);
});
test('new rows remain staged; Cancel, X/Escape and removal cancellation never write',async()=>{
 for(const id of [null,'bp1']) {
 const p={...props,id},h=partnerHarness('business-partner-workspace','en',()=>base);const render=()=>h.tree('BusinessPartnerEditor',p);render();await h.flush();let tree=render();
 for(const dismiss of ['cancel','dialog']){action(tree,'add-tax').props.onClick();tree=render();field(tree,`bp-tax-${id?1:0}-value`).props.onChange({target:{value:'Discard'}});tree=render();if(dismiss==='cancel')action(tree,'cancel-related').props.onClick();else find(tree,n=>n.props?.open&&n.props?.onOpenChange).props.onOpenChange(false);tree=render();}
 if(!id){action(tree,'add-tax').props.onClick();tree=render();assert.equal(action(tree,'apply-related').props.children,'Apply');field(tree,'bp-tax-0-value').props.onChange({target:{value:'12345678901'}});tree=render();await childForm(tree).props.onSubmit(event);tree=render();}
 action(tree,'remove-tax-0').props.onClick();tree=render();action(tree,'cancel-remove-related').props.onClick();assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
 }
});
for(const kind of ['tax','address','contact'] as const)test(`existing ${kind} addition immediately saves only that collection with exclusive defaults/primary`,async()=>{
 let record:any=plain(base);
 const h=partnerHarness('business-partner-workspace','en',(_path,method,body)=>{if(method==='PUT'){record={...record,version:record.version+1};for(const [api,key] of [['taxIdentifiers','tax_identifiers'],['addresses','addresses'],['contactChannels','contact_channels']])if(api in body)record[key]=body[api];}return record;});
 const render=()=>h.tree('BusinessPartnerEditor',props);render();await h.flush();let tree=render();
 find(tree,n=>n.props?.value==='ORGANIZATION'&&n.props?.onValueChange).props.onValueChange('PERSON');tree=render();
 field(tree,'bp-first_name').props.onChange({target:{value:'Pending first'}});field(tree,'bp-last_name').props.onChange({target:{value:'Pending last'}});tree=render();
 find(tree,n=>n.props?.value==='DRAFT'&&n.props?.onValueChange).props.onValueChange('ACTIVE');tree=render();
 action(tree,`add-${kind}`).props.onClick();tree=render();
 if(kind==='address'){field(tree,'bp-address-1-label').props.onChange({target:{value:'New office'}});tree=render();field(tree,'bp-address-1-SHIPPING').props.onCheckedChange(true);tree=render();field(tree,'bp-address-1-SHIPPING-default').props.onCheckedChange(true);}
 else {field(tree,`bp-${kind}-1-value`).props.onChange({target:{value:kind==='tax'?'12345678902':'new@example.com'}});if(kind==='contact'){tree=render();field(tree,'bp-contact-1-primary').props.onCheckedChange(true);}}
 tree=render();await childForm(tree).props.onSubmit(event);tree=render();
 const mutations=h.calls.filter(c=>c.method==='PUT');assert.equal(mutations.length,1);const body=mutations[0].body;
 assert.deepEqual(Object.keys(body).sort(),['values','expectedVersion',collections[kind]].sort());assert.deepEqual(plain(body.values),{});assert.equal(body[collections[kind]].length,2);
 if(kind==='address')assert.deepEqual(plain(body.addresses.map((r:any)=>r.usages[0].is_default)),[false,true]);
 if(kind==='contact')assert.deepEqual(plain(body.contactChannels.map((r:any)=>r.is_primary)),[false,true]);
 assert.equal(field(tree,'bp-first_name').props.value,'Pending first');assert.equal(field(tree,'bp-last_name').props.value,'Pending last');assert.ok(find(tree,n=>n.props?.value==='ACTIVE'));assert.ok(action(tree,`details-${kind}-1`));
});
test('failed removal stays open, guards synchronous duplicates and dismissals, and retains identity and children',async()=>{
 let reject!:(error:any)=>void;
 const h=partnerHarness('business-partner-workspace','en',(_path,method)=>method==='PUT'?new Promise((_r,j)=>{reject=j;}):base);
 const render=()=>h.tree('BusinessPartnerEditor',props);render();await h.flush();let tree=render();field(tree,'bp-legal_name').props.onChange({target:{value:'Pending'}});tree=render();
 action(tree,'remove-contact-0').props.onClick();tree=render();const submit=action(tree,'confirm-remove-related').props.onClick;
 let prevented=0;const pending=submit({preventDefault(){prevented++;}});submit(event);assert.equal(prevented,1);assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);
 tree=render();assert.equal(action(tree,'confirm-remove-related').props.disabled,true);assert.equal(action(tree,'cancel-remove-related').props.disabled,true);assert.ok(action(tree,'details-contact-0'));
 find(tree,n=>n.props?.open&&n.props?.onOpenChange).props.onOpenChange(false);action(tree,'cancel-remove-related').props.onClick();assert.ok(action(render(),'confirm-remove-related'));
 reject(new ApiError('stale_version',409));await pending;tree=render();assert.ok(action(tree,'confirm-remove-related'));assert.ok(action(tree,'details-contact-0'));assert.equal(field(tree,'bp-legal_name').props.value,'Pending');assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);
 action(tree,'cancel-remove-related').props.onClick();tree=render();assert.equal(action(tree,'confirm-remove-related'),undefined);assert.ok(action(tree,'details-contact-0'));
});
