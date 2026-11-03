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
  const eligibility = await privateRead(
    "/api/v1/platform/administration-eligibility",
    cookie,
  );
  if (eligibility.status !== 200 || !eligibility.value?.canAdministerPlatform)
    return (
      <OrganizationWorkspace
        initial={{
          status: eligibility.status === 200 ? 403 : eligibility.status,
          tenants: [],
          hierarchy: null,
        }}
      />
    );
  const directory = await privateRead("/api/v1/platform/tenants", cookie);
  const { tenant } = await searchParams;
  const target =
    directory.status === 200 &&
    directory.value.tenants.some((t: { id: string }) => t.id === tenant)
      ? tenant
      : undefined;
  const hierarchy = target
    ? await privateRead("/api/v1/platform/tenants/" + target, cookie)
    : null;
  return (
    <OrganizationWorkspace
      initial={{
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
