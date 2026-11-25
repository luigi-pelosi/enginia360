import test from 'node:test';
import assert from 'node:assert/strict';
import {can, groupPermissions, permissionRows, resourceKeys, navigationPath} from '../lib/model.ts';
import {harness, session, find} from './workspace-harness.ts';
const obsolete = ['read','create','update','delete'].map(action => ({id:`settings.${action}`,code:`settings.${action}`}));
for (const isSuperAdmin of [false,true]) test(`removed settings CRUD denied including legacy grants (root=${isSuperAdmin})`,()=>{
 const operator={...session,isSuperAdmin,tenantId:isSuperAdmin?null:'t',permissions:obsolete.map(row=>row.code)};
 assert.equal(resourceKeys.includes('settings'),false);
 for(const action of ['read','create','update','delete']) assert.equal(can(operator,'settings',action),false,action);
});
for(const locale of ['it','en']) for(const isSuperAdmin of [false,true]) test(`local settings navigation without metadata or grants (${locale}, root=${isSuperAdmin})`,async()=>{
 const operator={...session,isSuperAdmin,tenantId:isSuperAdmin?null:'t',permissions:[]};
 const h=harness(locale,{0:operator,1:false,5:[],6:'settings',7:isSuperAdmin?'':'t'},(path:string)=>path==='/resources'?[]:path==='/session'?operator:{items:[],total:0});
 const component=h.components.default();
 const navigation=find(component,n=>n.type?.name==='WorkspaceNavigation');
 assert.equal(navigation.props.accessible.filter((route:{key:string})=>route.key==='settings').length,isSuperAdmin?1:0);
 if(!isSuperAdmin) {
  assert.equal(find(navigation.type(navigation.props),n=>n.props?.['aria-current']==='page'),undefined);
  h.effects[3](); h.effects[5](); await new Promise(resolve=>setImmediate(resolve));
  assert.equal((h.updates[6] as (current:string)=>string)('settings'),'','zero grants must not fall back to Settings');
  assert.equal(h.apiCalls.some(path=>/\/data\/settings(?:[/?]|$)/.test(path)),false);
  return;
 }
 const menu=navigation.type(navigation.props);
 const entry=find(menu,n=>typeof n.props?.onClick==='function' && Boolean(find(n,c=>c.type==='span' && c.props?.children===(locale==='it'?'Impostazioni':'Settings'))));
 assert.ok(entry,'Settings sidebar entry exists without resource metadata');
 assert.equal(entry.props['aria-current'],'page');entry.props.onClick();assert.equal(h.updates[6],'settings');
 const html=harness(locale,{0:operator,1:false,5:[],6:'settings',7:isSuperAdmin?'':'t'}).render('default');
 assert.match(html,locale==='it'?/aria-label="Impostazioni"/:/aria-label="Settings"/);
 assert.match(html,locale==='it'?/<h1>Impostazioni<\/h1>/:/<h1>Settings<\/h1>/);
 if(isSuperAdmin) assert.match(html,locale==='it'?/>Sistema<\/h2>/:/>System<\/h2>/);
 else assert.doesNotMatch(html,/>System<\/h2>|>Sistema<\/h2>/);
 h.effects[3](); h.effects[5](); await new Promise(resolve=>setImmediate(resolve));
 assert.equal((h.updates[6] as unknown as (current:string)=>string)('settings'),'settings');
 const metadata=h.updates[5] as {key:string}[];
 assert.equal(metadata.some(item=>item.key==='settings'),false,'local shell is not backend metadata');
 assert.equal(h.apiCalls.some(path=>/\/data\/settings(?:[/?]|$)/.test(path)),false);
});
for(const child of ['countries','cities','currencies','catalog-units','business-partner-numbering','catalog-numbering']) test(`only ${child}.read opens its own Settings ancestors`,async()=>{
 const operator={...session,permissions:[`${child}.read`]};
 const resources=[{key:child,fields:[]}];
 const h=harness('en',{0:operator,1:false,5:resources,6:'settings',7:'t'},(path:string)=>path==='/resources'?resources:{items:[],total:0});
 const tree=h.components.default();const navigation=find(tree,n=>n.type?.name==='WorkspaceNavigation');
 assert.ok(navigation.props.accessible.some((route:{key:string})=>route.key==='settings'));
 for(const ancestor of navigationPath(child)) {
  navigation.props.navigate(ancestor);assert.equal(h.updates[6],ancestor,ancestor);
 }
 for(const denied of ['settings-system','settings-master-data','settings-business-partners','settings-catalog','catalog','payments','companies']) {
  if(navigationPath(child).includes(denied)) continue;
  h.updates[6]=undefined;navigation.props.navigate(denied);assert.equal(h.updates[6],undefined,denied);
 }
 h.effects[3]();await new Promise(resolve=>setImmediate(resolve));
 assert.equal((h.updates[6] as (current:string)=>string)('settings'),'settings','metadata refresh keeps authorized shell');
 for(const action of ['read','create','update','delete']) assert.equal(can(operator,'settings',action),false);
 assert.equal(can(operator,child,'update'),false);
 assert.equal(h.apiCalls.some(path=>path.startsWith('/data/')),false);
});
for(const permissions of [[],['settings.read'],['countries.create'],['catalog-units.update'],['business-partner-numbering.update'],['catalog-numbering.update'],['companies.read'],['business-partners.read'],['catalog-items.read'],['payment-settings.read']]) test(`no readable Settings descendant means no menu (${permissions.join(',')||'zero grants'})`,()=>{
 const h=harness('en',{0:{...session,permissions},1:false,5:resourceKeys.map(key=>({key,fields:[]})),6:'settings',7:'t'});
 const tree=h.components.default();const navigation=find(tree,n=>n.type?.name==='WorkspaceNavigation');
 assert.equal(navigation.props.accessible.some((route:{key:string})=>route.key==='settings'),false);
 navigation.props.navigate('settings');assert.equal(h.updates[6],undefined);
});
test('non-menu payment capabilities do not open an empty Payments workspace',()=>{
 const h=harness('en',{0:{...session,permissions:['payment-resolution.read','payment-partner-defaults.read']},1:false,5:[{key:'payments',fields:[]}],6:'payments',7:'t'});
 const tree=h.components.default();const navigation=find(tree,n=>n.type?.name==='WorkspaceNavigation');
 assert.equal(navigation.props.accessible.some((route:{key:string})=>route.key==='payments'),false);
});
test('denied Settings renders the neutral no-access state, never an empty shell',()=>{
 const h=harness('en',{0:{...session,permissions:['settings.read']},1:false,5:[],6:'settings',7:'t'});
 const html=h.render('default');
 assert.match(html,/<h1>No resources available<\/h1>/);
 assert.doesNotMatch(html,/aria-label="Settings"|<h1>Settings<\/h1>/);
});
test('settings tree drops only obsolete CRUD and preserves numbering descendants and filtered bulk count',()=>{
 const live=['business-partner-numbering.read','business-partner-numbering.update','catalog-numbering.read','catalog-numbering.update','payment-settings.read'].map(code=>({id:code,code}));
 const rows=[...obsolete,...live];
 const tree=groupPermissions(rows);
 assert.deepEqual(tree.flatMap(domain=>domain.resources.flatMap(permissionRows)).map(row=>row.id).sort(),live.map(row=>row.id).sort());
 let changed:string[]=[];
 const h=harness();
 const props={rows,query:'business-partner-numbering.read',selectedIds:[],onSelectedIdsChange:(ids:string[])=>{changed=ids;},renderLeaf:()=>null};
 const component=h.components.PermissionTree(props);
 const branch=find(component,n=>n.props?.['data-permission-resource']==='settings');assert.ok(branch);
 const bulk=find(branch,n=>n.props?.['data-permission-resource-checkbox']==='settings');bulk.props.onCheckedChange(true);
 assert.deepEqual([...changed].sort(),live.filter(row=>!row.code.startsWith('payment-settings.')).map(row=>row.id).sort());
 const html=h.render('PermissionTree',props);assert.match(html,/0\/4/);assert.doesNotMatch(html,/data-permission-code="settings\./);
});
