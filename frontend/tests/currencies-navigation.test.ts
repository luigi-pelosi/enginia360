import test from 'node:test';
import assert from 'node:assert/strict';
import {can, navigationPath} from '../lib/model.ts';

test('currency catalog belongs to Settings → System and requires an explicit ordinary read grant', () => {
  assert.deepEqual(navigationPath('currencies'), ['settings', 'settings-system', 'currencies']);
  const user = {isSuperAdmin:false, tenantId:'tenant', permissions:['currencies.read']};
  assert.equal(can(user, 'currencies', 'read'), true);
  assert.equal(can(user, 'currencies', 'update'), false);
  assert.equal(can({isSuperAdmin:true, tenantId:null, permissions:[]}, 'currencies', 'delete'), true);
});
