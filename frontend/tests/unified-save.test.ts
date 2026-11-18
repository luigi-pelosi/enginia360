import test from "node:test";
import assert from "node:assert/strict";
import {harness, session} from "./workspace-harness.ts";
export function find(node: any, predicate: (node: any) => boolean): any {
  if (!node || typeof node !== "object") return;
  if (predicate(node)) return node;
  for (const child of [node.props?.children].flat(Infinity)) {const result = find(child, predicate); if (result) return result;}
}
const props = {resource: {key: "companies", fields: [{name: "name", type: "text", required: true}]}, row: {id: "c", name: "Old"}, canWrite: true, session, scope: (p: string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onSessionRefresh: async () => session, onError: () => "error"};
export {props as recordProps};
test("assignment-only unified Save omits values, preserves hidden IDs and has no child Save", async () => {
  const h = harness("it", {4: false, 5: {"role-permissions": {options: [], initialIds: ["old"], ids: ["old", "hidden"]}}, 6: false, 7: ""}, {id: "r"});
  const p = {...props, resource: {key: "roles", fields: []}, row: {id: "r", tenant_id: "t"}, canWrite: false, session: {...session, permissions: ["roles.read", "permissions.read", "roles.assign_permissions"]}};
  const html = harness("it").render("RecordEditor", p);
  assert.equal((html.match(/>Salva</g) ?? []).length, 1);
  assert.doesNotMatch(html, /Salva ·/);
  const run = harness("it", {4: false, 5: {"role-permissions": {options: [], initialIds: ["old"], ids: ["old", "hidden"]}}, 6: false, 7: ""}, {id: "r"});
  await find(run.components.RecordEditor(p), n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(run.apiCalls, ["/data/roles/r/save"]);
  assert.deepEqual(JSON.parse(JSON.stringify(run.apiPayloads)), [{links: {"role-permissions": ["old", "hidden"]}}]);
});
test("record Save sends a single /save request with changed values only", async () => {
  const h = harness("it", {0: {name: "New"}}, {id: "c", name: "New"});
  const tree = h.components.RecordEditor(props);
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(h.apiCalls, ["/data/companies/c/save"]);
  assert.deepEqual(JSON.parse(JSON.stringify(h.apiPayloads)), [{values: {name: "New"}}]);
});

const permissions = ["groups.read", "users.read", "roles.read", "groups.assign_users", "roles.assign"];
const groupProps = {...props, resource: {key: "groups", fields: [{name: "name", type: "text", required: true}]}, row: {id: "g", name: "Old", tenant_id: "t"}, session: {...session, permissions}};
const drafts = {"group-users": {options: [], ids: ["u", "hidden"], initialIds: ["u"]}, "group-roles": {options: [], ids: ["r"], initialIds: []}};
test("combined edit posts changed fields and both relation drafts in one request", async () => {
  const h = harness("en", {0: {name: "New"}, 5: drafts, 6: false}, {id: "g"});
  await find(h.components.RecordEditor(groupProps), n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(h.apiCalls, ["/data/groups/g/save"]);
  assert.deepEqual(JSON.parse(JSON.stringify(h.apiPayloads)), [{values: {name: "New"}, links: {"group-users": ["u", "hidden"], "group-roles": ["r"]}}]);
});
test("creation offers preliminary associations and submits a single POST without owner link reads", async () => {
  const events: string[] = [];
  const h = harness("it", {}, () => {throw Error("new record must not read links")});
  h.components.RecordEditor({...groupProps, row: null, load: async (key: string) => {events.push(key); return [{id: key}]}});
  h.effects[0](); await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(events.sort(), ["roles", "users"]);
  assert.deepEqual(h.apiCalls, []);
  const loaded = JSON.parse(JSON.stringify(h.updates[5]));
  assert.deepEqual(loaded["group-users"].initialIds, []);
  const choose = harness("it", {0: {name: "New"}, 5: loaded, 6: false});
  const tree = choose.components.RecordEditor({...groupProps, row: null});
  find(tree, n => n.props?.relation === "group-users").props.onIdsChange(["users"]);
  assert.deepEqual(choose.apiCalls, [], "choices stay local");
  const selected = (choose.updates[5] as Function)(loaded);
  const save = harness("it", {0: {name: "New"}, 5: selected, 6: false}, {id: "new"});
  await find(save.components.RecordEditor({...groupProps, row: null}), n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(save.apiCalls, ["/data/groups/save"]);
  assert.deepEqual(JSON.parse(JSON.stringify(save.apiPayloads)), [{values: {name: "New"}, links: {"group-users": ["users"]}}]);
});
for (const [name, overrides] of [["loading", {6: true}], ["error", {6: false, 7: "failed"}], ["missing draft", {5: {}, 6: false}]] as const) {
 test(`editable relations ${name} blocks the unified submit without erasing selections`, async () => {
  const h = harness("it", Object.assign({0: {name: "New"}, 5: drafts, 6: false}, overrides));
  const tree = h.components.RecordEditor(groupProps);
  assert.equal(find(tree, n => n.props?.form === "record-form").props.disabled, true);
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(h.apiCalls, []);
  assert.equal(h.updates[5], undefined);
 });
}
test("no-op is disabled and protected from synthetic submit; Cancel only closes", async () => {
 let closed = 0;
 const h = harness();
 const tree = h.components.RecordEditor({...props, onClose: () => closed++});
 assert.equal(find(tree, n => n.props?.form === "record-form").props.disabled, true);
 await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
 find(tree, n => n.props?.variant === "outline" && n.props?.onClick).props.onClick();
 assert.equal(closed, 1);
 assert.deepEqual(h.apiCalls, []);
});
test("unauthorized and unchanged links are omitted instead of overwriting associations", async () => {
 const h = harness("it", {0: {name: "New"}, 5: {...drafts, "group-users": {...drafts["group-users"], ids: ["u"]}}, 6: false}, {id: "g"});
 await find(h.components.RecordEditor({...groupProps, session: {...session, permissions: ["groups.read", "users.read", "roles.read", "groups.assign_users"]}}), n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
 assert.deepEqual(JSON.parse(JSON.stringify(h.apiPayloads)), [{values: {name: "New"}}]);
});
test("failed write preserves parent drafts and allows an explicit retry", async () => {
 let calls = 0;
 const h = harness("it", {0: {name: "New"}, 5: drafts, 6: false}, () => {if (++calls === 1) throw Error("failed"); return {id: "g"}});
 const submit = find(h.components.RecordEditor(groupProps), n => n.props?.id === "record-form").props.onSubmit;
 await submit({preventDefault() {}});
 assert.equal(h.updates[2], "error");
 assert.equal(h.updates[5], undefined);
 await submit({preventDefault() {}});
 assert.equal(h.apiCalls.length, 2);
 assert.deepEqual(h.apiPayloads[0], h.apiPayloads[1]);
});
