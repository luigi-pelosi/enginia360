import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, session, find} from './workspace-harness.ts';
const resources=[{key:'settings',fields:[]},{key:'business-partners',fields:[]}];
const reader={...session,permissions:['business-partner-numbering.read']};
function page(active:string,locale='it',operator=reader) {
 return harness(locale,{0:operator,1:false,5:resources,6:active,7:'t'});
}
function tile(tree:any,label:string):any {
 return find(tree,(node:any)=>typeof node.props?.onClick==='function' && Boolean(find(node,(child:any)=>child.type==='h2' && child.props?.children===label)));
}
for(const locale of ['it','en']) test(`settings contains the complete master data → BP → numbering hierarchy (${locale})`,()=>{
 const labels=locale==='it'?['Anagrafiche','Business Partner','Numerazione']:['Master data','Business Partner','Numbering'];
 const screens=['settings','settings-master-data','settings-business-partners','business-partner-numbering'];
 for(let i=0;i<3;i++) {
  const h=page(screens[i],locale),button=tile(h.components.default(),labels[i]);
  assert.ok(button,`Missing ${labels[i]} under ${screens[i]}`);
  button.props.onClick();assert.equal(h.updates[6],screens[i+1]);
 }
 const h=page(screens[3],locale),html=h.render('default');
 assert.match(html,locale==='it'?/Impostazioni[\s\S]*Anagrafiche[\s\S]*Business Partner/:/Settings[\s\S]*Master data[\s\S]*Business Partner/);
 assert.match(html,new RegExp(`<h1>${labels[2]}</h1>`));
 const backPage=page(screens[3],locale),tree=backPage.components.default();
 const back=find(tree,(n:any)=>n.props?.children===(locale==='it'?'Torna ai Business Partner':'Back to Business Partner'));
 back.props.onClick();assert.equal(backPage.updates[6],'settings-business-partners');
 const nav=html.match(/<nav[\s\S]*?<\/nav>/)?.[0]||'';
 assert.match(nav,/aria-current="page"/);assert.doesNotMatch(nav,/Business Partner/);
});
test('settings intermediates preserve their state on metadata refresh without parent-data access',async()=>{
 for(const active of ['settings-master-data','settings-business-partners','business-partner-numbering']) {
  const h=harness('en',{0:reader,1:false,5:resources,6:active,7:'t'},(path:string)=>path==='/session'?reader:path==='/resources'?resources:{items:[],total:0});
  h.components.default();h.effects[1]();await new Promise(resolve=>setImmediate(resolve));
  assert.equal((h.updates[6] as (current:string)=>string)(active),active);
 }
});
test('operational BP page no longer contains numbering navigation',()=>{
 const operator={...session,permissions:['business-partners.read','business-partner-numbering.read']};
 const h=page('business-partners','it',operator),tree=h.components.default();
 assert.equal(find(tree,(n:any)=>typeof n.props?.onNumbering==='function'),undefined);
 assert.doesNotMatch(h.render('default'),/>Numerazione<\/button>/);
});
test('settings.read and BP read do not expose numbering configuration',()=>{
 const h=page('settings','it',{...session,permissions:['settings.read','business-partners.read']});
 assert.equal(tile(h.components.default(),'Anagrafiche'),undefined);
});
