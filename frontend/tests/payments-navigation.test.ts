import test from "node:test";
import assert from "node:assert/strict";
import {can, navigationSections, navigationPath} from "../lib/model.ts";
test("payments navigation and permissions are independent", () => {
  assert.ok(navigationSections.find(s => s.label === "masterData")?.keys.includes("payments"));
  assert.deepEqual(navigationPath("payment-terms"), ["payments", "payment-terms"]);
  const s = {isSuperAdmin:false, tenantId:"t", permissions:["payment-terms.read"]};
  assert.equal(can(s, "payment-terms", "read"), true);
  assert.equal(can(s, "payment-methods", "read"), false);
  assert.equal(can(s, "payment-terms", "update"), false);
});
