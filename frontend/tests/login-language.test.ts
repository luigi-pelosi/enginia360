import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
import ts from "typescript";

// Execute the real login handler with its browser/API boundary isolated.
const source = readFileSync(new URL("../components/workspace.tsx", import.meta.url), "utf8");
const handler = source.slice(source.indexOf("  async function login("), source.indexOf("  async function logout("));
const tenantHelpers = source.slice(source.indexOf('function workspaceTenantKey('), source.indexOf('/* end-workspace-navigation-helpers */'));
const executable = ts.transpileModule(tenantHelpers + '\n' + handler, {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
async function login(currentLocale: string, preferredLanguage: "it" | "en", mustChangePassword = false, failure = "", overrides: Record<string, unknown> = {}) {
  const events: string[] = [];
  const session = {id: "user", tenantId: "tenant", displayName: "Ada Lovelace", preferredLanguage, mustChangePassword, ...overrides};
  let authenticated: unknown = null;
  const document = {cookie: ""};
  const context = {
    sessionStorage: {setItem: (key: string, value: string) => events.push(`storage:${key}:${value}`)},
    locale: currentLocale, username: "ada", password: "secret", tenantCode: "",
    document, location: {reload: () => events.push("reload")},
    api: async (path: string) => {events.push(path); if(failure) throw Error(failure); return session},
    refreshCsrf: async () => {events.push("csrf")},
    setBusy: (value: boolean) => events.push(`busy:${value}`),
    setError: (value: string) => events.push(`error:${value}`),
    setPassword: (value: string) => events.push(`password:${value}`),
    setSession: (value: unknown) => {authenticated = value; events.push("session")},
    setTenant: (value: string) => events.push(`tenant:${value}`),
    setVersion: () => events.push("version"),
    translateError: (error: Error) => error.message,
  };
  const invoke = runInNewContext(`${executable}; login`, context);
  await invoke({preventDefault() {}});
  return {events, authenticated, session, cookie: document.cookie};
}

test("successful login applies stored language cookie and reloads on a different locale", async () => {
  for (const [current, preferred] of [["it", "en"], ["en", "it"]] as const) {
    const result = await login(current, preferred);
    assert.equal(result.cookie, `locale=${preferred}; Path=/; Max-Age=31536000; SameSite=Strict`);
    assert.equal(result.events.filter(event => event === "reload").length, 1);
    assert.ok(result.events.indexOf("csrf") < result.events.indexOf("reload"));
    assert.ok(result.events.includes("password:"));
  }
});
test("same-locale login keeps authenticated flow and forced password-change state", async () => {
  for (const language of ["it", "en"] as const) {
    for (const mustChange of [false, true]) {
      const result = await login(language, language, mustChange);
      assert.equal(result.cookie, `locale=${language}; Path=/; Max-Age=31536000; SameSite=Strict`);
      assert.ok(!result.events.includes("reload"));
      assert.equal(result.authenticated, result.session);
      assert.ok(result.events.includes("tenant:tenant"));
      assert.ok(result.events.includes("version"));
    }
  }
});
test("failed login never applies a language or reloads", async () => {
  const result = await login("it", "en", false, "invalid_credentials");
  assert.equal(result.cookie, "");
  assert.equal(result.authenticated, null);
  assert.ok(!result.events.includes("reload"));
  assert.ok(result.events.includes("error:invalid_credentials"));
});
test("global login preselects the organization without changing identity scope", async () => {
  const result = await login("it", "it", false, "", {tenantId:null,isSuperAdmin:true,selectedTenantId:"chosen-organization"});
  assert.equal(result.session.tenantId, null);
  assert.ok(result.events.includes("tenant:chosen-organization"));
  assert.ok(result.events.includes("storage:workspace-tenant:user:chosen-organization"));
  assert.equal(result.authenticated, result.session);
});
test("session restoration and password-change do not overwrite temporary language choice", () => {
  const restoration = source.slice(source.indexOf('api<Session>("/session")'), source.indexOf('api<Resource[]>("/resources")'));
  assert.doesNotMatch(restoration, /document\.cookie|location\.reload/);
  assert.ok(source.includes("if (session.mustChangePassword)"));
});
