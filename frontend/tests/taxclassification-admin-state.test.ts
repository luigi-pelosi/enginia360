import test from 'node:test';
import assert from 'node:assert/strict';
import {taxSections, taxDefaults, readTaxState,resetTaxState} from '../lib/tax.ts';
test('classification-only sections survive workspace recovery without changing phase-one date context',()=>{
 for(const section of ['tax-item-classifications','tax-partner-classifications']){
  assert.ok((taxSections as readonly string[]).includes(section));
  const state=readTaxState({getItem:()=>JSON.stringify({...taxDefaults(),section,date:'2030-04-30'})},'key');
  assert.equal(state.section,section);assert.equal(state.date,'2030-04-30');
 }
});

test('menu reset preserves selected section when either classification kind has an uncertain command',()=>{
 for(const kind of ['item','partner']){const storage=new Map([['base','selected-phase-two'],['base:classifications:'+kind+':pending','uncertain']]);resetTaxState({getItem:k=>storage.get(k)??null,removeItem:k=>{storage.delete(k);}},'base');assert.equal(storage.get('base'),'selected-phase-two');}
});
