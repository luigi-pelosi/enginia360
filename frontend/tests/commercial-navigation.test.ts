import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {can, navigationSections, permissionLabel, groupPermissions} from "../lib/model.ts";
import {workspace, session} from "./workspace-harness.ts";
import {catalog} from "./permission-catalog.ts";
for (const locale of ["it", "en"]) test(`commercial navigation and precise authorities ${locale}`, () => {
  const messages = JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), "utf8"));
  for (const key of ["sales-organizations", "purchasing-organizations"]) {
    assert.ok(navigationSections.find(section => section.label === "organization")?.keys.includes(key), `${key} belongs to Organization`);
    const s = {...session, permissions: [`${key}.read`]};
    assert.equal(can(s, key, "read"), true);
    assert.equal(can(s, key, "update"), false);
    assert.ok(workspace({key, fields: []}, s.permissions, {id: "org"}, locale).includes(messages.resources[key]));
    assert.equal(permissionLabel({id: "p", code: `${key}.read`}, messages), `${messages.resources[key]} · ${messages.permissionActions.read}`);
  }
  assert.equal(can({...session, permissions: ["purchasing-organizations.assign_scope"]}, "purchasing-organizations", "assign_scope"), true);
  assert.equal(can({...session, permissions: ["sales-organizations.assign_scope"]}, "sales-organizations", "assign_scope"), false);
  assert.equal(permissionLabel({id: "scope", code: "purchasing-organizations.assign_scope"}, messages), `${messages.resources["purchasing-organizations"]} · ${messages.permissionActions.assign_scope}`);
});
test("commercial catalog is finite and grouped by the shared taxonomy", () => {
  assert.equal(catalog.length, 55);
  assert.deepEqual(groupPermissions(catalog).map(d => [d.key, d.resources.reduce((n,r) => n + r.rows.length, 0)]), [["masterData",5],["organization",17],["warehouse",12],["administration",21]]);
});
