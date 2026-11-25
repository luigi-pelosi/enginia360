import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import * as model from "../lib/model.ts";
import {harness, session, workspace, source} from "./workspace-harness.ts";
const resource = {key: "permissions", readOnly: true, fields: [{name: "code", type: "text" as const, required: true}, {name: "name", type: "text" as const, required: true}]};
const row = {id: "p", code: "warehouse-types.create", name: "RAW LEGACY NAME"};
const messages = (locale: string) => JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), "utf8"));
for (const [locale, label] of [["it", "Tipi di magazzino · Creazione"], ["en", "Warehouse types · Create"]]) {
  test(`${locale}: permission table uses code-derived localized label`, () => {
    const html = workspace(resource, ["permissions.read"], row, locale);
    assert.ok(html.includes(label), "table localized label");
    assert.ok(html.includes(row.code), "stable code remains visible");
    assert.ok(!html.includes(row.name), "table never reuses stored permission name");
  });
  test(`${locale}: permission details use code-derived localized label`, () => {
    const editor = harness(locale).render("RecordEditor", {resource, row, canWrite: false, session, scope: (p: string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onError: () => "error"});
    assert.ok(editor.includes(label), "detail localized label");
    assert.ok(!editor.includes(row.name));
  });
  test(`${locale}: permission assignment checkbox uses code-derived localized label`, () => {
    const links = harness(locale).render("RelationEditor", {draft: {options: [row], ids: [row.id], initialIds: []}, onIdsChange() {}, relation: "role-permissions", target: "permissions", ownerId: "r", editable: true, allowedRead: true, scope: (p: string) => p, load: async () => [], onError: () => "error", onChanged: async () => {}});
    assert.ok(links.includes(`aria-label="${label}"`), "checkbox localized accessible name");
    assert.ok(links.includes(row.code));
    assert.ok(!links.includes(row.name));
  });
}
test("permission search matches localized labels in both languages and stable codes", () => {
  assert.equal(typeof model.permissionMatches, "function", "shared bilingual matcher exists");
  for (const query of ["Tipi di magazzino", "Creazione", "Warehouse types", "Create", "warehouse-types.create"])
    assert.equal(model.permissionMatches(row, query, [messages("it"), messages("en")]), true, query);
  assert.equal(model.permissionMatches(row, "RAW LEGACY NAME", [messages("it"), messages("en")]), false);
  assert.equal(model.permissionMatches(row, "delete", [messages("it"), messages("en")]), false);
});
test("all supported permission actions have IT/EN translations", () => {
  for (const locale of ["it", "en"])
    for (const action of ["read", "create", "update", "delete", "reset_password", "assign", "assign_users", "assign_permissions", "assign_scope"])
      assert.ok(messages(locale).permissionActions?.[action], `${locale}:${action}`);
});
test("permission list applies bilingual search before client pagination, without backend raw-name filtering", async () => {
  const h = harness("it", {0: {...session, permissions: ["permissions.read"]}, 1: false, 5: [resource], 6: "permissions", 7: "t", 12: "Warehouse types", 13: "Warehouse types"}, {items: [row], total: 1, page: 1, pageSize: 100});
  h.render("default");
  h.effects.find(effect => String(effect).includes("pageSize=25"))!();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.ok(h.apiCalls.some(path => path.includes("pageSize=100") && !path.includes("search=")), "load complete finite catalog before filtering");
  assert.deepEqual(JSON.parse(JSON.stringify(h.updates[9])), [row]);
  assert.equal(h.updates[10], 1);
});
test("permission assignment filter accepts either language without using stored names", () => {
  for (const query of ["Creazione", "Create", "warehouse-types.create"])
    assert.ok(harness("it", {0: query}).render("RelationEditor", {draft: {options: [row], ids: [row.id], initialIds: []}, onIdsChange() {}, relation: "role-permissions", target: "permissions", ownerId: "r", editable: false, allowedRead: true, scope: (p: string) => p, load: async () => [], onError: () => "error"}).includes("Tipi di magazzino · Creazione"));
});
test("permission catalog keeps all 50 filtered rows without pagination", async () => {
  const catalog = Array.from({length: 50}, (_, index) => ({...row, id: `p-${index}`}));
  const h = harness("en", {0: {...session, permissions: ["permissions.read"]}, 1: false, 5: [resource], 6: "permissions", 7: "t", 11: 2, 13: "Creazione"}, {items: catalog, total: catalog.length, page: 1, pageSize: 100});
  h.render("default");
  h.effects.find(effect => String(effect).includes("pageSize=25"))!();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(JSON.parse(JSON.stringify(h.updates[9])), catalog);
  assert.equal(h.updates[10], catalog.length);
});
