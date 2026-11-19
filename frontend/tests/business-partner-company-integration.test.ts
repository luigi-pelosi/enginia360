import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const props={id:'bp1',session:{...session,permissions:['business-partners.read','business-partner-companies.read']},scope:(p:string)=>p,onError:(e:any)=>e.code,onClose(){},onSaved(){}};
const record={id:'bp1',version:5,code:'BP-1',kind:'ORGANIZATION',status:'ACTIVE',legal_name:'Original',tax_identifiers:[],addresses:[],contact_channels:[]};
test('persisted BP exposes independent companies section; new identity never exposes it',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>record);h.tree('BusinessPartnerEditor',props);await h.flush();
 const tree=h.tree('BusinessPartnerEditor',props),child=find(tree,n=>n.type?.name==='BusinessPartnerCompanies');assert.ok(child);assert.equal(child.props.businessPartnerId,'bp1');assert.equal(child.props.onSaved,undefined);
 const fresh=partnerHarness();assert.equal(find(fresh.tree('BusinessPartnerEditor',{...props,id:null}),n=>n.type?.name==='BusinessPartnerCompanies'),undefined);
});
test('company relationships require both BP and relationship read',async()=>{
 for(const permissions of [['business-partners.read'],['business-partner-companies.read'],[]]){const h=partnerHarness('business-partner-workspace','en',()=>record);h.tree('BusinessPartnerEditor',{...props,session:{...session,permissions}});await h.flush();assert.equal(find(h.tree('BusinessPartnerEditor',{...props,session:{...session,permissions}}),n=>n.type?.name==='BusinessPartnerCompanies'),undefined);}
});
test('BP workspace offers authorized operational company view without separate menu',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}));let tree=h.tree('BusinessPartnerWorkspace',props);const button=find(tree,n=>n.props?.['data-action']==='partner-company-view');assert.ok(button);button.props.onClick();tree=h.tree('BusinessPartnerWorkspace',props);assert.ok(find(tree,n=>n.type?.name==='CompanyBusinessPartners'));
});
