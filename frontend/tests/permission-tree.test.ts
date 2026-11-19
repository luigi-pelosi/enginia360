import test from "node:test";
import assert from "node:assert/strict";
import * as model from "../lib/model.ts";

import {catalog} from "./permission-catalog.ts";
test("groups the exact 55 catalog IDs by domain and action order, including virtual numbering settings", () => {
  assert.equal(typeof model.groupPermissions, "function", "permission grouping is available");
  const tree = model.groupPermissions(catalog);
  assert.deepEqual(tree.map(domain => [domain.key, domain.resources.reduce((n, resource) => n + resource.rows.length, 0)]), [["masterData", 5], ["organization", 17], ["warehouse", 12], ["administration", 21]]);
  assert.deepEqual(tree.flatMap(domain => domain.resources.map(resource => resource.key)), model.navigationSections.flatMap(section => section.label === "masterData" ? [...section.keys, "business-partner-numbering"] : section.keys).filter(key => !["tenants", "countries", "cities"].includes(key)));
  const ids = tree.flatMap(domain => domain.resources.flatMap(resource => resource.rows.map(row => row.id)));
  assert.equal(ids.length, 55);
  assert.equal(new Set(ids).size, 55);
  assert.deepEqual([...ids].sort(), catalog.map(row => row.id).sort());
  assert.deepEqual(tree.find(domain => domain.key === "administration")!.resources.find(resource => resource.key === "roles")!.rows.map(row => row.code), ["roles.read", "roles.create", "roles.update", "roles.delete", "roles.assign", "roles.assign_permissions"]);
});
test("keeps unknown codes visible in an explicit fallback, deduplicating IDs", () => {
  assert.equal(typeof model.groupPermissions, "function", "permission grouping is available");
  const unknown = [{id: "x", code: "future.export"}, {id: "y", code: "malformed"}];
  const tree = model.groupPermissions([...unknown, ...unknown, {id: "z", code: "roles.future"}]);
  assert.deepEqual(tree.flatMap(domain => domain.resources.flatMap(resource => resource.rows.map(row => row.id))).sort(), ["x", "y", "z"]);
  assert.equal(tree.find(domain => domain.key === "administration")!.resources[0].key, "roles");
  assert.equal(tree.at(-1)!.key, "other");
});
