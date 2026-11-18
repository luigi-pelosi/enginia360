import test from "node:test";
import assert from "node:assert/strict";
import {harness, session, find} from "./workspace-harness.ts";
const props = {resource: {key: "companies", fields: [{name: "name", type: "text", required: true}]}, row: {id: "c", name: "Old"}, canWrite: true, session, scope: (p: string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onSessionRefresh: async () => session, onError: () => "error"};
test("rapid repeated submit issues only one write while awaiting commit", async () => {
  const h = harness("it", {0: {name: "New"}}, {id: "c"});
  const submit = find(h.components.RecordEditor(props), n => n.props?.id === "record-form").props.onSubmit;
  await Promise.all([submit({preventDefault() {}}), submit({preventDefault() {}})]);
  assert.equal(h.apiCalls.length, 1);
});
