import { check, decimal, positive, record, uuid } from './contracts';
// R03.c runtime parsers for the EXISTING closure contracts. The legacy parseSummary assumes one group equal to the order,
// revision = row count and one row per kind; none of that holds for the persisted multigroup snapshot pinned by a request.
const money = (v: unknown): v is string => typeof v === 'string' && /^\d{1,12}\.\d{6}$/.test(v);
const nonNegative = (n: unknown): n is number => typeof n === 'number' && Number.isSafeInteger(n) && n >= 0;
const micro = (v: string) => BigInt(v.replace('.', ''));

export type SnapshotLine = Readonly<{ id: string; orderId: string; catalogItemId: string; catalogVersion: number; catalogLabel: string; kind: 'Service' | 'Part'; quantity: string; unitPrice: string; discountPercent: string; netAmount: string; taxRate: string; payerId: string; workingGroupId: string; configurationVersion: number }>;
export type Snapshot = Readonly<{ orderId: string; payerId: string; revision: number; lines: readonly SnapshotLine[]; netAmount: string; taxAmount: string; total: string; currency: 'EUR'; policy: 'Case001' }>;

export function parseSnapshot(value: unknown, orderId: string): Snapshot {
  const s = record(value);
  check(s.orderId === orderId && uuid(s.payerId) && nonNegative(s.revision) && Array.isArray(s.lines) && s.currency === 'EUR' && s.policy === 'Case001' && money(s.netAmount) && money(s.taxAmount) && money(s.total));
  const ids = new Set<string>(); let net = 0n;
  for (const item of s.lines as unknown[]) {
    const l = record(item);
    check(uuid(l.id) && !ids.has(l.id) && uuid(l.catalogItemId) && l.orderId === orderId && l.payerId === s.payerId && uuid(l.workingGroupId) && positive(l.catalogVersion) && positive(l.configurationVersion) && typeof l.catalogLabel === 'string' && (l.kind === 'Service' || l.kind === 'Part') && ['quantity', 'unitPrice', 'discountPercent', 'taxRate'].every(k => decimal(l[k])) && money(l.netAmount));
    ids.add(l.id); net += micro(l.netAmount);
  }
  check(micro(s.netAmount) === net && micro(s.total) === net + micro(s.taxAmount));
  return s as unknown as Snapshot;
}

const DELIVERY = ['Queued', 'Received', 'Retrying', 'Uncertain', 'NeedsReconciliation', 'Completed', 'Rejected'];
const REFERENCE = /^[A-Za-z0-9][A-Za-z0-9-]{0,63}$/, CODE = /^[a-z0-9_]{1,64}$/;
export type Delivery = Readonly<{ state: 'Queued' | 'Received' | 'Retrying' | 'Uncertain' | 'NeedsReconciliation' | 'Completed' | 'Rejected'; attempts: number; failures: number; lastAttemptAt: string | null; nextAttemptAt: string | null; lastError: string | null }>;
export type AdministrativeRequest = Readonly<{ id: string; orderId: string; legalEntityId: string; siteId: string; destination: 'External'; destinationVersion: number; contractVersion: 1; summary: Snapshot; requestedAt: string; operatorId: string; status: 'Pending' | 'Confirmed' | 'Rejected'; externalReference: string | null; rejectionCode: string | null; outcomeAt: string | null; delivery: Delivery }>;
export function parseRequest(value: unknown, orderId: string): AdministrativeRequest {
  const r = record(value);
  check(uuid(r.id) && r.orderId === orderId && uuid(r.legalEntityId) && uuid(r.siteId) && r.destination === 'External' && positive(r.destinationVersion) && r.contractVersion === 1 && typeof r.requestedAt === 'string' && uuid(r.operatorId));
  const summary = parseSnapshot(r.summary, orderId);
  const d = record(r.delivery);
  check(DELIVERY.includes(d.state as string) && nonNegative(d.attempts) && nonNegative(d.failures) && ['lastAttemptAt', 'nextAttemptAt', 'lastError'].every(k => d[k] === null || typeof d[k] === 'string'));
  // Business outcome fields are exclusive: Pending has none; Confirmed has only a stable reference; Rejected has only a code.
  if (r.status === 'Pending') check(r.externalReference === null && r.rejectionCode === null && r.outcomeAt === null);
  else if (r.status === 'Confirmed') check(typeof r.externalReference === 'string' && REFERENCE.test(r.externalReference) && r.rejectionCode === null && typeof r.outcomeAt === 'string');
  else if (r.status === 'Rejected') check(typeof r.rejectionCode === 'string' && CODE.test(r.rejectionCode) && r.externalReference === null && typeof r.outcomeAt === 'string');
  else check(false);
  return { ...r, summary } as unknown as AdministrativeRequest;
}

export type TechnicalClosure = Readonly<{ id: string; orderId: string; revision: number; closedAt: string; operatorId: string }>;
export function parseTechnical(value: unknown, orderId: string): TechnicalClosure {
  const t = record(value);
  check(uuid(t.id) && t.orderId === orderId && nonNegative(t.revision) && typeof t.closedAt === 'string' && uuid(t.operatorId));
  return t as unknown as TechnicalClosure;
}
export type AdministrativeClosure = Readonly<{ id: string; orderId: string; requestId: string; externalReference: string; closedAt: string; operatorId: string }>;
export function parseAdministrativeClosure(value: unknown, orderId: string): AdministrativeClosure {
  const c = record(value);
  check(uuid(c.id) && c.orderId === orderId && uuid(c.requestId) && typeof c.externalReference === 'string' && REFERENCE.test(c.externalReference) && typeof c.closedAt === 'string' && uuid(c.operatorId));
  return c as unknown as AdministrativeClosure;
}

export type Gate = Readonly<{ orderId: string; status: 'Clear' | 'Blocked'; requirements: readonly Readonly<{ lineId: string; catalogItemId: string; requiredInstalled: string; returned: string; outstanding: string }>[] }>;
export function parseGate(value: unknown, orderId: string): Gate {
  const g = record(value);
  check(g.orderId === orderId && (g.status === 'Clear' || g.status === 'Blocked') && Array.isArray(g.requirements) && Array.isArray(g.requirements));
  let outstanding = false;
  for (const item of g.requirements as unknown[]) { const r = record(item); check(uuid(r.lineId) && uuid(r.catalogItemId) && ['requiredInstalled', 'returned', 'outstanding'].every(k => decimal(r[k]))); if (Number(r.outstanding) > 0) outstanding = true; }
  // Clear keeps covered requirements listed with nothing outstanding; Blocked always has something outstanding.
  check((g.status === 'Blocked') === outstanding);
  return g as unknown as Gate;
}

const ACTIONS = ['readAdministrativeState', 'completeTechnical', 'requestAdministrative', 'reconcile', 'completeAdministrative'];
const REASONS = ['not_authorized', 'capability_disabled', 'route_unavailable', 'administrative_read_required', 'technical_closure_required', 'already_closed', 'already_requested',
  'administrative_destination_missing', 'internal_invoice_already_allocated', 'external_confirmation_required', 'reconciliation_not_available'];
const FLAGS = ['canReadAdministrativeState', 'canCompleteTechnical', 'canRequestAdministrative', 'mayRequestReconciliation', 'canCompleteAdministrative'] as const;
export type Actions = Readonly<{ orderId: string; commercialRevision: number; technicalClosure: TechnicalClosure | null; canReadAdministrativeState: boolean; canCompleteTechnical: boolean; canRequestAdministrative: boolean; mayRequestReconciliation: boolean; canCompleteAdministrative: boolean; actionReasons: readonly Readonly<{ action: string; code: string }>[]; administrativeRuntime: Readonly<{ kind: 'SimulatorV1' | 'Unavailable'; contractVersion: 0 | 1 }> }>;
export function parseActions(value: unknown, orderId: string): Actions {
  const a = record(value);
  const keys = ['orderId', 'commercialRevision', 'technicalClosure', ...FLAGS, 'actionReasons', 'administrativeRuntime'];
  check(Object.keys(a).length === keys.length && keys.every(k => k in a) && a.orderId === orderId && nonNegative(a.commercialRevision) && FLAGS.every(k => typeof a[k] === 'boolean'));
  const technicalClosure = a.technicalClosure === null ? null : parseTechnical(a.technicalClosure, orderId);
  // Without the exact administrative read nothing administrative may be offered; a closed order offers no technical closure.
  check(a.canReadAdministrativeState || !(a.canRequestAdministrative || a.mayRequestReconciliation || a.canCompleteAdministrative));
  check(!(technicalClosure && a.canCompleteTechnical));
  check(Array.isArray(a.actionReasons));
  for (const item of a.actionReasons as unknown[]) { const r = record(item); check(ACTIONS.includes(r.action as string) && REASONS.includes(r.code as string)); }
  const runtime = record(a.administrativeRuntime);
  check((runtime.kind === 'SimulatorV1' && runtime.contractVersion === 1) || (runtime.kind === 'Unavailable' && runtime.contractVersion === 0));
  return { ...a, technicalClosure } as unknown as Actions;
}

const STATUS = ['Open', 'TechnicallyClosed', 'AwaitingAdministrativeConfirmation', 'AdministrativelyConfirmed', 'AdministrativeRejected', 'AdministrativelyClosed'] as const;
export type ClosureState = Readonly<{ orderId: string; status: (typeof STATUS)[number]; technicalClosure: TechnicalClosure | null; request: AdministrativeRequest | null; administrativeClosure: AdministrativeClosure | null }>;
export function parseClosureState(value: unknown, orderId: string): ClosureState {
  const s = record(value);
  check(s.orderId === orderId && STATUS.includes(s.status as never));
  const technical = s.technicalClosure === null ? null : parseTechnical(s.technicalClosure, orderId);
  const request = s.request === null ? null : parseRequest(s.request, orderId);
  const closure = s.administrativeClosure === null ? null : parseAdministrativeClosure(s.administrativeClosure, orderId);
  // The pinned snapshot is exactly the frozen technical closure revision; the status is derived from the facts, never trusted alone.
  check(request === null || (technical !== null && request.summary.revision === technical.revision));
  const expected = { Open: [false, null, false], TechnicallyClosed: [true, null, false], AwaitingAdministrativeConfirmation: [true, 'Pending', false], AdministrativelyConfirmed: [true, 'Confirmed', false],
    AdministrativeRejected: [true, 'Rejected', false], AdministrativelyClosed: [true, 'Confirmed', true] }[s.status as (typeof STATUS)[number]];
  check((technical !== null) === expected[0] && (request?.status ?? null) === expected[1] && (closure !== null) === expected[2]);
  if (closure) check(request !== null && closure.requestId === request.id && closure.externalReference === request.externalReference);
  return { orderId, status: s.status as ClosureState['status'], technicalClosure: technical, request, administrativeClosure: closure };
}
