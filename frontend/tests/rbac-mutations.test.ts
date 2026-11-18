import test from "node:test";
import assert from "node:assert/strict";
import {harness, session, find} from "./workspace-harness.ts";
const base = {scope: (p: string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onError: () => "error", session};
test("read-only form submit cannot issue a record mutation", async () => {
  const h = harness();
  const tree = h.components.RecordEditor({...base, resource: {key: "companies", fields: []}, row: {id: "c"}, canWrite: false});
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(h.apiCalls, []);
});
test("read-only relation handlers cannot mutate parent draft or transport", () => {
  let changes = 0;
  const h = harness();
  const tree = h.components.RelationEditor({relation: "user-roles", target: "roles", ownerId: "u", editable: false, allowedRead: true, draft: {options: [{id: "r", name: "Role"}], ids: [], initialIds: []}, onIdsChange: () => changes++});
  const checkbox = find(tree, n => n.props?.id === "user-roles-u-r");
  checkbox.props.onCheckedChange(true);
  assert.equal(changes, 0);
  assert.deepEqual(h.apiCalls, []);
});
