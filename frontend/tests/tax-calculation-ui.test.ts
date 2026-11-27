import test from 'node:test';
import assert from 'node:assert/strict';
import {calculationHarness, successfulScenario, calculationSession, policy, uuid} from './tax-calculation-harness.ts';
import {emptyTaxCalculation, appendTaxCalculationScenario} from '../lib/tax-calculation.ts';

async function captured(options:any = {}) {
  const h=calculationHarness({initial:initial(),...options});
  await h.settle();
  h.byId('tax-calc-add-scenario').props.onClick();
  await h.settle();
  return h;
}
test('refresh and remount preserve separate document input/result/pin without automatic POST', async () => {
  const h=await captured();
  const id=h.state.calculation.draft.lines[0].line_id;
  h.change('tax-calc-price-'+id,'123456789012.12345678');
  await h.settle();
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  h.byId('tax-calc-pin').props.onClick();
  await h.settle();
  h.change('tax-calc-price-'+id,'2.00');
  await h.settle();
  assert.ok(h.byId('tax-calc-stale'));
  const saved=h.state;
  assert.equal(saved.calculation.submitted.input.lines[0].unit_price,'123456789012.12345678');
  assert.equal(saved.calculation.comparison.input.lines[0].unit_price,'123456789012.12345678');
  h.byId('tax-sim-refresh').props.onClick();
  await h.settle();
  assert.equal(h.calls.filter(c=>c.method==='POST').length,1);
  h.unmount();
  const recovered=calculationHarness({storage:h.map});
  await recovered.settle();
  assert.equal(recovered.byId('tax-calc-price-'+id).props.value,'2.00');
  assert.ok(recovered.byId('tax-calc-result'));
  assert.ok(recovered.byId('tax-calc-comparison'));
  assert.equal(recovered.calls.filter(c=>c.method==='POST').length,0);
});
test('two real rendered lines keep independent prices, scenario inputs and sequential adjustments', async () => {
  const h=await captured();
  h.byId('tax-calc-add-scenario').props.onClick();
  await h.settle();
  const [first,second]=h.state.calculation.draft.lines;
  assert.notEqual(first.line_id,second.line_id);
  h.change('tax-calc-price-'+first.line_id,'10');
  await h.settle();
  h.change('tax-calc-price-'+second.line_id,'20');
  await h.settle();
  h.change('tax-sim-date','2026-11-28');
  await h.settle();
  assert.equal(h.state.calculation.draft.lines[0].scenario.input.tax_date,first.scenario.input.tax_date);
  h.byId('tax-calc-adjustments-'+first.line_id+'-add').props.onClick();
  await h.settle();
  h.byId('tax-calc-adjustments-'+first.line_id+'-add').props.onClick();
  await h.settle();
  const adjustments=h.state.calculation.draft.lines[0].adjustments;
  h.change('tax-calc-adjustments-'+first.line_id+'-value-'+adjustments[0].adjustment_id,'10,25');
  await h.settle();
  h.find(n=>n.props?.['aria-label']==='moveDown'&&!n.props.disabled).props.onClick();
  await h.settle();
  const updated=h.state.calculation.draft.lines;
  assert.equal(updated[0].adjustments[1].adjustment_id,adjustments[0].adjustment_id);
  assert.equal(updated[0].adjustments[1].sequence,2);
  assert.equal(updated[1].unit_price,'20');
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  const post=h.calls.find(c=>c.method==='POST');
  assert.equal(post.body.lines.length,2);
  assert.equal(post.body.lines[0].adjustments[1].value,'10.25');
  assert.equal(post.body.lines[1].unit_price,'20');
});
test('purchase percentage stays unknown when cleared and reversal keeps input magnitudes positive', async () => {
  const state=initial();
  state.input.operation_type='PURCHASE';
  const h=await captured({initial:state});
  const id=h.state.calculation.draft.lines[0].line_id;
  h.change('tax-calc-deductible-'+id,'40,5');
  await h.settle();
  h.change('tax-calc-deductible-'+id,'');
  await h.settle();
  h.change('tax-calc-direction','REVERSAL');
  await h.settle();
  h.change('tax-calc-price-'+id,'12.00');
  await h.settle();
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  const body=h.calls.find(c=>c.method==='POST').body;
  assert.equal(body.direction,'REVERSAL');
  assert.equal(body.lines[0].unit_price,'12.00');
  assert.equal(body.lines[0].deductible_percentage,null);
});
test('calculation permissions do not imply F4 read; F4-only users gain no F5 tab or policy reads', async () => {
  for(const permissions of [calculationSession.permissions.filter(p=>!p.startsWith('tax-determination.')),calculationSession.permissions.filter(p=>!p.startsWith('tax-calculation.'))]) {
    const h=calculationHarness({initial:initial(),session:{...calculationSession,permissions}});
    await h.settle();
    assert.equal(h.byId('tax-calculation-panel'),undefined);
    assert.equal(h.byId('tax-calc-add-scenario'),undefined);
    assert.equal(h.calls.some(c=>c.path.includes('calculation-policy')),false);
  }
});
test('read-only F5 can inspect policy but cannot calculate without both simulation grants', async () => {
  for(const options of [
    {session:{...calculationSession,permissions:calculationSession.permissions.filter(p=>p!=='tax-calculation.simulate')}},
    {f4Permissions:['read','determine']},
    {policy:{...policy,permissions:['read']}},
  ]) {
    const h=await captured(options);
    assert.ok(h.byId('tax-calc-policy'));
    assert.equal(h.byId('tax-calc-run').props.disabled,true);
    h.byId('tax-calc-run').props.onClick();
    await h.settle();
    assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
  }
});
test('fresh identity, source and company authority revocations prevent POST', async () => {
  for(const options of [
    {freshSession:{...calculationSession,id:'other-user'}},
    {freshSession:{...calculationSession,permissions:calculationSession.permissions.filter(p=>p!=='tax-calculation.simulate')}},
    {freshSession:{...calculationSession,permissions:calculationSession.permissions.filter(p=>p!=='catalog-items.read')}},
    {handler:(path:string)=>path.includes('calculation-policy')?{...policy,permissions:['read']}:undefined},
  ]) {
    const h=await captured(options);
    h.byId('tax-calc-run').props.onClick();
    await h.settle();
    assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
  }
});
test('dedicated adapter preserves indexed field and fiscal 422 trace without replacing last result', async () => {
  let attempts=0;
  const h=await captured({fetch:()=>++attempts===1?undefined:({ok:false,status:422,json:async()=>({code:'tax_calculation_determination_failed',field:'lines[0].fiscal_context',outcome:'NO_MATCHING_RULE',isSimulation:true,trace:{missingFields:['partner.actingAsTaxablePerson']}})})});
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  const accepted=h.state.calculation.submitted;
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  assert.ok(h.find(n=>n.props?.role==='alert'));
  assert.ok(h.find(n=>n.props?.role==='alert'&&Array.isArray(n.props.children)&&n.props.children.includes('tax_calculation_determination_failed')));
  assert.ok(h.find(n=>n.props?.children==='partner.actingAsTaxablePerson'));
  assert.deepEqual(h.state.calculation.submitted,accepted);
  assert.equal(h.state.calculation.draft.lines.length,1);
});
test('ordinary in-flight lock blocks duplicate calculation and F4 writes; unmount suppresses late persistence', async () => {
  let release:any;
  const response=new Promise(resolve=>{release=resolve;});
  const h=await captured({fetch:()=>response});
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  assert.equal(h.byId('tax-calc-run').props.disabled,true);
  h.byId('tax-calc-run').props.onClick();
  h.byId('tax-sim-run').props.onClick();
  await h.settle();
  assert.equal(h.calls.filter(c=>c.method==='POST').length,1);
  const before=h.map.get(h.key);
  h.unmount();
  release({ok:true,status:200,json:async()=>({isSimulation:true,result:{lines:[],summaries:[],totals:{}}})});
  await h.settle();
  assert.equal(h.map.get(h.key),before);
});
test('document scopes use stable IDs, warn about mixed modes and remove references with removed lines', async () => {
  const h=await captured();
  h.byId('tax-calc-add-scenario').props.onClick();
  await h.settle();
  const [first,second]=h.state.calculation.draft.lines;
  h.change('tax-calc-price-mode-'+second.line_id,'TAX_INCLUSIVE');
  await h.settle();
  h.byId('tax-calc-document-add').props.onClick();
  await h.settle();
  assert.ok(h.find(n=>n.props?.children==='mixedModes'));
  const all=h.find(n=>n.type==='input'&&n.props.type==='checkbox'&&n.props.checked);
  all.props.onChange({target:{checked:false}});
  await h.settle();
  assert.deepEqual(h.state.calculation.draft.document_adjustments[0].applicable_line_ids,[first.line_id,second.line_id]);
  h.byId('tax-calc-remove-'+first.line_id).props.onClick();
  await h.settle();
  assert.deepEqual(h.state.calculation.draft.document_adjustments[0].applicable_line_ids,[second.line_id]);
});
test('menu-style reset clears calculation and F4 ordinary state under the same recovery key', async () => {
  const h=await captured();
  h.byId('tax-sim-reset').props.onClick();
  await h.settle();
  assert.equal(h.state.calculation.draft.lines.length,0);
  assert.equal(h.state.submitted,null);
  assert.equal(h.state.tab,'context');
});
test('recovered other-company document cannot submit against the current company', async () => {
  const state:any=initial();
  const slice=emptyTaxCalculation();
  slice.draft=appendTaxCalculationScenario(slice.draft,state.submitted as any,()=>uuid(60));
  state.calculation=slice;
  state.input={...state.input,company_id:uuid(61)};
  const h=calculationHarness({initial:state});
  await h.settle();
  assert.equal(h.byId('tax-calc-run').props.disabled,true);
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
});


test('fresh company action changes after display prevent submission', async () => {
  for (const kind of ['f4','f5']) {
    let policyReads=0, f4Reads=0;
    const h=await captured({handler:(path:string)=>{
      if(path.includes('calculation-policy')) return {...policy,permissions:++policyReads===1||kind!=='f5'?['read','simulate']:['read']};
      if(path.includes('determination-lookups')) return {countries:[],types:[],companies:[],registrations:[],permissions:++f4Reads===1||kind!=='f4'?['read','simulate','determine']:['read']};
    }});
    assert.equal(h.byId('tax-calc-run').props.disabled,false);
    h.byId('tax-calc-run').props.onClick();
    await h.settle();
    assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
    assert.ok(h.find(n=>n.props?.role==='alert'));
  }
});
test('indexed decimal error marks the actual line input without coercing it', async () => {
  const h=await captured({fetch:()=>({ok:false,status:400,json:async()=>({code:'tax_calculation_invalid_decimal',field:'lines[0].unit_price'})})});
  const id=h.state.calculation.draft.lines[0].line_id;
  h.change('tax-calc-price-'+id,'1e2');
  await h.settle();
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  assert.equal(h.byId('tax-calc-price-'+id).props['aria-invalid'],true);
  assert.equal(h.byId('tax-calc-price-'+id).props.value,'1e2');
});
test('failed F4 scenarios cannot be captured; 100 recovered real line editors remain bounded', async () => {
  const failed:any=initial();
  failed.submitted.output={outcome:'NO_MATCHING_RULE',result:null,isSimulation:true,trace:{}};
  const denied=calculationHarness({initial:failed});
  await denied.settle();
  assert.equal(denied.byId('tax-calc-add-scenario'),undefined);
  const state:any=initial();
  state.calculation=emptyTaxCalculation();
  state.calculation.draft=appendTaxCalculationScenario(state.calculation.draft,state.submitted,()=>uuid(70));
  const line=state.calculation.draft.lines[0];
  state.calculation.draft.lines=Array.from({length:100},(_,index)=>({...structuredClone(line),line_id:uuid(100+index)}));
  const h=calculationHarness({initial:state});
  await h.settle();
  for(let index=0;index<100;index++) assert.ok(h.byId('tax-calc-price-'+uuid(100+index)));
  h.byId('tax-calc-add-scenario').props.onClick();
  await h.settle();
  assert.equal(h.state.calculation.draft.lines.length,100);
  assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
});

function initial() {
  const scenario = successfulScenario();
  return {input:scenario.input,drafts:scenario.draftVersionIds,submitted:scenario,comparison:null,tab:'result'};
}
test('real simulator captures successful F4 into editable document and explicitly posts raw facts', async () => {
  const h = calculationHarness({initial:initial()});
  await h.settle();
  assert.ok(h.byId('tax-calc-add-scenario'), 'successful F4 result has no calculation capture action');
  h.byId('tax-calc-add-scenario').props.onClick();
  await h.settle();
  assert.equal(h.state.tab, 'calculation');
  const id = h.state.calculation.draft.lines[0].line_id;
  h.change('tax-calc-price-'+id, '10,00');
  await h.settle();
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  const posts = h.calls.filter(c=>c.method==='POST');
  assert.equal(posts.length,1);
  assert.equal(posts[0].path,'/api/tax/calculations/simulate');
  assert.equal(posts[0].body.lines[0].unit_price,'10.00');
  assert.ok(!('determination' in posts[0].body.lines[0]));
  assert.ok(h.byId('tax-calc-result'));
  assert.equal(h.state.calculation.submitted.output.result.totals.amountPayable,'12.20');
});
