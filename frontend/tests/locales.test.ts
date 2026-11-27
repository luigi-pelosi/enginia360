import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createTranslator} from 'next-intl';
import {resourceKeys} from '../lib/model.ts';
const it=JSON.parse(readFileSync(new URL('../messages/it.json',import.meta.url),'utf8'));
const en=JSON.parse(readFileSync(new URL('../messages/en.json',import.meta.url),'utf8'));
test('user details have concise localized field and language labels without display name', () => {
 assert.deepEqual([it.fields.first_name,it.fields.last_name,it.fields.date_of_birth,it.fields.phone_number,it.fields.preferred_language], ['Nome','Cognome','Data di nascita','Telefono','Lingua predefinita']);
 assert.deepEqual([en.fields.first_name,en.fields.last_name,en.fields.date_of_birth,en.fields.phone_number,en.fields.preferred_language], ['First name','Last name','Date of birth','Phone','Default language']);
 assert.deepEqual(it.languages, {it: 'Italiano', en: 'Inglese'});
 assert.deepEqual(en.languages, {it: 'Italian', en: 'English'});
 assert.equal(it.fields.display_name, undefined);
 assert.equal(en.fields.display_name, undefined);
});
test('record counts use singular and plural in both locales', () => {
 const italian = createTranslator({locale: 'it', messages: it, namespace: 'app'});
 const english = createTranslator({locale: 'en', messages: en, namespace: 'app'});
 assert.equal(italian('records', {count: 1}), 'elemento');
 assert.equal(italian('records', {count: 2}), 'elementi');
 assert.equal(english('records', {count: 1}), 'record');
 assert.equal(english('records', {count: 2}), 'records');
});
test('Italian and English cover every resource, field and stable contract error',()=>{
 for(const section of ['app','resources','fields','errors'])assert.deepEqual(Object.keys(it[section]).sort(),Object.keys(en[section]).sort());
 // Resource labels also include local navigation containers; these are not CRUD resources.
 // settings-system-catalog is a retained label for the former route, not an authority.
 const navigationLabels=['settings','catalog','settings-catalog','settings-system','settings-master-data','settings-system-catalog','tax-management'];
 assert.deepEqual(Object.keys(it.resources).sort(),[...resourceKeys,...navigationLabels].sort());
 for(const field of ['code','name','description','is_enabled','company_id','site_id','warehouse_type_id','warehouse_id','site_type','vat_number','tax_code','address','city','province','postal_code','country_code','key','value','username','first_name','last_name','date_of_birth','phone_number','preferred_language','email']){assert.ok(it.fields[field]);assert.ok(en.fields[field])}
 for(const code of ['invalid_credentials','validation_error','forbidden','not_found','conflict','password_change_required','rate_limited','server_error']){assert.ok(it.errors[code]);assert.ok(en.errors[code])}
});
