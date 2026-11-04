import React from "react";
import { cookies } from "next/headers";
import { privateRead } from "../../lib/private-backend";
import { OnboardingAdministration } from "../../components/onboarding-workspace";
import { onboardingPath } from "../../lib/onboarding";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export default async function OnboardingAdminPage({ searchParams }: { searchParams: Promise<{ tenant?: string }> }) {
  const cookie = (await cookies()).toString();
  const workspace = await privateRead(onboardingPath + "/onboarding/workspace", cookie);
  if (workspace.status !== 200) return <OnboardingAdministration initial={{ status: workspace.status, data: null, tenants: [] }} />;
  const tenants: { id: string; name: string }[] = workspace.value.tenants || [];
  const { tenant } = await searchParams;
  if (workspace.value.mode === "owner" && tenant && tenants.some(t => t.id === tenant)) {
    const selected = await privateRead(onboardingPath + "/" + tenant + "/onboarding", cookie);
    return <OnboardingAdministration initial={{ status: selected.status, data: selected.value, tenants }} />;
  }
  return <OnboardingAdministration initial={{ status: 200, data: workspace.value.mode === "delegate" ? workspace.value : null, tenants }} />;
}
