import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';

import * as calc from '../lib/tax-calculation.ts';
import {emptyTaxDeterminationInput, resetTaxSimulatorRecovery, taxSimulatorRecoveryKey, resetTaxRuleRecovery, taxRuleRecoveryKey} from '../lib/tax-rules.ts';

function scenario(): any {
  return {input:{...emptyTaxDeterminationInput(),company_id:'company'},draftVersionIds:['draft'],output:{outcome:'SUCCESS',result:{rate:'22'},isSimulation:true,trace:{}}};
}
function draft() {
  return calc.appendTaxCalculationScenario(calc.emptyTaxCalculation().draft, scenario(), ()=>'line');
}
const output: calc.TaxCalculationOutput = {isSimulation:true,result:{currency:'EUR',calculationPolicyCode:'policy',calculationPolicyVersion:1,lines:[],summaries:[],totals:{amountPayable:'0.00'},calculationTrace:{}}};

test('decimal transport keeps exact text, nullable purchase percentage and rejects no value silently', () => {
  const value = draft();
  value.operation_type = 'PURCHASE';
  value.lines[0].scenario.input.operation_type = 'PURCHASE';
  value.lines[0].unit_price = '999999999999.12345678';
  value.lines[0].quantity = '12345678901234.123456';
  value.lines[0].deductible_percentage = '';
  const body = calc.taxCalculationCommand(value);
  assert.equal(body.lines[0].unit_price, '999999999999.12345678');
  assert.equal(body.lines[0].quantity, '12345678901234.123456');
  assert.equal(body.lines[0].deductible_percentage, null);
  assert.equal(calc.taxCalculationDecimal('12,34'),'12.34');
  for(const invalid of ['1,234.56','1.234,56','1e2','-1',' 1 ']) assert.equal(calc.taxCalculationDecimal(invalid),invalid);
});
test('effective DTO omits draft key entirely and refuses any draft scenario', () => {
  const value = draft();
  assert.throws(()=>calc.taxCalculationCommand(value,false), /draftsSimulationOnly/);
  value.lines[0].scenario.draftVersionIds=[];
  const context=calc.taxCalculationCommand(value,false).lines[0].fiscal_context;
  assert.ok(!('draft_version_ids' in context));
});
test('ordered adjustments and stable document scopes survive the DTO whitelist', () => {
  const value = draft();
  value.lines[0].adjustments=[{adjustment_id:'a',type:'DISCOUNT',calculation_mode:'PERCENTAGE',value:'10,25',sequence:2,applicable_line_ids:['forbidden-line-scope']}];
  value.document_adjustments=[{adjustment_id:'doc',type:'SURCHARGE',calculation_mode:'FIXED_AMOUNT',value:'1,00',sequence:1,applicable_line_ids:['line']}];
  const body=calc.taxCalculationCommand(value);
  assert.deepEqual(body.lines[0].adjustments,[{adjustment_id:'a',type:'DISCOUNT',calculation_mode:'PERCENTAGE',value:'10.25',sequence:2}]);
  assert.deepEqual(body.document_adjustments[0].applicable_line_ids,['line']);
  assert.equal(body.document_adjustments[0].value,'1.00');
});
test('stale comparison preserves array order and ignores fiscal browser result mutations', () => {
  const value=draft();
  value.document_adjustments=[{adjustment_id:'a',type:'DISCOUNT',calculation_mode:'PERCENTAGE',value:'10',sequence:1},{adjustment_id:'b',type:'SURCHARGE',calculation_mode:'FIXED_AMOUNT',value:'1',sequence:2}];
  const snapshot={input:structuredClone(value),output};
  value.lines[0].scenario.output.result!.rate='999';
  assert.equal(calc.taxCalculationStale(snapshot,value),false);
  value.document_adjustments.reverse();
  assert.equal(calc.taxCalculationStale(snapshot,value),true);
  assert.equal(calc.taxCalculationCanonical({b:1,a:2}),calc.taxCalculationCanonical({a:2,b:1}));
});
test('recovery defaults legacy F4 slice and preserves detached inputs, result and pin', () => {
  assert.deepEqual(calc.recoverTaxCalculation(undefined),calc.emptyTaxCalculation());
  const value={draft:draft(),submitted:{input:draft(),output},comparison:{input:draft(),output}};
  const recovered=calc.recoverTaxCalculation(JSON.parse(JSON.stringify(value)));
  assert.deepEqual(recovered,value);
  recovered.draft.lines[0].unit_price='42.00';
  assert.equal(recovered.submitted!.input.lines[0].unit_price,'0.00');
  assert.equal(recovered.comparison!.input.lines[0].unit_price,'0.00');
  const malformed=structuredClone(value) as any;
  malformed.draft.lines[0].unit_price=42;
  assert.deepEqual(calc.recoverTaxCalculation(malformed),calc.emptyTaxCalculation());
});
test('capture refuses mismatched company/operation and the 101st line', () => {
  const value=draft(),other=scenario();
  other.input.company_id='other';
  assert.throws(()=>calc.appendTaxCalculationScenario(value,other),/contextMismatch/);
  other.input.company_id=value.company_id;
  other.input.operation_type='PURCHASE';
  assert.throws(()=>calc.appendTaxCalculationScenario(value,other),/contextMismatch/);
  value.lines=Array.from({length:100},(_,i)=>({...value.lines[0],line_id:String(i)}));
  assert.throws(()=>calc.appendTaxCalculationScenario(value,scenario()),/lineLimit/);
});
test('actual menu reset removes ordinary simulator slice without touching pending rule markers or other users', () => {
  const key=taxSimulatorRecoveryKey('u','t'),other=taxSimulatorRecoveryKey('v','t'),rules=taxRuleRecoveryKey('u','t');
  const map=new Map([[key,JSON.stringify({calculation:{draft:draft()}})],[other,'other-user'],[rules,JSON.stringify({pending:{body:'original'}})]]);
  const storage={getItem:(k:string)=>map.get(k)??null,removeItem:(k:string)=>map.delete(k)};
  resetTaxSimulatorRecovery(storage,'u','t');
  resetTaxRuleRecovery(storage,'u','t');
  assert.equal(map.has(key),false);
  assert.equal(map.get(other),'other-user');
  assert.equal(JSON.parse(map.get(rules)!).pending.body,'original');
});

const source = new URL('../lib/tax-calculation.ts', import.meta.url);
test('F5 builds detached raw-facts DTO, never sends browser fiscal results', async () => {
  assert.ok(existsSync(source), 'F5 raw-facts calculation adapter is missing');
  const calc = await import('../lib/tax-calculation.ts');
  const tax = await import('../lib/tax-rules.ts');
  const scenario:any = {
    input: {...tax.emptyTaxDeterminationInput(), company_id:'company', item_id:'item'},
    draftVersionIds:['draft'],
    output: {outcome:'SUCCESS', result:{rate:'22'}, isSimulation:true, trace:{}},
  };
  const state = calc.emptyTaxCalculation();
  const draft = calc.appendTaxCalculationScenario(state.draft, scenario, ()=>'stable-line');
  scenario.input.item_id = 'changed';
  scenario.draftVersionIds.push('changed');
  const body = calc.taxCalculationCommand(draft);
  assert.equal(body.lines[0].fiscal_context.item_id, 'item');
  assert.deepEqual(body.lines[0].fiscal_context.draft_version_ids, ['draft']);
  assert.equal(body.lines[0].quantity, '1');
  assert.equal(body.lines[0].unit_price, '0.00');
  assert.equal(body.lines[0].line_id, 'stable-line');
  assert.ok(!JSON.stringify(body).includes('rate'));
  assert.ok(!('policy' in body));
});
