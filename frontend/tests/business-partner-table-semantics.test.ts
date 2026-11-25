import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const props={session:{...session,permissions:['business-partners.read','business-partner-companies.read']},scope:(p:string)=>p,onError:String,onOpenPartner(){},businessPartnerId:'bp'};
const row={id:'r',company_id:'c',company_name:'Company',business_partner_id:'bp',bp_name:'Partner',bp_code:'00123',bp_status:'ACTIVE',status:'ACTIVE',roles:[],usable_roles:[]};
function all(node:any,predicate:(n:any)=>boolean):any[]{if(!node||typeof node!=='object')return [];return [...(predicate(node)?[node]:[]),...[node.props?.children].flat(Infinity).flatMap(child=>all(child,predicate))];}
for(const [file,component] of [['business-partner-companies','BusinessPartnerCompanies'],['company-business-partners','CompanyBusinessPartners']])test(`${component} centers status and fixed action columns, not digit-only codes`,async()=>{
 const h=partnerHarness(file,'en',p=>p.includes('/options')?{items:[{id:'c',name:'Company',permissions:['read'],is_enabled:true}]}:{items:[row],total:1,page:1,pageSize:25});
 const render=()=>h.tree(component,props);render();await h.flush();render();await h.flush();const tree=render();
 const actions=find(tree,n=>n.props?.children==='Actions');assert.equal(actions.props.kind,'actions');assert.match(actions.props.className,/w-\[120px\]/);
 const status=find(tree,n=>n.props?.children==='Relationship status');assert.equal(status.props.kind,'status');
 assert.ok(all(tree,n=>n.props?.kind==='status').length>=2);
 assert.equal(find(tree,n=>n.props?.children==='Assigned roles').props.kind,'status');
 assert.ok(find(tree,n=>n.props?.kind==='status'&&n.props?.className==='whitespace-normal'),'assigned role badge groups are centered');
 if(file==='company-business-partners')assert.equal(find(tree,n=>n.props?.children==='00123').props.kind,'text');
});
test('BP list declares status and actions while codes and tax/phone values stay textual',()=>{
 const source=readFileSync(new URL('../components/business-partner-workspace.tsx',import.meta.url),'utf8');
 assert.match(source,/<TableHead key={key} kind={key === "status" \? "status" : "text"}/);
 assert.match(source,/<TableCell kind="status"><Badge/);
 assert.match(source,/<TableCell kind="text"[^>]*>{row.value}/);
 assert.match(source,/<TableCell kind="status">{row.is_primary/);
});
test('company list uses compact search-first controlled filters only',()=>{
 const h=partnerHarness('company-business-partners');const tree=h.tree('CompanyBusinessPartners',props);
 const bar=find(tree,n=>Array.isArray(n.props?.fields));assert.ok(bar,'shared compact filter bar');
 assert.deepEqual(Array.from(bar.props.fields,(field:any)=>field.key),['search','company','role','usable']);
 assert.ok(find(bar.props.fields[0].content,n=>n.props?.id==='company-partner-search'));
 assert.ok(find(bar.props.fields[3].content,n=>n.props?.id==='company-partner-usable'));
});
