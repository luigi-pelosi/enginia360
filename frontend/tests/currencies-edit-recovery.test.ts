import test from 'node:test';
import assert from 'node:assert/strict';
import {harness, session} from './workspace-harness.ts';

test('currency edit recovery reads authoritative row even when changed, and rejects missing or wrong resource', async () => {
 const h=harness('en');
 const recover=h.components.recoverCurrencyEdit;
 assert.equal(typeof recover,'function');
 const saved={kind:'edit',id:'eur',baseline:{code:'EUR',name:'Euro'},values:{name:'draft'}};
 const fields=[{name:'code',type:'text'},{name:'name',type:'text'}];
 const resource={key:'currencies',fields};
 const row={id:'eur',code:'EUR',name:'Euro'};
 assert.deepEqual(JSON.parse(JSON.stringify(await recover(saved,resource,async()=>[row]))),row);
 assert.equal((await recover(saved,resource,async()=>[{...row,name:'changed'}])).name,'changed');
 assert.equal(await recover(saved,resource,async()=>[]),null);
 assert.equal(await recover(saved,{...resource,key:'countries'},async()=>[row]),null);
});
