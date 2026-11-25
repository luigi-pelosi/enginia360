import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {runInNewContext} from 'node:vm';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {clsx} from 'clsx';
import {twMerge} from 'tailwind-merge';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const module = {exports: {} as any};
runInNewContext(ts.transpileModule(readFileSync(new URL('../components/ui/table.tsx', import.meta.url), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}}).outputText, {
  module, exports: module.exports,
  require: (name: string) => name === '@/lib/utils' ? {cn: (...values: any[]) => twMerge(clsx(values))} : require(name),
});
const {Table, TableHeader, TableBody, TableRow, TableHead, TableCell} = module.exports;

for (const kind of [undefined, 'text', 'number', 'status', 'actions']) {
  test(`semantic table alignment wins over legacy classes: ${kind ?? 'default'}`, () => {
    const head = TableHead({kind, scope: 'col', className: 'w-24 px-4 text-right text-left'});
    const cell = TableCell({kind, colSpan: 2, className: 'w-24 px-4 text-center text-left'});
    const headClasses = head.props.className.split(' '), cellClasses = cell.props.className.split(' ');
    assert.equal(head.props['data-kind'], kind ?? 'text');
    assert.equal(cell.props['data-kind'], kind ?? 'text');
    assert.deepEqual(headClasses.filter((v: string) => /^text-(left|right|center)$/.test(v)), [!kind || kind === 'text' ? 'text-left' : 'text-center']);
    assert.deepEqual(cellClasses.filter((v: string) => /^text-(left|right|center)$/.test(v)), [kind === 'number' ? 'text-right' : kind === 'status' || kind === 'actions' ? 'text-center' : 'text-left']);
    assert.ok(cellClasses.includes('w-24')); assert.ok(cellClasses.includes('px-4'));
    if (kind === 'number') {
      assert.ok(cellClasses.includes('tabular-nums'));
      assert.ok(cellClasses.includes('[&_input]:text-right'));
    }
    if (kind === 'status' || kind === 'actions') {
      assert.ok(cellClasses.includes('[&>div]:justify-center'));
      assert.ok(cellClasses.includes('[&>svg]:mx-auto'));
      assert.ok(!cellClasses.includes('[&:has([role=checkbox])]:pr-0'), 'centered checkbox cells retain symmetric padding');
      assert.ok(!headClasses.includes('[&:has([role=checkbox])]:pr-0'), 'centered checkbox headers retain symmetric padding');
    } else assert.ok(!cellClasses.includes('[&>div]:justify-center'));
    const html = renderToStaticMarkup(React.createElement(Table, null,
      React.createElement(TableHeader, null, React.createElement(TableRow, null, React.createElement(TableHead, {kind, scope: 'col'}, 'Heading'))),
      React.createElement(TableBody, null, React.createElement(TableRow, null, React.createElement(TableCell, {kind, colSpan: 2}, React.createElement('span', {'data-slot': 'badge'}, 'Value'))))));
    assert.match(html, /<table /); assert.match(html, /<thead /); assert.match(html, /<tbody /);
    assert.match(html, /<th[^>]*scope="col"/); assert.match(html, /<td[^>]*colSpan="2"/);
    assert.doesNotMatch(html, /\skind=/);
  });
}
