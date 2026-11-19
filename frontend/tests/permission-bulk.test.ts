import test from "node:test";
import assert from "node:assert/strict";
import {harness} from "./workspace-harness.ts";
import {catalog} from "./permission-catalog.ts";
function find(node: any, key: string, value: string): any {
  if (!node || typeof node !== "object") return;
  if (node.props?.[key] === value) return node;
  for (const child of [node.props?.children].flat(Infinity)) {const result = find(child, key, value); if (result) return result;}
}
for (const [key, value, count] of [["data-permission-selection", "all", 61], ["data-permission-domain-checkbox", "masterData", 8], ["data-permission-domain-checkbox", "organization", 17], ["data-permission-resource-checkbox", "business-partners", 8], ["data-permission-resource-checkbox", "business-partner-companies", 5], ["data-permission-resource-checkbox", "companies", 4], ["data-permission-resource-checkbox", "purchasing-organizations", 5], ["data-permission-resource-checkbox", "settings", 6], ["data-permission-resource-checkbox", "settings-business-partners", 2]] as const) {
  test(`${value}: bulk includes hidden original scope, tristate and preserves external selections`, () => {
    let changed: string[] = [];
    const selectedCode = value === "masterData" || value === "business-partners" ? "business-partners.read" : value === "business-partner-companies" ? "business-partner-companies.read" : value.startsWith('settings') ? "business-partner-numbering.read" : value === "purchasing-organizations" ? "purchasing-organizations.read" : "companies.read";
    const props = {rows: catalog, query: selectedCode, selectedIds: [selectedCode, "outside"], renderLeaf: () => null, onSelectedIdsChange: (ids: string[]) => {changed = ids}};
    const h = harness();
    const tree = h.components.PermissionTree(props);
    const control = find(tree, key, value);
    assert.ok(control, `missing ${value} bulk control`);
    assert.equal(control.props.checked, "indeterminate");
    control.props.onCheckedChange(true);
    assert.equal(changed.length, count + 1);
    assert.ok(changed.includes("outside"));
    assert.equal(new Set(changed).size, changed.length);
    let stopped = 0;
    control.props.onClick({stopPropagation() {stopped++}});
    control.props.onKeyDown({key: " ", stopPropagation() {stopped++}});
    assert.equal(stopped, 2);
    const full = harness().components.PermissionTree({...props, selectedIds: changed});
    const selected = find(full, key, value);
    assert.equal(selected.props.checked, true);
    selected.props.onCheckedChange(false);
    assert.deepEqual([...changed], ["outside"]);
  });
}
test("catalog has no bulk controls; readonly selector bulk cannot mutate", () => {
  const props = {rows: catalog, renderLeaf: () => null};
  const catalogTree = harness().components.PermissionTree(props);
  assert.equal(find(catalogTree, "data-permission-selection", "all"), undefined);
  let calls = 0;
  const readonly = harness().components.PermissionTree({...props, selectedIds: [], disabled: true, onSelectedIdsChange: () => calls++});
  const control = find(readonly, "data-permission-selection", "all");
  assert.ok(control);
  assert.equal(control.props.disabled, true);
  assert.equal(control.props.checked, false);
  control.props.onCheckedChange(true);
  assert.equal(calls, 0);
});
