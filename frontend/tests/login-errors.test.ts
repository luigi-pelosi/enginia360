import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

for (const locale of ['it','en']) {
  const errors = JSON.parse(readFileSync(new URL(`../messages/${locale}.json`,import.meta.url),'utf8')).errors;
  test(`login diagnostic messages identify the relevant fields and account states (${locale})`, () => {
    for (const key of ['invalid_organization_code','login_details_invalid','account_disabled','account_temporarily_locked']) assert.equal(typeof errors[key],'string',key);
    for (const word of locale==='it' ? ['nome utente','password','codice organizzazione'] : ['username','password','organization code']) assert.ok(errors.login_details_invalid.toLowerCase().includes(word),word);
    assert.match(errors.invalid_organization_code,locale==='it' ? /organizzazione/i : /organization/i);
    assert.match(errors.account_disabled,locale==='it' ? /amministratore/i : /administrator/i);
  });
}
