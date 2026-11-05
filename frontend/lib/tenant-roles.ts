export const tenantRolePath = "/api/v1/platform/tenant-roles";
export type TrustedMember = {
  membershipId: string;
  internalIdentityId: string;
  bindingHash: string;
  accessEnabled: boolean;
  accessRevision: number;
  organizationDelegationActive: boolean;
  isCurrentIdentity: boolean;
  canEnableAccess: boolean;
  active: boolean;
  resourceId: string | null;
  revision: number;
};
export type TenantRoleObject = {
  resourceId: string;
  tenantId: string;
  revision: number;
  kind: string;
  label?: string;
  action?: string;
  legalEntityId?: string | null;
  siteId?: string | null;
  warehouseId?: string | null;
  permissionIds?: string[];
  roleId?: string;
  membershipId?: string;
  active?: boolean;
};
export type TenantRoleData = {
  state: string;
  mode: string;
  tenantId: string;
  actions: string[];
  memberships: TrustedMember[];
  permissions: TenantRoleObject[];
  roles: TenantRoleObject[];
  assignments: TenantRoleObject[];
  companies?: { legalEntityId: string; name: string }[];
  sites?: { siteId: string; legalEntityId: string; name: string }[];
  warehouses: {
    warehouseId: string;
    legalEntityId: string;
    siteId: string;
    name: string;
  }[];
};
export type InitialTenantRoles = {
  status: number;
  data: TenantRoleData | null;
  tenants: { id: string; name: string }[];
};
