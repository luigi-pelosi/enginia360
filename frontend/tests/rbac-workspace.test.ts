import test from "node:test";
import assert from "node:assert/strict";
import {harness, session, workspace} from "./workspace-harness.ts";
const companies = {key: "companies", fields: [{name: "name", type: "text" as const, required: true}]};
const users = {...companies, key: "users"};
const row = {id: "record", tenant_id: "t", name: "Example"};
test("create-only workspace offers New but the existing row remains Details", () => {
  const html = workspace(companies, ["companies.read", "companies.create"], row);
  assert.match(html, />Nuovo</);
  assert.match(html, /aria-label="Dettagli Example"/);
  assert.doesNotMatch(html, /aria-label="Modifica Example"/);
});
test("update-only workspace offers Edit but not New", () => {
  const html = workspace(companies, ["companies.read", "companies.update"], row);
  assert.match(html, /aria-label="Modifica Example"/);
  assert.doesNotMatch(html, />Nuovo</);
});
test("reset password is independent of updating a user", () => {
  const reset = workspace(users, ["users.read", "users.reset_password"], row);
  assert.match(reset, /aria-label="Imposta password Example"/);
  assert.match(reset, /aria-label="Dettagli Example"/);
  const update = workspace(users, ["users.read", "users.update"], row);
  assert.doesNotMatch(update, /aria-label="Imposta password Example"/);
});
test("read-only metadata hides create/edit/delete even with exact grants", () => {
  const html = workspace({...companies, readOnly: true}, ["companies.read", "companies.create", "companies.update", "companies.delete"], row);
  assert.doesNotMatch(html, />Nuovo</);
  assert.doesNotMatch(html, /aria-label="(?:Modifica|Elimina) Example"/);
});
