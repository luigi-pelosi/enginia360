import test from 'node:test';
import assert from 'node:assert/strict';
import {partnerHarness, find, session} from './business-partner-harness.ts';
import {driver} from './profile-dialog-harness.ts';

const props = {id:null, session:{...session, permissions:['business-partners.create','business-partner-numbering.read']}, scope:(s:string)=>s, onClose(){}, onSaved(){}, onError(){return 'error';}};
const label=(tree:any,id:string)=>{const result=find(tree,n=>n.props?.htmlFor===id);assert.ok(result,`label ${id}`);return result;};
const marker=(tree:any,id:string,required:boolean)=>assert.equal(Boolean(label(tree,id).props.required),required,id);

test('partner identity markers follow status, kind and numbering mode',async()=>{
 const h=partnerHarness('business-partner-workspace','en',()=>({mode:'MANUAL'}));
 const render=()=>h.tree('BusinessPartnerEditor',props);let tree=render();await h.flush();tree=render();
 marker(tree,'bp-code',true);marker(tree,'bp-legal_name',true);
 find(tree,n=>n.props?.value==='ACTIVE'&&n.props?.onValueChange).props.onValueChange('DRAFT');tree=render();marker(tree,'bp-legal_name',false);
 find(tree,n=>n.props?.value==='DRAFT'&&n.props?.onValueChange).props.onValueChange('ACTIVE');tree=render();
 find(tree,n=>n.props?.value==='ORGANIZATION'&&n.props?.onValueChange).props.onValueChange('PERSON');tree=render();marker(tree,'bp-first_name',true);marker(tree,'bp-last_name',true);
 find(tree,n=>n.props?.value==='ACTIVE'&&n.props?.onValueChange).props.onValueChange('DRAFT');tree=render();marker(tree,'bp-first_name',false);marker(tree,'bp-last_name',false);
});

test('partner child editors mark required and optional fields',()=>{
 for(const [kind,required,optional] of [
  ['tax',['country','type','value'],[]],
  ['address',['street','postal_code','city','country'],['label','street_number','province','additional_info']],
  ['contact',['type','value'],['purpose']],
 ] as const){
  const h=partnerHarness();const render=()=>h.tree('BusinessPartnerEditor',props);let tree=render();
  find(tree,n=>n.props?.['data-action']===`add-${kind}`).props.onClick();tree=render();
  for(const key of required)marker(tree,`bp-${kind}-0-${key}`,true);
  for(const key of optional)marker(tree,`bp-${kind}-0-${key}`,false);
 }
});

test('profile password labels are required only when changing password',async()=>{
 const h=driver();let tree=await h.load();
 for(const key of ['first_name','last_name','email'])marker(tree,`profile-${key}`,true);
 for(const key of ['date_of_birth','phone_number'])marker(tree,`profile-${key}`,false);
 for(const key of ['current','new','confirm'])marker(tree,`profile-password-${key}`,false);
 h.change(tree,'profile-password-new','something');tree=h.render();
 for(const key of ['current','new','confirm'])marker(tree,`profile-password-${key}`,true);
 h.change(tree,'profile-password-new','');tree=h.render();
 for(const key of ['current','new','confirm'])marker(tree,`profile-password-${key}`,false);
});
