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
  type: "text" | "textarea" | "boolean" | "json" | "reference" | "date" | "tel" | "select" | "multiselect";
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
  {label: "organization", keys: ["tenants", "companies", "sites", "sales-organizations", "purchasing-organizations"]},
  {label: "warehouse", keys: ["warehouse-types", "warehouses", "warehouse-locations"]},
  {label: "administration", keys: ["settings", "users", "groups", "roles", "permissions"]},
];
export type PermissionDomain = {key: string; resources: {key: string; rows: Row[]}[]};
export function groupPermissions(rows: Row[]): PermissionDomain[] {
  const unique = [...new Map(rows.map(row => [row.id, row])).values()];
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
  const domains: PermissionDomain[] = navigationSections.map(section => ({
    key: section.label,
    resources: section.keys.filter(key => byResource.has(key)).map(key => ({key, rows: byResource.get(key)!})),
  })).filter(domain => domain.resources.length);
  const known = new Set(navigationSections.flatMap(section => section.keys));
  const fallback = [...byResource.keys()].filter(key => !known.has(key)).sort().map(key => ({key, rows: byResource.get(key)!}));
  if (fallback.length) domains.push({key: "other", resources: fallback});
  return domains;
}
type PermissionMessages = {resources: Record<string, string>; permissionActions: Record<string, string>; app?: Record<string, string>};
export function permissionLabel(row: Row, messages: PermissionMessages): string {
  const code = String(row.code ?? "");
  const [resource, action] = code.split(".");
  if (!resource || !action || code !== `${resource}.${action}` || resource === "tenants" ||
      !can({isSuperAdmin: true, tenantId: null, permissions: []}, resource, action)) return code;
  return `${messages.resources[resource]} · ${messages.permissionActions[action]}`;
}
export function permissionMatches(row: Row, query: string, messages: PermissionMessages[]): boolean {
  const resource = String(row.code ?? "").split(".")[0];
  const domain = navigationSections.find(section => section.keys.includes(resource))?.label ?? "otherPermissions";
  return [String(row.code ?? ""), ...messages.flatMap((locale) => [permissionLabel(row, locale), locale.app?.[domain] ?? ""])]
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
  "countries",
  "cities",
  "tenants",
  "companies",
  "sites",
  "sales-organizations",
  "purchasing-organizations",
  "warehouse-types",
  "warehouses",
  "warehouse-locations",
  "settings",
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
  const standard = ["read", "create", "update", "delete"];
  const extra: Record<string, string[]> = {
    "purchasing-organizations": ["assign_scope"],
    users: ["reset_password"],
    groups: ["assign_users"],
    roles: ["assign", "assign_permissions"],
  };
  if (resource === "permissions" ? action !== "read" :
      !standard.includes(action) && !extra[resource]?.includes(action)) return false;
  if (resource === "users" && row?.tenant_id === null && action !== "read")
    return false;
  const global = session.isSuperAdmin && session.tenantId === null;
  if (resource === "countries" || resource === "cities") return action === "read" || global;
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
