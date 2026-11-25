import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

function tags(file: string, tag: string) {
 const source=ts.createSourceFile(file,readFileSync(new URL(`../components/${file}`,import.meta.url),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 const result:ts.JsxElement[]=[];
 function visit(n:ts.Node){if(ts.isJsxElement(n)&&n.openingElement.tagName.getText(source)===tag)result.push(n);ts.forEachChild(n,visit);}visit(source);
 return result.map(n=>({body:n.children.map(c=>c.getText(source)).join(''),attrs:n.openingElement.attributes.getText(source)}));
}

test('generic workspace derives matching header and cell semantics from field metadata',()=>{
 const source=readFileSync(new URL('../components/workspace.tsx',import.meta.url),'utf8');
 const heads=tags('workspace.tsx','TableHead'), cells=tags('workspace.tsx','TableCell');
 const expected='col.type === "integer" ? "number" : col.type === "boolean" || col.name === "is_enabled" ? "status" : "text"';
 assert.ok(heads.some(n=>n.attrs.includes(`kind={${expected}}`)));
 assert.ok(cells.some(n=>n.attrs.includes(`kind={${expected}}`)));
 assert.ok(heads.some(n=>n.attrs.includes('kind="actions"')));
 assert.ok(cells.some(n=>n.attrs.includes('kind="actions"')));
 assert.match(source,/col.type === "boolean" \|\| col.name === "is_enabled" \? \(/);
});

test('payment numeric, text and action columns declare their semantic kinds',()=>{
 const heads=tags('payments-workspace.tsx','TableHead'),cells=tags('payments-workspace.tsx','TableCell');
 for(const head of heads.filter(n=>n.body.includes("a('actions')"))) assert.ok(head.attrs.includes('kind="actions"'));
 for(const head of heads.filter(n=>n.body==="{t('installment')}"||n.body==="{t('amount')}")) assert.ok(head.attrs.includes('kind="number"'));
 for(const cell of cells.filter(n=>n.body==='{i+1}'||n.body==='{row.amount}'||/input\(`(?:percent|months|days|fixed)-/.test(n.body))) assert.ok(cell.attrs.includes('kind="number"'),cell.body);
 for(const cell of cells.filter(n=>n.body.includes('<Button'))) assert.ok(cell.attrs.includes('kind="actions"'));
 for(const cell of cells.filter(n=>n.body.includes('{x.name}'))) assert.ok(!cell.attrs.includes('kind="status"'),'name and disabled badge remain text');
 assert.ok(heads.some(n=>n.attrs.includes("['percentage','offsetMonths','offsetDays','fixedDay'].includes(key) ? 'number' : 'text'")));
});
