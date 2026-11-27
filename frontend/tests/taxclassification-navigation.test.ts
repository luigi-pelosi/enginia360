import test from 'node:test';
import assert from 'node:assert/strict';
import {can,groupPermissions,navigationPath,taxResources} from '../lib/model.ts';

const global={isSuperAdmin:true,tenantId:null,permissions:[]};
for(const kind of ['item','partner']) {
 const classification=`tax-${kind}-classifications`,profile=`tax-${kind}-profiles`;
 test(`${classification}: percorso condiviso, operazioni finite e nessun grant implicito`,()=>{
  assert.ok(taxResources.includes(classification));
  assert.deepEqual(navigationPath(classification),['settings','settings-master-data','tax-management',classification]);
  for(const action of ['read','create','update','deactivate','reactivate','install_templates'])assert.equal(can(global,classification,action),true,action);
  for(const action of ['delete','assign','schedule','any'])assert.equal(can(global,classification,action),false,action);
  const reader={isSuperAdmin:false,tenantId:'tenant',permissions:[classification+'.read']};
  assert.equal(can(reader,classification,'read'),true);
  assert.equal(can(reader,classification,'create'),false);
  assert.equal(can(reader,'tax-codes','read'),false);
  assert.equal(can(reader,profile,'assign'),false);
 });
 test(`${profile}: permessi della scheda anagrafica distinti da modifica e nomenclatori`,()=>{
  assert.equal(taxResources.includes(profile),false);
  assert.deepEqual(navigationPath(profile),kind==='item'?['catalog','catalog-items',profile]:['business-partners',profile]);
  for(const action of ['read','assign','schedule'])assert.equal(can(global,profile,action),true,action);
  for(const action of ['create','update','delete','deactivate','reactivate','install_templates'])assert.equal(can(global,profile,action),false,action);
  const scheduler={isSuperAdmin:false,tenantId:'tenant',permissions:[profile+'.read',profile+'.schedule']};
  assert.equal(can(scheduler,profile,'schedule'),true);
  assert.equal(can(scheduler,profile,'assign'),false);
  assert.equal(can(scheduler,classification,'read'),false);
  const tree=groupPermissions([{id:'read',code:profile+'.read'}]);
  function find(nodes:any[]):any{return nodes.find(n=>n.key===profile)||nodes.map(n=>find(n.children||n.resources||[])).find(Boolean);}
  assert.equal(find(tree)?.key,profile);
 });
}
