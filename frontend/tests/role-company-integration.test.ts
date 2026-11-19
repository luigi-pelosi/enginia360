import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './record-editor-harness.ts';
const p={resource:{key:'roles',fields:[{name:'name',type:'text',required:true}]},row:{id:'role1',name:'Role'},canWrite:false,session:{...session,permissions:['roles.read','companies.read','roles.assign_companies']},tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:(e:any)=>e.code};
test('persisted role has independent authorized company editor while profile readonly; new roles have no fake owner',()=>{
 const h=partnerHarness('workspace');const tree=h.tree('RecordEditor',p);const panel=find(tree,n=>n.type?.name==='RoleCompanyAccess');assert.ok(panel);assert.equal(panel.props.roleId,'role1');assert.equal(panel.props.onSaved,undefined);
 assert.equal(find(h.tree('RecordEditor',{...p,row:null}),n=>n.type?.name==='RoleCompanyAccess'),undefined);
});
