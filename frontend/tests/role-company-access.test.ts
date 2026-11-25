import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const company=(t:any,s:string)=>find(t,n=>n.props?.['data-company-id']===s&&typeof n.props.onCheckedChange==='function');
for(const locale of ['it','en'])test(`controlled companies chooser reads all pages, preserves hidden/inactive, never writes or renders own actions (${locale})`,async()=>{
 const h=partnerHarness('role-company-access',locale,p=>({items:p.includes('page=2')?[{id:'c2',name:'Two'}]:[{id:'c1',name:'One',is_enabled:false}],total:2,page:p.includes('page=2')?2:1,pageSize:1}));let ids=['c1','hidden'];let ready=false;
 const props={session:{...session,permissions:['roles.read','companies.read','roles.assign_companies']},roleId:'role1',scope:(p:string)=>p,onError:()=>'',ids,ready:true,error:'',editable:true,busy:false,onIdsChange:(next:string[])=>{ids=next;},onLookupState:(r:boolean)=>{ready=r;}};
 const render=()=>h.tree('RoleCompanyAccess',{...props,ids});render();await h.flush();let tree=render();assert.equal(ready,true);assert.equal(company(tree,'c1').props.checked,true);assert.equal(company(tree,'hidden').props.checked,true);assert.ok(company(tree,'c2'));
 assert.equal(find(tree,n=>n.props?.['data-action']==='save-role-companies'),undefined);assert.equal(find(tree,n=>n.props?.['data-action']==='cancel-role-companies'),undefined);assert.equal(find(tree,n=>n.props?.role==='status'),undefined);
 company(tree,'c2').props.onCheckedChange(true);assert.deepEqual([...ids],['c1','c2','hidden']);assert.equal(h.calls.length,2);assert.ok(h.calls.every(c=>c.method==='GET'&&c.path.startsWith('/data/companies')));
 tree=render();find(tree,n=>n.props?.['aria-label']?.startsWith(locale==='it'?'Cerca':'Search')).props.onChange({target:{value:'Two'}});assert.equal(company(render(),'hidden'),undefined);assert.equal(ids.includes('hidden'),true);
});
test('chooser reports lookup failure, keeps selected fallback visible and disables toggles',async()=>{
 const h=partnerHarness('role-company-access','en',()=>{throw new Error('failed');});let status:any;let changed=false;const props={session:{...session,permissions:['roles.read','companies.read','roles.assign_companies']},roleId:'',scope:(p:string)=>p,onError:()=>'',ids:['hidden'],ready:true,error:'',editable:true,busy:false,onIdsChange:()=>{changed=true;},onLookupState:(...args:any[])=>{status=args;}};
 h.tree('RoleCompanyAccess',props);await h.flush();const tree=h.tree('RoleCompanyAccess',props);assert.equal(status[0],false);assert.equal(company(tree,'hidden').props.disabled,true);company(tree,'hidden').props.onCheckedChange(false);assert.equal(changed,false);assert.equal(h.calls.some(c=>c.path.startsWith('/roles/')),false);
});
test('all company checkboxes honor parent edit, readiness, error and busy gates',async()=>{
 for(const gate of [{editable:false},{ready:false},{error:'assignment failed'},{busy:true}]){
  let changed=false;const h=partnerHarness('role-company-access','en',()=>({items:[{id:'c1',name:'One'}],total:1,page:1,pageSize:100}));const props={roleId:'role1',scope:(p:string)=>p,onError:()=>'',ids:['hidden'],ready:true,error:'',editable:true,busy:false,onIdsChange:()=>{changed=true;},onLookupState:()=>{},...gate};h.tree('RoleCompanyAccess',props);await h.flush();const tree=h.tree('RoleCompanyAccess',props);
  for(const id of ['c1','hidden']){assert.equal(company(tree,id).props.disabled,true);company(tree,id).props.onCheckedChange(true);}assert.equal(changed,false);
 }
});
