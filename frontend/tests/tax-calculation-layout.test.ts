import test from 'node:test';
import assert from 'node:assert/strict';
import {calculationHarness, successfulScenario} from './tax-calculation-harness.ts';

// Il DOM reale del pannello deve dare tutta la riga agli oggetti annidati.
test('nested calculation snapshots retain full-width fields in current and pinned results', async () => {
  const scenario = successfulScenario();
  const h = calculationHarness({initial: {
    input: scenario.input, drafts: scenario.draftVersionIds,
    submitted: scenario, comparison: null, tab: 'result',
  }});
  await h.settle();
  h.byId('tax-calc-add-scenario').props.onClick();
  await h.settle();
  h.byId('tax-calc-run').props.onClick();
  await h.settle();
  h.byId('tax-calc-pin').props.onClick();
  await h.settle();
  for (const id of ['tax-calc-result', 'tax-calc-comparison']) {
    let compositeCount = 0;
    function inspect(node: any) {
      if (Array.isArray(node)) {node.forEach(inspect); return;}
      if (!node || typeof node !== 'object') return;
      if (node.type === 'dd' && ['dl', 'ol'].includes(node.props.children?.type)) {
        compositeCount++;
        assert.ok(node.props.className.includes('col-span-full'),
          `${id}: nested object is constrained to the parent value column`);
        assert.ok(node.props.className.includes('text-left'));
      }
      inspect(node.props?.children);
    }
    assert.ok(h.byId(id));
    inspect(h.byId(id));
    assert.ok(compositeCount >= 5, 'the test must reach the full acquired scenario');
  }
});
