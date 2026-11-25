import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, session, find} from './workspace-harness.ts';
const resources=[{key:'settings',fields:[]},{key:'currencies',fields:[{name:'code',type:'text',required:true}]}];
for (const locale of ['it','en']) test(`global currency navigation has both parent screens (${locale})`,()=>{
 const labels=locale==='it'?['Sistema','Valute']:['System','Currencies'];
 for(const [index,active] of ['settings','settings-system'].entries()) {
  const h=harness(locale,{0:{...session,isSuperAdmin:true,tenantId:null},1:false,5:resources,6:active,7:''});
  const button=find(h.components.default(), n=>typeof n.props?.onClick==='function' && !!find(n,c=>c.type==='h2' && c.props?.children===labels[index]));
  assert.ok(button);button.props.onClick();assert.equal(h.updates[6],index?'currencies':'settings-system');
 }
 const h=harness(locale,{0:{...session,isSuperAdmin:true,tenantId:null},1:false,5:resources,6:'currencies',7:''});
 const html=h.render('default');assert.match(html,locale==='it'?/Impostazioni[\s\S]*Sistema[\s\S]*Valute/:/Settings[\s\S]*System[\s\S]*Currencies/);
 const back=harness(locale,{0:{...session,isSuperAdmin:true,tenantId:null},1:false,5:resources,6:'currencies',7:''});
 const button=find(back.components.default(),n=>n.props?.children===(locale==='it'?'Torna a Sistema':'Back to System'));assert.ok(button);button.props.onClick();assert.equal(back.updates[6],'settings-system');
});
