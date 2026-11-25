import test from "node:test";
import assert from "node:assert/strict";
import {harness, session} from "./workspace-harness.ts";
import {permissionMatches} from "../lib/model.ts";
import {catalog} from "./permission-catalog.ts";
import {readFileSync} from "node:fs";
const messages = ["it", "en"].map(locale => JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), "utf8")));
const rows = ["companies.read", "warehouse-types.create", "roles.assign_permissions"].map(code => ({id: code, code}));
const props = {onIdsChange() {}, relation: "role-permissions", target: "permissions", ownerId: "r", editable: true, allowedRead: true, scope: (p: string) => p, load: async () => [], onError: () => "error", onChanged: async () => true};
for (const [locale, domain, resource] of [["it", "Organizzazione", "Aziende"], ["en", "Organization", "Companies"]]) {
  test(`${locale}: catalog has two closed accessible levels, all leaves, details and no pagination`, () => {
    const h = harness(locale, {0: {...session, permissions: ["permissions.read"]}, 1: false, 5: [{key: "permissions", fields: [], readOnly: true}], 6: "permissions", 7: "t", 9: rows, 10: 3});
    const html = h.render("default");
    assert.equal((html.match(/data-permission-domain=/g) ?? []).length, 3);
    assert.equal((html.match(/data-permission-resource=/g) ?? []).length, 3);
    assert.equal((html.match(/data-permission-code=/g) ?? []).length, 3);
    assert.match(html, new RegExp(`<summary[^>]*aria-label="${domain}"`));
    assert.match(html, new RegExp(`<summary[^>]*aria-label="${resource}"`));
    assert.doesNotMatch(html, /<details[^>]* open/);
    assert.doesNotMatch(html, /class="pagination"/);
    assert.ok(html.includes(`${locale === "it" ? "Dettagli" : "Details"} ${resource}`));
  });
}
test("domain search is bilingual and opens only matching branches in the role selector", () => {
  for (const query of ["Organization", "Organizzazione", "Warehouse", "Magazzino", "Administration", "Amministrazione"]) {
    const expected = query.match(/Organization|Organizzazione/) ? rows[0] : query.match(/Warehouse|Magazzino/) ? rows[1] : rows[2];
    assert.equal(permissionMatches(expected, query, messages), true, query);
    const html = harness("it", {0: query}).render("RelationEditor", {...props, draft: {options: rows, ids: rows.map(row => row.id), initialIds: []}});
    assert.equal((html.match(/data-permission-domain=/g) ?? []).length, 1);
    assert.equal((html.match(/<details[^>]* open/g) ?? []).length, 2);
    assert.equal((html.match(/data-permission-code=/g) ?? []).length, 1);
    assert.ok(html.includes(`data-permission-code="${expected.code}"`));
  }
});
test("readonly selector preserves checked IDs, disabled badge and selected/visible branch counts", () => {
  const html = harness("en", {0: "Organization"}).render("RelationEditor", {...props, editable: false, draft: {options: rows.map(row => ({...row, is_enabled: false})), ids: rows.map(row => row.id), initialIds: []}});
  assert.match(html, /type="checkbox"[^>]*checked/);
  assert.match(html, /disabled/);
  assert.ok(html.includes(messages[1].app.disabled));
  assert.ok(html.includes("1/1"));
  assert.doesNotMatch(html, /Save ·/);
});
test("filtered selector edits a parent-owned draft without sending a request", () => {
  let ids: string[] = [];
  const h = harness("en", {0: "Organization"});
  const tree = h.components.RelationEditor({...props, draft: {options: rows, ids: rows.map(row => row.id), initialIds: []}, onIdsChange: (next: string[]) => {ids = next}});
  const permissionTree = tree.props.children[2].props.children;
  permissionTree.props.onSelectedIdsChange([...rows.map(row => row.id), "hidden"]);
  assert.deepEqual([...ids], [...rows.map(row => row.id), "hidden"]);
  assert.deepEqual(h.apiCalls, []);
});
test("full SSR catalog and selector render all 60 stable IDs exactly once with consistent branch counts", () => {
  const html = harness("en").render("RelationEditor", {...props, draft: {options: catalog, ids: catalog.slice(0, 5).map(row => row.id), initialIds: []}});
  assert.equal((html.match(/data-permission-code=/g) ?? []).length, 60);
  assert.equal((html.match(/data-permission-domain=/g) ?? []).length, 4);
  assert.equal((html.match(/data-permission-resource=/g) ?? []).length, 21);
  for (const row of catalog) assert.equal(html.split(`data-permission-code="${row.code}"`).length - 1, 1, row.code);
  assert.ok(html.includes("3/8"));
  assert.ok(html.includes("0/17"));
  assert.ok(html.includes("0/12"));
  assert.ok(html.includes("2/23"));
  assert.doesNotMatch(html, /<details[^>]* open/);
});
test("action and resource searches filter leaves at every depth and counts reflect original branch scopes", () => {
  for (const [query, count, domains] of [["Create", 12, 4], ["Lettura", 17, 4], ["roles.assign_permissions", 1, 1], ["Organization", 17, 1], ["Anagrafiche", 10, 2], ["Master data", 10, 2], ["Magazzino", 12, 1], ["Administration", 23, 1], ["Settings", 5, 1], ["Impostazioni", 5, 1], ["no matching permission", 0, 0]] as const) {
    const html = harness("en", {0: query}).render("RelationEditor", {...props, draft: {options: catalog, ids: catalog.map(row => row.id), initialIds: []}});
    assert.equal((html.match(/data-permission-code=/g) ?? []).length, count, query);
    assert.equal((html.match(/data-permission-domain=/g) ?? []).length, domains, query);
    if (query === "Create") for (const branchCount of [17, 12, 23]) assert.ok(html.includes(`${branchCount}/${branchCount}`));
  }
});
test("other relation editors remain flat", () => {
  const html = harness("en").render("RelationEditor", {...props, relation: "group-users", target: "users", draft: {options: [{id: "u", name: "Ada"}], ids: ["u"], initialIds: []}});
  assert.doesNotMatch(html, /data-permission-/);
  assert.match(html, /aria-label="Ada"/);
});
