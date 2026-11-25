import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
test('management dialog presents relationship status as shared badge',async()=>{
 const row={id:'r',company_id:'c1',business_partner_id:'bp',company_name:'One',status:'ACTIVE',version:1,roles:[],usable_roles:[]};
 const h=partnerHarness('business-partner-companies','en',p=>p.startsWith('/business-partner-companies/options')?{items:[{id:'c1',name:'One',is_enabled:true,permissions:['read','update']}]}:{items:[row]});
 const props={businessPartnerId:'bp',session:{...session,permissions:['business-partners.read','business-partner-companies.read','business-partner-companies.update']},scope:(p:string)=>p,onError:String};const render=()=>h.tree('BusinessPartnerCompanies',props);render();await h.flush();let tree=render();const badge=find(tree,n=>n.props?.variant==='secondary'&&n.props?.children==='Active');assert.ok(badge);find(tree,n=>n.props?.['data-action']==='manage-company-c1').props.onClick();tree=render();const dialog=find(tree,n=>n.props?.['data-bp-company-editor']==='manage');assert.ok(find(dialog,n=>n.type===badge.type&&n.props?.children==='Active'),'dialog relationship status badge');
});
