import test from 'node:test';
import assert from 'node:assert/strict';
import {can,groupPermissions,navigationPath,taxResources,resourceKeys} from '../lib/model.ts';

const global={isSuperAdmin:true,tenantId:null,permissions:[]};
test('regimi fiscali: percorso TaxManagement e catalogo di sola consultazione',()=>{
 assert.ok(taxResources.includes('tax-regimes'));
 assert.deepEqual(navigationPath('tax-regimes'),['settings','settings-master-data','tax-management','tax-regimes']);
 assert.equal(can(global,'tax-regimes','read'),true);
 for(const action of ['create','update','delete','assign','activate'])assert.equal(can(global,'tax-regimes',action),false,action);
 const reader={isSuperAdmin:false,tenantId:'t',permissions:['tax-regimes.read']};
 assert.equal(can(reader,'tax-regimes','read'),true);
 for(const resource of ['tax-codes','tax-types','tax-item-classifications','companies','company-tax-configurations'])assert.equal(can(reader,resource,'read'),false,resource);
});
test('configurazione fiscale: autorizzazioni finite sotto Aziende, non un nuovo menu CRUD',()=>{
 const resource='company-tax-configurations';
 assert.ok(resourceKeys.includes(resource));assert.equal(taxResources.includes(resource),false);
 assert.deepEqual(navigationPath(resource),['companies',resource]);
 for(const action of ['read','create','update','activate','suspend','register','close','assign_regime','schedule_regime'])assert.equal(can(global,resource,action),true,action);
 for(const action of ['delete','assign','schedule','register_extra'])assert.equal(can(global,resource,action),false,action);
 const reader={isSuperAdmin:false,tenantId:'t',permissions:[resource+'.read']};
 assert.equal(can(reader,resource,'read'),true);assert.equal(can(reader,resource,'register'),false);assert.equal(can(reader,'companies','read'),false);
 const groups=groupPermissions([{id:'read',code:resource+'.read'}]);
 const organization=groups.find(group=>group.key==='organization');
 assert.equal(organization?.resources.find(branch=>branch.key==='companies')?.children[0]?.key,resource);
});
