import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';

function helpers() {
  const source = readFileSync(new URL('../components/workspace.tsx', import.meta.url), 'utf8');
  const block = source.match(/\/\* workspace-navigation-helpers \*\/([\s\S]*?)\/\* end-workspace-navigation-helpers \*\//)?.[1] || '';
  const code = ts.transpileModule(`${block || 'function workspaceRoute() { return ""; }'}\nmodule.exports = {workspaceRoute};`, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
  const module = {exports: {} as {workspaceRoute: (value:string,allowed:string[])=>string}};
  runInNewContext(code, {module, URLSearchParams});
  return module.exports;
}
test('restores only a permitted route from a URL', () => {
  const {workspaceRoute} = helpers();
  assert.equal(workspaceRoute('?view=companies', ['companies','sites']), 'companies');
  assert.equal(workspaceRoute('?view=users', ['companies']), '');
  assert.equal(workspaceRoute('?view=companies&view=users', ['companies']), '');
});
