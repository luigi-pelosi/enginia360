import React from "react";
import { cookies } from "next/headers";
import { privateRead } from "../../lib/private-backend";
import { TenantRoleWorkspace } from "../../components/tenant-role-workspace";
import { tenantRolePath } from "../../lib/tenant-roles";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export default async function TenantRolesPage({
  searchParams,
}: {
  searchParams: Promise<{ tenant?: string }>;
}) {
  const cookie = (await cookies()).toString();
  const session = await privateRead("/auth/session", cookie);
  if (session.status !== 200 || !session.value?.authenticated)
    return (
      <TenantRoleWorkspace
        initial={{
          status: session.status === 200 ? 401 : session.status,
          data: null,
          tenants: [],
        }}
      />
    );
  const workspace = await privateRead(tenantRolePath + "/workspace", cookie);
  if (workspace.status !== 200)
    return (
      <TenantRoleWorkspace
        initial={{ status: workspace.status, data: null, tenants: [] }}
      />
    );
  const { tenant } = await searchParams;
  const tenants: { id: string; name: string }[] = workspace.value.tenants || [];
  if (
    workspace.value.mode === "owner" &&
    tenant &&
    tenants.some((t) => t.id === tenant)
  ) {
    const selected = await privateRead(tenantRolePath + "/" + tenant, cookie);
    return (
      <TenantRoleWorkspace
        initial={{ status: selected.status, data: selected.value, tenants }}
      />
    );
  }
  return (
    <TenantRoleWorkspace
      initial={{
        status: 200,
        data: workspace.value.mode === "delegate" ? workspace.value : null,
        tenants,
      }}
    />
  );
}
