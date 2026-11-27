export type Session = {
  id: string;
  username: string;
  displayName: string;
  preferredLanguage: "it" | "en";
  isSuperAdmin: boolean;
  tenantId: string | null;
  selectedTenantId?: string | null;
  mustChangePassword: boolean;
  permissions: string[];
};
export type Field = {
  name: string;
  type: "text" | "integer" | "textarea" | "boolean" | "json" | "reference" | "date" | "tel" | "select" | "multiselect";
  required: boolean;
  reference?: string;
  options?: string[];
  defaultValue?: string;
};
export type Resource = { key: string; fields: Field[]; readOnly?: boolean };
export type Row = { id: string; [key: string]: unknown };
export function tableFields(resource?: Resource): Field[] {
  return resource?.fields.filter(field => !['textarea', 'json'].includes(field.type))
    .filter((field, index) => index < 6 || (resource.key === 'sites' && field.name === 'address')) ?? [];
}
export function siteAddress(row: Row, locale: string): string {
  const locality = [row.postal_code, row.city, row.province].filter(Boolean).join(' ');
  const country = row.country_code ? countryLabel(String(row.country_code), locale) : '';
  return [row.address, locality, country].filter(Boolean).join(', ') || '—';
}
export const navigationSections = [
  {label: "masterData", keys: ["business-partners", "payments", "catalog"]},
  {label: "organization", keys: ["tenants", "companies", "sites", "sales-organizations", "purchasing-organizations"]},
  {label: "warehouse", keys: ["warehouse-types", "warehouses", "warehouse-locations"]},
  {label: "administration", keys: ["settings", "users", "groups", "roles", "permissions"]},
];
// A local navigation container, never a backend CRUD resource.
export const settingsRoute = {key: "settings"} as const;
export const settingsCatalogs = ["countries", "cities"];
export function isCurrentPermission(row: Row): boolean {
  return !["settings.read", "settings.create", "settings.update", "settings.delete"].includes(String(row.code ?? ""));
}
export const partnerSettingsParents: Record<string, string> = {
  "settings-master-data": "settings",
  "settings-business-partners": "settings-master-data",
  "business-partner-numbering": "settings-business-partners",
};
export const catalogRouteParents: Record<string, string> = {
  "catalog-items": "catalog",
  "catalog-item-companies": "catalog-items",
  "catalog-brands": "catalog",
  "catalog-categories": "catalog",
  "catalog-types": "settings-catalog",
  "catalog-units": "settings-system",
  "settings-catalog": "settings-master-data",
  "catalog-numbering": "settings-catalog",
};
export const catalogResources = ["catalog-item-companies", "catalog-items", "catalog-brands", "catalog-units", "catalog-categories", "catalog-types", "catalog-numbering"];
export const catalogRoutes = ["catalog", ...Object.keys(catalogRouteParents)];
export const taxResources = ["tax-codes", "tax-types", "tax-nature-codes", "tax-item-classifications", "tax-partner-classifications", "tax-regimes", "tax-rules", "tax-determination"];
export const taxRouteParents: Record<string, string> = {
  "tax-management": "settings-master-data",
  "tax-codes": "tax-management",
  "tax-types": "tax-management",
  "tax-nature-codes": "tax-management",
  "tax-item-classifications": "tax-management",
  "tax-partner-classifications": "tax-management",
  "tax-regimes": "tax-management",
  "tax-rules": "tax-management",
  "tax-determination": "tax-management",
};
export const taxRoutes = Object.keys(taxRouteParents);
export const routeParents: Record<string, string> = {
  ...taxRouteParents,
  ...catalogRouteParents,
  "settings-system": "settings",
  "currencies": "settings-system",
  "payment-methods": "payments",
  "payment-terms": "payments",
  "payment-settings": "payments",
  "payment-partner-defaults": "payments",
  "payment-schedule": "payments",
  "payment-resolution": "payments",
  "business-partner-companies": "business-partners",
  "tax-item-profiles": "catalog-items",
  "tax-partner-profiles": "business-partners",
  "tax-calculation": "tax-determination",
  "company-tax-configurations": "companies",
  ...partnerSettingsParents,
  ...Object.fromEntries(settingsCatalogs.map(key => [key, "settings-system"])),
};
export function navigationPath(key: string): string[] {
  const path = [key];
  while (Object.hasOwn(routeParents, key)) {key = routeParents[key]; path.unshift(key);}
  return path;
}
export type PermissionBranch = {key: string; rows: Row[]; children: PermissionBranch[]};
export type PermissionDomain = {key: string; resources: PermissionBranch[]};
export function permissionRows(branch: PermissionBranch): Row[] {
  return [...branch.rows, ...branch.children.flatMap(permissionRows)];
}
export function groupPermissions(rows: Row[]): PermissionDomain[] {
  const unique = [...new Map(rows.filter(isCurrentPermission).map(row => [row.id, row])).values()];
  const standard = ["read", "create", "update", "delete"];
  const actionRank = (row: Row) => {
    const rank = standard.indexOf(String(row.code ?? "").split(".")[1]);
    return rank < 0 ? standard.length : rank;
  };
  const byResource = new Map<string, Row[]>();
  for (const row of unique) {
    const resource = String(row.code ?? "").split(".")[0] || "other";
    byResource.set(resource, [...(byResource.get(resource) ?? []), row]);
  }
  for (const entries of byResource.values()) entries.sort((a, b) =>
    actionRank(a) - actionRank(b) || String(a.code).localeCompare(String(b.code)) || a.id.localeCompare(b.id));
  const domains: PermissionDomain[] = [...navigationSections.map(section => ({key: section.label, resources: [] as PermissionBranch[]})), {key: "other", resources: []}];
  const branches = new Map<string, PermissionBranch>();
  const add = (key: string): PermissionBranch => {
    const existing = branches.get(key);
    if (existing) return existing;
    const branch: PermissionBranch = {key, rows: byResource.get(key) ?? [], children: []};
    branches.set(key, branch);
    if (Object.hasOwn(routeParents, key)) add(routeParents[key]).children.push(branch);
    else {
      const domain = navigationSections.find(section => section.keys.includes(key))?.label ?? "other";
      domains.find(entry => entry.key === domain)!.resources.push(branch);
    }
    return branch;
  };
  const ordered = [...navigationSections.flatMap(section => section.keys), ...Object.keys(routeParents), ...[...byResource.keys()].sort()];
  for (const key of ordered) if (byResource.has(key)) add(key);
  for (const domain of domains) {
    const order = navigationSections.find(section => section.label === domain.key)?.keys;
    if (order) domain.resources.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  }
  return domains.filter(domain => domain.resources.length);
}
type PermissionMessages = {resources: Record<string, string>; permissionActions: Record<string, string>; app?: Record<string, string>};
export function permissionLabel(row: Row, messages: PermissionMessages): string {
  const code = String(row.code ?? "");
  const [resource, action] = code.split(".");
  if (!resource || !action || code !== `${resource}.${action}` || resource === "tenants" ||
      !can({isSuperAdmin: true, tenantId: null, permissions: []}, resource, action)) return code;
  const label = resource.endsWith("-profiles") && resource.startsWith("tax-") && ["assign", "schedule"].includes(action)
    ? `${action}_profile` : resource.endsWith("-classifications") && action === "install_templates" ? "install_classification_templates" : action;
  return `${messages.resources[resource]} · ${messages.permissionActions[label]}`;
}
export function permissionMatches(row: Row, query: string, messages: PermissionMessages[]): boolean {
  const resource = String(row.code ?? "").split(".")[0];
  const path = navigationPath(resource);
  const domain = navigationSections.find(section => section.keys.includes(path[0]))?.label ?? "otherPermissions";
  return [String(row.code ?? ""), ...messages.flatMap((locale) => [permissionLabel(row, locale), locale.app?.[domain] ?? "", ...path.map(key =>
    key === "settings-master-data" ? locale.app?.masterData ?? "" : key === "settings-system" ? locale.app?.system ?? "" : locale.resources[key === "settings-business-partners" ? "business-partners" : key] ?? key)])]
    .some((value) => value.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
}
export function countryLabel(code: string, locale: string) {
  return `${new Intl.DisplayNames([locale === "en" ? "en" : "it"], {type: "region"}).of(code)} (${code})`;
}
export function formatFieldValue(
  field: Field,
  value: unknown,
  locale: string,
  languageLabel: (language: "it" | "en") => string,
  optionLabel: (option: string) => string = () => "—",
) {
  if (value == null || value === "") return "—";
  if (field.name === "preferred_language" && (value === "it" || value === "en"))
    return languageLabel(value);
  if (field.name === "country_code") return countryLabel(String(value), locale);
  if (field.name === "site_type") return optionLabel(String(value));
  if (field.type === "multiselect") {
    const selected = Array.isArray(value) ? (field.options ?? []).filter(option => value.includes(option)) : [];
    return selected.length ? selected.map(optionLabel).join(", ") : "—";
  }
  if (field.type === "date" && /^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
    const date = new Date(`${value}T00:00:00Z`);
    if (!Number.isNaN(date.getTime()))
      return new Intl.DateTimeFormat(locale === "en" ? "en-US" : "it-IT", {
        year: "numeric", month: "2-digit", day: "2-digit", timeZone: "UTC",
      }).format(date);
  }
  return String(value);
}
export const resourceKeys = [
  ...taxResources,
  "tax-calculation",
  "tax-item-profiles",
  "tax-partner-profiles",
  "company-tax-configurations",
  ...catalogResources,
  "payments",
  "payment-methods",
  "payment-terms",
  "payment-settings",
  "payment-schedule",
  "payment-partner-defaults",
  "payment-resolution",
  "business-partner-companies",
  "business-partners",
  "business-partner-numbering",
  "countries",
  "cities",
  "currencies",
  "tenants",
  "companies",
  "sites",
  "sales-organizations",
  "purchasing-organizations",
  "warehouse-types",
  "warehouses",
  "warehouse-locations",
  "users",
  "groups",
  "roles",
  "permissions",
];
export function can(
  session: Pick<Session, "isSuperAdmin" | "permissions"> & Partial<Pick<Session, "tenantId">>,
  resource: string,
  action: string,
  row?: Row | null,
) {
  if (!resourceKeys.includes(resource)) return false;
  if (resource === "payments") return false;
  if (["tax-types", "tax-nature-codes", "tax-regimes"].includes(resource) && action !== "read") return false;
  if (resource === "company-tax-configurations" && !["read", "create", "update", "activate", "suspend", "register", "close", "assign_regime", "schedule_regime"].includes(action)) return false;
  if (resource === "tax-codes" && !["read", "create", "update", "schedule", "deactivate", "reactivate", "install_templates"].includes(action)) return false;
  if (resource === "tax-rules" && !["read", "create", "update", "validate", "publish", "withdraw", "install_templates"].includes(action)) return false;
  if (resource === "tax-determination" && !["read", "simulate", "determine"].includes(action)) return false;
  if (resource === "tax-calculation" && !["read", "simulate", "calculate"].includes(action)) return false;
  if (["tax-item-classifications", "tax-partner-classifications"].includes(resource) && !["read", "create", "update", "deactivate", "reactivate", "install_templates"].includes(action)) return false;
  if (["tax-item-profiles", "tax-partner-profiles"].includes(resource) && !["read", "assign", "schedule"].includes(action)) return false;
  if (["catalog-units", "catalog-brands", "catalog-item-companies"].includes(resource) && !["read", "create", "update"].includes(action)) return false;
  if (resource === "catalog-items" && !["read", "create", "update", "activate", "deactivate", "archive"].includes(action)) return false;
  if (resource === "catalog-numbering" && !["read", "update"].includes(action)) return false;
  if (resource === "business-partners" && !["read", "create", "update"].includes(action)) return false;
  if (resource === "business-partner-companies" && !["read", "create", "update", "use_customer", "use_supplier"].includes(action)) return false;
  if (resource === "business-partner-numbering" && !["read", "update"].includes(action)) return false;
  if (resource === "payment-schedule" && action !== "preview") return false;
  if (["payment-settings", "payment-partner-defaults"].includes(resource) && !["read", "update"].includes(action)) return false;
  if (resource === "payment-resolution" && action !== "read") return false;
  if (["payment-methods", "payment-terms"].includes(resource) && !["read", "create", "update"].includes(action)) return false;
  const standard = ["read", "create", "update", "delete"];
  const extra: Record<string, string[]> = {
    "tax-codes": ["schedule", "deactivate", "reactivate", "install_templates"],
    "tax-rules": ["validate", "publish", "withdraw", "install_templates"],
    "tax-determination": ["simulate", "determine"],
    "tax-calculation": ["simulate", "calculate"],
    "tax-item-classifications": ["deactivate", "reactivate", "install_templates"],
    "tax-partner-classifications": ["deactivate", "reactivate", "install_templates"],
    "tax-item-profiles": ["assign", "schedule"],
    "tax-partner-profiles": ["assign", "schedule"],
    "company-tax-configurations": ["activate", "suspend", "register", "close", "assign_regime", "schedule_regime"],
    "catalog-items": ["activate", "deactivate", "archive"],
    "payment-schedule": ["preview"],
    "business-partner-companies": ["use_customer", "use_supplier"],
    "purchasing-organizations": ["assign_scope"],
    users: ["reset_password"],
    groups: ["assign_users"],
    roles: ["assign", "assign_permissions", "assign_companies"],
  };
  if (resource === "permissions" ? action !== "read" :
      !standard.includes(action) && !extra[resource]?.includes(action)) return false;
  if (resource === "users" && row?.tenant_id === null && action !== "read")
    return false;
  const global = session.isSuperAdmin && session.tenantId === null;
  if (resource === "countries" || resource === "cities" || resource === "currencies") return global || action === "read" && session.permissions.includes(`${resource}.read`);
  return global || (resource !== "tenants" && session.permissions.includes(`${resource}.${action}`));
}
export function relationOptions(target: string, rows: Row[]): Row[] {
  return target === "users" ? rows.filter((row) => row.tenant_id !== null) : rows;
}
export const relations: Record<string, {key: string; target: string; authority: [string, string]}[]> = {
  users: [{key: "user-roles", target: "roles", authority: ["roles", "assign"]}],
  groups: [
    {key: "group-users", target: "users", authority: ["groups", "assign_users"]},
    {key: "group-roles", target: "roles", authority: ["roles", "assign"]},
  ],
  roles: [{key: "role-permissions", target: "permissions", authority: ["roles", "assign_permissions"]}],
};
export function canRelation(session: Session, owner: string, key: string, action: "read" | "assign", row: Row) {
  const relation = relations[owner]?.find((entry) => entry.key === key);
  if (!relation || (owner === "users" && row.tenant_id === null)) return false;
  return can(session, owner, "read", row) && can(session, relation.target, "read") &&
    (action === "read" || can(session, ...relation.authority));
}
export function normalizeValues(
  fields: Field[],
  values: Record<string, unknown>,
) {
  return Object.fromEntries(
    fields.map((f) => [
      f.name,
      f.name === "iso_code" && typeof values[f.name] === "string"
        ? String(values[f.name]).toUpperCase()
        : f.type === "integer"
        ? (values[f.name] === "" || values[f.name] == null ? null : (() => { const value = Number(values[f.name]); if (!Number.isSafeInteger(value)) throw new Error("Invalid integer"); return value; })())
        : f.type === "multiselect"
        ? (f.options ?? []).filter(option => Array.isArray(values[f.name]) && (values[f.name] as unknown[]).includes(option))
        : f.type === "json"
        ? JSON.parse(String(values[f.name]))
        : f.type === "boolean"
          ? Boolean(values[f.name])
          : (values[f.name] === "" || values[f.name] == null) && f.defaultValue !== undefined
            ? f.defaultValue
          : values[f.name] === "" && !f.required
            ? null
            : values[f.name],
    ]),
  );
}
export const rowLabel = (row: Row) =>
  String(
    (row.country_id && row.name && row.postal_code ? [row.name, row.postal_code, row.province].filter(Boolean).join(" · ") : undefined) ??
    ([row.first_name, row.last_name].filter(Boolean).join(" ") || undefined) ??
    row.name ??
      row.username ??
      row.key ??
      row.code ??
      row.id,
  );
