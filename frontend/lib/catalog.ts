export const catalogPath = "/api/v1/catalog/management";
export type CatalogKind = "Article" | "Service";
export type CatalogIdentity = Readonly<{ id: string; kind: CatalogKind; label: string; revision: number }>;
export type CatalogData = Readonly<{
  state: string; tenantId: string; authority: Readonly<{ state: string; version: number }>;
  canCreate: boolean; canEdit: boolean; items: CatalogIdentity[]; detail: CatalogIdentity | null;
}>;
export type CatalogQuery = { search?: string; after?: string; id?: string; kind?: CatalogKind };
export function catalogReadPath(query: CatalogQuery = {}) {
  const params = new URLSearchParams();
  for (const key of ["search", "after", "id", "kind"] as const) if (query[key]) params.set(key, query[key]);
  return catalogPath + (params.size ? "?" + params.toString() : "");
}
export function finiteCatalogRead(path: string): boolean {
  const [route, query, extra] = path.split("?");
  if (route !== catalogPath || extra !== undefined) return false;
  const params = new URLSearchParams(query); const keys = [...params.keys()];
  if (new Set(keys).size !== keys.length) return false;
  return keys.every(key => key === "search" ? [...(params.get(key) || "")].length <= 200 && !/[\u0000-\u001f\u007f]/.test(params.get(key) || "")
    : key === "kind" ? ["", "Article", "Service"].includes(params.get(key) || "")
    : ["after", "id"].includes(key) && /^(?!00000000-0000-0000-0000-000000000000$)[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(params.get(key) || ""));
}
export const kindLabel = (kind: CatalogKind) => kind === "Article" ? "Articolo" : "Servizio";
