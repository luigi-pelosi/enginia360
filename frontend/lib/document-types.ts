export const documentTypesPath = "/api/v1/document-types";
export type QuantityEffect = "Load" | "Unload" | "Transfer" | "None";
export const effectLabels: Readonly<Record<QuantityEffect, string>> = { Load: "Carico", Unload: "Scarico", Transfer: "Trasferimento", None: "Nessun effetto" };
export type DocumentTypeVersion = Readonly<{ id: string; legalEntityId: string; revision: number; label: string; effect: QuantityEffect; occurredAt: string }>;
export type DocumentTypesData = Readonly<{
  paths?: ReadonlyArray<DevelopmentPath>; canManagePaths?: boolean;
  state: string; companies: ReadonlyArray<Readonly<{ id: string; name: string }>>; selectedCompanyId: string | null;
  canCreate: boolean; canEdit: boolean; items: ReadonlyArray<DocumentTypeVersion>; detail: DocumentTypeVersion | null;
  history: ReadonlyArray<DocumentTypeVersion>; selectedVersion: DocumentTypeVersion | null;
}>;
export type DocumentTypesQuery = { legalEntityId?: string; search?: string; after?: string; id?: string; revision?: string; beforeRevision?: string };
export function documentTypesReadPath(query: DocumentTypesQuery = {}) {
  const params = new URLSearchParams();
  for (const key of ["legalEntityId", "search", "after", "id", "revision", "beforeRevision"] as const) if (query[key] !== undefined) params.set(key, query[key]);
  return documentTypesPath + (params.size ? "?" + params.toString() : "");
}
export function finiteDocumentTypesRead(path: string): boolean {
  const [route, query, extra] = path.split("?");
  if (route !== documentTypesPath || extra !== undefined) return false;
  const params = new URLSearchParams(query); const keys = [...params.keys()];
  if (new Set(keys).size !== keys.length) return false;
  if ((params.has("revision") || params.has("beforeRevision")) && !params.has("id")) return false;
  if (!params.has("legalEntityId") && keys.length) return false;
  return keys.every(key => key === "search" ? [...(params.get(key) || "")].length <= 200 && !/[\u0000-\u001f\u007f-\u009f\ud800-\udfff]/u.test(params.get(key) || "")
    : ["revision", "beforeRevision"].includes(key) ? /^[1-9][0-9]{0,9}$/.test(params.get(key) || "") && Number(params.get(key)) <= 2147483647
    : ["legalEntityId", "after", "id"].includes(key) && /^(?!00000000-0000-0000-0000-000000000000$)[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(params.get(key) || ""));
}

export type DevelopmentPath = Readonly<{sourceTypeId:string; destinationTypeId:string; revision:number; enabled:boolean; allowCrossSite:boolean; occurredAt:string}>;
