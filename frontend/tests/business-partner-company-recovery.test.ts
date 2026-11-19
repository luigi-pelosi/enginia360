import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const props={session:{...session,permissions:['business-partners.read','business-partner-companies.read']},scope:(p:string)=>p,onError:()=> 'error',tenantId:'t'};
function storage(){const entries=new Map<string,string>();return {getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}};}
test('revoking company read restores the identity list without retaining an unauthorized active view',()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}));let tree=h.tree('BusinessPartnerWorkspace',props);find(tree,n=>n.props?.['data-action']==='partner-company-view').props.onClick();tree=h.tree('BusinessPartnerWorkspace',{...props,session:{...props.session,permissions:['business-partners.read']}});assert.ok(find(tree,n=>n.props?.className==='gap-0 overflow-hidden py-0'));assert.equal(find(tree,n=>n.type?.name==='CompanyBusinessPartners'),undefined);
});
test('company view survives workspace remount in same user/tenant and is denied after permission removal',async()=>{
 const saved=storage();const first=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),saved);const render=()=>first.tree('BusinessPartnerWorkspace',props);render();await first.flush();find(render(),n=>n.props?.['data-action']==='partner-company-view').props.onClick();render();await first.flush();
 const second=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),saved);second.tree('BusinessPartnerWorkspace',props);await second.flush();assert.ok(find(second.tree('BusinessPartnerWorkspace',props),n=>n.type?.name==='CompanyBusinessPartners'));
 const denied=partnerHarness('business-partner-workspace','en',()=>({items:[],total:0}),saved);const p={...props,session:{...props.session,permissions:['business-partners.read']}};denied.tree('BusinessPartnerWorkspace',p);await denied.flush();assert.equal(find(denied.tree('BusinessPartnerWorkspace',p),n=>n.type?.name==='CompanyBusinessPartners'),undefined);
});
