import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source = readFileSync(new URL('../components/workspace.tsx', import.meta.url), 'utf8');
const label = source.slice(source.indexOf('<Label htmlFor="tenant-code">'), source.indexOf('</Label>', source.indexOf('<Label htmlFor="tenant-code">')));

test('organization code login label never advertises general optionality', () => {
  assert.ok(label.includes('t("tenantCode")'));
  assert.doesNotMatch(label, /t\("optional"\)|className="optional"/);
});

test('global admin omission remains possible without guessing privileges before authentication', () => {
  const field = source.slice(source.indexOf('id="tenant-code"'), source.indexOf('/>', source.indexOf('id="tenant-code"')));
  assert.doesNotMatch(field, /\brequired\b/);
  assert.match(source, /\.\.\.\(tenantCode \? \{ tenantCode \} : \{\}\)/);
  assert.doesNotMatch(source, /username\s*===\s*["']luigi/);
});
