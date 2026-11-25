import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
for(const locale of ['it','en'])test(`catalog fields and every backend catalog error are localized (${locale})`,()=>{
 const m=JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8'));const other=JSON.parse(readFileSync(new URL(`../messages/${locale==='it'?'en':'it'}.json`,import.meta.url),'utf8'));assert.deepEqual(Object.keys(m.catalog).sort(),Object.keys(other.catalog).sort());
 const codes=['invalid_catalog_decimal','invalid_decimal_places','catalog_conversion_overflow','invalid_unit_dimension','invalid_base_factor','immutable_unit_definition','active_base_required','invalid_category_parent','category_cycle','invalid_item_kind','immutable_item_kind','service_cannot_track_stock','catalog_code_or_base_exists','catalog_constraint_violation','category_has_children','inactive_unit','incompatible_unit_dimensions','invalid_target_unit','invalid_numbering_kind','version_exhausted','expected_version_required','invalid_paging'];for(const code of codes)assert.ok(m.catalog[code]||m.errors[code],code);
});
test('catalog has usable forms, shared modal, conversion and safe writes',()=>{
 const path=new URL('../components/catalog-workspace.tsx',import.meta.url);assert.ok(existsSync(path),'catalog workspace exists');const s=readFileSync(path,'utf8');
 for(const token of ['DialogContent','expectedVersion','/session','catalogUncertain','unroundedQuantity','categoryParents','SelectContent','TableHeader','readOnly','pending']) assert.ok(s.includes(token),token);
});
