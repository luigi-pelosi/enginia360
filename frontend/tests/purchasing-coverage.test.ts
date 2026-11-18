import test from "node:test";
import assert from "node:assert/strict";
import {harness, find, session} from "./workspace-harness.ts";
const company = "11111111-1111-1111-1111-111111111111", site = "22222222-2222-2222-2222-222222222222";
const permissions = ["purchasing-organizations.read", "purchasing-organizations.assign_scope", "companies.read", "sites.read"];
const props = {resource: {key: "purchasing-organizations", fields: [{name: "name", type: "text", required: true}, {name: "code", type: "text", required: false}]}, row: null, canWrite: true, session: {...session, permissions}, scope: (p: string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onError: () => "error"};
const entry = {companyId: company, siteScope: "selected_sites", siteIds: [site]};
const draft = {companies: [{id: company, name: "Acme", is_enabled: false}], sites: [{id: site, company_id: company, name: "Main", is_enabled: false}, {id: "other", company_id: "other-company", name: "Other"}], initial: [], coverage: [entry]};
const loaded = {0: {name: "Purchases", code: ""}, 9: draft, 10: false};
const submit = (h: ReturnType<typeof harness>, p: any = props) => find(h.components.RecordEditor(p), n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
test("creation stages coverage mode and site choices and writes exactly one aggregate Save", async () => {
  const h = harness("it", loaded, {id: "new"});
  const tree = h.components.RecordEditor(props);
  const panel = find(tree, n => n.props?.draft?.coverage === draft.coverage);
  assert.ok(panel, "RecordEditor owns and renders the coverage draft");
  const rendered = harness("it", loaded).render("RecordEditor", props);
  assert.match(rendered, /data-purchasing-coverage/);
  assert.match(rendered, /Aziende e sedi/);
  assert.equal((rendered.match(/>Salva</g) ?? []).length, 1);
  assert.match(rendered, /Disattivo/);
  assert.doesNotMatch(rendered, />Other</);
  assert.deepEqual(h.apiCalls, []);
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(h.apiCalls, ["/data/purchasing-organizations/save"]);
  assert.deepEqual(JSON.parse(JSON.stringify(h.apiPayloads)), [{values: {name: "Purchases", code: null}, coverage: [entry]}]);
});
const existing = {...props, row: {id: "org", name: "Purchases", code: null}, canWrite: false};
const flush = () => new Promise(resolve => setTimeout(resolve, 0));
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));
const panel = (tree: any) => find(tree, n => typeof n.props?.onChange === "function" && "editable" in n.props);
const childProps = {draft, editable: true, loading: false, busy: false, onChange(_entries: unknown) {}};

test("coverage-only authority leaves profile readonly and omits values", async () => {
  const h = harness("en", loaded, {id: "org"});
  const tree = h.components.RecordEditor(existing);
  assert.equal(find(tree, n => n.type === "fieldset").props.disabled, true);
  assert.equal(find(tree, n => n.props?.form === "record-form").props.disabled, false);
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(plain(h.apiPayloads), [{coverage: [entry]}]);
  assert.deepEqual(h.apiCalls, ["/data/purchasing-organizations/org/save"]);
});
test("readonly panel cannot stage or save without assign_scope", async () => {
  const p = {...existing, session: {...session, permissions: props.session.permissions.filter(p => !p.endsWith("assign_scope"))}};
  const h = harness("it", loaded);
  const tree = h.components.RecordEditor(p);
  assert.equal(panel(tree).props.editable, false);
  panel(tree).props.onChange([]);
  assert.equal(h.updates[9], undefined);
  assert.equal(find(tree, n => n.props?.form === "record-form"), undefined);
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(h.apiCalls, []);
});
for (const missing of ["purchasing-organizations.read", "companies.read", "sites.read"]) test(`missing ${missing} hides panel, makes no reference reads, omits coverage`, async () => {
  const reads: string[] = [];
  const h = harness("it", loaded, {id: "org"});
  const p = {...props, row: existing.row, session: {...session, permissions: props.session.permissions.filter(p => p !== missing)}, load: async (key: string) => {reads.push(key); return []}};
  const tree = h.components.RecordEditor(p);
  assert.equal(panel(tree), undefined);
  for (const effect of h.effects) effect();
  await flush();
  assert.deepEqual(reads, []);
  assert.deepEqual(h.apiCalls, []);
  const save = harness("it", {...loaded, 0: {name: "Changed", code: ""}}, {id: "org"});
  await submit(save, p);
  assert.deepEqual(plain(save.apiPayloads), [{values: {name: "Changed"}}]);
});
test("new record reads all company/site options but never invents an owner GET", async () => {
  const reads: string[] = [];
  const h = harness("it", {}, () => {throw Error("no owner GET for create")});
  h.components.RecordEditor({...props, load: async (key: string) => {reads.push(key); return key === "companies" ? draft.companies : draft.sites}});
  h.effects[2](); await flush();
  assert.deepEqual(reads, ["companies", "sites"]);
  assert.deepEqual(h.apiCalls, []);
  assert.deepEqual(plain(h.updates[9]), {...draft, initial: [], coverage: []});
  assert.equal(h.updates[10], false);
});
test("existing record loads the exact scoped coverage endpoint and retains inactive assignments", async () => {
  const h = harness("it", {}, {coverage: [entry]});
  h.components.RecordEditor({...existing, scope: (p: string) => `${p}?tenantId=t`, load: async (key: string) => key === "companies" ? draft.companies : draft.sites});
  h.effects[2](); await flush();
  assert.deepEqual(h.apiCalls, ["/data/purchasing-organizations/org/coverage?tenantId=t"]);
  assert.deepEqual(plain(h.updates[9]), {...draft, initial: [entry]});
});
for (const [name, state] of [
  ["initial", {}], ["loading", {9: draft, 10: true}], ["load error", {9: draft, 10: false, 11: "failed"}],
  ["missing draft", {10: false}], ["busy", {...loaded, 3: true}],
  ["unselected mode", {...loaded, 9: {...draft, coverage: [{...entry, siteScope: ""}]}}],
  ["empty selected sites", {...loaded, 9: {...draft, coverage: [{...entry, siteIds: []}]}}],
  ["all sites with IDs", {...loaded, 9: {...draft, coverage: [{...entry, siteScope: "all_sites"}]}}],
  ["duplicate companies", {...loaded, 9: {...draft, coverage: [entry, entry]}}],
  ["foreign site", {...loaded, 9: {...draft, coverage: [{...entry, siteIds: ["other"]}]}}],
] as const) test(`${name} blocks synthetic submit and footer without requests`, async () => {
  const h = harness("it", state);
  const tree = h.components.RecordEditor(props);
  assert.equal(find(tree, n => n.props?.form === "record-form").props.disabled, true);
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(h.apiCalls, []);
});
test("coverage load errors and failed option loads remain blocking after loading completes", async () => {
  for (const fail of ["companies", "sites", "coverage"]) {
    const h = harness("it", {}, () => {if (fail === "coverage") throw Error("failed"); return {coverage: [entry]}});
    h.components.RecordEditor({...existing, load: async (key: string) => {if (key === fail) throw Error("failed"); return []}});
    h.effects[2](); await flush();
    assert.equal(h.updates[11], "error");
    assert.equal(h.updates[10], false);
    assert.equal(h.updates[9], undefined);
  }
});
test("unchanged coverage is omitted on profile update; coverage no-op is blocked", async () => {
  const state = {...loaded, 9: {...draft, initial: [entry]}};
  const h = harness("it", state);
  await submit(h, {...props, row: existing.row});
  assert.deepEqual(h.apiCalls, []);
  const changed = harness("it", {...state, 0: {name: "Changed", code: ""}}, {id: "org"});
  await submit(changed, {...props, row: existing.row});
  assert.deepEqual(plain(changed.apiPayloads), [{values: {name: "Changed"}}]);
});
test("explicit clear sends coverage [] while all_sites never expands site IDs", async () => {
  for (const coverage of [[], [{companyId: company, siteScope: "all_sites", siteIds: []}]]) {
    const h = harness("it", {...loaded, 9: {...draft, initial: [entry], coverage}}, {id: "org"});
    await submit(h, existing as any);
    assert.deepEqual(plain(h.apiPayloads), [{coverage}]);
  }
});
test("rapid double submit is latched, closes before refresh, and postcommit error is not retryable", async () => {
  let release!: (value: unknown) => void;
  const events: string[] = [];
  const h = harness("it", loaded, () => new Promise(resolve => {release = resolve}));
  const tree = h.components.RecordEditor({...existing, onClose: () => events.push("close"), onSaved: async () => {events.push("refresh"); throw Error("401")}});
  const fn = find(tree, n => n.props?.id === "record-form").props.onSubmit;
  const first = fn({preventDefault() {}}), second = fn({preventDefault() {}});
  assert.equal(h.apiCalls.length, 1);
  release({id: "org"}); await Promise.all([first, second]);
  assert.deepEqual(events, ["close", "refresh"]);
  assert.equal(h.updates[2], "");
  await fn({preventDefault() {}});
  assert.equal(h.apiCalls.length, 1);
});
test("write failure preserves the draft and allows an identical explicit retry; Cancel does not write", async () => {
  let attempts = 0, closed = 0;
  const h = harness("it", loaded, () => {if (++attempts === 1) throw Error("409"); return {id: "org"}});
  const tree = h.components.RecordEditor({...existing, onClose: () => closed++});
  const fn = find(tree, n => n.props?.id === "record-form").props.onSubmit;
  await fn({preventDefault() {}});
  assert.equal(h.updates[2], "error");
  assert.equal(h.updates[9], undefined);
  assert.equal(closed, 0);
  await fn({preventDefault() {}});
  assert.deepEqual(h.apiPayloads[0], h.apiPayloads[1]);
  const cancel = harness("it", loaded);
  const cancelled = cancel.components.RecordEditor({...existing, onClose: () => closed++});
  panel(cancelled).props.onChange([]);
  find(cancelled, n => n.props?.variant === "outline" && n.props?.onClick).props.onClick();
  assert.deepEqual(cancel.apiCalls, []);
});
test("company Add requires explicit site mode; duplicates cannot be added", () => {
  let changed: any;
  const h = harness("it", {0: company});
  const tree = h.components.PurchasingCoverageEditor({...childProps, draft: {...draft, coverage: []}, onChange: (value: unknown) => {changed = plain(value)}});
  find(tree, n => n.props?.children === "Aggiungi").props.onClick();
  assert.deepEqual(changed, [{companyId: company, siteScope: "", siteIds: []}]);
  const duplicate = harness("it", {0: company}).components.PurchasingCoverageEditor({...childProps, onChange: () => {throw Error("duplicate")}});
  const add = find(duplicate, n => n.props?.children === "Aggiungi");
  assert.equal(add.props.disabled, true); add.props.onClick();
  assert.deepEqual(h.apiCalls, []);
});
test("mode/site/remove handlers only edit the draft and all_sites clears staged IDs", () => {
  let changed: any;
  const h = harness("it");
  const tree = h.components.PurchasingCoverageEditor({...childProps, onChange: (value: unknown) => {changed = plain(value)}});
  const mode = find(tree, n => typeof n.props?.onValueChange === "function" && n.props?.value === "selected_sites");
  mode.props.onValueChange("all_sites");
  assert.deepEqual(changed, [{companyId: company, siteScope: "all_sites", siteIds: []}]);
  const allTree = harness().components.PurchasingCoverageEditor({...childProps, draft: {...draft, coverage: changed}, onChange: (value: unknown) => {changed = plain(value)}});
  find(allTree, n => typeof n.props?.onValueChange === "function" && n.props?.value === "all_sites").props.onValueChange("selected_sites");
  assert.deepEqual(changed, [{companyId: company, siteScope: "selected_sites", siteIds: []}]);
  const select = find(tree, n => n.props?.["data-coverage-site"] === site);
  assert.equal(select.props.checked, true); select.props.onCheckedChange(false);
  assert.deepEqual(changed, [{...entry, siteIds: []}]);
  assert.equal(find(tree, n => n.props?.["data-coverage-site"] === "other"), undefined);
  find(tree, n => n.props?.children === "Rimuovi").props.onClick();
  assert.deepEqual(changed, []);
  assert.deepEqual(h.apiCalls, []);
});
for (const state of [{editable: false}, {busy: true}, {loading: true}]) test(`disabled child guards handlers ${JSON.stringify(state)}`, () => {
  let calls = 0;
  const h = harness("it", {0: company});
  const tree = h.components.PurchasingCoverageEditor({...childProps, ...state, onChange: () => calls++});
  const visit = (node: any) => {if (!node || typeof node !== "object") return; if (node.props?.onCheckedChange) node.props.onCheckedChange(false); if (node.props?.onValueChange) node.props.onValueChange("all_sites"); if (node.props?.onClick) node.props.onClick(); for (const child of [node.props?.children].flat(Infinity)) visit(child);};
  visit(tree); assert.equal(calls, 0); assert.deepEqual(h.apiCalls, []);
});
test("Add, mode and site handlers stage a parent-owned creation draft before the single POST", async () => {
  let staged: any = {...draft, coverage: []};
  const update = (entries: unknown) => {
    const parent = harness("it", {...loaded, 9: staged});
    panel(parent.components.RecordEditor(props)).props.onChange(entries);
    assert.deepEqual(parent.apiCalls, []);
    staged = (parent.updates[9] as Function)(staged);
  };
  const add = harness("it", {0: company}).components.PurchasingCoverageEditor({...childProps, draft: staged, onChange: update});
  find(add, n => n.props?.children === "Aggiungi").props.onClick();
  assert.equal(staged.coverage[0].siteScope, "");
  const chooseMode = harness().components.PurchasingCoverageEditor({...childProps, draft: staged, onChange: update});
  find(chooseMode, n => n.props?.onValueChange && find(n, child => child.props?.["data-coverage-mode"] === company)).props.onValueChange("selected_sites");
  const chooseSite = harness().components.PurchasingCoverageEditor({...childProps, draft: staged, onChange: update});
  find(chooseSite, n => n.props?.["data-coverage-site"] === site).props.onCheckedChange(true);
  assert.deepEqual(plain(staged.coverage), [entry]);
  const save = harness("it", {...loaded, 9: staged}, {id: "created"});
  await submit(save);
  assert.deepEqual(save.apiCalls, ["/data/purchasing-organizations/save"]);
  assert.deepEqual(plain(save.apiPayloads), [{values: {name: "Purchases", code: null}, coverage: [entry]}]);
});

test("sales metadata reuses Name priority, optional Code and required Company controls", () => {
  const resource = {key: "sales-organizations", fields: [{name: "company_id", type: "reference", required: true, reference: "companies"}, {name: "name", type: "text", required: true}, {name: "code", type: "text", required: false}]};
  const html = harness("en", {1: {companies: draft.companies}, 4: false}).render("RecordEditor", {...props, resource});
  assert.ok(html.indexOf("field-name") < html.indexOf("field-code"));
  assert.match(html, /id="field-code"[^>]*value=""/);
  assert.doesNotMatch(html, /id="field-code"[^>]*required/);
  assert.match(html, /Company/);
  assert.doesNotMatch(html, /data-purchasing-coverage/);
});

test("missing references are shown as fallbacks and never silently removed", () => {
  const html = harness("en").render("PurchasingCoverageEditor", {...childProps, draft: {...draft, companies: [], sites: []}});
  assert.match(html, new RegExp(company)); assert.match(html, new RegExp(site));
  assert.match(html, /checked/);
  assert.match(html, /Companies and sites/);
});
