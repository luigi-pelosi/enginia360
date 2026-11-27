import test from "node:test";
import assert from "node:assert/strict";
import {harness, find, session, workspace} from "./workspace-harness.ts";
import {partnerHarness} from "./record-editor-harness.ts";
import {normalizeValues, type Resource} from "../lib/model.ts";

const legal = {name: "site_type", type: "select" as const, required: false, options: ["LEGAL", "LOCAL_UNIT", "SECONDARY"]};
const resource: Resource = {key: "sites", fields: [legal]};
const props = {resource, row: {id: "s", site_type: "LEGAL"}, canWrite: true, session, scope: (p: string) => p, load: async () => [], onClose() {}, onSaved: async () => {}, onError: () => "error"};
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));
const functions = {name: "functions", type: "multiselect" as const, required: false, options: ["OPERATIONAL", "ADMINISTRATIVE", "COMMERCIAL", "PRODUCTION", "LOGISTICS", "WAREHOUSE", "TECHNICAL_SERVICE", "MANAGEMENT", "RETAIL"]};
const fullResource = {key: "sites", fields: [legal, functions]};
const fullProps = {...props, resource: fullResource, row: {id: "s", site_type: "LEGAL", functions: ["OPERATIONAL"]}};

test("functions use nine accessible checkboxes in a parent-owned draft and canonical array", async () => {
  const h = harness("it");
  const tree = h.components.RecordEditor(fullProps);
  const fieldset = find(tree, n => n.type === "fieldset" && n.props?.id === "field-functions");
  assert.ok(fieldset, "multiselect has fieldset and legend");
  assert.equal(find(fieldset, n => n.type === "legend").props.children, "Funzioni");
  for (const option of functions.options) {
    const checkbox = find(fieldset, n => n.props?.id === `field-functions-${option}` && typeof n.props?.onCheckedChange === "function");
    assert.ok(checkbox, option);
    assert.equal(checkbox.props.checked, option === "OPERATIONAL");
    assert.ok(find(fieldset, n => n.props?.htmlFor === checkbox.props.id));
  }
  const retail = find(fieldset, n => n.props?.id === "field-functions-RETAIL" && n.props?.onCheckedChange);
  retail.props.onCheckedChange(true);
  const values = (h.updates[0] as (old: Record<string, unknown>) => Record<string, unknown>)({site_type: "LEGAL", functions: ["OPERATIONAL"]});
  assert.deepEqual(plain(values.functions), ["OPERATIONAL", "RETAIL"]);
  assert.deepEqual(h.apiCalls, [], "checkboxes never autosave");
  const normalized = normalizeValues([functions], {functions: ["RETAIL", "OPERATIONAL", "RETAIL"]});
  assert.deepEqual(normalized, {functions: ["OPERATIONAL", "RETAIL"]});
  assert.deepEqual(normalizeValues([functions], {functions: []}), {functions: []});
  // L'inizializzatore viene eseguito direttamente dal vero editor.
  const html = harness("en").render("RecordEditor", {...fullProps, row: null});
  assert.match(html, /<legend[^>]*>Functions<\/legend>/);
  assert.equal((html.match(/type="checkbox"/g) ?? []).length, 9);
});

test("classification draft submits once through values and Cancel discards it", async () => {
  const fields = [...fullResource.fields, {name: "code", type: "text" as const, required: false}];
  const p = {...fullProps, resource: {...fullResource, fields}, row: {...fullProps.row, code: null}};
  const initial = {site_type: "LEGAL", functions: ["OPERATIONAL"], code: ""};
  const draft = harness("it");
  const tree = draft.components.RecordEditor(p);
  find(tree, n => n.props?.name === "site_type").props.onValueChange("SECONDARY");
  let values = (draft.updates[0] as (old: Record<string, unknown>) => Record<string, unknown>)(initial);
  find(tree, n => n.props?.id === "field-functions-RETAIL" && n.props?.onCheckedChange).props.onCheckedChange(true);
  values = (draft.updates[0] as (old: Record<string, unknown>) => Record<string, unknown>)(values);
  find(tree, n => n.props?.id === "field-functions-OPERATIONAL" && n.props?.onCheckedChange).props.onCheckedChange(false);
  values = (draft.updates[0] as (old: Record<string, unknown>) => Record<string, unknown>)(values);
  assert.deepEqual(draft.apiCalls, []);
  let closed = 0;
  const cancel = harness("it", {0: values});
  find(cancel.components.RecordEditor({...p, onClose: () => closed++}), n => n.props?.variant === "outline" && n.props?.onClick).props.onClick();
  assert.equal(closed, 1);
  assert.deepEqual(cancel.apiCalls, []);
  assert.equal(find(harness().components.RecordEditor(p), n => n.props?.name === "site_type").props.value, "LEGAL");
  const save = harness("it", {0: values}, {id: "s"});
  const submit = find(save.components.RecordEditor(p), n => n.props?.id === "record-form").props.onSubmit;
  await Promise.all([submit({preventDefault() {}}), submit({preventDefault() {}})]);
  assert.deepEqual(save.apiCalls, ["/data/sites/s/save"]);
  assert.deepEqual(plain(save.apiPayloads), [{values: {site_type: "SECONDARY", functions: ["RETAIL"]}}]);
  const clear = harness("en", {0: {...initial, site_type: "", functions: []}}, {id: "s"});
  await find(clear.components.RecordEditor(p), n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(plain(clear.apiPayloads), [{values: {site_type: null, functions: []}}]);
});

for (const [locale, labels] of [
  ["it", ["Operativa", "Amministrativa", "Commerciale", "Produttiva", "Logistica", "Magazzino", "Assistenza tecnica", "Direzionale", "Punto vendita"]],
  ["en", ["Operations", "Administration", "Sales", "Production", "Logistics", "Warehouse", "Technical service", "Management", "Retail"]],
] as const) {
  test(`localized functions table and readonly editor never expose raw codes (${locale})`, async () => {
    const row = {...fullProps.row, functions: functions.options};
    const html = workspace(fullResource, ["sites.read"], row, locale);
    for (const label of labels) assert.ok(html.includes(label), `table ${label}`);
    assert.doesNotMatch(html, />[^<]*(?:OPERATIONAL|TECHNICAL_SERVICE|LEGAL)[^<]*</);
    const readonly = harness(locale);
    const tree = readonly.components.RecordEditor({...fullProps, row, canWrite: false});
    const select = find(tree, n => n.props?.name === "site_type");
    assert.equal(select.props.disabled, true);
    select.props.onValueChange("SECONDARY");
    for (const option of functions.options) {
      const box = find(tree, n => n.props?.id === `field-functions-${option}` && n.props?.onCheckedChange);
      assert.equal(box.props.disabled, true);
      assert.equal(box.props.checked, true);
      box.props.onCheckedChange(false);
    }
    assert.equal(readonly.updates[0], undefined, "synthetic readonly changes are ignored");
    assert.equal(find(tree, n => n.props?.form === "record-form"), undefined);
    await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
    assert.deepEqual(readonly.apiCalls, []);
    const details = harness(locale).render("RecordEditor", {...fullProps, row, canWrite: false});
    for (const label of labels) assert.ok(details.includes(label));
    assert.doesNotMatch(details, />OPERATIONAL<|>TECHNICAL_SERVICE<|>LEGAL</);
  });
}

test("readonly classification select ignores synthetic changes", () => {
  const h = harness("it");
  const tree = h.components.RecordEditor({...fullProps, canWrite: false});
  find(tree, n => n.props?.name === "site_type").props.onValueChange("SECONDARY");
  assert.equal(h.updates[0], undefined);
});

test("new site has no implicit legal classification, empty functions and one Save", async () => {
  const h = partnerHarness("workspace", "en");
  const p = {...fullProps, row: null, tenant: "t"};
  h.tree("RecordEditor", p);
  await h.flush();
  const tree = h.tree("RecordEditor", p);
  assert.equal(find(tree, n => n.props?.name === "site_type").props.value, "");
  for (const option of functions.options)
    assert.equal(find(tree, n => n.props?.id === `field-functions-${option}` && n.props?.onCheckedChange).props.checked, false);
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(plain(h.calls.map(call => call.body)), [{values: {site_type: null, functions: []}}]);
  assert.equal((harness("en").render("RecordEditor", {...fullProps, row: null}).match(/>Save</g) ?? []).length, 1);
});

test("unchanged classification disables Save; busy controls cannot edit or submit", async () => {
  for (const busy of [false, true]) {
    const h = harness("it", {3: busy});
    const tree = h.components.RecordEditor(fullProps);
    assert.equal(find(tree, n => n.props?.form === "record-form").props.disabled, true);
    if (busy) {
      find(tree, n => n.props?.name === "site_type").props.onValueChange("SECONDARY");
      find(tree, n => n.props?.id === "field-functions-RETAIL" && n.props?.onCheckedChange).props.onCheckedChange(true);
      assert.equal(h.updates[0], undefined);
    }
    await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
    assert.deepEqual(h.apiCalls, []);
  }
});

test("dirty comparison treats initial functions as canonical sets", async () => {
  const p = {...fullProps, resource: {...fullResource, fields: [...fullResource.fields, {name: "name", type: "text" as const, required: true}]}, row: {...fullProps.row, functions: ["RETAIL", "OPERATIONAL"], name: "Sede"}};
  const initial = harness("it");
  const tree = initial.components.RecordEditor(p);
  assert.equal(find(tree, n => n.props?.form === "record-form").props.disabled, true, "initial array order is not a change");
  await find(tree, n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(initial.apiCalls, []);
  const edited = harness("it", {0: {site_type: "LEGAL", functions: ["OPERATIONAL", "RETAIL"], name: "Nuova sede"}}, {id: "s"});
  await find(edited.components.RecordEditor(p), n => n.props?.id === "record-form").props.onSubmit({preventDefault() {}});
  assert.deepEqual(plain(edited.apiPayloads), [{values: {name: "Nuova sede"}}], "unchanged function set omitted");
});

test("preferred_language select retains metadata default and localized choices", () => {
  const language = {name: "preferred_language", type: "select" as const, required: false, options: ["it", "en"], defaultValue: "it"};
  const p = {...props, resource: {key: "users", fields: [language]}, row: null};
  const h = harness("en");
  const tree = h.components.RecordEditor(p);
  const select = find(tree, n => n.props?.name === "preferred_language");
  assert.equal(select.props.value, "it");
  assert.equal(find(select, n => n.props?.value === "__none__"), undefined);
  select.props.onValueChange("en");
  assert.deepEqual(plain((h.updates[0] as (old: Record<string, unknown>) => Record<string, unknown>)({preferred_language: "it"})), {preferred_language: "en"});
  const html = harness("en").render("RecordEditor", p);
  assert.match(html, />Italian</);
  assert.match(html, />English</);
});

for (const [locale, title, labels] of [
  ["it", "Tipologia giuridica", ["Sede legale", "Unità locale", "Sede secondaria"]],
  ["en", "Legal classification", ["Registered office", "Local unit", "Secondary office"]],
] as const) {
  test(`legal classification select is localized and clearable (${locale})`, async () => {
    const h = harness(locale);
    const tree = h.components.RecordEditor(props);
    const select = find(tree, n => n.props?.name === "site_type");
    assert.ok(select, "metadata select exists");
    assert.ok(find(select, n => n.props?.value === "__none__"), "optional select has clear choice");
    const html = harness(locale).render("RecordEditor", props);
    assert.ok(html.includes(title));
    for (const label of labels) assert.ok(html.includes(label), label);
    assert.doesNotMatch(html, />LEGAL<|>LOCAL_UNIT<|>SECONDARY</);
    select.props.onValueChange("__none__");
    const values = (h.updates[0] as (old: Record<string, unknown>) => Record<string, unknown>)({site_type: "LEGAL"});
    assert.deepEqual(plain(values), {site_type: ""});
    assert.deepEqual(normalizeValues(resource.fields, values), {site_type: null});
    assert.deepEqual(h.apiCalls, []);
    const table = workspace(resource, ["sites.read"], props.row, locale);
    assert.ok(table.includes(labels[0]), "table shows localized classification");
    assert.doesNotMatch(table, />LEGAL</);
  });
}
