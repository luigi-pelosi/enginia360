import test from 'node:test';
import assert from 'node:assert/strict';
import {can, groupPermissions, permissionRows, permissionLabel} from '../lib/model.ts';
import {readFileSync} from 'node:fs';
import {harness,session,find} from './workspace-harness.ts';
const catalogs=['countries','cities','currencies','catalog-units'];
const resources=catalogs.map(key=>({key,fields:[],readOnly:true}));
function tiles(permissions:string[]) {
 const h=harness('en',{0:{...session,permissions},1:false,5:resources,6:'settings-system',7:'t'});
 const tree=h.components.default();
 const grid=find(tree,n=>n.type==='div' && n.props?.className==='grid gap-4 sm:grid-cols-2 xl:grid-cols-3');
 return grid?[grid.props.children].flat(Infinity).filter((node:any)=>node?.type==='button'):[];
}
test('global catalogs require exact ordinary read grants; root maintenance remains intrinsic',()=>{
 for(const key of catalogs.slice(0,3)) {
  assert.equal(can(session,key,'read'),false,key);
  assert.equal(can({...session,permissions:[`${key}.update`]},key,'read'),false,key);
  assert.equal(can({...session,permissions:[`${key}.read`]},key,'read'),true,key);
  assert.equal(can({...session,permissions:[`${key}.read`]},key,'update'),false,key);
  assert.equal(can({...session,isSuperAdmin:true,tenantId:null},key,'read'),true,key);
  assert.equal(can({...session,isSuperAdmin:true,tenantId:null},key,'update'),true,key);
 }
});
test('no catalog grants exposes no System or catalog tiles; one grant exposes exactly its child',()=>{
 assert.equal(tiles([]).length,0);
 for(const key of catalogs) {
  const entries=tiles([`${key}.read`]);assert.equal(entries.length,1,key);
  const h=harness('en',{0:{...session,permissions:[`${key}.read`]},1:false,5:resources,6:'settings',7:'t'});
  assert.ok(find(h.components.default(),n=>n.type==='h2' && n.props?.children==='System'));
 }
 const h=harness('en',{0:session,1:false,5:resources,6:'settings',7:'t'});
 assert.equal(find(h.components.default(),n=>n.type==='h2' && n.props?.children==='System'),undefined);
});
for(const active of ['settings-system',...catalogs]) test(`denied direct route, readonly metadata and saved draft cannot request ${active}`,async()=>{
 const storage=new Map([[`workspace:u:t:record:${active}`,JSON.stringify({kind:'create',values:{name:'obsolete'}})]]);
 const h=harness('en',{0:session,1:false,5:resources,6:active,7:'t',25:true},(path:string)=>path==='/resources'?resources:{items:[],total:0},storage);
 h.components.default();h.effects[3]();h.effects[5]();h.effects[8]();await new Promise(resolve=>setImmediate(resolve));
 assert.equal(h.apiCalls.some(path=>path.includes(`/data/${active}`)),false);
 assert.equal(h.updates[16],undefined);
 assert.equal((h.updates[6] as (current:string)=>string)(active),'','zero grants must not reopen Settings');
});
test('three global read permissions live under Settings → System without manufacturing CRUD grants',()=>{
 const rows=catalogs.map(key=>({id:key,code:`${key}.read`}));
 const settings=groupPermissions(rows)[0].resources[0];assert.equal(settings.key,'settings');assert.equal(settings.rows.length,0);
 const system=settings.children[0];assert.equal(system.key,'settings-system');
 assert.deepEqual(permissionRows(system).map(row=>row.id).sort(),[...catalogs].sort());
});
for(const locale of ['it','en']) test(`global permission labels, search and System container are localized (${locale})`,()=>{
 const rows=catalogs.slice(0,3).map(key=>({id:key,code:`${key}.read`}));
 const messages=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));
 const html=harness(locale).render('PermissionTree',{rows,query:locale==='it'?'Sistema':'System',renderLeaf:(row:any)=>permissionLabel(row,messages)});
 for(const row of rows) assert.ok(html.includes(`${messages.resources[row.id]} · ${messages.permissionActions.read}`));
 assert.match(html,new RegExp(`aria-label="${locale==='it'?'Sistema':'System'}"`));
 assert.match(html,new RegExp(`aria-label="${locale==='it'?'Impostazioni':'Settings'}"`));
 assert.equal((html.match(/data-permission-code=/g)||[]).length,3);
});
for(const active of catalogs) test(`refresh revocation hides ${active} and returns to neutral no-access`,async()=>{
 const operator={...session,permissions:[`${active}.read`]};
 const metadata=resources.map(resource=>({...resource,readOnly:true}));
 // The dedicated unit workspace owns its refresh; simulate the same fresh-session metadata transition below.
 if(active==='catalog-units') {
  const fresh=harness('en',{0:session,1:false,5:metadata,6:'settings-system',7:'t'});
  const grid=find(fresh.components.default(),n=>n.type==='div' && n.props?.className==='grid gap-4 sm:grid-cols-2 xl:grid-cols-3');
  assert.equal(grid,undefined,'revoked System shell is not rendered');
  return;
 }
 const h=harness('en',{0:operator,1:false,5:metadata,6:active,7:'t'},session);
 const refresh=find(h.components.default(),n=>n.props?.['aria-label']==='Refresh');assert.ok(refresh);
 await refresh.props.onClick();assert.equal(h.updates[6],'');assert.equal(h.updates[0],session);
 const fresh=harness('en',{0:session,1:false,5:metadata,6:active,7:'t'});
 fresh.components.default();fresh.effects[5]();assert.equal(fresh.apiCalls.length,0);
});
