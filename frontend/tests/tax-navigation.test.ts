import test from 'node:test';
import assert from 'node:assert/strict';
import {can, navigationPath, groupPermissions} from '../lib/model.ts';

test('tax resources follow settings master data and grant only the nine finite operations', () => {
  assert.deepEqual(navigationPath('tax-codes'), ['settings','settings-master-data','tax-management','tax-codes']);
  const global = {isSuperAdmin:true,tenantId:null,permissions:[]};
  for (const action of ['read','create','update','schedule','deactivate','reactivate','install_templates']) assert.equal(can(global,'tax-codes',action),true,action);
  for (const action of ['delete','activate','preview']) assert.equal(can(global,'tax-codes',action),false,action);
  for (const resource of ['tax-types','tax-nature-codes']) {
    assert.equal(can(global,resource,'read'),true);
    for (const action of ['create','update','delete','schedule']) assert.equal(can(global,resource,action),false);
  }
  assert.equal(can(global,'tax-management','read'),false);
  assert.equal(can({isSuperAdmin:false,permissions:['tax-codes.read']},'tax-codes','schedule'),false);
  const tree=groupPermissions([{id:'p',code:'tax-nature-codes.read'}]);
  assert.equal(tree[0].resources[0].children[0].children[0].key,'tax-management');
});
