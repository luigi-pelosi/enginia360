import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';

function harness(active: string) {
  const source = readFileSync(new URL('../components/workspace.tsx', import.meta.url), 'utf8');
  const file = ts.createSourceFile('workspace.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let navigation: ts.FunctionDeclaration | undefined;
  function visit(node: ts.Node) {
    if (ts.isFunctionDeclaration(node) && node.name?.text === 'navigate') navigation = node;
    ts.forEachChild(node, visit);
  }
  visit(file);
  assert.ok(navigation, 'navigate exists');
  const code = ts.transpileModule(`${navigation.getText(file)}\nmodule.exports = navigate;`, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}}).outputText;
  const state: Record<string, unknown> = {active, editor: 'open', deleting: 'open', profileOpen: true, resetUser: 'open', search: 'abc', query: 'abc', page: 3, notice: 'notice', error: 'error', partnerWorkspaceVersion: 0, workspaceVersion: 0};
  const history: string[] = [], recoveries: string[] = [];
  const context: Record<string, unknown> = {module: {exports: null}, active, editor: {resource: {key: active}}, clearRecordRecovery: () => {}, clearProfileRecovery: () => {}, session: {id: 'user'}, tenant: 'tenant', window: {location: {pathname: '/'}, history: {pushState: (_a: unknown, _b: unknown, url: string) => history.push(url)}}, resetBusinessPartnerRecovery: () => recoveries.push('reset'), resetBusinessPartnerNumberingRecovery: () => recoveries.push('numbering')};
  for (const key of Object.keys(state)) context[`set${key[0].toUpperCase()}${key.slice(1)}`] = (value: unknown) => {state[key] = typeof value === 'function' ? value(state[key]) : value;};
  runInNewContext(code, context);
  return {navigate: (context.module as {exports: (key: string) => void}).exports, state, history, recoveries};
}

test('menu navigation closes workspace dialogs and clears filters even on the current view', () => {
  const h = harness('companies');
  h.navigate('companies');
  assert.equal(h.state.editor, null);
  assert.equal(h.state.deleting, null);
  assert.equal(h.state.profileOpen, false);
  assert.equal(h.state.resetUser, null);
  assert.equal(h.state.search, '');
  assert.equal(h.state.query, '');
  assert.equal(h.state.page, 1);
  assert.equal(h.state.error, '');
  assert.deepEqual(h.history, []);
});


test('reselecting numbering remounts its local editor state', () => {
  const h = harness('business-partner-numbering');
  h.navigate('business-partner-numbering');
  assert.equal(h.state.workspaceVersion, 1);
  assert.deepEqual(h.recoveries,['numbering']);
  const source = readFileSync(new URL('../components/workspace.tsx', import.meta.url), 'utf8');
  assert.match(source, /<BusinessPartnerNumbering key=\{`\$\{tenant\}:\$\{workspaceVersion\}`} /);
});
