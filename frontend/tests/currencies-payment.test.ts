import test from 'node:test';
import assert from 'node:assert/strict';
import * as payments from '../lib/payments.ts';
test('simulator offers only enabled currencies with known precision, including zero', () => {
 assert.deepEqual(payments.paymentCurrencyOptions([{code:'USD',name:'Dollar',is_enabled:true,minor_units:2},{code:'JPY',name:'Yen',is_enabled:true,minor_units:0},{code:'XXX',name:'No currency',is_enabled:true,minor_units:null},{code:'OLD',name:'Old',is_enabled:false,minor_units:2}]), [{value:'USD',label:'USD · Dollar'},{value:'JPY',label:'JPY · Yen'}]);
});
