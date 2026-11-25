import {readFileSync} from "node:fs";
import {createRequire} from "node:module";
import {runInNewContext} from "node:vm";
import ts from "typescript";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {createTranslator} from "next-intl";
import * as model from "../lib/model.ts";
import * as catalog from "../lib/catalog.ts";

export const source = readFileSync(new URL("../components/workspace.tsx", import.meta.url), "utf8");
const require = createRequire(import.meta.url);
export function harness(locale = "it", states: Record<number, unknown> = {}, apiResult: unknown = {ids: []}, storage = new Map<string, string>(), browserWindow?: object) {
  const messages = JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), "utf8"));
  let index = 0;
  const effects: Array<() => unknown> = [];

  const updates: Record<number, unknown> = {};
  const ui = new Proxy({}, {get: (_target, name) => name === "useSidebar" ? () => ({setOpenMobile() {}}) : (props: Record<string, unknown>) => {
    const tag = name === "Button" ? "button" : name === "Checkbox" || name === "Input" ? "input" : name === "Label" ? "label" : "div";
    const safe = Object.fromEntries(Object.entries(props).filter(([key]) => ["children", "disabled", "className", "id", "value", "checked", "htmlFor"].includes(key) || key.startsWith("aria-") || key.startsWith("data-")));
    if (name === "Checkbox") safe.type = "checkbox";
    if (tag === "input") {delete safe.children; safe.readOnly = true;}
    return React.createElement(tag, safe);
  }});
  const module = {exports: {} as Record<string, (...args: any[]) => any>};
  const code = ts.transpileModule(source + "\nexport {RecordEditor, RelationEditor, PermissionTree, PasswordForm, PurchasingCoverageEditor, recoverCurrencyEdit};", {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true}}).outputText;
  const apiCalls: string[] = [];
  const apiPayloads: unknown[] = [];
  const resolve = (name: string): any => {
    if (name === "react") return {...React, useState: (value: unknown) => {
      const current = index++;
      return [Object.hasOwn(states, current) ? states[current] : typeof value === "function" ? value() : value, (next: unknown) => {updates[current] = next}];
    }, useRef: (current: unknown) => ({current}), useEffect: (effect: () => unknown) => effects.push(effect), useMemo: (fn: () => unknown) => fn(), useCallback: (fn: unknown) => fn};
    if (name === "next-intl") return {useLocale: () => locale, useTranslations: (namespace: string) => createTranslator({locale, messages, namespace})};
    if (name === "@/lib/model") return model;
    if (name === "@/lib/catalog") return catalog;
    if (name === "@/components/catalog-workspace") return {
      CatalogWorkspace: () => null,
      resetCatalogRecovery: (session: model.Session, tenant: string, resource: string) => catalog.resetCatalog(sessionStorage, catalog.catalogKey(session.id, session.isSuperAdmin ? tenant : session.tenantId || "", resource)),
    };
    if (name === "@/components/catalog-items-overview") return {CatalogItemsOverview: () => null};
    if (name === "@/components/catalog-item-workspace") return {CatalogItemWorkspace: () => null};
    if (name === "@/components/payment-partner-defaults") return {PaymentPartnerDefaults: () => null};
    if (name === "@/components/payments-workspace") return {PaymentsWorkspace: () => null};
    if (name === "@/lib/country-codes") return {countryCodes: JSON.parse(readFileSync(new URL('./country-codes.json', import.meta.url), 'utf8'))};
    if (name === "@/lib/password") {
      const child = {exports: {}};
      const text = readFileSync(new URL("../lib/password.ts", import.meta.url), "utf8");
      runInNewContext(ts.transpileModule(text, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText, {module: child, exports: child.exports});
      return child.exports;
    }
    if (name === "@/lib/api") return {api: async (path: string, _method?: string, body?: unknown) => {apiCalls.push(path); apiPayloads.push(body); return typeof apiResult === "function" ? apiResult(path, _method, body) : apiResult}, ApiError: class extends Error {}, refreshCsrf: async () => {}};
    if (name === "@/components/business-partner-companies" || name === "@/components/company-business-partners" || name === "@/components/role-company-access" || name === "@/components/business-partner-numbering" || name === "@/components/business-partner-workspace" || name === "@/components/profile-dialog" || name === "@/components/permission-tree" || name === "@/components/purchasing-coverage-editor" || name === "@/components/address-autocomplete" || name === "@/components/site-country-select") {
      const child = {exports: {}};
      const childSource = readFileSync(new URL(`../components/${name.split("/").at(-1)}.tsx`, import.meta.url), "utf8");
      const childCode = ts.transpileModule(childSource, {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true}}).outputText;
      runInNewContext(childCode, {module: child, exports: child.exports, require: resolve, AbortController, setTimeout, clearTimeout});
      return child.exports;
    }
    if (name.startsWith("@/components/ui/")) return ui;
    return require(name);
  };
  const sessionStorage = {get length() {return storage.size;}, key: (i: number) => [...storage.keys()][i] ?? null, getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => {storage.set(key, value);}, removeItem: (key: string) => {storage.delete(key);}};
  runInNewContext(code, {module, exports: module.exports, require: resolve, console, setTimeout, clearTimeout, sessionStorage, URLSearchParams, ...(browserWindow ? {window: browserWindow} : {})});
  return {components: module.exports, effects, updates, apiCalls, apiPayloads, render: (component: string, props = {}) => renderToStaticMarkup(React.createElement(module.exports[component], props))};
}
export function find(node: any, predicate: (node: any) => boolean): any {
  if (!node || typeof node !== "object") return;
  if (predicate(node)) return node;
  for (const child of [node.props?.children, ...(node.props?.fields ?? []).map((field: any) => field.content)].flat(Infinity)) {const result = find(child, predicate); if (result) return result;}
}
export const session: model.Session = {id: "u", username: "ada", displayName: "Ada", preferredLanguage: "it", tenantId: "t", isSuperAdmin: false, mustChangePassword: false, permissions: []};
export function workspace(resource: model.Resource, permissions: string[], row: model.Row, locale = "it") {
  return harness(locale, {0: {...session, permissions}, 1: false, 5: [resource], 6: resource.key, 7: "t", 9: [row], 10: 1}).render("default");
}
