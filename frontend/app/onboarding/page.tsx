import React from "react";
import { cookies } from "next/headers";
import { privateRead } from "../../lib/private-backend";
import { PendingOnboardingWorkspace } from "../../components/onboarding-workspace";
export const dynamic = "force-dynamic";
export const revalidate = 0;
export default async function OnboardingPage({ searchParams }: { searchParams: Promise<{ invitation?: string }> }) {
  const { invitation } = await searchParams;
  const exact = typeof invitation === "string" && /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(invitation) ? invitation : null;
  const result = await privateRead("/auth/onboarding/status", (await cookies()).toString());
  return <PendingOnboardingWorkspace status={result.status} initial={result.status === 200 ? result.value : null} invitation={exact} />;
}
