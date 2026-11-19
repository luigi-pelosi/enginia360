import test from 'node:test';
import assert from 'node:assert/strict';
import {can,groupPermissions,navigationPath,permissionLabel} from '../lib/model.ts';
import {readFileSync} from 'node:fs';
import {session} from './workspace-harness.ts';
test('finite company partner authorities and company assignment are recognized without delete or umbrella grants',()=>{
 for(const action of ['read','create','update','use_customer','use_supplier'])assert.equal(can({...session,permissions:[`business-partner-companies.${action}`]},'business-partner-companies',action),true);
 assert.equal(can({...session,permissions:['roles.assign_companies']},'roles','assign_companies'),true);
 for(const action of ['delete','assign','use','anything'])assert.equal(can({...session,isSuperAdmin:true,tenantId:null},'business-partner-companies',action),false);
 assert.equal(can({...session,permissions:['roles.update']},'roles','assign_companies'),false);
});
test('company partner permissions belong to operational Master data > Business Partner and localize in both languages',()=>{
 assert.deepEqual(navigationPath('business-partner-companies'),['business-partners','business-partner-companies']);
 const row={id:'p',code:'business-partner-companies.use_customer'};
 const tree=groupPermissions([row]);assert.equal(tree[0].key,'masterData');assert.equal(tree[0].resources[0].children[0].key,'business-partner-companies');
 for(const locale of ['it','en']){const messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));assert.doesNotMatch(permissionLabel(row,messages),/undefined|use_customer|business-partner-companies/);assert.ok(messages.permissionActions.assign_companies);}
});
