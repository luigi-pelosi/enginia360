import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const props={roleId:'role1',session:{...session,permissions:['roles.read','companies.read','roles.assign_companies']},scope:(s:string)=>s+(s.includes('?')?'&':'?')+'tenantId=t',onError:(e:any)=>e.code||e.message};
const action=(t:any,s:string)=>find(t,n=>n.props?.['data-action']===s);
const company=(t:any,s:string)=>find(t,n=>n.props?.['data-company-id']===s&&typeof n.props.onCheckedChange==='function');
const event={preventDefault(){},stopPropagation(){}};
function setup(locale='en',respond?:(p:string,m:string,b:any)=>any){let ids=['c1'];const h=partnerHarness('role-company-access',locale,respond??((p,m,b)=>{if(m==='PUT'){ids=b.companyIds;return {companyIds:ids};}return p.startsWith('/roles/')?{companyIds:ids}:{items:p.includes('page=2')?[{id:'c2',name:'Two',is_enabled:true}]:[{id:'c1',name:'One',is_enabled:false}],total:2,page:p.includes('page=2')?2:1,pageSize:1};}));const render=()=>h.tree('RoleCompanyAccess',props);return {h,render};}
for(const locale of ['it','en'])test(`role company draft loads all pages, preserves inactive assignment, cancel has no writes and own save submits once (${locale})`,async()=>{
 const {h,render}=setup(locale);render();await h.flush();let tree=render();assert.ok(company(tree,'c1'),'loaded inactive assignment is shown');assert.equal(company(tree,'c1').props.checked,true);assert.ok(company(tree,'c2'));assert.equal(action(tree,'save-role-companies').props.disabled,true);
 company(tree,'c2').props.onCheckedChange(true);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);tree=render();assert.equal(action(tree,'save-role-companies').props.disabled,false);action(tree,'cancel-role-companies').props.onClick();assert.equal(company(render(),'c2').props.checked,false);
 company(render(),'c2').props.onCheckedChange(true);tree=render();const save=action(tree,'save-role-companies').props.onClick;await Promise.all([save(event),save(event)]);
 const writes=h.calls.filter(c=>c.method==='PUT');assert.equal(writes.length,1);assert.equal(writes[0].path,'/roles/role1/companies?tenantId=t');assert.deepEqual(JSON.parse(JSON.stringify(writes[0].body)),{companyIds:['c1','c2']});assert.equal(h.calls.at(-1)?.method,'GET');assert.equal(action(render(),'save-role-companies').props.disabled,true);
});
test('failed reference or assignment load blocks replacement, including programmatic save',async()=>{
 const {h,render}=setup('en',(p,m)=>{if(p.startsWith('/data/companies'))throw {code:'denied'};return {companyIds:['hidden']};});render();await h.flush();const tree=render();assert.equal(action(tree,'save-role-companies').props.disabled,true);await action(tree,'save-role-companies').props.onClick(event);assert.equal(h.calls.filter(c=>c.method==='PUT').length,0);
});
test('reads need role and company read; assignment requires its own exact action',async()=>{
 for(const permissions of [['roles.read'],['companies.read'],['roles.assign_companies']]){const h=partnerHarness('role-company-access');assert.equal(h.tree('RoleCompanyAccess',{...props,session:{...session,permissions}}),null);await h.flush();assert.equal(h.calls.length,0);}
 const {h}=setup();const readonly={...props,session:{...session,permissions:['roles.read','companies.read','roles.update']}};h.tree('RoleCompanyAccess',readonly);await h.flush();const tree=h.tree('RoleCompanyAccess',readonly);assert.equal(company(tree,'c1').props.disabled,true);assert.equal(action(tree,'save-role-companies'),undefined);
});
test('missing selected references are retained, not silently revoked; empty owner never fetches',async()=>{
 const {h,render}=setup('en',p=>p.startsWith('/roles/')?{companyIds:['hidden']}:{items:[{id:'c1',name:'One'}],total:1,page:1,pageSize:25});render();await h.flush();assert.ok(company(render(),'hidden'));assert.equal(company(render(),'hidden').props.checked,true);assert.equal(action(render(),'save-role-companies').props.disabled,true);
 const fresh=partnerHarness('role-company-access');assert.equal(fresh.tree('RoleCompanyAccess',{...props,roleId:''}),null);await fresh.flush();assert.equal(fresh.calls.length,0);
});
