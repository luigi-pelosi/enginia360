import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';
import * as model from '../lib/model.ts';

test('tax navigation mounts a bounded workspace instead of generic CRUD',()=>{
  const source=readFileSync(new URL('../components/workspace.tsx',import.meta.url),'utf8');
  assert.match(source,/import \{ TaxManagement/);
  assert.match(source,/<TaxManagement/);
  assert.match(source,/resetTaxRecovery/);
});
test('each tax-only reader can traverse Settings without gaining generic CRUD or sidebar entries',()=>{
 const source=readFileSync(new URL('../components/workspace.tsx',import.meta.url),'utf8');
 const require=createRequire(import.meta.url),module={exports:{} as any};
 const code=ts.transpileModule(source+'\nexport {canOpenResource};',{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
 runInNewContext(code,{module,exports:module.exports,require:(name:string)=>name==='@/lib/model'?model:name.startsWith('@/')?new Proxy({},{get:()=>()=>null}):require(name)});
 for(const resource of model.taxResources){
  const session={isSuperAdmin:false,tenantId:'t',permissions:[resource+'.read']};
  for(const container of ['settings','settings-master-data','tax-management'])assert.equal(module.exports.canOpenResource(session,container),true,container);
  assert.equal(model.can(session,'tax-management','update'),false);
 }
 assert.equal(module.exports.canOpenResource({isSuperAdmin:false,permissions:['tax-codes.schedule']},'tax-management'),false);
 assert.equal(model.navigationSections.some(section=>section.keys.includes('tax-management')),false);
});
test('both languages cover all tax UI labels and permission actions',()=>{
 const messages=['it','en'].map(locale=>JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8')));
 assert.deepEqual(Object.keys(messages[0].tax).sort(),Object.keys(messages[1].tax).sort());
 for(const messagesForLocale of messages){
  for(const key of ['tax-management',...model.taxResources])assert.ok(messagesForLocale.resources[key]);
  for(const action of ['schedule','deactivate','reactivate','install_templates'])assert.ok(messagesForLocale.permissionActions[action]);
 }
});
