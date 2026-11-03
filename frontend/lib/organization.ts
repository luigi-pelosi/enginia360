export type Kind = "tenant" | "company" | "site" | "warehouse";
export type OrganizationNode = {
  id: string;
  name: string;
  revision: number;
  parentId?: string | null;
};
export type Hierarchy = {
  tenant: OrganizationNode;
  companies: OrganizationNode[];
  sites: OrganizationNode[];
  warehouses: OrganizationNode[];
};
export type OrganizationMembership = { membershipId: string; internalIdentityId: string; bindingHash: string; active: boolean; revision: number; };
export type InitialOrganization = {
  status: number;
  mode?: "owner" | "delegate";
  memberships?: OrganizationMembership[];
  tenants: OrganizationNode[];
  hierarchy: Hierarchy | null;
};
export type Edit = {
  kind: Kind;
  operation: "create" | "rename";
  node: OrganizationNode | null;
  parentId: string | null;
};
export const directoryPath = "/api/v1/platform/tenants";
export class HttpFailure extends Error {
  constructor(public status: number) {
    super("HTTP " + status);
  }
}
export async function readJson(path: string, options: RequestInit = {}) {
  const response = await fetch(path, {
    ...options,
    cache: "no-store",
    redirect: "error",
    signal: AbortSignal.timeout(12000),
  });
  if (!response.ok) throw new HttpFailure(response.status);
  return response.json();
}
