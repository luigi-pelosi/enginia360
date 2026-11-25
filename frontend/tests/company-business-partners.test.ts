import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find as findChild,session} from './business-partner-harness.ts';
const find=(tree:any,predicate:(n:any)=>boolean):any=>findChild(tree,predicate) ?? (()=>{const bar=findChild(tree,n=>Array.isArray(n.props?.fields));for(const field of bar?.props.fields??[]){const match=findChild(field.content,predicate);if(match)return match;}})();
const props={session:{...session,permissions:['business-partners.read','business-partner-companies.read']},scope:(p:string)=>p+'&tenantId=t',onError:(e:any)=>e.code,onOpenPartner:(id:string)=>{}};
const companies=[{id:'a',name:'Alpha',is_enabled:true,permissions:['read','use_customer']},{id:'b',name:'Beta',is_enabled:true,permissions:['create']},{id:'c',name:'Charlie',is_enabled:false,permissions:['read']}];
const select=(tree:any,id:string)=>find(tree,n=>typeof n.props?.onValueChange==='function'&&find(n,c=>c.props?.id===id));
const action=(tree:any,id:string)=>find(tree,n=>n.props?.['data-action']===id);
test('default company view lists every authorized company with no role or usability filter',async()=>{
 const h=partnerHarness('company-business-partners','en',p=>p.startsWith('/business-partner-companies/options')?{items:companies}:{items:[],total:0,page:1,pageSize:25});
 const render=()=>h.tree('CompanyBusinessPartners',props);
 render();await h.flush();render();await h.flush();const tree=render();
 assert.equal(find(tree,n=>n.props?.id==='company-partner-usable').props.checked,false);
 assert.equal(select(tree,'company-partner-company').props.value,'all');
 assert.ok(h.calls.some(c=>c.path.startsWith('/business-partner-companies?role=&usableOnly=false&search=&page=1&pageSize=25')));
 assert.match(h.render('CompanyBusinessPartners',props),/All companies/);
});
test('operational view selects only exact readable companies and requests server usable role/search/page filters',async()=>{
 const opened:string[]=[];const h=partnerHarness('company-business-partners','en',(p)=>p.startsWith('/business-partner-companies/options')?{items:companies}:{items:[{id:'r',company_id:'a',company_name:'Alpha',business_partner_id:'bp',bp_name:'Partner',bp_code:'BP1',bp_status:'ACTIVE',status:'ACTIVE',roles:[{id:'role',role_code:'CUSTOMER',status:'ACTIVE'}],usable_roles:[]}],total:30,page:1,pageSize:25});const render=()=>h.tree('CompanyBusinessPartners',{...props,onOpenPartner:(id:string)=>opened.push(id)});
 render();await h.flush();let tree=render();assert.ok(select(tree,'company-partner-company'),'operational company selector exists');assert.equal(h.calls.filter(c=>c.path.startsWith('/companies/')).length,0);
 select(tree,'company-partner-company').props.onValueChange('b');render();await h.flush();assert.equal(h.calls.filter(c=>c.path.startsWith('/companies/')).length,0);
 select(render(),'company-partner-company').props.onValueChange('a');render();await h.flush();tree=render();assert.match(h.calls.at(-1)!.path,/\/companies\/a\/business-partners\?role=&usableOnly=false&search=&page=1&pageSize=25/);
 select(tree,'company-partner-role').props.onValueChange('CUSTOMER');find(render(),n=>n.props?.id==='company-partner-search').props.onChange({target:{value:'Ab & Z'}});find(render(),n=>n.props?.id==='company-partner-usable').props.onCheckedChange(false);render();await h.flush();tree=render();assert.match(h.calls.at(-1)!.path,/role=CUSTOMER&usableOnly=false&search=Ab%20%26%20Z/);
 action(tree,'next-company-partners').props.onClick();render();await h.flush();assert.match(h.calls.at(-1)!.path,/page=2&/);action(render(),'open-company-partner-bp').props.onClick();assert.deepEqual(opened,['bp']);
 // Structural customer assignment is not reported as usable when the server returns [].
 assert.equal(find(render(),n=>n.props?.['data-usable-roles']==='bp').props.children,'—');
});
test('company filters restore only after fresh authorized options, including page and structural mode',async()=>{
 const entries=new Map([['recovery',JSON.stringify({draft:{legal_name:'Pending'},companyFilters:{version:2,companyId:'a',role:'SUPPLIER',usableOnly:false,search:'Stored',page:2,filtersExpanded:true}})]]);const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}};
 const h=partnerHarness('company-business-partners','en',(p)=>p.startsWith('/business-partner-companies/options')?{items:companies}:{items:[{id:'r',business_partner_id:'bp',roles:[],usable_roles:[],status:'ACTIVE'}],total:30,page:2,pageSize:25},storage);const p={...props,recoveryKey:'recovery'};h.tree('CompanyBusinessPartners',p);await h.flush();h.tree('CompanyBusinessPartners',p);await h.flush();assert.ok(h.calls.some(c=>/role=SUPPLIER&usableOnly=false&search=Stored&page=2&/.test(c.path)));
 const tree=h.tree('CompanyBusinessPartners',p);await h.flush();const bar=find(tree,n=>n.props?.id==='company-partner-filters');assert.equal(bar.props.expanded,true);const requests=h.calls.length;
 bar.props.onExpandedChange(false);h.tree('CompanyBusinessPartners',p);await h.flush();assert.equal(h.calls.length,requests);const restored=JSON.parse(entries.get('recovery')!);assert.equal(restored.companyFilters.filtersExpanded,false);assert.equal(restored.companyFilters.page,2);assert.deepEqual(restored.draft,{legal_name:'Pending'});
});
test('no relationship read or no BP read means no options or partner fetch',async()=>{
 for(const permissions of [['business-partners.read'],['business-partner-companies.read'],[]]){const h=partnerHarness('company-business-partners');assert.equal(h.tree('CompanyBusinessPartners',{...props,session:{...session,permissions}}),null);await h.flush();assert.equal(h.calls.length,0);}
});
test('old automatically stored filters do not override the new unfiltered default or erase identity drafts',async()=>{
 const entries=new Map([['recovery',JSON.stringify({draft:{legal_name:'Pending'},companyFilters:{companyId:'a',role:'',usableOnly:true,search:'',page:1}})]]);
 const storage={getItem:(k:string)=>entries.get(k)??null,setItem:(k:string,v:string)=>{entries.set(k,v)},removeItem:(k:string)=>{entries.delete(k)},clear:()=>entries.clear(),key:(i:number)=>[...entries.keys()][i]??null,get length(){return entries.size}};
 const h=partnerHarness('company-business-partners','it',p=>p.startsWith('/business-partner-companies/options')?{items:companies}:{items:[],total:0,page:1,pageSize:25},storage);
 const p={...props,recoveryKey:'recovery'},render=()=>h.tree('CompanyBusinessPartners',p);
 render();await h.flush();render();await h.flush();const tree=render();await h.flush();
 assert.equal(select(tree,'company-partner-company').props.value,'all');
 assert.equal(find(tree,n=>n.props?.id==='company-partner-usable').props.checked,false);
 assert.deepEqual(JSON.parse(entries.get('recovery')!).draft,{legal_name:'Pending'});
 assert.match(h.calls.at(-1)!.path,/^\/business-partner-companies\?/);
});
