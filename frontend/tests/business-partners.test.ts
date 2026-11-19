import test from 'node:test';
import assert from 'node:assert/strict';
import {can, groupPermissions, navigationSections} from '../lib/model.ts';
import {harness,find,session} from './workspace-harness.ts';
import {readFileSync} from 'node:fs';
import {countryCodes} from '../lib/country-codes.ts';
const resources=[{key:'settings',fields:[]},{key:'business-partners',fields:[]}];
test('BP navigation and exact action allowlists do not infer delete or numbering create',()=>{
 assert.ok(navigationSections.find(s=>s.label==='masterData')?.keys.includes('business-partners'));
 for(const action of ['read','create','update']) assert.equal(can({...session,permissions:[`business-partners.${action}`]},'business-partners',action),true);
 for(const resource of ['business-partners','business-partner-numbering']) assert.equal(can({...session,isSuperAdmin:true,tenantId:null},resource,'delete'),false);
 assert.equal(can({...session,permissions:['business-partner-numbering.read']},'business-partner-numbering','read'),true);
 assert.equal(can({...session,isSuperAdmin:true,tenantId:null},'business-partner-numbering','create'),false);
 assert.equal(groupPermissions([{id:'n',code:'business-partner-numbering.read'}])[0].key,'administration');
});
for(const locale of ['it','en']) test(`numbering is absent from Settings and has no separate sidebar entry (${locale})`,()=>{
 const h=harness(locale,{0:{...session,permissions:['business-partners.read','business-partner-numbering.read']},1:false,5:resources,6:'settings',7:'t'});
 const html=h.render('default');
 assert.doesNotMatch(html,locale==='it'?/Numerazione Business Partner/:/Business Partner numbering/);
 assert.doesNotMatch(html.match(/<nav[\s\S]*?<\/nav>/)?.[0]||'',/Numerazione|numbering/);
});
test('settings.read alone never exposes BP numbering',()=>{
 const h=harness('en',{0:{...session,permissions:['settings.read']},1:false,5:resources,6:'settings',7:'t'});
 assert.doesNotMatch(h.render('default'),/Business Partner numbering/);
});
test('BP main page uses dedicated list labels and search',()=>{
 const h=harness('en',{0:{...session,permissions:['business-partners.read','business-partners.create','business-partners.update']},1:false,5:resources,6:'business-partners',7:'t'});
 const html=h.render('default');
 assert.match(html,/New Business Partner/);
 assert.match(html,/Search code, name, tax ID or contact/);
});
test('clicking the active Business Partner menu entry resets its workspace',()=>{
 const states={0:{...session,permissions:['business-partners.read']},1:false,5:resources,6:'business-partners',7:'t'};
 const h=harness('en',states), tree=h.components.default();
 const navigation=find(tree,n=>n.type?.name==='WorkspaceNavigation');
 const before=find(tree,n=>n.type?.name==='BusinessPartnerWorkspace');
 const entry=find(navigation.type(navigation.props),n=>n.props?.['aria-current']==='page');
 assert.ok(entry);entry.props.onClick();
 const reset=Object.values(h.updates).find(value=>typeof value==='function') as ((current:number)=>number)|undefined;
 assert.ok(reset,'menu click triggers workspace reset');
 const afterHarness=harness('en',{...states,23:reset(0)});
 const after=find(afterHarness.components.default(),n=>n.type?.name==='BusinessPartnerWorkspace');
 assert.notEqual(after.key,before.key,'reset remounts the workspace');
});
test('BP numbering page has its parent breadcrumb and back action without resource metadata',()=>{
 const h=harness('en',{0:{...session,permissions:['business-partner-numbering.read','business-partner-numbering.update']},1:false,5:resources,6:'business-partner-numbering',7:'t'});
 const html=h.render('default');
 assert.match(html,/Back to Business Partner/);
 assert.doesNotMatch(html,/Back to settings/);
 assert.match(html,/<h1>Numbering<\/h1>/);
 assert.match(html,/Master data[\s\S]*Business Partner/);
 assert.match(html,/Numbering applies only to Business Partners/);
});
test('resource refresh preserves the permitted virtual numbering page without metadata',async()=>{
 const operator={...session,permissions:['business-partner-numbering.read']};
 const h=harness('en',{0:operator,1:false,5:resources,6:'business-partner-numbering',7:'t'},(path:string)=>path==='/session'?operator:path==='/resources'?resources:{items:[],total:0});
 h.components.default();h.effects[2]();await new Promise(resolve=>setImmediate(resolve));
 assert.deepEqual(h.apiCalls,['/resources']);
 assert.equal((h.updates[6] as (current:string)=>string)('business-partner-numbering'),'business-partner-numbering');
});

test('local ISO country choices are complete without depending on test fixtures at runtime',()=>{
 const expected=JSON.parse(readFileSync(new URL('./country-codes.json',import.meta.url),'utf8'));
 assert.deepEqual([...countryCodes].sort(),expected.sort());assert.equal(new Set(countryCodes).size,countryCodes.length);
});
