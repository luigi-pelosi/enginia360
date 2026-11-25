import test from 'node:test';
import assert from 'node:assert/strict';
import {itemHarness,root,itemSession} from './catalog-items-harness.ts';
test('saved item viewer exposes independent company tab and preserves root draft and version',async()=>{
 const h=itemHarness(undefined,{session:{...itemSession,permissions:['catalog-items.read','catalog-items.update','catalog-item-companies.read','catalog-item-companies.update']},record:root()});
 await h.settle();await h.action('Modifica Item A').props.onClick();await h.settle();await h.edit('item-name','Unsaved root draft');
 assert.ok(h.byId('item-tab-companies'),'saved item must expose Companies tab');
 await h.click('item-tab-companies');assert.equal(h.state.editor?.values.name,'Unsaved root draft');assert.equal(h.state.editor?.version,4);
 const again=itemHarness(undefined,{storage:h.storage});await again.settle();assert.equal(again.state.tab,'companies');assert.equal(again.state.editor?.values.name,'Unsaved root draft');
 h.unmount();again.unmount();
});
test('new item does not expose Companies or associate automatically',async()=>{
 const h=itemHarness();await h.settle();await h.click('catalog-item-new');assert.ok(!h.byId('item-tab-companies'));assert.equal(h.calls.some(c=>c.path.includes('/item-companies')),false);h.unmount();
});
