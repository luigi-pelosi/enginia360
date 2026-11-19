import test from "node:test";
import assert from "node:assert/strict";
import * as model from "../lib/model.ts";

import {catalog} from "./permission-catalog.ts";
test("groups the exact 61 catalog IDs by domain and action order, including operational company roles and virtual numbering settings", () => {
  assert.equal(typeof model.groupPermissions, "function", "permission grouping is available");
  const tree = model.groupPermissions(catalog);
  assert.deepEqual(tree.map(domain => [domain.key, domain.resources.flatMap(model.permissionRows).length]), [["masterData", 8], ["organization", 17], ["warehouse", 12], ["administration", 24]]);
  assert.deepEqual(tree.flatMap(domain => domain.resources.map(resource => resource.key)), model.navigationSections.flatMap(section => section.keys).filter(key => !["tenants", "countries", "cities"].includes(key)));
  const ids = tree.flatMap(domain => domain.resources.flatMap(model.permissionRows).map(row => row.id));
  assert.equal(ids.length, 61);
  assert.equal(new Set(ids).size, 61);
  assert.deepEqual([...ids].sort(), catalog.map(row => row.id).sort());
  assert.deepEqual(tree.find(domain => domain.key === "administration")!.resources.find(resource => resource.key === "roles")!.rows.map(row => row.code), ["roles.read", "roles.create", "roles.update", "roles.delete", "roles.assign", "roles.assign_companies", "roles.assign_permissions"]);
});
test("keeps unknown codes visible in an explicit fallback, deduplicating IDs", () => {
  assert.equal(typeof model.groupPermissions, "function", "permission grouping is available");
  const unknown = [{id: "x", code: "future.export"}, {id: "y", code: "constructor.read"}];
  const tree = model.groupPermissions([...unknown, ...unknown, {id: "z", code: "roles.future"}]);
  assert.deepEqual(tree.flatMap(domain => domain.resources.flatMap(resource => resource.rows.map(row => row.id))).sort(), ["x", "y", "z"]);
  assert.equal(tree.find(domain => domain.key === "administration")!.resources[0].key, "roles");
  assert.equal(tree.at(-1)!.key, "other");
});
test("settings catalogs follow their routes without inventing parent grants", () => {
  const rows = ["countries.read", "cities.read", "business-partner-numbering.update"].map(code => ({id: code, code}));
  const tree = model.groupPermissions(rows);
  assert.equal(tree.length, 1);
  assert.equal(tree[0].key, "administration");
  const settings = tree[0].resources[0];
  assert.equal(settings.key, "settings");
  assert.deepEqual(settings.rows, []);
  assert.deepEqual(settings.children.map(branch => branch.key), ["settings-master-data", "countries", "cities"]);
  assert.deepEqual(model.permissionRows(settings).map(row => row.id).sort(), rows.map(row => row.id).sort());
});
