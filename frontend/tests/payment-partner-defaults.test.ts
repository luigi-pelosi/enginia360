import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError} from '../lib/api.ts';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const props={businessPartnerId:'bp1',session:{...session,permissions:['payment-partner-defaults.read','payment-partner-defaults.update']},scope:(p:string)=>p,onError:(e:any)=>e.message,selectedCompanyId:'c1',onClose:()=>{},companies:[{id:'c1',permissions:['payment-partner-defaults.read','payment-partner-defaults.update','payment-methods.read','payment-terms.read']}]};
test('loads and saves role defaults using company-specific grants and version',async()=>{
 const h=partnerHarness('payment-partner-defaults','en',(path,method)=>{
  if(path==='/payment-companies') return {items:[{id:'c1',name:'One',permissions:['payment-partner-defaults.read','payment-partner-defaults.update','payment-methods.read','payment-terms.read']}]};
  if(path.includes('/payment-methods')||path.includes('/payment-terms')) return {items:[]};
  if(path.includes('/payment-defaults/')) return {paymentTermId:null,paymentMethodId:null,version:4};
  throw Error(path);
 });
 const p={...props,relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER','SUPPLIER']} ]};
 h.tree('PaymentPartnerDefaults',p);await h.flush();let tree=h.tree('PaymentPartnerDefaults',p);await h.flush();tree=h.tree('PaymentPartnerDefaults',p);await h.flush();tree=h.tree('PaymentPartnerDefaults',p);
 tree=h.tree('PaymentPartnerDefaults',p);await h.flush();tree=h.tree('PaymentPartnerDefaults',p);
 assert.ok(h.calls.some(x=>x.path==='/companies/c1/business-partners/bp1/payment-defaults/CUSTOMER'));
 const form=find(tree,n=>n.props?.['data-payment-defaults-form']==='CUSTOMER');assert.ok(form);assert.equal(form.type,'div','payment defaults must not nest a form inside the partner form');
 const save=find(form,n=>n.type && n.props?.type==='button' && typeof n.props?.onClick==='function');assert.ok(save);let stopped=false;save.props.onClick({stopPropagation(){stopped=true;}});await h.flush();assert.equal(stopped,true);
 const call=h.calls.find(x=>x.method==='PUT');assert.equal(call?.path,'/companies/c1/business-partners/bp1/payment-defaults/CUSTOMER');assert.deepEqual(JSON.parse(JSON.stringify(call?.body)),{paymentTermId:null,paymentMethodId:null,expectedVersion:4});
});
test('does not fetch defaults for a company without its own read grant',async()=>{
 const h=partnerHarness('payment-partner-defaults','en',()=>({items:[{id:'other',permissions:['payment-partner-defaults.read']}]}));
 const p={...props,companies:[{id:'other',permissions:['payment-partner-defaults.read']}],relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER']}]};
 h.tree('PaymentPartnerDefaults',p);await h.flush();h.tree('PaymentPartnerDefaults',p);await h.flush();h.tree('PaymentPartnerDefaults',p);await h.flush();
 assert.equal(h.calls.some(x=>x.path.includes('/payment-defaults/')),false);
});
test('role switch fetches supplier independently and submits the supplier version',async()=>{
 const h=partnerHarness('payment-partner-defaults','en',(path,method)=>{
  if(path==='/payment-companies')return {items:[{id:'c1',permissions:['payment-partner-defaults.read','payment-partner-defaults.update','payment-methods.read','payment-terms.read']}]};
  if(path.includes('/payment-defaults/'))return {paymentTermId:null,paymentMethodId:null,version:path.endsWith('SUPPLIER')?9:4};
  return {items:[]};
 });
 const p={...props,relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER','SUPPLIER']}]};
 h.tree('PaymentPartnerDefaults',p);await h.flush();h.tree('PaymentPartnerDefaults',p);await h.flush();h.tree('PaymentPartnerDefaults',p);await h.flush();let tree=h.tree('PaymentPartnerDefaults',p);
 tree=h.tree('PaymentPartnerDefaults',p);await h.flush();tree=h.tree('PaymentPartnerDefaults',p);
 const select=find(tree,n=>n.props?.onValueChange && n.props?.children?.some?.((x:any)=>x?.props?.id==='defaults-role'));assert.ok(select);select.props.onValueChange('SUPPLIER');
 h.tree('PaymentPartnerDefaults',p);await h.flush();tree=h.tree('PaymentPartnerDefaults',p);const form=find(tree,n=>n.props?.['data-payment-defaults-form']==='SUPPLIER');assert.ok(form);const save=find(form,n=>n.props?.type==='button' && typeof n.props?.onClick==='function');assert.ok(save);save.props.onClick({stopPropagation(){}});await h.flush();
 const put=h.calls.find(x=>x.method==='PUT');assert.equal(put?.path,'/companies/c1/business-partners/bp1/payment-defaults/SUPPLIER');assert.equal(put?.body.expectedVersion,9);
});
test('defaults editor opens on demand and cancellation never writes',async()=>{
 const h=partnerHarness('payment-partner-defaults','en',path=>path.includes('/payment-defaults/')?{paymentTermId:null,paymentMethodId:null,version:1}:{items:[]});
 let selected:string|null=null;const render=()=>h.tree('PaymentPartnerDefaults',{...props,selectedCompanyId:selected,onClose:()=>{selected=null;},relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER']}]});
 assert.equal(render(),null);selected='c1';render();await h.flush();let tree=render();await h.flush();tree=render();assert.ok(find(tree,n=>n.props?.['data-payment-defaults-form']));
 find(tree,n=>n.props?.['data-action']==='cancel-payment-defaults').props.onClick();assert.equal(render(),null);assert.equal(h.calls.some(c=>c.method==='PUT'),false);
});

test('summary renders active roles and their own readable terms',async()=>{
 const h=partnerHarness('payment-partner-defaults','en',path=>path.endsWith('/payment-terms')?{items:[{id:'t1',code:'N30',name:'Net 30'}]}:{paymentTermId:path.endsWith('CUSTOMER')?'t1':null,paymentMethodId:null,version:1});
 const p={...props,relation:{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER','SUPPLIER']},permissions:['payment-partner-defaults.read','payment-terms.read','payment-methods.read'],revision:0};
 let tree;for(let i=0;i<3;i++){tree=h.tree('PaymentDefaultsSummary',p);await h.flush();}tree=h.tree('PaymentDefaultsSummary',p);const text=JSON.stringify(tree);assert.match(text,/Net 30/);assert.match(text,/Customer/);assert.match(text,/Supplier/);assert.equal(h.calls.filter(c=>c.path.includes('payment-defaults/')).length,2);
});
test('summary does not fetch when company payment permissions are missing',async()=>{const h=partnerHarness('payment-partner-defaults');const p={...props,relation:{company_id:'c1',usable_roles:['CUSTOMER']},permissions:['payment-partner-defaults.read'],revision:0};h.tree('PaymentDefaultsSummary',p);await h.flush();assert.equal(h.calls.length,0);});
test('uncertain save locks company and role changes until refresh',async()=>{
 const h=partnerHarness('payment-partner-defaults','en',(path,method)=>{if(method==='PUT')throw new ApiError('network_error',0);if(path==='/payment-companies')return {items:[{id:'c1',permissions:['payment-partner-defaults.read','payment-partner-defaults.update','payment-methods.read','payment-terms.read']}]};if(path.includes('/payment-defaults/'))return {paymentTermId:null,paymentMethodId:null,version:1};return {items:[]};});
 const p={...props,relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER','SUPPLIER']}]};let tree;for(let i=0;i<4;i++){tree=h.tree('PaymentPartnerDefaults',p);await h.flush();}tree=h.tree('PaymentPartnerDefaults',p);await h.flush();tree=h.tree('PaymentPartnerDefaults',p);find(tree,n=>n.props?.['data-payment-defaults-form']).props.children[1].props.onClick({stopPropagation(){}});await h.flush();tree=h.tree('PaymentPartnerDefaults',p);const role=find(tree,n=>n.props?.onValueChange&&n.props?.children?.some?.((x:any)=>x?.props?.id==='defaults-role'));assert.equal(role.props.disabled,true);
});

test('summary avoids terms endpoint without methods read permission',async()=>{const h=partnerHarness('payment-partner-defaults');const p={...props,relation:{company_id:'c1',usable_roles:['CUSTOMER']},permissions:['payment-partner-defaults.read','payment-terms.read'],revision:0};h.tree('PaymentDefaultsSummary',p);await h.flush();assert.equal(h.calls.length,0);});
test('cannot save while catalog requests are pending',async()=>{
 let release!:()=>void;const pending=new Promise<any>(r=>{release=()=>r({items:[]});});
 const h=partnerHarness('payment-partner-defaults','en',path=>path==='/payment-companies'?{items:[{id:'c1',permissions:['payment-partner-defaults.read','payment-partner-defaults.update','payment-methods.read','payment-terms.read']}]}:path.includes('/payment-defaults/')?{paymentTermId:null,paymentMethodId:null,version:1}:pending);
 const p={...props,relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER']}]};let tree;for(let i=0;i<4;i++){tree=h.tree('PaymentPartnerDefaults',p);await h.flush();}tree=h.tree('PaymentPartnerDefaults',p);await h.flush();tree=h.tree('PaymentPartnerDefaults',p);
 const form=find(tree,n=>n.props?.['data-payment-defaults-form']);assert.equal(Boolean(form && !form.props.children[1].props.disabled),false);release();await h.flush();
});
test('uncertain default save invalidates summary and refresh invalidates it again',async()=>{
 let invalidations=0;const h=partnerHarness('payment-partner-defaults','en',(path,method)=>{if(method==='PUT')throw new ApiError('network_error',0);if(path==='/payment-companies')return {items:[{id:'c1',permissions:['payment-partner-defaults.read','payment-partner-defaults.update','payment-methods.read','payment-terms.read']}]};if(path.includes('/payment-defaults/'))return {paymentTermId:null,paymentMethodId:null,version:1};return {items:[]};});
 const p={...props,onSaved:()=>invalidations++,relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER']}]};let tree;for(let i=0;i<4;i++){tree=h.tree('PaymentPartnerDefaults',p);await h.flush();}tree=h.tree('PaymentPartnerDefaults',p);await h.flush();tree=h.tree('PaymentPartnerDefaults',p);find(tree,n=>n.props?.['data-payment-defaults-form']).props.children[1].props.onClick({stopPropagation(){}});await h.flush();tree=h.tree('PaymentPartnerDefaults',p);assert.equal(invalidations,1);const refresh=find(tree,n=>n.type&&n.props?.children==='Refresh');refresh.props.onClick();assert.equal(invalidations,2);
});
test('second company saves only its own supplier defaults',async()=>{
 const h=partnerHarness('payment-partner-defaults','en',(path,method)=>path.includes('/payment-defaults/')?{paymentTermId:null,paymentMethodId:null,version:method==='PUT'?8:7}:{items:[]});
 const p={...props,selectedCompanyId:'c2',companies:[{id:'c2',permissions:['payment-partner-defaults.read','payment-partner-defaults.update','payment-methods.read','payment-terms.read']}],relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER']},{company_id:'c2',company_name:'Two',usable_roles:['SUPPLIER']}]};let tree;for(let i=0;i<5;i++){tree=h.tree('PaymentPartnerDefaults',p);await h.flush();}tree=h.tree('PaymentPartnerDefaults',p);const form=find(tree,n=>n.props?.['data-payment-defaults-form']==='SUPPLIER');assert.ok(form);find(form,n=>n.props?.type==='button'&&n.props?.onClick).props.onClick({stopPropagation(){}});await h.flush();const writes=h.calls.filter(c=>c.method==='PUT');assert.equal(writes.length,1);assert.equal(writes[0].path,'/companies/c2/business-partners/bp1/payment-defaults/SUPPLIER');assert.equal(writes[0].body.expectedVersion,7);
});
test('read-only company has details but no save action',async()=>{
 const h=partnerHarness('payment-partner-defaults','en',p=>p.includes('/payment-defaults/')?{paymentTermId:null,paymentMethodId:null,version:1}:{items:[]});const p={...props,companies:[{id:'c1',permissions:['payment-partner-defaults.read','payment-methods.read','payment-terms.read']}],relations:[{company_id:'c1',company_name:'One',usable_roles:['CUSTOMER']}]};let tree;for(let i=0;i<4;i++){tree=h.tree('PaymentPartnerDefaults',p);await h.flush();}tree=h.tree('PaymentPartnerDefaults',p);const form=find(tree,n=>n.props?.['data-payment-defaults-form']);assert.ok(form);assert.equal(find(form,n=>n.props?.children==='Save'),undefined);assert.equal(h.calls.some(c=>c.method==='PUT'),false);
});
