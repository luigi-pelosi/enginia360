import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

test('item type flag labels omit the default qualifier in both languages', () => {
 for (const [locale, expected] of Object.entries({it:['Vendibile','Acquistabile','Gestione stock'], en:['Sellable','Purchasable','Track stock']})) {
  const messages = JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), 'utf8'));
  assert.deepEqual(['default_sellable','default_purchasable','default_track_stock'].map(key => messages.catalog[key]), expected);
 }
});
