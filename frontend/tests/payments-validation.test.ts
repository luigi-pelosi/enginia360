import test from 'node:test';
import assert from 'node:assert/strict';
import {installmentsValid} from '../lib/payments.ts';
test('installments require exact four-place total and valid fixed days', () => {
 const row = {percentage:'33.3333',offsetMonths:0,offsetDays:30,dateRule:'EXACT',offsetBase:'REFERENCE_DATE',fixedDay:null,methodId:null};
 assert.equal(installmentsValid([row,row,{...row,percentage:'33.3334'}]), true);
 assert.equal(installmentsValid([row,row,row]), false);
 assert.equal(installmentsValid([{...row,percentage:'100',dateRule:'FIXED_DAY',fixedDay:32}]), false);
 assert.equal(installmentsValid([{...row,percentage:'100',offsetDays:-1}]), false);
 assert.equal(installmentsValid([]), false);
});
