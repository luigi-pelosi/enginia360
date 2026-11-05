import type { DocumentTypeVersion } from "./document-types";
export const documentsPath = "/api/v1/documents";
export type DocumentsQuery = { legalEntityId?: string; siteId?: string; warehouseId?: string; id?: string; search?: string; after?: string; selection?: string; selectionAfter?: string; ledgerAfter?: string };
export type CatalogChoice = Readonly<{ id: string; revision: number; kind: "Article" | "Service"; label: string }>;
export type DocumentLine = Readonly<{ id: string; itemId: string; catalogRevision: number; kind: "Article" | "Service"; label: string; quantity: string; warehouseId: string | null; destinationWarehouseId: string | null }>;
export type QuantityPolicy = Readonly<{ revision: number; allowNegative: boolean; occurredAt: string | null }>;
export type DocumentSnapshot = Readonly<{ id: string; legalEntityId: string; siteId: string; documentTypeId: string; revision: number; state: "Draft" | "Confirmed"; title: string; confirmedAt: string | null; lines: ReadonlyArray<DocumentLine>; appliedConfiguration: Readonly<{ documentType: DocumentTypeVersion; policy: QuantityPolicy }> | null }>;
export type DocumentsData = Readonly<{
 state: string; companies: ReadonlyArray<Readonly<{id: string; name: string}>>;
 sites: ReadonlyArray<Readonly<{id: string; name: string; canReadDocuments: boolean}>>;
 warehouses: ReadonlyArray<Readonly<{id: string; name: string; canApply: boolean; canReadStock: boolean}>>;
 items: ReadonlyArray<DocumentSnapshot>; detail: DocumentSnapshot | null;
 types: ReadonlyArray<DocumentTypeVersion>; catalog: ReadonlyArray<CatalogChoice>;
 policy: QuantityPolicy | null; policyHistory: ReadonlyArray<QuantityPolicy>;
 balances: ReadonlyArray<Readonly<{itemId: string; label: string; quantity: string}>>;
 ledger: ReadonlyArray<Readonly<{id: string; documentId: string; lineId: string; warehouseId: string; itemId: string; catalogRevision: number; label: string; leg: string; quantity: string; occurredAt: string; canReadDocument: boolean}>>;
 canSave: boolean; canConfirm: boolean; canManagePolicy: boolean;
}>;
export function documentsReadPath(query: DocumentsQuery = {}) {
 const params = new URLSearchParams();
 for (const key of ["legalEntityId", "siteId", "warehouseId", "id", "search", "after", "selection", "selectionAfter", "ledgerAfter"] as const) if (query[key] !== undefined) params.set(key, query[key]);
 return documentsPath + (params.size ? "?" + params.toString() : "");
}
export function finiteDocumentsRead(path: string): boolean {
 const [route, query, extra] = path.split("?");
 if (route !== documentsPath || extra !== undefined) return false;
 const params = new URLSearchParams(query); const keys = [...params.keys()];
 if (new Set(keys).size !== keys.length || (!params.has("legalEntityId") && keys.length > 0)
  || (!params.has("siteId") && ["warehouseId", "id", "selection", "search", "after", "selectionAfter", "ledgerAfter"].some(key => params.has(key)))
  || (params.has("selectionAfter") && !params.has("selection")) || (params.has("ledgerAfter") && !params.has("warehouseId") && !params.has("id"))) return false;
 return keys.every(key => key === "search" ? [...(params.get(key) || "")].length <= 200 && !/[\u0000-\u001f\u007f-\u009f\ud800-\udfff]/u.test(params.get(key) || "")
  : key === "selection" ? ["catalog", "types"].includes(params.get(key) || "")
  : ["legalEntityId", "siteId", "warehouseId", "id", "after", "selectionAfter", "ledgerAfter"].includes(key) && /^(?!00000000-0000-0000-0000-000000000000$)[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(params.get(key) || ""));
}
