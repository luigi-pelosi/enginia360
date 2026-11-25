import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const source = readFileSync(new URL('../components/ui/label.tsx', import.meta.url), 'utf8');
const module = {exports: {} as any};
runInNewContext(ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}}).outputText, {
  module, exports: module.exports,
  require: (name: string) => name === '@/lib/utils' ? {cn: (...values: unknown[]) => values.filter(Boolean).join(' ')} : require(name),
});
const {Label} = module.exports;

test('required label renders one decorative indicator and preserves accessible label association', () => {
  const html = renderToStaticMarkup(React.createElement(Label, {required: true, htmlFor: 'name', id: 'name-label'}, 'Name'));
  assert.match(html, /<label[^>]*for="name"[^>]*>/);
  assert.match(html, /id="name-label"/);
  assert.match(html, /Name<span[^>]*aria-hidden="true"[^>]*>\*<\/span>/);
  assert.doesNotMatch(html, /\srequired(?:=|\s|>)/);
});

test('optional labels preserve children and omit required marker', () => {
  for (const required of [undefined, false]) {
    const html = renderToStaticMarkup(React.createElement(Label, {required, htmlFor: 'optional', className: 'extra'}, React.createElement('em', null, 'Optional')));
    assert.match(html, /for="optional"/);
    assert.match(html, /class="[^"]*extra/);
    assert.match(html, /<em>Optional<\/em>/);
    assert.doesNotMatch(html, /\*|\srequired(?:=|\s|>)/);
  }
});

test('required asChild keeps its element and properties', () => {
  const html = renderToStaticMarkup(React.createElement(Label, {required: true, asChild: true, htmlFor: 'item'}, React.createElement('label', {'data-test': 'slot'}, 'Item')));
  assert.match(html, /<label[^>]*for="item"/);
  assert.match(html, /data-test="slot"/);
  assert.match(html, /Item<span[^>]*aria-hidden="true"[^>]*>\*<\/span>/);
});

test('required label does not duplicate an existing trailing indicator', () => {
  const html = renderToStaticMarkup(React.createElement(Label, {required: true}, 'Name *'));
  assert.equal((html.match(/\*/g) || []).length, 1);
});
