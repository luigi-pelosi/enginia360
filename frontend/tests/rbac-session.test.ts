import test from "node:test";
import assert from "node:assert/strict";
import {runInNewContext} from "node:vm";
import ts from "typescript";
import {source, harness, session} from "./workspace-harness.ts";
const compile = (code: string) => ts.transpileModule(code, {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
function clickHandler(element: any, label: string): (() => Promise<void>) | undefined {
  if (!element || typeof element !== "object") return;
  if (element.props?.["aria-label"] === label) return element.props.onClick;
  for (const child of [element.props?.children].flat(Infinity)) {
    const match = clickHandler(child, label);
    if (match) return match;
  }
}
test("Refresh reads /session before reloading data and replaces revoked UI authority", async () => {
  const refreshed = {...session, permissions: []};
  const h = harness("it", {0: {...session, permissions: ["companies.read", "companies.update"]}, 1: false, 5: [{key: "companies", fields: []}], 6: "companies", 7: "t"}, refreshed);
  const tree = h.components.default({});
  const refresh = clickHandler(tree, "Aggiorna");
  assert.equal(typeof refresh, "function");
  await refresh!();
  assert.equal(h.apiCalls[0], "/session", "refresh obtains fresh effective permissions");
  assert.equal(h.updates[0], refreshed, "session is replaced, not merged with old grants");
  assert.equal(h.updates[6], "", "zero grants falls back to neutral no-access, never Settings");
  assert.equal(typeof h.updates[15], "function", "data version invalidated after session reload");
});
test("unified assignment save closes before fresh session and never performs protected link readback", async () => {
  for (const readable of [true, false]) {
    const events: string[] = [];
    const h = harness("it", {4: false, 5: {"user-roles": {options: [], ids: ["r"], initialIds: []}}, 6: false}, () => {events.push("PUT"); return {id: "u"}});
    const tree = h.components.RecordEditor({resource: {key: "users", fields: []}, row: {id: "u", tenant_id: "t"}, canWrite: false,
      session: {...session, permissions: ["users.read", "roles.read", "roles.assign"]}, scope: (p: string) => p, load: async () => [],
      onClose: () => events.push("close"), onSaved: async () => {events.push("session"); if (!readable) throw new Error("401");}, onError: () => "error"});
    const form = (await import("./workspace-harness.ts")).find(tree, n => n.props?.id === "record-form");
    await form.props.onSubmit({preventDefault() {}});
    assert.deepEqual(events, ["PUT", "close", "session"]);
    assert.equal(h.apiCalls.length, 1);
    assert.equal(h.updates[2], "", "postcommit session error is not a failed write");
  }
});
