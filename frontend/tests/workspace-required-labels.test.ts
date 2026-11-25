import test from 'node:test';
import assert from 'node:assert/strict';
import {source} from './workspace-harness.ts';

test('login and password labels mark exactly their required inputs', () => {
  for (const id of ['username', 'password', 'current-password', 'new-password', 'confirm-password'])
    assert.match(source, new RegExp(`<Label htmlFor="${id}" required>`));
  assert.match(source, /<Label htmlFor="tenant-code">/);
});

test('generic field labels use the same conditional required state as fiscal inputs', () => {
  assert.match(source, /<Label htmlFor=\{id\} required=\{fieldRequired\}>/);
  assert.match(source, /required=\{fieldRequired\}/);
  assert.match(source, /const fieldRequired = fiscalFields && \["vat_number", "tax_code"\]\.includes\(field\.name\) \? !String\(values\[field\.name === "vat_number" \? "tax_code" : "vat_number"\] \?\? ""\)\.trim\(\) : field\.required;/);
  assert.doesNotMatch(source, /field\.required && <span aria-hidden="true"> \*<\/span>/);
});
