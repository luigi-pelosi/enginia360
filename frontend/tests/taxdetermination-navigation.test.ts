import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {can,groupPermissions,navigationPath,taxResources,type Session} from '../lib/model.ts';
import {taxSections,type TaxSection} from '../lib/tax.ts';
import {harness} from './tax-interaction.test.ts';

const actions={
 'tax-rules':['read','create','update','validate','publish','withdraw','install_templates'],
 'tax-determination':['read','simulate','determine'],
};
const global={isSuperAdmin:true,tenantId:null,permissions:[]};

test('Fase 4 routing and permissions remain finite under TaxManagement',()=>{
 for(const [resource,allowed] of Object.entries(actions)){
  assert.ok(taxResources.includes(resource));assert.ok((taxSections as readonly string[]).includes(resource));
  assert.deepEqual(navigationPath(resource),['settings','settings-master-data','tax-management',resource]);
  for(const action of allowed)assert.equal(can(global,resource,action),true,resource+'.'+action);
  for(const action of ['delete','schedule','reactivate','create_version','simulate_draft','determine_extra'].filter(action=>!allowed.includes(action)))assert.equal(can(global,resource,action),false,resource+'.'+action);
  const reader={isSuperAdmin:false,tenantId:'t',permissions:[resource+'.read']};
  assert.equal(can(reader,resource,'read'),true);for(const action of allowed.filter(action=>action!=='read'))assert.equal(can(reader,resource,action),false);
 }
 const rows=Object.entries(actions).flatMap(([resource,list])=>list.map(action=>({id:resource+'.'+action,code:resource+'.'+action})));
 const administration=groupPermissions(rows).find(group=>group.key==='administration');
 const settings=administration?.resources.find(branch=>branch.key==='settings');
 const master=settings?.children.find(branch=>branch.key==='settings-master-data');
 const tax=master?.children.find(branch=>branch.key==='tax-management');
 assert.deepEqual(tax?.children.map(branch=>branch.key),Object.keys(actions));
});

for(const [resource,component] of [['tax-rules','TaxRules'],['tax-determination','TaxSimulator']] as const)test('Fase 4 mounts '+resource+' without hidden phase-one reads',async()=>{
 const identity:Session={id:'u',username:'reader',displayName:'Reader',preferredLanguage:'it',isSuperAdmin:false,tenantId:'t',mustChangePassword:false,permissions:[resource+'.read','tax-codes.read']};
 const editor={id:'r',expectedVersion:4,original:null,values:{name:'Existing draft',code:'VAT',description:'',tax_type_id:'vat',country_id:'it'},versions:[],readonly:true};
 const h=harness({section:resource as TaxSection,tab:'audit',editor},()=>undefined,identity);await h.settle();
 const mounted=h.find((node:any)=>node.type?.name===component);assert.ok(mounted,component+' must own the selected route');
 assert.equal(mounted.props.tenantId,'t');assert.equal(mounted.props.session.id,'u');assert.ok(mounted.props.navigation);
 assert.equal(h.calls.length,0,'The outer workspace must not fetch codes, catalogs or a recovered hidden audit');h.unmount();
});

test('Fase 4 permissions have consistent Italian and English labels',()=>{
 for(const locale of ['it','en']){
  const messages=JSON.parse(readFileSync(new URL('../messages/'+locale+'.json',import.meta.url),'utf8'));
  for(const [resource,list] of Object.entries(actions)){
   assert.ok(messages.resources[resource],locale+': '+resource);
   for(const action of list)assert.ok(messages.permissionActions[action],locale+': '+action);
  }
  assert.ok(messages.taxRules);assert.ok(messages.taxSimulator);
 }
});
