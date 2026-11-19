import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';

test('create recovery excludes secret and arbitrary JSON fields', () => {
  const source = readFileSync(new URL('../components/workspace.tsx', import.meta.url), 'utf8');
  const block = source.match(/\/\* record-recovery-helpers \*\/([\s\S]*?)\/\* end-record-recovery-helpers \*\//)?.[1] || 'function recoverableValues(){return {}}';
  const code = ts.transpileModule(`${block}\nmodule.exports = {recoverableValues};`, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
  const module = {exports: {} as any}; runInNewContext(code, {module});
  const result = module.exports.recoverableValues([{name:'name',type:'text'},{name:'password',type:'password'},{name:'settings',type:'json'}], {name:'safe',password:'secret',settings:'{"token":"secret"}'});
  assert.equal(JSON.stringify(result), '{"name":"safe"}');
});
