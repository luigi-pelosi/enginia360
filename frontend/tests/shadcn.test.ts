import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {harness, session, find} from './workspace-harness.ts';
const read=(p:string)=>readFileSync(new URL('../'+p,import.meta.url),'utf8');
for (const [label, expected] of [
 ['edit/details label', '!resource.readOnly && can(session, active, "update", row) ? t("edit") : t("details")'],
 ['reset password', 'can(session, "users", "reset_password", row) && ('],
 ['delete', 'can(session, active, "delete", row) && ('],
 ['detail form', 'canWrite={!editor.resource.readOnly && can(session, editor.resource.key, editor.row ? "update" : "create", editor.row)}'],
]) {
 test(`user row-aware permissions reach ${label}`, () => {
  assert.ok(read('components/workspace.tsx').includes(expected), expected);
 });
}
test('read-only detail fields stay disabled and no Save appears', () => {
 const html = harness().render('RecordEditor', {resource: {key: 'users', fields: []}, row: {id: 'u', tenant_id: 't'}, session, canWrite: false, scope: (p:string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onError: () => 'error'});
 assert.match(html, /fieldset disabled/);
 assert.doesNotMatch(html, />Salva</);
});
test('global user detail does not load tenant user-role relations', async () => {
 const h = harness();
 h.components.RecordEditor({resource: {key: 'users', fields: []}, row: {id: 'u', tenant_id: null}, session: {...session, isSuperAdmin: true, tenantId: null}, canWrite: false, scope: (p:string) => p, load: async () => {throw Error('unexpected target load')}, onClose() {}, onSaved: async () => {}, onError: () => 'error'});
 h.effects[0]();
 await new Promise(resolve => setTimeout(resolve, 0));
 assert.deepEqual(h.apiCalls, []);
 assert.deepEqual(Object.keys(h.updates[5] as object), []);
});
test('relation choices exclude global users while preserving the full Users list', async () => {
 const options = [{id:'global',tenant_id:null},{id:'tenant',tenant_id:'t'}];
 const h = harness('it', {}, {ids: []});
 h.components.RecordEditor({resource: {key:'groups', fields:[]}, row:{id:'g',tenant_id:'t'}, session:{...session,permissions:['groups.read','users.read','groups.assign_users']}, canWrite:false, scope:(p:string)=>p, load:async()=>options,onClose(){},onSaved:async()=>{},onError:()=> 'error'});
 h.effects[0](); await new Promise(resolve=>setTimeout(resolve,0));
 assert.deepEqual(JSON.parse(JSON.stringify((h.updates[5] as Record<string, {options: unknown[]}>)['group-users'].options)), [options[1]]);
 assert.equal(options.length,2);
});
test('official New York primitives retain registry config and approved logo palette',()=>{
 assert.ok(existsSync(new URL('../components.json',import.meta.url)), 'official components.json required');
 const config=JSON.parse(read('components.json')); assert.equal(config.style,'new-york'); assert.equal(config.tailwind.baseColor,'neutral');
 const css=read('app/globals.css');
 for(const token of ['--primary: #0b1f43;', '--accent-foreground: #075fe8;', '--chart-4: #09a9e0;', '--background: #08152c;']) assert.ok(css.includes(token),token);
 assert.doesNotMatch(css,/#17675e|#102a36|!important/);
 const workspace=read('components/workspace.tsx');
 for(const component of ['SidebarProvider','SidebarTrigger','TableHeader','TableCell','SelectTrigger','Checkbox','Label','Card','AlertDialogContent']) assert.ok(workspace.includes(component),component);
 assert.doesNotMatch(workspace,/<select\b|<table\b|type="checkbox"/);
});
test('required Radix references cannot submit empty and optional sentinel never serializes',()=>{
 const source=read('components/workspace.tsx');
 assert.match(source,/const missingRequired = resource\.fields\.some/);
 const h = harness('it');
 const tree = h.components.RecordEditor({resource:{key:'sites',fields:[{name:'company_id',type:'reference',required:true}]},row:null,canWrite:true,session,scope:(p:string)=>p,load:async()=>[],onClose(){},onSaved:async()=>{},onError:()=> 'error'});
 assert.equal(find(tree,n=>n.props?.form==='record-form').props.disabled,true);
 assert.match(source,/canWrite && \(refsLoading \|\| missingRequired \|\| refsFailed\)/);
 assert.match(source,/selected === "__none__" \? "" : selected/);
 assert.match(source,/!field\.required && <SelectItem value="__none__">/);
});
test('metadata user controls preserve date/tel types, default language and official Select', () => {
 const source=read('components/workspace.tsx');
 assert.match(source,/field\.type === "date" \|\| field\.type === "tel" \? field\.type/);
 assert.match(source,/field\.type === "select"/);
 assert.match(source,/\(field\.options \?\? \[\]\)\.map/);
 assert.match(source,/languages\(option\)/);
 assert.match(source,/field\.defaultValue \?\? ""/);
 assert.match(source,/required=\{field\.required\}/);
 assert.match(source,/field\.required && <span aria-hidden="true"> \*<\/span>/);
 assert.doesNotMatch(source,/display_name/);
 const select=source.slice(source.indexOf(') : field.type === "select" ? ('),source.indexOf(') : field.type === "reference" ? ('));
 for(const token of ['<Select','name={field.name}','required={field.required}','disabled={!canWrite || busy}','<SelectTrigger id={id}','<SelectContent>','<SelectItem']) assert.ok(select.includes(token),token);
});
test('CRUD, exact RBAC, all four relation editors and settings chain preserved',()=>{
 const source=read('components/workspace.tsx');
 const contract = source + read('lib/model.ts');
 for(const key of ['tenants','companies','sites','warehouse-types','warehouses','warehouse-locations','settings','users','groups','roles','permissions','user-roles','group-users','group-roles','role-permissions']) assert.ok(contract.includes('"'+key+'"'),key);
 for(const behavior of ['normalizeValues(resource.fields, values)','can(session, active, "create")','can(session, active, "delete", row)','canRelation(session, resource.key, relation.key, "read", owner)','company_id: value','site_id: ""','company_id: site.company_id','await refreshCsrf()','drafts[relation.key].ids','currentPassword: current']) assert.ok(source.includes(behavior),behavior);
});
