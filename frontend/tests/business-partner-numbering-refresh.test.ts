import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness, find, session} from './business-partner-harness.ts';
const storage=()=>{const m=new Map<string,string>();return {getItem:(k:string)=>m.get(k)??null,setItem:(k:string,v:string)=>m.set(k,v),removeItem:(k:string)=>m.delete(k),key:(i:number)=>[...m.keys()][i]??null,clear:()=>m.clear(),get length(){return m.size;}} as Storage;};
const initial={mode:'AUTO',prefix:'BP-',padding:6,nextNumber:1,version:3};
const props={session:{...session,tenantId:'tenant',permissions:['business-partner-numbering.read','business-partner-numbering.update']},scope:(p:string)=>p,onError:()=> 'error'};
const field=(tree:any)=>find(tree,n=>n.props?.id==='bp-numbering-prefix');
test('refresh restores draft only after authoritative read and submits its original version',async()=>{
 const s=storage();const h=partnerHarness('business-partner-numbering','en',()=>initial,s);
 h.tree('BusinessPartnerNumbering',props);await h.flush();let tree=h.tree('BusinessPartnerNumbering',props);field(tree).props.onChange({target:{value:'EDIT-'}});
 const fresh=partnerHarness('business-partner-numbering','en',()=>({...initial,version:4}),s);fresh.tree('BusinessPartnerNumbering',props);await fresh.flush();tree=fresh.tree('BusinessPartnerNumbering',props);
 assert.equal(field(tree).props.value,'EDIT-');await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 assert.equal(fresh.calls.find(c=>c.method==='PUT')?.body.version,3);
});
test('recovery isolates users and tenants and requires explicit superadmin tenant',async()=>{
 const s=storage();const h=partnerHarness('business-partner-numbering','en',()=>initial,s);
 h.tree('BusinessPartnerNumbering',props);await h.flush();field(h.tree('BusinessPartnerNumbering',props)).props.onChange({target:{value:'PRIVATE-'}});
 for(const p of [{...props,session:{...props.session,id:'other'}},{...props,session:{...props.session,tenantId:'other'}},{...props,session:{...props.session,isSuperAdmin:true,selectedTenantId:'tenant'}}]){
  const other=partnerHarness('business-partner-numbering','en',()=>initial,s);other.tree('BusinessPartnerNumbering',p);await other.flush();assert.equal(field(other.tree('BusinessPartnerNumbering',p)).props.value,'BP-');
 }
 const admin={...props,session:{...props.session,isSuperAdmin:true},tenantId:'tenant'};const same=partnerHarness('business-partner-numbering','en',()=>initial,s);same.tree('BusinessPartnerNumbering',admin);await same.flush();assert.equal(field(same.tree('BusinessPartnerNumbering',admin)).props.value,'PRIVATE-');
});
test('cancel and confirmed save discard recovery, and logout cleanup covers numbering',async()=>{
 const s=storage();const h=partnerHarness('business-partner-numbering','en',(_p,method,body)=>method==='PUT'?{...body,version:4}:initial,s);
 h.tree('BusinessPartnerNumbering',props);await h.flush();let tree=h.tree('BusinessPartnerNumbering',props);field(tree).props.onChange({target:{value:'EDIT-'}});assert.equal(s.length,1);
 tree=h.tree('BusinessPartnerNumbering',props);find(tree,n=>n.props?.children==='Cancel').props.onClick();assert.equal(s.length,0);
 tree=h.tree('BusinessPartnerNumbering',props);field(tree).props.onChange({target:{value:'SAVE-'}});tree=h.tree('BusinessPartnerNumbering',props);await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});assert.equal(s.length,0);
 tree=h.tree('BusinessPartnerNumbering',props);field(tree).props.onChange({target:{value:'LOGOUT-'}});assert.equal(s.length,1);
 const cleanup=partnerHarness('business-partner-workspace','en',()=>({}),s);cleanup.components.clearBusinessPartnerRecoveries(props.session);assert.equal(s.length,0);
});
test('failed authoritative read never exposes recovery',async()=>{
 const s=storage(),h=partnerHarness('business-partner-numbering','en',()=>initial,s);h.tree('BusinessPartnerNumbering',props);await h.flush();field(h.tree('BusinessPartnerNumbering',props)).props.onChange({target:{value:'EDIT-'}});
 const failing=partnerHarness('business-partner-numbering','en',()=>{throw Error('failed');},s);failing.tree('BusinessPartnerNumbering',props);await failing.flush();assert.equal(find(failing.tree('BusinessPartnerNumbering',props),n=>n.type==='form'),undefined);assert.equal(s.length,1);
});
test('menu reset discards numbering recovery for the selected tenant',async()=>{
 const s=storage(),h=partnerHarness('business-partner-numbering','en',()=>initial,s);h.tree('BusinessPartnerNumbering',props);await h.flush();field(h.tree('BusinessPartnerNumbering',props)).props.onChange({target:{value:'EDIT-'}});
 h.components.resetBusinessPartnerNumberingRecovery(props.session,'tenant');assert.equal(s.length,0);
});

test('Reload discards the draft and displays the latest server configuration',async()=>{
 const s=storage();let current={...initial};const h=partnerHarness('business-partner-numbering','en',()=>current,s);
 h.tree('BusinessPartnerNumbering',props);await h.flush();let tree=h.tree('BusinessPartnerNumbering',props);
 field(tree).props.onChange({target:{value:'DRAFT-'}});assert.equal(s.length,1);current={...initial,prefix:'SERVER-',version:4};
 tree=h.tree('BusinessPartnerNumbering',props);find(tree,n=>n.props?.children==='Reload saved configuration').props.onClick();
 h.tree('BusinessPartnerNumbering',props);await h.flush();tree=h.tree('BusinessPartnerNumbering',props);
 assert.equal(field(tree).props.value,'SERVER-');assert.equal(s.length,0);
 await find(tree,n=>n.type==='form').props.onSubmit({preventDefault(){}});
 assert.equal(h.calls.find(c=>c.method==='PUT')?.body.version,4);
});
