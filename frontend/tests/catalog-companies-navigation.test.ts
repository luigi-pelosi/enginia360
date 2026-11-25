import test from 'node:test';
import assert from 'node:assert/strict';
import {can,navigationPath,groupPermissions,catalogRoutes} from '../lib/model.ts';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';
test('company-only user traverses Catalog and reaches its independent company catalog workspace',()=>{
 const session={...catalogSession,permissions:['catalog-item-companies.read']};const h=catalogHarness();const resources=catalogRoutes.map(key=>({key,fields:[]}));const w=h.workspace({0:session,1:false,5:resources,6:'catalog-items',7:'t'});
 assert.equal(w.canOpenResource(session,'catalog'),true);assert.equal(w.canOpenResource(session,'catalog-item-companies'),true);assert.equal(w.canOpenResource(session,'catalog-items'),true);assert.equal(w.canOpenResource(session,'companies'),false);
 const tree=w.default();assert.ok(findCatalog(tree,n=>n.props?.session===session&&n.props?.tenantId==='t'&&typeof n.type==='function'),'dedicated lazy workspace, not generic data CRUD');
});
test('company-only catalog reader has a finite independent resource in the catalog permission tree',()=>{
 const session={isSuperAdmin:false,tenantId:'tenant',permissions:['catalog-item-companies.read']};
 assert.equal(can(session,'catalog-item-companies','read'),true);
 assert.equal(can(session,'catalog-items','read'),false);
 assert.equal(can({...session,isSuperAdmin:true,tenantId:null},'catalog-item-companies','delete'),false);
 assert.deepEqual(navigationPath('catalog-item-companies'),['catalog','catalog-items','catalog-item-companies']);
 const tree=groupPermissions([{id:'read',code:'catalog-item-companies.read'}]);
 assert.equal(tree[0].resources[0].key,'catalog');
 assert.equal(tree[0].resources[0].children[0].key,'catalog-items');
 assert.equal(tree[0].resources[0].children[0].children[0].key,'catalog-item-companies');
});
