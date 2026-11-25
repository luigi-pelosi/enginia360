import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, find} from './workspace-harness.ts';
import {catalog} from './permission-catalog.ts';

for (const locale of ['it', 'en']) test(`permission hierarchy follows Settings routes in catalog and role selector (${locale})`, () => {
 const h=harness(locale);
 const props={rows:catalog,query:'business-partner-numbering',renderLeaf:()=>null};
 for (const selectedIds of [undefined,['business-partner-numbering.read']]) {
  const tree=h.components.PermissionTree({...props,selectedIds,onSelectedIdsChange:()=>{}});
  let branch=find(tree,n=>n.props?.['data-permission-domain']==='administration');
  assert.ok(branch);
  for (const key of ['settings','settings-master-data','settings-business-partners','business-partner-numbering']) {
   branch=find(branch,n=>n.props?.['data-permission-resource']===key);
   assert.ok(branch,`missing route branch ${key}`);
  }
  assert.equal(find(tree,n=>n.props?.['data-permission-domain']==='masterData'),undefined);
 }
});

test('Settings bulk selects original descendant permissions even while filtering',()=>{
 let changed:string[]=[];
 const tree=harness().components.PermissionTree({rows:catalog,query:'business-partner-numbering.read',selectedIds:['outside'],renderLeaf:()=>null,onSelectedIdsChange:(ids:string[])=>{changed=ids}});
 const control=find(tree,n=>n.props?.['data-permission-resource-checkbox']==='settings');
 assert.ok(control);
 control.props.onCheckedChange(true);
 assert.deepEqual([...changed].sort(),['outside',...catalog.filter(row=>row.code.startsWith('business-partner-numbering.')||['countries.read','cities.read','currencies.read'].includes(row.code)).map(row=>row.id)].sort());
});
