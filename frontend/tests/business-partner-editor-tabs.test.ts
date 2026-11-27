import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness,find,session} from './business-partner-harness.ts';
const record={id:'bp1',version:5,code:'BP-1',kind:'ORGANIZATION',status:'ACTIVE',legal_name:'Original',tax_identifiers:[],addresses:[],contact_channels:[]};
const props={id:'bp1' as string|null,session:{...session,permissions:['business-partners.read','business-partners.update','business-partner-companies.read']},scope:(p:string)=>p,onError:(e:any)=>e.code,onClose(){},onSaved(){}};
const byId=(tree:any,id:string)=>find(tree,n=>n.props?.id===id);
function storage(){const values=new Map<string,string>();return {values,getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v)},removeItem:(k:string)=>{values.delete(k)},clear:()=>values.clear(),key:(i:number)=>[...values.keys()][i]??null,get length(){return values.size}};}
test('companies and roles belong to a dedicated tab, not the identity panel',async()=>{
 for(const locale of ['it','en']){
  const h=partnerHarness('business-partner-workspace',locale,()=>record),render=()=>h.tree('BusinessPartnerEditor',props);
  render();await h.flush();let tree=render();
  const tab=byId(tree,'bp-tab-companies');assert.ok(tab,'Missing companies tab');assert.equal(tab.props.type,'button');
  assert.equal(tab.props.children,locale==='it'?'Aziende e ruoli':'Companies and roles');
  assert.equal(find(byId(tree,'bp-panel-general'),n=>n.type?.name==='BusinessPartnerCompanies'),undefined);
  assert.equal(byId(tree,'bp-panel-companies').props.hidden,true);
  byId(tree,'bp-legal_name').props.onChange({target:{value:'Pending identity'}});
  tab.props.onClick();tree=render();assert.equal(byId(tree,'bp-panel-general').props.hidden,true);assert.equal(byId(tree,'bp-panel-companies').props.hidden,false);
  assert.ok(find(byId(tree,'bp-panel-companies'),n=>n.type?.name==='BusinessPartnerCompanies'));
  byId(tree,'bp-tab-general').props.onClick();tree=render();assert.equal(byId(tree,'bp-legal_name').props.value,'Pending identity');
  assert.equal(h.calls.filter(call=>call.method!=='GET').length,0);
 }
});
test('companies tab survives remount and remains independent of base edit permissions',async()=>{
 const saved=storage(),p={...props,session:{...props.session,permissions:['business-partners.read','business-partner-companies.read']}};
 const h=partnerHarness('business-partner-workspace','en',()=>record,saved),render=()=>h.tree('BusinessPartnerEditor',p);
 render();await h.flush();byId(render(),'bp-tab-companies').props.onClick();render();await h.flush();
 const restored=partnerHarness('business-partner-workspace','en',()=>record,saved);restored.tree('BusinessPartnerEditor',p);await restored.flush();
 const tree=restored.tree('BusinessPartnerEditor',p);assert.equal(byId(tree,'bp-tab-companies').props['aria-selected'],true);assert.equal(byId(tree,'bp-panel-companies').props.hidden,false);
 const denied={...p,session:{...p.session,permissions:['business-partners.read']}};
 const rejected=partnerHarness('business-partner-workspace','en',()=>record,saved);rejected.tree('BusinessPartnerEditor',denied);await rejected.flush();const deniedTree=rejected.tree('BusinessPartnerEditor',denied);
 assert.equal(byId(deniedTree,'bp-tab-companies'),undefined);assert.equal(byId(deniedTree,'bp-panel-general').props.hidden,false);
});
test('new BP has no company tab and an existing taxation tab is preserved',async()=>{
 const fresh=partnerHarness('business-partner-workspace','en',()=>record);assert.equal(byId(fresh.tree('BusinessPartnerEditor',{...props,id:null}),'bp-tab-companies'),undefined);
 const h=partnerHarness('business-partner-workspace','en',()=>record),p={...props,session:{...props.session,permissions:[...props.session.permissions,'tax-partner-profiles.read']}};
 h.tree('BusinessPartnerEditor',p);await h.flush();const tree=h.tree('BusinessPartnerEditor',p);assert.ok(byId(tree,'bp-tab-taxation'));assert.ok(byId(tree,'bp-tab-companies'));
});
