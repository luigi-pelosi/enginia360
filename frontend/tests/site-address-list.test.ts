import test from 'node:test';
import assert from 'node:assert/strict';
import * as model from '../lib/model.ts';

const fields = ['company_id','name','code','site_type','functions','vat_number','tax_code','address','city','province','postal_code','country_code'].map(name => ({name,type:'text' as const,required:false}));

test('sites table adds one address column while other resource columns remain unchanged', () => {
  assert.equal(typeof model.tableFields, 'function');
  assert.deepEqual(model.tableFields({key:'sites',fields}).map(field=>field.name), [...fields.slice(0,6).map(field=>field.name),'address']);
  assert.deepEqual(model.tableFields({key:'users',fields}).map(field=>field.name), fields.slice(0,6).map(field=>field.name));
  assert.deepEqual(model.tableFields(undefined), []);
});

test('complete site address includes street, postcode, city, province and localized country', () => {
  assert.equal(typeof model.siteAddress, 'function');
  const row = {id:'s',address:'Via Appia 1',postal_code:'81043',city:'Capua',province:'CE',country_code:'IT'};
  assert.equal(model.siteAddress(row,'it'), 'Via Appia 1, 81043 Capua CE, Italia (IT)');
  assert.equal(model.siteAddress(row,'en'), 'Via Appia 1, 81043 Capua CE, Italy (IT)');
  assert.equal(model.siteAddress({id:'s',address:'1 QA Street',postal_code:'SW1A 1AA',city:'London',province:'Greater London',country_code:'GB'},'en'), '1 QA Street, SW1A 1AA London Greater London, United Kingdom (GB)');
});

test('missing address components do not produce undefined, separators or invented values', () => {
  assert.equal(typeof model.siteAddress, 'function');
  assert.equal(model.siteAddress({id:'s'},'it'), '—');
  assert.equal(model.siteAddress({id:'s',city:'Capua',province:null},'it'), 'Capua');
});
