import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';

const sourceDirectory = new URL('../../backend/Modules/TaxManagement/', import.meta.url);
const sourceFiles = readdirSync(sourceDirectory).filter(name =>
  /^TaxCalculation.*\.cs$/.test(name) || ['TaxAdjustmentAllocation.cs', 'TaxRoundingService.cs'].includes(name)
).sort();
function calculationCodes(source: string): string[] {
  return [...source.matchAll(/"(tax_calculation_[a-z0-9_]+)"/g)].map(match => match[1]);
}
const codes = [...new Set(sourceFiles.flatMap(name =>
  calculationCodes(readFileSync(new URL(name, sourceDirectory), 'utf8'))
))].sort();
const locales = Object.fromEntries(['it', 'en'].map(locale => [locale,
  JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), 'utf8')).taxCalculation as Record<string, string>
]));

test('F5 error extraction selects quoted calculation codes, not fields or identifiers', () => {
  assert.deepEqual(calculationCodes('"tax_calculation_discount_exceeds_base" "unit_price" "lines[0].value" tax_calculation_not_a_string "tax_calculation_invalid_id"'),
    ['tax_calculation_discount_exceeds_base', 'tax_calculation_invalid_id']);
  for (const file of ['TaxCalculationInput.cs', 'TaxCalculationEndpoints.cs', 'TaxCalculationEngine.cs', 'TaxCalculationNumber.cs', 'TaxCalculationPolicyResolver.cs', 'TaxAdjustmentAllocation.cs', 'TaxRoundingService.cs']) {
    assert.ok(sourceFiles.includes(file), `Missing F5 source: ${file}`);
  }
  for (const code of ['tax_calculation_discount_exceeds_base', 'tax_calculation_amount_out_of_range', 'tax_calculation_allocation_invariant']) {
    assert.ok(codes.includes(code), `Missing F5 error: ${code}`);
  }
});

for (const locale of ['it', 'en']) {
  test(`${locale} localizes every finite F5 source error inside taxCalculation`, () => {
    const missing = codes.filter(code => !Object.hasOwn(locales[locale], code) ||
      typeof locales[locale][code] !== 'string' || !locales[locale][code].trim() || locales[locale][code] === code);
    assert.deepEqual(missing, [], `${locale}: missing or untranslated F5 calculation errors`);
  });
}

test('Italian and English calculation namespaces have identical keys and no blank labels', () => {
  assert.deepEqual(Object.keys(locales.it).sort(), Object.keys(locales.en).sort());
  for (const [locale, labels] of Object.entries(locales)) {
    for (const [key, value] of Object.entries(labels)) {
      assert.equal(typeof value, 'string', `${locale}.${key}`);
      assert.ok(value.trim(), `${locale}.${key} is blank`);
    }
  }
});
