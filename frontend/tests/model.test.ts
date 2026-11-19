import test from "node:test";
import assert from "node:assert/strict";
import * as model from "../lib/model.ts";
import { can, normalizeValues, resourceKeys, rowLabel } from "../lib/model.ts";
test("user labels use first and last names, never persisted display names", () => {
  assert.equal(rowLabel({id: "u", username: "ada", first_name: "Ada", last_name: "Lovelace", display_name: "Old name"}), "Ada Lovelace");
  assert.equal(rowLabel({id: "u", username: "ada", display_name: "Old name"}), "ada");
  assert.equal(rowLabel({id: "c", name: "Company", code: "C"}), "Company");
  assert.equal(rowLabel({id: "s", name: "Site", postal_code: "00100", province: "RM"}), "Site");
});
test("optional user blanks become null while metadata language default is maintained", () => {
  const fields = [
    {name: "date_of_birth", type: "date" as const, required: false},
    {name: "phone_number", type: "tel" as const, required: false},
    {name: "preferred_language", type: "select" as const, required: false, options: ["it", "en"], defaultValue: "it"},
  ];
  assert.deepEqual(normalizeValues(fields, {date_of_birth: "", phone_number: "", preferred_language: ""}), {date_of_birth: null, phone_number: null, preferred_language: "it"});
  assert.deepEqual(normalizeValues(fields, {date_of_birth: "2000-02-29", phone_number: "+39 123", preferred_language: "en"}), {date_of_birth: "2000-02-29", phone_number: "+39 123", preferred_language: "en"});
});
test("table dates and language values are localized without timezone day shift", () => {
  assert.equal(typeof model.formatFieldValue, "function", "metadata table formatter is available");
  const date = {name: "date_of_birth", type: "date" as const, required: false};
  const language = {name: "preferred_language", type: "select" as const, required: false};
  for (const timezone of ["America/Los_Angeles", "Pacific/Kiritimati", "Europe/Rome"]) {
    process.env.TZ = timezone;
    assert.equal(model.formatFieldValue(date, "2000-02-29", "it", code => ({it: "Italiano", en: "Inglese"})[code]), "29/02/2000");
    assert.equal(model.formatFieldValue(date, "2000-02-29", "en", code => ({it: "Italian", en: "English"})[code]), "02/29/2000");
  }
  assert.equal(model.formatFieldValue(date, null, "it", () => ""), "—");
  assert.equal(model.formatFieldValue(date, "bad-date", "it", () => ""), "bad-date");
  assert.equal(model.formatFieldValue(language, "en", "it", code => ({it: "Italiano", en: "Inglese"})[code]), "Inglese");
  assert.equal(model.formatFieldValue(language, "it", "en", code => ({it: "Italian", en: "English"})[code]), "Italian");
});
test("all resources including BP and its virtual numbering settings are supported", () => {
  assert.equal(resourceKeys.length, 18);
  assert.ok(resourceKeys.includes("business-partner-companies"));
  assert.ok(resourceKeys.includes("business-partners"));
  assert.ok(resourceKeys.includes("business-partner-numbering"));
});
test("permission gates use exact grants and global administrator", () => {
  assert.equal(
    can({ isSuperAdmin: false, permissions: ["users.read"] }, "users", "write"),
    false,
  );
  assert.equal(
    can({ isSuperAdmin: false, permissions: ["users.read"] }, "users", "read"),
    true,
  );
  assert.equal(
    can(
      { isSuperAdmin: false, permissions: ["tenants.read"] },
      "tenants",
      "read",
    ),
    false,
  );
  assert.equal(
    can({ isSuperAdmin: true, tenantId: null, permissions: [] }, "tenants", "create"),
    true,
  );
});
for (const action of ["create", "update", "delete", "reset_password"]) {
  test(`global user rows deny ${action} even for SuperAdmin or exact grants`, () => {
    for (const session of [
      {isSuperAdmin: true, tenantId: null, permissions: []},
      {isSuperAdmin: false, permissions: [`users.${action}`]},
    ]) {
      assert.equal(can(session, "users", action, {id: "global", tenant_id: null}), false);
      assert.equal(can(session, "users", action, {id: "tenant-user", tenant_id: "tenant"}), true);
      assert.equal(can(session, "users", action, {id: "legacy"}), true);
      assert.equal(can(session, "users", action, null), true);
      assert.equal(can(session, "users", action), true);
    }
    assert.equal(can({isSuperAdmin: false, permissions: []}, "users", action, {id: "tenant-user", tenant_id: "tenant"}), false);
    assert.equal(can({isSuperAdmin: true, tenantId: null, permissions: []}, "companies", action, {id: "company", tenant_id: null}), action !== "reset_password");
  });
}
test("global user read access still requires the normal grant or SuperAdmin", () => {
  const row = {id: "global", tenant_id: null};
  assert.equal(can({isSuperAdmin: true, tenantId: null, permissions: []}, "users", "read", row), true);
  assert.equal(can({isSuperAdmin: false, permissions: ["users.read"]}, "users", "read", row), true);
  assert.equal(can({isSuperAdmin: false, permissions: []}, "users", "read", row), false);
});
test("user relation choices exclude only explicit null-tenant global users", () => {
  const rows = [
    {id: "global", tenant_id: null},
    {id: "tenant-user", tenant_id: "tenant"},
    {id: "legacy"},
    {id: "disabled", tenant_id: "tenant", is_enabled: false},
  ];
  assert.equal(typeof model.relationOptions, "function");
  assert.deepEqual(model.relationOptions("users", rows), rows.slice(1));
  assert.deepEqual(model.relationOptions("roles", rows), rows);
  assert.equal(rows.length, 4, "list data is not mutated");
  assert.deepEqual(model.relationOptions("users", []), []);
});
test("Radix controlled booleans and references preserve transport types", () => {
  const fields = [
    {name: "is_enabled", type: "boolean" as const, required: true},
    {name: "company_id", type: "reference" as const, required: true},
    {name: "site_id", type: "reference" as const, required: false},
  ];
  assert.deepEqual(normalizeValues(fields, {is_enabled: false, company_id: "company-id", site_id: ""}), {is_enabled: false, company_id: "company-id", site_id: null});
  assert.deepEqual(normalizeValues(fields, {is_enabled: true, company_id: "company-id", site_id: "site-id"}), {is_enabled: true, company_id: "company-id", site_id: "site-id"});
});
test("JSON and optional reference fields are serialized correctly", () => {
  assert.deepEqual(
    normalizeValues(
      [
        { name: "value", type: "json", required: true },
        { name: "site_id", type: "reference", required: false },
      ],
      { value: '{"a":1}', site_id: "" },
    ),
    { value: { a: 1 }, site_id: null },
  );
  assert.throws(() =>
    normalizeValues([{ name: "value", type: "json", required: true }], {
      value: "bad",
    }),
  );
});
