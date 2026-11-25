import test from 'node:test';
import assert from 'node:assert/strict';
import {navigationPath, can, groupPermissions} from '../lib/model.ts';
test('catalog uses the complete shared hierarchy, without landing authority', () => {
  assert.deepEqual(navigationPath('catalog-categories'), ['catalog', 'catalog-categories']);
  assert.deepEqual(navigationPath('catalog-units'), ['settings','settings-system','catalog-units']);
  assert.deepEqual(navigationPath('catalog-numbering'), ['settings','settings-master-data','settings-catalog','catalog-numbering']);
  assert.deepEqual(navigationPath('business-partner-numbering'), ['settings','settings-master-data','settings-business-partners','business-partner-numbering']);
  const global = {isSuperAdmin:true,tenantId:null,permissions:[]};
  assert.equal(can(global,'catalog','read'),false);
  assert.equal(can(global,'catalog-units','delete'),false);
  assert.equal(can(global,'catalog-types','delete'),true);
  assert.equal(can({isSuperAdmin:false,permissions:['catalog-types.read','catalog-types.update']},'catalog-types','delete'),false);
  assert.equal(can({isSuperAdmin:false,permissions:['catalog-types.read','catalog-types.delete']},'catalog-types','delete'),true);
  assert.equal(can(global,'catalog-categories','delete'),true);
  assert.equal(can(global,'catalog-numbering','create'),false);
  const tree = groupPermissions([{id:'p',code:'catalog-units.update'}]);
  assert.equal(tree[0].resources[0].children[0].children[0].key,'catalog-units');
});
