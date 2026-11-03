import React from "react";
import { cookies } from "next/headers";
import { privateRead } from "../../lib/private-backend";
import { OrganizationWorkspace } from "../../components/organization-workspace";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export default async function OrganizationPage({
  searchParams,
}: {
  searchParams: Promise<{ tenant?: string }>;
}) {
  const cookie = (await cookies()).toString();
  const session = await privateRead("/auth/session", cookie);
  if (session.status !== 200 || !session.value?.authenticated)
    return (
      <OrganizationWorkspace
        initial={{
          status: session.status === 200 ? 401 : session.status,
          tenants: [],
          hierarchy: null,
        }}
      />
    );
  const directory = await privateRead("/api/v1/platform/tenants/workspace", cookie);
  if (directory.status !== 200)
    return (
      <OrganizationWorkspace
        initial={{
          status: directory.status,
          tenants: [],
          hierarchy: null,
        }}
      />
    );
  const { tenant } = await searchParams;
  const target =
    directory.status === 200 &&
    directory.value.tenants.some((t: { id: string }) => t.id === tenant)
      ? tenant
      : directory.value.mode === "delegate" && !tenant ? directory.value.tenants[0]?.id : undefined;
  const hierarchy = target
    ? await privateRead("/api/v1/platform/tenants/" + target, cookie)
    : null;
  const grants = target && directory.value.mode === "owner"
    ? await privateRead("/api/v1/platform/tenants/" + target + "/delegations", cookie) : null;
  return (
    <OrganizationWorkspace
      initial={{
        mode: directory.value.mode,
        memberships: grants?.value?.memberships || [],
        status:
          hierarchy && hierarchy.status !== 200
            ? hierarchy.status
            : directory.status,
        tenants: directory.value?.tenants || [],
        hierarchy: hierarchy?.value || null,
      }}
    />
  );
}
