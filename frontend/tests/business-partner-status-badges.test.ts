import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';

const options=[{id:'c1',name:'One',is_enabled:true,permissions:['read','update']}];
const row={id:'rel',company_id:'c1',business_partner_id:'bp1',company_name:'One',bp_name:'Partner',bp_status:'ACTIVE',status:'ACTIVE',version:1,roles:[{id:'r1',role_code:'CUSTOMER',status:'ACTIVE'},{id:'r2',role_code:'SUPPLIER',status:'BLOCKED'}],usable_roles:[]};
const labels:any={en:{active:'Active',blocked:'Blocked',customer:'Customer',supplier:'Supplier'},it:{active:'Attivo',blocked:'Bloccato',customer:'Cliente',supplier:'Fornitore'}};
function all(node:any,predicate:(n:any)=>boolean):any[]{if(!node||typeof node!=='object')return [];return [...(predicate(node)?[node]:[]),...[node.props?.children].flat(Infinity).flatMap(child=>all(child,predicate))];}
for(const locale of ['it','en']) for(const view of ['business-partner-companies','company-business-partners']) test(`${view} displays localized assigned-role statuses as badges (${locale})`,async()=>{
 const h=partnerHarness(view,locale,p=>p.startsWith('/business-partner-companies/options')?{items:options}:view==='business-partner-companies'?{items:[row]}:{items:[row],total:1,page:1,pageSize:25});
 const component=view==='business-partner-companies'?'BusinessPartnerCompanies':'CompanyBusinessPartners';
 const props={businessPartnerId:'bp1',session:{...session,permissions:['business-partners.read','business-partner-companies.read','business-partner-companies.update']},scope:(p:string)=>p,onError:String,onOpenPartner:()=>{}};
 const render=()=>h.tree(component,props);render();await h.flush();if(view==='company-business-partners'){render();await h.flush();}
 const tree=render(), l=labels[locale], relationBadge=find(tree,n=>n.props?.variant==='secondary'&&n.props?.children===l.active);
 assert.ok(relationBadge,'existing relationship status badge');
 const badges=all(tree,n=>n.type===relationBadge.type&&n.props?.variant==='secondary');
 assert.ok(badges.some(n=>n.props.children===l.blocked),'blocked assigned role is a badge');
 assert.ok(badges.filter(n=>n.props.children===l.active).length >= (view==='company-business-partners'?3:2),'active assigned role is a badge');
 assert.ok(find(tree,n=>n.props?.children===l.customer),'role remains separate text');
 assert.ok(find(tree,n=>n.props?.children===l.supplier),'role remains separate text');
 if(view==='business-partner-companies'){
  find(tree,n=>n.props?.['data-action']==='manage-company-c1').props.onClick();
  const dialog=find(render(),n=>n.props?.['data-bp-company-editor']==='manage');
  assert.ok(find(dialog,n=>n.type===relationBadge.type&&n.props?.children===l.active),'relationship status in management dialog is a badge');
 }
});
