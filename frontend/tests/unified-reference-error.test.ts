import test from "node:test";
import assert from "node:assert/strict";
import {harness, session, find} from "./workspace-harness.ts";
test("a failed reference load keeps Save blocked after loading finishes", async () => {
  const props = {resource: {key: "sites", fields: [{name: "name", type: "text", required: true}, {name: "company_id", type: "reference", reference: "companies", required: true}]}, row: {id: "s", name: "Old", company_id: "c"}, canWrite: true, session, scope: (p: string) => p, load: async () => {throw new Error("network")}, onClose() {}, onSaved: async () => {}, onError: () => "load failed"};
  const state = {0: {name: "New", company_id: "c"}};
  const h = harness("it", state);
  h.components.RecordEditor(props);
  h.effects[1]();
  await new Promise(resolve => setTimeout(resolve, 0));
  const retry = harness("it", {...state, ...h.updates});
  const tree = retry.components.RecordEditor(props);
  assert.equal(find(tree, n => n.props?.form === "record-form").props.disabled, true);
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(retry.apiCalls, []);
});
