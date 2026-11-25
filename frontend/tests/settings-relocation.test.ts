import test from 'node:test';
import assert from 'node:assert/strict';
import {navigationPath, groupPermissions} from '../lib/model.ts';
import {catalogHarness, catalogSession, findCatalog} from './catalog-harness.ts';

test('settings destinations and permission branches use their new parents',()=>{
 for(const key of ['countries','cities']) assert.deepEqual(navigationPath(key),['settings','settings-system',key]);
 assert.deepEqual(navigationPath('catalog-units'),['settings','settings-system','catalog-units']);
 const domains=groupPermissions([{id:'u',code:'catalog-units.read'}]);
 assert.equal(domains[0].resources[0].key,'settings');
 assert.equal(domains[0].resources[0].children[0].key,'settings-system');
 assert.equal(domains[0].resources[0].children[0].children[0].key,'catalog-units');
});
test('unit-only reader can traverse system without unrelated grants',()=>{
 const w=catalogHarness().workspace({}); const s={...catalogSession,isSuperAdmin:false,tenantId:'t',permissions:['catalog-units.read']};
 assert.equal(w.canOpenResource(s,'settings-system'),true);
 assert.equal(w.canOpenResource(s,'settings-catalog'),false);
 assert.equal(w.canOpenResource(s,'settings-master-data'),false);
 assert.equal(w.canOpenResource(s,'catalog-units'),true);
});
test('settings system shows geography and units, master data excludes units',()=>{
 const h=catalogHarness(); const resources=[{key:'settings',fields:[]},{key:'countries',fields:[]},{key:'cities',fields:[]}];
 const text=(n:any):string=>typeof n==='string'?n:n?.props?[n.props.children].flat(Infinity).map(text).join(' '):'';
 const system=h.workspace({0:{...catalogSession,permissions:[...catalogSession.permissions,'countries.read','cities.read']},1:false,5:resources,6:'settings-system',7:'t'}).default();
 assert.match(text(system),/Nazioni/); assert.match(text(system),/Città/);
 const master=h.workspace({0:catalogSession,1:false,5:resources,6:'settings-master-data',7:'t'}).default();
 assert.match(text(system),/Unità di misura/); assert.doesNotMatch(text(master),/Unità di misura/);
});
