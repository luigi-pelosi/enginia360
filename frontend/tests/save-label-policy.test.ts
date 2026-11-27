import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {harness, session} from './workspace-harness.ts';

for (const [locale, label] of [['it','Salva'], ['en','Save']] as const) {
  test(`company editor uses shared ${label} label`, () => {
    const h = harness(locale);
    const html = h.render('RecordEditor', {resource:{key:'companies', fields:[]}, row:null, canWrite:true, session, tenant:'t', scope:(p:string)=>p, load:async()=>[], onClose(){}, onSaved:async()=>{}, onError:String});
    assert.match(html, new RegExp(`>${label}</button>`));
    assert.doesNotMatch(html, /Salva dati generali|Save general details/);
  });
}
test('activation save confirmation uses shared save while archive stays distinct', () => {
  const source = readFileSync(new URL('../components/catalog-item-workspace.tsx', import.meta.url), 'utf8');
  assert.match(source, /confirmation==='ACTIVE'\s*\?\s*a\('save'\)\s*:\s*t\('archive'\)/);
});
