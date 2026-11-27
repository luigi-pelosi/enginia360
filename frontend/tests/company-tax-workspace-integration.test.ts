import test from 'node:test';
import assert from 'node:assert/strict';
import {harness,find,session} from './workspace-harness.ts';
import {companyTaxKey} from '../lib/company-tax.ts';
const resource={key:'companies',fields:[{name:'name',type:'text',required:true},{name:'is_enabled',type:'boolean'}]};
const draft={values:{tax_type_id:'vat',establishment_country_id:'it',tax_code:'CF-INITIAL'},registrations:[{values:{country_id:'it',tax_identifier:'IT12345678901',registration_type:'DOMESTIC',valid_from:'2026-11-26',valid_to:null,notes:null},profiles:[{tax_regime_id:'ordinary',valid_from:'2026-11-26',valid_to:null}]}]};
function setup(row:any=null,storage=new Map<string,string>(),respond:(p:string,m:string,b:any)=>any=(p)=>p.endsWith('/configurations')?{items:[{id:'root',company_id:'c',tenant_id:'t',...draft.values,registrations:draft.registrations.map(r=>({...r.values,profiles:r.profiles}))}]}:{id:'c',tenant_id:'t',name:'New',is_enabled:true},global=true,canWrite=true,locale='en') {
 const h=harness(locale,{},respond,storage,undefined,true);
 const props={resource,row,canWrite,session:{...session,isSuperAdmin:global,permissions:['companies.read','companies.create','companies.update','company-tax-configurations.read','company-tax-configurations.create']},tenant:'t',scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:String};
 const render=()=>h.tree('RecordEditor',props);
 const settle=async()=>{for(let i=0;i<4;i++){render();await h.flush();}return render();};
 return {h,props,storage,render,settle};
}
const panel=(tree:any)=>find(tree,n=>n.type?.name==='CompanyTaxation');
const id=(tree:any,value:string)=>find(tree,n=>n.props?.id===value);
const save=(tree:any)=>id(tree,'record-form').props.onSubmit({preventDefault(){}});

test('Company mounts independent fiscal panel outside general form and fieldset, including read-only general',async()=>{
 for(const locale of ['it','en']) {
  const s=setup({id:'c',name:'Company',is_enabled:true},undefined,undefined,false,false,locale);let tree=await s.settle();
  assert.ok(id(tree,'company-tab-general'));assert.ok(id(tree,'company-tab-taxation'));
  id(tree,'company-tab-taxation').props.onClick();tree=s.render();
  assert.match(find(tree,n=>n.props?.className?.startsWith('flex max-h-[90dvh]')).props.className,/sm:max-w-\[min\(96vw,90rem\)\]/);
  assert.equal(panel(tree).props.companyId,'c');assert.equal(panel(tree).props.disabled,false);
  assert.equal(find(id(tree,'record-form'),n=>n.type?.name==='CompanyTaxation'),undefined);
  assert.equal(id(tree,'record-form').props.hidden,true);
  assert.equal(find(id(tree,'record-form'),n=>n.type==='fieldset').props.disabled,true);
  assert.deepEqual(s.h.apiCalls,[]);
 }
});

test('initial fiscal drafts join only first POST and frozen parent recovery, then clear after readback',async()=>{
 const s=setup();let tree=await s.settle();id(tree,'field-name').props.onChange({target:{value:'New'}});panel(s.render()).props.onStagedChange([draft]);
 tree=await s.settle();assert.deepEqual(JSON.parse(s.storage.get('workspace:u:t:record:companies')!).taxConfigurations,[draft]);
 s.storage.set(companyTaxKey('u','t','new'),JSON.stringify({mode:'create'}));
 await save(tree);
 const call=s.h.apiCalls.findIndex(p=>p==='/data/companies/save');assert.ok(call>=0);assert.deepEqual(JSON.parse(JSON.stringify(s.h.apiPayloads[call])).taxConfigurations,[draft]);
 assert.equal(s.storage.has(companyTaxKey('u','t','new')),false);
 assert.ok(s.h.apiCalls.some(p=>p==='/tax/companies/c/configurations'));
});

test('existing general recovery preserves original baseline and tab without a fictitious company version or tax PUT',async()=>{
 const storage=new Map([['workspace:u:t:record:companies',JSON.stringify({kind:'edit',id:'c',baseline:{name:'Old',is_enabled:true},values:{name:'Draft',is_enabled:true},tab:'taxation',taxConfigurations:[draft]})]]);
 const s=setup({id:'c',name:'Old',is_enabled:true},storage);let tree=await s.settle();
 assert.equal(id(tree,'field-name').props.value,'Draft');assert.equal(id(tree,'record-form').props.hidden,true);
 assert.equal(panel(tree).props.staged.length,0);
 await save(tree);const body=s.h.apiPayloads[s.h.apiCalls.findIndex(p=>p.includes('/save'))] as any;
 assert.equal(Object.hasOwn(body,'taxConfigurations'),false);assert.equal(Object.hasOwn(body,'expectedVersion'),false);
 const recovery=JSON.parse(storage.get('workspace:u:t:record:companies')!);assert.equal(recovery.baseline.name,'Old');assert.equal(Object.hasOwn(recovery,'version'),false);
});

test('uncertain initial Company creation retains frozen staged body and blocks reload replay',async()=>{
 const s=setup(null,undefined,()=>{throw Error('lost response');});let tree=await s.settle();id(tree,'field-name').props.onChange({target:{value:'New'}});panel(s.render()).props.onStagedChange([draft]);tree=await s.settle();await save(tree);
 assert.deepEqual(JSON.parse(s.storage.get('workspace:u:t:record:companies')!).taxConfigurations,[draft]);
 assert.ok(s.storage.has('record-pending:u:t:companies'));
 assert.deepEqual(JSON.parse(s.storage.get('record-pending:u:t:companies')!).body.taxConfigurations,[draft]);
 const reloaded=setup(null,s.storage);tree=await reloaded.settle();assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,true);await save(tree);assert.deepEqual(reloaded.h.apiCalls,[]);
});

test('pending Company draft stays frozen when the uncertain general editor receives a change',async()=>{
 const storage=new Map([['workspace:u:t:record:companies',JSON.stringify({kind:'create',values:{name:'Frozen',is_enabled:true},taxConfigurations:[draft]})],['record-pending:u:t:companies','pending']]);
 const s=setup(null,storage);let tree=await s.settle();id(tree,'field-name').props.onChange({target:{value:'Must not replace frozen body'}});await s.settle();assert.equal(JSON.parse(storage.get('workspace:u:t:record:companies')!).values.name,'Frozen');
});

test('a Company reader reopens the recovered fiscal tab after an authoritative list read without companies.update',async()=>{
 const storage=new Map([['workspace:u:t:record:companies',JSON.stringify({kind:'edit',id:'c',baseline:{name:'Company'},values:{name:'Company'},tab:'taxation'})]]);
 const operator={...session,permissions:['companies.read','company-tax-configurations.read']};
 const h=harness('en',{0:operator,1:false,5:[resource],6:'companies',7:'t',25:true},()=>({items:[{id:'c',tenant_id:'t',name:'Company'}],total:1}),storage);
 h.components.default();h.effects[8]();await new Promise(resolve=>setImmediate(resolve));
 assert.equal((h.updates[16] as any)?.row.id,'c');
});

test('a tax-only grant cannot expose Company CRUD traversal',()=>{
 const h=harness();assert.equal(h.components.canOpenResource({...session,permissions:['company-tax-configurations.read']},'companies'),false);
 assert.equal(h.components.canOpenResource({...session,permissions:['companies.read']},'companies'),true);
});

test('recovered general PUT only includes locally edited fields, preserving fresh unedited values',async()=>{
 const storage=new Map([['workspace:u:t:record:companies',JSON.stringify({kind:'edit',id:'c',baseline:{name:'Old',is_enabled:true},values:{name:'Draft',is_enabled:true}})]]);
 const s=setup({id:'c',name:'Old',is_enabled:false},storage);const tree=await s.settle();await save(tree);const body=s.h.apiPayloads[s.h.apiCalls.findIndex(p=>p.includes('/save'))] as any;
 assert.equal(body.values.name,'Draft');assert.equal(Object.hasOwn(body.values,'is_enabled'),false);assert.equal(Object.hasOwn(body,'expectedVersion'),false);
});

test('Companies menu reset clears ordinary tax recovery and preserves pending plus other users and tenants',()=>{
 const ordinary=companyTaxKey('u','t','c'),pending=companyTaxKey('u','t','pending'),foreign=companyTaxKey('other','t','c'),tenant=companyTaxKey('u','other','c');
 const storage=new Map([[ordinary,JSON.stringify({editor:{}})],[pending,JSON.stringify({pending:{path:'/frozen',body:{expectedVersion:2}}})],[foreign,'{}'],[tenant,'{}'],['workspace:u:t:record:companies',JSON.stringify({kind:'edit',id:'c'})]]);
 const h=harness('en',{0:{...session,permissions:['companies.read']},1:false,5:[resource],6:'companies',7:'t'},undefined,storage);
 const tree=h.components.default();find(tree,n=>n.type?.name==='WorkspaceNavigation').props.navigate('companies');
 assert.equal(storage.has(ordinary),false);assert.equal(storage.has('workspace:u:t:record:companies'),false);assert.equal(storage.has(pending),true);assert.equal(storage.has(foreign),true);assert.equal(storage.has(tenant),true);
});

test('logout clears only this user ordinary fiscal recoveries across tenants and retains uncertain markers',async()=>{
 const ordinary=companyTaxKey('u','t','c'),otherTenant=companyTaxKey('u','other','c'),pending=companyTaxKey('u','t','pending'),foreign=companyTaxKey('other','t','c');
 const storage=new Map([[ordinary,'{}'],[otherTenant,'{}'],[pending,JSON.stringify({pending:{path:'/frozen'}})],[foreign,'{}']]);
 const browser={history:{replaceState(){}},location:{pathname:'/'}};
 const h=harness('en',{0:{...session,permissions:['companies.read']},1:false,5:[resource],6:'companies',7:'t'},undefined,storage,browser);
 const tree=h.components.default();id(tree,'user-logout-menu-item').props.onSelect();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(storage.has(ordinary),false);assert.equal(storage.has(otherTenant),false);assert.equal(storage.has(pending),true);assert.equal(storage.has(foreign),true);
});

test('failed initial fiscal readback preserves pending staged Company and prevents a second POST',async()=>{
 let posts=0;const s=setup(null,undefined,(_p,m)=>{if(m==='POST'){posts++;return {id:'c'};}return {items:[]};});let tree=await s.settle();id(tree,'field-name').props.onChange({target:{value:'New'}});panel(s.render()).props.onStagedChange([draft]);tree=await s.settle();await save(tree);
 assert.ok(s.storage.has('record-pending:u:t:companies'));assert.deepEqual(JSON.parse(s.storage.get('workspace:u:t:record:companies')!).taxConfigurations,[draft]);tree=s.render();assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,true);await save(tree);assert.equal(posts,1);
});

test('native validation on hidden Company general reveals the general tab without unmounting inputs',async()=>{
 const s=setup();let tree=await s.settle();id(tree,'company-tab-taxation').props.onClick();tree=s.render();assert.equal(id(tree,'record-form').props.hidden,true);id(tree,'record-form').props.onInvalidCapture();tree=s.render();assert.equal(id(tree,'record-form').props.hidden,false);assert.ok(id(tree,'field-name'));
});

test('ordinary new Company cannot stage fiscal children but ordinary creation remains available',async()=>{
 const s=setup(null,undefined,undefined,false);let tree=await s.settle();assert.equal(panel(tree).props.disabled,true);id(tree,'field-name').props.onChange({target:{value:'New'}});panel(s.render()).props.onStagedChange([draft]);tree=await s.settle();await save(tree);
 const body=s.h.apiPayloads[s.h.apiCalls.findIndex(p=>p.includes('/save'))] as any;assert.equal(Object.hasOwn(body,'taxConfigurations'),false);
});
