import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness, find, session} from './business-partner-harness.ts';

const numberingProps = {session:{...session,permissions:['business-partner-numbering.read','business-partner-numbering.update']},scope:(p:string)=>p,onError:()=> 'error'};
const marker = (tree:any,id:string,required:boolean) => {const label=find(tree,n=>n.props?.htmlFor===id);assert.ok(label,`label ${id}`);assert.equal(Boolean(label.props.required),required,id);};

test('numbering labels mark the validated configuration, including disabled manual values',async()=>{
 const h=partnerHarness('business-partner-numbering','en',()=>({mode:'AUTO',prefix:'',padding:6,nextNumber:1,version:0}));
 const render=()=>h.tree('BusinessPartnerNumbering',numberingProps);render();await h.flush();let tree=render();
 for(const mode of ['AUTO','MANUAL']) {
  if(mode==='MANUAL'){find(tree,n=>n.props?.value==='AUTO' && n.props?.onValueChange).props.onValueChange('MANUAL');tree=render();}
  for(const id of ['mode','padding','nextNumber']) marker(tree,`bp-numbering-${id}`,true);
  marker(tree,'bp-numbering-prefix',false);
  for(const id of ['padding','nextNumber']) assert.equal(find(tree,n=>n.props?.id===`bp-numbering-${id}`).props.disabled,mode==='MANUAL');
 }
});

test('association preselects the required available company but roles remain optional',async()=>{
 const options=[{id:'c1',name:'One',is_enabled:true,permissions:['read','create']}];
 const props={businessPartnerId:'bp1',session:{...session,permissions:['business-partners.read','business-partner-companies.read','business-partner-companies.create']},scope:(p:string)=>p,onError:()=> 'error'};
 const h=partnerHarness('business-partner-companies','en',(p,m)=>m==='GET'?(p.startsWith('/business-partner-companies/options')?{items:options}:{items:[]}):{});
 const render=()=>h.tree('BusinessPartnerCompanies',props);render();await h.flush();let tree=render();
 find(tree,n=>n.props?.['data-action']==='associate-company').props.onClick();tree=render();
 marker(tree,'bp-company-id',true);
 assert.equal(find(tree,n=>n.props?.['data-action']==='confirm-company-association').props.disabled,false);
 assert.equal(find(tree,n=>n.props?.onValueChange && find(n,c=>c.props?.id==='bp-company-id')).props.value,'c1');
 const company=find(tree,n=>n.props?.onValueChange && find(n,c=>c.props?.id==='bp-company-id'));company.props.onValueChange('c1');tree=render();
 assert.equal(find(tree,n=>n.props?.['data-action']==='confirm-company-association').props.disabled,false);
 const fieldset=find(tree,n=>n.type==='fieldset');assert.ok(fieldset);assert.equal(Boolean(fieldset.props.required),false);
 for(const role of ['CUSTOMER','SUPPLIER']) {const checkbox=find(tree,n=>n.props?.id===`bp-company-${role}`);assert.ok(checkbox);assert.equal(Boolean(checkbox.props.required),false);}
});
