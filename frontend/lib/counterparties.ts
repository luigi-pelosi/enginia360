export const counterpartyPath = "/api/v1/counterparties/management";
export type Counterparty = { id: string; legalName: string; fiscalIdentifier: string; registeredOffice: string; isSupplier: boolean; revision: number };
export type CompanyDestination = { id: string; address: string; published: boolean; ownerLegalEntityId: string; revision: number };
export type CounterpartyData = {
  state: string; tenantId: string; authority: { state: string; version: number };
  canCreate: boolean; canEdit: boolean; canWriteRoles: boolean;
  items: Counterparty[]; detail: Counterparty | null;
  companies: { id: string; name: string; canWrite: boolean }[];
  companyId?: string; destinations?: CompanyDestination[];
};
export type CounterpartyQuery = { search?: string; after?: string; id?: string; company?: string };
export function counterpartyReadPath(query: CounterpartyQuery = {}) {
  const params = new URLSearchParams();
  for (const key of ["search", "after", "id", "company"] as const) if (query[key]) params.set(key, query[key]);
  return counterpartyPath + (params.size ? "?" + params.toString() : "");
}
export function finiteCounterpartyRead(path: string): boolean {
  const [route, query, extra] = path.split("?");
  if (route !== counterpartyPath || extra !== undefined) return false;
  const params = new URLSearchParams(query);
  const keys = [...params.keys()];
  if (new Set(keys).size !== keys.length) return false;
  return keys.every((key) => key === "search" ? [...(params.get(key) || "")].length <= 200 && !/[\u0000-\u001f\u007f]/.test(params.get(key) || "")
    : ["after", "id", "company"].includes(key) && /^(?!00000000-0000-0000-0000-000000000000$)[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(params.get(key) || ""));
}
