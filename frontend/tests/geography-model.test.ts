import test from 'node:test';
import assert from 'node:assert/strict';
import {can, navigationSections, resourceKeys, normalizeValues, rowLabel} from '../lib/model.ts';
const ordinary={isSuperAdmin:false,tenantId:'tenant',permissions:[]};
test('global geography requires effective read permission and only global SuperAdmin can mutate',()=>{
 for(const key of ['countries','cities']) {
  assert.ok(resourceKeys.includes(key));
  assert.equal(can(ordinary,key,'read'),false);
  assert.equal(can({...ordinary,permissions:[`${key}.read`]},key,'read'),true);
  assert.equal(can({...ordinary,permissions:[`${key==='countries'?'cities':'countries'}.read`]},key,'read'),false);
  assert.equal(can({isSuperAdmin:true,tenantId:null,permissions:[]},key,'read'),true);
  for(const action of ['create','update','delete']) {
   assert.equal(can({...ordinary,permissions:[`${key}.${action}`]},key,action),false);
   assert.equal(can({isSuperAdmin:true,tenantId:null,permissions:[]},key,action),true);
   assert.equal(can({...ordinary,isSuperAdmin:true},key,action),false);
  }
 }
 assert.equal(can(ordinary,'tenants','read'),false);
 assert.equal(can({...ordinary,permissions:['users.update']},'users','update',{id:'global',tenant_id:null}),false);
 assert.ok(!navigationSections.some(section=>section.keys.some(key=>['countries','cities'].includes(key))));
});
test('country codes canonicalize without numeric conversion of postal codes; city labels disambiguate CAP',()=>{
 assert.deepEqual(normalizeValues([{name:'iso_code',type:'text',required:true},{name:'postal_code',type:'text',required:true}],{iso_code:'it',postal_code:'00100'}),{iso_code:'IT',postal_code:'00100'});
 assert.equal(rowLabel({id:'city',name:'Roma',country_id:'IT',postal_code:'00100',province:'RM'}),'Roma · 00100 · RM');
});
