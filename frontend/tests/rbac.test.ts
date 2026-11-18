import test from "node:test";
import assert from "node:assert/strict";
import {can} from "../lib/model.ts";

const tenant = {isSuperAdmin: false, tenantId: "tenant", permissions: [] as string[]};
const global = {isSuperAdmin: true, tenantId: null, permissions: [] as string[]};
test("companies.create does not imply update", () => {
  const session = {...tenant, permissions: ["companies.create"]};
  assert.equal(can(session, "companies", "create"), true);
  assert.equal(can(session, "companies", "update"), false);
});
test("legacy write never grants an action, including write itself", () => {
  const session = {...tenant, permissions: ["companies.write"]};
  for (const action of ["read", "create", "update", "delete", "write"])
    assert.equal(can(session, "companies", action), false, action);
  assert.equal(can(global, "companies", "write"), false);
});
test("permissions is read-only even for global administrators", () => {
  for (const session of [global, {...tenant, permissions: ["permissions.read", "permissions.create", "permissions.update", "permissions.delete"]}]) {
    assert.equal(can(session, "permissions", "read"), true);
    for (const action of ["create", "update", "delete", "write", "assign"])
      assert.equal(can(session, "permissions", action), false, action);
  }
});
test("unknown resources/actions fail closed and only true global administrators control tenants", () => {
  for (const [resource, action] of [["future", "read"], ["companies", "assign"], ["tenants", "reset_password"]])
    assert.equal(can(global, resource, action), false);
  assert.equal(can(global, "tenants", "create"), true);
  assert.equal(can({...global, tenantId: "tenant"}, "tenants", "read"), false);
  assert.equal(can({...tenant, permissions: ["tenants.read"]}, "tenants", "read"), false);
});
test("all 50 tenant catalog actions are exact, including hyphenated resource keys", () => {
  const mutable = ["companies", "sites", "sales-organizations", "purchasing-organizations", "warehouse-types", "warehouses", "warehouse-locations", "settings", "users", "groups", "roles"];
  const codes = mutable.flatMap(resource => ["read", "create", "update", "delete"].map(action => `${resource}.${action}`));
  codes.push("permissions.read", "users.reset_password", "roles.assign", "groups.assign_users", "roles.assign_permissions", "purchasing-organizations.assign_scope");
  assert.equal(codes.length, 50);
  for (const code of codes) {
    const [resource, action] = code.split(".");
    assert.equal(can({...tenant, permissions: [code]}, resource, action), true, code);
    assert.equal(can({...tenant, permissions: []}, resource, action), false, code);
  }
});
