import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError} from '../lib/api.ts';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const props={businessPartnerId:'bp1',session:{...session,permissions:['business-partners.read','business-partner-companies.read','business-partner-companies.update','business-partner-companies.create']},scope:(p:string)=>p+'?tenantId=t',onError:(e:any)=>e.code||e.message};
const options=[{id:'c1',name:'One',is_enabled:true,permissions:['read','update']},{id:'c2',name:'Two',is_enabled:true,permissions:['read','create']},{id:'c3',name:'Three',is_enabled:true,permissions:['read']}];
const relation={id:'rel',company_id:'c1',business_partner_id:'bp1',company_name:'One',status:'ACTIVE',version:7,roles:[{id:'r1',role_code:'CUSTOMER',status:'ACTIVE'}],usable_roles:[]};
const action=(tree:any,s:string)=>find(tree,n=>n.props?.['data-action']===s||n.props?.['data-company-action']===s);
const field=(tree:any,s:string)=>s==='bp-company-choice'?find(tree,n=>typeof n.props?.onValueChange==='function'&&find(n,c=>c.props?.id==='bp-company-id')):find(tree,n=>n.props?.id===s.replace('bp-company-role-','bp-company-'));
const event={preventDefault(){},stopPropagation(){}};
async function ready(locale='en',companies=options,rows=[relation],mutate?:any){const h=partnerHarness('business-partner-companies',locale,(p,m,b)=>m==='GET'?(p.startsWith('/business-partner-companies/options')?{items:companies}:{items:rows}):mutate?mutate(p,m,b):{...relation,version:8});const render=()=>h.tree('BusinessPartnerCompanies',props);render();await h.flush();return {h,render};}
for(const locale of ['it','en'])test(`association is explicitly confirmed once with chosen company and roles (${locale})`,async()=>{
 const {h,render}=await ready(locale);let tree=render();assert.ok(action(tree,'associate-company'),'authorized association action is available');action(tree,'associate-company').props.onClick();tree=render();field(tree,'bp-company-choice').props.onValueChange('c2');tree=render();field(tree,'bp-company-role-CUSTOMER').props.onCheckedChange(true);tree=render();
 assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
 const submit=find(tree,n=>n.props?.['data-company-association-form']).props.onSubmit;await Promise.all([submit(event),submit(event)]);
 const writes=h.calls.filter(c=>c.method!=='GET');assert.equal(writes.length,1);assert.equal(writes[0].method,'POST');assert.equal(writes[0].path,'/companies/c2/business-partners?tenantId=t');assert.deepEqual(JSON.parse(JSON.stringify(writes[0].body)),{businessPartnerId:'bp1',roles:['CUSTOMER']});
 assert.equal(action(render(),'confirm-company-association'),undefined);assert.equal(h.calls.at(-1)?.method,'GET');
});
test('association cancellation and rejected company choice perform no writes; zero-role relation accepted',async()=>{
 const {h,render}=await ready();action(render(),'associate-company').props.onClick();let tree=render();field(tree,'bp-company-choice').props.onValueChange('c3');tree=render();await find(tree,n=>n.props?.['data-company-association-form']).props.onSubmit(event);assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);
 action(render(),'cancel-company-association').props.onClick();assert.equal(action(render(),'confirm-company-association'),undefined);
 action(render(),'associate-company').props.onClick();field(render(),'bp-company-choice').props.onValueChange('c2');await find(render(),n=>n.props?.['data-company-association-form']).props.onSubmit(event);assert.deepEqual(JSON.parse(JSON.stringify(h.calls.find(c=>c.method==='POST')!.body.roles)),[]);
});
test('assigned role cannot be unchecked; separate confirmed block and activate use exact relation version',async()=>{
 const {h,render}=await ready();action(render(),'manage-company-c1').props.onClick();let tree=render();assert.equal(field(tree,'bp-existing-c1-CUSTOMER').props.checked,true);assert.equal(field(tree,'bp-existing-c1-CUSTOMER').props.disabled,true);
 action(tree,'role-c1-CUSTOMER').props.onClick();assert.equal(h.calls.filter(c=>c.method!=='GET').length,0);await action(render(),'confirm-company-operation').props.onClick(event);
 let write=h.calls.find(c=>c.method==='PUT')!;assert.equal(write.path,'/companies/c1/business-partners/bp1/roles/CUSTOMER?tenantId=t');assert.deepEqual(JSON.parse(JSON.stringify(write.body)),{status:'BLOCKED',expectedVersion:7});
 action(render(),'relationship-c1').props.onClick();await action(render(),'confirm-company-operation').props.onClick(event);write=h.calls.find(c=>c.method==='PATCH')!;assert.deepEqual(JSON.parse(JSON.stringify(write.body)),{status:'BLOCKED',expectedVersion:7});
});
test('unassigned role PUT is explicit, no deletion; exact per-company authority overrides permission union',async()=>{
 const {h,render}=await ready();action(render(),'manage-company-c1').props.onClick();action(render(),'assign-c1-SUPPLIER').props.onClick();await action(render(),'confirm-company-operation').props.onClick(event);assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);assert.match(h.calls.find(c=>c.method==='PUT')!.path,/roles\/SUPPLIER/);
 const readonly=await ready('en',options.map(o=>({...o,permissions:['read']})));assert.equal(action(readonly.render(),'associate-company'),undefined);assert.equal(action(readonly.render(),'manage-company-c1'),undefined);
 assert.equal(readonly.h.calls.filter(c=>c.method!=='GET').length,0);
});
test('failed mutation keeps confirmation and stale version; retry requires fresh authoritative relation',async()=>{
 const {h,render}=await ready('en',options,[relation],()=>{throw new ApiError('stale_version',409);});action(render(),'manage-company-c1').props.onClick();action(render(),'role-c1-CUSTOMER').props.onClick();await action(render(),'confirm-company-operation').props.onClick(event);assert.ok(action(render(),'confirm-company-operation'));assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);assert.equal(action(render(),'confirm-company-operation').props.disabled,true);await action(render(),'confirm-company-operation').props.onClick(event);assert.equal(h.calls.filter(c=>c.method==='PUT').length,1);
});
test('authoritative readback advances only relation revision and usable roles; subsequent role uses returned revision',async()=>{
 let current=JSON.parse(JSON.stringify(relation));const h=partnerHarness('business-partner-companies','en',(p,m,b)=>{if(m==='GET')return p.startsWith('/business-partner-companies')?{items:options}:{items:[current]};current={...current,version:current.version+1,roles:current.roles.map((r:any)=>({...r,status:b.status}))};return current;});const render=()=>h.tree('BusinessPartnerCompanies',props);render();await h.flush();action(render(),'manage-company-c1').props.onClick();action(render(),'role-c1-CUSTOMER').props.onClick();await action(render(),'confirm-company-operation').props.onClick(event);action(render(),'role-c1-CUSTOMER').props.onClick();await action(render(),'confirm-company-operation').props.onClick(event);assert.deepEqual(h.calls.filter(c=>c.method==='PUT').map(c=>JSON.parse(JSON.stringify(c.body))),[{status:'BLOCKED',expectedVersion:7},{status:'ACTIVE',expectedVersion:8}]);assert.equal(h.calls.some(c=>c.path.includes('/save')),false);
});
test('accepted relation write with failed verification cannot be repeated from stale confirmation',async()=>{
 let committed=false;const h=partnerHarness('business-partner-companies','en',(p,m)=>{if(m!=='GET'){committed=true;return {...relation,version:8};}if(p.startsWith('/business-partner-companies'))return {items:options};if(committed)throw new ApiError('network_error',0);return {items:[relation]};});const render=()=>h.tree('BusinessPartnerCompanies',props);render();await h.flush();action(render(),'relationship-c1').props.onClick();await action(render(),'confirm-company-operation').props.onClick(event);assert.equal(action(render(),'confirm-company-operation'),undefined);assert.equal(action(render(),'relationship-c1').props.disabled,true);assert.equal(h.calls.filter(c=>c.method==='PATCH').length,1);
});
test('read gates refuse all API requests and failed options cannot expose mutation controls',async()=>{
 for(const permissions of [['business-partners.read'],['business-partner-companies.read'],[]]){const h=partnerHarness('business-partner-companies');assert.equal(h.tree('BusinessPartnerCompanies',{...props,session:{...session,permissions}}),null);await h.flush();assert.equal(h.calls.length,0);}
 const h=partnerHarness('business-partner-companies','en',()=>{throw new ApiError('forbidden',403);});h.tree('BusinessPartnerCompanies',props);await h.flush();assert.equal(action(h.tree('BusinessPartnerCompanies',props),'associate-company'),undefined);
});
