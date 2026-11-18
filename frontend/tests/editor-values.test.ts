import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
import ts from "typescript";
import {normalizeValues, type Resource, type Row} from "../lib/model.ts";

const source = readFileSync(new URL("../components/workspace.tsx", import.meta.url), "utf8");
const start = source.indexOf("  const [values, setValues]");
const end = source.indexOf("    [refs, setRefs]", start);
const initializer = source.slice(start, end).trim().replace(/,$/, ";");
const code = ts.transpileModule(initializer, {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
const users: Resource = {key: "users", fields: [
  {name: "username", type: "text", required: true},
  {name: "first_name", type: "text", required: true},
  {name: "last_name", type: "text", required: true},
  {name: "email", type: "text", required: true},
  {name: "date_of_birth", type: "date", required: false},
  {name: "phone_number", type: "tel", required: false},
  {name: "preferred_language", type: "select", required: false, options: ["it", "en"], defaultValue: "it"},
  {name: "is_enabled", type: "boolean", required: true},
]};
function initialValues(resource: Resource, row: Row | null): Record<string, unknown> {
  const result = runInNewContext(`${code}; values`, {resource, row, useState: (initialize: () => unknown) => [initialize(), () => {}]});
  // VM objects have their own prototype; compare the serializable transport shape.
  return JSON.parse(JSON.stringify(result));
}
test("new metadata user editor initializes Italian, empty detail fields, enabled boolean", () => {
  const values = initialValues(users, null);
  assert.deepEqual(values, {username: "", first_name: "", last_name: "", email: "", date_of_birth: "", phone_number: "", preferred_language: "it", is_enabled: true});
  assert.deepEqual(normalizeValues(users.fields, values), {...values, date_of_birth: null, phone_number: null});
});
test("editing preserves stored details and English, absent optional values use metadata default", () => {
  const row = {id: "user", username: "ada", first_name: "Ada", last_name: "Lovelace", email: "ada@example.test", date_of_birth: "2000-02-29", phone_number: "+39 123", preferred_language: "en", is_enabled: false};
  const {id: _id, ...details} = row;
  assert.deepEqual(initialValues(users, row), details);
  assert.equal(initialValues(users, {...row, preferred_language: null}).preferred_language, "it");
});
test("non-user metadata editor defaults and JSON formatting stay unchanged", () => {
  const resource: Resource = {key: "settings", fields: [
    {name: "key", type: "text", required: true},
    {name: "value", type: "json", required: true},
    {name: "site_id", type: "reference", required: false},
    {name: "is_enabled", type: "boolean", required: true},
  ]};
  assert.deepEqual(initialValues(resource, null), {key: "", value: "{}", site_id: "", is_enabled: true});
  assert.equal(initialValues(resource, {id: "setting", value: {a: 1}}).value, '{\n  "a": 1\n}');
});
