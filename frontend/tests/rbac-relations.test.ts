import test from "node:test";
import assert from "node:assert/strict";
import * as model from "../lib/model.ts";
import {harness, session} from "./workspace-harness.ts";
const cases = [
  ["users", "roles", "user-roles", "roles.assign", "Ruoli utente"],
  ["groups", "roles", "group-roles", "roles.assign", "Ruoli del gruppo"],
  ["groups", "users", "group-users", "groups.assign_users", "Utenti del gruppo"],
  ["roles", "permissions", "role-permissions", "roles.assign_permissions", "Permessi del ruolo"],
];
for (const [owner, target, relation, grant, label] of cases) {
  const row = {id: "record", tenant_id: "t", name: "Example"};
  const props = {resource: {key: owner, fields: []}, row, canWrite: false, scope: (p: string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onError: () => "error"};
  test(`${relation}: exact assignment grant manages links while record stays read-only`, () => {
    const permissions = [`${owner}.read`, `${target}.read`, grant];
    const html = harness("it").render("RecordEditor", {...props, session: {...session, permissions}});
    assert.equal((html.match(/>Salva</g) ?? []).length, 1, "one footer Save independent of record update");
    assert.doesNotMatch(html, /Salva ·/);
    assert.match(html, /fieldset disabled/);
    const withoutGrant = harness("it").render("RecordEditor", {...props, session: {...session, permissions: [`${owner}.read`, `${target}.read`, `${owner}.update`]}});
    assert.doesNotMatch(withoutGrant, />Salva</, "owner.update is not assignment authority");
  });
  test(`${relation}: reads need owner and target read, not assignment permission`, () => {
    const html = harness("it").render("RecordEditor", {...props, session: {...session, permissions: [`${owner}.read`, `${target}.read`]}});
    assert.ok(html.includes(`<h3>${label}</h3>`));
    const denied = harness("it").render("RecordEditor", {...props, session: {...session, permissions: [`${target}.read`, grant]}});
    assert.ok(!denied.includes(`<h3>${label}</h3>`), "missing owner.read hides relation");
  });
}
test("global user self record stays non-associable", () => {
  const html = harness("it").render("RecordEditor", {resource: {key: "users", fields: []}, row: {id: "self", tenant_id: null}, canWrite: false, session: {...session, isSuperAdmin: true, tenantId: null}, scope: (p: string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onError: () => "error"});
  assert.doesNotMatch(html, /<h3>Ruoli utente/);
});
