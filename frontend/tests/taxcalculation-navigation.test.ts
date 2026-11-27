import test from 'node:test';
import assert from 'node:assert/strict';
import {can, groupPermissions, navigationPath, resourceKeys, taxResources, taxRoutes} from '../lib/model.ts';

const admin = {isSuperAdmin: true, tenantId: null, permissions: []};

test('Tax Calculation is a finite permission resource inside the existing simulator, not another workspace', () => {
  assert.ok(resourceKeys.includes('tax-calculation'));
  assert.ok(!taxResources.includes('tax-calculation'));
  assert.ok(!taxRoutes.includes('tax-calculation'));
  assert.deepEqual(navigationPath('tax-calculation'), ['settings', 'settings-master-data', 'tax-management', 'tax-determination', 'tax-calculation']);
});

test('Tax Calculation grants only read, simulate and calculate, with no implicit determination authority', () => {
  for (const action of ['read', 'simulate', 'calculate']) assert.equal(can(admin, 'tax-calculation', action), true);
  for (const action of ['create', 'update', 'delete', 'determine', 'write']) assert.equal(can(admin, 'tax-calculation', action), false);
  const operator = {isSuperAdmin: false, tenantId: 'tenant', permissions: ['tax-calculation.read']};
  assert.equal(can(operator, 'tax-calculation', 'read'), true);
  assert.equal(can(operator, 'tax-calculation', 'simulate'), false);
  assert.equal(can(operator, 'tax-determination', 'read'), false);
});

test('Tax Calculation permission tree retains the complete simulator hierarchy', () => {
  const rows = [{id: 'calculation-read', code: 'tax-calculation.read', is_system: true, is_enabled: true}];
  const domains = groupPermissions(rows);
  const leaves: string[] = [];
  function visit(branch: {key: string; children: unknown[]}) {
    leaves.push(branch.key);
    for (const child of branch.children) visit(child as typeof branch);
  }
  for (const domain of domains) for (const branch of domain.resources) visit(branch);
  assert.ok(leaves.includes('tax-determination'));
  assert.ok(leaves.includes('tax-calculation'));
});
