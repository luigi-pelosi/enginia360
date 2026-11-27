import test from 'node:test';
import assert from 'node:assert/strict';
import {source} from './workspace-harness.ts';

test('login and password labels mark exactly their required inputs', () => {
  for (const id of ['username', 'password', 'current-password', 'new-password', 'confirm-password'])
    assert.match(source, new RegExp(`<Label htmlFor="${id}" required>`));
  assert.match(source, /<Label htmlFor="tenant-code">/);
});

test('generic field labels use metadata without fiscal alternatives on sites', () => {
  assert.match(source, /<Label htmlFor=\{id\} required=\{fieldRequired\}>/);
  assert.match(source, /required=\{fieldRequired\}/);
  assert.match(source, /const fieldRequired = field\.required;/);
  assert.doesNotMatch(source, /fiscalFields|missingFiscal|taxIdentityRequired/);
  assert.doesNotMatch(source, /field\.required && <span aria-hidden="true"> \*<\/span>/);
});
