export const onboardingPath = "/api/v1/platform/tenant-roles";
export type Invitation = { invitationId: string; revision: number; active: boolean; expiresAt: string };
export type PendingRequest = { requestId: string; invitationId: string; revision: number; issuer: string; subject: string; expiresAt: string; approved: boolean; available: boolean; membershipId: string | null; internalIdentityId: string | null };
export type OnboardingData = { state: string; mode: "owner" | "delegate"; tenantId: string; invitations: Invitation[]; requests: PendingRequest[] };
export type PendingStatus = { requestId: string; tenantId: string; expiresAt: string; revision: number; approved: boolean };
export type OnboardingInitial = { status: number; data: OnboardingData | null; tenants: { id: string; name: string }[] };
