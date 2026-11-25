import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeValues} from '../lib/model.ts';

test('currency minor units preserve zero and ISO N.A. as nullable integer', () => {
 const fields = [{name:'minor_units', type:'integer' as const, required:false}, {name:'is_enabled', type:'boolean' as const, required:true}];
 assert.deepEqual(normalizeValues(fields, {minor_units:'0', is_enabled:false}), {minor_units:0,is_enabled:false});
 assert.deepEqual(normalizeValues(fields, {minor_units:'', is_enabled:true}), {minor_units:null,is_enabled:true});
 assert.throws(()=>normalizeValues(fields, {minor_units:'1.5',is_enabled:true}));
});
